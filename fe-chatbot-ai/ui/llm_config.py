"""Configuración de proveedores LLM — panel izquierdo (keys/modelo) + panel derecho (orden drag-and-drop)."""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

import api
from config import BACKEND

_PROVIDERS: dict[str, dict] = {
    "gemini":   {"label": "Google Gemini",  "color": "#4285F4", "hint": "AIza…"},
    "groq":     {"label": "Groq",           "color": "#F5A623", "hint": "gsk_…"},
    "cerebras": {"label": "Cerebras",       "color": "#9B59B6", "hint": "csk-…"},
    "deepseek": {"label": "DeepSeek",       "color": "#00bfa5", "hint": "sk-…"},
}
_ALL = list(_PROVIDERS.keys())
_DEFAULT_MODELS: dict[str, str] = {
    "gemini":   "gemini-2.0-flash",
    "groq":     "llama-3.3-70b-versatile",
    "cerebras": "llama-3.3-70b",
    "deepseek": "deepseek-chat",
}


def _load() -> None:
    cfg = api.get(f"{BACKEND}/admin/llm-config") or {}
    st.session_state["llm_order"] = list(cfg.get("provider_order", _ALL[:]))
    st.session_state["llm_providers"] = cfg.get("providers", {
        p: {"keys": [], "model": _DEFAULT_MODELS[p]} for p in _ALL
    })
    for p in _ALL:
        st.session_state.setdefault(f"llm_rm_{p}", [])
        st.session_state.setdefault(f"llm_add_{p}", [])


def render_llm_config() -> None:
    st.markdown(
        '<div style="color:#e2e8f0;font-size:1.05rem;font-weight:600;'
        'margin-bottom:.75rem;font-family:sans-serif;">Configuración de Modelos LLM</div>',
        unsafe_allow_html=True,
    )

    if "llm_order" not in st.session_state:
        _load()

    models_map: dict = api.get(f"{BACKEND}/admin/llm-models") or {}
    order: list[str] = st.session_state["llm_order"]
    providers_data: dict = st.session_state["llm_providers"]

    col_left, col_right = st.columns([3, 2], gap="large")

    # ── Left: provider key/model config ──────────────────────────────────────
    with col_left:
        st.markdown(
            '<div style="font-size:.75rem;color:#8b949e;letter-spacing:.07em;'
            'margin-bottom:.6rem;">PROVEEDORES — MODELOS Y API KEYS</div>',
            unsafe_allow_html=True,
        )
        for p in _ALL:
            _render_provider_card(p, providers_data, models_map)

    # ── Right: drag-and-drop priority list ───────────────────────────────────
    with col_right:
        st.markdown(
            '<div style="font-size:.75rem;color:#8b949e;letter-spacing:.07em;'
            'margin-bottom:.6rem;">ORDEN DE PRIORIDAD</div>',
            unsafe_allow_html=True,
        )
        _render_drag_order(order, providers_data)

    # ── Save ─────────────────────────────────────────────────────────────────
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    if st.button(
        "Guardar y aplicar configuración",
        type="primary",
        use_container_width=True,
        key="llm_save",
    ):
        _save(order, providers_data)


# ── Left panel: per-provider card ────────────────────────────────────────────

