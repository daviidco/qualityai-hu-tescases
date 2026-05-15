"""Página de documentación de agentes."""

import streamlit as st

_DOCS: list[dict] = [
    {
        "title": "Refinador con Validación Humana",
        "version": "v4.0 · HITL",
        "icon": "⚡",
        "color": "#00bcd4",
        "what": (
            "El único agente donde el analista tiene la última palabra. "
            "Antes de llamar al LLM, el detector IEEE 830 / ISO 25010 escanea el "
            "requerimiento y extrae cada término ambiguo. El frontend presenta una "
            "tarjeta por ambigüedad y el analista decide: aceptar la sugerencia automática, "
            "escribir su propia definición concreta, o confirmar que el término no es ambiguo. "
            "Solo después de resolver todas las ambigüedades el LLM genera las historias, "
            "usando las decisiones como hechos (<code>assumption_made: false</code>). "
            "El resultado es un Contract A JSON sin ninguna suposición del modelo."
        ),
        "flow": [
            "Envías el requerimiento → el detector lo escanea (sin LLM, respuesta inmediata)",
            "Si hay ambigüedades: aparece el panel de revisión con una tarjeta por término",
            "Por cada ambigüedad eliges: <b>Aceptar sugerencia</b> · <b>Resolución personalizada</b> · <b>No es ambiguo</b>",
            "Clic en <b>Generar Historias →</b> · el LLM recibe tus decisiones como hechos",
            "Resultado: Contract A JSON con <code>assumption_made: false</code> en todas las ambigüedades",
        ],
        "output": "Contract A JSON · Pydantic validado · assumption_made: false garantizado",
        "when": "Cuando necesitas trazabilidad total: cada decisión de diseño queda documentada y firmada por el analista.",
        "examples": [
            "El sistema debe ser rápido y seguro para gestionar los usuarios del portal",
            "Se necesita un módulo para administrar el inventario de forma eficiente y escalable",
            "El usuario debe poder acceder a sus reportes periódicamente desde la plataforma",
            "Implementar autenticación robusta y confiable para varios tipos de usuario",
        ],
    },
    {
        "title": "Refinador con Detección de Ambigüedades",
        "version": "v3.0 · Ambiguity-Aware",
        "icon": "🏗",
        "color": "#7c3aed",
        "what": (
            "Agrega una etapa de análisis estático antes del LLM. El detector IEEE 830 "
            "escanea el requerimiento y genera una sección de contexto que se inyecta "
            "en el prompt, instruyendo al modelo a resolver cada término ambiguo con "
            "valores concretos. El LLM asume las resoluciones por sí mismo: más rápido "
            "que HITL, pero con <code>assumption_made: true</code> en los campos resueltos."
        ),
        "flow": [
            "Envías el requerimiento",
            "El detector genera una sección de ambigüedades (IEEE 830) e inyecta en el prompt",
            "El LLM resuelve cada ambigüedad y genera el Contract A JSON",
            "Resultado inmediato · sin intervención humana",
        ],
        "output": "Contract A JSON · Pydantic validado · LLM resuelve ambigüedades automáticamente",
        "when": "Para refinamientos rápidos donde la calidad importa pero no necesitas validación humana por cada término.",
        "examples": [
            "El sistema debe procesar pagos de forma segura y eficiente",
            "Crear un dashboard intuitivo para que los administradores gestionen métricas en tiempo real",
            "Se requiere un módulo de notificaciones confiable para varios canales de comunicación",
            "El sistema debe escalar automáticamente según la carga de usuarios",
        ],
    },
    {
        "title": "Constructor de Historias Estructuradas",
        "version": "v2.0 · JSON",
        "icon": "⚙",
        "color": "#059669",
        "what": (
            "Combina RAG con validación estricta de esquema. Recupera historias similares "
            "de la base de conocimiento ChromaDB (katary_stories), las inyecta como "
            "ejemplos de calidad en el prompt, y valida la respuesta del LLM con modelos "
            "Pydantic. Si el JSON es inválido o incompleto, reintenta automáticamente "
            "hasta 3 veces con los errores de validación como correcciones."
        ),
        "flow": [
            "Envías el requerimiento",
            "RAG: busca las <i>top_k</i> historias más similares en ChromaDB por embedding",
            "El LLM genera el Contract A con las historias de referencia como guía",
            "Pydantic valida el JSON · si falla, reintenta con los errores como feedback",
            "Resultado: Contract A validado con criterios de aceptación estructurados",
        ],
        "output": "Contract A JSON · Pydantic validado · given/when/then · test_data_examples",
        "when": "Cuando el requerimiento es claro y quieres historias bien estructuradas usando el conocimiento acumulado del equipo.",
        "examples": [
            "El cliente debe poder registrarse con email y contraseña",
            "El sistema debe generar reportes de ventas mensuales en formato PDF",
            "Implementar un carrito de compras con cálculo de impuestos automático",
            "El administrador debe poder asignar roles y permisos a los usuarios del sistema",
        ],
    },
    {
        "title": "Generador de Borradores RAG",
        "version": "v1.0 · RAG",
        "icon": "🛡",
        "color": "#d97706",
        "what": (
            "El agente más rápido y exploratorio. Solo hace RAG: recupera historias "
            "similares de ChromaDB y genera una respuesta en texto libre. "
            "No valida estructura, no detecta ambigüedades, no aplica Pydantic. "
            "Útil para explorar qué historias similares existen en la base de conocimiento "
            "o para obtener un primer borrador informal antes de usar un agente más riguroso."
        ),
        "flow": [
            "Envías el requerimiento",
            "RAG: busca las <i>top_k</i> historias más similares en ChromaDB",
            "El LLM genera texto libre usando esas referencias como contexto",
            "Sin validación de formato · respuesta directa",
        ],
        "output": "Texto libre · sin estructura JSON · ideal para borradores rápidos",
        "when": "Para exploración inicial, borradores informales, o cuando quieres ver qué hay en la base de conocimiento antes de refinar.",
        "examples": [
            "Login con redes sociales",
            "Sistema de gestión de inventario para tienda",
            "Módulo de reportes y analytics",
            "API de integración con sistemas externos",
        ],
    },
]


