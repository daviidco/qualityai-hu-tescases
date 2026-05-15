# QualityAI — Backend API

Backend FastAPI que expone los agentes de refinamiento de requerimientos de **qualityai-modulo1** como endpoints REST.

---

## ¿Qué hace?

Recibe un requerimiento en texto libre y lo transforma en historias de usuario estructuradas con criterios de aceptación Given/When/Then. Hay tres agentes disponibles, cada uno con mayor nivel de procesamiento que el anterior:

| Agente | Endpoint | Descripción |
|--------|----------|-------------|
| v1 RAG | `POST /api/v1/agent-rag/refine` | Busca historias similares en la base de conocimiento y genera historias en **texto libre** |
| v2 JSON | `POST /api/v1/agent-json/refine` | Igual que v1 pero con salida **JSON validada** (Contract A con Pydantic) y reintentos automáticos |
| v3 Ambiguity | `POST /api/v1/agent-ambiguity/refine` | Igual que v2 más un **detector determinístico de ambigüedades** (IEEE 830 / ISO 25010) que inyecta las ambigüedades en el prompt antes de llamar al LLM |

## Arquitectura

```
be-chatbot-ai/
├── main.py              # FastAPI app + lifespan (inicializa los 3 agentes al arrancar)
├── schemas.py           # Schemas de request/response
├── agents/
│   ├── v1_wrapper.py    # Clase AgentRAG — encapsula la lógica funcional de agente_v1_rag
│   ├── v2_wrapper.py    # Re-exporta RequirementsRefinerAgent de agente_v2_json
│   └── v3_wrapper.py    # Re-exporta RequirementsRefinerAgent de agente_v3_ambiguity
└── routers/
    └── agents.py        # Los 3 endpoints POST
```

Los agentes viven en `../qualityai-modulo1/`. Este backend los importa en tiempo de arranque y los mantiene en memoria para no recargar los embeddings (`SentenceTransformer`) ni la base vectorial (`ChromaDB`) en cada request.

---

## Requisitos previos

- Python 3.10+
- El directorio `qualityai-modulo1/` debe existir en `../` (mismo nivel que esta carpeta)
- Una API key de [Groq](https://console.groq.com)

---

## Instalación y arranque

### 1. Crear entorno virtual

```bash
cd be-chatbot-ai
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

> La primera instalación descarga el modelo `all-MiniLM-L6-v2` (~90 MB). Solo ocurre una vez.

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` y agregar la API key de Groq:

```env
GROQ_API_KEY=gsk_...
```

### 4. Arrancar el servidor

```bash
uvicorn main:app --reload
```

El servidor queda disponible en `http://localhost:8000`.

> Al arrancar por primera vez se cargan los embeddings y ChromaDB (~3-5 segundos). Los requests posteriores no tienen ese overhead.

---

## Documentación interactiva

Una vez corriendo, FastAPI genera documentación automática:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## Uso de los endpoints

Todos los endpoints reciben el mismo body:

```json
{
  "requirement": "Necesito un sistema de login seguro para la plataforma",
  "top_k": 3
}
```

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `requirement` | `string` | requerido | Texto libre del requerimiento |
| `top_k` | `int` | `3` | Cuántas historias similares recuperar de ChromaDB (1–10) |

### Ejemplo con curl

```bash
curl -X POST http://localhost:8000/api/v1/agent-ambiguity/refine \
  -H "Content-Type: application/json" \
  -d '{"requirement": "Necesito un módulo de pagos rápido y seguro", "top_k": 3}'
```

### Respuesta v1 (`agent-rag`)

```json
{
  "requirement": "...",
  "agent_version": "1.0.0",
  "result": "Como usuario registrado, quiero..."
}
```

### Respuesta v2 y v3 (`agent-json` / `agent-ambiguity`)

Retorna el **Contract A** completo — objeto `RefinedRequirements` con:

```json
{
  "pipeline_run_id": "run-abc12345",
  "agent_version": "3.0.0",
  "original_requirements_text": "...",
  "project_context": "...",
  "user_stories": [
    {
      "id": "US-001",
      "title": "...",
      "story_type": "functional",
      "priority": "high",
      "as_a": "usuario registrado",
      "i_want": "...",
      "so_that": "...",
      "acceptance_criteria": [
        {
          "id": "AC-001",
          "description": "...",
          "given": "...",
          "when": "...",
          "then": "...",
          "test_data_examples": [...],
          "is_negative_case": false,
          "boundary_values": [...]
        }
      ],
      "ambiguities_resolved": [
        {
          "original_text": "seguro",
          "issue": "adjetivo vago sin métrica",
          "resolution": "cifrado TLS 1.3 + tokens JWT con expiración de 24h",
          "assumption_made": true
        }
      ]
    }
  ],
  "total_ambiguities_found": 2,
  "total_assumptions_made": 2
}
```

---

## Códigos de respuesta

| Código | Significado |
|--------|-------------|
| `200` | Éxito |
| `422` | El LLM no generó JSON válido después de los reintentos (solo v2/v3) |
| `500` | Error interno del servidor |
