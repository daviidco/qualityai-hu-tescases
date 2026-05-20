"""Handlers del flujo HITL de 3 fases para el pipeline de Módulo 3."""
from __future__ import annotations

import threading
import time
from datetime import datetime

import httpx
import streamlit as st

import api
from config import BACKEND

# Module-level store for background generation threads.
# Key: hitl_session_id.  Value: dict with running/result/error/cancelled/start_time.
# Written from background threads, read from Streamlit thread — safe under CPython GIL
# for simple dict key assignments.
_GEN_STORE: dict[str, dict] = {}


def handle_analyze(requirement: str) -> None:
    """Fase 1-a: detecta ambigüedades y transiciona a la vista correspondiente."""
    st.session_state.rate_limit_error = None
    st.session_state.is_running = True
    _record_history(requirement)

    if "_prev_view" not in st.session_state:
        st.session_state["_prev_view"] = st.session_state.get("view", "chat")

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
        handle_generate_tests([])
        return

    st.rerun()


def handle_generate_tests(resolutions: list[dict]) -> None:
    """Fase 1-b + 2: genera HU con las resoluciones y luego los test cases.

    Runs the API call in a background thread and shows a cancellable modal dialog
    while waiting. Session navigation happens inside the dialog once the result arrives.
    """
    session_id = st.session_state.hitl_session_id

    if session_id not in _GEN_STORE:
        store: dict = {
            "running": True,
            "result": None,
            "error": None,
            "cancelled": False,
            "start_time": time.time(),
        }
        _GEN_STORE[session_id] = store

        # Capture auth token before spawning the thread (session_state is not
        # safe to read from background threads in Streamlit).
        _token = st.session_state.get("token")
        _headers = {"Authorization": f"Bearer {_token}"} if _token else {}

        def _worker() -> None:
            try:
                r = httpx.post(
                    f"{BACKEND}/pipeline/generate-tests",
                    json={"session_id": session_id, "resolutions": resolutions},
                    headers=_headers,
                    timeout=300,
                )
                r.raise_for_status()
                store["result"] = r.json()
            except Exception as exc:  # noqa: BLE001
                store["error"] = str(exc)
            finally:
                store["running"] = False

        threading.Thread(target=_worker, daemon=True).start()
        st.session_state["_gen_key"] = session_id

    _gen_progress_dialog(session_id)


_PROVIDER_LABELS: dict[str, str] = {
    "gemini":   "Google Gemini",
    "groq":     "Groq",
    "cerebras": "Cerebras",
    "deepseek": "DeepSeek",
}
_PROVIDER_COLORS: dict[str, str] = {
    "gemini":   "#4285F4",
    "groq":     "#F5A623",
    "cerebras": "#9B59B6",
    "deepseek": "#00bfa5",
}


