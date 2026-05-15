import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Agrega la raíz del repo al path para poder importar modulo3_quality_pipeline
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

# Carga el .env de modulo3 (contiene todas las API keys del pipeline)
_MODULO3_ENV = _REPO_ROOT / "modulo3_quality_pipeline" / ".env"
load_dotenv(_MODULO3_ENV)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.pipeline import router as pipeline_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from modulo3_quality_pipeline.config import Settings
    from modulo3_quality_pipeline.main import build_pipeline

    print("⏳ Inicializando Módulo 3 pipeline (ChromaDB + embeddings)…")
    settings = Settings(_env_file=str(_MODULO3_ENV))  # type: ignore[call-arg]
    _app.state.pipeline = build_pipeline(settings)
    _app.state.sessions = {}   # session_id → {requirement, contract_a, contract_b}
    print("✅ Pipeline listo")

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
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(pipeline_router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
