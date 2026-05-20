"""Custom minimizable sidebar injected into parent DOM via components.html()."""
from datetime import datetime
import json

import streamlit as st
import streamlit.components.v1 as components

from ui.icons import icon

_ROLE_DISPLAY = {
    "admin":        "Administrador",
    "scrum_leader": "Scrum Leader",
    "analyst":      "Analista",
    "developer":    "Desarrollador",
}
_NAV = {
    "admin": [
        {"label": "Usuarios",    "icon": "users",  "key": "nav_admin_users", "view": "admin_users",    "extra": {}},
        {"label": "Proyectos",   "icon": "folder", "key": "nav_admin_proj",  "view": "scrum_projects", "extra": {"scrum_selected_project": None}},
        {"label": "Config. LLM", "icon": "cog",    "key": "nav_llm_config",  "view": "llm_config",     "extra": {}},
    ],
    "scrum_leader": [
        {"label": "Mis proyectos", "icon": "folder", "key": "nav_scrum_projects", "view": "scrum_projects", "extra": {"scrum_selected_project": None}},
    ],
    "analyst": [
        {"label": "Mis proyectos", "icon": "beaker", "key": "nav_analyst_proj", "view": "analyst_projects", "extra": {"analyst_selected_project": None}},
    ],
}

_AVATAR_PALETTE = [
    "#0c3d5c", "#1e3a5f", "#134e4a", "#1e1b4b", "#3b1f2b", "#1a2c3d",
]


def _initials(name: str, email: str) -> str:
    src = name.strip() if name and name.strip() else email.split("@")[0].replace(".", " ").replace("-", " ").replace("_", " ")
    parts = src.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return src[:2].upper()


def _avatar_color(email: str) -> str:
    h = 0
    for c in email:
        h = (h * 31 + ord(c)) & 0xFFFF
    return _AVATAR_PALETTE[h % len(_AVATAR_PALETTE)]


@st.fragment
def _render_hidden_nav() -> None:
    """Hidden nav buttons. Must be called from within a st.sidebar context so the
    fragment inherits it — fragments cannot open outside containers themselves."""
    role = st.session_state.get("user_role", "")
    for item in _NAV.get(role, []):
        if st.button(item["label"], key=f"__navbtn_{item['key']}"):
            for k, v in item["extra"].items():
                st.session_state[k] = v
            st.session_state.view = item["view"]
            st.rerun()


def render_sidebar() -> None:
    """Render the visual sidebar and register the navigation fragment."""
    role      = st.session_state.get("user_role")
    email     = st.session_state.get("user_email", "")
    name      = st.session_state.get("user_name", "")
    view      = st.session_state.get("view", "")
    projects  = st.session_state.get("projects", [])
    active    = st.session_state.get("active_project")
    nav_items = _NAV.get(role, [])

    # ── Display name and avatar ───────────────────────────────────────────────
    display_name = (
        name.strip() if name and name.strip()
        else email.split("@")[0].replace(".", " ").replace("-", " ").replace("_", " ").title()
    )
    initials    = _initials(name, email)
    avatar_bg   = _avatar_color(email)

    # ── Build data for injected JS ────────────────────────────────────────────
    nav_data = []
    for item in nav_items:
        nav_data.append({
            "label":   item["label"],
            "lbl":     item["label"],
            "ico":     icon(item["icon"], 20, "#9ca3af"),
            "ico_act": icon(item["icon"], 20, "#00bcd4"),
            "active":  view == item["view"],
        })

    hist_data = []
    for proj in projects[:8]:
        pid    = proj["run_id"]
        ts_raw = proj.get("timestamp", proj.get("created_at", ""))
        try:
            ts = datetime.fromisoformat(str(ts_raw)).strftime("%d/%m %H:%M")
        except Exception:
            ts = str(ts_raw)[:16]
        pname = proj.get("project_name") or proj.get("req_preview", "Análisis")
        pname = pname[:22] + ("…" if len(pname) > 22 else "")
        hist_data.append({
            "label":  pname,
            "ts":     ts,
            "lbl":    f"R:{pid[:8]}",
            "active": pid == active,
        })

    data = {
        "logout_svg":   icon("logout", 20, "#ef4444"),
        "chev_col":     icon("chevrons-left",  15, "#9ca3af"),
        "chev_exp":     icon("chevrons-right", 15, "#9ca3af"),
        "doc_svg":      icon("document", 14, "#6b7280"),
        "email":        email,
        "display_name": display_name,
        "role_label":   _ROLE_DISPLAY.get(role, role),
        "initials":     initials,
        "avatar_bg":    avatar_bg,
        "nav":          nav_data,
        "hist":         hist_data,
    }

    with st.sidebar:
        _render_hidden_nav()   # fragment inherits sidebar context → buttons render off-screen
    _inject(data)              # visual sidebar + JS clicker


