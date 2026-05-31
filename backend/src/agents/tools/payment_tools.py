from langchain_core.tools import tool

from ..context import get_current_user_id


@tool
async def get_payment_methods_tool() -> str:
    """Get the current user's saved payment methods. Returns card brand, last four digits, expiry, and whether it's the default method."""
    from ...services.card_service import card_service

    user_id = get_current_user_id()
    cards = await card_service.list_cards(user_id)

    if not cards:
        return "No saved payment methods found. Ask the user to add a payment method via the app or API (POST /api/v1/payment-methods)."

    lines = [f"Saved payment methods ({len(cards)}):"]
    for c in cards:
        default_tag = " [DEFAULT]" if c["is_default"] else ""
        lines.append(
            f"- ID: {c['id']} | {c['card_brand'].capitalize()} ••••{c['card_last_four']} | "
            f"Exp: {c['expiry_month']:02d}/{c['expiry_year']}{default_tag}"
        )
    return "\n".join(lines)


@tool
async def process_payment_tool(
    booking_id: str,
    amount: float,
    payment_method_id: str | None = None,
    points_used: int = 0,
) -> str:
    """Process payment for a booking using a saved payment method and/or loyalty points.
    Provide booking_id (UUID or PNR), amount in USD.
    Optionally provide payment_method_id (from get_payment_methods) and/or points_used for loyalty redemption.
    If both are provided, points offset the card charge. If only points_used covers the full amount, no card is needed."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.payment import Payment
    from ...models.loyalty import LoyaltyAccount, LoyaltyTransaction
    from ...services.card_service import card_service
    from sqlalchemy import select
    from uuid import UUID
    import uuid as uuid_mod

    DOLLARS_PER_POINT = 0.01
    POINTS_PER_DOLLAR = 10
    user_id = get_current_user_id()

    async with async_session() as db:
        try:
            result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id.upper()))
        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found. Cannot process payment."

        card_info = None
        if payment_method_id:
            cards = await card_service.list_cards(user_id)
            for c in cards:
                if c["id"] == payment_method_id:
                    card_info = c
                    break
            if not card_info:
                return "Payment method not found. Use get_payment_methods to see available options."

        points_discount = 0.0
        account = None
        if points_used > 0:
            acct_result = await db.execute(
                select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
            )
            account = acct_result.scalar_one_or_none()
            if not account or account.points < points_used:
                available = account.points if account else 0
                return f"Insufficient loyalty points. Available: {available:,}"
            points_discount = round(points_used * DOLLARS_PER_POINT, 2)
            if points_discount > amount:
                points_used = int(amount / DOLLARS_PER_POINT)
                points_discount = round(points_used * DOLLARS_PER_POINT, 2)
            account.points -= points_used
            db.add(LoyaltyTransaction(
                account_id=account.id, points=-points_used,
                transaction_type="payment", source=f"Booking {booking.pnr}",
            ))

        card_amount = round(amount - points_discount, 2)

        if card_amount > 0 and not payment_method_id:
            return (
                f"Card payment of ${card_amount:.2f} required but no payment method specified. "
                f"Use get_payment_methods to list saved cards, then provide the payment_method_id."
            )

        if card_amount > 0 and card_info:
            try:
                await card_service.internal_charge(
                    card_id=payment_method_id,
                    amount=card_amount,
                    reference_id=str(booking.id),
                    description=f"Payment for booking {booking.pnr}",
                )
            except Exception as e:
                return f"Card charge failed: {str(e)}"

        effective_method = "points" if card_amount <= 0 else ("points+card" if points_used > 0 else "credit_card")

        txn_id = f"txn_{uuid_mod.uuid4().hex[:16]}"
        payment = Payment(
            booking_id=booking.id,
            amount=amount,
            method=effective_method,
            transaction_id=txn_id,
            card_last_four=card_info["card_last_four"] if card_amount > 0 and card_info else None,
        )
        db.add(payment)

        points_earned = int(card_amount * POINTS_PER_DOLLAR)
        if points_earned > 0:
            if not account:
                acct_result = await db.execute(
                    select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
                )
                account = acct_result.scalar_one_or_none()
            if account:
                account.points += points_earned
                db.add(LoyaltyTransaction(
                    account_id=account.id, points=points_earned,
                    transaction_type="earn", source=f"Booking {booking.pnr}",
                ))

        await db.commit()

    parts = [
        f"Payment processed successfully!",
        f"Transaction: {txn_id}",
        f"Booking: {booking.pnr}",
        f"Total: ${amount:.2f}",
    ]
    if points_used > 0:
        parts.append(f"Points redeemed: {points_used:,} (${points_discount:.2f})")
    if card_amount > 0 and card_info:
        parts.append(f"Card charged: ${card_amount:.2f} via {card_info['card_brand'].capitalize()} ••••{card_info['card_last_four']}")
    if points_earned > 0:
        parts.append(f"Points earned: {points_earned:,}")
    parts.append(f"Method: {effective_method}")

    return "\n".join(parts)


@tool
async def get_refund_quote_tool(booking_id: str) -> str:
    """Get a refund quote showing the amount, destination, and timeline before processing.
    Call this BEFORE process_refund to show the user what they'll receive. After user confirms, call process_refund."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.flight import Flight
    from ...models.payment import Payment
    from ...services.card_service import card_service
    from sqlalchemy import select
    from uuid import UUID

    user_id = get_current_user_id()

    async with async_session() as db:
        try:
            result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id.upper()))

        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found."

        if booking.status == "refunded":
            return f"Booking {booking.pnr} has already been refunded."

        flight_result = await db.execute(select(Flight).where(Flight.id == booking.flight_id))
        flight = flight_result.scalar_one_or_none()

        payment_result = await db.execute(
            select(Payment).where(Payment.booking_id == booking.id)
        )
        payment = payment_result.scalar_one_or_none()

    refund_amount = payment.amount if payment else 0

    lines = [
        f"Refund Quote for PNR {booking.pnr}:",
        f"Flight: {flight.flight_number} ({flight.origin} → {flight.destination})" if flight else "Flight: N/A",
        f"Travel Date: {booking.travel_date.isoformat() if booking.travel_date else 'Not specified'}",
        f"Passenger: {booking.passenger_name}",
        f"Booking Status: {booking.status.capitalize()}",
        f"",
        f"Refund details:",
        f"  Payment amount: ${refund_amount:.2f}",
        f"  Refund amount: ${refund_amount:.2f}",
        f"",
    ]

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
        points_back = int(refund_amount / 0.01)
        lines.append(f"Refund to: Loyalty points ({points_back:,} points)")
        lines.append(f"Processing time: Immediate")
    else:
        lines.append(f"No payment found for this booking.")

    lines.append(f"")
    lines.append(f"After user confirms, call process_refund to finalize.")

    return "\n".join(lines)


