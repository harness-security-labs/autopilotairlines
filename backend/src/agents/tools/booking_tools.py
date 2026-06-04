import random
import string
from datetime import date

from langchain_core.tools import tool

from ..context import get_current_user_id
from ...constants import DOLLARS_PER_POINT


@tool
async def get_booking_quote_tool(
    flight_id: str, travel_date: str, cabin_class: str = "economy", num_passengers: int = 1
) -> str:
    """Get a price quote for booking a flight. Shows fare, available seats, and payment options WITHOUT making any changes.
    Call this first to show the user what the booking will cost. After user confirms, call create_booking to finalize.
    cabin_class options: economy, premium_economy, business."""
    from ...database import async_session
    from ...models.flight import Flight
    from ...models.loyalty import LoyaltyAccount
    from ...services.card_service import card_service
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from sqlalchemy import select
    from uuid import UUID
    from datetime import date as date_type

    user_id = get_current_user_id()

    async with async_session() as db:
        result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
        flight = result.scalar_one_or_none()
        if not flight:
            return f"Flight not found with ID {flight_id}."

        try:
            target_date = date_type.fromisoformat(travel_date)
        except ValueError:
            return f"Invalid date format: {travel_date}. Use YYYY-MM-DD."

        if not flight_operates_on(flight, target_date):
            return f"Flight {flight.flight_number} does not operate on {travel_date}."

        booked_count = await count_bookings_for_flight_date(db, flight.id, target_date)
        seats_left = max(0, flight.total_seats - booked_count)
        if seats_left < num_passengers:
            return f"Not enough seats. Only {seats_left} available on {flight.flight_number} for {travel_date}."

        base_price = compute_dynamic_price(flight.base_price, booked_count, flight.total_seats)

        if cabin_class == "premium_economy" and flight.cabin_classes:
            cabin_data = flight.cabin_classes if isinstance(flight.cabin_classes, dict) else {}
            if "premium_economy" in cabin_data:
                base_price = cabin_data["premium_economy"].get("price", base_price * 1.5)
            else:
                base_price = base_price * 1.5
        elif cabin_class == "business" and flight.cabin_classes:
            cabin_data = flight.cabin_classes if isinstance(flight.cabin_classes, dict) else {}
            if "business" in cabin_data:
                base_price = cabin_data["business"].get("price", base_price * 2.5)
            else:
                base_price = base_price * 2.5

        per_passenger = round(base_price, 2)
        total = round(per_passenger * num_passengers, 2)

        dep, arr = project_flight_to_date(flight, target_date)
        duration_min = int((arr - dep).total_seconds() / 60)
        duration_str = f"{duration_min // 60}h {duration_min % 60}m"

        loyalty_result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
        )
        loyalty = loyalty_result.scalar_one_or_none()
        points_available = loyalty.points if loyalty else 0
        max_points_for_booking = min(points_available, int(total / DOLLARS_PER_POINT))
        points_value = round(max_points_for_booking * DOLLARS_PER_POINT, 2)

    cards = []
    try:
        cards = await card_service.list_cards(user_id)
    except Exception:
        pass

    from ...routers.bookings import (
        STATIC_COUPONS, ADMIN_COUPONS, BULK_TIERS,
        _get_active_holiday_coupons, evaluate_conditions, TIER_ORDER,
    )

    user_tier = loyalty.tier if loyalty else "bronze"
    available_coupons = []

    async with async_session() as db2:
        for code, info in STATIC_COUPONS.items():
            err = await evaluate_conditions(
                info.get("conditions", {}), code, user_id, user_tier,
                flight, cabin_class, total, db2,
            )
            if not err:
                savings = round(total * info["discount_percent"] / 100, 2)
                available_coupons.append((code, info["discount_percent"], info["description"], savings))

        for ac in ADMIN_COUPONS:
            err = await evaluate_conditions(
                ac.get("conditions", {}), ac["code"], user_id, user_tier,
                flight, cabin_class, total, db2,
            )
            if not err:
                savings = round(total * ac["discount_percent"] / 100, 2)
                available_coupons.append((ac["code"], ac["discount_percent"], ac["description"], savings))

        holiday_coupons = _get_active_holiday_coupons()
        for code, info in holiday_coupons.items():
            savings = round(total * info["discount_percent"] / 100, 2)
            available_coupons.append((code, info["discount_percent"], info["description"], savings))

        for min_pax, discount, bulk_code, description in BULK_TIERS:
            if num_passengers >= min_pax:
                savings = round(total * discount / 100, 2)
                available_coupons.append((bulk_code, discount, description, savings))

    available_coupons.sort(key=lambda x: x[3], reverse=True)

    lines = [
        f"Booking Quote for {flight.flight_number}:",
        f"Route: {flight.origin} → {flight.destination}",
        f"Date: {travel_date} | {dep.strftime('%H:%M')} → {arr.strftime('%H:%M')} ({duration_str})",
        f"Aircraft: {flight.aircraft}",
        f"Cabin: {cabin_class.replace('_', ' ').title()}",
        f"Seats available: {seats_left}",
        f"",
        f"Fare breakdown:",
        f"  Per passenger: ${per_passenger:.2f}",
        f"  Passengers: {num_passengers}",
        f"  ---",
        f"  Total: ${total:.2f}",
        f"",
        f"Payment options:",
    ]

    if cards:
        lines.append(f"  Saved cards:")
        for c in cards:
            default_tag = " [DEFAULT]" if c["is_default"] else ""
            lines.append(f"    - {c['card_brand'].capitalize()} ••••{c['card_last_four']}{default_tag} (ID: {c['id']})")
    else:
        lines.append(f"  No saved cards. User needs to add a payment method.")

    if points_available > 0:
        lines.append(f"  Loyalty points: {points_available:,} available (worth ${points_available * DOLLARS_PER_POINT:.2f})")
        if points_value >= total:
            lines.append(f"  → Can cover full fare with {int(total / DOLLARS_PER_POINT):,} points")
        else:
            lines.append(f"  → Can offset up to ${points_value:.2f} from card charge")
    else:
        lines.append(f"  No loyalty points available.")

    if available_coupons:
        lines.append(f"")
        lines.append(f"Available coupons (best first):")
        for code, pct, desc, savings in available_coupons:
            lines.append(f"  - {code}: {pct}% off — {desc} (saves ${savings:.2f})")
        lines.append(f"  Suggest the best coupon to the user. Pass coupon_code to create_booking if they accept.")

    lines.append(f"")
    lines.append(f"Present this quote to the user. After confirmation, call create_booking then process_payment.")

    return "\n".join(lines)


