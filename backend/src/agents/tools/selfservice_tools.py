import json
from datetime import date, datetime, timedelta
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select, func

from ..context import get_current_user_id
from ...constants import DOLLARS_PER_POINT


@tool
async def get_my_bookings_tool(filter: str = "upcoming") -> str:
    """Get bookings for the current authenticated user.
    filter options: 'upcoming' (default, shows future confirmed bookings), 'past' (shows past/completed bookings), 'cancelled' (shows only cancelled bookings), 'all' (shows everything).
    Use 'past' when user asks about past/previous/old/history bookings. Use 'cancelled' when user asks about cancelled/refunded bookings. Use 'all' when user wants to see everything."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from sqlalchemy import case

    user_id = get_current_user_id()
    today = date.today()

    async with async_session() as db:
        query = (
            select(Booking, Flight)
            .join(Flight, Booking.flight_id == Flight.id)
            .where(Booking.user_id == UUID(user_id))
        )

        if filter == "upcoming":
            query = query.where(
                Booking.travel_date >= today,
                Booking.status == "confirmed",
            ).order_by(Booking.travel_date.asc())
        elif filter == "past":
            query = query.where(
                (Booking.travel_date < today) | (Booking.status != "confirmed")
            ).order_by(Booking.travel_date.desc().nullslast())
        elif filter == "cancelled":
            query = query.where(
                Booking.status == "cancelled"
            ).order_by(Booking.created_at.desc())
        else:
            query = query.order_by(
                case(
                    (Booking.status == "confirmed", 0),
                    else_=1,
                ),
                Booking.travel_date.desc().nullslast(),
                Booking.created_at.desc(),
            )

        result = await db.execute(query.limit(10))
        rows = result.all()

    if not rows:
        if filter == "upcoming":
            return "You don't have any upcoming bookings."
        elif filter == "past":
            return "You don't have any past bookings."
        elif filter == "cancelled":
            return "You don't have any cancelled bookings."
        return "You don't have any bookings yet."

    bookings = []
    lines = []
    for booking, flight in rows:
        b = {
            "id": str(booking.id),
            "pnr": booking.pnr,
            "flight_number": flight.flight_number,
            "origin": flight.origin,
            "destination": flight.destination,
            "travel_date": booking.travel_date.isoformat() if booking.travel_date else None,
            "status": booking.status,
            "cabin_class": booking.cabin_class or "economy",
        }
        bookings.append(b)
        lines.append(
            f"- PNR: {b['pnr']} | {b['flight_number']} {b['origin']}->{b['destination']} | "
            f"{b['travel_date'] or 'no date'} | {b['status']} | {b['cabin_class']}"
        )

    label = "upcoming" if filter == "upcoming" else "past" if filter == "past" else ""
    text = f"Found {len(bookings)} {label} booking(s):\n" + "\n".join(lines)
    action = f"\n\n<!--ACTION:booking_list{json.dumps(bookings)}-->"
    return text + action


@tool
async def get_booking_details_tool(pnr: str) -> str:
    """Look up booking details by PNR code. Returns flight info, passenger details, and booking status.
    Use when a customer asks about a specific booking by PNR or confirmation code."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight

    async with async_session() as db:
        result = await db.execute(
            select(Booking).where(Booking.pnr == pnr.upper())
        )
        booking = result.scalar_one_or_none()

        if not booking:
            return f"No booking found with PNR {pnr}."

        flight_result = await db.execute(
            select(Flight).where(Flight.id == booking.flight_id)
        )
        flight = flight_result.scalar_one_or_none()

    info = {
        "pnr": booking.pnr,
        "status": booking.status,
        "passenger_name": booking.passenger_name,
        "passenger_email": booking.passenger_email,
        "cabin_class": booking.cabin_class or "economy",
        "travel_date": booking.travel_date.isoformat() if booking.travel_date else None,
        "flight_number": flight.flight_number if flight else None,
        "origin": flight.origin if flight else None,
        "destination": flight.destination if flight else None,
        "departure": flight.departure.strftime("%H:%M") if flight else None,
        "arrival": flight.arrival.strftime("%H:%M") if flight else None,
        "aircraft": flight.aircraft if flight else None,
    }

    lines = [
        f"Booking {booking.pnr} — {booking.status.upper()}",
        f"Passenger: {booking.passenger_name} ({booking.passenger_email})",
        f"Class: {(booking.cabin_class or 'economy').replace('_', ' ').title()}",
    ]
    if booking.travel_date:
        lines.append(f"Travel Date: {booking.travel_date.isoformat()}")
    if flight:
        lines.append(f"Flight: {flight.flight_number} {flight.origin} → {flight.destination}")
        lines.append(f"Departure: {flight.departure.strftime('%H:%M')} | Arrival: {flight.arrival.strftime('%H:%M')}")
        lines.append(f"Aircraft: {flight.aircraft}")

    text = "\n".join(lines)
    action = f"\n\n<!--ACTION:booking_info{json.dumps(info)}-->"
    return text + action


