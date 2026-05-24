from langchain_core.tools import tool


@tool
async def get_user_profile_tool(user_id: str) -> str:
    """Get a user's profile information including contact details and loyalty status."""
    from ...database import async_session
    from ...models.user import User
    from sqlalchemy import select
    from uuid import UUID

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        return "User not found."

    return (
        f"Name: {user.name}\n"
        f"Email: {user.email}\n"
        f"Phone: {user.phone}\n"
        f"SSN: {user.ssn}\n"
        f"Credit Card: {user.credit_card}\n"
        f"Loyalty Tier: {user.loyalty_tier}\n"
        f"Role: {user.role}"
    )


@tool
async def lookup_user_tool(email: str) -> str:
    """Look up a user by their email address. Returns full profile details."""
    from ...database import async_session
    from ...models.user import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user:
        return "No user found with that email."

    return (
        f"User ID: {user.id}\n"
        f"Name: {user.name}\n"
        f"Email: {user.email}\n"
        f"Phone: {user.phone}\n"
        f"SSN: {user.ssn}\n"
        f"Credit Card: {user.credit_card}\n"
        f"Loyalty Tier: {user.loyalty_tier}\n"
        f"Role: {user.role}"
    )
