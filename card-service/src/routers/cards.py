import random
import uuid as uuid_mod
from datetime import datetime, date, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Card, CardTransaction, Settlement

router = APIRouter(prefix="/cards", tags=["cards"])


def detect_brand(card_number: str) -> str:
    num = card_number.replace(" ", "").replace("-", "")
    if num.startswith("37"):
        return "amex"
    if num[:2] in ("60", "65", "81", "82"):
        return "rupay"
    if num.startswith("4"):
        return "visa"
    if num.startswith("5"):
        return "mastercard"
    if num.startswith("6"):
        return "discover"
    return "prepaid"


def luhn_check(card_number: str) -> bool:
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    reverse = digits[::-1]
    for i, d in enumerate(reverse):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def generate_auth_code() -> str:
    return f"AUTH{uuid_mod.uuid4().hex[:8].upper()}"


BRAND_PREFIXES = {
    "visa": ["4"],
    "mastercard": ["51", "52", "53", "54", "55"],
    "amex": ["37"],
    "discover": ["6011", "644", "645", "646", "647", "648", "649", "65"],
    "rupay": ["60", "65", "81", "82"],
}

BRAND_LENGTHS = {
    "visa": 16,
    "mastercard": 16,
    "amex": 15,
    "discover": 16,
    "rupay": 16,
}


def _generate_card_number(brand: str) -> str:
    prefixes = BRAND_PREFIXES.get(brand, ["4"])
    prefix = random.choice(prefixes)
    length = BRAND_LENGTHS.get(brand, 16)

    body = prefix + "".join([str(random.randint(0, 9)) for _ in range(length - len(prefix) - 1)])

    digits = [int(d) for d in body]
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    check_digit = (10 - (checksum % 10)) % 10
    return body + str(check_digit)


# --- Request/Response Models ---

class CardResponse(BaseModel):
    id: str
    user_id: str
    label: str
    card_last_four: str
    card_brand: str
    expiry_month: int
    expiry_year: int
    balance: float
    available_balance: float
    hold_amount: float
    currency: str
    is_default: bool
    status: str


class CardCreate(BaseModel):
    user_id: str
    card_number: str
    cvv: str
    expiry_month: int
    expiry_year: int
    initial_balance: float = 5000.0


class ChargeRequest(BaseModel):
    amount: float
    cvv: str
    expiry_month: int
    expiry_year: int
    reference_id: str | None = None
    merchant: str = "AutoPilot Airlines"
    description: str | None = None


class CreditRequest(BaseModel):
    amount: float
    reference_id: str | None = None
    merchant: str = "AutoPilot Airlines"
    description: str | None = None


class GenerateCardRequest(BaseModel):
    brand: str = "visa"


class GenerateCardResponse(BaseModel):
    card_number: str
    cvv: str
    expiry_month: int
    expiry_year: int
    brand: str


class TopupRequest(BaseModel):
    amount: float
    description: str | None = None


class TransactionResponse(BaseModel):
    id: str
    card_id: str
    transaction_type: str
    status: str
    amount: float
    balance_before: float
    balance_after: float
    reference_id: str | None
    merchant: str
    description: str | None
    auth_code: str | None
    settled_at: str | None
    created_at: str


class ChargeResponse(BaseModel):
    transaction_id: str
    auth_code: str
    status: str
    amount: float
    balance_before: float
    balance_after: float
    available_balance: float


class SettlementResponse(BaseModel):
    id: str
    card_id: str
    total_amount: float
    transaction_count: int
    status: str
    settlement_date: str
    created_at: str


class StatementResponse(BaseModel):
    card_id: str
    card_brand: str
    card_last_four: str
    period_start: str
    period_end: str
    opening_balance: float
    closing_balance: float
    total_charges: float
    total_credits: float
    total_topups: float
    transaction_count: int
    transactions: list[TransactionResponse]


# --- Helpers ---

def _card_response(card: Card) -> CardResponse:
    return CardResponse(
        id=str(card.id),
        user_id=str(card.user_id),
        label=card.label,
        card_last_four=card.card_last_four,
        card_brand=card.card_brand,
        expiry_month=card.expiry_month,
        expiry_year=card.expiry_year,
        balance=card.balance,
        available_balance=card.balance - card.hold_amount,
        hold_amount=card.hold_amount,
        currency=card.currency,
        is_default=card.is_default,
        status=card.status,
    )


