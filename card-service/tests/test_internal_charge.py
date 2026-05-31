import pytest
from httpx import AsyncClient

USER_ID = "00000000-0000-0000-0000-000000000001"
VALID_VISA = "4532015112830366"
CVV = "737"
EXPIRY_MONTH = 12
EXPIRY_YEAR = 2027


async def create_card(client: AsyncClient, balance: float = 5000.0) -> str:
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
        "initial_balance": balance,
    })
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_internal_charge_success(client: AsyncClient):
    card_id = await create_card(client, 2000.0)

    resp = await client.post(f"/cards/{card_id}/internal/charge", json={
        "amount": 500.0,
        "reference_id": "booking_123",
        "description": "Server-side payment",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "settled"
    assert data["balance_before"] == 2000.0
    assert data["balance_after"] == 1500.0
    assert data["auth_code"].startswith("AUTH")


@pytest.mark.asyncio
async def test_internal_charge_no_cvv_required(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    resp = await client.post(f"/cards/{card_id}/internal/charge", json={
        "amount": 100.0,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "settled"


@pytest.mark.asyncio
async def test_internal_charge_insufficient_funds(client: AsyncClient):
    card_id = await create_card(client, 50.0)

    resp = await client.post(f"/cards/{card_id}/internal/charge", json={
        "amount": 200.0,
    })
    assert resp.status_code == 402
    detail = resp.json()["detail"]
    assert detail["available"] == 50.0
    assert detail["required"] == 200.0


@pytest.mark.asyncio
async def test_internal_charge_not_found(client: AsyncClient):
    resp = await client.post("/cards/99999999-9999-9999-9999-999999999999/internal/charge", json={
        "amount": 50.0,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_internal_charge_records_transaction(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    await client.post(f"/cards/{card_id}/internal/charge", json={
        "amount": 150.0,
        "reference_id": "txn_abc",
        "merchant": "AutoPilot Airlines",
        "description": "Reschedule fee",
    })

    txns_resp = await client.get(f"/cards/{card_id}/transactions")
    txns = txns_resp.json()
    charges = [t for t in txns if t["transaction_type"] == "charge" and t["status"] == "settled"]
    assert len(charges) == 1
    assert charges[0]["amount"] == 150.0
    assert charges[0]["reference_id"] == "txn_abc"
    assert charges[0]["merchant"] == "AutoPilot Airlines"
