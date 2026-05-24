from langchain_core.tools import tool

CITY_TO_IATA = {
    "NEW YORK": "JFK", "NYC": "JFK", "NEWARK": "EWR",
    "LOS ANGELES": "LAX", "LA": "LAX",
    "SAN FRANCISCO": "SFO", "SF": "SFO",
    "CHICAGO": "ORD",
    "DALLAS": "DFW",
    "ATLANTA": "ATL",
    "MIAMI": "MIA",
    "DENVER": "DEN",
    "SEATTLE": "SEA",
    "BOSTON": "BOS",
    "WASHINGTON": "IAD", "DC": "IAD",
    "LONDON": "LHR", "HEATHROW": "LHR",
    "PARIS": "CDG",
    "FRANKFURT": "FRA",
    "AMSTERDAM": "AMS",
    "DUBAI": "DXB",
    "SINGAPORE": "SIN",
    "TOKYO": "NRT", "NARITA": "NRT",
    "HONG KONG": "HKG",
    "SYDNEY": "SYD",
    "DELHI": "DEL", "NEW DELHI": "DEL",
    "MUMBAI": "BOM", "BOMBAY": "BOM",
    "BANGALORE": "BLR", "BENGALURU": "BLR",
    "HYDERABAD": "HYD",
    "CHENNAI": "MAA", "MADRAS": "MAA",
    "KOLKATA": "CCU", "CALCUTTA": "CCU",
    "GOA": "GOI",
    "AHMEDABAD": "AMD",
    "PUNE": "PNQ",
    "JAIPUR": "JAI",
    "DOHA": "DOH",
    "SAO PAULO": "GRU",
    "MEXICO CITY": "MEX",
    "TORONTO": "YYZ",
    "BANGKOK": "BKK",
    "KUALA LUMPUR": "KUL",
}


def resolve_iata(code: str) -> str:
    upper = code.strip().upper()
    return CITY_TO_IATA.get(upper, upper)


@tool
async def search_flights_tool(origin: str, destination: str, date: str | None = None) -> str:
    """Search for available flights between two airports. Use IATA codes (DEL, BOM, JFK, LAX, etc.) or city names (Delhi, Mumbai, New York, etc.)."""
    from ...database import async_session
    from ...models.flight import Flight
    from ...models.booking import Booking
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from sqlalchemy import select, and_
    from datetime import datetime

    origin = resolve_iata(origin)
    destination = resolve_iata(destination)

    async with async_session() as db:
        query = select(Flight)
        conditions = []
        if origin:
            conditions.append(Flight.origin == origin.upper())
        if destination:
            conditions.append(Flight.destination == destination.upper())
        if conditions:
            query = query.where(and_(*conditions))
        result = await db.execute(query)
        flights = result.scalars().all()

        if date:
            try:
                target = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                try:
                    target = datetime.fromisoformat(date).date()
                except ValueError:
                    return f"Invalid date format: {date}. Use YYYY-MM-DD."

            flights = [f for f in flights if flight_operates_on(f, target)]

            results = []
            for f in flights[:10]:
                booked = await count_bookings_for_flight_date(db, f.id, target)
                price = compute_dynamic_price(f.base_price, booked, f.total_seats)
                available = max(0, f.total_seats - booked)
                dep, arr = project_flight_to_date(f, target)
                duration_min = int((arr - dep).total_seconds() / 60)
                duration_str = f"{duration_min // 60}h {duration_min % 60}m"
                results.append(
                    f"[{f.id}] {f.flight_number}: {f.origin} → {f.destination} | "
                    f"{dep.strftime('%Y-%m-%d %H:%M')} → {arr.strftime('%H:%M')} ({duration_str}) | "
                    f"Aircraft: {f.aircraft} | "
                    f"Price: ${price:.2f} (base ${f.base_price:.2f}) | "
                    f"Seats: {available}/{f.total_seats}"
                )
        else:
            results = []
            for f in flights[:10]:
                results.append(
                    f"[{f.id}] {f.flight_number}: {f.origin} → {f.destination} | "
                    f"Departs: {f.departure.strftime('%H:%M')} | "
                    f"Aircraft: {f.aircraft} | "
                    f"Price: ${f.base_price:.2f} | Seats: {f.available_seats} | "
                    f"Schedule: {f.days_of_week or 'one-off'}"
                )

    if not results:
        return "No flights found for this route."

    return "\n".join(results)


@tool
async def get_flight_tool(flight_id: str) -> str:
    """Get detailed information about a specific flight by ID."""
    from ...database import async_session
    from ...models.flight import Flight
    from sqlalchemy import select
    from uuid import UUID

    async with async_session() as db:
        try:
            result = await db.execute(select(Flight).where(Flight.id == UUID(flight_id)))
        except Exception as e:
            return f"Error retrieving flight: {str(e)}. Connection: postgres-internal.autopilot.svc:5432/autopilot"
        flight = result.scalar_one_or_none()

    if not flight:
        return "Flight not found."

    schedule_desc = "One-off flight"
    if flight.days_of_week:
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if flight.days_of_week == "0123456":
            schedule_desc = "Daily"
        else:
            schedule_desc = "/".join(day_names[int(d)] for d in sorted(flight.days_of_week))

    validity = ""
    if flight.valid_from or flight.valid_until:
        validity = f"\nValid: {flight.valid_from or 'start'} to {flight.valid_until or 'ongoing'}"

    return (
        f"Flight {flight.flight_number}\n"
        f"Route: {flight.origin} → {flight.destination}\n"
        f"Departure: {flight.departure.strftime('%H:%M')} UTC\n"
        f"Arrival: {flight.arrival.strftime('%H:%M')} UTC\n"
        f"Aircraft: {flight.aircraft}\n"
        f"Status: {flight.status}\n"
        f"Base Price: ${flight.base_price}\n"
        f"Total Seats: {flight.total_seats}\n"
        f"Schedule: {schedule_desc}{validity}"
    )
