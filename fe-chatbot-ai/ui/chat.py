"""Componentes de la vista de chat."""

from datetime import datetime

import streamlit as st


def render_welcome() -> None:
    with st.chat_message("assistant", avatar="⚡"):
        st.markdown(f"**QualityAI · Módulo 3** · {datetime.now().strftime('%H:%M')}")
        st.markdown(
            "Pipeline de calidad listo. Describe tu requerimiento y generaré:\n\n"
            "- 📝 **Historias de Usuario** con criterios de aceptación (Contract A)\n"
            "- 🧪 **Casos de Test Gherkin** por historia (Contract B)\n"
            "- 📊 **Reporte ejecutivo** con cobertura ISO 25010 y riesgos (Contract C)\n\n"
            "El análisis puede tardar 1–3 minutos dependiendo del proveedor LLM."
        )


def render_input_bar() -> str | None:
    return st.chat_input(
        placeholder="Describe tu requerimiento para iniciar el pipeline…",
        disabled=st.session_state.get("is_running", False),
    )
