from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..constants import DOLLARS_PER_POINT, TIER_THRESHOLDS
from ..database import get_db
from ..models.audit import AuditLog
from ..models.user import User
from ..models.booking import Booking
from ..models.flight import Flight
from ..models.loyalty import LoyaltyAccount, LoyaltyTransaction
from ..middleware.auth import require_admin_user
from ..services.saas.automail import send_email
from .bookings import ADMIN_COUPONS

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    users_count = await db.execute(select(func.count(User.id)))
    bookings_count = await db.execute(select(func.count(Booking.id)))
    return {
        "users": users_count.scalar(),
        "bookings": bookings_count.scalar(),
        "mcp_tools": 8,
        "active_conversations": 12,
    }


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 50,
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "actor": log.actor,
            "action": log.action,
            "resource": log.resource,
            "details": log.details,
            "ip_address": log.ip_address,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]


@router.get("/users")
async def list_all_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str = Query("", description="Search by name or email"),
    role: str = Query("", description="Filter by role"),
    tier: str = Query("", description="Filter by loyalty tier"),
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    count_query = select(func.count(User.id))
    conditions = []
    if search:
        conditions.append(or_(User.name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
    if role:
        conditions.append(User.role == role)
    if tier:
        conditions.append(User.loyalty_tier == tier)
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()
    return {
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "phone": u.phone,
                "ssn": u.ssn,
                "credit_card": u.credit_card,
                "loyalty_tier": u.loyalty_tier,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.post("/scheduler/trigger")
async def trigger_scheduler(
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from ..services.flight_scheduler import check_and_add_demand_flights, check_and_add_holiday_flights
    await check_and_add_demand_flights()
    await check_and_add_holiday_flights()
    from ..models.flight import Flight
    flight_count = await db.execute(select(func.count(Flight.id)))
    return {
        "status": "triggered",
        "message": "Demand and holiday flight checks completed",
        "total_flights": flight_count.scalar(),
    }


class UserRoleUpdate(BaseModel):
    role: str


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    await db.commit()
    return {"status": "updated", "user_id": user_id, "new_role": body.role}


class FlightReschedule(BaseModel):
    new_departure: str
    new_arrival: str
    reason: str | None = None


@router.put("/flights/{flight_id}/reschedule")
async def reschedule_flight(
    flight_id: str,
    body: FlightReschedule,
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    old_departure = flight.departure.isoformat()
    flight.departure = datetime.fromisoformat(body.new_departure)
    flight.arrival = datetime.fromisoformat(body.new_arrival)
    await db.commit()

    bookings_result = await db.execute(
        select(Booking).where(
            Booking.flight_id == UUID(flight_id),
            Booking.status != "cancelled",
        )
    )
    affected_bookings = bookings_result.scalars().all()

    for booking in affected_bookings:
        await send_email(
            to=booking.passenger_email,
            subject=f"Flight {flight.flight_number} Rescheduled - PNR {booking.pnr}",
            body=(
                f"Dear {booking.passenger_name},\n\n"
                f"Your flight {flight.flight_number} has been rescheduled.\n"
                f"New departure: {body.new_departure}\n"
                f"New arrival: {body.new_arrival}\n"
                f"Reason: {body.reason or 'Operational requirements'}\n\n"
                f"We apologize for the inconvenience."
            ),
        )

    return {
        "status": "rescheduled",
        "flight_id": flight_id,
        "flight_number": flight.flight_number,
        "old_departure": old_departure,
        "new_departure": body.new_departure,
        "new_arrival": body.new_arrival,
        "affected_bookings": len(affected_bookings),
    }


class FlightCancel(BaseModel):
    reason: str | None = None
    cancel_date: str | None = None


@router.post("/flights/{flight_id}/cancel")
async def cancel_flight(
    flight_id: str,
    body: FlightCancel = FlightCancel(),
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from ..models.payment import Payment, RefundRecord
    from ..services.card_service import card_service

    from datetime import date as date_type

    result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    cancel_date = None
    if body.cancel_date and flight.days_of_week:
        cancel_date = date_type.fromisoformat(body.cancel_date)

    if not cancel_date:
        flight.status = "cancelled"
    else:
        from ..models.flight import FlightCancellation
        db.add(FlightCancellation(
            flight_id=flight.id,
            cancelled_date=cancel_date,
            reason=body.reason,
        ))
    await db.commit()

    booking_filters = [
        Booking.flight_id == UUID(flight_id),
        Booking.status != "cancelled",
    ]
    if cancel_date:
        booking_filters.append(Booking.travel_date == cancel_date)

    bookings_result = await db.execute(
        select(Booking).where(*booking_filters)
    )
    affected_bookings = bookings_result.scalars().all()

    reason = body.reason or "Operational requirements"
    refunds_processed = 0

    for booking in affected_bookings:
        booking.status = "cancelled"

        db.add(RefundRecord(
            booking_id=booking.id,
            user_id=booking.user_id,
            action_type="cancellation",
            amount=0,
            reason=f"Flight {flight.flight_number} cancelled: {reason}",
            refund_method=None,
            card_last_four=None,
            status="completed",
            pnr=booking.pnr,
        ))

        payment_result = await db.execute(
            select(Payment).where(Payment.booking_id == booking.id)
        )
        payment = payment_result.scalar_one_or_none()

        if payment and payment.amount > 0:
            refund_method = None
            card_last_four = None

            if payment.card_last_four:
                try:
                    cards = await card_service.list_cards(str(booking.user_id))
                    for c in cards:
                        if c["card_last_four"] == payment.card_last_four:
                            await card_service.credit(
                                card_id=c["id"],
                                amount=payment.amount,
                                reference_id=str(booking.id),
                                description=f"Refund - flight {flight.flight_number} cancelled",
                            )
                            refund_method = "card"
                            card_last_four = payment.card_last_four
                            break
                except Exception:
                    pass
            elif payment.method == "points":
                points_back = int(payment.amount / DOLLARS_PER_POINT)
                acct_result = await db.execute(
                    select(LoyaltyAccount).where(LoyaltyAccount.user_id == booking.user_id)
                )
                account = acct_result.scalar_one_or_none()
                if account:
                    account.points += points_back
                    db.add(LoyaltyTransaction(
                        account_id=account.id, points=points_back,
                        transaction_type="refund", source=f"Flight cancelled {booking.pnr}",
                    ))
                refund_method = "points"

            db.add(RefundRecord(
                booking_id=booking.id,
                user_id=booking.user_id,
                action_type="refund",
                amount=payment.amount,
                reason=f"Refund for flight {flight.flight_number} cancellation",
                refund_method=refund_method or "card",
                card_last_four=card_last_four,
                status="completed",
                pnr=booking.pnr,
            ))
            refunds_processed += 1

        await send_email(
            to=booking.passenger_email,
            subject=f"Flight {flight.flight_number} Cancelled - PNR {booking.pnr}",
            body=(
                f"Dear {booking.passenger_name},\n\n"
                f"We regret to inform you that flight {flight.flight_number} has been cancelled.\n"
                f"Reason: {reason}\n\n"
                f"Your booking (PNR: {booking.pnr}) has been cancelled and "
                f"a refund of ${payment.amount:.2f} has been processed to your original payment method.\n\n"
                f"We apologize for the inconvenience."
            ) if payment and payment.amount > 0 else (
                f"Dear {booking.passenger_name},\n\n"
                f"We regret to inform you that flight {flight.flight_number} has been cancelled.\n"
                f"Reason: {reason}\n\n"
                f"Your booking (PNR: {booking.pnr}) has been cancelled.\n\n"
                f"We apologize for the inconvenience."
            ),
        )

    await db.commit()

    return {
        "status": "cancelled",
        "flight_id": flight_id,
        "flight_number": flight.flight_number,
        "affected_bookings": len(affected_bookings),
        "refunds_processed": refunds_processed,
        "reason": reason,
    }


class BookingCancelAdmin(BaseModel):
    reason: str | None = None


@router.post("/bookings/{booking_id}/cancel")
async def admin_cancel_booking(
    booking_id: str,
    body: BookingCancelAdmin = BookingCancelAdmin(),
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from ..models.payment import Payment, RefundRecord
    from ..services.card_service import card_service

    result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Booking already cancelled")

    reason = body.reason or "Administrative action"
    booking.status = "cancelled"

    db.add(RefundRecord(
        booking_id=booking.id,
        user_id=booking.user_id,
        action_type="cancellation",
        amount=0,
        reason=reason,
        refund_method=None,
        card_last_four=None,
        status="completed",
        pnr=booking.pnr,
    ))

    payment_result = await db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    )
    payment = payment_result.scalar_one_or_none()
    refund_amount = 0.0

    if payment and payment.amount > 0:
        refund_amount = payment.amount
        refund_method = None
        card_last_four = None

        if payment.card_last_four:
            try:
                cards = await card_service.list_cards(str(booking.user_id))
                for c in cards:
                    if c["card_last_four"] == payment.card_last_four:
                        await card_service.credit(
                            card_id=c["id"],
                            amount=payment.amount,
                            reference_id=str(booking.id),
                            description=f"Refund - admin cancelled {booking.pnr}",
                        )
                        refund_method = "card"
                        card_last_four = payment.card_last_four
                        break
            except Exception:
                pass
        elif payment.method == "points":
            points_back = int(payment.amount / DOLLARS_PER_POINT)
            acct_result = await db.execute(
                select(LoyaltyAccount).where(LoyaltyAccount.user_id == booking.user_id)
            )
            account = acct_result.scalar_one_or_none()
            if account:
                account.points += points_back
                db.add(LoyaltyTransaction(
                    account_id=account.id, points=points_back,
                    transaction_type="refund", source=f"Admin cancelled {booking.pnr}",
                ))
            refund_method = "points"

        db.add(RefundRecord(
            booking_id=booking.id,
            user_id=booking.user_id,
            action_type="refund",
            amount=payment.amount,
            reason=f"Refund for cancellation",
            refund_method=refund_method or "card",
            card_last_four=card_last_four,
            status="completed",
            pnr=booking.pnr,
        ))

    await db.commit()

    await send_email(
        to=booking.passenger_email,
        subject=f"Booking Cancelled - PNR {booking.pnr}",
        body=(
            f"Dear {booking.passenger_name},\n\n"
            f"Your booking (PNR: {booking.pnr}) has been cancelled.\n"
            f"Reason: {reason}\n\n"
            + (f"A refund of ${refund_amount:.2f} has been processed to your original payment method.\n\n" if refund_amount > 0 else "")
            + f"We apologize for the inconvenience."
        ),
    )

    return {
        "status": "cancelled",
        "booking_id": booking_id,
        "pnr": booking.pnr,
        "refund_amount": refund_amount,
        "reason": reason,
    }


@router.get("/flights")
async def list_all_flights(
    status: str | None = None,
    date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str = Query("", description="Search by flight number, origin, or destination"),
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from ..models.flight import FlightCancellation
    from .flights import flight_operates_on
    from datetime import date as date_type

    query = select(Flight)
    count_query = select(func.count(Flight.id))
    conditions = []

    target_date = None
    if date:
        target_date = date_type.fromisoformat(date)

    if status and not target_date:
        conditions.append(Flight.status == status)
    if search:
        conditions.append(or_(
            Flight.flight_number.ilike(f"%{search}%"),
            Flight.origin.ilike(f"%{search}%"),
            Flight.destination.ilike(f"%{search}%"),
        ))
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    if target_date:
        all_result = await db.execute(query.order_by(Flight.departure.desc()))
        all_flights = [f for f in all_result.scalars().all() if flight_operates_on(f, target_date)]

        cancel_result = await db.execute(
            select(FlightCancellation.flight_id).where(FlightCancellation.cancelled_date == target_date)
        )
        cancelled_ids = set(cancel_result.scalars().all())

        if status == "cancelled":
            all_flights = [f for f in all_flights if f.status == "cancelled" or f.id in cancelled_ids]
        elif status == "scheduled":
            all_flights = [f for f in all_flights if f.status != "cancelled" and f.id not in cancelled_ids]

        total = len(all_flights)
        start = (page - 1) * page_size
        flights = all_flights[start:start + page_size]
    else:
        total = (await db.execute(count_query)).scalar() or 0
        result = await db.execute(
            query.order_by(Flight.departure.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        flights = result.scalars().all()
        cancelled_ids = set()

    if target_date:
        cancelled_count = len([f for f in all_flights if f.status == "cancelled" or f.id in cancelled_ids])
        scheduled_count = total - cancelled_count
    else:
        scheduled_count = (await db.execute(select(func.count(Flight.id)).where(Flight.status == "scheduled"))).scalar() or 0
        cancelled_count = (await db.execute(select(func.count(Flight.id)).where(Flight.status == "cancelled"))).scalar() or 0

    return {
        "items": [
            {
                "id": str(f.id),
                "flight_number": f.flight_number,
                "origin": f.origin,
                "destination": f.destination,
                "departure": f.departure.isoformat(),
                "arrival": f.arrival.isoformat(),
                "status": "cancelled" if f.id in cancelled_ids else f.status,
                "aircraft": f.aircraft,
                "available_seats": f.available_seats,
                "total_seats": f.total_seats,
                "days_of_week": f.days_of_week,
                "cancelled_for_date": f.id in cancelled_ids,
            }
            for f in flights
        ],
        "total": total,
        "scheduled_count": scheduled_count,
        "cancelled_count": cancelled_count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/bookings")
async def list_all_bookings(
    status: str | None = None,
    flight_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Booking)
    count_query = select(func.count(Booking.id))
    conditions = []
    if status:
        conditions.append(Booking.status == status)
    if flight_id:
        conditions.append(Booking.flight_id == UUID(flight_id))
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Booking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    bookings = result.scalars().all()
    return {
        "items": [
            {
                "id": str(b.id),
                "flight_id": str(b.flight_id),
                "user_id": str(b.user_id),
                "pnr": b.pnr,
                "passenger_name": b.passenger_name,
                "passenger_email": b.passenger_email,
                "status": b.status,
                "cabin_class": b.cabin_class or "economy",
                "travel_date": b.travel_date.isoformat() if b.travel_date else None,
                "created_at": b.created_at.isoformat(),
            }
            for b in bookings
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


# --- Offers Management ---

class ConditionsInput(BaseModel):
    max_uses_total: int | None = None
    max_uses_per_user: int | None = None
    new_user: bool | None = None
    min_bookings_last_n_days: dict | None = None
    loyalty_tier_min: str | None = None
    routes: list[dict] | None = None
    cabin_class: list[str] | None = None
    min_booking_value: float | None = None
    keywords: list[str] | None = None


class OfferCreate(BaseModel):
    code: str
    discount_percent: int
    description: str
    valid_from: str | None = None
    valid_until: str | None = None
    conditions: ConditionsInput | None = None


@router.post("/offers")
async def create_offer(
    body: OfferCreate,
    current_user: dict = Depends(require_admin_user),
):
    conditions = {}
    if body.conditions:
        c = body.conditions
        if c.max_uses_total is not None:
            conditions["max_uses_total"] = c.max_uses_total
        if c.max_uses_per_user is not None:
            conditions["max_uses_per_user"] = c.max_uses_per_user
        if c.new_user:
            conditions["new_user"] = True
        if c.min_bookings_last_n_days:
            conditions["min_bookings_last_n_days"] = c.min_bookings_last_n_days
        if c.loyalty_tier_min:
            conditions["loyalty_tier_min"] = c.loyalty_tier_min
        if c.routes:
            conditions["routes"] = c.routes
        if c.cabin_class:
            conditions["cabin_class"] = c.cabin_class
        if c.min_booking_value is not None:
            conditions["min_booking_value"] = c.min_booking_value
        if c.keywords:
            conditions["keywords"] = c.keywords

    offer = {
        "code": body.code.upper(),
        "discount_percent": body.discount_percent,
        "description": body.description,
        "valid_from": body.valid_from,
        "valid_until": body.valid_until,
        "conditions": conditions,
    }
    ADMIN_COUPONS.append(offer)
    return {"status": "created", **offer}


@router.get("/offers")
async def list_offers(
    current_user: dict = Depends(require_admin_user),
):
    return {"offers": ADMIN_COUPONS}


# --- Points & Tier Management ---

VALID_TIERS = ["bronze", "silver", "gold", "platinum"]


class CreditPointsRequest(BaseModel):
    points: int
    reason: str


@router.post("/users/{user_id}/credit-points")
async def credit_points(
    user_id: str,
    body: CreditPointsRequest,
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    acct_result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        account = LoyaltyAccount(user_id=UUID(user_id), points=0, tier="bronze")
        db.add(account)
        await db.flush()

    account.points += body.points
    txn = LoyaltyTransaction(
        account_id=account.id,
        points=body.points,
        transaction_type="admin_credit",
        source=body.reason,
    )
    db.add(txn)
    await db.commit()

    return {
        "status": "credited",
        "user_id": user_id,
        "points_credited": body.points,
        "new_balance": account.points,
        "reason": body.reason,
    }


class TierUpdateRequest(BaseModel):
    tier: str


@router.put("/users/{user_id}/tier")
async def update_user_tier(
    user_id: str,
    body: TierUpdateRequest,
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if body.tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of: {', '.join(VALID_TIERS)}")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    previous_tier = user.loyalty_tier
    user.loyalty_tier = body.tier

    tier_minimums = TIER_THRESHOLDS

    acct_result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
    )
    account = acct_result.scalar_one_or_none()
    if account:
        account.tier = body.tier
        min_points = tier_minimums.get(body.tier, 0)
        if account.points < min_points:
            points_added = min_points - account.points
            account.points = min_points
            db.add(LoyaltyTransaction(
                account_id=account.id,
                points=points_added,
                transaction_type="adjustment",
                source=f"Tier upgrade to {body.tier}",
            ))

    await db.commit()

    return {
        "status": "updated",
        "user_id": user_id,
        "new_tier": body.tier,
        "previous_tier": previous_tier,
    }


# --- Day-Specific Schedule Override ---

class ScheduleOverrideRequest(BaseModel):
    date: str
    new_departure: str
    new_arrival: str
    reason: str | None = None


@router.post("/flights/{flight_id}/override-schedule")
async def override_flight_schedule(
    flight_id: str,
    body: ScheduleOverrideRequest,
    current_user: dict = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    if not flight.days_of_week:
        raise HTTPException(status_code=400, detail="Flight is not recurring. Use the reschedule endpoint instead.")

    target_date = date.fromisoformat(body.date)
    weekday = str(target_date.weekday())
    if weekday not in flight.days_of_week:
        raise HTTPException(status_code=400, detail=f"Flight does not operate on {target_date.strftime('%A')}s")

    new_departure = datetime.fromisoformat(body.new_departure)
    new_arrival = datetime.fromisoformat(body.new_arrival)

    override_flight = Flight(
        flight_number=flight.flight_number,
        origin=flight.origin,
        destination=flight.destination,
        departure=new_departure,
        arrival=new_arrival,
        aircraft=flight.aircraft,
        status="scheduled",
        base_price=flight.base_price,
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        economy_seats=flight.economy_seats,
        premium_economy_seats=flight.premium_economy_seats,
        business_seats=flight.business_seats,
        days_of_week=None,
        valid_from=target_date,
        valid_until=target_date,
    )
    db.add(override_flight)
    await db.flush()

    bookings_result = await db.execute(
        select(Booking).where(and_(
            Booking.flight_id == UUID(flight_id),
            Booking.travel_date == target_date,
            Booking.status != "cancelled",
        ))
    )
    affected_bookings = bookings_result.scalars().all()

    for booking in affected_bookings:
        booking.flight_id = override_flight.id
        await send_email(
            to=booking.passenger_email,
            subject=f"Flight {flight.flight_number} Schedule Change on {body.date} - PNR {booking.pnr}",
            body=(
                f"Dear {booking.passenger_name},\n\n"
                f"Your flight {flight.flight_number} on {body.date} has been rescheduled.\n"
                f"New departure: {body.new_departure}\n"
                f"New arrival: {body.new_arrival}\n"
                f"Reason: {body.reason or 'Operational requirements'}\n\n"
                f"Your booking (PNR: {booking.pnr}) has been updated automatically.\n\n"
                f"We apologize for the inconvenience."
            ),
        )

    await db.commit()

    return {
        "status": "override_created",
        "original_flight_id": flight_id,
        "override_flight_id": str(override_flight.id),
        "date": body.date,
        "new_departure": body.new_departure,
        "new_arrival": body.new_arrival,
        "affected_bookings": len(affected_bookings),
    }
