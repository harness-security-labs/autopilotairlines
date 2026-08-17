from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from ..config import settings

security = HTTPBearer(auto_error=False)


async def get_current_user(request: Request) -> dict | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        decode_kwargs = {}
        if settings.jwt_audience_required:
            decode_kwargs["audience"] = settings.jwt_audience
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": settings.jwt_audience_required},
            **decode_kwargs,
        )
        return payload
    except JWTError:
        return None


async def require_auth(request: Request) -> dict:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_admin_user(request: Request) -> dict:
    """Require authentication. When admin_role_check_enabled is True (intermediate/advanced),
    also require the JWT role claim to be 'admin'."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if settings.admin_role_check_enabled and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
