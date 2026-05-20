# QualityAI — Módulo 3

Pipeline de generación de calidad de software asistido por IA: transforma requerimientos en texto libre en Historias de Usuario estructuradas, casos de prueba Gherkin y un reporte ejecutivo de riesgos ISO 25010, con revisión humana en cada etapa crítica (HITL).

---

## Propósito

Los equipos de QA y análisis de requerimientos invierten horas convirtiendo descripciones de negocio en artefactos verificables. QualityAI M3 automatiza ese proceso en tres etapas secuenciales, manteniendo al analista en el centro del flujo:

| Problema                                     | Solución                                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------- |
| Requerimientos ambiguos llegan al desarrollo | Detector determinístico (IEEE 830) + resolución explícita antes del LLM   |
| Test cases generados sin trazabilidad        | Contract A → Contract B con cobertura AC-por-AC                           |
| Sin visibilidad de riesgos no funcionales    | Mapeo automático a ISO 25010, matriz de riesgos y recomendaciones         |
| El analista pierde control sobre la IA       | HITL en dos puntos: ambigüedades y aprobación de test cases               |
| Proyectos generados se pierden al cerrar     | Historial persistente en disco, recuperable entre sesiones                |
| LLMs con límite de tokens truncan el JSON    | Reparación automática con `json_repair` + límites explícitos en el prompt |
| Rate limit del proveedor LLM da error 500    | Detección y banner informativo en el frontend con tiempo de espera        |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        Usuario (Analista QA)                    │
└───────────────────┬───────────────────────────────┬─────────────┘
                    │ Streamlit (8501)               │
┌───────────────────▼───────────────────────────────▼─────────────┐
│                     Frontend — fe-chatbot-ai                     │
│                                                                  │
│  Vista: chat → hitl_ambiguities → hitl_tests → report            │
│  Sidebar: historial de proyectos con carga lazy del reporte      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / JSON
┌───────────────────────────▼─────────────────────────────────────┐
│                     Backend — be-chatbot-ai                      │
│                         FastAPI (8000)                           │
│                                                                  │
│  POST /pipeline/analyze          → detecta ambigüedades          │
│  POST /pipeline/generate-tests   → genera HU + test cases        │
│  POST /pipeline/finalize         → revisión + reporte + PDF      │
│  GET  /pipeline/projects         → lista historial               │
│  GET  /pipeline/projects/{id}    → detalle de un proyecto        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Python in-process
┌───────────────────────────▼─────────────────────────────────────┐
│              modulo3_quality_pipeline                            │
│                                                                  │
│  AmbiguityDetector (IEEE 830)                                    │
│  RequirementsAgent v5  ── RAG híbrido ── LLM → Contract A       │
│  TestArchitectAgent    ── RAG híbrido ── LLM → Contract B        │
│  QualityPipeline       ──────────────────────── Contract C       │
│  HtmlReporter          ─────────────────── Reporte HTML          │
│                                                                  │
│  RAG: HyDE + BM25 + Dense + RRF + CrossEncoder reranker         │
│  Vector store: ChromaDB (KB de historias + patrones)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tecnologías

### Backend