def _txn_response(t: CardTransaction) -> TransactionResponse:
    return TransactionResponse(
        id=str(t.id),
        card_id=str(t.card_id),
        transaction_type=t.transaction_type,
        status=t.status,
        amount=t.amount,
        balance_before=t.balance_before,
        balance_after=t.balance_after,
        reference_id=t.reference_id,
        merchant=t.merchant,
        description=t.description,
        auth_code=t.auth_code,
        settled_at=t.settled_at.isoformat() if t.settled_at else None,
        created_at=t.created_at.isoformat(),
    )


# --- Endpoints ---

@router.post("/generate", response_model=GenerateCardResponse)
async def generate_card(body: GenerateCardRequest):
    brand = body.brand.lower().strip()
    supported = list(BRAND_PREFIXES.keys())
    if brand not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported brand. Supported: {', '.join(supported)}",
        )

    card_number = _generate_card_number(brand)
    cvv_length = 4 if brand == "amex" else 3
    cvv = "".join([str(random.randint(0, 9)) for _ in range(cvv_length)])

    today = date.today()
    expiry_year = random.randint(today.year + 1, today.year + 6)
    expiry_month = random.randint(1, 12)

    return GenerateCardResponse(
        card_number=card_number,
        cvv=cvv,
        expiry_month=expiry_month,
        expiry_year=expiry_year,
        brand=brand,
    )


@router.get("", response_model=list[CardResponse])
async def list_cards(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Card)
        .where(Card.user_id == UUID(user_id))
        .order_by(Card.is_default.desc(), Card.created_at.desc())
    )
    return [_card_response(c) for c in result.scalars().all()]


