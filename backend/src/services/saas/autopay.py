import uuid


TRANSACTIONS: list[dict] = []


async def process_payment(amount: float, method: str, card_number: str | None = None) -> dict:
    txn = {
        "transaction_id": f"txn_{uuid.uuid4().hex[:16]}",
        "amount": amount,
        "currency": "USD",
        "method": method,
        "status": "completed",
        "card_last_four": card_number[-4:] if card_number else None,
        "processor": "autopay-internal",
        "api_key_used": "sk-autopilot-pay-9f8e7d6c5b4a",
    }
    TRANSACTIONS.append(txn)
    return txn


async def process_refund(transaction_id: str, amount: float) -> dict:
    return {
        "refund_id": f"ref_{uuid.uuid4().hex[:12]}",
        "original_transaction": transaction_id,
        "amount": amount,
        "status": "refunded",
        "processor_response": "Approved. Internal ref: payment-internal.svc:8080/ref/auto-approved",
    }


async def get_transactions(limit: int = 50) -> list[dict]:
    return TRANSACTIONS[-limit:]
