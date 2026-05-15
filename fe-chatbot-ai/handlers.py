"""Handlers del flujo HITL de 3 fases para el pipeline de Módulo 3."""

from datetime import datetime

import streamlit as st

import api
from config import BACKEND


def handle_analyze(requirement: str) -> None:
    """Fase 1-a: detecta ambigüedades y transiciona a la vista correspondiente."""
    st.session_state.rate_limit_error = None
    st.session_state.is_running = True
    _record_history(requirement)

    with st.spinner("Analizando ambigüedades en el requerimiento…"):
        data = api.post(f"{BACKEND}/pipeline/analyze", {"requirement": requirement}, timeout=60)

    st.session_state.is_running = False
    if data is None:
        return

    st.session_state.hitl_session_id = data["session_id"]
    st.session_state.hitl_requirement = requirement
    st.session_state.hitl_ambiguities = data["ambiguities"]
    st.session_state.hitl_scenario_decisions = {}

    if data["has_ambiguities"]:
        st.session_state.view = "hitl_ambiguities"
    else:
        # Sin ambigüedades: saltamos directamente a generar tests
        handle_generate_tests([])
        return

    st.rerun()


def handle_generate_tests(resolutions: list[dict]) -> None:
    """Fase 1-b + 2: genera HU con las resoluciones y luego los test cases."""
    st.session_state.is_running = True

    with st.spinner("Generando Historias de Usuario y Test Cases… (puede tardar 1-3 min)"):
        data = api.post(
            f"{BACKEND}/pipeline/generate-tests",
            {
                "session_id": st.session_state.hitl_session_id,
                "resolutions": resolutions,
            },
            timeout=300,
        )

    st.session_state.is_running = False
    if data is None:
        return

    st.session_state.hitl_features = data["features"]
    st.session_state.hitl_user_stories = data.get("user_stories", [])
    st.session_state.hitl_total_scenarios = data["total_scenarios"]
    st.session_state.hitl_scenario_decisions = {}
    st.session_state.view = "hitl_tests"
    st.rerun()


def handle_finalize(
    reviewer_name: str,
    global_decision: str,
    analyst_feedback: str,
) -> None:
    """Fase 3: envía decisiones de revisión y genera el reporte final."""
    st.session_state.is_running = True

    raw_decisions = st.session_state.hitl_scenario_decisions
    scenario_decisions = []
    for key, dec in raw_decisions.items():
        feature_id, scenario_name = key.split("|", 1)
        scenario_decisions.append({
            "feature_id": feature_id,
            "scenario_name": scenario_name,
            "action": dec.get("action", "accepted"),
            "notes": dec.get("notes", ""),
            "new_iso": dec.get("new_iso"),
        })

    with st.spinner("Generando reporte ejecutivo final…"):
        data = api.post(
            f"{BACKEND}/pipeline/finalize",
            {
                "session_id": st.session_state.hitl_session_id,
                "reviewer_name": reviewer_name,
                "global_decision": global_decision,
                "analyst_feedback": analyst_feedback,
                "scenario_decisions": scenario_decisions,
            },
            timeout=120,
        )

    st.session_state.is_running = False
    if data is None:
        return

    run_id = data["pipeline_run_id"]
    proj = {
        "run_id": run_id,
        "timestamp": data["summary"]["created_at"],
        "req_preview": st.session_state.hitl_requirement,
        "summary": data["summary"],
        "html_content": data["html_content"],
        "report_data": data.get("report_data"),
        "pdf_base64": data.get("pdf_base64", ""),
    }
    projects: list = st.session_state.projects
    projects.insert(0, proj)
    st.session_state.projects = projects
    st.session_state.active_project = run_id

    # Limpiar estado HITL
    st.session_state.hitl_session_id = None
    st.session_state.hitl_requirement = ""
    st.session_state.hitl_ambiguities = []
    st.session_state.hitl_features = []
    st.session_state.hitl_user_stories = []
    st.session_state.hitl_scenario_decisions = {}
    st.session_state.view = "report"
    st.rerun()


def _record_history(requirement: str) -> None:
    hist = st.session_state.input_history
    if not hist or hist[0] != requirement:
        hist.insert(0, requirement)
        if len(hist) > 50:
            st.session_state.input_history = hist[:50]
