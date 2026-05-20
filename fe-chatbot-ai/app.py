"""QualityAI — Módulo 3 — Punto de entrada Streamlit."""

import base64
import json
import time as _time
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="QualityAI",
    layout="wide",
    initial_sidebar_state="expanded",
)

import api
from config import BACKEND
from handlers import handle_analyze, handle_finalize, handle_generate_tests
from state import init_state
from ui.admin_panel import render_admin_panel
from ui.analyst_panel import render_analyst_panel
from ui.hitl_ambiguities import render_ambiguity_review
from ui.hitl_tests import render_test_review
from ui.llm_config import render_llm_config
from ui.report_view import render_report_native
from ui.scrum_panel import render_scrum_panel
from ui.sidebar import render_sidebar
from ui.styles import inject_styles

inject_styles()
init_state()


# ── Session restore helpers ───────────────────────────────────────────────────

def _decode_jwt_claims(token: str) -> dict | None:
    """Decode JWT payload (no signature check); returns None if expired or malformed."""
    try:
        b64 = token.split(".")[1]
        b64 += "=" * (-len(b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(b64))
        if claims.get("exp", 0) > _time.time():
            return claims
    except Exception:
        pass
    return None


_ROLE_DEFAULT_VIEW = {
    "admin": "admin_users",
    "scrum_leader": "scrum_projects",
}


def _apply_sidebar_nav(lbl: str) -> None:
    """Apply a navigation label coming from the sidebar postMessage."""
    from ui.sidebar import _NAV
    role = st.session_state.get("user_role", "")
    for item in _NAV.get(role, []):
        if item["label"] == lbl:
            for k, v in item["extra"].items():
                st.session_state[k] = v
            st.session_state.view = item["view"]
            return
    # History project items: label is "R:{run_id[:8]}"
    for proj in st.session_state.get("projects", []):
        if lbl == f"R:{proj['run_id'][:8]}":
            st.session_state.active_project = proj["run_id"]
            st.session_state.view = "report"
            return

# ── Auth handler script (injected into parent head once per page load) ────────
_AUTH_HANDLER_JS = """<script>
(function(){
  var D=window.parent.document;
  if(D.getElementById('qa-auth-handler')) return;
  var s=D.createElement('script');s.id='qa-auth-handler';
  s.textContent=`
    window.addEventListener('message',function(e){
      var m=e.data;
      if(m&&m.type==='qa-store-auth'){
        try{localStorage.setItem('qa-auth',JSON.stringify(m.data));}catch(ex){}
        return;
      }
      if(m&&m.type==='qa-check-ls'){
        var d=null;
        try{d=JSON.parse(localStorage.getItem('qa-auth')||'null');}catch(ex){}
        var u=new URL(window.location.href);
        u.searchParams.set('_qt',d&&d.token?d.token:'_empty');
        window.location.replace(u.toString());
        return;
      }
      if(m&&m.type==='qa-navigate'){
        var u=new URL(window.location.href);
        u.searchParams.set('_nav',m.lbl);
        window.location.replace(u.toString());
        return;
      }
      if(m==='qa-do-logout'){
        try{localStorage.removeItem('qa-auth');}catch(ex){}
        window.location.replace('/login?logout=1');
      }
    });
  `;
  D.head.appendChild(s);
})();
</script>"""

_LS_CHECK_JS = """<script>
(function(){
  window.parent.postMessage({type:'qa-check-ls'},'*');
})();
</script>"""


def _handle_session_restore() -> bool:
    """
    Try to restore a session from localStorage via the _qt URL param.
    Also processes _nav when present so both resolve in a single rerun.
    Returns True when a redirect/stop has been issued and caller should not continue.
    """
    _qt = st.query_params.get("_qt", "")

    if _qt:
        # Capture _nav before clearing params so navigation survives the restore
        _nav = st.query_params.get("_nav", "")
        st.query_params.pop("_qt")
        if _nav:
            st.query_params.pop("_nav")

        if _qt != "_empty":
            claims = _decode_jwt_claims(_qt)
            if claims:
                st.session_state.token      = _qt
                st.session_state.user_email = claims.get("sub", "")
                st.session_state.user_role  = claims.get("role", "")
                st.session_state.user_name  = st.session_state.get("user_name", "")
                if _nav:
                    _apply_sidebar_nav(_nav)   # apply navigation in the same pass
                else:
                    st.session_state.view = _ROLE_DEFAULT_VIEW.get(
                        claims.get("role", ""), "analyst_projects"
                    )
                st.rerun()
        # Invalid token or _empty → fall through to login redirect
        st.switch_page("pages/login.py")
        st.stop()
        return True

    # No _qt param: directly read localStorage from iframe (same-origin)
    if not st.session_state.get("token"):
        components.html(_AUTH_HANDLER_JS + _LS_CHECK_JS, height=0, scrolling=False)
        st.markdown(
            '<div style="background:#0d1117;position:fixed;inset:0;z-index:99999;"></div>',
            unsafe_allow_html=True,
        )
        st.stop()
        return True

    return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_project() -> dict | None:
    run_id = st.session_state.active_project
    if not run_id:
        return None
    for proj in st.session_state.projects:
        if proj["run_id"] == run_id:
            return proj
    return None


def _ensure_full_project(proj: dict) -> dict:
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



def _rate_limit_banner() -> None:
    err = st.session_state.get("rate_limit_error")
    if not err:
        return
    retry_in = err.get("retry_in", "unos minutos")
    detail = err.get("detail", "")
    st.markdown(
        f'<div style="background:#431407;border:1px solid #f97316;border-radius:8px;'
        f'padding:.85rem 1.25rem;margin-bottom:1rem;">'
        f'<div style="color:#fed7aa;font-weight:700;font-size:1rem;margin-bottom:.25rem;">'
        f'Rate limit — espera {retry_in} y reintenta</div>'
        f'<div style="color:#fdba74;font-size:.9rem;">{detail}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("Cerrar aviso", key="_rl_dismiss"):
        st.session_state.rate_limit_error = None
        st.rerun()


# ── Enrutador principal ───────────────────────────────────────────────────────

def main() -> None:
    # ── Auth guard: restore from localStorage or redirect to login ────────────
    if not st.session_state.get("token"):
        _handle_session_restore()
        return

    # ── Sidebar navigation via postMessage → URL param ────────────────────────
    _nav_lbl = st.query_params.get("_nav", "")
    if _nav_lbl:
        st.query_params.pop("_nav")
        _apply_sidebar_nav(_nav_lbl)
        st.rerun()

    # ── JS-initiated team member add (custom multiselect → query params) ──────
    _t_add  = st.query_params.get("_team_add", "")
    _t_proj = st.query_params.get("_team_proj", "")
    if _t_add and _t_proj:
        st.query_params.pop("_team_add")
        st.query_params.pop("_team_proj")
        for _em in _t_add.split(","):
            _em = _em.strip()
            if _em:
                api.post(
                    f"{BACKEND}/projects/{_t_proj}/assign-analyst",
                    {"analyst_email": _em},
                    suppress_codes=(400, 409),
                )
        st.session_state.pop("_sp_user_map", None)
        st.rerun()
        return

    # ── JS-initiated team member remove (✕ inside card → query params) ───────
    _t_rm   = st.query_params.get("_team_rm", "")
    _t_rproj = st.query_params.get("_team_proj", "")
    if _t_rm and _t_rproj:
        st.query_params.pop("_team_rm")
        st.query_params.pop("_team_proj")
        api.delete(f"{BACKEND}/projects/{_t_rproj}/team/{_t_rm}")
        st.session_state.pop("_sp_user_map", None)
        st.rerun()
        return

    # ── LLM provider drag-and-drop order (JS sets _llm_order param) ─────────
    _llm_order = st.query_params.get("_llm_order", "")
    if _llm_order:
        st.query_params.pop("_llm_order")
        new_order = [p.strip() for p in _llm_order.split(",") if p.strip()]
        if new_order:
            st.session_state["llm_order"] = new_order
        st.rerun()
        return

    # ── Project name click → detail view (JS sets _sel_proj param) ───────────
    _sel_proj = st.query_params.get("_sel_proj", "")
    if _sel_proj:
        st.query_params.pop("_sel_proj")
        st.session_state.scrum_selected_project = _sel_proj
        st.session_state.view = "scrum_projects"
        st.rerun()
        return

    view = st.session_state.get("view", "")

    # ── Vistas autenticadas ───────────────────────────────────────────────────
    render_sidebar()

    _rate_limit_banner()

    role = st.session_state.get("user_role", "")

    # ── Admin: gestión de usuarios ────────────────────────────────────────────
    if view == "admin_users":
        render_admin_panel()
        return

    # ── Admin: configuración LLM ──────────────────────────────────────────────
    if view == "llm_config":
        render_llm_config()
        return

    # ── Scrum Leader: proyectos ───────────────────────────────────────────────
    if view == "scrum_projects":
        render_scrum_panel()
        return

    # ── Analista: proyectos asignados ─────────────────────────────────────────
    if view == "analyst_projects":
        render_analyst_panel()
        return

    # ── HITL: revisión de ambigüedades ────────────────────────────────────────
    if view == "hitl_ambiguities":
        render_ambiguity_review(on_submit=handle_generate_tests)
        return

    # ── HITL: revisión de test cases ──────────────────────────────────────────
    if view == "hitl_tests":
        render_test_review(on_submit=handle_finalize)
        return

    # ── Reporte ejecutivo ─────────────────────────────────────────────────────
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
            # No hay datos: volver a la vista principal del rol
            _redirect_to_home(role)
        return

    # ── Análisis libre (admin / cualquier rol con acceso) ─────────────────────
    if view == "chat":
        from ui.chat import render_file_uploader, render_input_bar, render_welcome
        from ui.js_utils import inject_history_nav

        # Auto-analyze iniciado desde el panel Scrum (requerimiento pre-seleccionado)
        _auto_req = st.session_state.pop("_auto_analyze", None)
        if _auto_req:
            handle_analyze(_auto_req)
            return

        if not st.session_state.projects and not st.session_state.hitl_session_id:
            render_welcome()

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        file_req = render_file_uploader()
        if file_req:
            handle_analyze(file_req)
            return

        prompt = render_input_bar()
        if prompt:
            handle_analyze(prompt.strip())

        inject_history_nav(st.session_state.input_history)
        return

    # ── Fallback: redirigir según rol ─────────────────────────────────────────
    _redirect_to_home(role)


def _redirect_to_home(role: str) -> None:
    if role == "admin":
        st.session_state.view = "admin_users"
    elif role == "scrum_leader":
        st.session_state.view = "scrum_projects"
    else:
        st.session_state.view = "analyst_projects"
    st.rerun()


main()
