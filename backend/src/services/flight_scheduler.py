import asyncio
import random
import uuid
import logging
from datetime import datetime, date, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session
from ..models.flight import Flight
from ..models.booking import Booking

logger = logging.getLogger("flight_scheduler")

AIRPORTS = [
    "SFO", "JFK", "LAX", "ORD", "MIA", "SEA", "BOS", "ATL", "DFW",
    "DEL", "BOM", "BLR", "HYD", "MAA", "CCU",
    "LHR", "CDG", "FRA",
    "DXB", "SIN", "HKG", "NRT", "ICN",
    "SYD", "GRU", "MEX", "YVR", "MLE", "CUN",
]

AIRCRAFT = [
    ("Boeing 737-800", 156),
    ("Boeing 737 MAX 8", 175),
    ("Airbus A320neo", 180),
    ("Airbus A321neo", 190),
    ("Boeing 787-9", 250),
    ("Boeing 787-9 Dreamliner", 250),
    ("Airbus A350-900", 300),
    ("Boeing 777-300ER", 300),
    ("Boeing 777-200LR", 280),
    ("Airbus A350-1000", 280),
]

SHORT_HAUL_AIRCRAFT = [
    ("Boeing 737-800", 156),
    ("Boeing 737 MAX 8", 175),
    ("Airbus A320neo", 180),
    ("Airbus A321neo", 190),
    ("Embraer E195-E2", 120),
]

LONG_HAUL_AIRCRAFT = [
    ("Boeing 787-9", 250),
    ("Boeing 787-9 Dreamliner", 250),
    ("Airbus A350-900", 300),
    ("Boeing 777-300ER", 300),
    ("Boeing 777-200LR", 280),
    ("Airbus A350-1000", 280),
]

HOLIDAYS = [
    (1, 1, "New Year"),
    (2, 14, "Valentine's Day"),
    (3, 17, "St Patrick's Day"),
    (5, 26, "Memorial Day"),
    (7, 4, "Independence Day"),
    (9, 1, "Labor Day"),
    (10, 31, "Halloween"),
    (11, 27, "Thanksgiving"),
    (12, 24, "Christmas Eve"),
    (12, 25, "Christmas"),
    (12, 31, "New Year's Eve"),
    (1, 26, "Republic Day"),
    (8, 15, "Independence Day India"),
    (10, 15, "Dussehra"),
    (11, 1, "Diwali"),
]

POPULAR_HOLIDAY_ROUTES = [
    ("JFK", "MIA"), ("LAX", "SFO"), ("SFO", "JFK"), ("ORD", "MIA"),
    ("JFK", "CUN"), ("LAX", "GRU"), ("LHR", "MLE"), ("DEL", "MLE"),
    ("DEL", "DXB"), ("BOM", "LHR"), ("SFO", "NRT"), ("LAX", "SYD"),
    ("BLR", "SIN"), ("DEL", "BOM"), ("HKG", "NRT"), ("DXB", "LHR"),
]

DEMAND_ROUTES = [
    ("SFO", "JFK"), ("JFK", "SFO"), ("LAX", "ORD"), ("ORD", "LAX"),
    ("DEL", "BOM"), ("BOM", "DEL"), ("DEL", "BLR"), ("BLR", "DEL"),
    ("LHR", "CDG"), ("CDG", "LHR"), ("DXB", "DEL"), ("DEL", "DXB"),
    ("SIN", "HKG"), ("HKG", "SIN"), ("JFK", "LHR"), ("LHR", "JFK"),
]


def _estimate_duration_hours(origin: str, destination: str) -> float:
    domestic_us = {"SFO", "JFK", "LAX", "ORD", "MIA", "SEA", "BOS", "ATL", "DFW"}
    domestic_in = {"DEL", "BOM", "BLR", "HYD", "MAA", "CCU"}
    europe = {"LHR", "CDG", "FRA"}
    asia = {"NRT", "ICN", "SIN", "HKG"}

    if origin in domestic_us and destination in domestic_us:
        return random.uniform(2.5, 5.5)
    if origin in domestic_in and destination in domestic_in:
        return random.uniform(1.5, 3.0)
    if origin in europe and destination in europe:
        return random.uniform(1.5, 2.5)
    if origin in asia and destination in asia:
        return random.uniform(2.0, 5.0)
    if (origin in domestic_us and destination in europe) or (origin in europe and destination in domestic_us):
        return random.uniform(7.0, 10.0)
    if (origin in domestic_us and destination in asia) or (origin in asia and destination in domestic_us):
        return random.uniform(10.0, 16.0)
    if (origin in domestic_in and destination in asia) or (origin in asia and destination in domestic_in):
        return random.uniform(4.0, 7.0)
    return random.uniform(3.0, 12.0)


