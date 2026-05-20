"""Panel de administración: gestión de usuarios."""
import secrets
import string

import streamlit as st
import streamlit.components.v1 as components

import api
from config import BACKEND
from ui.icons import icon

_ROLE_LABELS = {
    "admin":        ("key",       "Admin"),
    "scrum_leader": ("clipboard", "Scrum Leader"),
    "analyst":      ("beaker",    "Analista"),
    "developer":    ("desktop",   "Desarrollador"),
}
_DEV_TYPE_LABELS = {
    "backend":  "Backend",
    "frontend": "Frontend",
    "devops":   "DevOps",
}

# ── Tailwind-style role badges ─────────────────────────────────────────────────
_ROLE_BADGE_STYLE = {
    "admin":        "background:#450a0a;color:#fca5a5;border:1px solid #991b1b;",
    "scrum_leader": "background:#0c1a3d;color:#93c5fd;border:1px solid #1d4ed8;",
    "analyst":      "background:#052e16;color:#86efac;border:1px solid #16a34a;",
    "developer":    "background:#2e1065;color:#d8b4fe;border:1px solid #7e22ce;",
}
_ROLE_BADGE_LABEL = {
    "admin":        "Admin",
    "scrum_leader": "Scrum Leader",
    "analyst":      "Analista",
    "developer":    "Desarrollador",
}


def _role_badge(role: str) -> str:
    style = _ROLE_BADGE_STYLE.get(
        role, "background:#1f2937;color:#9ca3af;border:1px solid #374151;"
    )
    label = _ROLE_BADGE_LABEL.get(role, role)
    return (
        f'<span style="{style}display:inline-flex;align-items:center;'
        f'border-radius:9999px;font-size:.72rem;font-weight:600;'
        f'padding:.18rem .65rem;letter-spacing:.04em;font-family:sans-serif;">'
        f'{label}</span>'
    )


def _show_toast(msg: str, kind: str = "success") -> None:
    """Tailwind-style sliding toast injected into parent DOM via components.html."""
    if kind == "success":
        bg, border, clr = "#052e16", "#166534", "#4ade80"
        icon_path = "M20 6 9 17l-5-5"
        title = "Operación exitosa"
    else:
        bg, border, clr = "#450a0a", "#991b1b", "#f87171"
        icon_path = "M18 6 6 18M6 6l12 12"
        title = "Error"

    msg_esc   = msg.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    title_esc = title

    js = f"""<script>
(function(){{
  var D=window.parent.document,B=D.body;
  if(!D.getElementById('qa-tn-css')){{
    var s=D.createElement('style');s.id='qa-tn-css';
    s.textContent=`
      #qa-tn{{
        position:fixed;top:1.25rem;right:1.25rem;z-index:99999;width:340px;
        transform:translateX(calc(100% + 2rem));opacity:0;
        transition:transform .35s cubic-bezier(.34,1.2,.64,1),opacity .25s;
      }}
      #qa-tn.qa-tn-in{{transform:none;opacity:1;}}
      .qa-tn-card{{
        border-radius:12px;padding:.9rem 1rem;
        display:flex;align-items:flex-start;gap:.75rem;
        box-shadow:0 8px 32px rgba(0,0,0,.55);
      }}
      .qa-tn-body{{flex:1;min-width:0;}}
      .qa-tn-title{{font-weight:700;font-size:.9rem;font-family:sans-serif;margin-bottom:.2rem;}}
      .qa-tn-msg{{font-size:.82rem;font-family:sans-serif;line-height:1.45;color:#d1d5db;}}
      .qa-tn-close{{
        flex-shrink:0;background:none;border:none;cursor:pointer;padding:2px;
        opacity:.55;transition:opacity .15s;line-height:0;
      }}
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
    +'<div class="qa-tn-title" style="color:{clr}">{title_esc}</div>'
    +'<div class="qa-tn-msg">{msg_esc}</div>'
    +'</div>'
    +'<button class="qa-tn-close"'
    +' onclick="document.getElementById(\\\'qa-tn\\\').classList.remove(\\\'qa-tn-in\\\')">'
    +'<svg width="14" height="14" viewBox="0 0 24 24" fill="none"'
    +' stroke="#9ca3af" stroke-width="2.5">'
    +'<path d="M18 6L6 18M6 6l12 12"/></svg>'
    +'</button>'
    +'</div>';
  requestAnimationFrame(function(){{
    t.classList.add('qa-tn-in');
    clearTimeout(t._tid);
    t._tid=setTimeout(function(){{t.classList.remove('qa-tn-in');}},4500);
  }});
}})();
</script>"""
    components.html(js, height=0, scrolling=False)


# ── Render ─────────────────────────────────────────────────────────────────────