def clear_sidebar() -> None:
    """Remove the injected sidebar from the DOM (call on login/logout page)."""
    components.html(
        """<script>
(function(){
  var D=window.parent.document;
  var sb=D.getElementById('qa-sb');
  if(sb) sb.remove();
  D.body.classList.remove('qa-has-sb','qa-mini');
})();
</script>""",
        height=0, scrolling=False,
    )


def _inject(data: dict) -> None:
    data_json = json.dumps(data, ensure_ascii=False)
    js = _SB_JS.replace("__QADATA__", data_json)
    components.html(js, height=0, scrolling=False)


# Plain string — not an f-string. {} are CSS braces, not Python format placeholders.
_SB_JS = """
<script>
(function(){
var D=window.parent.document;
var B=D.body;
var P=window.parent;

// ── CSS (injected once per page load) ────────────────────────────────────────
if(!D.getElementById('qa-sb-css')){
  var s=D.createElement('style');
  s.id='qa-sb-css';
  s.textContent=`
    #qa-sb{
      position:fixed!important;top:0;left:0;bottom:0;width:256px;
      background:#111827;border-right:1px solid #1f2937;
      display:flex;flex-direction:column;
      z-index:99999;transition:width .25s ease;overflow:hidden;
    }
    body.qa-mini #qa-sb{width:64px;}

    .qa-sb-brand{
      display:flex;align-items:center;padding:.9rem .85rem;
      gap:.55rem;border-bottom:1px solid #1f2937;flex-shrink:0;
    }
    body.qa-mini .qa-sb-brand{padding:.75rem;justify-content:center;}
    body.qa-mini .qa-sb-logo{display:none!important;}
    body.qa-mini .qa-sb-brand-text{display:none!important;}
    .qa-sb-logo{
      width:32px;height:32px;background:#0c3d5c;border-radius:8px;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;
      color:#00bcd4;font-weight:800;font-size:1.05rem;font-family:sans-serif;
    }
    .qa-sb-brand-text{
      flex:1;min-width:0;overflow:hidden;max-width:200px;
      transition:max-width .25s ease,opacity .2s ease;
    }
    body.qa-mini .qa-sb-brand-text{max-width:0;opacity:0;}
    .qa-sb-title{color:#00bcd4;font-weight:800;font-size:.87rem;letter-spacing:.07em;white-space:nowrap;font-family:sans-serif;}
    .qa-sb-sub{color:#4b5563;font-size:.63rem;letter-spacing:.08em;white-space:nowrap;font-family:sans-serif;}
    .qa-toggle-btn{
      flex-shrink:0;background:transparent;border:none;cursor:pointer;
      padding:4px;border-radius:5px;display:flex;align-items:center;justify-content:center;
      transition:background .15s;line-height:0;
    }
    .qa-toggle-btn:hover{background:#1f2937;}
    .qa-toggle-btn svg{margin:0!important;display:block;}

    .qa-nav{display:flex;flex-direction:column;padding:.3rem 0;flex-shrink:0;}
    .qa-nav-item,.qa-hist-item{
      display:flex;align-items:center;padding:.58rem .85rem;
      background:transparent;border:none;cursor:pointer;
      text-align:left;white-space:nowrap;width:100%;
      transition:background .15s,color .15s;color:#9ca3af;font-size:.88rem;font-family:sans-serif;
    }
    body.qa-mini .qa-nav-item,body.qa-mini .qa-hist-item{justify-content:center;padding:.68rem 0;}
    .qa-nav-item:hover,.qa-hist-item:hover{background:#1f2937;color:#e2e8f0;}
    .qa-nav-item.qa-active{background:#082f49!important;color:#00bcd4!important;border-left:3px solid #00bcd4;}
    body.qa-mini .qa-nav-item.qa-active{border-left:2px solid #00bcd4;}
    .qa-hist-item.qa-active{background:#082f49!important;color:#00bcd4!important;}

    .qa-divider{height:1px;background:#1f2937;flex-shrink:0;margin:.3rem 0;}
    .qa-sect-lbl{padding:.45rem .85rem .2rem;color:#4b5563;font-size:.67rem;letter-spacing:.1em;white-space:nowrap;font-family:sans-serif;}
    .qa-hist{display:flex;flex-direction:column;overflow-y:auto;max-height:200px;flex-shrink:0;}
    .qa-hist-name{font-size:.79rem;color:#d1d5db;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:148px;font-family:sans-serif;}
    .qa-hist-ts{font-size:.67rem;color:#6b7280;font-family:sans-serif;}

    .qa-sb-bottom{flex-shrink:0;border-top:1px solid #1f2937;}
    .qa-sb-user-row{display:flex;align-items:center;gap:.6rem;padding:.65rem .85rem;cursor:default;}
    body.qa-mini .qa-sb-user-row{justify-content:center;padding:.65rem 0;}
    .qa-avatar{
      width:34px;height:34px;border-radius:50%;flex-shrink:0;
      display:flex;align-items:center;justify-content:center;
      font-weight:700;font-size:.8rem;color:#fff;font-family:sans-serif;
      letter-spacing:.04em;
    }
    .qa-sb-uname{font-size:.8rem;color:#e2e8f0;font-weight:600;white-space:nowrap;font-family:sans-serif;}
    .qa-sb-urole{font-size:.68rem;color:#6b7280;white-space:nowrap;font-family:sans-serif;}
    .qa-logout-btn{
      display:flex;align-items:center;padding:.48rem .85rem;margin-bottom:.35rem;
      background:transparent;border:none;cursor:pointer;
      text-align:left;white-space:nowrap;width:100%;
      color:#ef4444;font-size:.88rem;font-family:sans-serif;transition:background .15s;
    }
    body.qa-mini .qa-logout-btn{justify-content:center;padding:.55rem 0;}
    .qa-logout-btn:hover{background:rgba(127,29,29,.15);}

    .qalbl{overflow:hidden;white-space:nowrap;max-width:180px;transition:max-width .25s ease,opacity .2s ease;}
    body.qa-mini .qalbl{max-width:0;opacity:0;pointer-events:none;}
  `;
  D.head.appendChild(s);
}

// ── Remove login left panel if present (page just authenticated) ─────────────
var _ll=D.getElementById('qa-login-left');if(_ll)_ll.remove();
var _llc=D.getElementById('qa-ll-css');if(_llc)_llc.remove();

// ── Sidebar click handler — injected ONCE into parent head (never destroyed) ──
// v6: Clicks hidden Streamlit button in off-screen sidebar → WebSocket rerun, no page reload.
var _oc=D.getElementById('qa-sb-clicker');
if(_oc&&_oc.getAttribute('data-ver')!=='6'){_oc.remove();_oc=null;}
if(!D.getElementById('qa-sb-clicker')){
  var _cs=D.createElement('script');_cs.id='qa-sb-clicker';
  _cs.setAttribute('data-ver','6');
  _cs.textContent=`
    function _qaRedirect(lbl){
      var auth=null;
      try{auth=JSON.parse(localStorage.getItem('qa-auth')||'null');}catch(ex){}
      var u=new URL(window.location.href);
      u.searchParams.set('_nav',lbl);
      if(auth&&auth.token)u.searchParams.set('_qt',auth.token);
      window.location.replace(u.toString());
    }
    document.addEventListener('click',function(e){
      if(!e.target||typeof e.target.closest!=='function') return;
      var sb=document.getElementById('qa-sb');
      if(!sb||!e.target.closest('#qa-sb')) return;

      /* Toggle mini */
      if(e.target.closest('.qa-toggle-btn')){
        var mini=localStorage.getItem('qa-sb-mini')==='1';
        mini=!mini;
        try{localStorage.setItem('qa-sb-mini',mini?'1':'0');}catch(err){}
        if(mini) document.body.classList.add('qa-mini');
        else     document.body.classList.remove('qa-mini');
        var chev=window.__qaChevs;
        var t=sb.querySelector('.qa-toggle-btn');
        if(t&&chev) t.innerHTML=mini?chev.exp:chev.col;
        return;
      }

      /* Logout */
      if(e.target.closest('.qa-logout-btn')){
        try{localStorage.removeItem('qa-auth');}catch(ex){}
        window.location.replace('/login?logout=1');
        return;
      }

      /* Nav */
      var btn=e.target.closest('[data-lbl]');
      if(!btn) return;
      var lbl=btn.getAttribute('data-lbl');

      /* History report items have no pre-rendered button — URL redirect */
      if(lbl.startsWith('R:')){_qaRedirect(lbl);return;}

      /* Click the hidden Streamlit button in the off-screen native sidebar.
         Streamlit processes it via WebSocket → fragment reruns → st.rerun() → no page reload. */
      var found=false;
      var stSb=document.querySelector('section[data-testid="stSidebar"]');
      if(stSb){
        var btns=stSb.querySelectorAll('button');
        for(var i=0;i<btns.length;i++){
          if(btns[i].textContent.trim()===lbl){
            btns[i].click();
            found=true;
            break;
          }
        }
      }
      if(!found) _qaRedirect(lbl);
    },true);
  `;
  D.head.appendChild(_cs);
}

// ── Data ──────────────────────────────────────────────────────────────────────
var d=__QADATA__;
P.__qaChevs={col:d.chev_col, exp:d.chev_exp};

// ── Mini state ────────────────────────────────────────────────────────────────
var mini=false;
try{mini=localStorage.getItem('qa-sb-mini')==='1';}catch(e){}
B.classList.add('qa-has-sb');
if(mini) B.classList.add('qa-mini');
else     B.classList.remove('qa-mini');

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function _navSig(){
  return d.nav.map(function(n){return n.lbl+(n.active?'*':'');}).join('|');
}
function _histSig(){
  return d.hist.map(function(h){return h.lbl+(h.active?'*':'')+h.ts;}).join('|');
}

function _navInner(){
  var h='';
  for(var i=0;i<d.nav.length;i++){
    var n=d.nav[i];
    var cls='qa-nav-item'+(n.active?' qa-active':'');
    h+='<button class="'+cls+'" data-lbl="'+esc(n.lbl)+'" title="'+esc(n.label)+'">'
      +'<span class="qa-nav-ico">'+(n.active?n.ico_act:n.ico)+'</span>'
      +'<span class="qalbl" style="margin-left:.5rem">'+esc(n.label)+'</span>'
      +'</button>';
  }
  return h;
}
function _histInner(){
  if(!d.hist.length) return '';
  var h='<div class="qa-divider"></div><div class="qa-hist">'
    +'<div class="qa-sect-lbl qalbl">REPORTES</div>';
  for(var i=0;i<d.hist.length;i++){
    var p=d.hist[i];
    var cls='qa-hist-item'+(p.active?' qa-active':'');
    h+='<button class="'+cls+'" data-lbl="'+esc(p.lbl)+'" title="'+esc(p.label)+'">'
      +d.doc_svg
      +'<div class="qalbl" style="margin-left:.4rem;min-width:0">'
      +'<div class="qa-hist-name">'+esc(p.label)+'</div>'
      +'<div class="qa-hist-ts">'+esc(p.ts)+'</div>'
      +'</div>'
      +'</button>';
  }
  h+='</div>';
  return h;
}

// ── Create sidebar (first render) or surgical update (subsequent renders) ─────
var SB_VER='9';
var sb=D.getElementById('qa-sb');
if(sb && sb.getAttribute('data-ver')!==SB_VER){sb.remove();sb=null;}

if(!sb){
  // ── First render: build full sidebar ─────────────────────────────────────
  sb=D.createElement('div');
  sb.id='qa-sb';
  sb.setAttribute('data-ver',SB_VER);
  B.appendChild(sb);

  sb.innerHTML=
    '<div class="qa-sb-brand">'
    +'<div class="qa-sb-logo">Q</div>'
    +'<div class="qa-sb-brand-text">'
    +'<div class="qa-sb-title">QUALITYAI</div>'
    +'<div class="qa-sb-sub">PIPELINE DE CALIDAD</div>'
    +'</div>'
    +'<button class="qa-toggle-btn" title="Minimizar / expandir">'
    +(mini?d.chev_exp:d.chev_col)
    +'</button>'
    +'</div>'
    +'<div class="qa-divider"></div>'
    +'<nav class="qa-nav" id="qa-sb-nav" data-sig="">'+_navInner()+'</nav>'
    +'<div id="qa-sb-hist" data-sig=""></div>'
    +'<div style="flex:1"></div>'
    +'<div class="qa-sb-bottom">'
    +'<div class="qa-sb-user-row">'
    +'<div class="qa-avatar" style="background:'+d.avatar_bg+'">'+esc(d.initials)+'</div>'
    +'<div class="qalbl" style="margin-left:.35rem;min-width:0;overflow:hidden">'
    +'<div class="qa-sb-uname">'+esc(d.display_name)+'</div>'
    +'<div class="qa-sb-urole">'+esc(d.role_label)+'</div>'
    +'</div>'
    +'</div>'
    +'<button class="qa-logout-btn" title="Cerrar sesión">'
    +d.logout_svg
    +'<span class="qalbl" style="margin-left:.5rem">Cerrar sesión</span>'
    +'</button>'
    +'</div>';

  // Store initial signatures
  var navEl=sb.querySelector('#qa-sb-nav');
  if(navEl) navEl.setAttribute('data-sig',_navSig());
  var histEl=sb.querySelector('#qa-sb-hist');
  if(histEl){histEl.innerHTML=_histInner();histEl.setAttribute('data-sig',_histSig());}

} else {
  // ── Subsequent renders: only update what changed ──────────────────────────

  // Nav: only update if active item changed
  var navEl=sb.querySelector('#qa-sb-nav');
  if(navEl && navEl.getAttribute('data-sig')!==_navSig()){
    navEl.innerHTML=_navInner();
    navEl.setAttribute('data-sig',_navSig());
  }

  // Hist: only update if list or active changed
  var histEl=sb.querySelector('#qa-sb-hist');
  if(histEl && histEl.getAttribute('data-sig')!==_histSig()){
    histEl.innerHTML=_histInner();
    histEl.setAttribute('data-sig',_histSig());
  }
}

})();
</script>
"""