def _compute_base_price(duration_hours: float) -> float:
    per_hour = random.uniform(60, 120)
    return round(duration_hours * per_hour + random.uniform(-20, 50), 2)


def _generate_flight_number() -> str:
    return f"AP{random.randint(2000, 9999)}"


async def _count_upcoming_bookings(db: AsyncSession, origin: str, destination: str, target_date: date) -> int:
    result = await db.execute(
        select(func.count(Booking.id))
        .join(Flight, Booking.flight_id == Flight.id)
        .where(and_(
            Flight.origin == origin,
            Flight.destination == destination,
            Booking.travel_date == target_date,
            Booking.status != "cancelled",
        ))
    )
    return result.scalar() or 0


async def _route_has_flight_on_date(db: AsyncSession, origin: str, destination: str, target_date: date) -> int:
    """Count flights operating on a specific date (recurring + one-off)."""
    from sqlalchemy import or_, cast, Date as SADate
    day_of_week = str(target_date.weekday())
    result = await db.execute(
        select(func.count(Flight.id))
        .where(and_(
            Flight.origin == origin,
            Flight.destination == destination,
            or_(
                Flight.days_of_week.contains(day_of_week),
                and_(Flight.days_of_week.is_(None), cast(Flight.departure, SADate) == target_date),
            ),
        ))
    )
    return result.scalar() or 0


AIRCRAFT_CABIN_CONFIG: dict[str, tuple[int, int, int]] = {
    # (economy, premium_economy, business) — actual counts per aircraft type
    "Embraer E195-E2": (108, 12, 0),
    "Boeing 737-800": (114, 30, 12),
    "Boeing 737 MAX 8": (129, 30, 16),
    "Airbus A320neo": (132, 32, 16),
    "Airbus A321neo": (142, 32, 16),
    "Boeing 787-9": (168, 52, 30),
    "Boeing 787-9 Dreamliner": (168, 52, 30),
    "Airbus A350-900": (198, 66, 36),
    "Boeing 777-300ER": (196, 66, 38),
    "Boeing 777-200LR": (184, 60, 36),
    "Airbus A350-1000": (184, 60, 36),
}


def _allocate_cabin_seats(total_seats: int, aircraft_name: str) -> tuple[int, int, int]:
    """Allocate seats based on aircraft type configuration."""
    if aircraft_name in AIRCRAFT_CABIN_CONFIG:
        economy, premium, business = AIRCRAFT_CABIN_CONFIG[aircraft_name]
        actual_total = economy + premium + business
        if actual_total != total_seats:
            economy = total_seats - premium - business
        return economy, premium, business
    business = max(8, int(total_seats * 0.10))
    premium = max(12, int(total_seats * 0.20))
    economy = total_seats - business - premium
    return economy, premium, business


async def add_demand_flight(db: AsyncSession, origin: str, destination: str, target_date: date) -> Flight | None:
    """Add a one-off flight for a specific date (days_of_week=NULL, departure set to target_date)."""
    duration_hours = _estimate_duration_hours(origin, destination)
    is_long_haul = duration_hours > 6
    aircraft_name, total_seats = random.choice(LONG_HAUL_AIRCRAFT if is_long_haul else SHORT_HAUL_AIRCRAFT)

    dep_hour = random.randint(5, 22)
    dep_minute = random.choice([0, 15, 30, 45])
    departure = datetime(target_date.year, target_date.month, target_date.day, dep_hour, dep_minute, tzinfo=timezone.utc)
    arrival = departure + timedelta(hours=duration_hours)

    economy, premium, business = _allocate_cabin_seats(total_seats, aircraft_name)

    flight = Flight(
        id=uuid.uuid4(),
        flight_number=_generate_flight_number(),
        origin=origin,
        destination=destination,
        departure=departure,
        arrival=arrival,
        aircraft=aircraft_name,
        status="scheduled",
        base_price=_compute_base_price(duration_hours),
        available_seats=total_seats,
        days_of_week=None,
        total_seats=total_seats,
        economy_seats=economy,
        premium_economy_seats=premium,
        business_seats=business,
    )
    db.add(flight)
    await db.commit()
    await db.refresh(flight)
    logger.info(f"Added demand flight {flight.flight_number} {origin}->{destination} on {target_date}")
    return flight