@tool
async def process_refund_tool(booking_id: str, reason: str = "Customer request") -> str:
    """Process a refund for a booking. Call get_refund_quote first to show the user what they'll receive.
    Credits the refund amount back to the original payment card."""
    from ...database import async_session
    from ...models.booking import Booking
    from ...models.payment import Payment
    from ...models.loyalty import LoyaltyAccount, LoyaltyTransaction
    from ...services.card_service import card_service
    from sqlalchemy import select
    from uuid import UUID

    user_id = get_current_user_id()

    async with async_session() as db:
        try:
            result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id.upper()))

        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found. Cannot process refund."

        if booking.status == "refunded":
            return f"Booking {booking.pnr} has already been refunded."

        payment_result = await db.execute(
            select(Payment).where(Payment.booking_id == booking.id)
        )
        payment = payment_result.scalar_one_or_none()

        refund_amount = payment.amount if payment else 0
        credited_card = None
        points_refunded = 0

        if payment and payment.card_last_four:
            cards = await card_service.list_cards(user_id)
            for c in cards:
                if c["card_last_four"] == payment.card_last_four:
                    await card_service.credit(
                        card_id=c["id"],
                        amount=payment.amount,
                        reference_id=str(booking.id),
                        description=f"Refund for booking {booking.pnr}",
                    )
                    credited_card = c
                    break
        elif payment and payment.method == "points":
            points_refunded = int(refund_amount / 0.01)
            acct_result = await db.execute(
                select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
            )
            account = acct_result.scalar_one_or_none()
            if account:
                account.points += points_refunded
                db.add(LoyaltyTransaction(
                    account_id=account.id, points=points_refunded,
                    transaction_type="refund", source=f"Refund {booking.pnr}",
                ))

        booking.status = "refunded"
        await db.commit()

    parts = [
        f"Refund processed successfully!",
        f"PNR: {booking.pnr}",
        f"Reason: {reason}",
        f"Refund amount: ${refund_amount:.2f}",
    ]
    if credited_card:
        parts.append(f"Credited to: {credited_card['card_brand'].capitalize()} ••••{credited_card['card_last_four']}")
        parts.append(f"The refund has been applied immediately and is available on your card now.")
    elif points_refunded > 0:
        parts.append(f"Refunded: {points_refunded:,} loyalty points")
        parts.append(f"Points are available in your account immediately.")
    elif payment and payment.card_last_four:
        parts.append(f"Credited back to card ••••{payment.card_last_four}")
    parts.append(f"Status: Refunded")

    return "\n".join(parts)
