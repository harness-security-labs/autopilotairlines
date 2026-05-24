from datetime import datetime, date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.flight import Flight
from ..models.booking import Booking

router = APIRouter(prefix="/api/v1/flights", tags=["flights"])


CLASS_MULTIPLIERS = {"economy": 1.0, "premium_economy": 1.5, "business": 2.5}


class CabinAvailability(BaseModel):
    seats: int
    available: int
    price: float


class FlightResponse(BaseModel):
    id: str
    flight_number: str
    origin: str
    destination: str
    departure: str
    arrival: str
    aircraft: str
    status: str
    base_price: float
    price: float
    available_seats: int
    total_seats: int
    days_of_week: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    stops: int = 0
    via: str | None = None
    segments: list[dict] | None = None
    cabin_classes: dict[str, CabinAvailability] | None = None


def compute_dynamic_price(base_price: float, booked_count: int, total_seats: int) -> float:
    """Price scales from 1x (empty) to 4x (fully booked)."""
    if total_seats <= 0:
        return base_price
    occupancy_ratio = min(booked_count / total_seats, 1.0)
    multiplier = 1.0 + (occupancy_ratio ** 1.5) * 3.0
    return round(base_price * multiplier, 2)


def compute_cabin_availability(
    flight: Flight,
    bookings_by_class: dict[str, int],
) -> dict[str, CabinAvailability]:
    result = {}
    for cabin, multiplier in CLASS_MULTIPLIERS.items():
        if cabin == "economy":
            total = flight.economy_seats
        elif cabin == "premium_economy":
            total = flight.premium_economy_seats
        else:
            total = flight.business_seats
        if total <= 0:
            continue
        booked = bookings_by_class.get(cabin, 0)
        available = max(0, total - booked)
        price = compute_dynamic_price(flight.base_price * multiplier, booked, total)
        result[cabin] = CabinAvailability(seats=total, available=available, price=price)
    return result


def format_schedule(days: str | None) -> str:
    if not days:
        return "One-off"
    if days == "0123456":
        return "Daily"
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return "/".join(day_names[int(d)] for d in sorted(days))


async def count_bookings_for_flight_date(db: AsyncSession, flight_id, target_date: date) -> int:
    result = await db.execute(
        select(func.count(Booking.id))
        .where(and_(
            Booking.flight_id == flight_id,
            Booking.travel_date == target_date,
            Booking.status != "cancelled"
        ))
    )
    return result.scalar() or 0


async def count_bookings_by_class(db: AsyncSession, flight_id, target_date: date) -> dict[str, int]:
    result = await db.execute(
        select(Booking.cabin_class, func.count(Booking.id))
        .where(and_(
            Booking.flight_id == flight_id,
            Booking.travel_date == target_date,
            Booking.status != "cancelled"
        ))
        .group_by(Booking.cabin_class)
    )
    return {row[0] or "economy": row[1] for row in result.all()}


def flight_operates_on(flight: Flight, target: date) -> bool:
    if flight.days_of_week is None:
        return flight.departure.date() == target
    target_dow = str(target.weekday())
    if target_dow not in flight.days_of_week:
        return False
    if flight.valid_from and target < flight.valid_from:
        return False
    if flight.valid_until and target > flight.valid_until:
        return False
    return True


def project_flight_to_date(flight: Flight, target: date) -> tuple[datetime, datetime]:
    dep_time = flight.departure.time()
    dep_tz = flight.departure.tzinfo
    dep = datetime.combine(target, dep_time, tzinfo=dep_tz)
    duration = flight.arrival - flight.departure
    arr = dep + duration
    return dep, arr