@tool
async def validate_coupon_tool(
    code: str,
    flight_id: str | None = None,
    cabin_class: str | None = None,
    subtotal: float | None = None,
    passengers: int | None = None,
) -> str:
    """Validate a coupon code for the current user. Optionally provide flight_id, cabin_class, subtotal, and passenger count for full condition checking."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.user import User
    from ...routers.bookings import (
        STATIC_COUPONS, ADMIN_COUPONS, BULK_TIERS,
        _get_active_holiday_coupons, _get_bulk_coupon, evaluate_conditions,
    )

    user_id = get_current_user_id()
    code_upper = code.upper()

    async with async_session() as db:
        user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = user_result.scalar_one_or_none()
        user_tier = user.loyalty_tier if user else "bronze"

        flight = None
        if flight_id:
            flight_result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
            flight = flight_result.scalar_one_or_none()

        if code_upper in STATIC_COUPONS:
            coupon = STATIC_COUPONS[code_upper]
            failure = await evaluate_conditions(
                coupon.get("conditions", {}), code_upper, user_id, user_tier,
                flight, cabin_class, subtotal, db,
            )
            if failure:
                result = {"valid": False, "code": code_upper, "discount_percent": 0, "description": failure}
            else:
                result = {"valid": True, "code": code_upper, "discount_percent": coupon["discount_percent"], "description": coupon["description"]}
            return json.dumps(result) + f"\n\n<!--ACTION:coupon_result{json.dumps(result)}-->"

        holiday_coupons = _get_active_holiday_coupons()
        if code_upper in holiday_coupons:
            info = holiday_coupons[code_upper]
            result = {"valid": True, "code": code_upper, "discount_percent": info["discount_percent"], "description": info["description"]}
            return json.dumps(result) + f"\n\n<!--ACTION:coupon_result{json.dumps(result)}-->"

        bulk = _get_bulk_coupon(code_upper)
        if bulk:
            pax = passengers or 1
            if pax >= bulk["min_passengers"]:
                result = {"valid": True, "code": code_upper, "discount_percent": bulk["discount_percent"], "description": bulk["description"]}
            else:
                result = {"valid": False, "code": code_upper, "discount_percent": 0, "description": f"Need at least {bulk['min_passengers']} passengers (you have {pax})"}
            return json.dumps(result) + f"\n\n<!--ACTION:coupon_result{json.dumps(result)}-->"

        today = date.today()
        for ac in ADMIN_COUPONS:
            if ac["code"].upper() == code_upper:
                if ac.get("valid_from") and today < date.fromisoformat(ac["valid_from"]):
                    break
                if ac.get("valid_until") and today > date.fromisoformat(ac["valid_until"]):
                    break
                failure = await evaluate_conditions(
                    ac.get("conditions", {}), code_upper, user_id, user_tier,
                    flight, cabin_class, subtotal, db,
                )
                if failure:
                    result = {"valid": False, "code": code_upper, "discount_percent": 0, "description": failure}
                else:
                    result = {"valid": True, "code": code_upper, "discount_percent": ac["discount_percent"], "description": ac["description"]}
                return json.dumps(result) + f"\n\n<!--ACTION:coupon_result{json.dumps(result)}-->"

        result = {"valid": False, "code": code_upper, "discount_percent": 0, "description": "Invalid coupon code"}
        return json.dumps(result) + f"\n\n<!--ACTION:coupon_result{json.dumps(result)}-->"


@tool
async def check_flight_status_tool(flight_number: str | None = None, flight_id: str | None = None) -> str:
    """Check the real-time status of a flight by flight number (e.g. AP101) or flight ID."""
    from ...database import async_session
    from ...models.flight import Flight
    from ...models.booking import Booking

    user_id = get_current_user_id()

    async with async_session() as db:
        if flight_id:
            result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
        elif flight_number:
            result = await db.execute(
                select(Flight).where(Flight.flight_number == flight_number.upper())
            )
        else:
            return "Please provide a flight number (e.g. AP101) or flight ID."

        flight = result.scalar_one_or_none()
        if not flight:
            return f"Flight not found."

        booking_result = await db.execute(
            select(Booking).where(
                Booking.user_id == UUID(user_id),
                Booking.flight_id == flight.id,
                Booking.status != "cancelled",
            )
        )
        user_booking = booking_result.scalar_one_or_none()

    info = (
        f"Flight: {flight.flight_number}\n"
        f"Route: {flight.origin} -> {flight.destination}\n"
        f"Status: {flight.status}\n"
        f"Departure: {flight.departure}\n"
        f"Arrival: {flight.arrival}\n"
        f"Aircraft: {flight.aircraft}\n"
        f"Available Seats: {flight.available_seats}/{flight.total_seats}"
    )
    if user_booking:
        info += f"\n\nYou have a booking on this flight (PNR: {user_booking.pnr}, Status: {user_booking.status})"

    return info


@tool
async def lookup_policy_tool(topic: str) -> str:
    """Look up airline policy information. Available topics: refund, baggage, loyalty, architecture."""
    from ...services.saas.autodocs import DOCUMENTS

    topic_map = {
        "refund": "policies/refund.md",
        "baggage": "policies/baggage.md",
        "loyalty": "policies/loyalty.md",
        "architecture": "internal/architecture.md",
    }

    path = topic_map.get(topic.lower().strip())
    if not path:
        for key, doc_path in topic_map.items():
            if key in topic.lower():
                path = doc_path
                break

    if not path:
        return f"No policy found for '{topic}'. Available topics: refund, baggage, loyalty"

    content = DOCUMENTS.get(path)
    if not content:
        return f"Document not found: {path}"
    return content


@tool
async def get_my_loyalty_tool() -> str:
    """Check the current user's loyalty points balance, tier, and recent transactions. Use when user asks about 'my points', 'my tier', 'my loyalty status'."""
    from ...database import async_session
    from ...models.loyalty import LoyaltyAccount, LoyaltyTransaction

    user_id = get_current_user_id()

    async with async_session() as db:
        result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
        )
        account = result.scalar_one_or_none()

        if not account:
            return "You don't have a loyalty account yet. Book a flight to get started!"

        txn_result = await db.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.account_id == account.id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .limit(10)
        )
        transactions = txn_result.scalars().all()

    points_value = account.points * DOLLARS_PER_POINT
    info = {
        "points": account.points,
        "tier": account.tier,
        "points_value": round(points_value, 2),
        "tier_expiry": account.tier_expiry.isoformat() if account.tier_expiry else None,
    }

    lines = [
        f"Loyalty Status:",
        f"  Points: {account.points:,} (worth ${points_value:.2f})",
        f"  Tier: {account.tier.capitalize()}",
    ]
    if account.tier_expiry:
        lines.append(f"  Tier Expiry: {account.tier_expiry.strftime('%b %d, %Y')}")

    if transactions:
        lines.append(f"\nRecent Transactions:")
        for txn in transactions[:5]:
            sign = "+" if txn.points > 0 else ""
            lines.append(f"  {sign}{txn.points} pts — {txn.source} ({txn.transaction_type})")

    text = "\n".join(lines)
    action = f"\n\n<!--ACTION:loyalty_info{json.dumps(info)}-->"
    return text + action


