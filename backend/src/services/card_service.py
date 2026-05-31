import httpx
from fastapi import HTTPException

from ..config import settings

BASE_URL = settings.card_service_url


def _handle_connect_error(e: httpx.ConnectError):
    raise HTTPException(status_code=503, detail="Card service unavailable")


class CardServiceClient:
    @staticmethod
    async def list_cards(user_id: str) -> list[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/cards", params={"user_id": user_id})
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def create_card(user_id: str, card_number: str, cvv: str, expiry_month: int, expiry_year: int, initial_balance: float = 5000.0) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/cards", json={
                    "user_id": user_id,
                    "card_number": card_number,
                    "cvv": cvv,
                    "expiry_month": expiry_month,
                    "expiry_year": expiry_year,
                    "initial_balance": initial_balance,
                })
                if resp.status_code == 400:
                    raise HTTPException(status_code=400, detail=resp.json().get("detail", "Invalid card"))
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def delete_card(card_id: str) -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.delete(f"{BASE_URL}/cards/{card_id}")
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def set_default(card_id: str) -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.patch(f"{BASE_URL}/cards/{card_id}/default")
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def get_balance(card_id: str) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/cards/{card_id}/balance")
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def internal_charge(card_id: str, amount: float, reference_id: str | None = None, merchant: str = "AutoPilot Airlines", description: str | None = None) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/cards/{card_id}/internal/charge", json={
                    "amount": amount,
                    "reference_id": reference_id,
                    "merchant": merchant,
                    "description": description,
                })
                if resp.status_code == 402:
                    detail = resp.json().get("detail", {})
                    raise HTTPException(status_code=402, detail=detail)
                if resp.status_code == 403:
                    raise HTTPException(status_code=403, detail=resp.json().get("detail", "Card not active"))
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def charge(card_id: str, amount: float, cvv: str, expiry_month: int, expiry_year: int, reference_id: str | None = None, merchant: str = "AutoPilot Airlines", description: str | None = None) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/cards/{card_id}/charge", json={
                    "amount": amount,
                    "cvv": cvv,
                    "expiry_month": expiry_month,
                    "expiry_year": expiry_year,
                    "reference_id": reference_id,
                    "merchant": merchant,
                    "description": description,
                })
                if resp.status_code == 402:
                    detail = resp.json().get("detail", {})
                    raise HTTPException(status_code=402, detail=detail)
                if resp.status_code == 403:
                    raise HTTPException(status_code=403, detail=resp.json().get("detail", "Card verification failed"))
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def credit(card_id: str, amount: float, reference_id: str | None = None, merchant: str = "AutoPilot Airlines", description: str | None = None) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/cards/{card_id}/credit", json={
                    "amount": amount,
                    "reference_id": reference_id,
                    "merchant": merchant,
                    "description": description,
                })
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def topup(card_id: str, amount: float, description: str | None = None) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/cards/{card_id}/topup", json={
                    "amount": amount,
                    "description": description,
                })
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                if resp.status_code == 400:
                    raise HTTPException(status_code=400, detail=resp.json().get("detail", "Invalid amount"))
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def get_transactions(card_id: str, limit: int = 50) -> list[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/cards/{card_id}/transactions", params={"limit": limit})
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def get_statement(card_id: str) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/cards/{card_id}/statement")
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)

    @staticmethod
    async def generate_card(brand: str = "visa") -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/cards/generate", json={"brand": brand})
                if resp.status_code == 400:
                    raise HTTPException(status_code=400, detail=resp.json().get("detail", "Invalid brand"))
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as e:
            _handle_connect_error(e)


card_service = CardServiceClient()
