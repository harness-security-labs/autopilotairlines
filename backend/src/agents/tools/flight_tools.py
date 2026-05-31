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
    """Search for available flights between two airports. Use IATA codes (DEL, BOM, JFK, LAX, etc.) or city names (Delhi, Mumbai, New York, etc.).
    Returns direct and connecting flights with full details including stops and segments."""
    from ...database import async_session
    from ...models.flight import Flight
    from ...models.booking import Booking
    from ...routers.flights import flight_operates_on, project_flight_to_date, compute_dynamic_price, count_bookings_for_flight_date
    from sqlalchemy import select, and_
    from datetime import datetime, timedelta

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
                    f"Dep: {dep.strftime('%Y-%m-%d %H:%M')} → Arr: {arr.strftime('%H:%M')} ({duration_str}) | "
                    f"Stops: 0 (Direct) | "
                    f"Price: ${price:.2f} | "
                    f"Seats: {available}/{f.total_seats}"
                )

            if origin and destination:
                all_scheduled = await db.execute(select(Flight).where(Flight.status != "cancelled"))
                all_on_date = [f for f in all_scheduled.scalars().all() if flight_operates_on(f, target)]

                by_origin: dict[str, list] = {}
                for f in all_on_date:
                    by_origin.setdefault(f.origin, []).append(f)

                def _valid_connection(arr_time, dep_time):
                    return timedelta(minutes=45) < (dep_time - arr_time) < timedelta(hours=24)

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
                        b1 = await count_bookings_for_flight_date(db, f1.id, target)
                        b2 = await count_bookings_for_flight_date(db, f2.id, target)
                        p1 = compute_dynamic_price(f1.base_price, b1, f1.total_seats)
                        p2 = compute_dynamic_price(f2.base_price, b2, f2.total_seats)
                        a1 = max(0, f1.total_seats - b1)
                        a2 = max(0, f2.total_seats - b2)
                        total_price = round(p1 + p2, 2)
                        total_duration = int((arr2 - dep1).total_seconds() / 60)
                        layover = int((dep2 - arr1).total_seconds() / 60)
                        results.append(
                            f"[{f1.id}_{f2.id}] {f1.flight_number}+{f2.flight_number}: {f1.origin} → {f2.destination} | "
                            f"Dep: {dep1.strftime('%Y-%m-%d %H:%M')} → Arr: {arr2.strftime('%H:%M')} ({total_duration // 60}h {total_duration % 60}m) | "
                            f"Stops: 1 via {f1.destination} (layover {layover // 60}h {layover % 60}m) | "
                            f"  Seg1: {f1.flight_number} {f1.origin}→{f1.destination} {dep1.strftime('%H:%M')}→{arr1.strftime('%H:%M')} | "
                            f"  Seg2: {f2.flight_number} {f2.origin}→{f2.destination} {dep2.strftime('%H:%M')}→{arr2.strftime('%H:%M')} | "
                            f"Price: ${total_price:.2f} | "
                            f"Seats: {min(a1, a2)}"
                        )

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
                                b1 = await count_bookings_for_flight_date(db, f1.id, target)
                                b2 = await count_bookings_for_flight_date(db, f2.id, target)
                                b3 = await count_bookings_for_flight_date(db, f3.id, target)
                                p1 = compute_dynamic_price(f1.base_price, b1, f1.total_seats)
                                p2 = compute_dynamic_price(f2.base_price, b2, f2.total_seats)
                                p3 = compute_dynamic_price(f3.base_price, b3, f3.total_seats)
                                a1 = max(0, f1.total_seats - b1)
                                a2 = max(0, f2.total_seats - b2)
                                a3 = max(0, f3.total_seats - b3)
                                total_price = round(p1 + p2 + p3, 2)
                                total_duration = int((arr3 - dep1).total_seconds() / 60)
                                lay1 = int((dep2 - arr1).total_seconds() / 60)
                                lay2 = int((dep3 - arr2).total_seconds() / 60)
                                results.append(
                                    f"[{f1.id}_{f2.id}_{f3.id}] {f1.flight_number}+{f2.flight_number}+{f3.flight_number}: {f1.origin} → {f3.destination} | "
                                    f"Dep: {dep1.strftime('%Y-%m-%d %H:%M')} → Arr: {arr3.strftime('%H:%M')} ({total_duration // 60}h {total_duration % 60}m) | "
                                    f"Stops: 2 via {f1.destination}, {f2.destination} (layovers {lay1 // 60}h {lay1 % 60}m + {lay2 // 60}h {lay2 % 60}m) | "
                                    f"  Seg1: {f1.flight_number} {f1.origin}→{f1.destination} {dep1.strftime('%H:%M')}→{arr1.strftime('%H:%M')} | "
                                    f"  Seg2: {f2.flight_number} {f2.origin}→{f2.destination} {dep2.strftime('%H:%M')}→{arr2.strftime('%H:%M')} | "
                                    f"  Seg3: {f3.flight_number} {f3.origin}→{f3.destination} {dep3.strftime('%H:%M')}→{arr3.strftime('%H:%M')} | "
                                    f"Price: ${total_price:.2f} | "
                                    f"Seats: {min(a1, a2, a3)}"
                                )

            results.sort(key=lambda r: ("Stops: 0" not in r, r))
        else:
            results = []
            for f in flights[:10]:
                results.append(
                    f"[{f.id}] {f.flight_number}: {f.origin} → {f.destination} | "
                    f"Dep: {f.departure.strftime('%H:%M')} → Arr: {f.arrival.strftime('%H:%M')} | "
                    f"Stops: 0 (Direct) | "
                    f"Price: ${f.base_price:.2f} | Seats: {f.available_seats}/{f.total_seats} | "
                    f"Schedule: {f.days_of_week or 'one-off'}"
                )

    if not results:
        return "No flights found for this route."

    return "\n".join(results[:15])


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
