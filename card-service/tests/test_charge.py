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
async def test_charge_success(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 250.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
        "reference_id": "booking_001",
        "description": "Flight payment",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "settled"
    assert data["amount"] == 250.0
    assert data["balance_before"] == 1000.0
    assert data["balance_after"] == 750.0
    assert data["available_balance"] == 750.0
    assert data["auth_code"].startswith("AUTH")
    assert data["transaction_id"]


@pytest.mark.asyncio
async def test_charge_insufficient_funds(client: AsyncClient):
    card_id = await create_card(client, 100.0)

    resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 500.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    assert resp.status_code == 402
    detail = resp.json()["detail"]
    assert detail["message"] == "Insufficient funds"
    assert detail["available"] == 100.0
    assert detail["required"] == 500.0


@pytest.mark.asyncio
async def test_charge_wrong_cvv(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 50.0,
        "cvv": "999",
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    assert resp.status_code == 403
    assert "CVV" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_charge_wrong_expiry(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 50.0,
        "cvv": CVV,
        "expiry_month": 1,
        "expiry_year": 2025,
    })
    assert resp.status_code == 403
    assert "expiry" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_charge_card_not_found(client: AsyncClient):
    resp = await client.post("/cards/99999999-9999-9999-9999-999999999999/charge", json={
        "amount": 50.0,
        "cvv": "123",
        "expiry_month": 1,
        "expiry_year": 2027,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_charge_exact_balance(client: AsyncClient):
    card_id = await create_card(client, 200.0)

    resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 200.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    assert resp.status_code == 200
    assert resp.json()["balance_after"] == 0.0


@pytest.mark.asyncio
async def test_multiple_charges_drain_balance(client: AsyncClient):
    card_id = await create_card(client, 500.0)

    for _ in range(5):
        resp = await client.post(f"/cards/{card_id}/charge", json={
            "amount": 100.0,
            "cvv": CVV,
            "expiry_month": EXPIRY_MONTH,
            "expiry_year": EXPIRY_YEAR,
        })
        assert resp.status_code == 200

    resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 1.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_charge_creates_declined_transaction_on_failure(client: AsyncClient):
    card_id = await create_card(client, 50.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 100.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })

    txns_resp = await client.get(f"/cards/{card_id}/transactions")
    txns = txns_resp.json()
    declined = [t for t in txns if t["status"] == "declined"]
    assert len(declined) == 1
    assert "Insufficient funds" in declined[0]["description"]


@pytest.mark.asyncio
async def test_charge_declined_cvv_creates_transaction(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 50.0,
        "cvv": "000",
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })

    txns_resp = await client.get(f"/cards/{card_id}/transactions")
    txns = txns_resp.json()
    declined = [t for t in txns if t["status"] == "declined"]
    assert len(declined) == 1
    assert "CVV mismatch" in declined[0]["description"]