@tool
async def generate_coupon_tool(discount_percent: int, reason: str) -> str:
    """Generate a one-time discount coupon for the current user as a goodwill gesture. Specify the discount percentage (5-25) and the reason for issuing it."""
    import random
    import string
    from ...routers.bookings import ADMIN_COUPONS

    user_id = get_current_user_id()
    code = "SORRY" + "".join(random.choices(string.digits, k=4))
    discount = max(5, min(25, discount_percent))

    ADMIN_COUPONS.append({
        "code": code,
        "discount_percent": discount,
        "description": f"{discount}% off — issued for: {reason}",
        "valid_from": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "conditions": {"user_id": user_id},
        "source": "ai_agent",
        "issued_to": user_id,
    })

    result = {"valid": True, "code": code, "discount_percent": discount, "description": f"{discount}% off your next booking (valid 30 days)"}
    return f"Coupon generated: {code} ({discount}% off, valid 30 days)\n\n<!--ACTION:coupon_result{json.dumps(result)}-->"


@tool
async def get_refund_history_tool(pnr: str | None = None) -> str:
    """Get refund and cancellation history for the current user, optionally filtered by PNR.
    Shows all refund/cancellation records with amounts, dates, and reasons."""
    from ...database import async_session
    from ...models.payment import RefundRecord
    from sqlalchemy import select

    user_id = get_current_user_id()

    async with async_session() as db:
        query = select(RefundRecord).where(RefundRecord.user_id == UUID(user_id))
        if pnr:
            query = query.where(RefundRecord.pnr == pnr.upper())
        query = query.order_by(RefundRecord.processed_at.desc()).limit(10)

        result = await db.execute(query)
        records = result.scalars().all()

    if not records:
        if pnr:
            return f"No refund or cancellation records found for PNR {pnr.upper()}."
        return "You don't have any refund or cancellation history."

    lines = [f"Found {len(records)} record(s):"]
    for r in records:
        date_str = r.processed_at.strftime("%Y-%m-%d %H:%M") if r.processed_at else "unknown"
        method_str = ""
        if r.refund_method == "card" and r.card_last_four:
            method_str = f" → card ••••{r.card_last_four}"
        elif r.refund_method == "points":
            method_str = " → loyalty points"
        lines.append(
            f"- [{r.action_type.upper()}] PNR: {r.pnr} | ${r.amount:.2f}{method_str} | "
            f"{r.status} | {date_str}"
            + (f" | Reason: {r.reason}" if r.reason else "")
        )

    return "\n".join(lines)
