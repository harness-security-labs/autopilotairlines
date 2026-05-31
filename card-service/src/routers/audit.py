from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Card, CardTransaction

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    total_cards = (await db.execute(select(func.count(Card.id)))).scalar() or 0
    total_transactions = (await db.execute(select(func.count(CardTransaction.id)))).scalar() or 0
    total_charges = (await db.execute(
        select(func.coalesce(func.sum(CardTransaction.amount), 0))
        .where(CardTransaction.transaction_type == "charge")
        .where(CardTransaction.status == "settled")
    )).scalar() or 0
    total_refunds = (await db.execute(
        select(func.coalesce(func.sum(CardTransaction.amount), 0))
        .where(CardTransaction.transaction_type == "refund")
        .where(CardTransaction.status == "settled")
    )).scalar() or 0

    result = await db.execute(
        select(CardTransaction, Card.card_brand, Card.card_last_four)
        .join(Card, CardTransaction.card_id == Card.id)
        .order_by(CardTransaction.created_at.desc())
        .limit(20)
    )
    recent = []
    for row in result.all():
        txn = row[0]
        txn.card_brand = row[1]
        txn.card_last_four = row[2]
        recent.append(txn)

    return templates.TemplateResponse(request, "dashboard.html", {
        "active": "dashboard",
        "total_cards": total_cards,
        "total_transactions": total_transactions,
        "total_charges": total_charges,
        "total_refunds": total_refunds,
        "recent_transactions": recent,
    })


@router.get("/cards", response_class=HTMLResponse)
async def cards_list(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Card).order_by(Card.user_id, Card.is_default.desc())
    )
    cards = result.scalars().all()

    return templates.TemplateResponse(request, "cards.html", {
        "active": "cards",
        "cards": cards,
    })


@router.get("/cards/{card_id}", response_class=HTMLResponse)
async def card_detail(request: Request, card_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        return HTMLResponse("<h1>Card not found</h1>", status_code=404)

    result = await db.execute(
        select(CardTransaction)
        .where(CardTransaction.card_id == UUID(card_id))
        .order_by(CardTransaction.created_at.desc())
    )
    transactions = result.scalars().all()

    return templates.TemplateResponse(request, "card_detail.html", {
        "active": "cards",
        "card": card,
        "transactions": transactions,
    })


@router.get("/transactions", response_class=HTMLResponse)
async def transactions_list(
    request: Request,
    type: str = "",
    status: str = "",
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(CardTransaction, Card.card_last_four)
        .join(Card, CardTransaction.card_id == Card.id)
    )
    if type:
        query = query.where(CardTransaction.transaction_type == type)
    if status:
        query = query.where(CardTransaction.status == status)

    query = query.order_by(CardTransaction.created_at.desc()).limit(200)
    result = await db.execute(query)

    transactions = []
    for row in result.all():
        txn = row[0]
        txn.card_last_four = row[1]
        transactions.append(txn)

    return templates.TemplateResponse(request, "transactions.html", {
        "active": "transactions",
        "transactions": transactions,
        "filter_type": type,
        "filter_status": status,
    })