@router.post("", response_model=CardResponse)
async def create_card(body: CardCreate, db: AsyncSession = Depends(get_db)):
    card_number = body.card_number.replace(" ", "").replace("-", "")

    if not luhn_check(card_number):
        raise HTTPException(status_code=400, detail="Invalid card number")

    if len(body.cvv) < 3 or len(body.cvv) > 4:
        raise HTTPException(status_code=400, detail="Invalid CVV")

    if body.expiry_month < 1 or body.expiry_month > 12:
        raise HTTPException(status_code=400, detail="Invalid expiry month")

    brand = detect_brand(card_number)
    last_four = card_number[-4:]
    label = f"{brand.capitalize()} ending {last_four}"

    existing = await db.execute(
        select(Card).where(Card.user_id == UUID(body.user_id))
    )
    is_first = not existing.scalars().first()

    card = Card(
        user_id=UUID(body.user_id),
        label=label,
        card_number=card_number,
        card_last_four=last_four,
        card_brand=brand,
        cvv=body.cvv,
        expiry_month=body.expiry_month,
        expiry_year=body.expiry_year,
        balance=body.initial_balance,
        is_default=is_first,
    )
    db.add(card)
    await db.flush()

    txn = CardTransaction(
        card_id=card.id,
        transaction_type="topup",
        status="settled",
        amount=body.initial_balance,
        balance_before=0.0,
        balance_after=body.initial_balance,
        merchant="Bank Transfer",
        description="Initial deposit",
        auth_code=generate_auth_code(),
        settled_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.commit()
    await db.refresh(card)

    return _card_response(card)


@router.delete("/{card_id}")
async def delete_card(card_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    await db.delete(card)
    await db.commit()
    return {"status": "deleted"}


@router.patch("/{card_id}/default")
async def set_default(card_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    all_cards = await db.execute(
        select(Card).where(Card.user_id == card.user_id)
    )
    for c in all_cards.scalars().all():
        c.is_default = (str(c.id) == card_id)
    await db.commit()
    return {"status": "default_updated"}


@router.get("/{card_id}/balance")
async def get_balance(card_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return {
        "card_id": str(card.id),
        "balance": card.balance,
        "available_balance": card.balance - card.hold_amount,
        "hold_amount": card.hold_amount,
        "currency": card.currency,
        "status": card.status,
    }


@router.post("/{card_id}/charge", response_model=ChargeResponse)
async def charge_card(card_id: str, body: ChargeRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.status != "active":
        txn = CardTransaction(
            card_id=card.id,
            transaction_type="charge",
            status="declined",
            amount=body.amount,
            balance_before=card.balance,
            balance_after=card.balance,
            reference_id=body.reference_id,
            merchant=body.merchant,
            description=f"DECLINED: Card inactive - {body.description or ''}",
            auth_code=generate_auth_code(),
        )
        db.add(txn)
        await db.commit()
        raise HTTPException(status_code=403, detail="Card is not active")

    if body.cvv != card.cvv:
        txn = CardTransaction(
            card_id=card.id,
            transaction_type="charge",
            status="declined",
            amount=body.amount,
            balance_before=card.balance,
            balance_after=card.balance,
            reference_id=body.reference_id,
            merchant=body.merchant,
            description=f"DECLINED: CVV mismatch - {body.description or ''}",
            auth_code=generate_auth_code(),
        )
        db.add(txn)
        await db.commit()
        raise HTTPException(status_code=403, detail="CVV verification failed")

    if body.expiry_month != card.expiry_month or body.expiry_year != card.expiry_year:
        txn = CardTransaction(
            card_id=card.id,
            transaction_type="charge",
            status="declined",
            amount=body.amount,
            balance_before=card.balance,
            balance_after=card.balance,
            reference_id=body.reference_id,
            merchant=body.merchant,
            description=f"DECLINED: Expiry mismatch - {body.description or ''}",
            auth_code=generate_auth_code(),
        )
        db.add(txn)
        await db.commit()
        raise HTTPException(status_code=403, detail="Card expiry verification failed")

    available = card.balance - card.hold_amount
    if available < body.amount:
        txn = CardTransaction(
            card_id=card.id,
            transaction_type="charge",
            status="declined",
            amount=body.amount,
            balance_before=card.balance,
            balance_after=card.balance,
            reference_id=body.reference_id,
            merchant=body.merchant,
            description=f"DECLINED: Insufficient funds - {body.description or ''}",
            auth_code=generate_auth_code(),
        )
        db.add(txn)
        await db.commit()
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Insufficient funds",
                "available": available,
                "required": body.amount,
            },
        )

    balance_before = card.balance
    card.balance -= body.amount
    balance_after = card.balance
    auth_code = generate_auth_code()
    now = datetime.now(timezone.utc)

    txn = CardTransaction(
        card_id=card.id,
        transaction_type="charge",
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reference_id=body.reference_id,
        merchant=body.merchant,
        description=body.description,
        auth_code=auth_code,
        settled_at=now,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    return ChargeResponse(
        transaction_id=str(txn.id),
        auth_code=auth_code,
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        available_balance=balance_after - card.hold_amount,
    )


@router.post("/{card_id}/credit", response_model=ChargeResponse)
async def credit_card(card_id: str, body: CreditRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    balance_before = card.balance
    card.balance += body.amount
    balance_after = card.balance
    auth_code = generate_auth_code()
    now = datetime.now(timezone.utc)

    txn = CardTransaction(
        card_id=card.id,
        transaction_type="refund",
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reference_id=body.reference_id,
        merchant=body.merchant,
        description=body.description,
        auth_code=auth_code,
        settled_at=now,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    return ChargeResponse(
        transaction_id=str(txn.id),
        auth_code=auth_code,
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        available_balance=balance_after - card.hold_amount,
    )


class InternalChargeRequest(BaseModel):
    amount: float
    reference_id: str | None = None
    merchant: str = "AutoPilot Airlines"
    description: str | None = None


@router.post("/{card_id}/internal/charge", response_model=ChargeResponse)
async def internal_charge_card(card_id: str, body: InternalChargeRequest, db: AsyncSession = Depends(get_db)):
    """Server-to-server charge using stored card credentials. No CVV/expiry required."""
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.status != "active":
        txn = CardTransaction(
            card_id=card.id,
            transaction_type="charge",
            status="declined",
            amount=body.amount,
            balance_before=card.balance,
            balance_after=card.balance,
            reference_id=body.reference_id,
            merchant=body.merchant,
            description=f"DECLINED: Card inactive - {body.description or ''}",
            auth_code=generate_auth_code(),
        )
        db.add(txn)
        await db.commit()
        raise HTTPException(status_code=403, detail="Card is not active")

    available = card.balance - card.hold_amount
    if available < body.amount:
        txn = CardTransaction(
            card_id=card.id,
            transaction_type="charge",
            status="declined",
            amount=body.amount,
            balance_before=card.balance,
            balance_after=card.balance,
            reference_id=body.reference_id,
            merchant=body.merchant,
            description=f"DECLINED: Insufficient funds - {body.description or ''}",
            auth_code=generate_auth_code(),
        )
        db.add(txn)
        await db.commit()
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Insufficient funds",
                "available": available,
                "required": body.amount,
            },
        )

    balance_before = card.balance
    card.balance -= body.amount
    balance_after = card.balance
    auth_code = generate_auth_code()
    now = datetime.now(timezone.utc)

    txn = CardTransaction(
        card_id=card.id,
        transaction_type="charge",
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reference_id=body.reference_id,
        merchant=body.merchant,
        description=body.description,
        auth_code=auth_code,
        settled_at=now,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    return ChargeResponse(
        transaction_id=str(txn.id),
        auth_code=auth_code,
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        available_balance=balance_after - card.hold_amount,
    )


@router.post("/{card_id}/topup", response_model=ChargeResponse)
async def topup_card(card_id: str, body: TopupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    balance_before = card.balance
    card.balance += body.amount
    balance_after = card.balance
    auth_code = generate_auth_code()
    now = datetime.now(timezone.utc)

    txn = CardTransaction(
        card_id=card.id,
        transaction_type="topup",
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        merchant="Bank Transfer",
        description=body.description or "Top-up",
        auth_code=auth_code,
        settled_at=now,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    return ChargeResponse(
        transaction_id=str(txn.id),
        auth_code=auth_code,
        status="settled",
        amount=body.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        available_balance=balance_after - card.hold_amount,
    )


@router.get("/{card_id}/transactions", response_model=list[TransactionResponse])
async def get_transactions(card_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Card not found")

    result = await db.execute(
        select(CardTransaction)
        .where(CardTransaction.card_id == UUID(card_id))
        .order_by(CardTransaction.created_at.desc())
        .limit(limit)
    )
    return [_txn_response(t) for t in result.scalars().all()]


@router.get("/{card_id}/settlements", response_model=list[SettlementResponse])
async def get_settlements(card_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Card not found")

    result = await db.execute(
        select(Settlement)
        .where(Settlement.card_id == UUID(card_id))
        .order_by(Settlement.settlement_date.desc())
    )
    return [
        SettlementResponse(
            id=str(s.id),
            card_id=str(s.card_id),
            total_amount=s.total_amount,
            transaction_count=s.transaction_count,
            status=s.status,
            settlement_date=s.settlement_date.isoformat(),
            created_at=s.created_at.isoformat(),
        )
        for s in result.scalars().all()
    ]


@router.post("/{card_id}/settle")
async def settle_transactions(card_id: str, db: AsyncSession = Depends(get_db)):
    """Settle all unsettled transactions for this card (batch settlement)."""
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    result = await db.execute(
        select(CardTransaction)
        .where(CardTransaction.card_id == UUID(card_id))
        .where(CardTransaction.settlement_id.is_(None))
        .where(CardTransaction.status == "settled")
    )
    txns = result.scalars().all()

    if not txns:
        return {"message": "No transactions to settle", "settlement_id": None}

    total = sum(t.amount if t.transaction_type == "charge" else -t.amount for t in txns)
    now = datetime.now(timezone.utc)

    settlement = Settlement(
        card_id=card.id,
        total_amount=abs(total),
        transaction_count=len(txns),
        status="completed",
        settlement_date=date.today(),
    )
    db.add(settlement)
    await db.flush()

    for t in txns:
        t.settlement_id = settlement.id
        t.settled_at = now

    await db.commit()
    await db.refresh(settlement)

    return {
        "settlement_id": str(settlement.id),
        "total_amount": settlement.total_amount,
        "transaction_count": settlement.transaction_count,
        "settlement_date": settlement.settlement_date.isoformat(),
        "status": "completed",
    }


@router.get("/{card_id}/statement", response_model=StatementResponse)
async def get_statement(card_id: str, db: AsyncSession = Depends(get_db)):
    """Get a card statement with all settled transactions."""
    result = await db.execute(select(Card).where(Card.id == UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    result = await db.execute(
        select(CardTransaction)
        .where(CardTransaction.card_id == UUID(card_id))
        .where(CardTransaction.status == "settled")
        .order_by(CardTransaction.created_at.asc())
    )
    txns = result.scalars().all()

    total_charges = sum(t.amount for t in txns if t.transaction_type == "charge")
    total_credits = sum(t.amount for t in txns if t.transaction_type == "refund")
    total_topups = sum(t.amount for t in txns if t.transaction_type == "topup")

    opening_balance = txns[0].balance_before if txns else card.balance
    closing_balance = card.balance

    period_start = txns[0].created_at.isoformat() if txns else datetime.now(timezone.utc).isoformat()
    period_end = txns[-1].created_at.isoformat() if txns else datetime.now(timezone.utc).isoformat()

    return StatementResponse(
        card_id=str(card.id),
        card_brand=card.card_brand,
        card_last_four=card.card_last_four,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_charges=total_charges,
        total_credits=total_credits,
        total_topups=total_topups,
        transaction_count=len(txns),
        transactions=[_txn_response(t) for t in txns],
    )
