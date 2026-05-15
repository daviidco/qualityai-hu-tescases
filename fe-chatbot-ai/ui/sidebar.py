"""Barra lateral con lista de proyectos e historial."""

import streamlit as st
from datetime import datetime


def render_sidebar() -> None:
    with st.sidebar:
        # ── Marca ────────────────────────────────────────────────────────────
        st.markdown(
            '<div style="padding:1rem 0.5rem 1.5rem;">'
            '<div style="font-size:1.6rem;font-weight:800;color:#00bcd4;letter-spacing:0.05em;">'
            "QUALITYAI</div>"
            '<div style="font-size:0.7rem;color:#475569;letter-spacing:0.1em;margin-top:2px;">'
            "MÓDULO 3 · PIPELINE</div></div>"
            '<div style="font-size:0.7rem;color:#475569;letter-spacing:0.1em;padding:0 0.5rem 0.5rem;">'
            "PROYECTOS</div>",
            unsafe_allow_html=True,
        )

        # ── Botón nuevo análisis ──────────────────────────────────────────────
        if st.button("＋  Nuevo Análisis", key="new_analysis"):
            st.session_state.view = "chat"
            st.session_state.active_project = None
            st.session_state.messages = []
            st.session_state.rate_limit_error = None
            st.rerun()

        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

        # ── Lista de proyectos ────────────────────────────────────────────────
        projects: list[dict] = st.session_state.get("projects", [])
        if not projects:
            st.markdown(
                '<div style="font-size:0.8rem;color:#475569;padding:0.5rem;">'
                "Aún no hay proyectos.<br>Envía tu primer requerimiento.</div>",
                unsafe_allow_html=True,
            )
        else:
            for proj in projects:
                _project_button(proj)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        st.divider()

        # ── Info del pipeline ─────────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:0.72rem;color:#475569;padding:0.5rem 0.25rem;">'
            "Pipeline: HU · Test Cases · ISO 25010 · Riesgos</div>",
            unsafe_allow_html=True,
        )


def _project_button(proj: dict) -> None:
    is_active = st.session_state.active_project == proj["run_id"]
    css_class = "agent-btn-active" if is_active else ""
    summary = proj.get("summary", {})

    label = proj.get("req_preview", "Análisis")[:28]
    if len(proj.get("req_preview", "")) > 28:
        label += "…"

    ts_raw = proj.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%d/%m %H:%M")
    except Exception:
        ts = ts_raw[:16]

    meta = (
        f"{summary.get('total_stories', '?')} HU · "
        f"{summary.get('total_scenarios', '?')} tests · "
        f"{summary.get('coverage_pct', '?')}%"
    )

    with st.container():
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        if st.button(
            f"📋  {label}\n{ts} · {meta}",
            key=f"proj_{proj['run_id']}",
        ):
            st.session_state.active_project = proj["run_id"]
            st.session_state.view = "report"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