async def add_holiday_flights(db: AsyncSession, holiday_date: date, holiday_name: str) -> list[Flight]:
    """Add flights for a short window around a holiday (2 days before to 1 day after)."""
    added = []
    routes = random.sample(POPULAR_HOLIDAY_ROUTES, min(random.randint(3, 6), len(POPULAR_HOLIDAY_ROUTES)))

    window_start = holiday_date - timedelta(days=2)
    window_end = holiday_date + timedelta(days=1)
    window_days = set()
    d = window_start
    while d <= window_end:
        window_days.add(str(d.weekday()))
        d += timedelta(days=1)
    days_of_week = "".join(sorted(window_days))

    for origin, destination in routes:
        existing = await _route_has_flight_on_date(db, origin, destination, holiday_date)
        if existing >= 3:
            continue

        duration_hours = _estimate_duration_hours(origin, destination)
        is_long_haul = duration_hours > 6
        aircraft_name, total_seats = random.choice(LONG_HAUL_AIRCRAFT if is_long_haul else SHORT_HAUL_AIRCRAFT)

        dep_hour = random.randint(6, 20)
        dep_minute = random.choice([0, 15, 30, 45])
        departure = datetime(2025, 7, 15, dep_hour, dep_minute, tzinfo=timezone.utc)
        arrival = departure + timedelta(hours=duration_hours)

        economy, premium, business = _allocate_cabin_seats(total_seats, aircraft_name)

        flight = Flight(
            id=uuid.uuid4(),
            flight_number=f"AP{random.randint(7000, 7999)}",
            origin=origin,
            destination=destination,
            departure=departure,
            arrival=arrival,
            aircraft=aircraft_name,
            status="scheduled",
            base_price=round(_compute_base_price(duration_hours) * random.uniform(1.1, 1.4), 2),
            available_seats=total_seats,
            days_of_week=days_of_week,
            valid_from=window_start,
            valid_until=window_end,
            total_seats=total_seats,
            economy_seats=economy,
            premium_economy_seats=premium,
            business_seats=business,
        )
        db.add(flight)
        added.append(flight)

    if added:
        await db.commit()
        logger.info(f"Added {len(added)} holiday flights for {holiday_name} ({window_start} to {window_end})")
    return added


async def check_and_add_demand_flights():
    today = date.today()
    lookahead_days = [today + timedelta(days=d) for d in range(1, 8)]

    async with async_session() as db:
        for target_date in lookahead_days:
            routes_to_check = random.sample(DEMAND_ROUTES, min(4, len(DEMAND_ROUTES)))
            for origin, destination in routes_to_check:
                existing = await _route_has_flight_on_date(db, origin, destination, target_date)
                if existing >= 2:
                    continue
                bookings_count = await _count_upcoming_bookings(db, origin, destination, target_date)
                if bookings_count >= 3 or (existing == 0 and random.random() < 0.3):
                    await add_demand_flight(db, origin, destination, target_date)


async def check_and_add_holiday_flights():
    today = date.today()

    async with async_session() as db:
        for month, day, name in HOLIDAYS:
            try:
                holiday_date = date(today.year, month, day)
            except ValueError:
                continue
            days_until = (holiday_date - today).days
            if 0 <= days_until <= 14:
                await add_holiday_flights(db, holiday_date, name)


async def run_scheduler():
    logger.info("Flight scheduler started")
    await asyncio.sleep(5)

    while True:
        try:
            await check_and_add_demand_flights()
            await check_and_add_holiday_flights()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        await asyncio.sleep(3600)
