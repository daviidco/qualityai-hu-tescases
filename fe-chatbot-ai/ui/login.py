"""Vista de login — split screen (panel izquierdo decorativo + formulario derecho)."""

import streamlit as st
import streamlit.components.v1 as components

import api
from config import BACKEND


_LOGIN_CSS = """<style>
/* ── Login page: form on the right half ── */
body:not(.qa-has-sb) section[data-testid="stMain"] {
  padding-left: 50% !important;
  box-sizing: border-box !important;
  min-height: 100vh !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  transition: none !important;
}
body:not(.qa-has-sb) section[data-testid="stMain"] .block-container {
  flex: 0 0 auto !important;
  width: 82% !important;
  max-width: 760px !important;
  padding: 2rem 3rem !important;
  margin: 0 !important;
  box-sizing: border-box !important;
}

/* ── Form card — Tailwind-style ── */
body:not(.qa-has-sb) [data-testid="stForm"] {
  background: #111827 !important;
  border: 1px solid #374151 !important;
  border-radius: 12px !important;
  padding: 2.5rem 2.25rem !important;
  box-shadow: 0 4px 24px rgba(0,0,0,.35) !important;
}

/* ── Heading block ── */
.qa-lf-header { margin-bottom: 2.5rem; }
.qa-lf-h1 {
  color: #f9fafb; font-size: 2.6rem; font-weight: 700;
  margin: 0 0 .4rem; line-height: 1.2;
}
.qa-lf-sub { color: #9ca3af; font-size: 1.2rem; margin: 0; line-height: 1.5; }

/* ── Labels ── */
body:not(.qa-has-sb) [data-testid="stTextInput"] label,
body:not(.qa-has-sb) [data-testid="stTextInput"] label * {
  display: block !important;
  color: #e5e7eb !important;
  font-size: 18px !important;
  font-weight: 500 !important;
  line-height: 1.5 !important;
  margin-bottom: .35rem !important;
}

/* ── Inputs — Tailwind ring style, padding-based (no fixed height) ── */
body:not(.qa-has-sb) [data-testid="stTextInput"] > div > div > input {
  display: block !important;
  width: 100% !important;
  background: #1f2937 !important;
  border: 1px solid #4b5563 !important;
  border-radius: 6px !important;
  color: #f9fafb !important;
  font-size: 1.05rem !important;
  line-height: 1.5 !important;
  padding: .625rem .875rem !important;
  height: auto !important;
  box-shadow: inset 0 1px 2px rgba(0,0,0,.2) !important;
  transition: border-color .15s, box-shadow .15s !important;
}
body:not(.qa-has-sb) [data-testid="stTextInput"] > div > div > input::placeholder {
  color: #6b7280 !important;
}
body:not(.qa-has-sb) [data-testid="stTextInput"] > div > div > input:focus {
  border-color: #0891b2 !important;
  outline: none !important;
  box-shadow: 0 0 0 2px rgba(8,145,178,.3) !important;
}

/* ── Hide Streamlit form hints and browser credential icon ── */
[data-testid="InputInstructions"]           { display: none !important; }
input::-webkit-credentials-auto-fill-button { visibility: hidden !important; pointer-events: none !important; }
input::-webkit-contacts-auto-fill-button    { visibility: hidden !important; pointer-events: none !important; }

/* ── Submit button — Tailwind full-width, padding-based ── */
body:not(.qa-has-sb) [data-testid="stFormSubmitButton"] button,
body:not(.qa-has-sb) [data-testid="stBaseButton-primaryFormSubmit"] button {
  display: flex !important;
  width: 100% !important;
  justify-content: center !important;
  background: #0891b2 !important;
  color: #fff !important;
  font-weight: 600 !important;
  font-size: 1.05rem !important;
  line-height: 1.5 !important;
  border-radius: 6px !important;
  border: none !important;
  padding: .7rem 1.5rem !important;
  height: auto !important;
  letter-spacing: .01em !important;
  transition: background .2s !important;
}
body:not(.qa-has-sb) [data-testid="stFormSubmitButton"] button:hover,
body:not(.qa-has-sb) [data-testid="stBaseButton-primaryFormSubmit"] button:hover {
  background: #0e7490 !important;
}
</style>"""


