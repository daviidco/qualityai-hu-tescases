"""QualityAI — Módulo 3 — Punto de entrada Streamlit."""

import streamlit as st

st.set_page_config(
    page_title="QualityAI — Módulo 3",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

import api
from config import BACKEND
from handlers import handle_analyze, handle_generate_tests, handle_finalize
from state import init_state
from ui.chat import render_input_bar, render_welcome
from ui.hitl_ambiguities import render_ambiguity_review
from ui.hitl_tests import render_test_review
from ui.js_utils import inject_history_nav, inject_sidebar_toggle
from ui.report_view import render_report_native
from ui.sidebar import render_sidebar
from ui.styles import inject_styles

inject_styles()
init_state()


def _load_history() -> None:
    """Carga proyectos del backend una vez por sesión."""
    if st.session_state.get("_history_loaded"):
        return
    data = api.get(f"{BACKEND}/pipeline/projects")
    if data and data.get("projects"):
        existing_ids = {p["run_id"] for p in st.session_state.projects}
        for proj in data["projects"]:
            if proj["run_id"] not in existing_ids:
                st.session_state.projects.append(proj)
        st.session_state.projects.sort(
            key=lambda p: p.get("timestamp", ""), reverse=True
        )
    st.session_state["_history_loaded"] = True


def _active_project() -> dict | None:
    run_id = st.session_state.active_project
    if not run_id:
        return None
    for proj in st.session_state.projects:
        if proj["run_id"] == run_id:
            return proj
    return None


def _ensure_full_project(proj: dict) -> dict:
    """Si el proyecto solo tiene metadata (cargado del historial), descarga el detalle."""
    if proj.get("report_data"):
        return proj
    full = api.get(f"{BACKEND}/pipeline/projects/{proj['run_id']}")
    if not full:
        return proj
    proj.update(full)
    for i, p in enumerate(st.session_state.projects):
        if p["run_id"] == proj["run_id"]:
            st.session_state.projects[i] = proj
            break
    return proj


def _header() -> None:
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.markdown(
            '<h2 style="color:#e2e8f0;margin-bottom:0;">QualityAI · Módulo 3</h2>',
            unsafe_allow_html=True,
        )
    view = st.session_state.view
    labels = {
        "chat":              ("⚡", "Listo"),
        "hitl_ambiguities":  ("🔍", "Revisión de Ambigüedades"),
        "hitl_tests":        ("🧪", "Revisión de Test Cases"),
        "report":            ("📊", "Reporte"),
    }
    icon, label = labels.get(view, ("⚡", "Listo"))
    with col_status:
        st.markdown(
            f'<div style="text-align:right;padding-top:.5rem;">'
            f'<span style="background:#0e3a4a;color:#00bcd4;padding:.25rem .75rem;'
            f'border-radius:20px;font-size:.8rem;border:1px solid #0e4f6b;">'
            f'<span class="status-dot"></span>{icon} {label}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)


def _rate_limit_banner() -> None:
    err = st.session_state.get("rate_limit_error")
    if not err:
        return
    retry_in = err.get("retry_in", "unos minutos")
    detail = err.get("detail", "")
    st.markdown(
        f'<div style="background:#431407;border:1px solid #f97316;border-radius:8px;'
        f'padding:.85rem 1.25rem;margin-bottom:1rem;display:flex;align-items:flex-start;gap:.75rem;">'
        f'<span style="font-size:1.4rem;line-height:1;">⏳</span>'
        f'<div>'
        f'<div style="color:#fed7aa;font-weight:700;font-size:1rem;margin-bottom:.25rem;">'
        f'Rate limit del proveedor LLM — espera {retry_in} y reintenta</div>'
        f'<div style="color:#fdba74;font-size:.9rem;">{detail}</div>'
        f'<div style="margin-top:.5rem;">'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )
    if st.button("✕  Cerrar aviso", key="_rl_dismiss"):
        st.session_state.rate_limit_error = None
        st.rerun()


def main() -> None:
    _load_history()
    render_sidebar()
    inject_sidebar_toggle()
    _header()
    _rate_limit_banner()

    view = st.session_state.view

    # ── Vista: reporte final ──────────────────────────────────────────────────
    if view == "report":
        proj = _active_project()
        if proj:
            proj = _ensure_full_project(proj)
        if proj and proj.get("report_data"):
            render_report_native(
                proj["report_data"],
                proj.get("html_content"),
                proj.get("pdf_base64", ""),
            )
        elif proj and proj.get("html_content"):
            import streamlit.components.v1 as components
            components.html(proj["html_content"], height=5200, scrolling=True)
        else:
            st.session_state.view = "chat"
            st.rerun()
        return

    # ── Vista: revisión de ambigüedades (HITL fase 1) ─────────────────────────
    if view == "hitl_ambiguities":
        render_ambiguity_review(on_submit=handle_generate_tests)
        return

    # ── Vista: revisión de test cases (HITL fase 2) ───────────────────────────
    if view == "hitl_tests":
        render_test_review(on_submit=handle_finalize)
        return

    # ── Vista: chat (bienvenida + input) ──────────────────────────────────────
    if not st.session_state.projects and not st.session_state.hitl_session_id:
        render_welcome()

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    prompt = render_input_bar()
    if prompt:
        handle_analyze(prompt.strip())

    inject_history_nav(st.session_state.input_history)

    st.markdown(
        '<div style="text-align:center;font-size:.7rem;color:#475569;padding-top:.5rem;">'
        '<span style="margin-right:1.5rem;">● SISTEMA SEGURO</span>'
        '<span style="margin-right:1.5rem;">● IA SINCRONIZADA</span>'
        '<span style="float:right;">v3.0 · PIPELINE UNIFICADO</span>'
        "</div>",
        unsafe_allow_html=True,
    )


main()
