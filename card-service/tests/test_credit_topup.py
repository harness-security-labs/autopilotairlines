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
async def test_credit_success(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    resp = await client.post(f"/cards/{card_id}/credit", json={
        "amount": 200.0,
        "reference_id": "refund_001",
        "description": "Refund for cancelled booking",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "settled"
    assert data["amount"] == 200.0
    assert data["balance_before"] == 1000.0
    assert data["balance_after"] == 1200.0
    assert data["auth_code"].startswith("AUTH")


@pytest.mark.asyncio
async def test_credit_card_not_found(client: AsyncClient):
    resp = await client.post("/cards/99999999-9999-9999-9999-999999999999/credit", json={
        "amount": 100.0,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_topup_success(client: AsyncClient):
    card_id = await create_card(client, 500.0)

    resp = await client.post(f"/cards/{card_id}/topup", json={
        "amount": 2000.0,
        "description": "Monthly deposit",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "settled"
    assert data["balance_before"] == 500.0
    assert data["balance_after"] == 2500.0


@pytest.mark.asyncio
async def test_topup_zero_amount(client: AsyncClient):
    card_id = await create_card(client, 500.0)

    resp = await client.post(f"/cards/{card_id}/topup", json={"amount": 0})
    assert resp.status_code == 400
    assert "positive" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_topup_negative_amount(client: AsyncClient):
    card_id = await create_card(client, 500.0)

    resp = await client.post(f"/cards/{card_id}/topup", json={"amount": -100.0})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_topup_card_not_found(client: AsyncClient):
    resp = await client.post("/cards/99999999-9999-9999-9999-999999999999/topup", json={
        "amount": 100.0,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_charge_then_refund_restores_balance(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 300.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
        "reference_id": "booking_abc",
    })

    balance_resp = await client.get(f"/cards/{card_id}/balance")
    assert balance_resp.json()["balance"] == 700.0

    await client.post(f"/cards/{card_id}/credit", json={
        "amount": 300.0,
        "reference_id": "refund_abc",
        "description": "Full refund",
    })

    balance_resp = await client.get(f"/cards/{card_id}/balance")
    assert balance_resp.json()["balance"] == 1000.0


@pytest.mark.asyncio
async def test_topup_after_drain(client: AsyncClient):
    card_id = await create_card(client, 100.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 100.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })

    balance_resp = await client.get(f"/cards/{card_id}/balance")
    assert balance_resp.json()["balance"] == 0.0

    await client.post(f"/cards/{card_id}/topup", json={"amount": 5000.0})

    balance_resp = await client.get(f"/cards/{card_id}/balance")
    assert balance_resp.json()["balance"] == 5000.0
