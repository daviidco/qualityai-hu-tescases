"""Configuración de proveedores LLM — panel izquierdo (keys/modelo) + panel derecho (orden de prioridad)."""
from __future__ import annotations

import streamlit as st

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

    # ── Right: priority order controls ───────────────────────────────────────
    with col_right:
        st.markdown(
            '<div style="font-size:.75rem;color:#8b949e;letter-spacing:.07em;'
            'margin-bottom:.6rem;">ORDEN DE PRIORIDAD</div>',
            unsafe_allow_html=True,
        )
        _render_order_controls(order, providers_data)

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


# ── Right panel: native priority order controls ───────────────────────────────

def _render_order_controls(order: list[str], providers_data: dict) -> None:
    """Botones ↑/↓ nativos de Streamlit para reordenar proveedores.

    El orden vive exclusivamente en st.session_state["llm_order"]; no hay
    comunicación JS→Python, por lo que el estado persiste correctamente en
    todos los reruns y recargas.
    """
    _ROW_CSS = (
        "<style>"
        "[class*='st-key-llm_up_'],[class*='st-key-llm_dn_']{"
        "  button{padding:0!important;min-height:1.6rem!important;"
        "  font-size:.85rem!important;background:transparent!important;"
        "  border:1px solid #30363d!important;color:#8b949e!important;}"
        "  button:hover{border-color:#58a6ff!important;color:#58a6ff!important;}"
        "}"
        "</style>"
    )
    st.markdown(_ROW_CSS, unsafe_allow_html=True)

    for i, p in enumerate(order):
        meta = _PROVIDERS.get(p, {})
        key_count = len(providers_data.get(p, {}).get("keys", []))

        is_primary = i == 0
        border_color = "#0891b2" if is_primary else "#21262d"
        bg_color = "#061a22" if is_primary else "#0d1117"

        key_badge = (
            f'<span style="background:#052e16;color:#4ade80;font-size:.65rem;'
            f'padding:.1rem .38rem;border-radius:5px;">'
            f'{key_count} key{"s" if key_count != 1 else ""}</span>'
            if key_count else
            '<span style="background:#450a0a;color:#fca5a5;font-size:.65rem;'
            'padding:.1rem .38rem;border-radius:5px;">sin keys</span>'
        )
        primary_badge = (
            '<span style="background:#0e3a4a;color:#00bcd4;font-size:.65rem;'
            'padding:.1rem .38rem;border-radius:5px;margin-left:.3rem;">primario</span>'
            if is_primary else ""
        )

        row_html = (
            f'<div style="display:flex;align-items:center;gap:.5rem;'
            f'background:{bg_color};border:1px solid {border_color};'
            f'border-radius:8px;padding:.45rem .7rem;margin-bottom:.35rem;">'
            f'<span style="width:1.4rem;height:1.4rem;border-radius:50%;'
            f'background:#1a1f2e;color:#8b949e;font-size:.75rem;font-weight:700;'
            f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
            f'{i + 1}</span>'
            f'<span style="width:9px;height:9px;border-radius:50%;'
            f'background:{meta.get("color","#888")};flex-shrink:0;"></span>'
            f'<span style="color:#e2e8f0;font-size:.88rem;font-weight:600;flex:1;">'
            f'{meta.get("label", p)}</span>'
            f'{key_badge}{primary_badge}'
            f'</div>'
        )

        col_row, col_up, col_dn = st.columns([6, 0.55, 0.55])
        with col_row:
            st.markdown(row_html, unsafe_allow_html=True)
        with col_up:
            disabled_up = i == 0
            if st.button("↑", key=f"llm_up_{p}", disabled=disabled_up, use_container_width=True):
                order[i - 1], order[i] = order[i], order[i - 1]
                st.session_state["llm_order"] = order[:]
                st.rerun()
        with col_dn:
            disabled_dn = i == len(order) - 1
            if st.button("↓", key=f"llm_dn_{p}", disabled=disabled_dn, use_container_width=True):
                order[i], order[i + 1] = order[i + 1], order[i]
                st.session_state["llm_order"] = order[:]
                st.rerun()


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
