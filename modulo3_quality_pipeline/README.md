# QualityAI — Módulo 3: Quality Pipeline

Pipeline unificado de calidad impulsado por Google Gemini. Toma un requerimiento en texto libre y produce historias de usuario refinadas, una suite de tests Gherkin y un reporte ejecutivo HTML.

```
Requerimiento
    ↓
RequirementsAgent   → Contract A (historias + criterios de aceptación + HITL)
    ↓
TestArchitectAgent  → Contract B (suite Gherkin + cobertura ISO 25010)
    ↓
QualityPipeline     → Contract C (reporte ejecutivo) + report.html
```

---

## Requisitos previos

| Herramienta | Versión mínima |
|-------------|----------------|
| Python | **3.11** (PyTorch no tiene wheels para 3.13) |
| Gemini API key | gratuita en [aistudio.google.com](https://aistudio.google.com) |

---

## Instalación

```bash
# 1. Entrar al directorio del módulo
cd modulo3_quality_pipeline

# 2. Crear el venv con Python 3.11
python3.11 -m venv .venv

# Si usas pyenv:
# ~/.pyenv/versions/3.11.9/bin/python -m venv .venv

# 3. Activar el venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 4. Instalar dependencias
#    numpy<2 primero para evitar conflicto con PyTorch 2.2
pip install "numpy<2"
pip install -r requirements.txt
```

> La primera instalación descarga `sentence-transformers` + `torch` (~1.5 GB). Es normal que tarde varios minutos.

---

## Configuración

```bash
# Dentro de modulo3_quality_pipeline/
cp .env.example .env
```

Abrir `.env` y completar:

```
GEMINI_API_KEY=AIza...   # única variable obligatoria
```

El resto de variables tienen valores por defecto funcionales.

---

## Ejecución

> **Importante:** los comandos se ejecutan desde el directorio **padre** (`QualityAI/`), con el venv activado.

```bash
# Activar el venv (si no está activo)
source modulo3_quality_pipeline/.venv/bin/activate

# Subir al directorio padre si estás dentro del módulo
cd ..

# Verificar que Python ve el módulo
python -c "import modulo3_quality_pipeline; print('OK')"
```

### Modo interactivo (recomendado para analistas)

```bash
python -m modulo3_quality_pipeline
```

El pipeline pide el requerimiento por consola y presenta cada ambigüedad para revisión HITL (Human-in-the-Loop).

### Modo automático (batch, sin intervención)

```bash
python -m modulo3_quality_pipeline --auto
```

### Leer requerimiento desde archivo

```bash
python -m modulo3_quality_pipeline --input reqs/login.txt
python -m modulo3_quality_pipeline --auto --input reqs/login.txt
```

---

## Por qué ejecutar desde el directorio padre

`python -m modulo3_quality_pipeline` le dice a Python que busque el paquete `modulo3_quality_pipeline` en `sys.path`. Python incluye en `sys.path` el directorio actual, por lo que:

- Desde `QualityAI/` → Python encuentra la carpeta `modulo3_quality_pipeline/` → ✅
- Desde dentro de `modulo3_quality_pipeline/` → Python busca una subcarpeta con ese mismo nombre que no existe → ❌

El archivo `__main__.py` incluido permite usar `python -m modulo3_quality_pipeline` (sin `.main`).

---

## Artefactos generados

Se guardan en `modulo3_quality_pipeline/output/`:

| Archivo | Contenido |
|---------|-----------|
| `contract_a_<id>.json` | Historias de usuario refinadas con criterios de aceptación |
| `contract_b_<id>.json` | Suite Gherkin con cobertura ISO 25010 y matriz de cobertura |
| `contract_c_<id>.json` | Reporte ejecutivo: métricas RAG, insights de calidad, duración |
| `report_<id>.html` | Reporte HTML autocontenido — abrir en el navegador |

---

## Estructura

```
modulo3_quality_pipeline/
├── __main__.py                 # Permite: python -m modulo3_quality_pipeline
├── main.py                     # CLI + wiring de dependencias (DI)
├── pipeline.py                 # QualityPipeline — secuenciador de etapas
├── config.py                   # Settings (Pydantic BaseSettings)
│
├── agents/
│   ├── base.py                 # AbstractBaseAgent[InputT, OutputT]
│   ├── requirements_agent.py   # Etapa 1: refinamiento + HITL
│   └── test_architect_agent.py # Etapa 2: generación Gherkin + ISO 25010
│
├── rag/
│   ├── embedder.py             # GeminiEmbedder (text-embedding-004, 768-dim)
│   ├── repository.py           # KnowledgeRepository (ChromaDB + chunked indexing)
│   ├── query_expander.py       # HyDEQueryExpander (Hypothetical Document Embeddings)
│   ├── retriever.py            # HybridRetriever (BM25 + Dense + RRF)
│   └── reranker.py             # CrossEncoderReranker (ms-marco-MiniLM-L-6-v2)
│
├── contracts/
│   ├── contract_a.py           # RefinedRequirements
│   ├── contract_b.py           # GherkinTestSuite
│   └── contract_c.py           # ExecutiveReport (meta-contrato)
│
├── analysis/
│   └── ambiguity_detector.py   # IEEE 830 / ISO 25010 — 46+ palabras ambiguas
│
├── llm/
│   └── gemini_provider.py      # GeminiProvider (JSON mode + exponential backoff)
│
├── reporting/
│   └── html_reporter.py        # → report.html autocontenido
│
├── knowledge_bases/
│   ├── stories_kb.json         # 15 historias de referencia
│   └── patterns_kb.json        # 10 patrones de testing
│
├── output/                     # Artefactos (ignorado en git)
├── .env.example
└── requirements.txt
```

---

## Pipeline RAG de 4 etapas

```
Query
  ↓ 1. HyDE — genera un documento hipotético ideal y lo embedea
  ↓ 2a. Dense retrieval — GeminiEmbedder → ChromaDB cosine → top-20
  ↓ 2b. BM25 sparse — captura keywords exactos que semantic search pierde
  ↓ 3. RRF (k=60) — fusiona rankings sin normalizar espacios de score
  ↓ 4. CrossEncoder — reranking preciso → top-5 al agente
```

La KB se indexa automáticamente en la primera ejecución (ChromaDB persistente en `chroma_db_m3/`).

---

## Solución de problemas

**`No module named 'modulo3_quality_pipeline'`**
Estás ejecutando desde dentro del directorio del módulo. Sube un nivel: `cd ..`

**`Error de configuración: gemini_api_key`**
Falta el archivo `.env` o la variable `GEMINI_API_KEY`.
```bash
cp .env.example .env   # luego editar y pegar la key
```

**`429 Resource Exhausted` / rate limit**
El tier gratuito tiene límite de 15 RPM. El pipeline tiene backoff exponencial automático (10s → 20s → 40s).

**NumPy / PyTorch incompatibilidad**
```bash
pip install "numpy<2" && pip install "torch>=2.4"
```

**`NameError: name 'nn'` en transformers**
```bash
pip install "transformers<5.0"
```
