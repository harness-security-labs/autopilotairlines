import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from src.services.card_service import CardServiceClient


@pytest.fixture
def client():
    return CardServiceClient()


def mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


@pytest.mark.asyncio
async def test_list_cards(client):
    cards = [
        {"id": "card-1", "card_brand": "visa", "balance": 5000.0},
        {"id": "card-2", "card_brand": "mastercard", "balance": 2500.0},
    ]
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = cards
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        result = await client.list_cards("user-123")
        assert result == cards
        mock_http.get.assert_called_once()


@pytest.mark.asyncio
async def test_create_card_success(client):
    card_data = {"id": "card-new", "card_brand": "visa", "balance": 5000.0}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = card_data
        resp.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=resp)

        result = await client.create_card("user-1", "4111111111111111", "123", 12, 2027)
        assert result == card_data


@pytest.mark.asyncio
async def test_create_card_invalid(client):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 400
        resp.json.return_value = {"detail": "Invalid card number"}
        mock_http.post = AsyncMock(return_value=resp)

        with pytest.raises(HTTPException) as exc_info:
            await client.create_card("user-1", "bad", "123", 12, 2027)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_charge_success(client):
    charge_result = {
        "transaction_id": "txn-1",
        "auth_code": "AUTH123",
        "status": "settled",
        "amount": 100.0,
        "balance_before": 5000.0,
        "balance_after": 4900.0,
        "available_balance": 4900.0,
    }
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = charge_result
        resp.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=resp)

        result = await client.charge("card-1", 100.0, "737", 12, 2027, "ref-1", "Test charge")
        assert result["status"] == "settled"
        assert result["balance_after"] == 4900.0


@pytest.mark.asyncio
async def test_charge_insufficient_funds(client):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 402
        resp.json.return_value = {"detail": {"message": "Insufficient funds", "available": 50.0, "required": 100.0}}
        mock_http.post = AsyncMock(return_value=resp)

        with pytest.raises(HTTPException) as exc_info:
            await client.charge("card-1", 100.0, "737", 12, 2027)
        assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_charge_cvv_failed(client):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 403
        resp.json.return_value = {"detail": "CVV verification failed"}
        mock_http.post = AsyncMock(return_value=resp)

        with pytest.raises(HTTPException) as exc_info:
            await client.charge("card-1", 100.0, "000", 12, 2027)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_internal_charge_success(client):
    charge_result = {
        "transaction_id": "txn-2",
        "auth_code": "AUTH456",
        "status": "settled",
        "amount": 200.0,
        "balance_before": 5000.0,
        "balance_after": 4800.0,
        "available_balance": 4800.0,
    }
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = charge_result
        resp.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=resp)

        result = await client.internal_charge("card-1", 200.0, "booking-1", "Payment")
        assert result["status"] == "settled"
        assert result["balance_after"] == 4800.0


@pytest.mark.asyncio
async def test_internal_charge_insufficient_funds(client):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 402
        resp.json.return_value = {"detail": {"message": "Insufficient funds", "available": 10.0, "required": 200.0}}
        mock_http.post = AsyncMock(return_value=resp)

        with pytest.raises(HTTPException) as exc_info:
            await client.internal_charge("card-1", 200.0)
        assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_credit_success(client):
    credit_result = {
        "transaction_id": "txn-3",
        "auth_code": "AUTH789",
        "status": "settled",
        "amount": 150.0,
        "balance_before": 4850.0,
        "balance_after": 5000.0,
        "available_balance": 5000.0,
    }
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = credit_result
        resp.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=resp)

        result = await client.credit("card-1", 150.0, "refund-1", "Refund")
        assert result["balance_after"] == 5000.0


@pytest.mark.asyncio
async def test_topup_success(client):
    topup_result = {
        "transaction_id": "txn-4",
        "auth_code": "AUTHABC",
        "status": "settled",
        "amount": 1000.0,
        "balance_before": 5000.0,
        "balance_after": 6000.0,
        "available_balance": 6000.0,
    }
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = topup_result
        resp.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=resp)

        result = await client.topup("card-1", 1000.0)
        assert result["balance_after"] == 6000.0


@pytest.mark.asyncio
async def test_delete_card(client):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "deleted"}
        resp.raise_for_status = MagicMock()
        mock_http.delete = AsyncMock(return_value=resp)

        await client.delete_card("card-1")


@pytest.mark.asyncio
async def test_delete_card_not_found(client):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {"detail": "Payment method not found"}
        mock_http.delete = AsyncMock(return_value=resp)

        with pytest.raises(HTTPException) as exc_info:
            await client.delete_card("bad-id")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_transactions(client):
    txns = [
        {"id": "t1", "transaction_type": "charge", "amount": 100.0, "status": "settled"},
        {"id": "t2", "transaction_type": "topup", "amount": 5000.0, "status": "settled"},
    ]
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = txns
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        result = await client.get_transactions("card-1")
        assert len(result) == 2


@pytest.mark.asyncio
async def test_get_statement(client):
    statement = {
        "card_id": "card-1",
        "total_charges": 300.0,
        "total_credits": 100.0,
        "total_topups": 5000.0,
        "transaction_count": 5,
    }
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = statement
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        result = await client.get_statement("card-1")
        assert result["total_charges"] == 300.0