# JS que inyecta el panel izquierdo como div fijo en el parent DOM.
_LOGIN_LEFT_JS = """<script>
(function(){
var D=window.parent.document;
var B=D.body;

/* CSS — versión 3: forzar reinyección con nuevo ID */
var _oldCss=D.getElementById('qa-ll-css');if(_oldCss)_oldCss.remove();
var _oldCss2=D.getElementById('qa-ll-css-v2');if(_oldCss2)_oldCss2.remove();
if(!D.getElementById('qa-ll-css-v3')){
  var s=D.createElement('style');
  s.id='qa-ll-css-v3';
  s.textContent=`
    #qa-login-left{
      position:fixed;top:0;left:0;bottom:0;width:50%;
      background:linear-gradient(150deg,#05101e 0%,#091d2e 45%,#0c3040 100%);
      display:flex;flex-direction:column;justify-content:center;
      padding:3.5rem 5.5rem;z-index:50;overflow:hidden;
      border-right:1px solid #1e2d3d;
    }
    .qa-ll-glow1{
      position:absolute;top:-100px;right:-60px;
      width:420px;height:420px;border-radius:50%;pointer-events:none;
      background:radial-gradient(circle,rgba(0,188,212,.08) 0%,transparent 65%);
    }
    .qa-ll-glow2{
      position:absolute;bottom:-60px;left:-40px;
      width:300px;height:300px;border-radius:50%;pointer-events:none;
      background:radial-gradient(circle,rgba(14,79,107,.3) 0%,transparent 70%);
    }
    .qa-ll-brand{display:flex;align-items:center;gap:1rem;margin-bottom:3.5rem;}
    .qa-ll-brand-logo{
      width:64px;height:64px;background:#0c3d5c;border-radius:14px;flex-shrink:0;
      display:flex;align-items:center;justify-content:center;
      color:#00bcd4;font-weight:900;font-size:1.9rem;font-family:sans-serif;
    }
    .qa-ll-brand-name{color:#00bcd4;font-weight:800;font-size:1.75rem;letter-spacing:.07em;font-family:sans-serif;}
    .qa-ll-brand-sub{color:#4b5563;font-size:.88rem;letter-spacing:.12em;margin-top:4px;font-family:sans-serif;}

    .qa-ll-headline{
      color:#f9fafb;font-size:3.4rem;font-weight:800;line-height:1.15;
      margin-bottom:1.4rem;font-family:sans-serif;
    }
    .qa-ll-headline em{color:#22d3ee;font-style:normal;}
    .qa-ll-desc{
      color:#94a3b8;font-size:1.2rem;line-height:1.75;
      margin-bottom:3rem;max-width:460px;font-family:sans-serif;
    }
    .qa-ll-list{display:flex;flex-direction:column;gap:1.3rem;}
    .qa-ll-item{display:flex;align-items:flex-start;gap:.9rem;}
    .qa-ll-dot{
      width:30px;height:30px;background:#0c3d5c;border-radius:50%;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;
    }
    .qa-ll-dot svg{margin:0!important;}
    .qa-ll-item-body{font-family:sans-serif;}
    .qa-ll-item-title{color:#f1f5f9;font-size:1.15rem;font-weight:600;line-height:1.4;}
    .qa-ll-item-desc{color:#64748b;font-size:1.05rem;line-height:1.45;}
  `;
  D.head.appendChild(s);
}

/* Panel — solo crear si no existe */
if(D.getElementById('qa-login-left')) return;

var CHK='<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" '
  +'fill="none" stroke="#22d3ee" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
  +'style="margin:0"><path d="M20 6 9 17l-5-5"/></svg>';

function feat(title,desc){
  return '<div class="qa-ll-item">'
    +'<div class="qa-ll-dot">'+CHK+'</div>'
    +'<div class="qa-ll-item-body">'
    +'<div class="qa-ll-item-title">'+title+'</div>'
    +'<div class="qa-ll-item-desc">'+desc+'</div>'
    +'</div>'
    +'</div>';
}

var p=D.createElement('div');
p.id='qa-login-left';
p.innerHTML=
  '<div class="qa-ll-glow1"></div>'
  +'<div class="qa-ll-glow2"></div>'

  +'<div class="qa-ll-brand">'
  +'<div class="qa-ll-brand-logo">Q</div>'
  +'<div>'
  +'<div class="qa-ll-brand-name">QUALITYAI</div>'
  +'<div class="qa-ll-brand-sub">PIPELINE DE CALIDAD</div>'
  +'</div>'
  +'</div>'

  +'<h2 class="qa-ll-headline">Calidad de software<br>con <em>inteligencia artificial</em></h2>'
  +'<p class="qa-ll-desc">Transforma requerimientos en lenguaje natural en artefactos estructurados, listos para desarrollo y pruebas de software.</p>'

  +'<div class="qa-ll-list">'
  +feat('Historias de usuario','Criterios de aceptación detallados con revisión HITL')
  +feat('Test cases Gherkin','Clasificación automática según ISO 25010')
  +feat('Reportes ejecutivos','Análisis de riesgo y cobertura · Exportación PDF')
  +'</div>';

B.appendChild(p);
})();
</script>"""


