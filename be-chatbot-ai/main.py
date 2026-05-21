import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# Agrega la raíz del repo al path para poder importar modulo3_quality_pipeline
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

# Carga el .env de modulo3 (contiene API keys del pipeline + MongoDB + JWT)
_MODULO3_ENV = _REPO_ROOT / "modulo3_quality_pipeline" / ".env"
load_dotenv(_MODULO3_ENV)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth_utils import hash_password
from db import get_db, init_indexes
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.pipeline import router as pipeline_router
from routers.projects import router as projects_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from modulo3_quality_pipeline.config import Settings
    from modulo3_quality_pipeline.main import build_pipeline

    # Directorios de almacenamiento persistente
    Path("/app/storage/logos").mkdir(parents=True, exist_ok=True)

    print("⏳ Inicializando Módulo 3 pipeline (ChromaDB + embeddings)…")
    settings = Settings(_env_file=str(_MODULO3_ENV))  # type: ignore[call-arg]
    _app.state.pipeline = build_pipeline(settings)
    _app.state.sessions = {}   # session_id → {requirement, contract_a, contract_b}
    print("✅ Pipeline listo")

    # ── MongoDB: índices + admin por defecto ──────────────────────────────────
    print("⏳ Conectando a MongoDB…")
    await init_indexes()
    print("✅ MongoDB listo")

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@qualityai.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin1234")
    db = get_db()
    if not await db.users.find_one({"email": admin_email}):
        pw_hash, salt = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": pw_hash,
            "salt": salt,
            "role": "admin",
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
            "last_login": None,
        })
        print(f"✅ Admin creado: {admin_email}")
    else:
        print(f"ℹ️  Admin ya existe: {admin_email}")

    # ── Restaurar config LLM desde MongoDB (multi-key + orden de prioridad) ─────
    llm_doc = await db["llm_config"].find_one({"_id": "llm_config"})
    if llm_doc:
        from routers.admin import _apply_to_env, _migrate
        from modulo3_quality_pipeline.llm.factory import create_provider_chain
        migrated = _migrate(llm_doc)
        _apply_to_env(migrated)
        try:
            chain = create_provider_chain(migrated)
            _app.state.pipeline.swap_llm_provider(chain)
            order = migrated.get("provider_order", [])
            print(f"✅ Config LLM restaurada — cadena de prioridad: {' → '.join(order)}")
        except Exception as exc:
            print(f"⚠️  No se pudo restaurar config LLM: {exc}")

    # ── Restaurar eco_mode desde MongoDB ──────────────────────────────────────
    eco_doc = await db["eco_config"].find_one({"_id": "eco_config"})
    if eco_doc:
        eco_mode = eco_doc.get("eco_mode", False)
        _app.state.pipeline.set_eco_mode(eco_mode)
        os.environ["ECO_MODE"] = "true" if eco_mode else "false"
        print(f"{'✅' if eco_mode else 'ℹ️ '} Eco mode: {'activado' if eco_mode else 'desactivado'}")
    else:
        # No hay config en MongoDB: respetar el valor del .env que ya tiene el pipeline
        current = _app.state.pipeline._settings.eco_mode
        print(f"{'✅' if current else 'ℹ️ '} Eco mode desde .env: {'activado' if current else 'desactivado'}")

    yield


app = FastAPI(
    title="QualityAI — Módulo 3 API",
    description="Pipeline de calidad: HU · Test Cases · Riesgos ISO 25010.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