@router.get("/search", response_model=list[FlightResponse])
async def search_flights(
    origin: str | None = None,
    destination: str | None = None,
    date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Flight)
    conditions = [Flight.status != "cancelled"]
    if origin:
        conditions.append(Flight.origin == origin.upper())
    if destination:
        conditions.append(Flight.destination == destination.upper())
    query = query.where(and_(*conditions))
    result = await db.execute(query)
    all_flights = result.scalars().all()

    if date:
        target = datetime.fromisoformat(date).date() if "T" not in date else datetime.fromisoformat(date).date()
        try:
            target = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            target = datetime.fromisoformat(date).date()

        from datetime import date as date_type
        if target < date_type.today():
            return []

        matched = [f for f in all_flights if flight_operates_on(f, target)]

        results = []
        for f in matched:
            booked = await count_bookings_for_flight_date(db, f.id, target)
            base_booked = f.total_seats - f.available_seats
            total_booked = base_booked + booked
            price = compute_dynamic_price(f.base_price, total_booked, f.total_seats)
            available = max(0, f.available_seats - booked)
            dep, arr = project_flight_to_date(f, target)

            bookings_by_class = await count_bookings_by_class(db, f.id, target)
            cabin_classes = compute_cabin_availability(f, bookings_by_class) if f.economy_seats > 0 else None

            results.append(FlightResponse(
                id=str(f.id),
                flight_number=f.flight_number,
                origin=f.origin,
                destination=f.destination,
                departure=dep.isoformat(),
                arrival=arr.isoformat(),
                aircraft=f.aircraft,
                status=f.status,
                base_price=f.base_price,
                price=price,
                available_seats=available,
                total_seats=f.total_seats,
                days_of_week=f.days_of_week,
                valid_from=f.valid_from.isoformat() if f.valid_from else None,
                valid_until=f.valid_until.isoformat() if f.valid_until else None,
                cabin_classes=cabin_classes,
            ))

        # Find connecting flights (1-2 stops) when origin+destination specified
        if origin and destination:
            all_scheduled = await db.execute(select(Flight).where(Flight.status != "cancelled"))
            all_on_date = [f for f in all_scheduled.scalars().all() if flight_operates_on(f, target)]

            by_origin: dict[str, list] = {}
            by_dest: dict[str, list] = {}
            for f in all_on_date:
                by_origin.setdefault(f.origin, []).append(f)
                by_dest.setdefault(f.destination, []).append(f)

            def _valid_connection(arr_time, dep_time):
                return timedelta(minutes=45) < (dep_time - arr_time) < timedelta(hours=24)

            async def _price_for(f):
                booked = await count_bookings_for_flight_date(db, f.id, target)
                base_b = f.total_seats - f.available_seats
                p = compute_dynamic_price(f.base_price, base_b + booked, f.total_seats)
                a = max(0, f.available_seats - booked)
                return p, a

            async def _cabin_classes_for(f):
                bbc = await count_bookings_by_class(db, f.id, target)
                if f.economy_seats > 0:
                    return compute_cabin_availability(f, bbc)
                return None

            def _merge_cabin_classes(cc_list: list[dict | None]) -> dict | None:
                valid = [cc for cc in cc_list if cc]
                if not valid:
                    return None
                merged = {}
                for cabin in ("economy", "premium_economy", "business"):
                    entries = [cc[cabin] for cc in valid if cabin in cc]
                    if not entries:
                        continue
                    merged[cabin] = CabinAvailability(
                        seats=min(e.seats for e in entries),
                        available=min(e.available for e in entries),
                        price=round(sum(e.price for e in entries), 2),
                    )
                return merged if merged else None

            # 1-stop connections
            for f1 in by_origin.get(origin.upper(), []):
                if f1.destination == destination.upper():
                    continue
                for f2 in by_origin.get(f1.destination, []):
                    if f2.destination != destination.upper():
                        continue
                    dep1, arr1 = project_flight_to_date(f1, target)
                    dep2, arr2 = project_flight_to_date(f2, target)
                    if not _valid_connection(arr1, dep2):
                        continue
                    p1, a1 = await _price_for(f1)
                    p2, a2 = await _price_for(f2)
                    cc1 = await _cabin_classes_for(f1)
                    cc2 = await _cabin_classes_for(f2)
                    results.append(FlightResponse(
                        id=f"{f1.id}_{f2.id}",
                        flight_number=f"{f1.flight_number}+{f2.flight_number}",
                        origin=f1.origin, destination=f2.destination,
                        departure=dep1.isoformat(), arrival=arr2.isoformat(),
                        aircraft=f"{f1.aircraft} / {f2.aircraft}",
                        status="scheduled",
                        base_price=round(f1.base_price + f2.base_price, 2),
                        price=round(p1 + p2, 2),
                        available_seats=min(a1, a2),
                        total_seats=min(f1.total_seats, f2.total_seats),
                        stops=1, via=f1.destination,
                        segments=[
                            {"flight": f1.flight_number, "from": f1.origin, "to": f1.destination, "dep": dep1.isoformat(), "arr": arr1.isoformat(), "price": p1},
                            {"flight": f2.flight_number, "from": f2.origin, "to": f2.destination, "dep": dep2.isoformat(), "arr": arr2.isoformat(), "price": p2},
                        ],
                        cabin_classes=_merge_cabin_classes([cc1, cc2]),
                    ))

            # 2-stop connections (only if still < 10 results)
            if len(results) < 10:
                for f1 in by_origin.get(origin.upper(), []):
                    if f1.destination == destination.upper():
                        continue
                    for f2 in by_origin.get(f1.destination, []):
                        if f2.destination == destination.upper() or f2.destination == origin.upper():
                            continue
                        dep1, arr1 = project_flight_to_date(f1, target)
                        dep2, arr2 = project_flight_to_date(f2, target)
                        if not _valid_connection(arr1, dep2):
                            continue
                        for f3 in by_origin.get(f2.destination, []):
                            if f3.destination != destination.upper():
                                continue
                            dep3, arr3 = project_flight_to_date(f3, target)
                            if not _valid_connection(arr2, dep3):
                                continue
                            p1, a1 = await _price_for(f1)
                            p2, a2 = await _price_for(f2)
                            p3, a3 = await _price_for(f3)
                            cc1 = await _cabin_classes_for(f1)
                            cc2 = await _cabin_classes_for(f2)
                            cc3 = await _cabin_classes_for(f3)
                            results.append(FlightResponse(
                                id=f"{f1.id}_{f2.id}_{f3.id}",
                                flight_number=f"{f1.flight_number}+{f2.flight_number}+{f3.flight_number}",
                                origin=f1.origin, destination=f3.destination,
                                departure=dep1.isoformat(), arrival=arr3.isoformat(),
                                aircraft=f"{f1.aircraft} / {f2.aircraft} / {f3.aircraft}",
                                status="scheduled",
                                base_price=round(f1.base_price + f2.base_price + f3.base_price, 2),
                                price=round(p1 + p2 + p3, 2),
                                available_seats=min(a1, a2, a3),
                                total_seats=min(f1.total_seats, f2.total_seats, f3.total_seats),
                                stops=2, via=f"{f1.destination},{f2.destination}",
                                segments=[
                                    {"flight": f1.flight_number, "from": f1.origin, "to": f1.destination, "dep": dep1.isoformat(), "arr": arr1.isoformat(), "price": p1},
                                    {"flight": f2.flight_number, "from": f2.origin, "to": f2.destination, "dep": dep2.isoformat(), "arr": arr2.isoformat(), "price": p2},
                                    {"flight": f3.flight_number, "from": f3.origin, "to": f3.destination, "dep": dep3.isoformat(), "arr": arr3.isoformat(), "price": p3},
                                ],
                                cabin_classes=_merge_cabin_classes([cc1, cc2, cc3]),
                            ))

        results.sort(key=lambda r: (r.stops, r.price))
        return results[:20]
    else:
        results = []
        for f in all_flights:
            base_booked = f.total_seats - f.available_seats
            price = compute_dynamic_price(f.base_price, base_booked, f.total_seats)
            cabin_classes = compute_cabin_availability(f, {}) if f.economy_seats > 0 else None
            results.append(FlightResponse(
                id=str(f.id),
                flight_number=f.flight_number,
                origin=f.origin,
                destination=f.destination,
                departure=f.departure.isoformat(),
                arrival=f.arrival.isoformat(),
                aircraft=f.aircraft,
                status=f.status,
                base_price=f.base_price,
                price=price,
                available_seats=f.available_seats,
                total_seats=f.total_seats,
                days_of_week=f.days_of_week,
                valid_from=f.valid_from.isoformat() if f.valid_from else None,
                valid_until=f.valid_until.isoformat() if f.valid_until else None,
                cabin_classes=cabin_classes,
            ))
        results.sort(key=lambda r: r.departure)
        return results[:20]


