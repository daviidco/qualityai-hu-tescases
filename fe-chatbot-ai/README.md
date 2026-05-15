# QualityAI — Frontend

Interfaz de chat para interactuar con los agentes de refinamiento de requerimientos. Construida con **Streamlit** — Python puro, sin JavaScript.

---

## Vista general

```
┌─────────────────────────────────────────────────┐
│  QUALITYAI        Command Center                 │
│  ─────────────    ─────────────────────────────  │
│  ⚡ Strategy      [mensajes del agente]          │
│  🏗 Architect                                    │
│  ⚙  QA Engineer  [mensaje del usuario]          │
│  🛡 Security                                     │
│                   [resultado con historias]      │
│  + New Refinement                               │
│                   ┌─────────────────────────┐   │
│                   │ Escribe tu requerimiento │   │
│                   └─────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## Agentes disponibles

| Icono | Nombre | Backend | Qué hace | Qué entrega |
|-------|--------|---------|----------|------------|
| ⚡ | Human-Validated Refiner | v4 HITL | Detecta ambigüedades y le presenta cada una al analista para que las resuelva antes de llamar al LLM | Contract A JSON — `assumption_made: false` en todas las ambigüedades |
| 🏗 | Ambiguity-Aware Refiner | v3 Ambiguity | Escanea el requerimiento con el detector IEEE 830 antes del LLM e inyecta las ambigüedades detectadas en el prompt | Contract A JSON con ambigüedades resueltas por el LLM |
| ⚙ | Structured Story Builder | v2 JSON | RAG sobre la base de conocimiento + validación Pydantic con reintentos automáticos si el JSON es inválido | Contract A JSON validado y estructurado |
| 🛡 | RAG Draft Generator | v1 RAG | Recupera historias similares de ChromaDB y genera con ese contexto, sin validación de estructura | Texto libre — útil para explorar o hacer borradores rápidos |

---

## Requisitos previos

- Python 3.10+
- El **backend** (`be-chatbot-ai`) corriendo en `http://localhost:8000`

---

## Instalación y arranque

### 1. Crear entorno virtual

```bash
cd fe-chatbot-ai
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno (opcional)

Por defecto apunta a `http://localhost:8000/api/v1`. Si el backend corre en otro puerto:

```bash
cp .env.example .env
# editar .env y cambiar BACKEND_URL
```

### 4. Arrancar

```bash
streamlit run app.py
```

La app queda disponible en `http://localhost:8501`.

> El backend debe estar corriendo antes de enviar cualquier mensaje. Si no hay conexión, la app muestra un error descriptivo en pantalla.

---

## Arranque completo (backend + frontend)

```bash
# Terminal 1 — backend
cd be-chatbot-ai
source venv/bin/activate
uvicorn main:app --reload

# Terminal 2 — frontend
cd fe-chatbot-ai
source venv/bin/activate
streamlit run app.py
```

---

## Flujo de uso

### Agentes simples (Test Architect, QA Engineer, Security Probe)

1. Seleccionar el agente en la barra lateral
2. Escribir el requerimiento en el input inferior
3. Presionar Enter — el agente responde con las historias de usuario

### Strategy Agent — Human-in-the-Loop (2 pasos)

1. Escribir el requerimiento y presionar Enter
2. Si hay ambigüedades: aparece el **panel de revisión** con una tarjeta por cada término ambiguo detectado
   - **Accept suggestion** — usa la resolución automática del detector (IEEE 830)
   - **Custom resolution** — escribir una definición concreta propia
   - **Not ambiguous — dismiss** — confirmar que el término es suficientemente claro
3. Hacer clic en **Generate Stories →** para que el LLM use las decisiones como hechos (`assumption_made: false`)

Si no se detectan ambigüedades, el agente genera las historias directamente.

---

## Controles

| Control | Ubicación | Descripción |
|---------|-----------|-------------|
| Selector de agente | Encima del input | Cambia el agente activo sin borrar el historial |
| `top_k` | Encima del input (derecha) | Cuántas historias similares recuperar de ChromaDB (1–10) |
| **New Refinement** | Sidebar inferior | Limpia el historial y reinicia la sesión |

---

## Estructura del proyecto

```
fe-chatbot-ai/
├── app.py                  # Aplicación completa (UI + lógica + llamadas al backend)
├── requirements.txt
├── .env.example
└── .streamlit/
    └── config.toml         # Tema oscuro y configuración del servidor
```
