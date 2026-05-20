"""Panel del Scrum Leader: proyectos, asignaciones y exportación Jira."""
from __future__ import annotations

import base64
import io
import re
import threading
import time

import httpx
import streamlit as st
import streamlit.components.v1 as components

import api
from config import BACKEND
from ui.icons import icon

# Module-level store for background code-generation threads.
# Key: store_key.  Value: dict with running/result/error/cancelled/start_time.
_CODE_GEN_STORE: dict[str, dict] = {}

# Module-level store for background Jira export threads.
_JIRA_STORE: dict[str, dict] = {}

_JIRA_STEPS = [
    "🔌 Conectando con Jira…",
    "📁 Creando proyecto…",
    "📋 Creando Epic…",
    "📝 Creando historias…",
    "🏷 Creando sub-tareas…",
    "✅ Finalizando…",
]

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

_B = 'padding:.15rem .6rem;border-radius:10px;font-size:.82rem;'
_STATUS_BADGE = {
    "created":   f'<span style="background:#1e3a5f;color:#93c5fd;{_B}">{icon("clock",12,"#93c5fd")} Sin analizar</span>',
    "analyzing": f'<span style="background:#1c3a2a;color:#6ee7b7;{_B}">{icon("rocket",12,"#6ee7b7")} Analizando</span>',
    "completed": f'<span style="background:#14532d;color:#86efac;{_B}">{icon("check-circle",12,"#86efac")} Completado</span>',
}
_BR = 'padding:.1rem .5rem;border-radius:10px;font-size:.72rem;'
_REVIEW_BADGE = {
    "pending_review": f'<span style="background:#422006;color:#fed7aa;{_BR}">{icon("clock",11,"#fed7aa")} Pendiente revisión</span>',
    "approved":       f'<span style="background:#14532d;color:#86efac;{_BR}">{icon("check-circle",11,"#86efac")} Aprobado</span>',
    "rejected":       f'<span style="background:#450a0a;color:#fca5a5;{_BR}">{icon("x-circle",11,"#fca5a5")} Rechazado</span>',
    "needs_changes":  f'<span style="background:#3b2007;color:#fcd34d;{_BR}">{icon("warning",11,"#fcd34d")} Requiere cambios</span>',
}


# ── Toast (same pattern as admin_panel) ──────────────────────────────────────

def _show_toast(msg: str, kind: str = "success") -> None:
    if kind == "success":
        bg, border, clr = "#052e16", "#166534", "#4ade80"
        icon_path = "M20 6 9 17l-5-5"
        title = "Operación exitosa"
    else:
        bg, border, clr = "#450a0a", "#991b1b", "#f87171"
        icon_path = "M18 6 6 18M6 6l12 12"
        title = "Error"

    msg_esc = msg.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    js = f"""<script>
(function(){{
  var W=window.parent,D=W.document,B=D.body;
  if(!D.getElementById('qa-tn-css')){{
    var s=D.createElement('style');s.id='qa-tn-css';
    s.textContent=`
      #qa-tn{{position:fixed;top:1.25rem;right:1.25rem;z-index:99999;width:340px;
        transform:translateX(calc(100% + 2rem));opacity:0;
        transition:transform .35s cubic-bezier(.34,1.2,.64,1),opacity .25s;}}
      #qa-tn.qa-tn-in{{transform:none;opacity:1;}}
      .qa-tn-card{{border-radius:12px;padding:.9rem 1rem;
        display:flex;align-items:flex-start;gap:.75rem;
        box-shadow:0 8px 32px rgba(0,0,0,.55);}}
      .qa-tn-body{{flex:1;min-width:0;}}
      .qa-tn-title{{font-weight:700;font-size:.9rem;font-family:sans-serif;margin-bottom:.2rem;}}
      .qa-tn-msg{{font-size:.82rem;font-family:sans-serif;line-height:1.45;color:#d1d5db;}}
      .qa-tn-close{{flex-shrink:0;background:none;border:none;cursor:pointer;padding:2px;
        opacity:.55;transition:opacity .15s;line-height:0;}}
      .qa-tn-close:hover{{opacity:1;}}
    `;D.head.appendChild(s);
  }}
  var t=D.getElementById('qa-tn');
  if(!t){{t=D.createElement('div');t.id='qa-tn';B.appendChild(t);}}
  t.innerHTML=
    '<div class="qa-tn-card" style="background:{bg};border:1px solid {border}">'
    +'<div style="flex-shrink:0;margin-top:2px">'
    +'<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
    +' stroke="{clr}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    +'<path d="{icon_path}"/></svg></div>'
    +'<div class="qa-tn-body">'
    +'<div class="qa-tn-title" style="color:{clr}">{title}</div>'
    +'<div class="qa-tn-msg">{msg_esc}</div>'
    +'</div>'
    +'<button class="qa-tn-close"'
    +' onclick="W.clearTimeout(W.__qaTnTid);D.getElementById(\\\'qa-tn\\\').classList.remove(\\\'qa-tn-in\\\')">'
    +'<svg width="14" height="14" viewBox="0 0 24 24" fill="none"'
    +' stroke="#9ca3af" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>'
    +'</button>'
    +'</div>';
  W.requestAnimationFrame(function(){{
    t.classList.add('qa-tn-in');
    W.clearTimeout(W.__qaTnTid);
    W.__qaTnTid=W.setTimeout(function(){{t.classList.remove('qa-tn-in');}},4500);
  }});
}})();
</script>"""
    components.html(js, height=0, scrolling=False)


# ── Entry point ───────────────────────────────────────────────────────────────

_GEN_CODE_CSS = (
    '<style>'
    '[class*="st-key-gen_code_"] button:not([disabled]){'
    'background:#7c3aed!important;border-color:#7c3aed!important;color:#fff!important;}'
    '[class*="st-key-gen_code_"] button:not([disabled]):hover{'
    'background:#6d28d9!important;border-color:#6d28d9!important;}'
    '[class*="st-key-gen_code_"] button[disabled]{'
    'background:transparent!important;border-color:#374151!important;color:#6b7280!important;opacity:.5!important;}'
    '[class*="st-key-hero_add_"] button{'
    'background:#2563eb!important;color:#fff!important;border:1px solid #2563eb!important;'
    'font-size:.78rem!important;padding:.15rem .4rem!important;line-height:1.3!important;'
    'min-height:unset!important;height:auto!important;}'
    '[class*="st-key-hero_edit_"] button{'
    'background:#d97706!important;color:#fff!important;border:1px solid #d97706!important;'
    'font-size:.78rem!important;padding:.15rem .4rem!important;line-height:1.3!important;'
    'min-height:unset!important;height:auto!important;}'
    '[class*="st-key-hero_del_"] button{'
    'background:#dc2626!important;color:#fff!important;border:1px solid #dc2626!important;'
    'font-size:.72rem!important;padding:.1rem .35rem!important;line-height:1.2!important;'
    'min-height:unset!important;height:auto!important;}'
    '.stHorizontalBlock:has([class*="st-key-hero_add_"]){'
    'flex-wrap:nowrap!important;justify-content:flex-end!important;gap:6px!important;}'
    '.stHorizontalBlock:has([class*="st-key-hero_add_"])>.stColumn{'
    'flex:none!important;width:auto!important;}'
    '.stHorizontalBlock:has([class*="st-key-hero_add_"])>.stColumn:first-child{'
    'flex:1!important;width:auto!important;}'
    '</style>'
)


def render_scrum_panel() -> None:
    st.markdown(_GEN_CODE_CSS, unsafe_allow_html=True)
    if st.session_state.get("scrum_selected_project"):
        _render_project_detail(st.session_state.scrum_selected_project)
        return

    # ── Pending toast ─────────────────────────────────────────────────────────
    if "_scrum_toast" in st.session_state:
        info = st.session_state.pop("_scrum_toast")
        _show_toast(info["msg"], info.get("kind", "success"))

    # ── Stretch list + wire project and delete clicks ────────────────────────
    components.html("""<script>
(function(){
  var D=window.parent.document,W=window.parent;

  function resize(){
    var els=D.querySelectorAll(
      '[data-testid="stVerticalBlockBorderWrapper"] > div, [data-testid="stVerticalBlock"] > div'
    );
    for(var i=0;i<els.length;i++){
      var cs=W.getComputedStyle(els[i]);
      var oy=cs.overflowY||'',ox=cs.overflow||'';
      if(oy==='auto'||oy==='scroll'||ox==='auto'||ox==='scroll'){
        els[i].style.height=(W.innerHeight-220)+'px';
        els[i].style.overflowY='auto';
      }
    }
  }

  setTimeout(function(){resize();},400);
  W.addEventListener('resize',resize);
  D.querySelectorAll('[data-sel-proj]').forEach(function(el){el.remove();});
})();
</script>""", height=0, scrolling=False)

    col_list, col_create = st.columns([3, 2], gap="large")

    with col_list:
        st.markdown(
            '<div style="color:#e2e8f0;font-size:1.05rem;font-weight:600;'
            'margin-bottom:.75rem;font-family:sans-serif;">Proyectos</div>',
            unsafe_allow_html=True,
        )
        _render_project_list()

    with col_create:
        with st.container(border=True, height=850):
            _render_create_form()


# ── Lista de proyectos ────────────────────────────────────────────────────────

_LIST_CARD_CSS = (
    '<style>'
    'a.qa-pname{color:#e2e8f0;font-weight:600;font-size:1.02rem;text-decoration:underline;'
    'text-underline-offset:3px;text-decoration-color:#334155;display:inline-block;line-height:1.3;}'
    'a.qa-pname:hover{text-decoration-color:#60a5fa;}'
    # Analizar buttons: green when enabled
    '[class*="st-key-analyze_"] button:not([disabled]){'
    'background:#16a34a!important;border-color:#16a34a!important;color:#fff!important;}'
    '[class*="st-key-analyze_"] button:not([disabled]):hover{'
    'background:#15803d!important;border-color:#15803d!important;}'
    # Gen Code buttons: purple when enabled, transparent when disabled
    '[class*="st-key-gen_code_"] button:not([disabled]){'
    'background:#7c3aed!important;border-color:#7c3aed!important;color:#fff!important;}'
    '[class*="st-key-gen_code_"] button:not([disabled]):hover{'
    'background:#6d28d9!important;border-color:#6d28d9!important;}'
    '[class*="st-key-gen_code_"] button[disabled]{'
    'background:transparent!important;border-color:#374151!important;color:#6b7280!important;opacity:.5!important;}'
    # Native delete button: red icon style
    '[class*="st-key-del_card_"] button{'
    'background:rgba(239,68,68,.08)!important;border:1px solid #7f1d1d!important;color:#ef4444!important;}'
    '[class*="st-key-del_card_"] button:hover{'
    'background:rgba(239,68,68,.18)!important;border-color:#ef4444!important;}'
    # Delete confirm button: red primary
    '[class*="st-key-_del_confirm_btn"] button{'
    'background:#dc2626!important;border-color:#991b1b!important;}'
    '[class*="st-key-_del_confirm_btn"] button:hover{'
    'background:#b91c1c!important;border-color:#7f1d1d!important;}'
    '</style>'
)


def _render_project_list() -> None:
    _render_del_confirm()

    st.markdown(_LIST_CARD_CSS, unsafe_allow_html=True)

    query = st.text_input(
        "Buscar",
        placeholder="Nombre, cliente o analista…",
        key="_sp_search",
        label_visibility="collapsed",
    )

    projects = api.get(f"{BACKEND}/projects") or []

    # Build user lookup map (cached per render via session_state)
    if "_sp_user_map" not in st.session_state:
        users = api.get(f"{BACKEND}/auth/users") or []
        st.session_state["_sp_user_map"] = {u["email"]: u for u in users}
    user_map: dict = st.session_state["_sp_user_map"]

    if not projects:
        st.info("No hay proyectos. Crea el primero con el formulario.")
        return

    q = query.strip().lower()
    filtered = [
        p for p in projects
        if not q
        or q in (p.get("project_name") or "").lower()
        or q in (p.get("client_name") or "").lower()
        or any(q in a.lower() for a in (p.get("assigned_analysts") or []))
    ]

    st.markdown(
        f'<span style="color:#8b949e;font-size:.82rem;">'
        f'{len(filtered)} de {len(projects)} proyectos</span>',
        unsafe_allow_html=True,
    )

    with st.container(height=700):
        if not filtered:
            st.info("Sin resultados para esa búsqueda.")
        for p in filtered:
            _project_card(p, user_map)


_AVATAR_PALETTES = [
    ("#0c1a3d", "#93c5fd"), ("#052e16", "#86efac"), ("#2e1065", "#d8b4fe"),
    ("#3b1a00", "#fed7aa"), ("#0f2d3d", "#7dd3fc"), ("#1a1060", "#a5b4fc"),
    ("#14432a", "#6ee7b7"), ("#450a0a", "#fca5a5"),
]

# Role-based colors (same palette as admin panel)
_ROLE_CHIP = {
    "scrum_leader": ("background:#0c1a3d;border:1px solid #1d4ed8;", "#93c5fd", "Scrum"),
    "analyst":      ("background:#052e16;border:1px solid #16a34a;", "#86efac", "Analista"),
    "developer":    ("background:#2e1065;border:1px solid #7e22ce;", "#d8b4fe", "Dev"),
    "admin":        ("background:#450a0a;border:1px solid #991b1b;", "#fca5a5", "Admin"),
}
_DEV_TYPE_LBL = {"backend": "Backend", "frontend": "Frontend", "devops": "DevOps"}
_ROLE_LBL = {"scrum_leader": "Scrum Leader", "analyst": "Analista",
             "developer": "Desarrollador", "admin": "Admin"}


def _guess_mime(raw: bytes) -> str:
    if raw[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if raw[:2] == b'\xff\xd8':
        return "image/jpeg"
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return "image/webp"
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return "image/gif"
    return "image/jpeg"


def _project_avatar_html(p: dict, size: int = 40) -> str:
    run_id   = p.get("run_id", "")
    name     = p.get("project_name", "?")
    has_logo = bool(p.get("logo_url"))
    words    = name.split()
    initials = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper() if words else "?"
    bg, fg   = _AVATAR_PALETTES[hash(name) % len(_AVATAR_PALETTES)]

    cache_key = f"_logo_b64_{run_id}"
    cached    = st.session_state.get(cache_key)  # None | ("b64str", "mime") | ("", "")

    # Fetch if: never cached, OR server now has a logo but we cached a miss
    if cached is None or (has_logo and cached[0] == ""):
        if has_logo:
            raw = api.get_bytes(f"{BACKEND}/projects/{run_id}/logo")
            if raw:
                st.session_state[cache_key] = (base64.b64encode(raw).decode(), _guess_mime(raw))
            else:
                st.session_state[cache_key] = ("", "image/jpeg")
        else:
            st.session_state[cache_key] = ("", "image/jpeg")
        cached = st.session_state[cache_key]

    logo_b64, mime = cached
    s = f"width:{size}px;height:{size}px;border-radius:50%;flex-shrink:0;"
    if logo_b64:
        return (
            f'<img src="data:{mime};base64,{logo_b64}" '
            f'style="{s}object-fit:cover;display:block;">'
        )
    return (
        f'<div style="{s}background:{bg};color:{fg};display:flex;'
        f'align-items:center;justify-content:center;'
        f'font-size:{round(size/2.5)}px;font-weight:700;font-family:sans-serif;">'
        f'{initials}</div>'
    )


def _project_avatar_clickable_html(p: dict, size: int = 72) -> str:
    """Hero logo wrapped in .qa-dlog-wrap so hovering shows camera and clicking uploads."""
    run_id   = p.get("run_id", "")
    name     = p.get("project_name", "?")
    has_logo = bool(p.get("logo_url"))
    words    = name.split()
    initials = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper() if words else "?"
    bg, fg   = _AVATAR_PALETTES[hash(name) % len(_AVATAR_PALETTES)]

    cache_key = f"_logo_b64_{run_id}"
    cached    = st.session_state.get(cache_key)
    if cached is None or (has_logo and cached[0] == ""):
        if has_logo:
            raw = api.get_bytes(f"{BACKEND}/projects/{run_id}/logo")
            if raw:
                st.session_state[cache_key] = (base64.b64encode(raw).decode(), _guess_mime(raw))
            else:
                st.session_state[cache_key] = ("", "image/jpeg")
        else:
            st.session_state[cache_key] = ("", "image/jpeg")
        cached = st.session_state[cache_key]

    logo_b64, mime = cached
    if logo_b64:
        inner = (f'<img src="data:{mime};base64,{logo_b64}" '
                 f'style="width:{size}px;height:{size}px;border-radius:50%;'
                 f'object-fit:cover;display:block;flex-shrink:0;">')
    else:
        inner = (f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
                 f'background:{bg};color:{fg};display:flex;align-items:center;'
                 f'justify-content:center;font-size:{round(size/2.5)}px;'
                 f'font-weight:700;font-family:sans-serif;flex-shrink:0;">{initials}</div>')

    cam_svg = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
               'stroke="#e2e8f0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4'
               'a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>')
    return (
        f'<div class="qa-dlog-wrap" title="Haz clic para cambiar el logo">'
        f'{inner}'
        f'<div class="qa-dlog-ov">{cam_svg}'
        f'<span class="qa-dlog-ov-txt">Cambiar</span></div>'
        f'</div>'
    )


def _person_avatar_chip(email: str, role: str = "") -> str:
    initials = email[0].upper()
    if role in _ROLE_CHIP:
        _, fg, _ = _ROLE_CHIP[role]
        bg_style = _ROLE_CHIP[role][0]
        style = f"{bg_style}color:{fg};"
    else:
        bg, fg = _AVATAR_PALETTES[hash(email) % len(_AVATAR_PALETTES)]
        style = f"background:{bg};color:{fg};"
    return (
        f'<span style="width:14px;height:14px;border-radius:50%;{style}'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:.55rem;font-weight:700;font-family:sans-serif;flex-shrink:0;">'
        f'{initials}</span>'
    )


def _team_chip_html(email: str, user_map: dict) -> str:
    u        = user_map.get(email, {})
    role     = u.get("role", "")
    dev_type = u.get("developer_type", "")
    chip_style, fg, _ = _ROLE_CHIP.get(
        role, ("background:#1a1f2e;border:1px solid #21262d;", "#c9d1d9", "")
    )
    label    = email.split("@")[0]
    # Role label: developer → dev_type label, others → role label
    if role == "developer" and dev_type:
        role_lbl = _DEV_TYPE_LBL.get(dev_type, dev_type)
    else:
        role_lbl = _ROLE_LBL.get(role, "")
    role_tag = (
        f'<span style="font-size:.7rem;opacity:.7;margin-left:.2rem;">· {role_lbl}</span>'
        if role_lbl else ""
    )
    return (
        f'<span style="display:inline-flex;align-items:center;gap:.15rem;'
        f'{chip_style}border-radius:9999px;'
        f'font-size:.8rem;padding:.1rem .55rem;color:{fg};margin:.1rem .2rem 0 0;">'
        f'{label}{role_tag}</span>'
    )


