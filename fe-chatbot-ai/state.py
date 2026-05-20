"""Inicialización del session state de Streamlit."""

import streamlit as st


def init_state() -> None:
    defaults: dict = {
        # ── Auth ─────────────────────────────────────────────────────────────
        "token": None,
        "user_email": None,
        "user_role": None,

        # ── Proyectos e historial ─────────────────────────────────────────────
        "projects": [],          # [{run_id, timestamp, req_preview, summary, ...}]
        "active_project": None,  # run_id del proyecto actualmente visualizado
        "input_history": [],     # historial de inputs para ↑↓

        # ── Vista activa ──────────────────────────────────────────────────────
        # "login" | "admin_users" | "scrum_projects" | "analyst_projects"
        # | "chat" | "hitl_ambiguities" | "hitl_tests" | "report"
        "view": "login",

        # ── Sub-vistas de paneles ─────────────────────────────────────────────
        "scrum_selected_project": None,  # run_id del proyecto seleccionado
        "scrum_show_create": False,
        "analyst_selected_project": None,

        # ── Contexto de proyecto activo (analista iniciando pipeline) ─────────
        "current_project_draft_id": None,
        "current_project_name": "",
        "current_req_id": None,

        # ── Estado HITL fase 1: ambigüedades ──────────────────────────────────
        "hitl_session_id": None,
        "hitl_requirement": "",
        "hitl_ambiguities": [],

        # ── Estado HITL fase 2: revisión de test cases ────────────────────────
        "hitl_features": [],
        "hitl_user_stories": [],
        "hitl_total_scenarios": 0,
        "hitl_scenario_decisions": {},

        # ── Misc ──────────────────────────────────────────────────────────────
        "rate_limit_error": None,
        "is_running": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