def _render_provider_card(p: str, providers_data: dict, models_map: dict) -> None:
    meta = _PROVIDERS[p]
    pdata = providers_data.get(p, {})
    key_count = len(pdata.get("keys", []))
    key_badge = (
        f'<span style="background:#052e16;color:#4ade80;font-size:.68rem;'
        f'padding:.1rem .4rem;border-radius:5px;margin-left:.4rem;">'
        f'{key_count} key{"s" if key_count != 1 else ""}</span>'
        if key_count else
        '<span style="background:#450a0a;color:#fca5a5;font-size:.68rem;'
        'padding:.1rem .4rem;border-radius:5px;margin-left:.4rem;">sin keys</span>'
    )
    gem_note = (
        ' <span style="background:#1a2a4a;color:#93c5fd;font-size:.65rem;'
        'padding:.1rem .4rem;border-radius:5px;margin-left:.25rem;">embeddings</span>'
        if p == "gemini" else ""
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:.45rem;margin-bottom:.4rem;">'
        f'<span style="width:10px;height:10px;border-radius:50%;'
        f'background:{meta["color"]};display:inline-block;flex-shrink:0;"></span>'
        f'<span style="color:#e2e8f0;font-weight:700;font-size:.95rem;">{meta["label"]}</span>'
        f'{key_badge}{gem_note}</div>',
        unsafe_allow_html=True,
    )

    # Model selector
    model_list = models_map.get(p, [_DEFAULT_MODELS[p]])
    current_model = pdata.get("model", _DEFAULT_MODELS[p])
    try:
        midx = model_list.index(current_model)
    except ValueError:
        midx = 0
    st.selectbox(
        "Modelo",
        model_list,
        index=midx,
        key=f"llm_model_{p}",
        label_visibility="collapsed",
    )

    # Existing keys
    rm_set = set(st.session_state.get(f"llm_rm_{p}", []))
    add_lst = list(st.session_state.get(f"llm_add_{p}", []))
    raw_keys: list[dict] = pdata.get("keys", [])
    active_keys = [k for k in raw_keys if k["index"] not in rm_set]

    if active_keys or add_lst:
        for k in active_keys:
            col_k, col_x = st.columns([6, 0.55])
            with col_k:
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #30363d;'
                    f'border-radius:6px;padding:.28rem .65rem;font-size:.8rem;'
                    f'font-family:monospace;color:#7dd3fc;">● {k["preview"]}</div>',
                    unsafe_allow_html=True,
                )
            with col_x:
                if st.button("✕", key=f"llm_rmk_{p}_{k['index']}"):
                    st.session_state[f"llm_rm_{p}"] = list(rm_set | {k["index"]})
                    st.rerun()
        for j, nk in enumerate(add_lst):
            preview = nk[:6] + "…" + nk[-4:] if len(nk) > 12 else "●" * len(nk)
            col_k, col_x = st.columns([6, 0.55])
            with col_k:
                st.markdown(
                    f'<div style="background:#0a2014;border:1px solid #166534;'
                    f'border-radius:6px;padding:.28rem .65rem;font-size:.8rem;'
                    f'font-family:monospace;color:#4ade80;">+ {preview} '
                    f'<span style="font-size:.7rem;color:#6ee7b7;">(nueva)</span></div>',
                    unsafe_allow_html=True,
                )
            with col_x:
                if st.button("✕", key=f"llm_rmnew_{p}_{j}"):
                    lst = list(st.session_state[f"llm_add_{p}"])
                    lst.pop(j)
                    st.session_state[f"llm_add_{p}"] = lst
                    st.rerun()
    else:
        st.markdown(
            '<div style="font-size:.77rem;color:#4b5563;margin:.15rem 0 .2rem;">'
            'Sin API keys configuradas.</div>',
            unsafe_allow_html=True,
        )

    # Add new key row
    ctr = st.session_state.get(f"llm_newkey_ctr_{p}", 0)
    col_inp, col_add = st.columns([5, 1])
    with col_inp:
        new_key_val = st.text_input(
            "Nueva key",
            key=f"llm_newkey_{p}_{ctr}",
            placeholder=meta["hint"],
            type="password",
            label_visibility="collapsed",
        )
    with col_add:
        if st.button("+ Agregar", key=f"llm_addkey_{p}", use_container_width=True):
            if new_key_val and new_key_val.strip():
                lst = list(st.session_state.get(f"llm_add_{p}", []))
                lst.append(new_key_val.strip())
                st.session_state[f"llm_add_{p}"] = lst
                st.session_state[f"llm_newkey_ctr_{p}"] = ctr + 1
                st.rerun()

    st.markdown(
        '<hr style="border:none;border-top:1px solid #21262d;margin:.7rem 0;">',
        unsafe_allow_html=True,
    )


# ── Right panel: drag-and-drop order ─────────────────────────────────────────

