"""Motor async client — conexión a MongoDB e inicialización de índices."""
from __future__ import annotations

import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        url = os.environ["MONGODB_URL"]
        _client = AsyncIOMotorClient(url)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    db_name = os.environ.get("MONGO_DB_NAME", "qualityai")
    return get_client()[db_name]


async def init_indexes() -> None:
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.projects.create_index("run_id", unique=True)
    await db.projects.create_index([("created_at", -1)])
    await db.projects.create_index("review_status")
