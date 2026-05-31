import pytest
from httpx import AsyncClient

USER_ID = "00000000-0000-0000-0000-000000000001"
VALID_VISA = "4532015112830366"
VALID_MASTERCARD = "5500000000000004"
VALID_AMEX = "378282246310005"
VALID_RUPAY = "6062826786276634"


@pytest.mark.asyncio
async def test_create_card_visa(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "737",
        "expiry_month": 12,
        "expiry_year": 2027,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_brand"] == "visa"
    assert data["card_last_four"] == "0366"
    assert data["balance"] == 5000.0
    assert data["available_balance"] == 5000.0
    assert data["status"] == "active"
    assert data["is_default"] is True


@pytest.mark.asyncio
async def test_create_card_mastercard(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_MASTERCARD,
        "cvv": "412",
        "expiry_month": 6,
        "expiry_year": 2026,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_brand"] == "mastercard"
    assert data["card_last_four"] == "0004"


@pytest.mark.asyncio
async def test_create_card_amex(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_AMEX,
        "cvv": "5891",
        "expiry_month": 3,
        "expiry_year": 2028,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_brand"] == "amex"
    assert data["card_last_four"] == "0005"


@pytest.mark.asyncio
async def test_create_card_rupay(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_RUPAY,
        "cvv": "556",
        "expiry_month": 11,
        "expiry_year": 2026,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_brand"] == "rupay"
    assert data["card_last_four"] == "6634"


@pytest.mark.asyncio
async def test_create_card_custom_balance(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "123",
        "expiry_month": 1,
        "expiry_year": 2028,
        "initial_balance": 10000.0,
    })
    assert resp.status_code == 200
    assert resp.json()["balance"] == 10000.0


@pytest.mark.asyncio
async def test_create_card_invalid_luhn(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": "4111111111111112",
        "cvv": "123",
        "expiry_month": 12,
        "expiry_year": 2027,
    })
    assert resp.status_code == 400
    assert "Invalid card number" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_card_invalid_cvv(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "12",
        "expiry_month": 12,
        "expiry_year": 2027,
    })
    assert resp.status_code == 400
    assert "Invalid CVV" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_card_invalid_expiry_month(client: AsyncClient):
    resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "123",
        "expiry_month": 13,
        "expiry_year": 2027,
    })
    assert resp.status_code == 400
    assert "Invalid expiry month" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_cards_empty(client: AsyncClient):
    resp = await client.get("/cards", params={"user_id": USER_ID})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_cards_after_create(client: AsyncClient):
    r1 = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "737",
        "expiry_month": 12,
        "expiry_year": 2027,
    })
    assert r1.status_code == 200
    r2 = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_MASTERCARD,
        "cvv": "412",
        "expiry_month": 6,
        "expiry_year": 2026,
    })
    assert r2.status_code == 200
    resp = await client.get("/cards", params={"user_id": USER_ID})
    assert resp.status_code == 200
    cards = resp.json()
    assert len(cards) == 2
    assert cards[0]["is_default"] is True


@pytest.mark.asyncio
async def test_delete_card(client: AsyncClient):
    create_resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "737",
        "expiry_month": 12,
        "expiry_year": 2027,
    })
    card_id = create_resp.json()["id"]

    resp = await client.delete(f"/cards/{card_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    list_resp = await client.get("/cards", params={"user_id": USER_ID})
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_delete_card_not_found(client: AsyncClient):
    resp = await client.delete("/cards/99999999-9999-9999-9999-999999999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_default(client: AsyncClient):
    r1 = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "737",
        "expiry_month": 12,
        "expiry_year": 2027,
    })
    assert r1.status_code == 200
    r2 = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_MASTERCARD,
        "cvv": "412",
        "expiry_month": 6,
        "expiry_year": 2026,
    })
    assert r2.status_code == 200
    card2_id = r2.json()["id"]

    resp = await client.patch(f"/cards/{card2_id}/default")
    assert resp.status_code == 200

    cards = (await client.get("/cards", params={"user_id": USER_ID})).json()
    defaults = [c for c in cards if c["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == card2_id


@pytest.mark.asyncio
async def test_get_balance(client: AsyncClient):
    create_resp = await client.post("/cards", json={
        "user_id": USER_ID,
        "card_number": VALID_VISA,
        "cvv": "737",
        "expiry_month": 12,
        "expiry_year": 2027,
        "initial_balance": 7500.0,
    })
    card_id = create_resp.json()["id"]

    resp = await client.get(f"/cards/{card_id}/balance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance"] == 7500.0
    assert data["available_balance"] == 7500.0
    assert data["hold_amount"] == 0.0
