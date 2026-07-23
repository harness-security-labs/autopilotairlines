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


def make_mock_db(booking=None, loyalty_account=None):
    db = AsyncMock()

    async def mock_execute(stmt):
        result = MagicMock()
        if "loyalty_accounts" in str(stmt) or "LoyaltyAccount" in str(type(stmt)):
            result.scalar_one_or_none.return_value = loyalty_account
        else:
            result.scalar_one_or_none.return_value = booking
        return result

    db.execute = AsyncMock(side_effect=mock_execute)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


class FakePayment:
    def __init__(self, booking_id, amount, method, transaction_id, card_last_four, currency="USD", status="completed"):
        self.id = uuid.uuid4()
        self.booking_id = booking_id
        self.amount = amount
        self.currency = currency
        self.method = method
        self.status = status
        self.transaction_id = transaction_id
        self.card_last_four = card_last_four


def test_payment_with_card_charge(client):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    fake_payment = FakePayment(
        booking_id=uuid.UUID(BOOKING_ID),
        amount=250.0,
        method="credit_card",
        transaction_id="txn_abc123",
        card_last_four="0366",
    )
    mock_db.refresh = AsyncMock(side_effect=lambda p: setattr(p, 'id', fake_payment.id) or
                                setattr(p, 'currency', 'USD') or
                                setattr(p, 'status', 'completed') or
                                setattr(p, 'transaction_id', 'txn_abc123'))

    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    charge_result = {
        "transaction_id": "card-txn-1",
        "auth_code": "AUTH123",
        "status": "settled",
        "amount": 250.0,
        "balance_before": 10000.0,
        "balance_after": 9750.0,
        "available_balance": 9750.0,
    }
    cards_list = [{"id": CARD_ID, "card_last_four": "0366", "card_brand": "visa"}]

    with patch("src.routers.payments.card_service") as mock_svc:
        mock_svc.charge = AsyncMock(return_value=charge_result)
        mock_svc.list_cards = AsyncMock(return_value=cards_list)

        resp = client.post("/api/v1/payments", json={
            "booking_id": BOOKING_ID,
            "amount": 250.0,
            "payment_method_id": CARD_ID,
            "cvv": "737",
            "expiry_month": 12,
            "expiry_year": 2027,
        }, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 250.0
        assert data["method"] == "credit_card"
        assert data["status"] == "completed"

        mock_svc.charge.assert_called_once_with(
            card_id=CARD_ID,
            amount=250.0,
            cvv="737",
            expiry_month=12,
            expiry_year=2027,
            reference_id=BOOKING_ID,
            description=f"Payment for booking {BOOKING_ID}",
        )

    del app.dependency_overrides[get_db]


def test_payment_missing_cvv(client):
    mock_db = AsyncMock()

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    resp = client.post("/api/v1/payments", json={
        "booking_id": BOOKING_ID,
        "amount": 100.0,
        "payment_method_id": CARD_ID,
    }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 400
    assert "CVV" in resp.json()["detail"]

    del app.dependency_overrides[get_db]


def test_payment_insufficient_funds(client):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    with patch("src.routers.payments.card_service") as mock_svc:
        from fastapi import HTTPException
        mock_svc.charge = AsyncMock(
            side_effect=HTTPException(status_code=402, detail={"message": "Insufficient funds", "available": 50.0, "required": 200.0})
        )

        resp = client.post("/api/v1/payments", json={
            "booking_id": BOOKING_ID,
            "amount": 200.0,
            "payment_method_id": CARD_ID,
            "cvv": "737",
            "expiry_month": 12,
            "expiry_year": 2027,
        }, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 402
        detail = resp.json()["detail"]
        assert detail["message"] == "Insufficient funds"
        assert detail["available"] == 50.0

    del app.dependency_overrides[get_db]


def test_payment_points_only(client):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # DOLLARS_PER_POINT = 0.10, so $100 costs exactly 1000 points.
    # Sending more than needed would trigger the capping branch (points_discount > amount),
    # which is tested implicitly but would change the returned points_used value.
    class FakeLoyaltyAccount:
        id = uuid.uuid4()
        user_id = uuid.UUID(MOCK_USER["sub"])
        points = 50000
        tier = "bronze"

    account = FakeLoyaltyAccount()

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = account
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    async def fake_refresh(obj):
        obj.id = obj.id or uuid.uuid4()
        obj.currency = "USD"
        obj.status = "completed"

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    # 1000 points × $0.10/point = $100.00, covering the full amount → method "points"
    resp = client.post("/api/v1/payments", json={
            "booking_id": BOOKING_ID,
            "amount": 100.0,
            "points_used": 1000,
        }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "points"
    assert data["points_used"] == 1000

    del app.dependency_overrides[get_db]


def test_payment_insufficient_points(client):
    mock_db = AsyncMock()

    class FakeLoyaltyAccount:
        id = uuid.uuid4()
        user_id = uuid.UUID(MOCK_USER["sub"])
        points = 100
        tier = "bronze"

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = FakeLoyaltyAccount()
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    resp = client.post("/api/v1/payments", json={
        "booking_id": BOOKING_ID,
        "amount": 100.0,
        "points_used": 50000,
    }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 400
    assert "Insufficient points" in resp.json()["detail"]

    del app.dependency_overrides[get_db]


def test_payment_card_without_payment_method_id(client):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def fake_refresh(obj):
        obj.id = obj.id or uuid.uuid4()
        obj.currency = "USD"
        obj.status = "completed"

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    async def db_override():
        yield mock_db

    app.dependency_overrides[get_db] = db_override

    resp = client.post("/api/v1/payments", json={
        "booking_id": BOOKING_ID,
        "amount": 100.0,
        "card_number": "4111111111111111",
    }, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "credit_card"

    del app.dependency_overrides[get_db]