def _project_card(p: dict, user_map: dict | None = None) -> None:
    um = user_map or {}
    req_count    = p.get("req_count", 0)
    req_analyzed = p.get("req_analyzed", 0)
    status       = p.get("status", "created")
    client       = p.get("client_name", "")
    analysts     = p.get("assigned_analysts") or []

    # Req-based status badge — always blue
    if req_count == 0:
        req_badge = f'<span style="background:#1a1f2e;color:#4b5563;{_B}">Sin reqs.</span>'
    elif status == "analyzing":
        req_badge = _STATUS_BADGE.get("analyzing", "")
    else:
        req_badge = (
            f'<span style="background:#1e3a5f;color:#93c5fd;{_B}">'
            f'{req_analyzed} de {req_count} analizados</span>'
        )

    contact_name  = p.get("contact_name") or ""
    contact_email = p.get("contact_email") or ""

    av = _project_avatar_html(p, size=36)
    has_pending = req_count > 0 and req_analyzed < req_count and status != "analyzing"

    _rid  = p["run_id"]
    pname = p.get("project_name", "Sin nombre")

    # Team chips (compact, no avatar initials)
    team_html = ""
    if analysts:
        chips = "".join(_team_chip_html(a, um) for a in analysts)
        team_html = f'<div style="margin-top:.25rem;display:flex;flex-wrap:wrap;">{chips}</div>'

    # Meta row: client · contact name · contact email
    _sep = '<span style="color:#374151;margin:0 .2rem;">·</span>'
    meta_parts: list[str] = []
    if client:
        meta_parts.append(f'<span style="color:#6b7280;font-size:.82rem;">{client}</span>')
    if contact_name:
        meta_parts.append(f'<span style="color:#6b7280;font-size:.82rem;">{contact_name}</span>')
    if contact_email:
        meta_parts.append(
            f'<a href="mailto:{contact_email}" style="color:#5b8dd9;font-size:.82rem;'
            f'text-decoration:none;">{contact_email}</a>'
        )
    meta_html = (
        f'<div style="margin-top:.12rem;display:flex;align-items:center;flex-wrap:wrap;">'
        + _sep.join(meta_parts) + "</div>"
    ) if meta_parts else ""

    desc     = p.get("description") or ""
    desc_html = (
        f'<div style="color:#6b7280;font-size:.82rem;margin-top:.1rem;">'
        f'{desc[:90]}{"…" if len(desc) > 90 else ""}</div>'
    ) if desc else ""

    _has_analysis = bool((p.get("summary") or {}).get("total_stories"))
    col_info, col_analyze, col_gencode, col_del = st.columns([5, 1, 1.5, 0.55])
    with col_info:
        # Layout: [logo]  [title · badge]
        #                 [desc / meta / team]
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:.6rem;margin:.1rem 0 .15rem;">'
            f'{av}'
            f'<div style="min-width:0;flex:1;">'
            f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:.45rem;margin-bottom:.18rem;">'
            f'<a class="qa-pname" href="?_sel_proj={_rid}" target="_self">{pname}</a>'
            f'{req_badge}'
            f'</div>'
            f'{desc_html}{meta_html}{team_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with col_analyze:
        if st.button(
            "Analizar",
            key=f"analyze_{_rid}",
            disabled=not has_pending,
            use_container_width=True,
            type="primary",
        ):
            _analyze_modal(_rid)
    has_analyzed = req_analyzed > 0
    with col_gencode:
        if st.button(
            "Gen Code",
            key=f"gen_code_{_rid}",
            use_container_width=True,
            disabled=not has_analyzed,
        ):
            _gen_code_modal(_rid)
    with col_del:
        if st.button("🗑", key=f"del_card_{_rid}", use_container_width=True):
            _delete_project_dialog(_rid, p, _has_analysis)
    st.divider()


# ── Crear proyecto ────────────────────────────────────────────────────────────

def _field_error(msg: str) -> None:
    st.markdown(
        f'<p style="color:#f87171;font-size:.8rem;margin-top:-.4rem;margin-bottom:.4rem;">'
        f'{icon("warning",12,"#f87171")} {msg}</p>',
        unsafe_allow_html=True,
    )


def _extract_req_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".txt"):
        return raw.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return raw.decode("utf-8", errors="replace")


def _validate_create(pname: str, cemail: str) -> dict:
    errs: dict = {}
    if not pname.strip():
        errs["project_name"] = "El nombre del proyecto es obligatorio."
    elif len(pname.strip()) < 2:
        errs["project_name"] = "El nombre debe tener al menos 2 caracteres."
    if cemail.strip() and not _EMAIL_RE.match(cemail.strip()):
        errs["contact_email"] = "Ingresa un email válido."
    return errs


@st.dialog("Agregar requerimiento", width="large")
def _add_req_dialog() -> None:
    st.text_input("Título *", key="_dlg_req_title",
                  placeholder="Ej: Módulo de autenticación SSO")

    # File uploader — extracts text into content field on upload
    uploaded = st.file_uploader(
        "Adjuntar archivo (opcional)",
        type=["txt", "pdf", "docx"],
        key="_dlg_req_file",
        help="El texto extraído se colocará automáticamente en el campo de requerimiento",
    )
    if uploaded:
        fname = uploaded.name
        if fname != st.session_state.get("_dlg_req_file_loaded"):
            extracted = _extract_req_text(uploaded)
            st.session_state["_dlg_req_content"] = extracted
            st.session_state["_dlg_req_file_loaded"] = fname
            # No st.rerun() — would close the dialog; widget rerun handles the update

    st.text_area("Requerimiento en bruto *", key="_dlg_req_content",
                 height=180, placeholder="Describe el requerimiento de forma libre…")

    col_c, col_s = st.columns([1, 2])
    with col_c:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_dlg_req_file_loaded", None)
            st.rerun()
    with col_s:
        if st.button("Agregar", type="primary", use_container_width=True):
            title   = st.session_state.get("_dlg_req_title", "").strip()
            content = st.session_state.get("_dlg_req_content", "").strip()
            errs: list[str] = []
            if not title:
                errs.append("El título es obligatorio.")
            if len(content) < 20:
                errs.append("El requerimiento debe tener al menos 20 caracteres.")
            if errs:
                for e in errs:
                    st.error(e)
            else:
                attachment = st.session_state.pop("_dlg_req_file_loaded", None)
                pending = st.session_state.setdefault("_cf_pending_reqs", [])
                pending.append({
                    "title": title,
                    "content": content,
                    "attachment_name": attachment or "",
                })
                st.rerun()


