"""Hashing de contraseñas con PBKDF2-HMAC-SHA256 + salt, y emisión/verificación JWT."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from jose import jwt

_ITERATIONS = 260_000
_ALGORITHM = "HS256"


def hash_password(password: str) -> tuple[str, str]:
    """Devuelve (hash_hex, salt_hex). Salt de 32 bytes aleatorios."""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return key.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(key.hex(), hash_hex)


def create_access_token(email: str, role: str) -> str:
    secret = os.environ["JWT_SECRET"]
    expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica y valida el JWT. Lanza JWTError si es inválido o expirado."""
    secret = os.environ["JWT_SECRET"]
    return jwt.decode(token, secret, algorithms=[_ALGORITHM])
