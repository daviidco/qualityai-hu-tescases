"""Inicialización del session state de Streamlit."""

import streamlit as st


def init_state() -> None:
    defaults: dict = {
        # ── Proyectos e historial ─────────────────────────────────────────────
        "projects": [],          # [{run_id, timestamp, req_preview, summary, html_content}]
        "active_project": None,  # run_id del proyecto actualmente visualizado
        "input_history": [],     # historial de inputs para ↑↓

        # ── Vistas ───────────────────────────────────────────────────────────
        # "chat" | "hitl_ambiguities" | "hitl_tests" | "report"
        "view": "chat",

        # ── Estado HITL fase 1: ambigüedades ──────────────────────────────────
        "hitl_session_id": None,
        "hitl_requirement": "",
        "hitl_ambiguities": [],     # list de AmbiguityItem dicts del backend

        # ── Estado HITL fase 2: revisión de test cases ────────────────────────
        "hitl_features": [],        # list de FeatureOut dicts del backend
        "hitl_user_stories": [],    # list de UserStoryOut dicts del backend
        "hitl_total_scenarios": 0,
        # decisiones acumuladas: {"{feature_id}|{scenario_name}": {action, notes, new_iso}}
        "hitl_scenario_decisions": {},

        # ── Misc ──────────────────────────────────────────────────────────────
        "rate_limit_error": None,
        "is_running": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