def _render_create_form() -> None:
    # Generation counter: incrementing forces all widgets to fresh instances
    _gen = st.session_state.get("_cf_gen", 0)

    st.markdown('<div id="qa-cf-anchor"></div>', unsafe_allow_html=True)

    # ── Header: título + avatar circular de logo (derecha) ───────────────────
    _cam_ic = icon("camera", 24, "#475569")
    _logo_src    = st.session_state.get("_logo_preview_src", "")
    _logo_border = "2px solid #0891b2" if _logo_src else "2px dashed #30363d"
    _img_style   = "display:block;" if _logo_src else "display:none;"
    _ic_style    = "display:none;" if _logo_src else "display:flex;"
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.7rem;">'
        f'<span style="color:#e2e8f0;font-size:1rem;font-weight:600;font-family:sans-serif;">Nuevo Proyecto</span>'
        f'<div id="qa-cf-logo-av" title="Adjuntar logo (JPG, PNG, WEBP · máx. 5 MB)" style="'
        f'width:60px;height:60px;border-radius:50%;background:#1a1f2e;'
        f'border:{_logo_border};display:flex;align-items:center;justify-content:center;'
        f'cursor:pointer;overflow:hidden;flex-shrink:0;position:relative;transition:border-color .2s;">'
        f'<span id="qa-cf-logo-ic" style="{_ic_style}align-items:center;">{_cam_ic}</span>'
        f'<img id="qa-cf-logo-img" src="{_logo_src}" '
        f'style="{_img_style}width:100%;height:100%;object-fit:cover;position:absolute;inset:0;border-radius:50%;"/>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    errs: dict = st.session_state.get("_create_errs", {})

    st.text_input("Nombre del proyecto *", key=f"g{_gen}_cf_pname",
                  placeholder="Ej: Portal de pagos B2B")
    if "project_name" in errs:
        _field_error(errs["project_name"])

    st.text_area("Descripción", key=f"g{_gen}_cf_desc", height=68,
                 placeholder="Breve descripción del proyecto (se mostrará en el listado)…")

    st.text_input("Cliente", key=f"g{_gen}_cf_client",
                  placeholder="Ej: Bancolombia S.A.")

    col3, col4 = st.columns(2)
    with col3:
        st.text_input("Nombre contacto", key=f"g{_gen}_cf_cname",
                      placeholder="Ana García")
    with col4:
        st.text_input("Email contacto", key=f"g{_gen}_cf_cemail",
                      placeholder="ana@empresa.com")
        if "contact_email" in errs:
            _field_error(errs["contact_email"])

    # ── Asignar equipo ────────────────────────────────────────────────────────
    _all_users = api.get(f"{BACKEND}/auth/users") or []
    # All active non-admin users can be assigned
    _assignable = [u for u in _all_users if u.get("is_active") and u.get("role") != "admin"]

    def _user_label(u: dict) -> str:
        base  = u.get("name") or u["email"]
        role  = _ROLE_LBL.get(u.get("role", ""), u.get("role", ""))
        dtype = _DEV_TYPE_LBL.get(u.get("developer_type", ""), "")
        suffix = f"{role} · {dtype}" if dtype else role
        return f"{base} — {suffix}"

    _user_opts = [u["email"] for u in _assignable]
    _user_fmt  = {u["email"]: _user_label(u) for u in _assignable}

    st.markdown(
        '<span style="color:#e2e8f0;font-size:.85rem;font-weight:500;">'
        'Asignar equipo</span>',
        unsafe_allow_html=True,
    )
    st.multiselect(
        "Asignar equipo",
        options=_user_opts,
        format_func=lambda e: _user_fmt.get(e, e),
        key=f"g{_gen}_cf_team",
        placeholder="Buscar por nombre o email…",
        label_visibility="collapsed",
    )

    # Uploader oculto del logo — JS dispara el click en input[type=file]
    st.markdown('<div id="qa-cf-logo-ul-anchor"></div>', unsafe_allow_html=True)
    logo_file = st.file_uploader(
        "Logo", type=["jpg", "jpeg", "png", "webp"],
        key=f"g{_gen}_cf_logo_file", label_visibility="collapsed",
    )
    if logo_file:
        if logo_file.size > 5 * 1024 * 1024:
            st.error("El logo supera 5 MB.")
        elif logo_file.name != st.session_state.get("_logo_preview_name"):
            _raw = logo_file.read()
            _mime = logo_file.type or "image/jpeg"
            st.session_state["_logo_preview_src"] = (
                f"data:{_mime};base64,{base64.b64encode(_raw).decode()}"
            )
            st.session_state["_logo_preview_name"] = logo_file.name
            logo_file.seek(0)

    # ── Requerimientos ────────────────────────────────────────────────────────
    _pending = st.session_state.setdefault("_cf_pending_reqs", [])
    _req_header_c, _req_add_c = st.columns([3, 1])
    with _req_header_c:
        st.markdown(
            f'<span style="color:#e2e8f0;font-size:.85rem;font-weight:500;">'
            f'Requerimientos</span>'
            f'<span style="color:#6b7280;font-size:.75rem;margin-left:.4rem;">'
            f'({len(_pending)})</span>',
            unsafe_allow_html=True,
        )
    with _req_add_c:
        if st.button("+ Agregar", key="cf_add_req_btn", use_container_width=True):
            _add_req_dialog()

    # List of pending requirements
    for _i, _r in enumerate(_pending):
        _rc, _rx = st.columns([8, 1])
        with _rc:
            st.markdown(
                f'<div style="background:#161b22;border:1px solid #21262d;'
                f'border-left:3px solid #00bcd4;border-radius:0 6px 6px 0;'
                f'padding:.4rem .75rem;margin-bottom:.25rem;">'
                f'<div style="color:#e2e8f0;font-size:.83rem;font-weight:600;">'
                f'{_r["title"]}</div>'
                f'<div style="color:#6b7280;font-size:.75rem;margin-top:.1rem;">'
                f'{_r["content"][:80]}{"…" if len(_r["content"]) > 80 else ""}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with _rx:
            if st.button("✕", key=f"cf_rm_req_{_i}", help="Quitar"):
                _pending.pop(_i)
                st.rerun()

    st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
    if st.button("Crear Proyecto", type="primary", use_container_width=True):
        pname  = st.session_state.get(f"g{_gen}_cf_pname", "")
        desc   = st.session_state.get(f"g{_gen}_cf_desc", "")
        client = st.session_state.get(f"g{_gen}_cf_client", "")
        cname  = st.session_state.get(f"g{_gen}_cf_cname", "")
        cemail = st.session_state.get(f"g{_gen}_cf_cemail", "")
        logo_f = logo_file

        new_errs = _validate_create(pname, cemail)
        if new_errs:
            st.session_state["_create_errs"] = new_errs
            st.rerun()

        st.session_state.pop("_create_errs", None)
        payload: dict = {"project_name": pname.strip()}
        if desc.strip():
            payload["description"] = desc.strip()
        if client.strip():
            payload["client_name"] = client.strip()
        if cname.strip():
            payload["contact_name"] = cname.strip()
        if cemail.strip():
            payload["contact_email"] = cemail.strip()

        with st.spinner("Creando proyecto…"):
            result = api.post(f"{BACKEND}/projects", payload)

        if result:
            run_id = result.get("run_id", "")
            # Upload logo
            if logo_f and logo_f.size <= 5 * 1024 * 1024 and run_id:
                api.upload_file(
                    f"{BACKEND}/projects/{run_id}/logo",
                    logo_f.getvalue(), logo_f.name, logo_f.type or "image/jpeg",
                )
            # Add pending requirements
            for req_item in (_pending or []):
                payload_req: dict = {"title": req_item["title"], "content": req_item["content"]}
                if req_item.get("attachment_name"):
                    payload_req["attachment_name"] = req_item["attachment_name"]
                api.post(f"{BACKEND}/projects/{run_id}/requirements", payload_req)
            # Assign team
            team = st.session_state.get(f"g{_gen}_cf_team") or []
            for email in team:
                api.post(
                    f"{BACKEND}/projects/{run_id}/assign-analyst",
                    {"analyst_email": email},
                    suppress_codes=(400, 404, 409),
                )
            # Reset form
            for k in list(st.session_state.keys()):
                if k.startswith(f"g{_gen}_cf_"):
                    st.session_state.pop(k, None)
            for k in ["_logo_preview_src", "_logo_preview_name",
                      "_create_errs", "_sp_user_map", "_cf_pending_reqs"]:
                st.session_state.pop(k, None)
            st.session_state["_cf_gen"] = _gen + 1
            st.session_state["_scrum_toast"] = {
                "msg": f"Proyecto '{result.get('project_name', '')}' creado correctamente.",
                "kind": "success",
            }
            st.rerun()
        else:
            st.session_state["_scrum_toast"] = {
                "msg": "No se pudo crear el proyecto. Verifica los datos.",
                "kind": "error",
            }
            st.rerun()

    _inject_create_form_js()


_CF_JS = """
(function(){
  var D=document,W=window;

  function childOfVB(el){
    while(el&&el.parentElement){
      if(el.parentElement.getAttribute('data-testid')==='stVerticalBlock') return el;
      el=el.parentElement;
    }
    return null;
  }

  /* Busca el textarea por sentinel o por aria-label (fallback siempre confiable) */
  function getTA(){
    var s=D.getElementById('qa-cf-ta-sentinel');
    if(s){
      var c=childOfVB(s);
      if(c){var n=c.nextElementSibling;while(n){var t=n.querySelector('textarea');if(t)return t;n=n.nextElementSibling;}}
    }
    return D.querySelector('textarea[aria-label="Requerimiento en bruto"]');
  }

  function findUL(anId){
    var a=D.getElementById(anId);if(!a)return null;
    var c=childOfVB(a);if(!c)return null;
    var n=c.nextElementSibling;
    while(n){
      if(n.querySelector('[data-testid="stFileUploader"]')||n.getAttribute('data-testid')==='stFileUploader')return n;
      n=n.nextElementSibling;
    }
    return null;
  }

  function hideBlock(b){
    if(!b)return;
    b.style.visibility='hidden';b.style.height='0';b.style.minHeight='0';
    b.style.maxHeight='0';b.style.overflow='hidden';b.style.margin='0';b.style.padding='0';
  }

  function hideUploaders(){
    hideBlock(findUL('qa-cf-logo-ul-anchor'));
    hideBlock(findUL('qa-cf-ul-anchor'));
  }

  function triggerReqUpload(){
    var b=findUL('qa-cf-ul-anchor');if(!b)return;
    var inp=b.querySelector('input[type="file"]');
    if(inp){inp.click();return;}
    b.style.visibility='visible';b.style.height='auto';b.style.maxHeight='none';b.style.overflow='visible';
    var btn=b.querySelector('button');if(btn)btn.click();
    setTimeout(hideUploaders,600);
  }

  function triggerLogoUpload(){
    var b=findUL('qa-cf-logo-ul-anchor');if(!b)return;
    var inp=b.querySelector('input[type="file"]');
    if(inp){
      inp.onchange=function(){
        var f=inp.files&&inp.files[0];if(!f)return;
        var rd=new FileReader();
        rd.onload=function(e){
          var img=D.getElementById('qa-cf-logo-img');
          var ic=D.getElementById('qa-cf-logo-ic');
          var av=D.getElementById('qa-cf-logo-av');
          if(img){img.src=e.target.result;img.style.display='block';}
          if(ic)ic.style.display='none';
          if(av)av.style.border='2px solid #0891b2';
        };
        rd.readAsDataURL(f);
      };
      inp.click();return;
    }
    b.style.visibility='visible';b.style.height='auto';b.style.maxHeight='none';b.style.overflow='visible';
    setTimeout(hideUploaders,600);
  }

  if(!W._qaFormClickAttached){
    W._qaFormClickAttached=true;
    D.addEventListener('click',function(e){
      if(!e.target||typeof e.target.closest!=='function')return;
      if(e.target.closest('#qa-cf-logo-av')){
        e.preventDefault();e.stopPropagation();triggerLogoUpload();
      }else if(e.target.closest('#qa-cf-clip-btn')){
        e.preventDefault();e.stopPropagation();triggerReqUpload();
      }else if(e.target.closest('#qa-cf-max-btn')){
        e.preventDefault();e.stopPropagation();_showModal();
      }
    },true);
  }

  if(!W._qaFormObserver){
    var _oT=null;
    W._qaFormObserver=new MutationObserver(function(){
      clearTimeout(_oT);_oT=setTimeout(hideUploaders,180);
    });
    W._qaFormObserver.observe(D.body,{childList:true,subtree:true});
  }

  function _showModal(){
    if(D.getElementById('qa-max-ov'))return;
    var ta=getTA();var txt=ta?ta.value:'';
    if(!D.getElementById('qa-max-css')){
      var s=D.createElement('style');s.id='qa-max-css';
      s.textContent=
        '#qa-max-ov{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:99999;display:flex;align-items:center;justify-content:center;}'
        +'#qa-max-mo{background:#161b22;border:1px solid #30363d;border-radius:12px;width:min(92vw,860px);height:min(88vh,820px);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 64px rgba(0,0,0,.6);}'
        +'#qa-max-hd{display:flex;align-items:center;justify-content:space-between;padding:.75rem 1.25rem;border-bottom:1px solid #21262d;flex-shrink:0;}'
        +'#qa-max-hd-t{color:#e2e8f0;font-size:1rem;font-weight:600;font-family:sans-serif;}'
        +'#qa-max-x{background:none;border:none;cursor:pointer;color:#8b949e;font-size:1.1rem;padding:.2rem .45rem;border-radius:4px;line-height:1;}'
        +'#qa-max-x:hover{color:#e2e8f0;background:#21262d;}'
        +'#qa-max-ta{flex:1;width:100%;background:#0d1117;color:#e2e8f0;border:none;outline:none;resize:none;font-size:.975rem;line-height:1.7;padding:1.25rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;box-sizing:border-box;}'
        +'#qa-max-ft{padding:.65rem 1.25rem;border-top:1px solid #21262d;display:flex;justify-content:flex-end;gap:.5rem;flex-shrink:0;}'
        +'.qmb{padding:.4rem .9rem;border-radius:6px;font-size:.88rem;font-family:sans-serif;cursor:pointer;border:1px solid #30363d;}'
        +'.qmb-p{background:#0891b2;color:#fff;border-color:#0891b2;}.qmb-p:hover{background:#0e7490;}'
        +'.qmb-s{background:transparent;color:#8b949e;}.qmb-s:hover{color:#e2e8f0;}';
      D.head.appendChild(s);
    }
    var ov=D.createElement('div');ov.id='qa-max-ov';
    var mo=D.createElement('div');mo.id='qa-max-mo';
    mo.innerHTML=
      '<div id="qa-max-hd"><span id="qa-max-hd-t">Requerimiento en bruto</span>'
      +'<button id="qa-max-x" title="Cerrar">&#x2715;</button></div>'
      +'<textarea id="qa-max-ta" placeholder="Describe el requerimiento de forma libre…"></textarea>'
      +'<div id="qa-max-ft">'
      +'<button class="qmb qmb-s" id="qa-max-cn">Cancelar</button>'
      +'<button class="qmb qmb-p" id="qa-max-ap">Aplicar cambios</button>'
      +'</div>';
    ov.appendChild(mo);D.body.appendChild(ov);
    var mta=D.getElementById('qa-max-ta');mta.value=txt;mta.focus();
    function close(){var o=D.getElementById('qa-max-ov');if(o)o.remove();}
    function apply(){
      var nv=mta.value;var stTa=getTA();
      if(stTa){
        var ns=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
        if(ns&&ns.set)ns.set.call(stTa,nv);
        ['input','change'].forEach(function(en){stTa.dispatchEvent(new Event(en,{bubbles:true}));});
      }
      close();
    }
    D.getElementById('qa-max-x').onclick=close;
    D.getElementById('qa-max-cn').onclick=close;
    D.getElementById('qa-max-ap').onclick=apply;
    ov.onclick=function(e){if(e.target===ov)close();};
  }

  W.qaFormInit=function(){hideUploaders();};
  setTimeout(W.qaFormInit,200);
})();
"""


def _inject_create_form_js() -> None:
    js = """<script>
(function(){
  var D=window.parent.document,W=window.parent;
  var VER='13';
  var old=D.getElementById('qa-cf-js');
  if(old&&old.getAttribute('data-ver')!==VER){
    old.remove();old=null;
    W._qaFormClickAttached=false;
    if(W._qaFormObserver){try{W._qaFormObserver.disconnect();}catch(ex){}W._qaFormObserver=null;}
  }
  if(!old){
    var sc=D.createElement('script');sc.id='qa-cf-js';
    sc.setAttribute('data-ver',VER);
    sc.textContent=""" + repr(_CF_JS) + """;
    D.head.appendChild(sc);
  }
  setTimeout(function(){W.qaFormInit&&W.qaFormInit();},260);
})();
</script>"""
    components.html(js, height=0, scrolling=False)


# ── Gen Code helpers ─────────────────────────────────────────────────────────

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


def _cg_progress_ui(store_key: str, status: dict) -> None:
    """Renders code-gen progress: spinner, active provider badge, chain chips, timer."""
    store = _CODE_GEN_STORE.get(store_key, {})
    elapsed = int(time.time() - store.get("start_time", time.time()))
    mins, secs = divmod(elapsed, 60)

    current_label: str = status.get("current_label", "—")
    chain_meta: list[dict] = status.get("chain_meta", [])
    current_meta = next(
        (m for m in chain_meta if m.get("label") == current_label), {}
    )
    pname = current_meta.get("provider", current_label.split("[")[0] if "[" in current_label else current_label)
    model = current_meta.get("model", "")
    display_name = _PROVIDER_LABELS.get(pname, pname.capitalize())
    dot_color = _PROVIDER_COLORS.get(pname, "#8b949e")

    # Spinner + title
    st.markdown(
        '<style>@keyframes cg-spin{to{transform:rotate(360deg);}}'
        '#cg-ring{width:40px;height:40px;border:3px solid #21262d;'
        'border-top:3px solid #7c3aed;border-radius:50%;'
        'animation:cg-spin 1s linear infinite;margin:1rem auto .9rem;}</style>'
        '<div id="cg-ring"></div>'
        '<div style="text-align:center;">'
        '<div style="font-weight:700;color:#e2e8f0;font-size:.97rem;margin-bottom:.35rem;">'
        'Generando código Python y Pytest tests</div>'
        '<div style="color:#6b7280;font-size:.83rem;margin-bottom:.7rem;">'
        'El agente está generando módulos de código y tests unitarios.<br>'
        'Este proceso puede tardar entre 1 y 3 minutos.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Active provider badge
    if display_name and display_name != "—":
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

    # Provider chain chips
    if len(chain_meta) > 1:
        chips = []
        for meta in chain_meta:
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
            + arrow.join(chips) + '</div>',
            unsafe_allow_html=True,
        )

    # Timer
    st.markdown(
        f'<div style="text-align:center;color:#7c3aed;font-size:.88rem;'
        f'font-weight:600;margin-bottom:.9rem;">⏱ {mins:02d}:{secs:02d} transcurridos</div>',
        unsafe_allow_html=True,
    )


def _start_cg_thread(store_key: str, ref_run_id: str, project_id: str) -> None:
    """Launches the background code-gen HTTP call and registers it in _CODE_GEN_STORE."""
    if store_key in _CODE_GEN_STORE:
        return
    _token = st.session_state.get("token")
    _headers = {"Authorization": f"Bearer {_token}"} if _token else {}
    store: dict = {
        "running": True, "result": None, "error": None,
        "cancelled": False, "start_time": time.time(),
        "ref_run_id": ref_run_id,
    }
    _CODE_GEN_STORE[store_key] = store

    def _worker() -> None:
        try:
            r = httpx.post(
                f"{BACKEND}/pipeline/generate-code",
                json={"run_id": ref_run_id, "project_id": project_id},
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


# ── Progress dialog (requirements tab) ───────────────────────────────────────

@st.dialog("Generando código", width="small")
def _code_gen_progress_dialog(store_key: str, cancel_key: str) -> None:
    """Progress-only dialog used from the requirements tab (refinement already known)."""
    store = _CODE_GEN_STORE.get(store_key)
    if store is None:
        st.session_state.pop(cancel_key, None)
        st.rerun()
        return

    if store.get("running"):
        status = api.get(f"{BACKEND}/pipeline/status") or {}
        _cg_progress_ui(store_key, status)
        if st.button("⏹ Cancelar", use_container_width=True, key=f"cg_stop_{store_key}"):
            store["cancelled"] = True
            store["running"] = False
            _CODE_GEN_STORE.pop(store_key, None)
            st.session_state.pop(cancel_key, None)
            st.rerun()
        time.sleep(2)
        st.rerun()
        return

    # Thread finished
    result = store.get("result")
    error  = store.get("error")
    _CODE_GEN_STORE.pop(store_key, None)
    st.session_state.pop(cancel_key, None)

    if store.get("cancelled"):
        st.rerun()
        return
    if error:
        st.error(f"Error al generar código: {error}")
        return
    if result:
        ref_run_id = store.get("ref_run_id", "")
        st.session_state[f"_code_result_{ref_run_id}"] = result
        st.session_state.pop(f"_ref_cache_{ref_run_id}", None)
    st.rerun()


# ── Select + generate dialog (project card) ───────────────────────────────────

@st.dialog("Generar Código", width="large")
def _gen_code_modal(run_id: str) -> None:
    """Two-phase dialog: phase 1 = select refinement, phase 2 = show progress inline."""
    phase_key = f"_cg_phase_{run_id}"
    sk_key    = f"_cg_sk_{run_id}"
    phase     = st.session_state.get(phase_key, "select")

    # ── Phase 2: running ──────────────────────────────────────────────────────
    if phase == "running":
        store_key = st.session_state.get(sk_key, "")
        store     = _CODE_GEN_STORE.get(store_key)

        if store is None:
            # Thread already finished and store was cleaned up
            st.session_state.pop(phase_key, None)
            st.session_state.pop(sk_key, None)
            st.rerun()
            return

        if store.get("running"):
            status = api.get(f"{BACKEND}/pipeline/status") or {}
            _cg_progress_ui(store_key, status)
            if st.button("⏹ Cancelar", use_container_width=True, key=f"cg_stopm_{store_key}"):
                store["cancelled"] = True
                store["running"] = False
                _CODE_GEN_STORE.pop(store_key, None)
                st.session_state.pop(phase_key, None)
                st.session_state.pop(sk_key, None)
                st.rerun()
            time.sleep(2)
            st.rerun()
            return

        # Thread done
        result = store.get("result")
        error  = store.get("error")
        _CODE_GEN_STORE.pop(store_key, None)
        st.session_state.pop(phase_key, None)
        st.session_state.pop(sk_key, None)

        if store.get("cancelled"):
            st.rerun()
            return
        if error:
            st.error(f"Error al generar código: {error}")
            return
        if result:
            ref_run_id = store.get("ref_run_id", "")
            st.session_state[f"_code_result_{ref_run_id}"] = result
            st.session_state.pop(f"_ref_cache_{ref_run_id}", None)
            st.success("Código generado. Ábrelo en el tab **Código Generado** del requerimiento.")
            if st.button("Cerrar", use_container_width=True):
                st.rerun()
        return

    # ── Phase 1: select refinement ────────────────────────────────────────────
    reqs = api.get(f"{BACKEND}/projects/{run_id}/requirements") or []
    options: list[dict] = []
    for req in reqs:
        req_title = req.get("title", req.get("req_id", ""))
        for ref in (req.get("refinements") or []):
            summary = ref.get("summary") or {}
            if summary.get("total_stories", 0) > 0:
                options.append({
                    "run_id":          ref.get("run_id", ""),
                    "req_title":       req_title,
                    "created_at":      str(ref.get("created_at", ""))[:16],
                    "total_stories":   summary.get("total_stories", 0),
                    "total_scenarios": summary.get("total_scenarios", 0),
                    "review_status":   ref.get("review_status") or "",
                    "created_by":      ref.get("created_by", ""),
                })

    if not options:
        st.info("No hay refinamientos analizados disponibles para este proyecto.")
        if st.button("Cerrar", use_container_width=True):
            st.rerun()
        return

    opt_map = {o["run_id"]: o for o in options}

    selected_id = st.selectbox(
        "Seleccionar refinamiento analizado",
        options=list(opt_map.keys()),
        format_func=lambda k: (
            f"{opt_map[k]['req_title']} · {opt_map[k]['created_at']} · "
            f"{opt_map[k]['total_stories']} HU · {opt_map[k]['total_scenarios']} tests"
        ),
    )

    selected = opt_map.get(selected_id or "")
    if selected:
        rev_badge = _REVIEW_BADGE.get(selected["review_status"], "")
        st.markdown(
            f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
            f'padding:.65rem .9rem;margin:.4rem 0;">'
            f'<div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin-bottom:.3rem;">'
            f'{rev_badge}'
            f'<span style="color:#6b7280;font-size:.8rem;">por {selected["created_by"]}</span>'
            f'</div>'
            f'<div style="color:#8b949e;font-size:.82rem;">'
            f'{selected["total_stories"]} historias de usuario &nbsp;·&nbsp; '
            f'{selected["total_scenarios"]} test cases</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    col_c, col_g = st.columns([1, 2])
    with col_c:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with col_g:
        if st.button("Generar Código →", type="primary", use_container_width=True,
                     disabled=not selected_id):
            ref_run_id = selected_id or ""
            store_key  = f"cg_{ref_run_id}"
            _start_cg_thread(store_key, ref_run_id, run_id)
            st.session_state[phase_key] = "running"
            st.session_state[sk_key]    = store_key
            st.rerun()


# ── Analizar requerimiento (modal) ───────────────────────────────────────────

@st.dialog("Iniciar análisis", width="large")
def _analyze_modal(run_id: str) -> None:
    reqs = api.get(f"{BACKEND}/projects/{run_id}/requirements") or []
    pending = [r for r in reqs if r.get("status", "created") != "completed"]
    if not pending:
        st.info("Todos los requerimientos ya han sido analizados.")
        return
    options = {r["req_id"]: r.get("title", r["req_id"]) for r in pending}
    selected_id = st.selectbox(
        "Seleccionar requerimiento",
        options=list(options.keys()),
        format_func=lambda k: options[k],
    )
    selected_req = next((r for r in pending if r["req_id"] == selected_id), None)
    if selected_req:
        preview = selected_req.get("content", "")
        st.markdown(
            f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
            f'padding:.65rem .9rem;margin:.4rem 0;color:#8b949e;font-size:.82rem;'
            f'max-height:120px;overflow-y:auto;line-height:1.55;">'
            f'{preview[:400]}{"…" if len(preview) > 400 else ""}</div>',
            unsafe_allow_html=True,
        )
    col_c, col_a = st.columns([1, 2])
    with col_c:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with col_a:
        if st.button("Analizar →", type="primary", use_container_width=True):
            if selected_req:
                st.session_state["_prev_view"]           = st.session_state.get("view", "scrum_projects")
                st.session_state["_auto_analyze"]      = selected_req.get("content", "")
                st.session_state["_auto_analyze_proj"]  = run_id
                st.session_state["_auto_analyze_req"]   = selected_id
                st.session_state.view                   = "chat"
                st.session_state.scrum_selected_project = None
                st.rerun()


# ── Detalle de proyecto ───────────────────────────────────────────────────────

def _section_divider(label: str, icon_name: str = "") -> None:
    ic = icon(icon_name, 13, "#00bcd4") if icon_name else ""
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:.5rem;margin:1.4rem 0 .7rem;">'
        f'<div style="width:3px;height:14px;background:#00bcd4;border-radius:2px;flex-shrink:0;"></div>'
        f'<span style="color:#00bcd4;font-size:.8rem;font-weight:600;'
        f'letter-spacing:.07em;text-transform:uppercase;font-family:sans-serif;">'
        f'{ic}&nbsp;{label}</span>'
        f'<div style="flex:1;height:1px;background:#21262d;margin-left:.35rem;"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_project_detail(run_id: str) -> None:
    if st.button("← Proyectos"):
        st.session_state.scrum_selected_project = None
        st.session_state.pop("_del_pending", None)
        st.rerun()

    _render_del_confirm()

    with st.spinner("Cargando proyecto…"):
        project = api.get(f"{BACKEND}/projects/{run_id}/detail")

    if not project:
        st.error("No se pudo cargar el proyecto.")
        return

    # Normalize logo_url from logo_path if needed
    if project.get("logo_path") and not project.get("logo_url"):
        project["logo_url"] = f"/projects/{run_id}/logo"

    status        = project.get("status", "created")
    review_status = project.get("review_status") or ""
    created_at    = str(project.get("created_at", ""))[:10]
    created_by    = project.get("created_by", "")

    status_b = _STATUS_BADGE.get(status, "")
    review_b = _REVIEW_BADGE.get(review_status, "")
    meta_parts = []
    if created_at:
        meta_parts.append(created_at)
    if created_by:
        meta_parts.append(f"por {created_by}")
    meta_str = " · ".join(meta_parts)

    # ── Hero: [✎] [logo · nombre · badges · meta · info cliente] ────────────
    _cname  = project.get("client_name") or ""
    _ctname = project.get("contact_name") or ""
    _ctemail = project.get("contact_email") or ""
    _cparts: list[str] = []
    if _cname:
        _cparts.append(f'<span>{_cname}</span>')
    if _ctname:
        _cparts.append(f'<span>{_ctname}</span>')
    if _ctemail:
        _cparts.append(
            f'<a href="mailto:{_ctemail}" style="color:#7dd3fc;text-decoration:none;">'
            f'{_ctemail}</a>'
        )
    _csep = '<span style="color:#374151;margin:0 .15rem;">·</span>'
    contact_html = (
        f'<div style="margin-top:.3rem;display:flex;flex-wrap:wrap;align-items:center;'
        f'color:#8b949e;font-size:.78rem;">'
        + _csep.join(_cparts) + '</div>'
    ) if _cparts else ""

    av_click = _project_avatar_clickable_html(project, size=72)
    _has_analysis = bool((project.get("report_data") or {}).get("user_stories"))
    st.markdown(
        _DET_LOGO_CSS
        + f'<div style="position:relative;display:flex;align-items:center;gap:1.1rem;'
        f'background:#161b22;border:1px solid #21262d;border-radius:12px;'
        f'padding:1rem 1.4rem;margin-bottom:1.1rem;">'
        f'{av_click}'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="font-size:1.3rem;font-weight:700;color:#e2e8f0;'
        f'line-height:1.25;word-break:break-word;">'
        f'{project.get("project_name","Proyecto")}</div>'
        f''
        f'<div style="color:#4b5563;font-size:.76rem;margin-top:.35rem;">{meta_str}</div>'
        f'{contact_html}'
        + (
            f'<div style="color:#6b7280;font-size:.8rem;margin-top:.35rem;">'
            f'{project.get("description","")[:120]}'
            f'{"…" if len(project.get("description") or "") > 120 else ""}</div>'
            if project.get("description") else ""
        )
        + f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # ── Hero toolbar: native Streamlit buttons ─────────────────────────────────
    _, _col_add, _col_edit, _col_del = st.columns([4.8, 1.2, 1, 1])
    with _col_add:
        if st.button("＋ Agregar req", key=f"hero_add_{run_id}"):
            _add_req_to_project_dialog(run_id)
    with _col_edit:
        if st.button("✎ Editar", key=f"hero_edit_{run_id}"):
            _edit_project_modal(run_id, project)
    with _col_del:
        if st.button("🗑 Eliminar", key=f"hero_del_{run_id}"):
            _delete_project_dialog(run_id, project, _has_analysis)

    # ── Hidden logo uploader (JS-triggered via click on .qa-dlog-wrap) ───────
    st.markdown('<div id="qa-det-logo-anchor"></div>', unsafe_allow_html=True)
    logo_up = st.file_uploader(
        "Logo", type=["jpg", "jpeg", "png", "webp"],
        key=f"logo_up_{run_id}", label_visibility="collapsed",
    )
    if logo_up:
        if logo_up.size > 5 * 1024 * 1024:
            st.error("El logo supera 5 MB.")
        else:
            with st.spinner("Guardando logo…"):
                res = api.upload_file(
                    f"{BACKEND}/projects/{run_id}/logo",
                    logo_up.getvalue(), logo_up.name,
                    logo_up.type or "image/jpeg",
                )
            if res:
                st.session_state.pop(f"_logo_b64_{run_id}", None)
                st.rerun()
    components.html(_DET_LOGO_JS, height=0, scrolling=False)

    # ── Tabs de detalle ───────────────────────────────────────────────────────
    reqs        = api.get(f"{BACKEND}/projects/{run_id}/requirements") or []
    _req_count  = len(reqs)
    _team_count = len(project.get("assigned_analysts") or [])
    tab_team, tab_reqs = st.tabs([
        f"Equipo ({_team_count})",
        f"Requerimientos ({_req_count})",
    ])
    with tab_team:
        _section_assign_analysts(run_id, project)
    with tab_reqs:
        _section_reqs_v2(run_id, reqs, project)


@st.dialog("Agregar requerimiento", width="large")
def _add_req_to_project_dialog(run_id: str) -> None:
    _k_title   = f"_ard_title_{run_id}"
    _k_content = f"_ard_content_{run_id}"
    _k_file    = f"_ard_file_{run_id}"
    _k_loaded  = f"_ard_loaded_{run_id}"

    st.text_input("Título *", key=_k_title,
                  placeholder="Ej: Módulo de autenticación SSO")

    uploaded = st.file_uploader(
        "Adjuntar archivo (opcional)",
        type=["txt", "pdf", "docx"],
        key=_k_file,
        help="El texto extraído se colocará automáticamente en el campo de requerimiento",
    )
    if uploaded:
        fname = uploaded.name
        if fname != st.session_state.get(_k_loaded):
            extracted = _extract_req_text(uploaded)
            st.session_state[_k_content] = extracted
            st.session_state[_k_loaded]  = fname

    st.text_area("Requerimiento *", key=_k_content,
                 height=180, placeholder="Describe el requerimiento de forma libre…")

    col_c, col_s = st.columns([1, 2])
    with col_c:
        if st.button("Cancelar", use_container_width=True, key=f"_ard_cancel_{run_id}"):
            for k in [_k_title, _k_content, _k_file, _k_loaded]:
                st.session_state.pop(k, None)
            st.rerun()
    with col_s:
        if st.button("Agregar", type="primary", use_container_width=True, key=f"_ard_ok_{run_id}"):
            title   = st.session_state.get(_k_title, "").strip()
            content = st.session_state.get(_k_content, "").strip()
            errs: list[str] = []
            if not title:
                errs.append("El título es obligatorio.")
            if len(content) < 20:
                errs.append("El requerimiento debe tener al menos 20 caracteres.")
            if errs:
                for e in errs:
                    st.error(e)
                return
            attachment = st.session_state.pop(_k_loaded, None)
            payload: dict = {"title": title, "content": content}
            if attachment:
                payload["attachment_name"] = attachment
            result = api.post(f"{BACKEND}/projects/{run_id}/requirements", payload)
            if result is not None:
                for k in [_k_title, _k_content, _k_file]:
                    st.session_state.pop(k, None)
                st.rerun()


@st.dialog("Editar proyecto", width="large")
def _edit_project_modal(run_id: str, project: dict) -> None:
    client        = project.get("client_name") or ""
    contact_name  = project.get("contact_name") or ""
    contact_email = project.get("contact_email") or ""

    new_pname   = st.text_input("Nombre del proyecto",
                                value=project.get("project_name", ""))
    ec1, ec2 = st.columns(2)
    with ec1:
        new_client  = st.text_input("Cliente", value=client)
        new_contact = st.text_input("Nombre del contacto", value=contact_name)
    with ec2:
        new_email = st.text_input("Email del contacto", value=contact_email)

    st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
    col_c, col_s = st.columns([1, 2])
    with col_c:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with col_s:
        if st.button("Guardar cambios", type="primary", use_container_width=True):
            if new_email.strip() and not _EMAIL_RE.match(new_email.strip()):
                st.error("El email no es válido.")
            else:
                payload: dict = {}
                if new_pname.strip():
                    payload["project_name"] = new_pname.strip()
                payload["client_name"]   = new_client.strip() or None
                payload["contact_name"]  = new_contact.strip() or None
                payload["contact_email"] = new_email.strip() or None
                result = api.patch(f"{BACKEND}/projects/{run_id}", payload)
                if result is not None:
                    st.rerun()


def _delete_project_dialog(run_id: str, project: dict, has_analysis: bool) -> None:
    """Schedules an inline delete confirmation (no dialog — avoids backdrop overlay bug)."""
    st.session_state["_del_pending"] = {
        "rid": run_id,
        "pname": project.get("project_name", "este proyecto"),
        "has_analysis": has_analysis,
    }
    st.rerun()


def _render_del_confirm() -> None:
    """Renders inline delete confirmation panel when a delete is pending.
    Must be called at the top of both list and detail views."""
    pending = st.session_state.get("_del_pending")
    if not pending:
        return

    rid = pending["rid"]
    pname = pending["pname"]
    has_analysis = pending["has_analysis"]

    if has_analysis:
        body_html = (
            f'<div style="color:#f87171;font-weight:700;font-size:.95rem;margin-bottom:.35rem;">'
            f'⚠ Acción irreversible</div>'
            f'<div style="color:#fca5a5;font-size:.84rem;line-height:1.55;">'
            f'Este proyecto tiene análisis de requerimientos, historias de usuario, '
            f'criterios de aceptación y test cases. '
            f'<strong>Todo será eliminado permanentemente.</strong></div>'
        )
    else:
        body_html = (
            f'<div style="color:#f87171;font-weight:700;font-size:.95rem;margin-bottom:.35rem;">'
            f'Eliminar proyecto</div>'
            f'<div style="color:#d1d5db;font-size:.88rem;line-height:1.55;">'
            f'¿Eliminar <strong style="color:#e2e8f0;">{pname}</strong>? '
            f'Se borrarán sus requerimientos y miembros asignados. '
            f'Esta acción no se puede deshacer.</div>'
        )

    st.markdown(
        f'<div style="background:#1c0a0a;border:1px solid #7f1d1d;border-radius:10px;'
        f'padding:.85rem 1.1rem;margin-bottom:.75rem;">'
        f'{body_html}</div>',
        unsafe_allow_html=True,
    )

    confirmed = True
    if has_analysis:
        st.markdown(
            f'<div style="color:#9ca3af;font-size:.83rem;margin-bottom:.25rem;">'
            f'Escribe <strong style="color:#e2e8f0;">{pname}</strong> para confirmar:</div>',
            unsafe_allow_html=True,
        )
        typed = st.text_input("", key="_del_confirm_name",
                              label_visibility="collapsed", placeholder=pname)
        confirmed = typed.strip() == pname.strip()

    # Style the confirm button red; scoped via data-qa-del-red span in last column.
    col_c, col_d = st.columns([1, 2])
    with col_c:
        if st.button("Cancelar", key="_del_cancel_btn", use_container_width=True):
            st.session_state.pop("_del_pending", None)
            st.rerun()
    with col_d:
        btn_label = "Eliminar proyecto" if has_analysis else "Aceptar, eliminar"
        if st.button(btn_label, key="_del_confirm_btn", type="primary",
                     use_container_width=True, disabled=not confirmed):
            with st.spinner("Eliminando…"):
                api.delete(f"{BACKEND}/projects/{rid}")
            st.session_state.pop("_del_pending", None)
            st.session_state.scrum_selected_project = None
            st.session_state.pop("_sp_user_map", None)
            st.rerun()

    st.markdown(
        '<hr style="border:none;border-top:1px solid #21262d;margin:.75rem 0 .5rem;">',
        unsafe_allow_html=True,
    )


# CSS shared for logo hover effect (injected once)
_DET_LOGO_CSS = """<style>
.qa-dlog-wrap{position:relative;cursor:pointer;border-radius:50%;display:inline-block;flex-shrink:0;}
.qa-dlog-ov{
  position:absolute;inset:0;border-radius:50%;
  background:rgba(0,0,0,.62);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  opacity:0;transition:opacity .18s;pointer-events:none;gap:3px;
}
.qa-dlog-wrap:hover .qa-dlog-ov{opacity:1;}
.qa-dlog-ov-txt{color:#e2e8f0;font-size:.58rem;font-family:sans-serif;font-weight:600;
  letter-spacing:.03em;text-transform:uppercase;}
</style>"""

# JS: logo upload + custom team multiselect
_DET_LOGO_JS = """<script>
(function(){
  var D=window.parent.document,W=window.parent;

  function childOfVB(el){
    while(el&&el.parentElement){
      if(el.parentElement.getAttribute('data-testid')==='stVerticalBlock') return el;
      el=el.parentElement;
    }
    return null;
  }

  function findUL(anId){
    var a=D.getElementById(anId);
    if(!a)return null;
    var c=childOfVB(a);
    if(!c)return null;
    var n=c.nextElementSibling;
    while(n){
      if(n.querySelector('[data-testid="stFileUploader"]')||
         n.getAttribute('data-testid')==='stFileUploader') return n;
      n=n.nextElementSibling;
    }
    return null;
  }

  function hideBlock(b){
    if(!b)return;
    b.style.visibility='hidden';b.style.height='0';b.style.minHeight='0';
    b.style.maxHeight='0';b.style.overflow='hidden';b.style.margin='0';b.style.padding='0';
  }

  function hideLogoUL(){hideBlock(findUL('qa-det-logo-anchor'));}

  function triggerLogoUpload(){
    var b=findUL('qa-det-logo-anchor');
    if(!b)return;
    var inp=b.querySelector('input[type="file"]');
    if(inp){inp.click();return;}
    b.style.visibility='visible';b.style.height='auto';
    b.style.maxHeight='none';b.style.overflow='visible';
    setTimeout(hideLogoUL,600);
  }

  function attach(){
    var wrap=D.querySelector('.qa-dlog-wrap');
    if(!wrap||wrap._qaLogoAttached)return;
    wrap._qaLogoAttached=true;
    wrap.addEventListener('click',function(){triggerLogoUpload();});
  }

  // ── Wire ✕ remove-member buttons → hidden Streamlit button ─────────────
  function wireRmBtns(){
    D.querySelectorAll('[data-rm-member]').forEach(function(span){
      if(span._qaRmOk)return;
      var anchId=span.getAttribute('data-rm-anch');
      if(!anchId)return;
      var anch=D.getElementById(anchId);
      if(!anch)return;
      var c=childOfVB(anch);
      if(!c||!c.nextElementSibling)return;
      var btnBlock=c.nextElementSibling;
      var sb=btnBlock.querySelector('button');
      if(!sb)return;
      span._qaRmOk=true;
      hideBlock(btnBlock);
      span.addEventListener('click',function(e){
        e.preventDefault();e.stopPropagation();
        sb.click();
      });
    });
  }

  // ── Custom multiselect for adding team members ───────────────────────────
  function setupTeamMS(){
    var ms=D.getElementById('qa-tms-root');
    if(!ms||ms._qaOk)return;
    ms._qaOk=true;

    var trigger=ms.querySelector('#qa-tms-trigger');
    var panel=ms.querySelector('#qa-tms-panel');
    var lbl=ms.querySelector('#qa-tms-lbl');
    var actions=ms.querySelector('#qa-tms-actions');
    var addBtn=ms.querySelector('#qa-tms-addbtn');
    var runId=ms.getAttribute('data-rid');
    var sel=new Set();

    if(!trigger||!panel)return;

    trigger.addEventListener('click',function(e){
      e.stopPropagation();
      if(panel.style.display==='block'){panel.style.display='none';return;}
      var rect=trigger.getBoundingClientRect();
      panel.style.position='fixed';
      panel.style.top=(rect.bottom+4)+'px';
      panel.style.left=rect.left+'px';
      panel.style.width=rect.width+'px';
      panel.style.zIndex='99990';
      panel.style.display='block';
    });

    ms.querySelectorAll('.qa-tms-opt').forEach(function(opt){
      opt.addEventListener('mouseover',function(){
        if(!sel.has(opt.getAttribute('data-email'))) opt.style.background='rgba(255,255,255,.04)';
      });
      opt.addEventListener('mouseout',function(){
        if(!sel.has(opt.getAttribute('data-email'))) opt.style.background='';
      });
      opt.addEventListener('click',function(e){
        e.stopPropagation();
        var email=opt.getAttribute('data-email');
        var chk=opt.querySelector('.qa-tms-chk');
        if(sel.has(email)){
          sel.delete(email);
          opt.style.background='';
          if(chk){chk.style.opacity='0';chk.style.background='#1a1f2e';chk.style.borderColor='#30363d';}
        } else {
          sel.add(email);
          opt.style.background='rgba(8,145,178,.1)';
          if(chk){chk.style.opacity='1';chk.style.background='rgba(8,145,178,.18)';chk.style.borderColor='#0891b2';}
        }
        lbl.textContent=sel.size>0
          ? sel.size+(sel.size===1?' miembro seleccionado':' miembros seleccionados')
          : 'Seleccionar miembros…';
        lbl.style.color=sel.size>0?'#e2e8f0':'#8b949e';
        if(actions)actions.style.display=sel.size>0?'block':'none';
        if(addBtn)addBtn.textContent='Añadir '+sel.size+' miembro'+(sel.size===1?'':'s');
      });
    });

    if(addBtn){
      addBtn.addEventListener('click',function(e){
        e.stopPropagation();
        if(sel.size===0)return;
        panel.style.display='none';
        var u=new URL(W.location.href);
        u.searchParams.set('_team_add',Array.from(sel).join(','));
        u.searchParams.set('_team_proj',runId);
        W.location.replace(u.toString());
      });
    }

    D.addEventListener('click',function(){
      if(panel&&panel.style.display==='block') panel.style.display='none';
    });
  }

  if(!W._qaDetLogoObs){
    var _t=null;
    W._qaDetLogoObs=new MutationObserver(function(){
      clearTimeout(_t);_t=setTimeout(function(){
        hideLogoUL();setupTeamMS();wireRmBtns();
      },180);
    });
    W._qaDetLogoObs.observe(D.body,{childList:true,subtree:true});
  }

  setTimeout(function(){hideLogoUL();attach();setupTeamMS();wireRmBtns();},400);
})();
</script>"""


_BS = 'padding:.1rem .45rem;border-radius:8px;font-size:.72rem;'
_REQ_STATUS_BADGE = {
    "created":   f'<span style="background:#1e3a5f;color:#93c5fd;{_BS}">{icon("clock",11,"#93c5fd")} Pendiente</span>',
    "analyzing": f'<span style="background:#1c3a2a;color:#6ee7b7;{_BS}">{icon("rocket",11,"#6ee7b7")} Analizando</span>',
    "completed": f'<span style="background:#14532d;color:#86efac;{_BS}">{icon("check-circle",11,"#86efac")} Completado</span>',
}


def _section_requirement(run_id: str, _project: dict) -> None:
    reqs = api.get(f"{BACKEND}/projects/{run_id}/requirements") or []

    if not reqs:
        st.markdown(
            '<div style="background:#1a1108;border:1px solid #713f12;border-radius:8px;'
            'padding:.7rem 1rem;color:#fcd34d;font-size:.87rem;">'
            f'{icon("warning",13,"#fcd34d")}&nbsp;'
            'Este proyecto no tiene requerimientos. El analista no podrá iniciar el análisis.</div>',
            unsafe_allow_html=True,
        )
    else:
        for req in reqs:
            _req_card(run_id, req)

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    with st.expander("+ Agregar requerimiento", expanded=False):
        _req_add_form(run_id)


def _req_card(run_id: str, req: dict) -> None:
    req_id          = req["req_id"]
    title           = req.get("title", req_id)
    status          = req.get("status", "created")
    content         = req.get("content", "")
    refinements     = req.get("refinements") or []
    attachment_name = req.get("attachment_name") or ""

    badge_html  = _REQ_STATUS_BADGE.get(status, "")
    preview     = content[:140].replace("\n", " ") + ("…" if len(content) > 140 else "")
    attach_html = (
        f'<div style="margin-top:.25rem;">'
        f'<span style="background:#1e2533;border:1px solid #30363d;border-radius:6px;'
        f'padding:.1rem .45rem;font-size:.72rem;color:#7dd3fc;">'
        f'📎 {attachment_name}</span></div>'
    ) if attachment_name else ""

    st.markdown(
        f'<div style="background:#1a1f2e;border:1px solid #21262d;border-left:3px solid #00bcd4;'
        f'border-radius:0 8px 8px 0;padding:.7rem 1rem;margin-bottom:.5rem;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:.3rem;">'
        f'<span style="font-weight:600;color:#e2e8f0;font-size:.92rem;">{title}</span>'
        f'{badge_html}</div>'
        f'<div style="color:#64748b;font-size:.8rem;line-height:1.5;">{preview}</div>'
        f'{attach_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_exp, col_edit = st.columns([3, 1])
    with col_exp:
        with st.expander("Ver contenido completo"):
            st.text_area(
                "", value=content, height=130, disabled=True,
                label_visibility="collapsed", key=f"req_view_{req_id}",
            )
            if refinements:
                st.markdown(
                    f'<div style="color:#6b7280;font-size:.78rem;margin-top:.5rem;">'
                    f'{icon("clock",11,"#6b7280")} {len(refinements)} refinamiento(s)</div>',
                    unsafe_allow_html=True,
                )
                for ref in refinements:
                    rev_badge = _REVIEW_BADGE.get(ref.get("review_status") or "", "")
                    summary   = ref.get("summary") or {}
                    stories   = summary.get("total_stories", 0)
                    scenarios = summary.get("total_scenarios", 0)
                    meta = f"&nbsp;{stories} HU · {scenarios} tests" if stories else ""
                    st.markdown(
                        f'<div style="padding:.3rem 0;border-top:1px solid #1e2533;'
                        f'font-size:.79rem;color:#8b949e;">'
                        f'{ref.get("created_at","")[:16]} {rev_badge}{meta}'
                        f'&nbsp; por <span style="color:#7dd3fc;">{ref.get("created_by","")}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    with col_edit:
        with st.expander("Editar"):
            _req_edit_form(run_id, req_id, title, content)


def _req_add_form(run_id: str) -> None:
    _k_title   = f"_at_{run_id}"
    _k_content = f"_ac_{run_id}"
    _k_file    = f"_af_{run_id}"
    _k_loaded  = f"_al_{run_id}"

    st.text_input("Título *", key=_k_title,
                  placeholder="Ej: Módulo de autenticación SSO")

    uploaded = st.file_uploader(
        "Adjuntar archivo (opcional)",
        type=["txt", "pdf", "docx"],
        key=_k_file,
        help="El texto extraído se colocará automáticamente en el campo de requerimiento",
    )
    if uploaded:
        fname = uploaded.name
        if fname != st.session_state.get(_k_loaded):
            extracted = _extract_req_text(uploaded)
            st.session_state[_k_content] = extracted
            st.session_state[_k_loaded] = fname

    st.text_area("Requerimiento en bruto *", key=_k_content,
                 height=180, placeholder="Describe el requerimiento de forma libre…")

    if st.button("Agregar requerimiento", type="primary", use_container_width=True):
        title   = st.session_state.get(_k_title, "").strip()
        content = st.session_state.get(_k_content, "").strip()
        errors = []
        if not title:
            errors.append("El título es obligatorio.")
        if len(content) < 20:
            errors.append("El requerimiento debe tener al menos 20 caracteres.")
        for e in errors:
            st.error(e)
        if errors:
            return

        attachment_name = st.session_state.pop(_k_loaded, None)
        payload: dict = {"title": title, "content": content}
        if attachment_name:
            payload["attachment_name"] = attachment_name

        result = api.post(
            f"{BACKEND}/projects/{run_id}/requirements",
            payload,
        )
        if result is not None:
            for k in [_k_title, _k_content, _k_file]:
                st.session_state.pop(k, None)
            st.rerun()


def _req_edit_form(run_id: str, req_id: str, current_title: str, current_content: str) -> None:
    with st.form(f"req_edit_{req_id}"):
        upd_title   = st.text_input("Título", value=current_title)
        upd_content = st.text_area("Contenido", value=current_content, height=150)
        save = st.form_submit_button("Guardar", type="primary", use_container_width=True)
    if save:
        if not upd_title.strip():
            st.error("El título es obligatorio.")
            return
        if len(upd_content.strip()) < 20:
            st.error("Mín. 20 caracteres.")
            return
        result = api.patch(
            f"{BACKEND}/projects/{run_id}/requirements/{req_id}",
            {"title": upd_title.strip(), "content": upd_content.strip()},
        )
        if result is not None:
            st.rerun()


def _section_assign_analysts(run_id: str, project: dict) -> None:
    assigned = list(project.get("assigned_analysts") or [])

    all_users  = api.get(f"{BACKEND}/auth/users") or []
    user_map   = {u["email"]: u for u in all_users}
    assignable = [u for u in all_users if u.get("is_active") and u.get("role") != "admin"]
    options    = [u["email"] for u in assignable]

    def _fmt(email: str) -> str:
        u    = user_map.get(email, {})
        name = u.get("name") or email.split("@")[0]
        role = _ROLE_LBL.get(u.get("role", ""), "")
        dev  = _DEV_TYPE_LBL.get(u.get("developer_type", ""), "")
        tag  = f"{role} · {dev}" if dev else role
        return f"{name} — {tag}" if tag else name

    col_members, col_assign = st.columns([3, 2])

    # ── Columna izquierda: miembros actuales ──────────────────────────────────
    with col_members:
        st.markdown(
            '<div style="color:#8b949e;font-size:.78rem;font-weight:600;'
            'text-transform:uppercase;letter-spacing:.04em;margin-bottom:.5rem;">'
            'Miembros del equipo</div>',
            unsafe_allow_html=True,
        )
        if not assigned:
            st.markdown(
                '<div style="color:#4b5563;font-size:.83rem;padding:.4rem 0;">'
                'Sin miembros asignados aún.</div>',
                unsafe_allow_html=True,
            )
        else:
            for email in assigned:
                u        = user_map.get(email, {})
                role     = u.get("role", "")
                dev_type = u.get("developer_type", "")
                name     = u.get("name") or email.split("@")[0]
                if role == "developer" and dev_type:
                    role_lbl = _DEV_TYPE_LBL.get(dev_type, dev_type)
                else:
                    role_lbl = _ROLE_LBL.get(role, role or "—")
                chip_style, fg, _ = _ROLE_CHIP.get(
                    role, ("background:#1a1f2e;border:1px solid #21262d;", "#c9d1d9", "")
                )
                safe_e  = re.sub(r'[^a-zA-Z0-9]', '_', email)
                anch_id = f"rm_anch_{safe_e}"
                st.markdown(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'background:#0d1117;border:1px solid #21262d;border-radius:8px;'
                    f'padding:.5rem .75rem;margin-bottom:.3rem;">'
                    f'<div>'
                    f'<div style="color:#e2e8f0;font-size:.87rem;font-weight:600;">{name}</div>'
                    f'<div style="color:#6b7280;font-size:.77rem;">{email}</div>'
                    f'<div style="margin-top:.2rem;">'
                    f'<span style="{chip_style}color:{fg};border-radius:9999px;'
                    f'font-size:.68rem;padding:.1rem .45rem;">{role_lbl}</span>'
                    f'</div></div>'
                    f'<span data-rm-member="{email}" data-rm-anch="{anch_id}" title="Quitar del equipo"'
                    f' style="display:inline-flex;align-items:center;justify-content:center;'
                    f'cursor:pointer;color:#0891b2;font-size:.85rem;'
                    f'padding:.25rem .45rem;border-radius:4px;line-height:1;">'
                    f'✕</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f'<div id="{anch_id}"></div>', unsafe_allow_html=True)
                if st.button("​", key=f"rm_btn_{safe_e}_{run_id}"):
                    api.delete(f"{BACKEND}/projects/{run_id}/team/{email}")
                    st.session_state.pop("_sp_user_map", None)
                    st.rerun()

    # ── Columna derecha: asignar miembros ─────────────────────────────────────
    with col_assign:
        st.markdown(
            '<div style="color:#8b949e;font-size:.78rem;font-weight:600;'
            'text-transform:uppercase;letter-spacing:.04em;margin-bottom:.5rem;">'
            'Asignar miembros</div>',
            unsafe_allow_html=True,
        )
        new_sel = st.multiselect(
            "Seleccionar",
            options=options,
            default=[e for e in assigned if e in options],
            format_func=_fmt,
            key=f"team_ms_{run_id}",
            placeholder="Buscar miembros…",
            label_visibility="collapsed",
        )
        if st.button("Guardar equipo", key=f"team_save_{run_id}", use_container_width=True, type="primary"):
            to_add    = set(new_sel) - set(assigned)
            to_remove = set(assigned) - set(new_sel)
            for email in to_add:
                api.post(f"{BACKEND}/projects/{run_id}/assign-analyst",
                         {"analyst_email": email}, suppress_codes=(400, 409))
            for email in to_remove:
                api.delete(f"{BACKEND}/projects/{run_id}/team/{email}")
            st.session_state.pop("_sp_user_map", None)
            st.rerun()


def _start_jira_thread(run_id: str, req_id: str, ref_run_id: str) -> str:
    """Launches background Jira export thread. Returns the store_key."""
    store_key = f"jira_{run_id}_{req_id}"
    if store_key in _JIRA_STORE:
        return store_key
    _token = st.session_state.get("token")
    _headers = {"Authorization": f"Bearer {_token}"} if _token else {}
    store: dict = {
        "running": True, "result": None, "error": None,
        "cancelled": False, "start_time": time.time(),
        "run_id": run_id, "req_id": req_id,
    }
    _JIRA_STORE[store_key] = store

    def _worker() -> None:
        try:
            r = httpx.post(
                f"{BACKEND}/projects/{run_id}/jira",
                json={"req_id": req_id, "ref_run_id": ref_run_id},
                headers=_headers,
                timeout=120,
            )
            if not r.is_success:
                try:
                    detail = r.json().get("detail", r.text)
                except Exception:
                    detail = r.text
                store["error"] = detail
                return
            store["result"] = r.json()
        except Exception as exc:  # noqa: BLE001
            store["error"] = str(exc)
        finally:
            store["running"] = False

    threading.Thread(target=_worker, daemon=True).start()
    return store_key


@st.dialog("Exportando a Jira", width="small")
def _jira_progress_dialog(store_key: str, done_key: str) -> None:
    """Progress dialog for Jira export thread."""
    store = _JIRA_STORE.get(store_key)
    if store is None:
        st.rerun()
        return

    if store.get("running"):
        elapsed = int(time.time() - store.get("start_time", time.time()))
        mins, secs = divmod(elapsed, 60)
        step_idx = min(elapsed // 9, len(_JIRA_STEPS) - 1)
        current_step = _JIRA_STEPS[step_idx]

        st.markdown(
            '<style>@keyframes jira-spin{to{transform:rotate(360deg);}}'
            '#jira-ring{width:40px;height:40px;border:3px solid #21262d;'
            'border-top:3px solid #0052cc;border-radius:50%;'
            'animation:jira-spin 1s linear infinite;margin:1rem auto .9rem;}</style>'
            '<div id="jira-ring"></div>'
            '<div style="text-align:center;">'
            '<div style="font-weight:700;color:#e2e8f0;font-size:.97rem;margin-bottom:.35rem;">'
            'Exportando a Jira</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="text-align:center;color:#8b949e;font-size:.85rem;margin-bottom:.6rem;">'
            f'{current_step}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="text-align:center;color:#0052cc;font-size:.88rem;'
            f'font-weight:600;margin-bottom:.9rem;">⏱ {mins:02d}:{secs:02d} transcurridos</div>',
            unsafe_allow_html=True,
        )
        if st.button("⏹ Cancelar", use_container_width=True, key=f"jira_stop_{store_key}"):
            store["cancelled"] = True
            store["running"] = False
            _JIRA_STORE.pop(store_key, None)
            st.rerun()
        time.sleep(1.5)
        st.rerun()
        return

    # Thread done
    result = store.get("result")
    error  = store.get("error")
    _JIRA_STORE.pop(store_key, None)

    if store.get("cancelled"):
        st.rerun()
        return
    if error:
        st.error(f"Error exportando a Jira: {error}")
        return
    if result:
        st.session_state[done_key] = result
    st.rerun()


def _section_req_jira_export(
    run_id: str, req_id: str, ref_run_id: str, project: dict
) -> None:
    """Per-requirement Jira export section rendered inside _render_req_panel_v2."""
    done_key = f"_jira_done_{req_id}"
    store_key = f"jira_{run_id}_{req_id}"

    # Fresh result from completed thread takes priority over persisted data
    fresh = st.session_state.pop(done_key, None)
    jira_exports = project.get("jira_exports") or {}
    jira_export = fresh or jira_exports.get(req_id)

    _section_divider("Exportar a Jira", "arrow-up-tray")

    if jira_export:
        proj_key    = jira_export.get("jira_project_key", "")
        proj_url    = jira_export.get("jira_project_url") or "#"
        epic_url    = (jira_export.get("epic") or {}).get("url", "#")
        epic_key    = (jira_export.get("epic") or {}).get("key", "")
        exported_at = str(jira_export.get("exported_at", ""))[:16]
        total       = jira_export.get("total_created", 0)
        st.markdown(
            f'<div style="background:#052e16;border:1px solid #166534;border-radius:8px;'
            f'padding:.75rem 1rem;display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem;">'
            f'{icon("check-circle",16,"#4ade80")}'
            f'<div><div style="color:#4ade80;font-size:.88rem;font-weight:600;">'
            f'Exportado el {exported_at} · {total} tickets</div>'
            f'<div style="color:#86efac;font-size:.8rem;">'
            f'Proyecto: <a href="{proj_url}" target="_blank" style="color:#86efac;">{proj_key}</a>'
            f'&nbsp;·&nbsp;Epic: '
            f'<a href="{epic_url}" target="_blank" style="color:#86efac;">{epic_key}</a>'
            f'</div></div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="color:#6b7280;font-size:.82rem;margin-bottom:.5rem;">'
            'Crea proyecto + Epic → Story → Sub-task automáticamente en Jira.</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Exportar a Jira →", type="primary",
            use_container_width=True, key=f"jira_btn_{req_id}",
        ):
            _start_jira_thread(run_id, req_id, ref_run_id)
        if store_key in _JIRA_STORE:
            _jira_progress_dialog(store_key, done_key)


# ── Helpers shared by artifact tabs ──────────────────────────────────────────

def _empty_tab(message: str, hint: str = "") -> None:
    hint_html = (
        f'<div style="color:#374151;font-size:.78rem;margin-top:.3rem;">{hint}</div>'
        if hint else ""
    )
    st.markdown(
        f'<div style="background:#0d1117;border:1px dashed #21262d;border-radius:10px;'
        f'padding:2rem 1.5rem;text-align:center;margin-top:.75rem;">'
        f'<div style="color:#4b5563;font-size:.9rem;">{message}</div>'
        f'{hint_html}</div>',
        unsafe_allow_html=True,
    )


# ── Tab: Historias de usuario ─────────────────────────────────────────────────

def _section_user_stories(run_id: str, project: dict) -> None:
    report_data = project.get("report_data") or {}
    stories = report_data.get("user_stories") or []

    if not stories:
        _empty_tab(
            "No hay historias de usuario generadas aún.",
            "Analiza un requerimiento para que los agentes generen las historias.",
        )
        return

    assignments_data = api.get(f"{BACKEND}/projects/{run_id}/assignments") or []
    assigned_map: dict[str, str] = {a["story_id"]: a["developer_email"] for a in assignments_data}

    all_users = api.get(f"{BACKEND}/auth/users") or []
    developers = [u for u in all_users if u.get("role") == "developer" and u.get("is_active")]
    dev_options: dict[str, str] = {
        u["email"]: u["email"].split("@")[0]
        + (f" · {_DEV_TYPE_LBL.get(u.get('developer_type', ''), '')}"
           if u.get("developer_type") else "")
        for u in developers
    }

    st.markdown(
        f'<div style="color:#6b7280;font-size:.8rem;margin-bottom:.5rem;">'
        f'{len(stories)} historia(s) de usuario</div>',
        unsafe_allow_html=True,
    )

    _PRIO_COLOR = {"High": "#f97316", "Medium": "#facc15", "Low": "#6b7280"}

    for story in stories:
        story_id    = story.get("id", "")
        title       = story.get("title", story_id)
        priority    = story.get("priority", "")
        story_type  = story.get("story_type", "")
        as_a        = story.get("as_a", "")
        i_want      = story.get("i_want", "")
        so_that     = story.get("so_that", "")
        biz_rules   = story.get("business_rules") or []
        acs         = story.get("acceptance_criteria") or []
        current_dev = assigned_map.get(story_id)
        prio_color  = _PRIO_COLOR.get(priority, "#6b7280")

        assigned_lbl = (
            f'<span style="color:#6ee7b7;font-size:.72rem;">'
            f'{icon("check-circle",10,"#6ee7b7")} {current_dev}</span>'
            if current_dev else
            f'<span style="color:#374151;font-size:.72rem;">Sin asignar</span>'
        )

        with st.expander(f"{story_id} — {title}"):
            st.markdown(
                f'<div style="color:#8b949e;font-style:italic;font-size:.88rem;'
                f'background:#161b22;border-left:3px solid #00bcd4;'
                f'padding:.45rem .75rem;border-radius:0 6px 6px 0;margin-bottom:.6rem;">'
                f'Como <strong style="color:#c9d1d9">{as_a}</strong>, '
                f'quiero <strong style="color:#c9d1d9">{i_want}</strong>, '
                f'para <strong style="color:#c9d1d9">{so_that}</strong>.'
                f'</div>',
                unsafe_allow_html=True,
            )
            meta_c1, meta_c2, meta_c3 = st.columns(3)
            with meta_c1:
                st.markdown(
                    f'<div style="color:#6b7280;font-size:.75rem;">Prioridad: '
                    f'<span style="color:{prio_color};font-weight:600;">{priority}</span></div>',
                    unsafe_allow_html=True,
                )
            with meta_c2:
                st.markdown(
                    f'<div style="color:#6b7280;font-size:.75rem;">Tipo: '
                    f'<span style="color:#c9d1d9;">{story_type}</span></div>',
                    unsafe_allow_html=True,
                )
            with meta_c3:
                st.markdown(
                    f'<div style="color:#6b7280;font-size:.75rem;">Desarrollador: '
                    f'{assigned_lbl}</div>',
                    unsafe_allow_html=True,
                )

            if biz_rules:
                st.markdown(
                    '<div style="color:#8b949e;font-size:.8rem;margin-top:.55rem;'
                    'font-weight:600;">Reglas de negocio</div>',
                    unsafe_allow_html=True,
                )
                for br in biz_rules:
                    st.markdown(
                        f'<div style="color:#c9d1d9;font-size:.82rem;padding:.1rem 0 .1rem .65rem;'
                        f'border-left:2px solid #21262d;">{br}</div>',
                        unsafe_allow_html=True,
                    )

            if acs:
                st.markdown(
                    f'<div style="color:#4b5563;font-size:.76rem;margin-top:.5rem;">'
                    f'{icon("check-circle",10,"#4b5563")} {len(acs)} criterio(s) de aceptación</div>',
                    unsafe_allow_html=True,
                )

            if dev_options:
                dev_emails  = list(dev_options.keys())
                default_idx = dev_emails.index(current_dev) if current_dev in dev_emails else 0
                _safe_sid2 = re.sub(r'[^a-zA-Z0-9]', '_', story_id)
                col_sel, col_btn = st.columns([5, 2])
                with col_sel:
                    selected_dev = st.selectbox(
                        "Asignar desarrollador",
                        dev_emails,
                        index=default_idx,
                        format_func=lambda e: dev_options.get(e, e),
                        key=f"dev_hu_{run_id}_{story_id}",
                    )
                with col_btn:
                    st.markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
                    if st.button("Asignar →", key=f"assign_hu_{run_id}_{story_id}",
                                 use_container_width=True):
                        result = api.post(
                            f"{BACKEND}/projects/{run_id}/stories/{story_id}/assign",
                            {"developer_email": selected_dev},
                        )
                        if result is not None:
                            st.rerun()
                if current_dev:
                    if st.button(
                        "✕ Desasignar", key=f"unassign_hu2_{run_id}_{_safe_sid2}",
                        use_container_width=True,
                    ):
                        api.delete(
                            f"{BACKEND}/projects/{run_id}/stories/{story_id}/assign"
                        )
                        st.rerun()


# ── Tab: Criterios de aceptación ──────────────────────────────────────────────

def _section_acceptance_criteria(run_id: str, project: dict) -> None:  # noqa: ARG001
    report_data = project.get("report_data") or {}
    stories = report_data.get("user_stories") or []
    total_acs = sum(len(s.get("acceptance_criteria") or []) for s in stories)

    if not total_acs:
        _empty_tab(
            "No hay criterios de aceptación generados aún.",
            "Completa el análisis de al menos un requerimiento.",
        )
        return

    st.markdown(
        f'<div style="color:#6b7280;font-size:.8rem;margin-bottom:.5rem;">'
        f'{total_acs} criterio(s) en {len(stories)} historia(s)</div>',
        unsafe_allow_html=True,
    )

    for story in stories:
        acs = story.get("acceptance_criteria") or []
        if not acs:
            continue
        story_title = story.get("title", story.get("id", ""))
        st.markdown(
            f'<div style="color:#00bcd4;font-size:.82rem;font-weight:600;'
            f'margin-top:.9rem;margin-bottom:.35rem;text-transform:uppercase;'
            f'letter-spacing:.06em;">{story_title}</div>',
            unsafe_allow_html=True,
        )
        for ac in acs:
            ac_id   = ac.get("id", "")
            desc    = ac.get("description", "")
            given   = ac.get("given", "")
            when    = ac.get("when", "")
            then    = ac.get("then", "")
            is_neg  = ac.get("is_negative_case", False)
            neg_tag = (
                '<span style="background:#431407;color:#f97316;border-radius:4px;'
                'padding:.05rem .3rem;font-size:.68rem;margin-left:.4rem;">NEG</span>'
                if is_neg else ""
            )
            st.markdown(
                f'<div style="background:#1a1f2e;border:1px solid #21262d;'
                f'border-radius:8px;padding:.6rem .85rem;margin-bottom:.4rem;">'
                f'<div style="color:#c9d1d9;font-size:.86rem;font-weight:600;'
                f'margin-bottom:.35rem;">{ac_id}{neg_tag} — {desc}</div>'
                f'<div style="font-size:.8rem;line-height:1.85;color:#8b949e;">'
                f'<span style="color:#60a5fa;font-weight:600;display:inline-block;width:3.5rem;">Given</span>{given}<br>'
                f'<span style="color:#a78bfa;font-weight:600;display:inline-block;width:3.5rem;">When</span>{when}<br>'
                f'<span style="color:#34d399;font-weight:600;display:inline-block;width:3.5rem;">Then</span>{then}'
                f'</div></div>',
                unsafe_allow_html=True,
            )


# ── Tab: Test cases (Gherkin) ─────────────────────────────────────────────────

def _section_test_cases(run_id: str, project: dict) -> None:  # noqa: ARG001
    report_data = project.get("report_data") or {}
    features    = report_data.get("features") or []
    total_sc    = sum(len(f.get("scenarios") or []) for f in features)

    if not total_sc:
        _empty_tab(
            "No hay test cases generados aún.",
            "El agente de test cases se ejecuta tras la revisión HITL del analista.",
        )
        return

    st.markdown(
        f'<div style="color:#6b7280;font-size:.8rem;margin-bottom:.5rem;">'
        f'{total_sc} escenario(s) en {len(features)} feature(s)</div>',
        unsafe_allow_html=True,
    )

    _KW_COLOR = {
        "Given": "#60a5fa", "When": "#a78bfa", "Then": "#34d399",
        "And": "#8b949e", "But": "#f87171",
    }

    for feature in features:
        feature_name = feature.get("name", "")
        feature_desc = feature.get("description", "")
        scenarios    = feature.get("scenarios") or []

        with st.expander(f"Feature: {feature_name}"):
            if feature_desc:
                st.markdown(
                    f'<div style="color:#6b7280;font-size:.82rem;margin-bottom:.5rem;">'
                    f'{feature_desc}</div>',
                    unsafe_allow_html=True,
                )
            for sc in scenarios:
                sc_name  = sc.get("name", "")
                sc_type  = sc.get("scenario_type", "")
                quality  = sc.get("quality_characteristic", "")
                tags     = sc.get("tags") or []
                steps    = sc.get("steps") or []

                tags_html = " ".join(
                    f'<span style="background:#1e3a4a;color:#7dd3fc;border-radius:4px;'
                    f'padding:.04rem .32rem;font-size:.68rem;">@{t}</span>'
                    for t in tags
                )
                steps_html = ""
                for step in steps:
                    kw  = step.get("keyword", "")
                    txt = step.get("text", "")
                    c   = _KW_COLOR.get(kw, "#8b949e")
                    steps_html += (
                        f'<div><span style="color:{c};font-weight:600;'
                        f'display:inline-block;width:3.5rem;">{kw}</span>{txt}</div>'
                    )

                quality_row = (
                    f'<div style="color:#374151;font-size:.7rem;margin-top:.3rem;">'
                    f'ISO 25010: {quality}</div>'
                ) if quality else ""

                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #21262d;'
                    f'border-radius:8px;padding:.6rem .85rem;margin-bottom:.45rem;">'
                    f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:.4rem;'
                    f'margin-bottom:.4rem;">'
                    f'<span style="color:#e2e8f0;font-size:.87rem;font-weight:600;">{sc_name}</span>'
                    f'<span style="color:#4b5563;font-size:.72rem;">{sc_type}</span>'
                    f'{tags_html}</div>'
                    f'<div style="font-family:monospace;font-size:.78rem;line-height:1.85;">'
                    f'{steps_html}</div>'
                    f'{quality_row}</div>',
                    unsafe_allow_html=True,
                )


# ── Tab: Comentarios ─────────────────────────────────────────────────────────

_ACTION_LABEL = {
    "accepted":     ("✓ Aceptado",     "#14532d", "#86efac"),
    "modified":     ("✎ Modificado",   "#1c3a2a", "#6ee7b7"),
    "rejected":     ("✗ Rechazado",    "#431407", "#f97316"),
    "reclassified": ("⇄ Reclasificado","#1e3a5f", "#93c5fd"),
}


def _section_comments_tab(ref_data: dict) -> None:
    """Shows global analyst feedback and per-scenario review notes."""
    report_data = ref_data.get("report_data") or {}
    hitl        = report_data.get("hitl") or {}
    feedback    = hitl.get("analyst_feedback") or ""
    changes     = hitl.get("changes") or []
    ambiguities = hitl.get("ambiguities_resolved") or []

    # ── Comentario global ─────────────────────────────────────────────────────
    if feedback:
        st.markdown(
            f'<div style="background:#161b22;border:1px solid #21262d;'
            f'border-left:3px solid #00bcd4;border-radius:0 8px 8px 0;'
            f'padding:.65rem 1rem;margin-bottom:.75rem;">'
            f'<div style="color:#6b7280;font-size:.72rem;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem;">Feedback global</div>'
            f'<div style="color:#c9d1d9;font-size:.85rem;line-height:1.6;">{feedback}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Comentarios por escenario ─────────────────────────────────────────────
    noted = [c for c in changes if c.get("notes")]
    if noted:
        st.markdown(
            f'<div style="color:#6b7280;font-size:.78rem;margin-bottom:.45rem;">'
            f'{len(noted)} comentario(s) de revisión por escenario</div>',
            unsafe_allow_html=True,
        )
        for ch in noted:
            action   = ch.get("action", "")
            label, bg, fc = _ACTION_LABEL.get(action, (action, "#21262d", "#8b949e"))
            sc_name  = ch.get("scenario_name", "—")
            notes    = ch.get("notes", "")
            ts       = (ch.get("timestamp") or "")[:16]
            st.markdown(
                f'<div style="background:#0d1117;border:1px solid #21262d;'
                f'border-radius:6px;padding:.55rem .85rem;margin-bottom:.35rem;">'
                f'<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;'
                f'margin-bottom:.3rem;">'
                f'<span style="background:{bg};color:{fc};border-radius:4px;'
                f'padding:.05rem .35rem;font-size:.72rem;font-weight:600;">{label}</span>'
                f'<span style="color:#c9d1d9;font-size:.83rem;font-weight:600;">{sc_name}</span>'
                f'{"<span style=color:#4b5563;font-size:.72rem;>" + ts + "</span>" if ts else ""}'
                f'</div>'
                f'<div style="color:#8b949e;font-size:.82rem;line-height:1.6;">{notes}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    elif not feedback:
        st.markdown(
            '<div style="color:#4b5563;font-size:.85rem;padding:.5rem 0;">'
            'No hay comentarios de revisión para este análisis.</div>',
            unsafe_allow_html=True,
        )

    # ── Ambigüedades resueltas ────────────────────────────────────────────────
    if ambiguities:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        with st.expander(f"Ambigüedades resueltas ({len(ambiguities)})"):
            for amb in ambiguities:
                orig       = amb.get("original_text", "")
                resolution = amb.get("resolution", "")
                assumption = amb.get("assumption_made", False)
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #21262d;'
                    f'border-left:2px solid #f59e0b;border-radius:0 6px 6px 0;'
                    f'padding:.5rem .8rem;margin-bottom:.35rem;">'
                    f'<div style="color:#fcd34d;font-size:.79rem;margin-bottom:.2rem;">{orig}</div>'
                    f'<div style="color:#c9d1d9;font-size:.82rem;line-height:1.55;">{resolution}</div>'
                    + (
                        '<div style="color:#f97316;font-size:.72rem;margin-top:.2rem;">'
                        '⚠ Asunción aplicada</div>'
                        if assumption else ""
                    )
                    + f'</div>',
                    unsafe_allow_html=True,
                )


# ── Tab: Reporte ──────────────────────────────────────────────────────────────

def _section_report_tab(run_id: str, project: dict) -> None:
    report_data = project.get("report_data")
    summary     = (project.get("report_data") or {}).get("summary") or project.get("summary") or {}

    if not report_data:
        _empty_tab(
            "No hay reporte generado aún.",
            "Completa el flujo HITL para generar el reporte ejecutivo.",
        )
        return

    # ── Métricas resumen ──────────────────────────────────────────────────────
    mc1, mc2, mc3, mc4 = st.columns(4)
    _metrics = [
        (mc1, "Historias",   str(summary.get("total_stories", 0)),    "#00bcd4"),
        (mc2, "Escenarios",  str(summary.get("total_scenarios", 0)),   "#a78bfa"),
        (mc3, "Cobertura",   f'{summary.get("coverage_pct", 0)}%',    "#4ade80"),
        (mc4, "LLM",         summary.get("llm_provider", "—"),         "#f97316"),
    ]
    for col, label, value, color in _metrics:
        with col:
            st.markdown(
                f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
                f'padding:.6rem .85rem;text-align:center;margin-bottom:.5rem;">'
                f'<div style="color:#6b7280;font-size:.7rem;text-transform:uppercase;'
                f'letter-spacing:.07em;margin-bottom:.2rem;">{label}</div>'
                f'<div style="color:{color};font-size:1.35rem;font-weight:700;">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Code quality tiles (if available) ────────────────────────────────────
    ref_data_local = _get_refinement_data(run_id) if run_id else {}
    qs_rep = ref_data_local.get("quality_summary") or {}
    cr_rep = ref_data_local.get("coverage_report") or {}
    cmmi_rep = ref_data_local.get("cmmi_l3_compliant")
    if qs_rep or cr_rep:
        st.markdown(
            '<div style="color:#6b7280;font-size:.72rem;text-transform:uppercase;'
            'letter-spacing:.06em;margin:.4rem 0 .3rem;">Calidad de código generado</div>',
            unsafe_allow_html=True,
        )
        qc1, qc2, qc3, qc4 = st.columns(4)
        mi_val = qs_rep.get("maintainability_index")
        _qtiles = [
            (qc1, "MI", f'{mi_val:.0f}/100' if mi_val is not None else "—", "#f97316"),
            (qc2, "Fnc > umbral", str(qs_rep.get("functions_exceeding_threshold", "—")), "#f87171"),
            (qc3, "Branch Cov.", f'{cr_rep.get("branch_coverage_pct", 0):.0f}%' if cr_rep else "—", "#4ade80"),
            (qc4, "CMMI L3", "✓ Sí" if cmmi_rep else ("✗ No" if cmmi_rep is False else "—"), "#4ade80" if cmmi_rep else "#f87171"),
        ]
        for col, label, value, color in _qtiles:
            with col:
                st.markdown(
                    f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
                    f'padding:.5rem .7rem;text-align:center;margin-bottom:.5rem;">'
                    f'<div style="color:#6b7280;font-size:.65rem;text-transform:uppercase;'
                    f'letter-spacing:.07em;margin-bottom:.15rem;">{label}</div>'
                    f'<div style="color:{color};font-size:1.1rem;font-weight:700;">{value}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    if st.button(
        "Ver reporte ejecutivo completo →",
        type="primary",
        use_container_width=True,
        key=f"rep_full_{run_id}",
    ):
        existing_ids = {p["run_id"] for p in st.session_state.projects}
        if run_id not in existing_ids:
            st.session_state.projects.insert(0, project)
        st.session_state.active_project = run_id
        st.session_state.view = "report"
        st.session_state.scrum_selected_project = None
        st.rerun()



# ── Requerimientos v2: master-detail ──────────────────────────────────────────

def _get_refinement_data(ref_run_id: str) -> dict:
    """Fetch and cache full pipeline data for a refinement run."""
    cache_key = f"_ref_cache_{ref_run_id}"
    if cache_key not in st.session_state:
        data = api.get(f"{BACKEND}/pipeline/projects/{ref_run_id}") or {}
        st.session_state[cache_key] = data
    return st.session_state[cache_key]


_REQ_LIST_CSS = """<style>
/* Hide native buttons — kept in DOM so JS can click them */
[class*="st-key-req_sel_"] {
  position:absolute!important;top:-9999px!important;
  left:-9999px!important;width:1px!important;height:1px!important;
  overflow:hidden!important;pointer-events:none!important;
}
</style>"""


def _section_reqs_v2(run_id: str, reqs: list, project: dict) -> None:
    """Master-detail requirements view inside the Requerimientos tab."""
    if not reqs:
        st.markdown(
            '<div style="background:#1a1108;border:1px solid #713f12;border-radius:8px;'
            'padding:.7rem 1rem;color:#fcd34d;font-size:.87rem;">'
            f'{icon("warning",13,"#fcd34d")}&nbsp;'
            'Este proyecto no tiene requerimientos. Usa el botón '
            '<strong>＋ Agregar req</strong> en la cabecera del proyecto.</div>',
            unsafe_allow_html=True,
        )
        return

    sel_key   = f"_sel_req_{run_id}"
    valid_ids = {r["req_id"] for r in reqs}
    if st.session_state.get(sel_key) not in valid_ids:
        st.session_state[sel_key] = reqs[0]["req_id"]

    col_list, col_detail = st.columns([1, 2.5])

    with col_list:
        _render_req_list_v2(run_id, reqs, st.session_state[sel_key], sel_key)

    with col_detail:
        sel_req = next((r for r in reqs if r["req_id"] == st.session_state[sel_key]), reqs[0])
        _render_req_panel_v2(run_id, sel_req, project)


_REVIEW_ICON = {
    "approved":       "✅",
    "rejected":       "❌",
    "needs_changes":  "⚠",
    "pending_review": "⏳",
}


def _render_req_list_v2(run_id: str, reqs: list, selected_id: str, sel_key: str) -> None:
    """Left-column requirement selector — compact scrollable HTML list."""
    st.markdown(_REQ_LIST_CSS, unsafe_allow_html=True)

    items_html = ""
    for req in reqs:
        req_id   = req["req_id"]
        title    = (req.get("title") or req_id).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        is_sel   = req_id == selected_id
        bg       = "#1a2744" if is_sel else "transparent"
        bl       = "#3b82f6" if is_sel else "#21262d"
        color    = "#93c5fd" if is_sel else "#c9d1d9"
        fw       = "600" if is_sel else "400"
        safe_key = f"req_sel_{run_id}_{req_id}"
        items_html += (
            f'<button onclick="clickSt(\'{safe_key}\')" '
            f'style="display:block;width:100%;text-align:left;background:{bg};'
            f'border:none;border-left:3px solid {bl};border-bottom:1px solid #21262d;'
            f'color:{color};font-weight:{fw};padding:.42rem .65rem;font-size:.82rem;'
            f'cursor:pointer;line-height:1.35;word-break:break-word;white-space:normal;">'
            f'{title}</button>'
        )

    scroll_h = min(len(reqs) * 46 + 4, 400)
    components.html(
        f'<style>button:hover{{background:#131d2e!important;color:#93c5fd!important;}}</style>'
        f'<div style="border:1px solid #21262d;border-radius:6px;'
        f'overflow-y:auto;max-height:{scroll_h}px;">'
        f'{items_html}</div>'
        f'<script>function clickSt(k){{'
        f'var b=window.parent.document.querySelector("[class*=\'st-key-"+k+"\'] button");'
        f'if(b)b.click();}}</script>',
        height=scroll_h + 10,
        scrolling=False,
    )

    # Hidden Streamlit buttons wired by the JS above
    for req in reqs:
        req_id  = req["req_id"]
        is_sel  = req_id == selected_id
        if st.button(
            req.get("title", req_id),
            key=f"req_sel_{run_id}_{req_id}",
            type="primary" if is_sel else "secondary",
        ) and not is_sel:
            st.session_state[sel_key] = req_id
            st.rerun()


@st.dialog("Editar requerimiento", width="large")
def _edit_req_dialog(
    run_id: str, req_id: str, current_title: str, current_content: str,
    current_attachment: str = "",
) -> None:
    _k_loaded = "_erd_file_loaded"

    new_title = st.text_input("Título *", value=current_title, key="_erd_title")

    uploaded = st.file_uploader(
        "Adjuntar archivo (opcional)",
        type=["txt", "pdf", "docx"],
        key="_erd_file",
        help="El texto extraído reemplazará el contenido del campo de requerimiento",
    )
    if uploaded:
        fname = uploaded.name
        if fname != st.session_state.get(_k_loaded):
            extracted = _extract_req_text(uploaded)
            st.session_state["_erd_content"] = extracted
            st.session_state[_k_loaded] = fname

    if current_attachment and not st.session_state.get(_k_loaded):
        st.markdown(
            f'<div style="color:#6b7280;font-size:.77rem;margin-bottom:.2rem;">'
            f'📎 Archivo cargado: <span style="color:#7dd3fc;">{current_attachment}</span></div>',
            unsafe_allow_html=True,
        )

    new_content = st.text_area(
        "Requerimiento *", value=current_content, height=200, key="_erd_content",
    )

    c_cancel, c_ok = st.columns([1, 2])
    with c_cancel:
        if st.button("Cancelar", use_container_width=True, key="_erd_cancel"):
            st.rerun()
    with c_ok:
        if st.button("Guardar cambios", type="primary", use_container_width=True, key="_erd_ok"):
            t = new_title.strip()
            c = new_content.strip()
            if not t:
                st.error("El título es obligatorio.")
                return
            if len(c) < 20:
                st.error("El requerimiento debe tener al menos 20 caracteres.")
                return
            payload: dict = {"title": t, "content": c}
            loaded = st.session_state.pop(_k_loaded, None) or current_attachment or None
            if loaded:
                payload["attachment_name"] = loaded
            result = api.patch(
                f"{BACKEND}/projects/{run_id}/requirements/{req_id}",
                payload,
            )
            if result is not None:
                st.rerun()


@st.dialog("Clonar requerimiento", width="large")
def _clone_req_dialog(run_id: str, src_title: str, src_content: str) -> None:
    st.markdown(
        '<div style="color:#6b7280;font-size:.83rem;margin-bottom:.75rem;">'
        'Crea una copia de este requerimiento con un nuevo nombre y/o contenido.</div>',
        unsafe_allow_html=True,
    )
    new_title = st.text_input(
        "Título *", value=f"{src_title} (copia)", key="_clone_title",
    )
    new_content = st.text_area(
        "Requerimiento *", value=src_content, height=200, key="_clone_content",
    )
    c_ok, c_cancel = st.columns([1, 1])
    with c_cancel:
        if st.button("Cancelar", use_container_width=True, key="_clone_cancel"):
            st.rerun()
    with c_ok:
        if st.button("Clonar", type="primary", use_container_width=True, key="_clone_ok"):
            t = new_title.strip()
            c = new_content.strip()
            if not t:
                st.error("El título es obligatorio.")
                return
            if len(c) < 20:
                st.error("El requerimiento debe tener al menos 20 caracteres.")
                return
            result = api.post(
                f"{BACKEND}/projects/{run_id}/requirements",
                {"title": t, "content": c},
            )
            if result is not None:
                st.success("Requerimiento clonado correctamente.")
                st.rerun()


def _render_req_panel_v2(run_id: str, req: dict, project: dict) -> None:
    """Right-column detail panel for the selected requirement."""
    req_id          = req["req_id"]
    title           = req.get("title", req_id)
    status          = req.get("status", "created")
    content         = req.get("content", "")
    refinements     = req.get("refinements") or []
    attachment_name = req.get("attachment_name") or ""

    # Review status from latest refinement
    latest_rv      = (refinements[-1].get("review_status") or "") if refinements else ""
    latest_by      = (refinements[-1].get("created_by") or "") if refinements else ""
    latest_date    = (refinements[-1].get("created_at") or "")[:16] if refinements else ""
    review_badge   = _REVIEW_BADGE.get(latest_rv, "")
    attach_html    = (
        f'<span style="background:#1e2533;border:1px solid #30363d;border-radius:6px;'
        f'padding:.1rem .45rem;font-size:.72rem;color:#7dd3fc;margin-left:.35rem;">'
        f'📎 {attachment_name}</span>'
    ) if attachment_name else ""
    _date_part  = f'{latest_date}&nbsp;·&nbsp;' if latest_date else ""
    _by_part    = f'por {latest_by}' if latest_by else ""
    approver_html = (
        f'<span style="font-size:.73rem;color:#6b7280;margin-left:.25rem;">'
        f'{_date_part}{_by_part}</span>'
    ) if review_badge and (_date_part or _by_part) else ""

    _no_analysis_badge = (
        '<span style="background:#450a0a;color:#fca5a5;padding:.1rem .5rem;'
        'border-radius:10px;font-size:.72rem;">Sin análisis</span>'
        if not refinements else ""
    )

    st.markdown(
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:.4rem;'
        f'margin-bottom:.55rem;">'
        f'<span style="font-size:1.05rem;font-weight:700;color:#e2e8f0;">{title}</span>'
        f'{_no_analysis_badge}{review_badge}{approver_html}{attach_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Scrollable content (same style for all reqs) ──────────────────────────
    _safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    st.markdown(
        f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
        f'padding:.6rem .9rem;max-height:110px;overflow-y:auto;color:#8b949e;'
        f'font-size:.8rem;line-height:1.6;margin-bottom:.55rem;">'
        f'{_safe_content}</div>',
        unsafe_allow_html=True,
    )

    if not refinements:
        # ── Unanalyzed: edit button (+ attachment chip) + CTA ─────────────────
        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        _col_edit, _col_attach = st.columns([1, 2])
        with _col_edit:
            if st.button(
                "Editar requerimiento", key=f"edit_req_btn_{req_id}",
                help="Modificar título y contenido de este requerimiento",
                use_container_width=True,
            ):
                _edit_req_dialog(run_id, req_id, title, content, attachment_name)
        with _col_attach:
            if attachment_name:
                st.markdown(
                    f'<div style="padding-top:.4rem;">'
                    f'<span style="background:#1e2533;border:1px solid #30363d;border-radius:6px;'
                    f'padding:.18rem .5rem;font-size:.75rem;color:#7dd3fc;">📎 {attachment_name}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<div style="background:#1a1108;border:1px solid #713f12;border-radius:10px;'
            'padding:1.1rem 1.25rem;margin-top:.75rem;">'
            f'<div style="color:#fcd34d;font-weight:600;font-size:.9rem;margin-bottom:.35rem;">'
            f'{icon("warning",13,"#fcd34d")}&nbsp; Sin análisis</div>'
            '<div style="color:#d97706;font-size:.82rem;line-height:1.55;">'
            'Este requerimiento aún no ha sido analizado. Inicia el flujo HITL para '
            'generar historias de usuario, test cases y el reporte ejecutivo.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        if st.button(
            "Iniciar análisis →", type="primary",
            key=f"start_analysis_{req_id}", use_container_width=True,
        ):
            st.session_state["_prev_view"]          = "scrum_projects"
            st.session_state["_auto_analyze"]       = content
            st.session_state["_auto_analyze_proj"]  = run_id
            st.session_state["_auto_analyze_req"]   = req_id
            st.session_state.view                   = "chat"
            st.rerun()
        return

    # ── Refinement selector ───────────────────────────────────────────────────
    ref_sel_key = f"_sel_ref_{run_id}_{req_id}"

    if len(refinements) > 1:
        ref_opts = {
            r["run_id"]: (
                r.get("created_at", "")[:16]
                + f"  ·  {r.get('summary', {}).get('total_stories', 0)} HU"
                + f"  ·  {r.get('summary', {}).get('total_scenarios', 0)} TC"
                + (f"  {_REVIEW_ICON.get(r.get('review_status',''), '')}"
                   if r.get("review_status") else "")
            )
            for r in refinements
        }
        sel_ref_id = st.selectbox(
            "Refinamiento",
            options=list(ref_opts.keys()),
            format_func=lambda k: ref_opts[k],
            key=ref_sel_key,
            label_visibility="collapsed",
        )
    else:
        sel_ref_id = refinements[0]["run_id"]
        st.session_state[ref_sel_key] = sel_ref_id

    # ── Clonar + Generar código (+ attachment chip) ───────────────────────────
    st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
    _col_clone, _col_code, _col_attach2 = st.columns([1, 1, 1])
    with _col_clone:
        if st.button(
            "Clonar requerimiento", key=f"clone_req_{req_id}",
            help="Crear una copia de este requerimiento con nuevo título y contenido",
            use_container_width=True,
        ):
            _clone_req_dialog(run_id, title, content)
    with _col_code:
        _cg_key   = f"_cg_active_{req_id}"
        store_key = f"cg_{sel_ref_id}"
        if st.button(
            "Generar código", key=f"gen_code_{req_id}",
            help="Genera módulos Python y tests Pytest para este requerimiento",
            use_container_width=True,
        ):
            _start_cg_thread(store_key, sel_ref_id, run_id)
            st.session_state[_cg_key] = store_key
            _code_gen_progress_dialog(store_key, _cg_key)
        elif st.session_state.get(_cg_key) in _CODE_GEN_STORE:
            _code_gen_progress_dialog(st.session_state[_cg_key], _cg_key)
    with _col_attach2:
        if attachment_name:
            st.markdown(
                f'<div style="padding-top:.4rem;">'
                f'<span style="background:#1e2533;border:1px solid #30363d;border-radius:6px;'
                f'padding:.18rem .5rem;font-size:.75rem;color:#7dd3fc;">📎 {attachment_name}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    ref_data = _get_refinement_data(sel_ref_id)
    if not ref_data:
        st.warning("No se pudieron cargar los datos del refinamiento.")
        return

    # ── Sub-tabs ──────────────────────────────────────────────────────────────
    tab_stories, tab_code, tab_comments, tab_rep = st.tabs(
        ["Historias y Tests", "Código Generado", "Comentarios", "Reporte"]
    )
    with tab_stories:
        _section_stories_unified(run_id, ref_data, project)
    with tab_code:
        _tab_codigo_generado(sel_ref_id, ref_data)
    with tab_comments:
        _section_comments_tab(ref_data)
    with tab_rep:
        _section_report_tab(sel_ref_id, ref_data)

    # ── Per-req Jira export (below all tabs) ──────────────────────────────────
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    _section_req_jira_export(run_id, req_id, sel_ref_id, project)


# ── Código Generado tab ───────────────────────────────────────────────────────

_CODE_REVIEW_BADGE = {
    "accepted":      '<span style="background:#14532d;color:#86efac;padding:.1rem .5rem;border-radius:8px;font-size:.72rem;">✓ Aceptado</span>',
    "needs_changes": '<span style="background:#3b2007;color:#fcd34d;padding:.1rem .5rem;border-radius:8px;font-size:.72rem;">⚠ Requiere cambios</span>',
    "rejected":      '<span style="background:#450a0a;color:#fca5a5;padding:.1rem .5rem;border-radius:8px;font-size:.72rem;">✗ Rechazado</span>',
}


def _badge(text: str, bg: str, fg: str) -> str:
    return (
        f'<span style="background:{bg};color:{fg};padding:.15rem .55rem;'
        f'border-radius:8px;font-size:.75rem;font-weight:600;">{text}</span>'
    )


def _tab_codigo_generado(ref_run_id: str, ref_data: dict) -> None:
    """Tab HITL para revisar código generado: módulos Python + tests Pytest."""
    # Priority: freshly generated (in session) → persisted in MongoDB
    code_result = st.session_state.get(f"_code_result_{ref_run_id}")
    if code_result is None:
        code_result = {
            "generated_code":       ref_data.get("generated_code"),
            "generated_tests":      ref_data.get("generated_tests"),
            "quality_report":       ref_data.get("quality_report"),
            "quality_summary":      ref_data.get("quality_summary"),
            "traceability_matrix":  ref_data.get("traceability_matrix"),
            "coverage_report":      ref_data.get("coverage_report"),
            "code_review":          ref_data.get("code_review"),
            "cmmi_l3_compliant":    ref_data.get("cmmi_l3_compliant"),
            "requirements_coverage_pct": ref_data.get("requirements_coverage_pct"),
            "branch_coverage_pct":  ref_data.get("branch_coverage_pct"),
        }

    modules  = code_result.get("generated_code") or []
    tests    = code_result.get("generated_tests") or []
    qs       = code_result.get("quality_summary") or {}
    qr       = code_result.get("quality_report") or {}
    tm       = code_result.get("traceability_matrix") or {}
    cr       = code_result.get("coverage_report") or {}
    v4_review = code_result.get("code_review") or {}

    if not modules:
        st.markdown(
            '<div style="text-align:center;padding:2.5rem 1rem;">'
            '<div style="font-size:2rem;margin-bottom:.75rem;">🤖</div>'
            '<div style="color:#e2e8f0;font-weight:600;font-size:1rem;margin-bottom:.4rem;">'
            'Sin código generado</div>'
            '<div style="color:#6b7280;font-size:.85rem;">'
            'Haz clic en <b style="color:#a78bfa;">Generar código</b> para que el agente '
            'produzca módulos Python y tests Pytest desde las historias analizadas.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Existing human HITL decisions saved via /pipeline/accept-code
    existing_decisions: dict[str, dict] = {
        d.get("filename", ""): d
        for d in (ref_data.get("code_decisions") or [])
    }
    existing_global = ref_data.get("code_review_status")

    # ── Metrics bar ──────────────────────────────────────────────────────────
    total_m   = len(modules)
    total_t   = len(tests)
    cc_exceed = qs.get("functions_exceeding_threshold", 0)
    sec_high  = qs.get("high_severity_count", 0)
    req_cov   = tm.get("requirements_coverage_pct") or code_result.get("requirements_coverage_pct") or 0
    br_cov    = cr.get("branch_coverage_pct") or code_result.get("branch_coverage_pct") or 0
    cmmi_ok   = tm.get("cmmi_l3_compliant") or code_result.get("cmmi_l3_compliant") or False
    v4_status = v4_review.get("review_status", "")
    v4_auto_approved = (
        not existing_decisions
        and v4_status in ("approved", "APPROVED")
    )

    badges_html = (
        f'<span style="background:#1e2533;border:1px solid #30363d;border-radius:8px;'
        f'padding:.25rem .7rem;font-size:.82rem;color:#93c5fd;">📦 {total_m} módulos</span>'
        f'<span style="background:#1e2533;border:1px solid #30363d;border-radius:8px;'
        f'padding:.25rem .7rem;font-size:.82rem;color:#86efac;">🧪 {total_t} tests</span>'
    )
    if qs:
        cc_c = "#f87171" if cc_exceed > 0 else "#6ee7b7"
        badges_html += _badge(f"🔬 CC {cc_exceed} supraumbral", "#1a0a0a" if cc_exceed else "#0a1a0a", cc_c)
        sec_c = "#f87171" if sec_high > 0 else "#6ee7b7"
        badges_html += _badge(f"🛡 {sec_high} HIGH", "#1a0a0a" if sec_high else "#0a1a0a", sec_c)
    if req_cov:
        rc_c = "#4ade80" if req_cov >= 80 else "#fbbf24"
        badges_html += _badge(f"🗺 Req {req_cov:.0f}%", "#0a1a0a" if req_cov >= 80 else "#1a1200", rc_c)
    if br_cov:
        bc_c = "#4ade80" if br_cov >= 80 else "#fbbf24"
        badges_html += _badge(f"🎯 Branch {br_cov:.0f}%", "#0a1a0a" if br_cov >= 80 else "#1a1200", bc_c)
    if cmmi_ok:
        badges_html += _badge("✓ CMMI L3", "#0a1a0a", "#4ade80")
    if v4_status:
        _v4_label = {"approved": "🤖 Auto-aprobado", "pending_review": "🤖 Auto-review PENDING",
                     "rejected": "🤖 Auto-rechazado", "needs_changes": "🤖 Auto: requiere cambios"}.get(v4_status, f"🤖 {v4_status}")
        _v4_bg = {"approved": "#052e16", "pending_review": "#1a1200", "rejected": "#1a0808"}.get(v4_status, "#1e2533")
        _v4_fg = {"approved": "#4ade80", "pending_review": "#fbbf24", "rejected": "#f87171"}.get(v4_status, "#93c5fd")
        badges_html += _badge(_v4_label, _v4_bg, _v4_fg)
    if existing_global:
        badges_html += f'<span style="margin-left:auto;">{_CODE_REVIEW_BADGE.get(existing_global,"")}</span>'

    st.markdown(
        f'<div style="display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap;">{badges_html}</div>',
        unsafe_allow_html=True,
    )

    # ── V4 auto-review notice ─────────────────────────────────────────────────
    if v4_auto_approved:
        st.markdown(
            '<div style="background:#0c1a2e;border:1px solid #1d4ed8;border-left:4px solid #3b82f6;'
            'border-radius:8px;padding:.7rem 1rem;margin-bottom:.75rem;">'
            '<div style="color:#93c5fd;font-weight:700;font-size:.88rem;margin-bottom:.2rem;">'
            '🤖 Pre-aprobado por revisión automática V4</div>'
            '<div style="color:#6b7280;font-size:.81rem;">'
            'El agente revisó y aprobó todos los módulos. Puedes aceptar esta decisión '
            'guardándola directamente, o sobrescribir módulo a módulo antes de guardar.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    elif v4_status and not existing_global:
        st.markdown(
            '<div style="background:#1a1200;border:1px solid #92400e;border-left:4px solid #f59e0b;'
            'border-radius:8px;padding:.7rem 1rem;margin-bottom:.75rem;">'
            '<div style="color:#fbbf24;font-weight:700;font-size:.88rem;margin-bottom:.2rem;">'
            f'🤖 Revisión automática V4: {v4_status}</div>'
            '<div style="color:#6b7280;font-size:.81rem;">'
            'Revisa los resultados del agente y guarda tu decisión final.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Quality dashboard ─────────────────────────────────────────────────────
    if qr:
        with st.expander("📊 Métricas de calidad del código", expanded=False):
            fn_metrics = qr.get("function_metrics") or []
            sec_findings = qr.get("security_findings") or []
            iso_cov = qr.get("iso_25010_coverage") or []
            mi = qr.get("maintainability_index")

            if mi is not None:
                mi_c = "#4ade80" if mi >= 20 else "#f87171"
                st.markdown(
                    f'<div style="margin-bottom:.6rem;">'
                    f'{_badge(f"🔧 MI {mi:.1f}/100", "#0d1117", mi_c)}</div>',
                    unsafe_allow_html=True,
                )

            if fn_metrics:
                st.markdown("**Complejidad por función**")
                rows = ""
                for f in fn_metrics:
                    exceed = f.get("exceeds_threshold", False)
                    cc_val = f.get("cyclomatic_complexity", 0)
                    cog    = f.get("cognitive_complexity", 0)
                    band   = f.get("cc_band", "A")
                    cc_clr = "#f87171" if exceed else "#c9d1d9"
                    rows += (
                        f'<tr style="border-bottom:1px solid #21262d;">'
                        f'<td style="padding:.3rem .5rem;color:#93c5fd;font-size:.78rem;">{f.get("function_name","")}</td>'
                        f'<td style="padding:.3rem .5rem;color:#6b7280;font-size:.78rem;">{f.get("module","")}</td>'
                        f'<td style="padding:.3rem .5rem;color:{cc_clr};font-size:.78rem;font-weight:{"700" if exceed else "400"};">{cc_val}</td>'
                        f'<td style="padding:.3rem .5rem;color:#c9d1d9;font-size:.78rem;">{cog}</td>'
                        f'<td style="padding:.3rem .5rem;color:#a78bfa;font-size:.78rem;">{band}</td>'
                        f'<td style="padding:.3rem .5rem;font-size:.78rem;">{"🔴" if exceed else "✅"}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse;margin-bottom:.75rem;">'
                    f'<thead><tr style="border-bottom:1px solid #30363d;">'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">Función</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">Módulo</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">CC</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">CogC</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">Banda</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">¿Excede?</th>'
                    f'</tr></thead><tbody>{rows}</tbody></table>',
                    unsafe_allow_html=True,
                )

            if sec_findings:
                st.markdown("**Hallazgos de seguridad**")
                rows = ""
                for s in sec_findings:
                    sev = s.get("severity", "low")
                    sev_c = {"high": "#f87171", "medium": "#fbbf24", "low": "#6b7280"}.get(sev, "#6b7280")
                    rows += (
                        f'<tr style="border-bottom:1px solid #21262d;">'
                        f'<td style="padding:.3rem .5rem;color:#a78bfa;font-size:.78rem;">{s.get("test_id","")}</td>'
                        f'<td style="padding:.3rem .5rem;color:{sev_c};font-size:.78rem;font-weight:700;">{sev.upper()}</td>'
                        f'<td style="padding:.3rem .5rem;color:#6b7280;font-size:.78rem;">{s.get("module","")}</td>'
                        f'<td style="padding:.3rem .5rem;color:#6b7280;font-size:.78rem;">{s.get("line_number","")}</td>'
                        f'<td style="padding:.3rem .5rem;color:#c9d1d9;font-size:.78rem;">{s.get("description","")}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse;margin-bottom:.75rem;">'
                    f'<thead><tr style="border-bottom:1px solid #30363d;">'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">ID</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">Sev.</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">Módulo</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">Línea</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">Descripción</th>'
                    f'</tr></thead><tbody>{rows}</tbody></table>',
                    unsafe_allow_html=True,
                )

            if iso_cov:
                st.markdown("**Cobertura ISO 25010**")
                rows = ""
                for ic in iso_cov:
                    st_val = ic.get("status", "")
                    st_c = {"MEASURED": "#4ade80", "NOT_APPLICABLE": "#6b7280",
                             "REQUIRES_HUMAN_JUDGMENT": "#fbbf24"}.get(st_val, "#c9d1d9")
                    rows += (
                        f'<tr style="border-bottom:1px solid #21262d;">'
                        f'<td style="padding:.3rem .5rem;color:#93c5fd;font-size:.78rem;">{ic.get("characteristic","")}</td>'
                        f'<td style="padding:.3rem .5rem;color:{st_c};font-size:.78rem;">{st_val}</td>'
                        f'<td style="padding:.3rem .5rem;color:#8b949e;font-size:.78rem;">{ic.get("verdict","")}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse;">'
                    f'<thead><tr style="border-bottom:1px solid #30363d;">'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">Característica</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;">Estado</th>'
                    f'<th style="padding:.3rem .5rem;color:#6b7280;font-size:.72rem;text-align:left;">Veredicto</th>'
                    f'</tr></thead><tbody>{rows}</tbody></table>',
                    unsafe_allow_html=True,
                )

    # ── Traceability matrix ───────────────────────────────────────────────────
    if tm:
        with st.expander("🗺 Matriz de trazabilidad CMMI L3", expanded=False):
            orphan_sc = tm.get("orphan_scenarios") or []
            orphan_ts = tm.get("orphan_tests") or []
            fwd       = tm.get("forward") or []
            bwd       = tm.get("backward") or []

            col_a, col_b, col_c, col_d = st.columns(4)
            for col, lbl, val, clr in [
                (col_a, "Req. cubiertos", f'{tm.get("requirements_coverage_pct", 0):.0f}%', "#4ade80"),
                (col_b, "Tests justif.", f'{tm.get("tests_justified_pct", 0):.0f}%', "#a78bfa"),
                (col_c, "Escenarios huérfanos", str(len(orphan_sc)), "#f87171" if orphan_sc else "#4ade80"),
                (col_d, "Tests huérfanos", str(len(orphan_ts)), "#f87171" if orphan_ts else "#4ade80"),
            ]:
                with col:
                    st.markdown(
                        f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
                        f'padding:.5rem;text-align:center;">'
                        f'<div style="color:#6b7280;font-size:.68rem;text-transform:uppercase;">{lbl}</div>'
                        f'<div style="color:{clr};font-size:1.15rem;font-weight:700;">{val}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

            if fwd:
                st.markdown("**Forward: escenario → tests**")
                for node in fwd:
                    is_orphan = node.get("status") == "ORPHAN_FORWARD"
                    clr = "#f87171" if is_orphan else "#4ade80"
                    covering = ", ".join(node.get("covering_tests") or []) or "—"
                    st.markdown(
                        f'<div style="background:#0d1117;border-left:3px solid {clr};'
                        f'border-radius:0 6px 6px 0;padding:.3rem .65rem;margin-bottom:.2rem;">'
                        f'<span style="color:{clr};font-size:.78rem;font-weight:600;">'
                        f'{node.get("scenario_name","")}</span>'
                        f'<span style="color:#6b7280;font-size:.75rem;"> → {covering}</span>'
                        + (' <span style="color:#f87171;font-size:.7rem;">⚠ huérfano</span>' if is_orphan else "")
                        + '</div>',
                        unsafe_allow_html=True,
                    )

            if bwd:
                st.markdown("**Backward: test → escenarios**")
                for node in bwd:
                    is_orphan = node.get("status") == "ORPHAN_BACKWARD"
                    clr = "#f87171" if is_orphan else "#a78bfa"
                    scenarios = ", ".join(node.get("justifying_scenarios") or []) or "—"
                    st.markdown(
                        f'<div style="background:#0d1117;border-left:3px solid {clr};'
                        f'border-radius:0 6px 6px 0;padding:.3rem .65rem;margin-bottom:.2rem;">'
                        f'<span style="color:{clr};font-size:.78rem;font-weight:600;">'
                        f'{node.get("test_name","")}</span>'
                        f'<span style="color:#6b7280;font-size:.75rem;"> ← {scenarios}</span>'
                        + (' <span style="color:#f87171;font-size:.7rem;">⚠ huérfano</span>' if is_orphan else "")
                        + '</div>',
                        unsafe_allow_html=True,
                    )

            # Coverage report
            if cr:
                br = cr.get("branch_coverage_pct", 0)
                ln = cr.get("line_coverage_pct", 0)
                meets = cr.get("meets_threshold", False)
                st.markdown(
                    f'<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.5rem;">'
                    + _badge(f"Branch {br:.0f}%", "#052e16" if br >= 80 else "#1a1200", "#4ade80" if br >= 80 else "#fbbf24")
                    + _badge(f"Line {ln:.0f}%", "#052e16" if ln >= 80 else "#1a1200", "#4ade80" if ln >= 80 else "#fbbf24")
                    + (_badge("✓ Umbral OK", "#052e16", "#4ade80") if meets else _badge("✗ Bajo umbral (80%)", "#1a0808", "#f87171"))
                    + '</div>',
                    unsafe_allow_html=True,
                )

    # ── Per-module code + HITL ────────────────────────────────────────────────
    decisions_state_key = f"_code_decisions_{ref_run_id}"
    if decisions_state_key not in st.session_state:
        # Seed priority: human HITL > V4 change_history > V4 global-approved > default accepted
        # V4 uses "approved" as action; map to our radio value "accepted"
        _v4_action_map = {"approved": "accepted", "rejected": "needs_changes",
                          "needs_changes": "needs_changes", "accepted": "accepted"}

        v4_changes: dict[str, dict] = {}
        for ch in (v4_review.get("change_history") or []):
            tgt = ch.get("target", "")
            if tgt:
                raw_action = ch.get("action", "approved")
                v4_changes[tgt] = {
                    "action": _v4_action_map.get(raw_action, "accepted"),
                    "notes":  ch.get("notes") or ("Auto-aprobado por V4" if raw_action == "approved" else ""),
                }

        st.session_state[decisions_state_key] = {
            m["filename"]: {
                "action": (
                    existing_decisions.get(m["filename"], {}).get("action")
                    or v4_changes.get(m["filename"], {}).get("action")
                    or ("accepted" if v4_auto_approved else "accepted")
                ),
                "notes": (
                    existing_decisions.get(m["filename"], {}).get("notes")
                    or v4_changes.get(m["filename"], {}).get("notes")
                    or ("Auto-aprobado por V4" if v4_auto_approved else "")
                ),
            }
            for m in modules
        }

    decisions_map: dict = st.session_state[decisions_state_key]

    tests_by_module: dict[str, list] = {}
    for t in tests:
        tests_by_module.setdefault(t.get("target_module", ""), []).append(t)

    fn_by_module: dict[str, list] = {}
    for fn in (qr.get("function_metrics") or []):
        fn_by_module.setdefault(fn.get("module", ""), []).append(fn)

    for mod_idx, mod in enumerate(modules):
        fname       = mod.get("filename", "module.py")
        description = mod.get("description", "")
        source_code = mod.get("source_code", "")
        mod_tests   = tests_by_module.get(fname, [])
        mod_fns     = fn_by_module.get(fname, [])
        cur         = decisions_map.setdefault(fname, {"action": "accepted", "notes": ""})
        has_issues  = any(f.get("exceeds_threshold") for f in mod_fns)

        label_prefix = "🔴 " if has_issues else ""
        with st.expander(f"{label_prefix}📄 `{fname}`", expanded=False):
            if description:
                st.markdown(
                    f'<div style="color:#9ca3af;font-size:.83rem;margin-bottom:.6rem;">{description}</div>',
                    unsafe_allow_html=True,
                )

            if mod_fns:
                fn_badges = " ".join(
                    _badge(
                        f"{f['function_name']} CC{f['cyclomatic_complexity']}",
                        "#1a0808" if f.get("exceeds_threshold") else "#0d1117",
                        "#f87171" if f.get("exceeds_threshold") else "#6b7280",
                    )
                    for f in mod_fns
                )
                st.markdown(
                    f'<div style="margin-bottom:.5rem;">{fn_badges}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("**Código fuente**")
            st.code(source_code, language="python")

            if mod_tests:
                st.markdown("**Tests Pytest**")
                for t in mod_tests:
                    st.markdown(
                        f"<small style='color:#6b7280;'>`{t.get('test_name','test_file.py')}`</small>",
                        unsafe_allow_html=True,
                    )
                    st.code(t.get("source_code", ""), language="python")

            st.markdown("---")
            st.markdown("**Decisión de revisión**")
            action_key = f"_cda_{ref_run_id}_{mod_idx}_{fname}"
            action = st.radio(
                "Acción",
                options=["accepted", "needs_changes"],
                format_func=lambda v: "✓ Aceptar" if v == "accepted" else "⚠ Solicitar cambios",
                index=0 if cur.get("action", "accepted") == "accepted" else 1,
                key=action_key,
                horizontal=True,
                label_visibility="collapsed",
            )
            decisions_map[fname]["action"] = action

            notes = ""
            if action == "needs_changes":
                notes = st.text_area(
                    "Observaciones",
                    value=cur.get("notes", ""),
                    key=f"_cdn_{ref_run_id}_{mod_idx}_{fname}",
                    placeholder="Describe los cambios requeridos…",
                    height=80,
                )
            decisions_map[fname]["notes"] = notes

    # Global decision + save
    st.markdown("---")
    col_g, col_s = st.columns([2, 1])
    with col_g:
        global_decision = st.radio(
            "Decisión global",
            options=["accepted", "needs_changes", "rejected"],
            format_func=lambda v: {"accepted": "✓ Aprobar todo", "needs_changes": "⚠ Requiere cambios", "rejected": "✗ Rechazar"}.get(v, v),
            index=0,
            key=f"_cdg_{ref_run_id}",
            horizontal=True,
        )
    with col_s:
        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        if st.button("💾 Guardar decisiones", key=f"_cds_{ref_run_id}", use_container_width=True, type="primary"):
            payload = {
                "run_id": ref_run_id,
                "global_decision": global_decision,
                "decisions": [
                    {"filename": fname, "action": v["action"], "notes": v.get("notes") or ""}
                    for fname, v in decisions_map.items()
                ],
                "reviewer": st.session_state.get("user_email", ""),
            }
            resp = api.post(f"{BACKEND}/pipeline/accept-code", payload)
            if resp and resp.get("ok"):
                _show_toast("Decisiones guardadas correctamente.")
                # Clear caches so next render re-fetches from MongoDB
                st.session_state.pop(f"_code_result_{ref_run_id}", None)
                st.session_state.pop(decisions_state_key, None)
                st.session_state.pop(f"_ref_cache_{ref_run_id}", None)
                st.rerun()
            else:
                _show_toast(f"Error al guardar: {resp}", "error")


# ── Unified HU + AC + TC view ─────────────────────────────────────────────────

_KW_COLOR = {
    "Given": "#60a5fa", "When": "#a78bfa", "Then": "#34d399",
    "And": "#8b949e", "But": "#f87171",
}
_PRIO_COLOR = {"High": "#f97316", "Medium": "#facc15", "Low": "#6b7280"}


def _section_stories_unified(run_id: str, ref_data: dict, project: dict) -> None:
    """Unified view: each User Story shows its ACs and Gherkin Test Cases as collapsible sections."""
    report_data = ref_data.get("report_data") or {}
    stories     = report_data.get("user_stories") or []
    features    = report_data.get("features") or []

    if not stories:
        _empty_tab(
            "No hay historias de usuario generadas aún.",
            "Analiza un requerimiento para que los agentes generen los artefactos.",
        )
        return

    # Build story_id → [scenario] map
    story_scenarios: dict[str, list] = {}
    for feat in features:
        fid = feat.get("user_story_id", "")
        for sc in (feat.get("scenarios") or []):
            story_scenarios.setdefault(fid, []).append(sc)

    # Fetch story assignments
    assignments_data = api.get(f"{BACKEND}/projects/{run_id}/assignments") or []
    assigned_map: dict[str, str] = {a["story_id"]: a["developer_email"] for a in assignments_data}

    # Build developer options from project's assigned_analysts filtered by role=developer
    if "_sp_user_map" not in st.session_state:
        users = api.get(f"{BACKEND}/auth/users") or []
        st.session_state["_sp_user_map"] = {u["email"]: u for u in users}
    user_map: dict = st.session_state["_sp_user_map"]

    assigned_analysts = project.get("assigned_analysts") or []
    dev_options: dict[str, str] = {}
    for email in assigned_analysts:
        u = user_map.get(email, {})
        if u.get("role") == "developer":
            name     = u.get("name") or email.split("@")[0]
            dev_type = u.get("developer_type", "")
            dev_options[email] = name + (
                f" · {_DEV_TYPE_LBL.get(dev_type, dev_type)}" if dev_type else ""
            )

    total_sc = sum(len(v) for v in story_scenarios.values())
    st.markdown(
        f'<div style="color:#6b7280;font-size:.8rem;margin-bottom:.5rem;">'
        f'{len(stories)} historia(s) · {total_sc} escenario(s)</div>',
        unsafe_allow_html=True,
    )

    for story in stories:
        story_id    = story.get("id", "")
        title       = story.get("title", story_id)
        priority    = story.get("priority", "")
        story_type  = story.get("story_type", "")
        as_a        = story.get("as_a", "")
        i_want      = story.get("i_want", "")
        so_that     = story.get("so_that", "")
        biz_rules   = story.get("business_rules") or []
        acs         = story.get("acceptance_criteria") or []
        scenarios   = story_scenarios.get(story_id, [])
        prio_color  = _PRIO_COLOR.get(priority, "#6b7280")
        current_dev = assigned_map.get(story_id)

        with st.expander(f"{story_id} — {title}"):
            # ── Story statement ───────────────────────────────────────────────
            st.markdown(
                f'<div style="color:#8b949e;font-style:italic;font-size:.88rem;'
                f'background:#161b22;border-left:3px solid #00bcd4;'
                f'padding:.45rem .75rem;border-radius:0 6px 6px 0;margin-bottom:.5rem;">'
                f'Como <strong style="color:#c9d1d9">{as_a}</strong>, '
                f'quiero <strong style="color:#c9d1d9">{i_want}</strong>, '
                f'para <strong style="color:#c9d1d9">{so_that}</strong>.'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="color:#6b7280;font-size:.75rem;margin-bottom:.4rem;">Prioridad: '
                f'<span style="color:{prio_color};font-weight:600;">{priority}</span>'
                f'&nbsp;&nbsp;Tipo: <span style="color:#c9d1d9;">{story_type}</span></div>',
                unsafe_allow_html=True,
            )

            # ── Business rules ────────────────────────────────────────────────
            if biz_rules:
                with st.expander(f"Reglas de negocio ({len(biz_rules)})"):
                    for br in biz_rules:
                        st.markdown(
                            f'<div style="color:#c9d1d9;font-size:.82rem;'
                            f'padding:.15rem 0 .15rem .65rem;'
                            f'border-left:2px solid #21262d;">{br}</div>',
                            unsafe_allow_html=True,
                        )

            # ── Acceptance Criteria (collapsible) ─────────────────────────────
            if acs:
                with st.expander(f"Criterios de aceptación ({len(acs)})"):
                    for ac in acs:
                        ac_id  = ac.get("id", "")
                        desc   = ac.get("description", "")
                        given  = ac.get("given", "")
                        when   = ac.get("when", "")
                        then   = ac.get("then", "")
                        is_neg = ac.get("is_negative_case", False)
                        neg_tag = (
                            '<span style="background:#431407;color:#f97316;border-radius:4px;'
                            'padding:.05rem .3rem;font-size:.68rem;margin-left:.35rem;">NEG</span>'
                            if is_neg else ""
                        )
                        st.markdown(
                            f'<div style="background:#0d1117;border:1px solid #21262d;'
                            f'border-left:2px solid #60a5fa;'
                            f'border-radius:0 6px 6px 0;padding:.5rem .8rem;margin-bottom:.35rem;">'
                            f'<div style="color:#c9d1d9;font-size:.84rem;font-weight:600;'
                            f'margin-bottom:.3rem;">{ac_id}{neg_tag} — {desc}</div>'
                            f'<div style="font-size:.79rem;line-height:1.85;color:#8b949e;">'
                            f'<span style="color:#60a5fa;font-weight:600;'
                            f'display:inline-block;width:3.5rem;">Given</span>{given}<br>'
                            f'<span style="color:#a78bfa;font-weight:600;'
                            f'display:inline-block;width:3.5rem;">When</span>{when}<br>'
                            f'<span style="color:#34d399;font-weight:600;'
                            f'display:inline-block;width:3.5rem;">Then</span>{then}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

            # ── Test Cases (collapsible) ──────────────────────────────────────
            if scenarios:
                with st.expander(f"Test Cases ({len(scenarios)})"):
                    for sc in scenarios:
                        sc_name = sc.get("name", "")
                        sc_type = sc.get("scenario_type", "")
                        quality = sc.get("quality_characteristic", "")
                        tags    = sc.get("tags") or []
                        steps   = sc.get("steps") or []

                        tags_html = " ".join(
                            f'<span style="background:#1e3a4a;color:#7dd3fc;border-radius:4px;'
                            f'padding:.04rem .32rem;font-size:.68rem;">@{t}</span>'
                            for t in tags
                        )
                        meta_parts = []
                        if sc_type:
                            meta_parts.append(f'<span style="color:#4b5563;font-size:.72rem;">{sc_type}</span>')
                        if tags_html:
                            meta_parts.append(tags_html)
                        if quality:
                            meta_parts.append(f'<span style="color:#4b5563;font-size:.72rem;">ISO 25010: {quality}</span>')
                        meta_row = "&nbsp;".join(meta_parts)

                        steps_parts = [
                            f'<span style="color:{_KW_COLOR.get(s.get("keyword",""),"#8b949e")};'
                            f'font-weight:600;display:inline-block;width:3.5rem;">'
                            f'{s.get("keyword","")}</span>{s.get("text","")}'
                            for s in steps
                        ]
                        steps_html = "<br>".join(steps_parts)

                        st.markdown(
                            f'<div style="background:#0d1117;border:1px solid #21262d;'
                            f'border-left:2px solid #a78bfa;'
                            f'border-radius:0 6px 6px 0;padding:.5rem .8rem;margin-bottom:.35rem;">'
                            f'<div style="color:#c9d1d9;font-size:.84rem;font-weight:600;'
                            f'margin-bottom:.3rem;">{sc_name}</div>'
                            f'<div style="font-size:.79rem;line-height:1.85;color:#8b949e;">'
                            f'{steps_html}</div>'
                            + (f'<div style="margin-top:.3rem;">{meta_row}</div>' if meta_row else "")
                            + f'</div>',
                            unsafe_allow_html=True,
                        )

            # ── Developer assignment (project team developers only) ────────────
            st.markdown(
                '<div style="border-top:1px solid #1e2533;margin:.6rem 0 .5rem;"></div>',
                unsafe_allow_html=True,
            )
            if dev_options:
                dev_emails  = list(dev_options.keys())
                default_idx = dev_emails.index(current_dev) if current_dev in dev_emails else 0
                col_current, col_select = st.columns([2, 3])

                with col_current:
                    st.markdown(
                        '<div style="color:#8b949e;font-size:.72rem;font-weight:600;'
                        'text-transform:uppercase;letter-spacing:.04em;margin-bottom:.3rem;">'
                        'Asignado a</div>',
                        unsafe_allow_html=True,
                    )
                    if current_dev:
                        dev_u    = user_map.get(current_dev, {})
                        dev_name = dev_u.get("name") or current_dev.split("@")[0]
                        dev_type = dev_u.get("developer_type", "")
                        dev_tag  = _DEV_TYPE_LBL.get(dev_type, "") if dev_type else ""
                        safe_sid = re.sub(r'[^a-zA-Z0-9]', '_', story_id)
                        st.markdown(
                            f'<div style="background:#0d1117;border:1px solid #21262d;'
                            f'border-left:3px solid #6ee7b7;border-radius:0 6px 6px 0;'
                            f'padding:.35rem .6rem;margin-bottom:.3rem;">'
                            f'<div style="color:#6ee7b7;font-size:.82rem;font-weight:600;">'
                            f'{dev_name}</div>'
                            + (f'<div style="color:#4b5563;font-size:.72rem;">{dev_tag}</div>'
                               if dev_tag else "")
                            + f'</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "✕ Desasignar",
                            key=f"unassign_hu_{run_id}_{safe_sid}",
                            use_container_width=True,
                        ):
                            api.delete(
                                f"{BACKEND}/projects/{run_id}/stories/{story_id}/assign"
                            )
                            st.rerun()
                    else:
                        st.markdown(
                            '<div style="background:#0d1117;border:1px solid #21262d;'
                            'border-radius:6px;padding:.35rem .6rem;'
                            'color:#4b5563;font-size:.8rem;">Sin asignar</div>',
                            unsafe_allow_html=True,
                        )

                with col_select:
                    st.markdown(
                        '<div style="color:#8b949e;font-size:.72rem;font-weight:600;'
                        'text-transform:uppercase;letter-spacing:.04em;margin-bottom:.3rem;">'
                        'Asignar</div>',
                        unsafe_allow_html=True,
                    )
                    selected_dev = st.selectbox(
                        "Asignar a",
                        dev_emails,
                        index=default_idx,
                        format_func=lambda e: dev_options.get(e, e),
                        key=f"dev_hu_{run_id}_{story_id}",
                        label_visibility="collapsed",
                    )
                    if st.button(
                        "Asignar desarrollador",
                        key=f"assign_hu_{run_id}_{story_id}",
                        use_container_width=True,
                        type="primary",
                    ):
                        result = api.post(
                            f"{BACKEND}/projects/{run_id}/stories/{story_id}/assign",
                            {"developer_email": selected_dev},
                        )
                        if result is not None:
                            st.rerun()
            else:
                st.markdown(
                    '<div style="color:#374151;font-size:.78rem;">'
                    'Sin desarrolladores en el equipo — añade miembros con rol Developer '
                    'en la pestaña Equipo para poder asignar historias.</div>',
                    unsafe_allow_html=True,
                )