@tool
async def create_booking_tool(
    flight_id: str, passenger_name: str, passenger_email: str,
    travel_date: str | None = None, cabin_class: str = "economy",
    coupon_code: str | None = None,
) -> str:
    """Create a new flight booking for a passenger. Call get_booking_quote first to show the user the price.
    After this tool succeeds, immediately process payment using process_payment with the returned PNR/booking_id.
    cabin_class options: economy, premium_economy, business. Optionally pass a validated coupon_code."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from sqlalchemy import select
    from uuid import UUID
    from datetime import date

    user_id = get_current_user_id()
    pnr = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    async with async_session() as db:
        result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
        flight = result.scalar_one_or_none()
        if not flight:
            return "Flight not found."

        target_date = date.fromisoformat(travel_date) if travel_date else None

        if target_date and not flight_operates_on(flight, target_date):
            return f"Flight {flight.flight_number} does not operate on {travel_date}."

        if target_date:
            booked_count = await count_bookings_for_flight_date(db, flight.id, target_date)
            seats_left = max(0, flight.total_seats - booked_count)
            if seats_left <= 0:
                return f"Flight {flight.flight_number} is fully booked on {travel_date}."
            price = compute_dynamic_price(flight.base_price, booked_count, flight.total_seats)
        else:
            price = flight.base_price

        if cabin_class == "premium_economy":
            price = round(price * 1.5, 2)
        elif cabin_class == "business":
            price = round(price * 2.5, 2)

        booking = Booking(
            user_id=UUID(user_id),
            flight_id=UUID(flight_id),
            pnr=pnr,
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            travel_date=target_date,
            cabin_class=cabin_class,
            coupon_code=coupon_code.upper() if coupon_code else None,
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)

        dep, arr = project_flight_to_date(flight, target_date) if target_date else (flight.departure, flight.arrival)

    lines = [
        f"Booking confirmed!",
        f"PNR: {pnr}",
        f"Booking ID: {str(booking.id)}",
        f"Flight: {flight.flight_number} ({flight.origin} → {flight.destination})",
        f"Date: {travel_date or 'not specified'}",
        f"Departure: {dep.strftime('%H:%M') if hasattr(dep, 'strftime') else dep}",
        f"Arrival: {arr.strftime('%H:%M') if hasattr(arr, 'strftime') else arr}",
        f"Passenger: {passenger_name} ({passenger_email})",
        f"Cabin: {cabin_class.replace('_', ' ').title()}",
        f"",
        f"Amount due: ${price:.2f}",
        f"Status: Confirmed (pending payment)",
        f"",
        f"NEXT STEP: Process payment of ${price:.2f} for booking {pnr} using process_payment tool.",
    ]

    return "\n".join(lines)


@tool
async def get_cancellation_quote_tool(booking_id: str) -> str:
    """Get a cancellation quote showing the refund amount, where it will be credited, and any fees.
    Call this BEFORE cancel_booking to show the user what they'll receive. After user confirms, call cancel_booking.
    If the flight is recurring and the user has multiple bookings on it, this will inform about all upcoming dates
    so you can ask whether to cancel just one date or all."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.payment import Payment
    from ...models.user import User
    from ...services.card_service import card_service
    from sqlalchemy import select, and_
    from uuid import UUID

    user_id = get_current_user_id()

    async with async_session() as db:
        try:
            uid = UUID(booking_id)
            result = await db.execute(select(Booking).where(Booking.id == uid))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id.upper()))

        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found."

        if booking.status == "cancelled":
            return f"Booking {booking.pnr} is already cancelled."

        if booking.status == "refunded":
            return f"Booking {booking.pnr} has already been refunded."

        flight_result = await db.execute(select(Flight).where(Flight.id == booking.flight_id))
        flight = flight_result.scalar_one_or_none()

        payment_result = await db.execute(
            select(Payment).where(Payment.booking_id == booking.id)
        )
        payment = payment_result.scalar_one_or_none()

        user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = user_result.scalar_one_or_none()
        user_tier = user.loyalty_tier.lower() if user and user.loyalty_tier else "bronze"

        other_bookings = []
        if flight and flight.days_of_week:
            other_result = await db.execute(
                select(Booking).where(and_(
                    Booking.flight_id == flight.id,
                    Booking.user_id == UUID(user_id),
                    Booking.status.in_(["confirmed", "checked_in"]),
                    Booking.id != booking.id,
                ))
            )
            other_bookings = list(other_result.scalars().all())

    refund_amount = payment.amount if payment else 0
    cancellation_fee = 0.0
    if user_tier in ("gold", "platinum"):
        cancellation_fee = 0.0
    elif refund_amount > 0:
        cancellation_fee = 0.0

    net_refund = refund_amount - cancellation_fee

    lines = [
        f"Cancellation Quote for PNR {booking.pnr}:",
        f"Flight: {flight.flight_number} ({flight.origin} → {flight.destination})" if flight else "Flight: N/A",
        f"Travel Date: {booking.travel_date.isoformat() if booking.travel_date else 'Not specified'}",
        f"Passenger: {booking.passenger_name}",
        f"Cabin: {(booking.cabin_class or 'economy').replace('_', ' ').title()}",
        f"Current Status: {booking.status.capitalize()}",
        f"",
    ]

    if flight and flight.days_of_week and other_bookings:
        lines.append(f"⚠ This is a recurring flight (operates on days: {flight.days_of_week}).")
        lines.append(f"You have {len(other_bookings) + 1} active bookings on this flight:")
        lines.append(f"  • {booking.travel_date.isoformat() if booking.travel_date else 'N/A'} — PNR {booking.pnr} (this one)")
        for ob in sorted(other_bookings, key=lambda b: b.travel_date or date.min):
            lines.append(f"  • {ob.travel_date.isoformat() if ob.travel_date else 'N/A'} — PNR {ob.pnr}")
        lines.append(f"")
        lines.append(f"Ask the user: cancel only {booking.travel_date.isoformat() if booking.travel_date else 'this booking'}, or cancel ALL dates?")
        lines.append(f"If all, call cancel_booking with cancel_all_recurring=true.")
        lines.append(f"")

    lines.append(f"Refund breakdown (this booking):")
    lines.append(f"  Original payment: ${refund_amount:.2f}")

    if cancellation_fee > 0:
        lines.append(f"  Cancellation fee: -${cancellation_fee:.2f}")
    else:
        lines.append(f"  Cancellation fee: $0.00 (waived)")

    lines.append(f"  ---")
    lines.append(f"  Net refund: ${net_refund:.2f}")
    lines.append(f"")

    if payment and payment.card_last_four:
        cards = []
        try:
            cards = await card_service.list_cards(user_id)
        except Exception:
            pass
        card_found = None
        for c in cards:
            if c["card_last_four"] == payment.card_last_four:
                card_found = c
                break
        if card_found:
            lines.append(f"Refund to: {card_found['card_brand'].capitalize()} ••••{card_found['card_last_four']}")
        else:
            lines.append(f"Refund to: Card ••••{payment.card_last_four}")
        lines.append(f"Processing time: Immediate credit upon confirmation")
    elif payment and payment.method == "points":
        points_back = int(refund_amount / DOLLARS_PER_POINT)
        lines.append(f"Refund to: Loyalty points ({points_back:,} points)")
        lines.append(f"Processing time: Immediate")
    else:
        lines.append(f"No payment on record — no refund to process.")

    lines.append(f"")
    lines.append(f"Present this to the user. After confirmation, call cancel_booking to finalize.")

    return "\n".join(lines)


