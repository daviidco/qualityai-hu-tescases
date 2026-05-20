# AGENTS.md — QualityAI Módulo 3

## Repo structure (3 Python packages)
```
├── be-chatbot-ai/               ← FastAPI backend (:8000)
├── fe-chatbot-ai/               ← Streamlit frontend (:8501)
├── modulo3_quality_pipeline/    ← Standalone orchestration library
├── docker-compose.yml           ← 3 services: backend + frontend + MongoDB
└── CLAUDE.md                    ← Existing instruction file (still relevant)
```
Backend loads `modulo3_quality_pipeline` at startup via `sys.path.insert(0, REPO_ROOT)` in `be-chatbot-ai/main.py:8-10`. The pipeline package is **not** pip-installed — it runs in-process.

## Essential commands

```bash
# Docker (recommended)
docker compose up --build          # first time (~5 min model download)
docker compose up                  # subsequent runs

# Local dev (3 terminals, from repo root)
# Terminal 1 — Backend
cd be-chatbot-ai && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd fe-chatbot-ai && pip install -r requirements.txt
streamlit run app.py

# Terminal 3 — Pipeline standalone (optional)
pip install "numpy<2"              # MUST be before sentence-transformers
pip install -r modulo3_quality_pipeline/requirements.txt
python -m modulo3_quality_pipeline --auto --input reqs/login.txt
```
The pipeline CLI (`python -m modulo3_quality_pipeline`) MUST be run from the repo root, not from inside `modulo3_quality_pipeline/`.

## Setup

- **Python 3.11 only** — `sentence-transformers` + PyTorch require `numpy<2`
- Copy `modulo3_quality_pipeline/.env.example` → `.env` and set at least `GEMINI_API_KEY`
- `GEMINI_API_KEY` is **always required** — embeddings use `gemini-embedding-001` regardless of `LLM_PROVIDER`
- LLM providers: `gemini | groq | deepseek | cerebras`
- Frontend only needs `BACKEND_URL=http://localhost:8000/api/v1`

## Architecture

### Pipeline stages (in `modulo3_quality_pipeline/`)
| Stage | Agent | Produces |
|-------|-------|----------|
| 1. Requirements refinement | `RequirementsAgent` | Contract A (user stories + ACs) |
| 2. Test generation | `TestArchitectAgent` | Contract B (Gherkin + ISO 25010) |
| 3–6. Code gen (optional) | `CodeGeneratorAgent`, `StaticAnalysisAgent`, `TraceabilityAgent`, `CodeReviewAgent` | Contract D |
| 7. Reporting | `HtmlReporter` | Contract C + HTML |

Contracts are typed Pydantic v2 models in `contracts/`. Never pass raw dicts between agents.

### Backend endpoints (`be-chatbot-ai/`)
All pipeline endpoints under `/api/v1/pipeline/`, **JWT auth required** (bearer token):
1. `POST /analyze` — detect IEEE 830 ambiguities, create HITL session
2. `POST /generate-tests` — apply analyst resolutions → Contract A + B
3. `POST /finalize` — apply test decisions → Contract C + HTML report + PDF
4. `GET /projects` — list history
5. `GET /projects/{run_id}` — full project detail
6. `GET /status` — active LLM provider info
7. `POST /skip-provider` — advance to next LLM in fallback chain

Additional endpoints: `/auth/` (login), `/admin/` (users + LLM config), `/projects/` (drafts).

### Frontend views (`fe-chatbot-ai/`)
Driven by `st.session_state.view`. HTTP via `api.py` (httpx async client). Views:
- `admin_users`, `llm_config` — admin
- `scrum_projects` — scrum leader
- `analyst_projects` — analyst
- `chat` — free analysis input
- `hitl_ambiguities`, `hitl_tests` — HITL review panels
- `report` — executive report

### RAG pipeline (4 stages)
HyDE → Dense (Gemini → ChromaDB) → BM25 → RRF fusion (k=60) → CrossEncoder reranker

### Sessions
HITL sessions stored in `app.state.sessions` (in-memory, not persisted across restarts).

## Key gotchas

- **No tests exist** — no pytest, no conftest, no test directory anywhere in the repo
- **MongoDB required** — backend persists projects, users, LLM config in MongoDB. Docker Compose includes a `mongodb` service. Standalone dev needs a running MongoDB.
- **Default admin credentials**: `admin@qualityai.com` / `admin1234` (created on first startup)
- **LLM config is in MongoDB** — `llm_config` document in `qualityai` DB, restored on restart. Multi-key fallback chain is supported.
- **Backend imports pipeline via sys.path** — `sys.path.insert(0, str(REPO_ROOT))` at `be-chatbot-ai/main.py:8-10`. This means `modulo3_quality_pipeline` must be at the repo root.
- **ChromaDB Docker volume**: Named volume `chroma_data`; deleting forces full re-index on next startup
- **Backend health check**: 150s start period (model loading)
- **ECO_MODE=true** reduces output (max 3 stories, 2 ACs per story, 2 scenarios per AC)
- **JSON truncation**: `json_repair` auto-fixes truncated LLM responses
- **Rate limit handling**: 429 responses with retry banners in frontend
- **Pipeline CLI uses `input()`** for interactive HITL — won't work in headless CI without `--auto`
- **`contract_d.py`** exists alongside contracts A/B/C for code generation results (stages 3-6)