def render_login() -> None:
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)
    components.html(_LOGIN_LEFT_JS, height=0, scrolling=False)

    # ── Heading ───────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin-bottom:2.25rem">'
        '<div style="color:#f9fafb;font-size:58px;font-weight:800;margin:0 0 12px;line-height:1.15;font-family:sans-serif;letter-spacing:-.5px">'
        'Bienvenido de nuevo</div>'
        '<div style="color:#9ca3af;font-size:20px;margin:0;line-height:1.5;font-family:sans-serif">'
        'Ingresa tus credenciales para continuar</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Inline error banner (set by api.post_login on failure) ────────────────
    _err = st.session_state.pop("_login_err", None)
    if _err:
        st.markdown(
            f'<div style="background:#450a0a;border:1px solid #991b1b;border-radius:8px;'
            f'padding:.75rem 1rem;margin-bottom:1rem;display:flex;align-items:center;gap:.6rem;">'
            f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2.5"'
            f' stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0">'
            f'<circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>'
            f'<span style="color:#fca5a5;font-family:sans-serif;font-size:.93rem;">{_err}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Form ──────────────────────────────────────────────────────────────────
    with st.form("login_form", clear_on_submit=False):
        email    = st.text_input("Correo electrónico", placeholder="usuario@empresa.com")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••")
        submitted = st.form_submit_button(
            "Iniciar sesión", use_container_width=True, type="primary",
        )

    if submitted:
        if not email.strip() or not password:
            st.session_state["_login_err"] = "Ingresa tu correo y contraseña."
            st.rerun()
            return
        with st.spinner("Autenticando…"):
            data = api.post_login(
                f"{BACKEND}/auth/login",
                {"email": email.strip(), "password": password},
            )
        if data:
            st.session_state.token      = data["access_token"]
            st.session_state.user_email = data["email"]
            st.session_state.user_role  = data["role"]
            st.session_state.user_name  = data.get("name", "")
            if data["role"] == "admin":
                st.session_state.view = "admin_users"
            elif data["role"] == "scrum_leader":
                st.session_state.view = "scrum_projects"
            else:
                st.session_state.view = "analyst_projects"
            # Persist auth to localStorage so hard-refresh restores the session
            import json as _json
            _auth_payload = _json.dumps({
                "token": data["access_token"],
                "email": data["email"],
                "role":  data["role"],
                "name":  data.get("name", ""),
            }).replace("\\", "\\\\").replace("`", "\\`")
            components.html(
                f"""<script>
(function(){{
  try{{window.parent.localStorage.setItem('qa-auth',`{_auth_payload}`);}}catch(ex){{}}
}})();
</script>""",
                height=0, scrolling=False,
            )
            st.switch_page("app.py")
