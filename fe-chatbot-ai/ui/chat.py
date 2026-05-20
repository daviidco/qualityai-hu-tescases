"""Componentes de la vista de chat."""

from datetime import datetime

import streamlit as st


def render_welcome() -> None:
    with st.chat_message("assistant"):
        st.markdown(f"**QualityAI** · {datetime.now().strftime('%H:%M')}")
        st.markdown(
            "Pipeline de calidad listo. Describe tu requerimiento y generaré:\n\n"
            "- **Historias de Usuario** con criterios de aceptación (Contract A)\n"
            "- **Casos de Test Gherkin** por historia (Contract B)\n"
            "- **Reporte ejecutivo** con cobertura ISO 25010 y riesgos (Contract C)\n\n"
            "El análisis puede tardar 1–3 minutos dependiendo del proveedor LLM."
        )


def render_file_uploader() -> str | None:
    """Área de carga de archivo. Devuelve el texto extraído cuando el usuario confirma."""
    is_running = st.session_state.get("is_running", False)

    with st.expander("Cargar requerimiento desde archivo  (.txt · .pdf · .docx)", expanded=False):
        uploaded = st.file_uploader(
            "archivo",
            type=["txt", "pdf", "docx"],
            accept_multiple_files=False,
            label_visibility="collapsed",
            disabled=is_running,
        )

        if uploaded is None:
            st.markdown(
                '<div style="font-size:.85rem;color:#64748b;text-align:center;padding:.5rem 0;">'
                'Arrastra un archivo aquí o haz clic en "Browse files"</div>',
                unsafe_allow_html=True,
            )
            return None

        # Extracción de texto
        try:
            from file_reader import extract_text
            text = extract_text(uploaded.getvalue(), uploaded.name)
        except ValueError as exc:
            st.error(str(exc))
            return None
        except Exception as exc:
            st.error(f"Error inesperado al leer el archivo: {exc}")
            return None

        if not text.strip():
            st.warning("El archivo no contiene texto extraíble.")
            return None

        # Métricas del archivo
        col_name, col_chars, col_words = st.columns(3)
        with col_name:
            st.metric("Archivo", uploaded.name[:24] + ("…" if len(uploaded.name) > 24 else ""))
        with col_chars:
            st.metric("Caracteres", f"{len(text):,}")
        with col_words:
            st.metric("Palabras aprox.", f"{len(text.split()):,}")

        # Vista previa del texto extraído
        preview = text[:600] + ("…" if len(text) > 600 else "")
        st.text_area(
            "Vista previa del texto extraído",
            value=preview,
            height=130,
            disabled=True,
        )

        if st.button(
            "Analizar requerimiento del archivo →",
            type="primary",
            use_container_width=True,
            disabled=is_running,
            key="btn_analyze_file",
        ):
            return text.strip()

    return None


def render_input_bar() -> str | None:
    return st.chat_input(
        placeholder="Describe tu requerimiento para iniciar el pipeline…",
        disabled=st.session_state.get("is_running", False),
    )