@tool
async def cancel_booking_tool(booking_id: str, reason: str = "Customer requested cancellation", cancel_all_recurring: bool = False) -> str:
    """Cancel an existing booking and process the refund. Call get_cancellation_quote first to show the user what they'll receive.
    If the flight is recurring and the user wants to cancel all dates, set cancel_all_recurring=True."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.payment import Payment, RefundRecord
    from ...models.loyalty import LoyaltyAccount, LoyaltyTransaction
    from ...services.card_service import card_service
    from sqlalchemy import select, and_
    from uuid import UUID

    user_id = get_current_user_id()

    async with async_session() as db:
        try:
            uid = UUID(booking_id)
            result = await db.execute(select(Booking).where(Booking.id == uid))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id.upper()))

        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found."

        if booking.status == "cancelled":
            return f"Booking {booking.pnr} is already cancelled."

        bookings_to_cancel = [booking]

        if cancel_all_recurring:
            flight_result = await db.execute(select(Flight).where(Flight.id == booking.flight_id))
            flight = flight_result.scalar_one_or_none()
            if flight and flight.days_of_week:
                other_result = await db.execute(
                    select(Booking).where(and_(
                        Booking.flight_id == flight.id,
                        Booking.user_id == UUID(user_id),
                        Booking.status.in_(["confirmed", "checked_in"]),
                        Booking.id != booking.id,
                    ))
                )
                bookings_to_cancel.extend(other_result.scalars().all())

        total_refund = 0.0
        cancelled_pnrs = []

        for bk in bookings_to_cancel:
            if bk.status == "cancelled":
                continue

            payment_result = await db.execute(
                select(Payment).where(Payment.booking_id == bk.id)
            )
            payment = payment_result.scalar_one_or_none()

            refund_amount = payment.amount if payment else 0
            refund_method = None

            if refund_amount > 0 and payment:
                if payment.card_last_four:
                    cards = await card_service.list_cards(user_id)
                    for c in cards:
                        if c["card_last_four"] == payment.card_last_four:
                            await card_service.credit(
                                card_id=c["id"],
                                amount=refund_amount,
                                reference_id=str(bk.id),
                                description=f"Cancellation refund for {bk.pnr}",
                            )
                            refund_method = "card"
                            break
                elif payment.method == "points":
                    points_refunded = int(refund_amount / DOLLARS_PER_POINT)
                    refund_method = "points"
                    acct_result = await db.execute(
                        select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
                    )
                    account = acct_result.scalar_one_or_none()
                    if account:
                        account.points += points_refunded
                        db.add(LoyaltyTransaction(
                            account_id=account.id, points=points_refunded,
                            transaction_type="refund", source=f"Cancellation {bk.pnr}",
                        ))

            bk.status = "cancelled"
            total_refund += refund_amount
            cancelled_pnrs.append(bk.pnr)

            cancel_record = RefundRecord(
                booking_id=bk.id,
                user_id=UUID(user_id),
                action_type="cancellation",
                amount=0,
                reason=reason,
                refund_method=None,
                card_last_four=None,
                status="completed",
                pnr=bk.pnr,
            )
            db.add(cancel_record)

            if refund_amount > 0:
                refund_record = RefundRecord(
                    booking_id=bk.id,
                    user_id=UUID(user_id),
                    action_type="refund",
                    amount=refund_amount,
                    reason=f"Refund for cancellation",
                    refund_method=refund_method or "card",
                    card_last_four=payment.card_last_four if payment else None,
                    status="completed",
                    pnr=bk.pnr,
                )
                db.add(refund_record)

        await db.commit()

    if len(cancelled_pnrs) > 1:
        lines = [
            f"All {len(cancelled_pnrs)} bookings cancelled successfully.",
            f"PNRs: {', '.join(cancelled_pnrs)}",
            f"Status: Cancelled",
            f"",
        ]
    else:
        lines = [
            f"Booking cancelled successfully.",
            f"PNR: {booking.pnr}",
            f"Status: Cancelled",
            f"",
        ]

    if total_refund > 0:
        lines.append(f"Total refund: ${total_refund:.2f}")
        lines.append(f"Refund has been processed and credited immediately.")
    else:
        lines.append(f"No payment was on record — no refund to process.")

    return "\n".join(lines)


@tool
async def get_reschedule_quote_tool(pnr: str, new_date: str, flight_number: str) -> str:
    """Get a cost quote for rescheduling a booking. Shows price difference and fees WITHOUT making any changes.
    Call this first to show the user what the reschedule will cost. After user confirms and payment is processed, call reschedule_booking to finalize."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.user import User
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from sqlalchemy import select
    from uuid import UUID
    from datetime import date

    user_id = get_current_user_id()
    RESCHEDULE_FEE = 25.00
    FEE_WAIVED_TIERS = ("gold", "platinum")

    async with async_session() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.pnr == pnr.upper(),
                Booking.user_id == UUID(user_id),
            )
        )
        booking = result.scalar_one_or_none()

        if not booking:
            return f"No booking found with PNR {pnr} for your account."

        if booking.status == "cancelled":
            return f"Booking {pnr} is cancelled and cannot be rescheduled."

        user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = user_result.scalar_one_or_none()
        user_tier = user.loyalty_tier.lower() if user and user.loyalty_tier else "bronze"
        fee_waived = user_tier in FEE_WAIVED_TIERS

        old_flight_result = await db.execute(
            select(Flight).where(Flight.id == booking.flight_id)
        )
        old_flight = old_flight_result.scalar_one_or_none()

        old_date = booking.travel_date
        if old_flight and old_date:
            old_booked = await count_bookings_for_flight_date(db, old_flight.id, old_date)
            original_price = compute_dynamic_price(old_flight.base_price, old_booked, old_flight.total_seats)
        else:
            original_price = old_flight.base_price if old_flight else 0

        flight_result = await db.execute(
            select(Flight).where(Flight.flight_number == flight_number.upper())
        )
        new_flight = flight_result.scalar_one_or_none()
        if not new_flight:
            return f"Flight {flight_number} not found."

        try:
            target_date = date.fromisoformat(new_date)
        except ValueError:
            return f"Invalid date format: {new_date}. Use YYYY-MM-DD."

        if not flight_operates_on(new_flight, target_date):
            return f"Flight {flight_number} does not operate on {new_date}."

        booked_count = await count_bookings_for_flight_date(db, new_flight.id, target_date)
        seats_left = max(0, new_flight.total_seats - booked_count)
        if seats_left <= 0:
            return f"Flight {flight_number} is fully booked on {new_date}."

        new_price = compute_dynamic_price(new_flight.base_price, booked_count, new_flight.total_seats)
        price_difference = new_price - original_price
        reschedule_fee = 0 if fee_waived else RESCHEDULE_FEE
        total_due = max(0, price_difference) + reschedule_fee

        dep, arr = project_flight_to_date(new_flight, target_date)

        lines = [
            f"Reschedule Quote for PNR {pnr}:",
            f"Current: {old_flight.flight_number if old_flight else 'N/A'} on {old_date} (${original_price:.2f})",
            f"New: {new_flight.flight_number} on {target_date} (${new_price:.2f})",
            f"Departure: {dep.strftime('%H:%M')} | Arrival: {arr.strftime('%H:%M')}",
            f"Seats available: {seats_left}",
            f"",
            f"Cost breakdown:",
            f"  Original fare: ${original_price:.2f}",
            f"  New fare: ${new_price:.2f}",
        ]

        if price_difference > 0:
            lines.append(f"  Fare difference: +${price_difference:.2f}")
        elif price_difference < 0:
            lines.append(f"  Fare difference: -${abs(price_difference):.2f} (credit)")
        else:
            lines.append(f"  Fare difference: $0.00")

        if fee_waived:
            lines.append(f"  Reschedule fee: $0.00 (waived — {user_tier.capitalize()} tier)")
        else:
            lines.append(f"  Reschedule fee: ${RESCHEDULE_FEE:.2f}")

        lines.append(f"  ---")
        if total_due > 0:
            lines.append(f"  Total to pay: ${total_due:.2f}")
        elif price_difference < 0 and reschedule_fee == 0:
            lines.append(f"  Credit back: ${abs(price_difference):.2f}")
            lines.append(f"  Credit will be refunded to the original payment card immediately upon confirmation.")
        else:
            lines.append(f"  Total to pay: $0.00")

        return "\n".join(lines)


