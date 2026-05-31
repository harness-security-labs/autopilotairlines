from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..middleware.auth import require_auth
from ..services.card_service import card_service

router = APIRouter(prefix="/api/v1/payment-methods", tags=["payment-methods"])


class PaymentMethodCreate(BaseModel):
    card_number: str
    cvv: str
    expiry_month: int
    expiry_year: int


class TopupRequest(BaseModel):
    amount: float


class PaymentMethodResponse(BaseModel):
    id: str
    label: str
    card_last_four: str
    card_brand: str
    expiry_month: int
    expiry_year: int
    currency: str
    is_default: bool
    status: str


class CardTransactionResponse(BaseModel):
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


class GenerateCardRequest(BaseModel):
    brand: str = "visa"


@router.post("/generate")
async def generate_card(body: GenerateCardRequest, current_user: dict = Depends(require_auth)):
    return await card_service.generate_card(body.brand)


@router.get("", response_model=list[PaymentMethodResponse])
async def list_payment_methods(current_user: dict = Depends(require_auth)):
    cards = await card_service.list_cards(current_user["sub"])
    return cards


@router.post("", response_model=PaymentMethodResponse)
async def add_payment_method(body: PaymentMethodCreate, current_user: dict = Depends(require_auth)):
    result = await card_service.create_card(
        user_id=current_user["sub"],
        card_number=body.card_number,
        cvv=body.cvv,
        expiry_month=body.expiry_month,
        expiry_year=body.expiry_year,
    )
    return result


@router.delete("/{method_id}")
async def delete_payment_method(method_id: str, current_user: dict = Depends(require_auth)):
    await card_service.delete_card(method_id)
    return {"status": "deleted"}


@router.patch("/{method_id}/default")
async def set_default_payment_method(method_id: str, current_user: dict = Depends(require_auth)):
    await card_service.set_default(method_id)
    return {"status": "default_updated"}


@router.post("/{method_id}/topup")
async def topup_payment_method(method_id: str, body: TopupRequest, current_user: dict = Depends(require_auth)):
    result = await card_service.topup(method_id, body.amount)
    return result


@router.get("/{method_id}/transactions", response_model=list[CardTransactionResponse])
async def get_payment_method_transactions(method_id: str, current_user: dict = Depends(require_auth)):
    return await card_service.get_transactions(method_id)


@router.get("/{method_id}/statement")
async def get_payment_method_statement(method_id: str, current_user: dict = Depends(require_auth)):
    return await card_service.get_statement(method_id)
