import random
import string
from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import DOLLARS_PER_POINT, POINTS_PER_DOLLAR
from ..database import get_db
from ..models.booking import Booking
from ..models.flight import Flight
from ..models.user import User
from ..middleware.auth import require_auth
from ..services.saas.automail import send_email
from ..models.loyalty import LoyaltyAccount, LoyaltyTransaction
from .flights import project_flight_to_date

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


def generate_pnr() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class BookingCreate(BaseModel):
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_id: str | None = None
    travel_date: str | None = None
    cabin_class: str = "economy"
    coupon_code: str | None = None


class BookingResponse(BaseModel):
    id: str
    flight_id: str
    user_id: str
    status: str
    pnr: str
    passenger_name: str
    passenger_email: str
    cabin_class: str = "economy"
    travel_date: str | None = None
    flight_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    departure: str | None = None
    created_at: str


@router.post("", response_model=BookingResponse)
async def create_booking(
    body: BookingCreate,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    cabin = body.cabin_class if body.cabin_class in ("economy", "premium_economy", "business") else "economy"

    flight_result = await db.execute(select(Flight).where(Flight.id == UUID(body.flight_id)))
    flight = flight_result.scalar_one_or_none()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    travel_d = date.fromisoformat(body.travel_date) if body.travel_date else None
    if travel_d and flight.economy_seats > 0:
        existing = await db.execute(
            select(func.count(Booking.id)).where(and_(
                Booking.flight_id == UUID(body.flight_id),
                Booking.travel_date == travel_d,
                Booking.cabin_class == cabin,
                Booking.status != "cancelled",
            ))
        )
        booked_in_class = existing.scalar() or 0
        class_capacity = {"economy": flight.economy_seats, "premium_economy": flight.premium_economy_seats, "business": flight.business_seats}[cabin]
        if booked_in_class >= class_capacity:
            raise HTTPException(status_code=409, detail=f"No {cabin.replace('_', ' ')} seats available on this flight")

    booking = Booking(
        user_id=UUID(current_user["sub"]),
        flight_id=UUID(body.flight_id),
        seat_id=UUID(body.seat_id) if body.seat_id else None,
        pnr=generate_pnr(),
        passenger_name=body.passenger_name,
        passenger_email=body.passenger_email,
        cabin_class=cabin,
        travel_date=travel_d,
        coupon_code=body.coupon_code.upper() if body.coupon_code else None,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    await send_email(
        to=body.passenger_email,
        subject=f"Booking Confirmed - {booking.pnr}",
        body=f"Dear {body.passenger_name},\n\nYour booking is confirmed.\nPNR: {booking.pnr}\nFlight: {body.flight_id}\n\nThank you for choosing AutoPilot Airlines.",
    )


    dep_str = None
    if travel_d and flight:
        dep, _ = project_flight_to_date(flight, travel_d)
        dep_str = dep.isoformat()
    elif flight and flight.departure:
        dep_str = flight.departure.isoformat()

    return BookingResponse(
        id=str(booking.id),
        flight_id=str(booking.flight_id),
        user_id=str(booking.user_id),
        status=booking.status,
        pnr=booking.pnr,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        cabin_class=booking.cabin_class or "economy",
        travel_date=booking.travel_date.isoformat() if booking.travel_date else None,
        flight_number=flight.flight_number if flight else None,
        origin=flight.origin if flight else None,
        destination=flight.destination if flight else None,
        departure=dep_str,
        created_at=booking.created_at.isoformat(),
    )


@router.get("", response_model=list[BookingResponse])
async def list_bookings(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):


    result = await db.execute(
        select(Booking, Flight)
        .join(Flight, Booking.flight_id == Flight.id)
        .where(Booking.user_id == UUID(current_user["sub"]))
        .order_by(Booking.created_at.desc())
    )
    rows = result.all()
    responses = []
    for b, f in rows:
        dep_str = None
        if b.travel_date and f:
            dep, _ = project_flight_to_date(f, b.travel_date)
            dep_str = dep.isoformat()
        elif f and f.departure:
            dep_str = f.departure.isoformat()
        responses.append(BookingResponse(
            id=str(b.id),
            flight_id=str(b.flight_id),
            user_id=str(b.user_id),
            status=b.status,
            pnr=b.pnr,
            passenger_name=b.passenger_name,
            passenger_email=b.passenger_email,
            cabin_class=b.cabin_class or "economy",
            travel_date=b.travel_date.isoformat() if b.travel_date else None,
            flight_number=f.flight_number if f else None,
            origin=f.origin if f else None,
            destination=f.destination if f else None,
            departure=dep_str,
            created_at=b.created_at.isoformat(),
        ))
    return responses


STATIC_COUPONS = {
    "FLY10": {"discount_percent": 10, "description": "10% off your flight", "conditions": {}},
    "WELCOME20": {"discount_percent": 20, "description": "20% welcome discount", "conditions": {"new_user": True, "max_uses_per_user": 1}},
    "VIP50": {"discount_percent": 50, "description": "VIP 50% discount", "conditions": {"loyalty_tier_min": "platinum"}},
    "SUMMER25": {"discount_percent": 25, "description": "Summer sale 25% off", "conditions": {"min_booking_value": 200}},
}

HOLIDAYS = [
    (1, 1, "NEWYEAR", "New Year Sale", 15),
    (2, 14, "VALENTINE", "Valentine's Day Getaway", 20),
    (3, 17, "STPAT", "St. Patrick's Day Deal", 10),
    (5, 26, "MEMORIAL", "Memorial Day Sale", 20),
    (7, 4, "JULY4", "Independence Day Special", 25),
    (9, 1, "LABOR", "Labor Day Deal", 15),
    (10, 31, "SPOOKY", "Halloween Travel Treat", 15),
    (11, 27, "THANKS", "Thanksgiving Special", 20),
    (12, 25, "XMAS", "Christmas Holiday Deal", 30),
    (12, 31, "NYE", "New Year's Eve Escape", 20),
    (1, 26, "REPUBLIC", "Republic Day Offer", 20),
    (8, 15, "FREEDOM", "Independence Day India", 15),
    (10, 15, "DUSSEHRA", "Dussehra Festival Offer", 20),
    (11, 1, "DIWALI", "Diwali Festival Special", 25),
    (3, 25, "HOLI", "Holi Color Fest Deal", 15),
]

BULK_TIERS = [
    (3, 10, "BULK3", "Book 3+ passengers, save 10%"),
    (5, 15, "BULK5", "Book 5+ passengers, save 15%"),
    (10, 25, "BULK10", "Group booking 10+, save 25%"),
]

ADMIN_COUPONS: list[dict] = [
    {
        "code": "LOYALTY15",
        "discount_percent": 15,
        "description": "15% off for Gold+ members",
        "valid_from": None,
        "valid_until": None,
        "conditions": {"loyalty_tier_min": "gold"},
    },
    {
        "code": "FREQUENT30",
        "discount_percent": 30,
        "description": "30% off — booked 5+ times in 30 days",
        "valid_from": None,
        "valid_until": None,
        "conditions": {"min_bookings_last_n_days": {"min_bookings": 5, "days": 30}},
    },
    {
        "code": "JFKDEAL",
        "discount_percent": 20,
        "description": "20% off any JFK flight",
        "valid_from": None,
        "valid_until": None,
        "conditions": {"keywords": ["JFK"]},
    },
    {
        "code": "BIZBOOKER",
        "discount_percent": 15,
        "description": "15% off business class bookings",
        "valid_from": None,
        "valid_until": None,
        "conditions": {"cabin_class": ["business"]},
    },
    {
        "code": "FLASH50",
        "discount_percent": 50,
        "description": "Flash sale — first 10 uses only",
        "valid_from": None,
        "valid_until": None,
        "conditions": {"max_uses_total": 10},
    },
    {
        "code": "ONCE25",
        "discount_percent": 25,
        "description": "25% off — one use per customer",
        "valid_from": None,
        "valid_until": None,
        "conditions": {"max_uses_per_user": 1},
    },
]


def _get_active_holiday_coupons() -> dict:
    today = date.today()
    active = {}
    for month, day, code, description, discount in HOLIDAYS:
        try:
            holiday_date = date(today.year, month, day)
        except ValueError:
            continue
        window_start = holiday_date - timedelta(days=5)
        window_end = holiday_date + timedelta(days=2)
        if window_start <= today <= window_end:
            active[code] = {
                "discount_percent": discount,
                "description": f"{description} — {discount}% off!",
                "type": "holiday",
                "valid_until": window_end.isoformat(),
            }
    return active


def _get_bulk_coupon(code: str) -> dict | None:
    for min_pax, discount, bulk_code, description in BULK_TIERS:
        if code == bulk_code:
            return {
                "discount_percent": discount,
                "description": description,
                "type": "bulk",
                "min_passengers": min_pax,
            }
    return None


TIER_ORDER = {"bronze": 0, "silver": 1, "gold": 2, "platinum": 3}


async def evaluate_conditions(
    conditions: dict,
    code: str,
    user_id: str,
    user_loyalty_tier: str,
    flight: Flight | None,
    cabin_class: str | None,
    subtotal: float | None,
    db: AsyncSession,
) -> str | None:
    if not conditions:
        return None

    if "max_uses_total" in conditions:
        total_uses = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.coupon_code == code,
                Booking.status != "cancelled",
            )
        )
        if (total_uses.scalar() or 0) >= conditions["max_uses_total"]:
            return f"Coupon {code} has reached its maximum usage limit"

    if "max_uses_per_user" in conditions:
        user_uses = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.coupon_code == code,
                Booking.user_id == UUID(user_id),
                Booking.status != "cancelled",
            )
        )
        if (user_uses.scalar() or 0) >= conditions["max_uses_per_user"]:
            return f"You have already used coupon {code}"

    if conditions.get("new_user"):
        booking_count = await db.execute(
            select(func.count(Booking.id)).where(Booking.user_id == UUID(user_id))
        )
        if (booking_count.scalar() or 0) > 0:
            return f"{code} is only for first-time bookers"

    if "min_bookings_last_n_days" in conditions:
        cfg = conditions["min_bookings_last_n_days"]
        cutoff = datetime.now() - timedelta(days=cfg["days"])
        recent = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.user_id == UUID(user_id),
                Booking.status == "confirmed",
                Booking.created_at >= cutoff,
            )
        )
        if (recent.scalar() or 0) < cfg["min_bookings"]:
            return f"You need at least {cfg['min_bookings']} bookings in the last {cfg['days']} days"

    if "loyalty_tier_min" in conditions:
        required = conditions["loyalty_tier_min"]
        if TIER_ORDER.get(user_loyalty_tier, 0) < TIER_ORDER.get(required, 0):
            return f"Requires {required} tier or above (you are {user_loyalty_tier})"

    if "routes" in conditions and flight:
        allowed_routes = conditions["routes"]
        matched = any(
            r["origin"] == flight.origin and r["destination"] == flight.destination
            for r in allowed_routes
        )
        if not matched:
            return f"{code} is not valid for this route"

    if "cabin_class" in conditions:
        allowed_classes = conditions["cabin_class"]
        if cabin_class and cabin_class not in allowed_classes:
            return f"{code} is only valid for {', '.join(allowed_classes)} class"

    if "min_booking_value" in conditions:
        if subtotal is not None and subtotal < conditions["min_booking_value"]:
            return f"Minimum booking value of ${conditions['min_booking_value']:.0f} required"

    if "keywords" in conditions and flight:
        keywords = [k.upper() for k in conditions["keywords"]]
        haystack = f"{flight.flight_number} {flight.origin} {flight.destination}".upper()
        if not any(kw in haystack for kw in keywords):
            return f"{code} is not valid for this flight"

    return None