| Tecnología                     | Rol                                                  |
| ------------------------------ | ---------------------------------------------------- |
| **FastAPI**                    | API REST, gestión de sesiones HITL server-side       |
| **Pydantic v2**                | Contratos tipados (Contract A / B / C)               |
| **ChromaDB**                   | Vector store para recuperación RAG                   |
| **sentence-transformers**      | Cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`)    |
| **rank-bm25**                  | Recuperación BM25 léxica en el paso de retrieval     |
| **Gemini API**                 | Embeddings (`gemini-embedding-001`) y generación     |
| **Groq / DeepSeek / Cerebras** | Proveedores LLM alternativos (seleccionable por env) |
| **json_repair**                | Repara JSON truncado por límites de tokens del LLM   |
| **fpdf2 + DejaVu**             | Generación de reporte PDF con soporte UTF-8 completo |
| **uvicorn**                    | ASGI server                                          |

### Frontend

| Tecnología         | Rol                                                             |
| ------------------ | --------------------------------------------------------------- |
| **Streamlit**      | Framework web Python para UI reactiva                           |
| **httpx**          | Cliente HTTP hacia el backend                                   |
| **report_view.py** | Reporte ejecutivo renderizado en Streamlit nativo (tema oscuro) |

---

## Componentes

### `modulo3_quality_pipeline/`

El núcleo del sistema. Pipeline secuencial independiente del frontend.

```
modulo3_quality_pipeline/
├── agents/
│   ├── requirements_agent.py   # Agente v5: AmbiguityDetector + RAG + LLM → Contract A
│   └── test_architect_agent.py # Agente: RAG + LLM → Contract B (Gherkin)
├── analysis/
│   └── ambiguity_detector.py   # Detector determinístico IEEE 830 / ISO 25010
├── contracts/
│   ├── contract_a.py           # RefinedRequirements: HU + criterios de aceptación
│   ├── contract_b.py           # GherkinTestSuite: escenarios + revisión HITL
│   └── contract_c.py           # ExecutiveReport: métricas, insights, cobertura
├── llm/
│   ├── gemini_provider.py      # Proveedor Gemini con json_repair + rate limit
│   ├── groq_provider.py        # Proveedor Groq con json_repair + rate limit
│   ├── deepseek_provider.py    # Proveedor DeepSeek con json_repair + rate limit
│   └── cerebras_provider.py   # Proveedor Cerebras con json_repair + rate limit
├── rag/
│   ├── embedder.py             # GeminiEmbedder
│   ├── retriever.py            # HybridRetriever (BM25 + Dense + RRF)
│   ├── query_expander.py       # HyDE: genera consulta hipotética para dense retrieval
│   └── reranker.py             # CrossEncoderReranker
├── reporting/
│   └── html_reporter.py        # Genera reporte HTML completo con CSS/JS interactivo
├── pipeline.py                 # Orquestador secuencial + métodos HITL web
└── main.py                     # CLI + DI wiring (build_pipeline)
```

### `be-chatbot-ai/`

API REST que expone el pipeline al frontend.

```
be-chatbot-ai/
├── main.py                     # FastAPI app + lifespan (init pipeline + sessions)
├── schemas.py                  # Pydantic schemas para los 5 endpoints
├── project_store.py            # Persistencia de proyectos en disco (/app/storage)
├── executive_pdf.py            # Generador PDF con fpdf2 y fuentes DejaVu Unicode
└── routers/
    └── pipeline.py             # POST /analyze · /generate-tests · /finalize
                                # GET  /projects · /projects/{run_id}
```

### `fe-chatbot-ai/`

Aplicación Streamlit con flujo de 4 vistas.

```
fe-chatbot-ai/
├── app.py                      # Routing entre vistas + carga de historial
├── config.py                   # BACKEND URL
├── state.py                    # Inicialización del session_state
├── handlers.py                 # handle_analyze / generate_tests / finalize
├── api.py                      # Cliente HTTP httpx (GET + POST + detección rate limit)
└── ui/
    ├── sidebar.py              # Lista de proyectos históricos
    ├── report_view.py          # Reporte ejecutivo nativo (tema oscuro + descarga PDF)
    ├── hitl_ambiguities.py     # Panel HITL: revisión de ambigüedades
    ├── hitl_tests.py           # Panel HITL: revisión de test cases + decisión global
    ├── styles.py               # CSS global inyectado
    └── js_utils.py             # Sidebar toggle + navegación historial ↑↓
```

---

## Flujo HITL (Human-In-The-Loop)

El analista interviene en **dos puntos críticos** antes de que el LLM tome decisiones:

```
1. Requerimiento ingresado
        │
        ▼
2. AmbiguityDetector (determinístico, sin LLM)
   Detecta palabras ambiguas según IEEE 830:
   adjetivos vagos · verbos imprecisos · cuantificadores sin métrica

        │ ¿hay ambigüedades?
        ├─ SÍ → Panel de revisión
        │       Analista: acepta sugerencia / escribe resolución propia / descarta
        │       → resoluciones inyectadas como HECHOS en el prompt (assumption_made=False)
        └─ NO → continúa sin intervención

        ▼
3. RequirementsAgent genera Contract A (Historias de Usuario + AC)
   TestArchitectAgent genera Contract B (Escenarios Gherkin)

        ▼
4. Panel de revisión de test cases
   Analista por escenario: acepta / reclasifica ISO / comenta / salta
   Analista: nombre del revisor · decisión global · feedback

        ▼
5. Pipeline genera Contract C + Reporte HTML + PDF ejecutivo
   Reporte guardado en historial de proyectos (persistente entre sesiones)
