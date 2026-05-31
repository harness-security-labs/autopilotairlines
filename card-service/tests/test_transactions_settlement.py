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
async def test_transactions_initial_topup(client: AsyncClient):
    card_id = await create_card(client, 3000.0)

    resp = await client.get(f"/cards/{card_id}/transactions")
    assert resp.status_code == 200
    txns = resp.json()
    assert len(txns) == 1
    assert txns[0]["transaction_type"] == "topup"
    assert txns[0]["status"] == "settled"
    assert txns[0]["amount"] == 3000.0
    assert txns[0]["description"] == "Initial deposit"


@pytest.mark.asyncio
async def test_transactions_all_recorded(client: AsyncClient):
    card_id = await create_card(client, 5000.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 100.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
        "description": "First charge",
    })
    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 200.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
        "description": "Second charge",
    })

    resp = await client.get(f"/cards/{card_id}/transactions")
    txns = resp.json()
    assert len(txns) == 3
    descriptions = [t["description"] for t in txns]
    assert "First charge" in descriptions
    assert "Second charge" in descriptions
    assert "Initial deposit" in descriptions


@pytest.mark.asyncio
async def test_transactions_limit(client: AsyncClient):
    card_id = await create_card(client, 10000.0)

    for i in range(5):
        await client.post(f"/cards/{card_id}/charge", json={
            "amount": 10.0,
            "cvv": CVV,
            "expiry_month": EXPIRY_MONTH,
            "expiry_year": EXPIRY_YEAR,
        })

    resp = await client.get(f"/cards/{card_id}/transactions", params={"limit": 3})
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_transactions_not_found(client: AsyncClient):
    resp = await client.get("/cards/99999999-9999-9999-9999-999999999999/transactions")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_settlement_flow(client: AsyncClient):
    card_id = await create_card(client, 5000.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 100.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 200.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })

    settle_resp = await client.post(f"/cards/{card_id}/settle")
    assert settle_resp.status_code == 200
    data = settle_resp.json()
    assert data["status"] == "completed"
    assert data["transaction_count"] == 3  # initial topup + 2 charges
    assert data["settlement_id"] is not None


@pytest.mark.asyncio
async def test_settlement_empty(client: AsyncClient):
    card_id = await create_card(client, 1000.0)

    # First settle all existing
    await client.post(f"/cards/{card_id}/settle")

    # Second settle should have nothing
    resp = await client.post(f"/cards/{card_id}/settle")
    assert resp.status_code == 200
    assert resp.json()["settlement_id"] is None


@pytest.mark.asyncio
async def test_settlements_list(client: AsyncClient):
    card_id = await create_card(client, 5000.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 50.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    await client.post(f"/cards/{card_id}/settle")

    resp = await client.get(f"/cards/{card_id}/settlements")
    assert resp.status_code == 200
    settlements = resp.json()
    assert len(settlements) == 1
    assert settlements[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_statement(client: AsyncClient):
    card_id = await create_card(client, 2000.0)

    await client.post(f"/cards/{card_id}/charge", json={
        "amount": 300.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
    })
    await client.post(f"/cards/{card_id}/credit", json={
        "amount": 100.0,
        "description": "Partial refund",
    })
    await client.post(f"/cards/{card_id}/topup", json={
        "amount": 500.0,
    })

    resp = await client.get(f"/cards/{card_id}/statement")
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_brand"] == "visa"
    assert data["card_last_four"] == "0366"
    assert data["opening_balance"] == 0.0
    assert data["closing_balance"] == 2300.0
    assert data["total_charges"] == 300.0
    assert data["total_credits"] == 100.0
    assert data["total_topups"] == 2500.0  # initial 2000 + 500
    assert data["transaction_count"] == 4


@pytest.mark.asyncio
async def test_full_lifecycle(client: AsyncClient):
    """End-to-end: create card, charge, refund, topup, verify audit trail."""
    card_id = await create_card(client, 1000.0)

    charge_resp = await client.post(f"/cards/{card_id}/charge", json={
        "amount": 400.0,
        "cvv": CVV,
        "expiry_month": EXPIRY_MONTH,
        "expiry_year": EXPIRY_YEAR,
        "reference_id": "booking_xyz",
        "description": "Flight DEL-BOM",
    })
    assert charge_resp.status_code == 200
    assert charge_resp.json()["balance_after"] == 600.0

    credit_resp = await client.post(f"/cards/{card_id}/credit", json={
        "amount": 400.0,
        "reference_id": "refund_xyz",
        "description": "Cancelled flight",
    })
    assert credit_resp.status_code == 200
    assert credit_resp.json()["balance_after"] == 1000.0

    topup_resp = await client.post(f"/cards/{card_id}/topup", json={
        "amount": 2000.0,
        "description": "Salary credit",
    })
    assert topup_resp.status_code == 200
    assert topup_resp.json()["balance_after"] == 3000.0

    txns_resp = await client.get(f"/cards/{card_id}/transactions")
    txns = txns_resp.json()
    assert len(txns) == 4
    types = [t["transaction_type"] for t in txns]
    assert "topup" in types
    assert "charge" in types
    assert "refund" in types
    assert all(t["status"] == "settled" for t in txns)