class CouponValidate(BaseModel):
    code: str
    passengers: int | None = None
    flight_id: str | None = None
    cabin_class: str | None = None
    subtotal: float | None = None


@router.post("/coupons/validate")
async def validate_coupon(
    body: CouponValidate,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    code = body.code.upper()
    user_id = current_user.get("sub")

    user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = user_result.scalar_one_or_none()
    user_tier = user.loyalty_tier if user else "bronze"

    flight = None
    if body.flight_id:
        flight_result = await db.execute(select(Flight).where(Flight.id == UUID(body.flight_id)))
        flight = flight_result.scalar_one_or_none()

    if code in STATIC_COUPONS:
        coupon = STATIC_COUPONS[code]
        failure = await evaluate_conditions(
            coupon.get("conditions", {}), code, user_id, user_tier,
            flight, body.cabin_class, body.subtotal, db,
        )
        if failure:
            return {"valid": False, "discount_percent": 0, "description": failure}
        return {"valid": True, "discount_percent": coupon["discount_percent"], "description": coupon["description"]}

    holiday_coupons = _get_active_holiday_coupons()
    if code in holiday_coupons:
        return {"valid": True, **holiday_coupons[code]}

    bulk = _get_bulk_coupon(code)
    if bulk:
        pax = body.passengers or 1
        if pax >= bulk["min_passengers"]:
            return {"valid": True, **bulk}
        return {
            "valid": False,
            "discount_percent": 0,
            "description": f"Need at least {bulk['min_passengers']} passengers for this discount (you have {pax})",
        }

    today = date.today()
    for ac in ADMIN_COUPONS:
        if ac["code"].upper() == code:
            if ac.get("valid_from") and today < date.fromisoformat(ac["valid_from"]):
                break
            if ac.get("valid_until") and today > date.fromisoformat(ac["valid_until"]):
                break
            failure = await evaluate_conditions(
                ac.get("conditions", {}), code, user_id, user_tier,
                flight, body.cabin_class, body.subtotal, db,
            )
            if failure:
                return {"valid": False, "discount_percent": 0, "description": failure}
            return {"valid": True, "discount_percent": ac["discount_percent"], "description": ac["description"], "type": "campaign"}

    return {"valid": False, "discount_percent": 0, "description": "Invalid coupon code"}


@router.get("/coupons/available")
async def list_available_coupons():
    today = date.today()
    offers = []

    holiday_coupons = _get_active_holiday_coupons()
    for code, info in holiday_coupons.items():
        offers.append({"code": code, **info})

    for min_pax, discount, code, description in BULK_TIERS:
        offers.append({
            "code": code,
            "discount_percent": discount,
            "description": description,
            "type": "bulk",
            "min_passengers": min_pax,
        })

    for code, info in STATIC_COUPONS.items():
        offers.append({"code": code, "discount_percent": info["discount_percent"], "description": info["description"], "type": "general", "conditions": info.get("conditions", {})})

    for ac in ADMIN_COUPONS:
        valid_from = date.fromisoformat(ac["valid_from"]) if ac.get("valid_from") else None
        valid_until = date.fromisoformat(ac["valid_until"]) if ac.get("valid_until") else None
        if valid_from and today < valid_from:
            continue
        if valid_until and today > valid_until:
            continue
        offers.append({"code": ac["code"], "discount_percent": ac["discount_percent"], "description": ac["description"], "type": "campaign", "valid_until": ac.get("valid_until"), "conditions": ac.get("conditions", {})})

    return {"offers": offers, "date": today.isoformat()}


class ConnectingFlightRequest(BaseModel):
    pnr: str
    destination: str
    preferred_time: str | None = None


@router.post("/connect")
async def book_connecting_flight(
    body: ConnectingFlightRequest,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    from .flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date

    result = await db.execute(
        select(Booking).where(
            Booking.pnr == body.pnr.upper(),
            Booking.user_id == UUID(current_user["sub"]),
        )
    )
    existing_booking = result.scalar_one_or_none()
    if not existing_booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if existing_booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot connect to a cancelled booking")

    flight_result = await db.execute(select(Flight).where(Flight.id == existing_booking.flight_id))
    first_leg = flight_result.scalar_one_or_none()
    if not first_leg:
        raise HTTPException(status_code=404, detail="Original flight not found")

    connection_origin = first_leg.destination
    travel_date = existing_booking.travel_date or first_leg.departure.date()

    if body.preferred_time and body.preferred_time.lower() == "next_day":
        travel_date = travel_date + timedelta(days=1)

    dest = body.destination.upper()
    connecting_flights = await db.execute(
        select(Flight).where(and_(
            Flight.origin == connection_origin,
            Flight.destination == dest,
        ))
    )
    available = connecting_flights.scalars().all()
    available = [f for f in available if flight_operates_on(f, travel_date)]

    if not available:
        raise HTTPException(
            status_code=404,
            detail=f"No connecting flights from {connection_origin} to {dest} on {travel_date.isoformat()}"
        )

    best = available[0]
    booked_count = await count_bookings_for_flight_date(db, best.id, travel_date)
    price = compute_dynamic_price(best.base_price, booked_count, best.total_seats)
    dep, arr = project_flight_to_date(best, travel_date)

    new_pnr = generate_pnr()
    connecting_booking = Booking(
        user_id=UUID(current_user["sub"]),
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

    return {
        "itinerary": {
            "first_leg": {
                "pnr": existing_booking.pnr,
                "flight_number": first_leg.flight_number,
                "origin": first_leg.origin,
                "destination": first_leg.destination,
                "passenger_name": existing_booking.passenger_name,
                "passenger_email": existing_booking.passenger_email,
                "travel_date": (existing_booking.travel_date or first_leg.departure.date()).isoformat(),
                "cabin_class": existing_booking.cabin_class or "economy",
            },
            "connecting_leg": {
                "pnr": new_pnr,
                "flight_number": best.flight_number,
                "origin": connection_origin,
                "destination": dest,
                "departure": dep.isoformat(),
                "arrival": arr.isoformat(),
                "travel_date": travel_date.isoformat(),
                "price": round(price, 2),
                "cabin_class": existing_booking.cabin_class or "economy",
            },
        }
    }


@router.get("/lookup")
async def lookup_booking(
    pnr: str,
    last_name: str = "",
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.pnr == pnr))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    flight_result = await db.execute(select(Flight).where(Flight.id == booking.flight_id))
    flight = flight_result.scalar_one_or_none()
    dep_str = None
    if booking.travel_date and flight:
        dep, _ = project_flight_to_date(flight, booking.travel_date)
        dep_str = dep.isoformat()
    elif flight and flight.departure:
        dep_str = flight.departure.isoformat()
    return BookingResponse(
        id=str(booking.id),
        flight_id=str(booking.flight_id),
        user_id=str(booking.user_id),
        status=booking.status,
        pnr=booking.pnr,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        cabin_class=booking.cabin_class or "economy",
        travel_date=booking.travel_date.isoformat() if booking.travel_date else None,
        flight_number=flight.flight_number if flight else None,
        origin=flight.origin if flight else None,
        destination=flight.destination if flight else None,
        departure=dep_str,
        created_at=booking.created_at.isoformat(),
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    flight_result = await db.execute(select(Flight).where(Flight.id == booking.flight_id))
    flight = flight_result.scalar_one_or_none()
    dep_str = None
    if booking.travel_date and flight:
        dep, _ = project_flight_to_date(flight, booking.travel_date)
        dep_str = dep.isoformat()
    elif flight and flight.departure:
        dep_str = flight.departure.isoformat()
    return BookingResponse(
        id=str(booking.id),
        flight_id=str(booking.flight_id),
        user_id=str(booking.user_id),
        status=booking.status,
        pnr=booking.pnr,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        cabin_class=booking.cabin_class or "economy",
        travel_date=booking.travel_date.isoformat() if booking.travel_date else None,
        flight_number=flight.flight_number if flight else None,
        origin=flight.origin if flight else None,
        destination=flight.destination if flight else None,
        departure=dep_str,
        created_at=booking.created_at.isoformat(),
    )


@router.get("/{booking_id}/receipt")
async def get_booking_receipt(
    booking_id: str,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    from ..models.payment import Payment
    from .baggage import BAGGAGE_RECORDS

    result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    flight_result = await db.execute(select(Flight).where(Flight.id == booking.flight_id))
    flight = flight_result.scalar_one_or_none()

    payment_result = await db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    )
    payment = payment_result.scalar_one_or_none()

    bags = BAGGAGE_RECORDS.get(booking_id, [])
    baggage_total = sum(b["fee"] for b in bags)

    cabin_multiplier = {"economy": 1.0, "premium_economy": 1.5, "business": 2.5}
    base_fare = flight.base_price * cabin_multiplier.get(booking.cabin_class or "economy", 1.0) if flight else 0
    taxes = round(base_fare * 0.12, 2)

    coupon_discount = 0.0
    if booking.coupon_code:
        coupon_info = STATIC_COUPONS.get(booking.coupon_code)
        if not coupon_info:
            for ac in ADMIN_COUPONS:
                if ac["code"].upper() == booking.coupon_code.upper():
                    coupon_info = ac
                    break
        if coupon_info:
            coupon_discount = round((base_fare + taxes) * coupon_info["discount_percent"] / 100, 2)
        elif payment:
            computed_total = round(base_fare + taxes + baggage_total, 2)
            if payment.amount < computed_total:
                coupon_discount = round(computed_total - payment.amount, 2)

    subtotal = round(base_fare + taxes, 2)
    points_value = 0.0
    points_used = 0
    if payment and payment.method in ("points", "points+card"):

        txn_result = await db.execute(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.source == f"Booking {booking_id}",
                LoyaltyTransaction.transaction_type == "payment",
            )
        )
        txn = txn_result.scalar_one_or_none()
        if txn:
            points_used = abs(txn.points)
            points_value = round(points_used * DOLLARS_PER_POINT, 2)

    if payment and coupon_discount == 0:
        expected = round(base_fare + taxes + baggage_total - points_value, 2)
        if abs(payment.amount - expected) > 0.01:
            base_fare = round(payment.amount + points_value - baggage_total, 2)
            taxes = 0.0
            subtotal = round(base_fare, 2)

    amount_paid = payment.amount if payment else 0.0
    points_earned = 0
    if payment:

        earn_result = await db.execute(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.source == f"Booking {booking_id}",
                LoyaltyTransaction.transaction_type == "earn",
            )
        )
        earn_txn = earn_result.scalar_one_or_none()
        if earn_txn:
            points_earned = earn_txn.points
        else:

            acct_result = await db.execute(
                select(LoyaltyAccount).where(LoyaltyAccount.user_id == booking.user_id)
            )
            acct = acct_result.scalar_one_or_none()
            rates = {"bronze": 1, "silver": 1, "gold": 1.5, "platinum": 3}
            rate = rates.get(acct.tier, 1) if acct else 1
            points_earned = int((amount_paid - points_value) * rate)
    else:
        from ..models.loyalty import LoyaltyAccount
        acct_result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == booking.user_id)
        )
        acct = acct_result.scalar_one_or_none()
        rates = {"bronze": 1, "silver": 1, "gold": 1.5, "platinum": 3}
        rate = rates.get(acct.tier, 1) if acct else 1
        points_earned = int(subtotal * rate)

    return {
        "booking": {
            "id": str(booking.id),
            "pnr": booking.pnr,
            "status": booking.status,
            "passenger_name": booking.passenger_name,
            "passenger_email": booking.passenger_email,
            "cabin_class": booking.cabin_class or "economy",
            "travel_date": booking.travel_date.isoformat() if booking.travel_date else None,
            "coupon_code": booking.coupon_code,
            "created_at": booking.created_at.isoformat(),
        },
        "flight": {
            "id": str(flight.id) if flight else None,
            "flight_number": flight.flight_number if flight else None,
            "origin": flight.origin if flight else None,
            "destination": flight.destination if flight else None,
            "departure": flight.departure.isoformat() if flight else None,
            "arrival": flight.arrival.isoformat() if flight else None,
            "aircraft": flight.aircraft if flight else None,
        },
        "pricing": {
            "base_fare": round(base_fare, 2),
            "taxes": taxes,
            "subtotal": subtotal,
            "coupon_code": booking.coupon_code,
            "coupon_discount": coupon_discount,
            "baggage_fees": baggage_total,
            "points_used": points_used,
            "points_value": points_value,
            "total": round(subtotal - coupon_discount + baggage_total - points_value, 2),
            "amount_paid": amount_paid,
            "points_earned": points_earned,
        },
        "payment": {
            "id": str(payment.id) if payment else None,
            "method": payment.method if payment else None,
            "status": payment.status if payment else None,
            "transaction_id": payment.transaction_id if payment else None,
            "card_last_four": payment.card_last_four if payment else None,
            "currency": payment.currency if payment else "USD",
            "created_at": payment.created_at.isoformat() if payment else None,
        } if payment else None,
        "addons": {
            "baggage": [
                {"tag_id": b["tag_id"], "bag_type": b["bag_type"], "weight_kg": b["weight_kg"], "fee": b["fee"]}
                for b in bags
            ],
            "baggage_total": baggage_total,
        },
    }


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    from ..models.payment import Payment, RefundRecord

    result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    payment_result = await db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    )
    payment = payment_result.scalar_one_or_none()

    booking.status = "cancelled"

    cancel_record = RefundRecord(
        booking_id=booking.id,
        user_id=UUID(current_user["sub"]),
        action_type="cancellation",
        amount=0,
        reason="Cancelled via booking management",
        refund_method=None,
        card_last_four=None,
        status="completed",
        pnr=booking.pnr,
    )
    db.add(cancel_record)

    if payment and payment.amount > 0:
        refund_record = RefundRecord(
            booking_id=booking.id,
            user_id=UUID(current_user["sub"]),
            action_type="refund",
            amount=payment.amount,
            reason="Refund for cancellation",
            refund_method="card" if payment.card_last_four else "none",
            card_last_four=payment.card_last_four,
            status="completed",
            pnr=booking.pnr,
        )
        db.add(refund_record)

    await db.commit()

    return {"status": "cancelled", "pnr": booking.pnr}
