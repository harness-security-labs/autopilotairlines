import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import require_auth
from src.database import get_db

MOCK_USER = {"sub": "00000000-0000-0000-0000-000000000001", "email": "test@example.com", "role": "user"}
BOOKING_ID = "11111111-1111-1111-1111-111111111111"
CARD_ID = "60000000-0000-0000-0000-000000000001"


def override_auth():
    return MOCK_USER


app.dependency_overrides[require_auth] = override_auth


@pytest.fixture
def client():
    return TestClient(app)


class FakeBooking:
    def __init__(self, booking_id, status="confirmed", pnr="ABC123"):
        self.id = uuid.UUID(booking_id)
        self.status = status
        self.pnr = pnr


class FakePayment:
    def __init__(self, booking_id, amount=250.0, card_last_four="0366"):
        self.id = uuid.uuid4()
        self.booking_id = uuid.UUID(booking_id)
        self.amount = amount
        self.card_last_four = card_last_four
        self.method = "credit_card"
        self.transaction_id = "txn_original"


def test_refund_with_card_credit(client):
    booking = FakeBooking(BOOKING_ID)
    payment = FakePayment(BOOKING_ID, amount=300.0, card_last_four="0366")

    mock_db = AsyncMock()
    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none.return_value = booking
        else:
            result.scalar_one_or_none.return_value = payment
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    cards_list = [
        {"id": CARD_ID, "card_last_four": "0366", "card_brand": "visa", "balance": 9700.0},
    ]
    credit_result = {
        "transaction_id": "credit-txn-1",
        "auth_code": "AUTHREFUND",
        "status": "settled",
        "amount": 300.0,
        "balance_before": 9700.0,
        "balance_after": 10000.0,
        "available_balance": 10000.0,
    }

    with patch("src.routers.refunds.card_service") as mock_svc:
        mock_svc.list_cards = AsyncMock(return_value=cards_list)
        mock_svc.credit = AsyncMock(return_value=credit_result)

        resp = client.post("/api/v1/refunds", json={
            "booking_id": BOOKING_ID,
            "reason": "Customer cancelled flight",
        }, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["refund_amount"] == 300.0

        mock_svc.credit.assert_called_once_with(
            card_id=CARD_ID,
            amount=300.0,
            reference_id=BOOKING_ID,
            description="Refund for booking ABC123",
        )

    assert booking.status == "refunded"
    del app.dependency_overrides[get_db]


def test_refund_booking_not_found(client):
    mock_db = AsyncMock()

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    resp = client.post("/api/v1/refunds", json={
        "booking_id": BOOKING_ID,
        "reason": "Test",
    }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 404
    assert "Booking not found" in resp.json()["detail"]

    del app.dependency_overrides[get_db]


def test_refund_no_payment_record(client):
    booking = FakeBooking(BOOKING_ID)
    mock_db = AsyncMock()
    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none.return_value = booking
        else:
            result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    resp = client.post("/api/v1/refunds", json={
        "booking_id": BOOKING_ID,
        "reason": "No payment to refund",
    }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["refund_amount"] is None
    assert "card_balance_after" not in data
    assert booking.status == "refunded"

    del app.dependency_overrides[get_db]


def test_refund_points_only_payment(client):
    booking = FakeBooking(BOOKING_ID)
    payment = FakePayment(BOOKING_ID, amount=100.0, card_last_four=None)

    mock_db = AsyncMock()
    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none.return_value = booking
        else:
            result.scalar_one_or_none.return_value = payment
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    resp = client.post("/api/v1/refunds", json={
        "booking_id": BOOKING_ID,
        "reason": "Points payment, no card to credit",
    }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["refund_amount"] is None
    assert "card_balance_after" not in data
    assert booking.status == "refunded"

    del app.dependency_overrides[get_db]


def test_refund_card_not_found_in_user_cards(client):
    booking = FakeBooking(BOOKING_ID)
    payment = FakePayment(BOOKING_ID, amount=200.0, card_last_four="9999")

    mock_db = AsyncMock()
    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none.return_value = booking
        else:
            result.scalar_one_or_none.return_value = payment
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    cards_list = [
        {"id": CARD_ID, "card_last_four": "0366", "card_brand": "visa"},
    ]

    with patch("src.routers.refunds.card_service") as mock_svc:
        mock_svc.list_cards = AsyncMock(return_value=cards_list)

        resp = client.post("/api/v1/refunds", json={
            "booking_id": BOOKING_ID,
            "reason": "Card was deleted",
        }, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["refund_amount"] is None
        assert "card_balance_after" not in data
        mock_svc.credit.assert_not_called()

    assert booking.status == "refunded"
    del app.dependency_overrides[get_db]