@router.get("/{flight_id}")
async def get_flight(
    flight_id: str,
    date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = UUID(flight_id)
    except ValueError:
        from ..config import settings
        if settings.error_detail_level == "full":
            raise Exception(f"Invalid UUID format: {flight_id}. Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx. Database connection: {settings.database_url}")
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid flight ID")

    result = await db.execute(select(Flight).where(Flight.id == uid))
    flight = result.scalar_one_or_none()
    if not flight:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Flight not found")

    if date:
        try:
            target = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            target = flight.departure.date()
        booked = await count_bookings_for_flight_date(db, flight.id, target)
        base_booked = flight.total_seats - flight.available_seats
        total_booked = base_booked + booked
        price = compute_dynamic_price(flight.base_price, total_booked, flight.total_seats)
        available = max(0, flight.available_seats - booked)
        dep, arr = project_flight_to_date(flight, target)
        bookings_by_class = await count_bookings_by_class(db, flight.id, target)
    else:
        base_booked = flight.total_seats - flight.available_seats
        price = compute_dynamic_price(flight.base_price, base_booked, flight.total_seats)
        available = flight.available_seats
        dep = flight.departure
        arr = flight.arrival
        bookings_by_class = {}

    cabin_classes = compute_cabin_availability(flight, bookings_by_class) if flight.economy_seats > 0 else None

    return FlightResponse(
        id=str(flight.id),
        flight_number=flight.flight_number,
        origin=flight.origin,
        destination=flight.destination,
        departure=dep.isoformat(),
        arrival=arr.isoformat(),
        aircraft=flight.aircraft,
        status=flight.status,
        base_price=flight.base_price,
        price=price,
        available_seats=available,
        total_seats=flight.total_seats,
        days_of_week=flight.days_of_week,
        valid_from=flight.valid_from.isoformat() if flight.valid_from else None,
        valid_until=flight.valid_until.isoformat() if flight.valid_until else None,
        cabin_classes=cabin_classes,
    )