@tool
async def reschedule_booking_tool(pnr: str, new_date: str, flight_number: str, payment_transaction_id: str | None = None) -> str:
    """Finalize a booking reschedule. If the reschedule quote shows a total > $0, payment MUST be processed first
    and payment_transaction_id provided. If the total is $0 (fee waived, no fare difference), payment_transaction_id can be omitted.
    Flow: get_reschedule_quote → (if total > $0) process_payment → reschedule_booking."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.payment import Payment
    from ...models.user import User
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from sqlalchemy import select
    from uuid import UUID
    from datetime import date

    user_id = get_current_user_id()
    RESCHEDULE_FEE = 25.00
    FEE_WAIVED_TIERS = ("gold", "platinum")

    async with async_session() as db:
        user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = user_result.scalar_one_or_none()
        user_tier = user.loyalty_tier.lower() if user and user.loyalty_tier else "bronze"
        fee_waived = user_tier in FEE_WAIVED_TIERS

        result = await db.execute(
            select(Booking).where(
                Booking.pnr == pnr.upper(),
                Booking.user_id == UUID(user_id),
            )
        )
        booking = result.scalar_one_or_none()

        if not booking:
            return f"No booking found with PNR {pnr} for your account."

        if booking.status == "cancelled":
            return f"Booking {pnr} is cancelled and cannot be rescheduled."

        flight_result = await db.execute(
            select(Flight).where(Flight.flight_number == flight_number.upper())
        )
        new_flight = flight_result.scalar_one_or_none()
        if not new_flight:
            return f"Flight {flight_number} not found."

        try:
            target_date = date.fromisoformat(new_date)
        except ValueError:
            return f"Invalid date format: {new_date}. Use YYYY-MM-DD."

        if not flight_operates_on(new_flight, target_date):
            return f"Flight {flight_number} does not operate on {new_date}."

        booked_count = await count_bookings_for_flight_date(db, new_flight.id, target_date)
        seats_left = max(0, new_flight.total_seats - booked_count)
        if seats_left <= 0:
            return f"Flight {flight_number} is fully booked on {new_date}."

        old_flight_result = await db.execute(
            select(Flight).where(Flight.id == booking.flight_id)
        )
        old_flight = old_flight_result.scalar_one_or_none()
        old_flight_number = old_flight.flight_number if old_flight else "Unknown"
        old_date = booking.travel_date

        if old_flight and old_date:
            old_booked = await count_bookings_for_flight_date(db, old_flight.id, old_date)
            original_price = compute_dynamic_price(old_flight.base_price, old_booked, old_flight.total_seats)
        else:
            original_price = old_flight.base_price if old_flight else 0

        new_price = compute_dynamic_price(new_flight.base_price, booked_count, new_flight.total_seats)
        price_difference = new_price - original_price
        reschedule_fee = 0 if fee_waived else RESCHEDULE_FEE
        total_due = max(0, price_difference) + reschedule_fee

        if total_due > 0 and not payment_transaction_id:
            return (
                f"Payment required before rescheduling. Total due: ${total_due:.2f}. "
                f"Process payment first using process_payment, then call reschedule_booking with the transaction ID."
            )

        if payment_transaction_id:
            payment_result = await db.execute(
                select(Payment).where(Payment.transaction_id == payment_transaction_id)
            )
            payment = payment_result.scalar_one_or_none()
            if not payment:
                return f"Payment not found with transaction ID {payment_transaction_id}. Process payment before rescheduling."

        credit_amount = abs(price_difference) if price_difference < 0 and reschedule_fee == 0 else 0

        if credit_amount > 0:
            from ...services.card_service import card_service

            payment_result = await db.execute(
                select(Payment).where(Payment.booking_id == booking.id)
            )
            original_payment = payment_result.scalar_one_or_none()
            credited_card = None

            if original_payment and original_payment.card_last_four:
                cards = await card_service.list_cards(user_id)
                for c in cards:
                    if c["card_last_four"] == original_payment.card_last_four:
                        await card_service.credit(
                            card_id=c["id"],
                            amount=credit_amount,
                            reference_id=str(booking.id),
                            description=f"Reschedule credit for {pnr}",
                        )
                        credited_card = c
                        break

        booking.travel_date = target_date
        booking.flight_id = new_flight.id
        await db.commit()

        dep, arr = project_flight_to_date(new_flight, target_date)

        result_lines = [
            f"Booking rescheduled successfully!",
            f"PNR: {pnr}",
            f"Previous: {old_flight_number} on {old_date}",
            f"New: {new_flight.flight_number} ({new_flight.origin} → {new_flight.destination}) on {target_date.isoformat()}",
            f"Departure: {dep.strftime('%H:%M')} | Arrival: {arr.strftime('%H:%M')}",
        ]
        if total_due > 0:
            result_lines.append(f"Paid: ${total_due:.2f} (Transaction: {payment_transaction_id})")
        elif credit_amount > 0:
            result_lines.append(f"Credit: ${credit_amount:.2f} refunded to original payment card")
            if credited_card:
                result_lines.append(f"Credited to: {credited_card['card_brand'].capitalize()} ••••{credited_card['card_last_four']}")
            result_lines.append(f"The credit has been applied immediately and is available on your card now.")
        else:
            result_lines.append(f"No charge (fee waived for {user_tier.capitalize()} tier)")

        return "\n".join(result_lines)


@tool
async def get_connecting_flight_quote_tool(
    pnr: str, destination: str, preferred_time: str | None = None
) -> str:
    """Get a quote for a connecting flight from an existing booking's destination. Shows available options,
    prices, and payment methods WITHOUT booking anything. Call this first to present options to the user.
    After user confirms, call book_connecting_flight to finalize."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.loyalty import LoyaltyAccount
    from ...services.card_service import card_service
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from .flight_tools import resolve_iata
    from sqlalchemy import select, and_
    from uuid import UUID
    from datetime import date, timedelta

    destination = resolve_iata(destination)
    user_id = get_current_user_id()

    async with async_session() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.pnr == pnr.upper(),
                Booking.user_id == UUID(user_id),
            )
        )
        existing_booking = result.scalar_one_or_none()

        if not existing_booking:
            return f"No booking found with PNR {pnr} for your account."

        if existing_booking.status == "cancelled":
            return f"Booking {pnr} is cancelled. Cannot add a connecting flight to a cancelled booking."

        flight_result = await db.execute(
            select(Flight).where(Flight.id == existing_booking.flight_id)
        )
        first_leg = flight_result.scalar_one_or_none()
        if not first_leg:
            return "Could not retrieve the original flight details."

        connection_origin = first_leg.destination
        travel_date = existing_booking.travel_date or first_leg.departure.date()

        if preferred_time and preferred_time.lower() == "next_day":
            travel_date = travel_date + timedelta(days=1)

        _, first_arr = project_flight_to_date(first_leg, travel_date)

        connecting_flights = await db.execute(
            select(Flight).where(
                and_(
                    Flight.origin == connection_origin,
                    Flight.destination == destination.upper(),
                )
            )
        )
        available = connecting_flights.scalars().all()
        available = [f for f in available if flight_operates_on(f, travel_date)]

        if not available:
            return (
                f"No connecting flights found from {connection_origin} to {destination} "
                f"on {travel_date.isoformat()}."
            )

        loyalty_result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
        )
        loyalty = loyalty_result.scalar_one_or_none()
        points_available = loyalty.points if loyalty else 0

        flight_options = []
        for f in available[:5]:
            booked_count = await count_bookings_for_flight_date(db, f.id, travel_date)
            price = compute_dynamic_price(f.base_price, booked_count, f.total_seats)
            seats_left = max(0, f.total_seats - booked_count)
            dep, arr = project_flight_to_date(f, travel_date)
            duration_min = int((arr - dep).total_seconds() / 60)
            flight_options.append({
                "flight": f,
                "price": round(price, 2),
                "seats": seats_left,
                "dep": dep,
                "arr": arr,
                "duration": f"{duration_min // 60}h {duration_min % 60}m",
            })

    cards = []
    try:
        cards = await card_service.list_cards(user_id)
    except Exception:
        pass

    lines = [
        f"Connecting Flight Quote:",
        f"Original booking: PNR {pnr} — {first_leg.origin} → {first_leg.destination}",
        f"First leg arrives: {first_arr.strftime('%H:%M')} at {connection_origin}",
        f"Connection: {connection_origin} → {destination} on {travel_date.isoformat()}",
        f"Cabin: {(existing_booking.cabin_class or 'economy').replace('_', ' ').title()}",
        f"Passenger: {existing_booking.passenger_name}",
        f"",
        f"Available connecting flights:",
    ]

    for i, opt in enumerate(flight_options, 1):
        f = opt["flight"]
        lines.append(
            f"  {i}. {f.flight_number} | {opt['dep'].strftime('%H:%M')} → {opt['arr'].strftime('%H:%M')} "
            f"({opt['duration']}) | ${opt['price']:.2f} | {opt['seats']} seats"
        )

    lines.append(f"")
    lines.append(f"Payment options:")
    if cards:
        lines.append(f"  Saved cards:")
        for c in cards:
            default_tag = " [DEFAULT]" if c["is_default"] else ""
            lines.append(f"    - {c['card_brand'].capitalize()} ••••{c['card_last_four']}{default_tag} (ID: {c['id']})")
    else:
        lines.append(f"  No saved cards.")

    if points_available > 0:
        lines.append(f"  Loyalty points: {points_available:,} available (worth ${points_available * DOLLARS_PER_POINT:.2f})")
    else:
        lines.append(f"  No loyalty points available.")

    lines.append(f"")
    lines.append(f"Present options to user. After they pick a flight and confirm, call book_connecting_flight.")

    return "\n".join(lines)