@st.dialog("Generando análisis", width="small")
def _gen_progress_dialog(key: str) -> None:
    """Cancellable progress dialog for the generate-tests background call."""
    store = _GEN_STORE.get(key)
    if store is None:
        st.session_state.pop("_gen_key", None)
        st.rerun()
        return

    elapsed = int(time.time() - store.get("start_time", time.time()))
    mins, secs = divmod(elapsed, 60)

    if store.get("running"):
        # ── Fetch current LLM state from backend ─────────────────────────────
        status = api.get(f"{BACKEND}/pipeline/status") or {}
        current_label: str = status.get("current_label", "—")
        chain_meta: list[dict] = status.get("chain_meta", [])
        skip_count: int = status.get("skip_count", 0)

        # Derive provider name + model from chain_meta
        current_meta = next(
            (m for m in chain_meta if m.get("label") == current_label), {}
        )
        pname = current_meta.get("provider", current_label.split("[")[0] if "[" in current_label else current_label)
        model = current_meta.get("model", "")
        display_name = _PROVIDER_LABELS.get(pname, pname.capitalize())
        dot_color = _PROVIDER_COLORS.get(pname, "#8b949e")

        # ── Spinner + title ───────────────────────────────────────────────────
        st.markdown(
            '<style>@keyframes qa-spin{to{transform:rotate(360deg);}}'
            '#qa-gen-ring{width:40px;height:40px;border:3px solid #21262d;'
            'border-top:3px solid #00bcd4;border-radius:50%;'
            'animation:qa-spin 1s linear infinite;margin:1rem auto .9rem;}</style>'
            '<div id="qa-gen-ring"></div>'
            '<div style="text-align:center;">'
            '<div style="font-weight:700;color:#e2e8f0;font-size:.97rem;margin-bottom:.35rem;">'
            'Generando Historias de Usuario y Test Cases</div>'
            '<div style="color:#6b7280;font-size:.83rem;margin-bottom:.7rem;">'
            'El pipeline de IA está procesando el requerimiento.<br>'
            'Este proceso puede tardar entre 1 y 3 minutos.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Active provider badge ─────────────────────────────────────────────
        model_str = f' · <span style="color:#9ca3af;">{model}</span>' if model else ""
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:.5rem;'
            f'background:#0d1117;border:1px solid #21262d;border-radius:8px;'
            f'padding:.45rem .75rem;margin-bottom:.5rem;">'
            f'<span style="width:8px;height:8px;border-radius:50%;'
            f'background:{dot_color};flex-shrink:0;"></span>'
            f'<span style="color:#e2e8f0;font-size:.85rem;font-weight:600;flex:1;">'
            f'{display_name}{model_str}</span>'
            f'<span style="font-size:.68rem;color:#4b5563;">{current_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Chain visualization (if multiple providers) ───────────────────────
        if len(chain_meta) > 1:
            chips = []
            for i, meta in enumerate(chain_meta):
                is_active = meta.get("label") == current_label
                bg = "#0e3a4a" if is_active else "#0d1117"
                border = "#0891b2" if is_active else "#21262d"
                txt_color = "#00bcd4" if is_active else "#4b5563"
                p = meta.get("provider", "?")
                dot = _PROVIDER_COLORS.get(p, "#555")
                chips.append(
                    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
                    f'background:{bg};border:1px solid {border};border-radius:6px;'
                    f'padding:.18rem .45rem;font-size:.72rem;color:{txt_color};">'
                    f'<span style="width:6px;height:6px;border-radius:50%;background:{dot};"></span>'
                    f'{_PROVIDER_LABELS.get(p, p.capitalize())}'
                    f'</span>'
                )
            arrow = '<span style="color:#374151;font-size:.7rem;"> → </span>'
            st.markdown(
                f'<div style="text-align:center;margin-bottom:.55rem;">'
                + arrow.join(chips)
                + '</div>',
                unsafe_allow_html=True,
            )

        # ── Timer ─────────────────────────────────────────────────────────────
        st.markdown(
            f'<div style="text-align:center;color:#00bcd4;font-size:.88rem;'
            f'font-weight:600;margin-bottom:.9rem;">⏱ {mins:02d}:{secs:02d} transcurridos</div>',
            unsafe_allow_html=True,
        )

        # ── Action buttons ────────────────────────────────────────────────────
        if st.button("⏹ Detener", use_container_width=True, key="gen_stop_btn"):
                store["cancelled"] = True
                store["running"] = False
                _GEN_STORE.pop(key, None)
                st.session_state.pop("_gen_key", None)
                st.session_state.is_running = False
                st.session_state.view = st.session_state.pop("_prev_view", "chat")
                st.rerun()

        # Poll every 2 seconds
        time.sleep(2)
        st.rerun()
        return

    # Thread finished — process result
    result = store.get("result")
    error = store.get("error")
    cancelled = store.get("cancelled", False)
    _GEN_STORE.pop(key, None)
    st.session_state.pop("_gen_key", None)

    if cancelled:
        st.session_state.is_running = False
        st.session_state.view = st.session_state.pop("_prev_view", "chat")
        st.rerun()
        return

    if error:
        st.session_state.is_running = False
        st.error(f"Error al generar: {error}")
        return

    if result is None:
        st.session_state.is_running = False
        st.error(
            "No se recibió respuesta del backend. "
            "Verifica que el servidor esté activo y vuelve a intentarlo."
        )
        return

    st.session_state.hitl_features = result["features"]
    st.session_state.hitl_user_stories = result.get("user_stories", [])
    st.session_state.hitl_total_scenarios = result["total_scenarios"]
    st.session_state.hitl_scenario_decisions = {}
    st.session_state.view = "hitl_tests"
    st.session_state.is_running = False
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

    payload: dict = {
        "session_id": st.session_state.hitl_session_id,
        "reviewer_name": reviewer_name,
        "global_decision": global_decision,
        "analyst_feedback": analyst_feedback,
        "scenario_decisions": scenario_decisions,
    }
    draft_id = st.session_state.get("current_project_draft_id")
    if draft_id:
        payload["project_draft_id"] = draft_id
    req_id = st.session_state.get("current_req_id")
    if req_id:
        payload["req_id"] = req_id

    with st.spinner("Generando reporte ejecutivo final…"):
        data = api.post(f"{BACKEND}/pipeline/finalize", payload, timeout=120)

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

    st.session_state.hitl_session_id = None
    st.session_state.hitl_requirement = ""
    st.session_state.hitl_ambiguities = []
    st.session_state.hitl_features = []
    st.session_state.hitl_user_stories = []
    st.session_state.hitl_scenario_decisions = {}
    st.session_state.current_project_draft_id = None
    st.session_state.current_project_name = ""
    st.session_state.current_req_id = None

    prev_view = st.session_state.pop("_prev_view", None)

    if draft_id:
        # Pre-select the analyzed requirement so the detail opens on it
        if req_id:
            st.session_state[f"_sel_req_{draft_id}"] = req_id
        # Clear any stale refinement cache so the new refinement loads fresh
        for _k in list(st.session_state.keys()):
            if _k.startswith("_ref_cache_"):
                del st.session_state[_k]

        if prev_view == "scrum_projects":
            st.session_state.scrum_selected_project = draft_id
            st.session_state.view = "scrum_projects"
        else:
            st.session_state.analyst_selected_project = draft_id
            st.session_state.view = "analyst_projects"
    else:
        st.session_state.analyst_selected_project = None
        st.session_state.view = "report"
    st.rerun()


def _record_history(requirement: str) -> None:
    hist = st.session_state.input_history
    if not hist or hist[0] != requirement:
        hist.insert(0, requirement)
        if len(hist) > 50:
            st.session_state.input_history = hist[:50]
