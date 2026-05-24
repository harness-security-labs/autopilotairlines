CONTACTS: list[dict] = [
    {"id": "crm-001", "name": "John Smith", "email": "john@example.com", "status": "active", "notes": "Frequent flyer, gold tier"},
    {"id": "crm-002", "name": "Jane Doe", "email": "jane@example.com", "status": "active", "notes": "Platinum member, VIP"},
    {"id": "crm-003", "name": "Bob Johnson", "email": "bob@corporate.com", "status": "active", "notes": "Corporate account"},
]

TICKETS: list[dict] = []


async def search_contacts(query: str) -> list[dict]:
    return [c for c in CONTACTS if query.lower() in c["name"].lower() or query.lower() in c["email"].lower()]


async def create_ticket(customer_email: str, subject: str, description: str) -> dict:
    ticket = {
        "id": f"TKT-{len(TICKETS) + 1001}",
        "customer_email": customer_email,
        "subject": subject,
        "description": description,
        "status": "open",
    }
    TICKETS.append(ticket)
    return ticket


async def get_tickets(limit: int = 50) -> list[dict]:
    return TICKETS[-limit:]
