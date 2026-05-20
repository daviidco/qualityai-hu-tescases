"""Dependencies de FastAPI para autenticación JWT."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from auth_utils import decode_token

_bearer = HTTPBearer()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    try:
        payload = decode_token(creds.credentials)
        return {"email": payload["sub"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol admin",
        )
    return user


async def require_analyst_or_leader(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("admin", "analyst", "scrum_leader"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol analyst o scrum_leader",
        )
    return user


async def require_scrum_or_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("admin", "scrum_leader"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol scrum_leader o admin",
        )
    return user