def render_admin_panel() -> None:
    # ── Show pending toast (set by create/deactivate actions) ─────────────────
    if "_admin_toast" in st.session_state:
        info = st.session_state.pop("_admin_toast")
        _show_toast(info["msg"], info.get("kind", "success"))

    # ── Stretch scrollable user-list to fill remaining viewport height ─────────
    components.html("""<script>
(function(){
  var D=window.parent.document;
  var W=window.parent;
  function resize(){
    // Use getComputedStyle (cross-browser) instead of inline style attribute
    var els=D.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"] > div, [data-testid="stVerticalBlock"] > div');
    for(var i=0;i<els.length;i++){
      var cs=W.getComputedStyle(els[i]);
      var oy=cs.overflowY||'';
      var ox=cs.overflow||'';
      if(oy==='auto'||oy==='scroll'||ox==='auto'||ox==='scroll'){
        els[i].style.height=(W.innerHeight-220)+'px';
        els[i].style.overflowY='auto';
      }
    }
  }
  // Run after DOM settles
  setTimeout(resize,100);
  W.addEventListener('resize',resize);
})();
</script>""", height=0, scrolling=False)

    col_list, col_create = st.columns([3, 2], gap="large")

    with col_list:
        st.markdown(
            '<div style="color:#e2e8f0;font-size:1.05rem;font-weight:600;'
            'margin-bottom:.75rem;font-family:sans-serif;">Usuarios</div>',
            unsafe_allow_html=True,
        )
        _render_user_list()

    with col_create:
        # Form card border injected via a scoped CSS rule
        st.markdown(
            """<style>
            div[data-testid="stVerticalBlockBorderWrapper"] .qa-form-card,
            .qa-form-card {
              border:1px solid #374151;border-radius:12px;
              padding:1.25rem 1rem;background:#0a0f1a;
            }
            </style>""",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            _render_create_user()


# ── User list ──────────────────────────────────────────────────────────────────

def _render_user_list() -> None:
    data = api.get(f"{BACKEND}/auth/users")
    if data is None:
        st.warning("No se pudo obtener la lista de usuarios.")
        return

    users = data if isinstance(data, list) else data.get("users", [])

    if not users:
        st.info("No hay usuarios registrados.")
        return

    # ── Search ─────────────────────────────────────────────────────────────────
    query = st.text_input(
        "Buscar usuario",
        placeholder="Email, nombre o rol…",
        key="_ul_search",
        label_visibility="collapsed",
    )
    q = query.strip().lower()
    filtered = [
        u for u in users
        if not q
        or q in u.get("email", "").lower()
        or q in u.get("name", "").lower()
        or q in _ROLE_BADGE_LABEL.get(u.get("role", ""), "").lower()
    ]

    st.markdown(
        f'<div style="color:#6b7280;font-size:.8rem;margin:.35rem 0 .6rem;">'
        f'{len(filtered)} de {len(users)} usuario(s)</div>',
        unsafe_allow_html=True,
    )

    # ── Scrollable list ─────────────────────────────────────────────────────────
    with st.container(height=700):
        my_email = st.session_state.get("user_email", "")
        for u in filtered:
            role      = u.get("role", "")
            dev_type  = _DEV_TYPE_LABELS.get(u.get("developer_type", ""), "")
            name_str  = u.get("name", "")
            active    = u.get("is_active", True)
            is_me     = u["email"] == my_email

            status_dot = (
                '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
                'background:#22c55e;margin-right:5px;vertical-align:middle;"></span>'
                '<span style="color:#86efac;font-size:.75rem;">Activo</span>'
                if active else
                '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
                'background:#ef4444;margin-right:5px;vertical-align:middle;"></span>'
                '<span style="color:#fca5a5;font-size:.75rem;">Inactivo</span>'
            )
            me_tag     = '&nbsp;<span style="color:#6b7280;font-size:.72rem;">(tú)</span>' if is_me else ""
            dev_html   = f'<span style="color:#6b7280;font-size:.72rem;">{dev_type}</span>' if dev_type else ""
            display    = name_str if name_str else u["email"].split("@")[0].replace(".", " ").replace("_", " ").title()
            secondary  = f'<div style="color:#6b7280;font-size:.78rem;font-family:sans-serif;">{u["email"]}{me_tag}</div>' if name_str else ""

            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(
                    f'<div style="color:#f1f5f9;font-size:.92rem;font-weight:600;font-family:sans-serif;">{display}</div>'
                    f'{secondary}'
                    f'<div style="margin-top:.3rem;display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;">'
                    f'{_role_badge(role)}{dev_html}&nbsp;{status_dot}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col_btn:
                if active and not is_me:
                    if st.button("Desactivar", key=f"deact_{u['email']}", type="secondary"):
                        ok = api.delete(f"{BACKEND}/auth/users/{u['email']}")
                        if ok:
                            st.session_state["_admin_toast"] = {
                                "msg": f"Usuario {u['email']} desactivado.",
                                "kind": "success",
                            }
                            st.rerun()
            st.divider()


# ── Create user ────────────────────────────────────────────────────────────────

_FORM_KEYS = ["_nu_name", "_nu_email", "_nu_password", "_nu_password_pending", "_nu_devtype"]


def _render_create_user() -> None:
    st.markdown(
        '<div style="color:#e2e8f0;font-size:1.05rem;font-weight:600;'
        'margin-bottom:1rem;font-family:sans-serif;">Nuevo usuario</div>',
        unsafe_allow_html=True,
    )

    # ── Form reset (must run BEFORE any widget) ────────────────────────────────
    if st.session_state.pop("_nu_reset_form", False):
        for k in _FORM_KEYS:
            st.session_state.pop(k, None)
        st.session_state["_nu_role"] = "analyst"
        st.session_state.pop("_user_create_errs", None)

    errs: dict = st.session_state.get("_user_create_errs", {})

    # ── Nombre y correo ────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Nombre completo *", key="_nu_name", placeholder="Ana García")
        if "name" in errs:
            _field_error(errs["name"])
    with col2:
        st.text_input("Correo electrónico *", key="_nu_email", placeholder="ana@empresa.com")
        if "email" in errs:
            _field_error(errs["email"])

    # ── Contraseña con generador ───────────────────────────────────────────────
    if "_nu_password_pending" in st.session_state:
        st.session_state["_nu_password"] = st.session_state.pop("_nu_password_pending")

    col_pass, col_gen = st.columns([3, 2])
    with col_pass:
        st.text_input(
            "Contraseña *", key="_nu_password", type="password",
            placeholder="Mín. 8 caracteres",
        )
        if "password" in errs:
            _field_error(errs["password"])
    with col_gen:
        st.markdown(
            f'<div style="height:1.85rem;display:flex;align-items:flex-end;">'
            f'{icon("arrow-path", 14, "#00bcd4")}'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Generar contraseña",
            help="Genera una contraseña aleatoria segura",
            key="gen_pass_btn",
            use_container_width=True,
        ):
            alphabet = string.ascii_letters + string.digits + "!@#$%&*"
            st.session_state["_nu_password_pending"] = "".join(
                secrets.choice(alphabet) for _ in range(16)
            )
            st.rerun()

    # ── Rol y tipo ─────────────────────────────────────────────────────────────
    col3, col4 = st.columns(2)
    with col3:
        role_val = st.selectbox(
            "Rol *", key="_nu_role",
            options=["analyst", "scrum_leader", "developer", "admin"],
            format_func=lambda r: _ROLE_LABELS.get(r, ("", r))[1],
        )
    with col4:
        if role_val == "developer":
            st.selectbox(
                "Tipo de desarrollador", key="_nu_devtype",
                options=["backend", "frontend", "devops"],
            )

    st.markdown("")
    if st.button("Crear usuario", type="primary", use_container_width=True, key="create_user_btn"):
        n  = st.session_state.get("_nu_name", "").strip()
        e  = st.session_state.get("_nu_email", "").strip()
        p  = st.session_state.get("_nu_password", "")
        r  = st.session_state.get("_nu_role", "analyst")
        dt = st.session_state.get("_nu_devtype", None) if r == "developer" else None

        new_errs: dict = {}
        if not n:
            new_errs["name"] = "El nombre es obligatorio."
        if not e:
            new_errs["email"] = "El correo electrónico es obligatorio."
        elif "@" not in e or "." not in e.split("@")[-1]:
            new_errs["email"] = "Ingresa un correo electrónico válido."
        if not p:
            new_errs["password"] = "La contraseña es obligatoria."
        elif len(p) < 8:
            new_errs["password"] = "Debe tener al menos 8 caracteres."

        if new_errs:
            st.session_state["_user_create_errs"] = new_errs
            st.rerun()

        st.session_state.pop("_user_create_errs", None)
        payload: dict = {"name": n, "email": e, "password": p, "role": r}
        if dt:
            payload["developer_type"] = dt

        st.session_state.pop("_api_last_http_error", None)
        result = api.post(f"{BACKEND}/auth/users", payload, suppress_codes=(409,))

        if result:
            role_label = _ROLE_LABELS[r][1]
            st.session_state["_nu_reset_form"] = True
            st.session_state["_admin_toast"] = {
                "msg":  f"Usuario {e} ({n}) creado con rol {role_label}.",
                "kind": "success",
            }
            st.rerun()

        last_err = st.session_state.get("_api_last_http_error", {})
        if last_err.get("status") == 409:
            st.session_state["_user_create_errs"] = {
                "email": f"Ya existe un usuario con el correo {e}."
            }
            st.rerun()


def _field_error(msg: str) -> None:
    st.markdown(
        f'<p style="color:#f87171;font-size:.8rem;margin-top:-.4rem;margin-bottom:.25rem;">'
        f'{icon("warning", 12, "#f87171")} {msg}</p>',
        unsafe_allow_html=True,
    )
