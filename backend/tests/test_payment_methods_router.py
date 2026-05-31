import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import require_auth


MOCK_USER = {"sub": "00000000-0000-0000-0000-000000000001", "email": "test@example.com", "role": "user"}


def override_auth():
    return MOCK_USER


app.dependency_overrides[require_auth] = override_auth


@pytest.fixture
def client():
    return TestClient(app)


def test_list_payment_methods(client):
    cards = [
        {
            "id": "card-1",
            "user_id": MOCK_USER["sub"],
            "label": "Visa ending 0366",
            "card_last_four": "0366",
            "card_brand": "visa",
            "expiry_month": 12,
            "expiry_year": 2027,
            "balance": 10000.0,
            "available_balance": 10000.0,
            "hold_amount": 0.0,
            "currency": "USD",
            "is_default": True,
            "status": "active",
        }
    ]
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.list_cards = AsyncMock(return_value=cards)
        resp = client.get("/api/v1/payment-methods", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["card_brand"] == "visa"
        assert "balance" not in data[0]


def test_add_payment_method(client):
    new_card = {
        "id": "card-new",
        "user_id": MOCK_USER["sub"],
        "label": "Visa ending 1111",
        "card_last_four": "1111",
        "card_brand": "visa",
        "expiry_month": 12,
        "expiry_year": 2027,
        "balance": 5000.0,
        "available_balance": 5000.0,
        "hold_amount": 0.0,
        "currency": "USD",
        "is_default": True,
        "status": "active",
    }
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.create_card = AsyncMock(return_value=new_card)
        resp = client.post("/api/v1/payment-methods", json={
            "card_number": "4111111111111111",
            "cvv": "123",
            "expiry_month": 12,
            "expiry_year": 2027,
        }, headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "card-new"


def test_delete_payment_method(client):
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.delete_card = AsyncMock(return_value=None)
        resp = client.delete("/api/v1/payment-methods/card-1", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


def test_set_default_payment_method(client):
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.set_default = AsyncMock(return_value=None)
        resp = client.patch("/api/v1/payment-methods/card-1/default", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200


def test_topup_payment_method(client):
    topup_result = {
        "transaction_id": "txn-1",
        "auth_code": "AUTH123",
        "status": "settled",
        "amount": 500.0,
        "balance_before": 5000.0,
        "balance_after": 5500.0,
        "available_balance": 5500.0,
    }
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.topup = AsyncMock(return_value=topup_result)
        resp = client.post("/api/v1/payment-methods/card-1/topup", json={"amount": 500.0}, headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["balance_after"] == 5500.0


def test_get_transactions(client):
    txns = [
        {
            "id": "t1",
            "card_id": "card-1",
            "transaction_type": "charge",
            "status": "settled",
            "amount": 100.0,
            "balance_before": 5000.0,
            "balance_after": 4900.0,
            "reference_id": "booking-1",
            "merchant": "AutoPilot Airlines",
            "description": "Flight payment",
            "auth_code": "AUTH111",
            "settled_at": "2026-05-30T10:00:00+00:00",
            "created_at": "2026-05-30T10:00:00+00:00",
        }
    ]
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.get_transactions = AsyncMock(return_value=txns)
        resp = client.get("/api/v1/payment-methods/card-1/transactions", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["transaction_type"] == "charge"
        assert data[0]["auth_code"] == "AUTH111"


def test_get_statement(client):
    statement = {
        "card_id": "card-1",
        "card_brand": "visa",
        "card_last_four": "0366",
        "period_start": "2026-05-01T00:00:00+00:00",
        "period_end": "2026-05-30T00:00:00+00:00",
        "opening_balance": 10000.0,
        "closing_balance": 9500.0,
        "total_charges": 600.0,
        "total_credits": 100.0,
        "total_topups": 0.0,
        "transaction_count": 4,
        "transactions": [],
    }
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.get_statement = AsyncMock(return_value=statement)
        resp = client.get("/api/v1/payment-methods/card-1/statement", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["closing_balance"] == 9500.0


def test_generate_card(client):
    generated = {
        "card_number": "4532015112830366",
        "cvv": "737",
        "expiry_month": 6,
        "expiry_year": 2029,
        "brand": "visa",
    }
    with patch("src.routers.payment_methods.card_service") as mock_svc:
        mock_svc.generate_card = AsyncMock(return_value=generated)
        resp = client.post("/api/v1/payment-methods/generate", json={"brand": "visa"}, headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["brand"] == "visa"
        assert data["card_number"] == "4532015112830366"
        assert data["cvv"] == "737"