def _render_drag_order(order: list[str], providers_data: dict) -> None:
    """Render an HTML5 drag-and-drop priority list inside a components.html iframe.
    On drop, JS sends new order via ?_llm_order= query param → app.py stores in session_state."""

    items_js = json.dumps([
        {
            "id": p,
            "label": _PROVIDERS.get(p, {}).get("label", p),
            "color": _PROVIDERS.get(p, {}).get("color", "#888"),
            "keys": len(providers_data.get(p, {}).get("keys", [])),
        }
        for p in order
    ])

    html = f"""
<style>
  body{{margin:0;padding:0;background:transparent;font-family:sans-serif;}}
  #drag-list{{list-style:none;margin:0;padding:0;}}
  .drag-item{{
    display:flex;align-items:center;gap:.6rem;
    background:#0d1117;border:1px solid #21262d;border-radius:8px;
    padding:.55rem .75rem;margin-bottom:.4rem;cursor:grab;
    transition:background .15s,border-color .15s,transform .1s;
    user-select:none;
  }}
  .drag-item:active{{cursor:grabbing;}}
  .drag-item.drag-over{{
    border-color:#0891b2;background:#0e2a38;transform:scale(1.01);
  }}
  .drag-item.dragging{{opacity:.4;}}
  .handle{{color:#4b5563;font-size:1rem;flex-shrink:0;line-height:1;}}
  .rank{{
    width:1.5rem;height:1.5rem;border-radius:50%;
    background:#1a1f2e;color:#8b949e;font-size:.78rem;font-weight:700;
    display:flex;align-items:center;justify-content:center;flex-shrink:0;
  }}
  .dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
  .label{{color:#e2e8f0;font-size:.88rem;font-weight:600;flex:1;}}
  .badge{{
    font-size:.65rem;padding:.1rem .38rem;border-radius:5px;flex-shrink:0;
  }}
  .badge-keys{{background:#052e16;color:#4ade80;}}
  .badge-nokeys{{background:#450a0a;color:#fca5a5;}}
  .badge-primary{{background:#0e3a4a;color:#00bcd4;}}
  .hint{{color:#4b5563;font-size:.75rem;margin-top:.5rem;text-align:center;}}
</style>

<ul id="drag-list"></ul>
<div class="hint">⠿ Arrastra para cambiar el orden</div>

<script>
(function(){{
  var W = window.parent;
  var items = {items_js};
  var list  = document.getElementById('drag-list');
  var dragged = null;

  function renderList() {{
    list.innerHTML = '';
    items.forEach(function(it, i) {{
      var li = document.createElement('li');
      li.className = 'drag-item';
      li.setAttribute('draggable','true');
      li.dataset.id = it.id;

      var keysHtml = it.keys > 0
        ? '<span class="badge badge-keys">' + it.keys + ' key' + (it.keys===1?'':'s') + '</span>'
        : '<span class="badge badge-nokeys">sin keys</span>';
      var primaryHtml = i === 0
        ? '<span class="badge badge-primary">primario</span>' : '';

      li.innerHTML =
        '<span class="handle">⠿</span>' +
        '<span class="rank">' + (i+1) + '</span>' +
        '<span class="dot" style="background:' + it.color + '"></span>' +
        '<span class="label">' + it.label + '</span>' +
        keysHtml + primaryHtml;

      li.addEventListener('dragstart', function(e) {{
        dragged = li;
        setTimeout(function(){{ li.classList.add('dragging'); }}, 0);
        e.dataTransfer.effectAllowed = 'move';
      }});
      li.addEventListener('dragend', function() {{
        li.classList.remove('dragging');
        list.querySelectorAll('.drag-item').forEach(function(el){{
          el.classList.remove('drag-over');
        }});
        // Read new order from DOM and send to Python via query param
        var newOrder = Array.from(list.querySelectorAll('.drag-item'))
          .map(function(el){{ return el.dataset.id; }});
        var u = new URL(W.location.href);
        u.searchParams.set('_llm_order', newOrder.join(','));
        W.location.replace(u.toString());
      }});
      li.addEventListener('dragover', function(e) {{
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if(dragged && dragged !== li) {{
          list.querySelectorAll('.drag-item').forEach(function(el){{
            el.classList.remove('drag-over');
          }});
          li.classList.add('drag-over');
        }}
      }});
      li.addEventListener('drop', function(e) {{
        e.preventDefault();
        if(!dragged || dragged === li) return;
        var allItems = Array.from(list.querySelectorAll('.drag-item'));
        var fromIdx = allItems.indexOf(dragged);
        var toIdx   = allItems.indexOf(li);
        // Reorder items array
        var moved = items.splice(fromIdx, 1)[0];
        items.splice(toIdx, 0, moved);
        renderList();
      }});

      list.appendChild(li);
    }});
  }}

  renderList();
}})();
</script>
"""
    components.html(html, height=len(order) * 58 + 40, scrolling=False)


# ── Save ─────────────────────────────────────────────────────────────────────

def _save(order: list[str], providers_data: dict) -> None:
    providers_payload: dict = {}
    for p in _ALL:
        pdata = providers_data.get(p, {})
        providers_payload[p] = {
            "model": st.session_state.get(
                f"llm_model_{p}", pdata.get("model", _DEFAULT_MODELS.get(p, ""))
            ),
            "add_keys":       list(st.session_state.get(f"llm_add_{p}", [])),
            "remove_indices": list(st.session_state.get(f"llm_rm_{p}", [])),
        }

    payload = {"provider_order": order, "providers": providers_payload}

    with st.spinner("Aplicando configuración y haciendo hot-swap del LLM…"):
        result = api.patch(f"{BACKEND}/admin/llm-config", payload)

    if result is not None:
        for key in list(st.session_state.keys()):
            if key.startswith("llm_"):
                del st.session_state[key]
        st.success("Configuración guardada y aplicada correctamente.")
        st.rerun()
