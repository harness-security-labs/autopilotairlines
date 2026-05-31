from datetime import date

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generate_visa(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "visa"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"] == "visa"
    assert data["card_number"].startswith("4")
    assert len(data["card_number"]) == 16
    assert len(data["cvv"]) == 3
    assert 1 <= data["expiry_month"] <= 12
    assert data["expiry_year"] > date.today().year


@pytest.mark.asyncio
async def test_generate_mastercard(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "mastercard"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"] == "mastercard"
    assert data["card_number"][0] == "5"
    assert len(data["card_number"]) == 16
    assert len(data["cvv"]) == 3


@pytest.mark.asyncio
async def test_generate_amex(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "amex"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"] == "amex"
    assert data["card_number"].startswith("37")
    assert len(data["card_number"]) == 15
    assert len(data["cvv"]) == 4


@pytest.mark.asyncio
async def test_generate_discover(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "discover"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"] == "discover"
    assert len(data["card_number"]) == 16


@pytest.mark.asyncio
async def test_generate_rupay(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "rupay"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"] == "rupay"
    assert len(data["card_number"]) == 16


@pytest.mark.asyncio
async def test_generate_unsupported_brand(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "diners"})
    assert resp.status_code == 400
    assert "Unsupported brand" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generated_card_passes_luhn(client: AsyncClient):
    for brand in ["visa", "mastercard", "amex", "discover", "rupay"]:
        resp = await client.post("/cards/generate", json={"brand": brand})
        data = resp.json()
        card_number = data["card_number"]

        digits = [int(d) for d in card_number]
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        assert checksum % 10 == 0, f"Luhn check failed for {brand}: {card_number}"


@pytest.mark.asyncio
async def test_generated_card_can_be_registered(client: AsyncClient):
    resp = await client.post("/cards/generate", json={"brand": "visa"})
    generated = resp.json()

    resp = await client.post("/cards", json={
        "user_id": "00000000-0000-0000-0000-000000000099",
        "card_number": generated["card_number"],
        "cvv": generated["cvv"],
        "expiry_month": generated["expiry_month"],
        "expiry_year": generated["expiry_year"],
    })
    assert resp.status_code == 200
    card = resp.json()
    assert card["card_brand"] == "visa"
    assert card["balance"] == 5000.0