def render_docs() -> None:
    st.markdown(
        '<h2 style="color:#e2e8f0;margin-bottom:0.25rem;">📚 Documentación de Agentes</h2>'
        '<p style="color:#8b949e;font-size:0.9rem;margin-bottom:1.5rem;">'
        "Guía de uso y ejemplos para cada agente disponible en QualityAI.</p>",
        unsafe_allow_html=True,
    )
    for doc in _DOCS:
        _render_agent_card(doc)


def _render_agent_card(doc: dict) -> None:
    color = doc["color"]

    st.markdown(
        f'<div style="background:#161b22;border:1px solid #21262d;border-left:4px solid {color};'
        f'border-radius:8px;padding:1.2rem 1.4rem;margin-bottom:0.5rem;">'
        f'<div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.6rem;">'
        f'<span style="font-size:1.5rem;">{doc["icon"]}</span>'
        f'<div><div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;">{doc["title"]}</div>'
        f'<div style="font-size:0.75rem;color:{color};font-weight:600;letter-spacing:0.06em;">'
        f'{doc["version"]}</div></div></div>'
        f'<div style="color:#c9d1d9;font-size:0.88rem;line-height:1.6;">{doc["what"]}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    col_flow, col_right = st.columns([3, 2])

    with col_flow:
        steps_html = "".join(
            f'<div style="display:flex;gap:0.6rem;margin-bottom:0.5rem;">'
            f'<span style="color:{color};font-weight:700;flex-shrink:0;">{i}.</span>'
            f'<span style="color:#c9d1d9;font-size:0.84rem;">{step}</span>'
            f"</div>"
            for i, step in enumerate(doc["flow"], 1)
        )
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;'
            f'padding:1rem 1.1rem;">'
            f'<div style="font-size:0.7rem;color:#475569;letter-spacing:0.08em;margin-bottom:0.75rem;">'
            f"FLUJO DE EJECUCIÓN</div>{steps_html}</div>",
            unsafe_allow_html=True,
        )

    with col_right:
        examples_html = "".join(
            f'<div style="background:#161b22;border:1px solid #21262d;border-radius:4px;'
            f'padding:0.4rem 0.7rem;margin-bottom:0.4rem;font-size:0.8rem;'
            f'color:#8b949e;font-style:italic;">"{ex}"</div>'
            for ex in doc["examples"]
        )
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:1rem 1.1rem;">'
            f'<div style="font-size:0.7rem;color:#475569;letter-spacing:0.08em;margin-bottom:0.75rem;">'
            f"EJEMPLOS PARA PROBAR</div>{examples_html}"
            f'<div style="margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid #21262d;font-size:0.75rem;color:#475569;">'
            f'<b style="color:#8b949e;">Salida:</b> {doc["output"]}</div>'
            f'<div style="margin-top:0.4rem;font-size:0.75rem;color:#475569;">'
            f'<b style="color:#8b949e;">Cuándo usarlo:</b> {doc["when"]}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