```

---

## Reporte generado

El reporte nativo (tema oscuro) incluye:

- **KPIs**: historias, criterios, tests generados, cobertura %
- **Ambigüedades** detectadas y resueltas (LLM vs. analista)
- **Historias de Usuario** con criterios de aceptación (acordeones interactivos)
- **Test Cases Gherkin** por historia, clasificados por tipo e ISO 25010
- **Revisión HITL**: tabla de decisiones por escenario, aprobador, fecha
- **Cobertura ISO 25010**: barras por las 8 características de calidad
- **Riesgos y recomendaciones**: matriz de riesgo + herramientas sugeridas
- **Descarga PDF**: reporte ejecutivo en PDF con fuentes Unicode (fondo blanco, listo para imprimir)
- **Badge ECO**: indica visualmente si el reporte fue generado en modo eco

---

## Historial de proyectos

Cada reporte generado se persiste automáticamente en disco. Al recargar la aplicación:

- El sidebar lista todos los proyectos anteriores (metadatos: fecha, HU, tests, cobertura)
- Al hacer clic en un proyecto se carga el reporte completo bajo demanda (carga lazy)
- Los datos sobreviven reinicios del contenedor gracias al volumen Docker `projects_data`

---

## Modo ECO

Activa una versión reducida del pipeline que genera menos tokens, útil cuando el proveedor LLM tiene límites de salida estrechos:

```env
ECO_MODE=true   # máx 3 HU · 2 AC por HU · 2 escenarios por AC
ECO_MODE=false  # modo completo (por defecto)
```

El reporte y el PDF muestran un badge **⚡ ECO** cuando el análisis fue generado en este modo.

---

## Resiliencia ante límites de tokens

El pipeline maneja de forma transparente dos problemas comunes con LLMs:

**JSON truncado**: Si el modelo corta su respuesta a mitad del JSON (por límite de tokens), `json_repair` reconstruye automáticamente el objeto y `_parse_contract_a` acepta historias parciales en vez de fallar toda la operación.

**Rate limit**: Cuando el proveedor LLM devuelve un 429, el backend retorna el error con código HTTP 429 y el frontend muestra un banner naranja con el tiempo de espera estimado en vez de un error genérico 500.

---

## Cómo levantar

### Prerrequisito: configurar API keys

```bash
cp modulo3_quality_pipeline/.env.example modulo3_quality_pipeline/.env
# Editar .env y agregar al menos GEMINI_API_KEY (embeddings siempre usan Gemini)
# LLM_PROVIDER puede ser: gemini | groq | deepseek | cerebras
```

### Con Docker (recomendado)

```bash
# Primera vez — construye imágenes (~5 min por la descarga de modelos)
docker compose up --build -d

# Levantamiento posterior (imágenes ya construidas)
docker compose up
```

- Frontend: http://localhost:8501
- Backend API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

> El backend tarda ~60-150 s en arrancar la primera vez: inicializa ChromaDB,
> indexa la base de conocimiento e inicializa el reranker. Las veces siguientes
> el índice ChromaDB ya existe en el volumen y arranca en ~20 s.

### En desarrollo local (sin Docker)

```bash
# Terminal 1 — Backend
cd be-chatbot-ai
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd fe-chatbot-ai
pip install -r requirements.txt
streamlit run app.py
```

### Variables de entorno relevantes

| Variable           | Descripción                          | Ejemplo                                     |
| ------------------ | ------------------------------------ | ------------------------------------------- |
| `LLM_PROVIDER`     | Proveedor LLM activo                 | `gemini` / `groq` / `deepseek` / `cerebras` |
| `GEMINI_API_KEY`   | Siempre requerida (embeddings)       | `AIza...`                                   |
| `GROQ_API_KEY`     | Requerida si `LLM_PROVIDER=groq`     | `gsk_...`                                   |
| `DEEPSEEK_API_KEY` | Requerida si `LLM_PROVIDER=deepseek` | `sk-...`                                    |
| `CEREBRAS_API_KEY` | Requerida si `LLM_PROVIDER=cerebras` | `csk-...`                                   |
| `ECO_MODE`         | Modo de bajo consumo de tokens       | `true` / `false`                            |
| `BACKEND_URL`      | URL del backend (solo FE)            | `http://localhost:8000/api/v1`              |

---

## Endpoints del Backend

| Método | Ruta                                 | Descripción                              |
| ------ | ------------------------------------ | ---------------------------------------- |
| `GET`  | `/health`                            | Health check                             |
| `POST` | `/api/v1/pipeline/analyze`           | Detecta ambigüedades, crea sesión        |
| `POST` | `/api/v1/pipeline/generate-tests`    | Genera Contract A + B con resoluciones   |
| `POST` | `/api/v1/pipeline/finalize`          | Aplica decisiones, genera reporte + PDF  |
| `GET`  | `/api/v1/pipeline/projects`          | Lista historial de proyectos (metadatos) |
| `GET`  | `/api/v1/pipeline/projects/{run_id}` | Detalle completo de un proyecto          |

Documentación interactiva completa: `http://localhost:8000/docs`