@tool
async def book_connecting_flight_tool(
    pnr: str, destination: str, preferred_time: str | None = None, flight_number: str | None = None
) -> str:
    """Book a connecting flight from an existing booking's destination. Call get_connecting_flight_quote first.
    Optionally specify flight_number to pick a specific flight from the quote options."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from .flight_tools import resolve_iata
    from sqlalchemy import select, and_
    from uuid import UUID
    from datetime import date, timedelta

    destination = resolve_iata(destination)
    user_id = get_current_user_id()

    async with async_session() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.pnr == pnr.upper(),
                Booking.user_id == UUID(user_id),
            )
        )
        existing_booking = result.scalar_one_or_none()

        if not existing_booking:
            return f"No booking found with PNR {pnr} for your account."

        if existing_booking.status == "cancelled":
            return f"Booking {pnr} is cancelled. Cannot add a connecting flight to a cancelled booking."

        flight_result = await db.execute(
            select(Flight).where(Flight.id == existing_booking.flight_id)
        )
        first_leg = flight_result.scalar_one_or_none()
        if not first_leg:
            return "Could not retrieve the original flight details."

        connection_origin = first_leg.destination
        travel_date = existing_booking.travel_date or first_leg.departure.date()

        if preferred_time and preferred_time.lower() == "next_day":
            travel_date = travel_date + timedelta(days=1)

        if flight_number:
            connecting_flights = await db.execute(
                select(Flight).where(
                    and_(
                        Flight.flight_number == flight_number.upper(),
                        Flight.origin == connection_origin,
                        Flight.destination == destination.upper(),
                    )
                )
            )
        else:
            connecting_flights = await db.execute(
                select(Flight).where(
                    and_(
                        Flight.origin == connection_origin,
                        Flight.destination == destination.upper(),
                    )
                )
            )
        available = connecting_flights.scalars().all()
        available = [f for f in available if flight_operates_on(f, travel_date)]

        if not available:
            return (
                f"No connecting flights found from {connection_origin} to {destination} "
                f"on {travel_date.isoformat()}."
            )

        best = available[0]
        booked_count = await count_bookings_for_flight_date(db, best.id, travel_date)
        price = compute_dynamic_price(best.base_price, booked_count, best.total_seats)
        seats_left = max(0, best.total_seats - booked_count)

        dep, arr = project_flight_to_date(best, travel_date)
        duration_min = int((arr - dep).total_seconds() / 60)
        duration_str = f"{duration_min // 60}h {duration_min % 60}m"

        new_pnr = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        connecting_booking = Booking(
            user_id=UUID(user_id),
            flight_id=best.id,
            pnr=new_pnr,
            passenger_name=existing_booking.passenger_name,
            passenger_email=existing_booking.passenger_email,
            cabin_class=existing_booking.cabin_class or "economy",
            travel_date=travel_date,
        )
        db.add(connecting_booking)
        await db.commit()
        await db.refresh(connecting_booking)

    lines = [
        f"Connecting flight booked successfully!",
        f"",
        f"Itinerary:",
        f"  Leg 1: PNR {pnr} — {first_leg.flight_number} {first_leg.origin} → {first_leg.destination}",
        f"  Leg 2: PNR {new_pnr} — {best.flight_number} {connection_origin} → {destination}",
        f"",
        f"Connection details:",
        f"  Flight: {best.flight_number}",
        f"  Route: {connection_origin} → {destination}",
        f"  Date: {travel_date.isoformat()}",
        f"  Departure: {dep.strftime('%H:%M')} | Arrival: {arr.strftime('%H:%M')} ({duration_str})",
        f"  Cabin: {(existing_booking.cabin_class or 'economy').replace('_', ' ').title()}",
        f"  Passenger: {existing_booking.passenger_name}",
        f"  Fare: ${price:.2f}",
        f"",
        f"  Booking ID: {str(connecting_booking.id)}",
        f"  PNR: {new_pnr}",
        f"  Status: Confirmed",
    ]

    return "\n".join(lines)
