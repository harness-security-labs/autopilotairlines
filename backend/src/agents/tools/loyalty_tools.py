from langchain_core.tools import tool


@tool
async def check_loyalty_points_tool(user_id: str) -> str:
    """Check loyalty points balance and tier for a user."""
    from ...database import async_session
    from ...models.loyalty import LoyaltyAccount
    from sqlalchemy import select
    from uuid import UUID

    async with async_session() as db:
        result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
        )
        account = result.scalar_one_or_none()

    if not account:
        return "No loyalty account found for this user."

    return f"Points: {account.points}\nTier: {account.tier}\nUser ID: {user_id}"


@tool
async def modify_loyalty_points_tool(user_id: str, points: int, reason: str) -> str:
    """Add or subtract loyalty points for a user. Positive values add points, negative subtract."""
    from ...database import async_session
    from ...models.loyalty import LoyaltyAccount, LoyaltyTransaction
    from sqlalchemy import select
    from uuid import UUID

    async with async_session() as db:
        result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
        )
        account = result.scalar_one_or_none()
        if not account:
            return "No loyalty account found."

        account.points += points
        txn = LoyaltyTransaction(
            account_id=account.id,
            points=points,
            transaction_type="adjustment",
            source=reason,
        )
        db.add(txn)
        await db.commit()

    return f"Loyalty points updated. New balance: {account.points}. Reason: {reason}"
