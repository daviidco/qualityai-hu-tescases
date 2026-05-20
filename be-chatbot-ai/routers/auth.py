"""Endpoints de autenticación y gestión de usuarios."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from auth_utils import create_access_token, hash_password, verify_password
from db import get_db
from dependencies import get_current_user, require_admin
from schemas import CreateUserRequest, LoginRequest, TokenResponse, UserOut

router = APIRouter(tags=["Auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    db = get_db()
    user = await db.users.find_one({"email": req.email, "is_active": True})
    if not user or not verify_password(req.password, user["password_hash"], user["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    await db.users.update_one(
        {"email": req.email},
        {"$set": {"last_login": datetime.now(timezone.utc)}},
    )
    token = create_access_token(user["email"], user["role"])
    return TokenResponse(access_token=token, email=user["email"], role=user["role"])


@router.get("/auth/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)) -> UserOut:
    db = get_db()
    user = await db.users.find_one({"email": current_user["email"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserOut(
        email=user["email"],
        name=user.get("name", ""),
        role=user["role"],
        is_active=user["is_active"],
        created_at=user["created_at"].isoformat(),
    )


@router.post("/auth/users", response_model=UserOut, status_code=201)
async def create_user(
    req: CreateUserRequest,
    _admin: dict = Depends(require_admin),
) -> UserOut:
    db = get_db()
    if await db.users.find_one({"name": req.name}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con el nombre '{req.name}'",
        )
    pw_hash, salt = hash_password(req.password)
    if req.role == "developer" and req.developer_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere developer_type (backend | frontend | devops) para rol developer",
        )
    if req.role != "developer" and req.developer_type is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="developer_type solo aplica para rol developer",
        )

    doc = {
        "email": req.email,
        "name": req.name,
        "password_hash": pw_hash,
        "salt": salt,
        "role": req.role,
        "developer_type": req.developer_type if req.role == "developer" else None,
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
        "last_login": None,
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con email {req.email}",
        )
    return UserOut(
        email=doc["email"],
        name=doc.get("name", ""),
        role=doc["role"],
        developer_type=doc.get("developer_type"),
        is_active=doc["is_active"],
        created_at=doc["created_at"].isoformat(),
    )


@router.get("/auth/users", response_model=list[UserOut])
async def list_users(_admin: dict = Depends(require_admin)) -> list[UserOut]:
    db = get_db()
    cursor = db.users.find({}, {"_id": 0, "password_hash": 0, "salt": 0}).sort("created_at", -1)
    users = await cursor.to_list(length=None)
    return [
        UserOut(
            email=u["email"],
            name=u.get("name", ""),
            role=u["role"],
            developer_type=u.get("developer_type"),
            is_active=u["is_active"],
            created_at=u["created_at"].isoformat(),
        )
        for u in users
    ]


@router.delete("/auth/users/{email}", status_code=204)
async def deactivate_user(
    email: str,
    current_admin: dict = Depends(require_admin),
) -> None:
    if email == current_admin["email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta",
        )
    db = get_db()
    result = await db.users.update_one({"email": email}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
