"""Panel HITL — Fase 1: revisión de ambigüedades detectadas."""

import streamlit as st

_SEVERITY_COLOR = {"alta": "#dc2626", "media": "#d97706", "baja": "#6b7280"}
_SEVERITY_LABEL = {"alta": "ALTA", "media": "MEDIA", "baja": "BAJA"}


def render_ambiguity_review(on_submit) -> None:
    """Renderiza el panel de revisión de ambigüedades.

    on_submit(resolutions: list[dict]) se llama cuando el analista confirma.
    """
    ambiguities: list[dict] = st.session_state.hitl_ambiguities
    req_preview = st.session_state.hitl_requirement[:120]

    st.markdown(
        '<h3 style="color:#e2e8f0;margin-bottom:0.25rem;">Revisión de Ambigüedades</h3>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="color:#64748b;font-size:0.85rem;margin-bottom:1rem;">'
        f'Requerimiento: <em>"{req_preview}{"…" if len(st.session_state.hitl_requirement) > 120 else ""}"</em></div>',
        unsafe_allow_html=True,
    )

    st.info(
        f"Se detectaron **{len(ambiguities)} término(s) ambiguo(s)** según IEEE 830 / ISO 25010. "
        "Revisa cada uno y proporciona tu resolución antes de continuar. "
        "Tus resoluciones se inyectan como **hechos verificados** en el prompt del LLM.",
    )

    resolutions_state: dict = {}

    for i, amb in enumerate(ambiguities):
        sev_color = _SEVERITY_COLOR.get(amb["severity"], "#6b7280")
        sev_label = _SEVERITY_LABEL.get(amb["severity"], amb["severity"].upper())

        with st.container(border=True):
            col_word, col_sev = st.columns([4, 1])
            with col_word:
                st.markdown(
                    f'<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">"{amb["word"]}"</span>'
                    f' <span style="font-size:0.78rem;color:#64748b;"> — {amb["category"]}</span>',
                    unsafe_allow_html=True,
                )
            with col_sev:
                st.markdown(
                    f'<div style="text-align:right;">'
                    f'<span style="background:{sev_color}22;color:{sev_color};border:1px solid {sev_color};'
                    f'border-radius:20px;padding:.15rem .65rem;font-size:.92rem;font-weight:700;">'
                    f'{sev_label}</span></div>',
                    unsafe_allow_html=True,
                )

            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown(
                    f'<div style="font-size:.98rem;color:#94a3b8;">Contexto detectado</div>'
                    f'<div style="font-size:1rem;color:#cbd5e1;font-style:italic;margin-bottom:.5rem;">'
                    f'"{amb["context"]}"</div>'
                    f'<div style="font-size:.98rem;color:#94a3b8;">Violación IEEE 830</div>'
                    f'<div style="font-size:1rem;color:#cbd5e1;">{amb["ieee_830_violation"]}</div>',
                    unsafe_allow_html=True,
                )
            with col_r:
                st.markdown(
                    f'<div style="font-size:.98rem;color:#94a3b8;">Sugerencia automática</div>'
                    f'<div style="font-size:1rem;color:#22d3ee;margin-bottom:.5rem;">{amb["suggestion"]}</div>'
                    f'<div style="font-size:.98rem;color:#94a3b8;">ISO 25010</div>'
                    f'<div style="font-size:1rem;color:#cbd5e1;">{amb["iso_25010_category"]}</div>',
                    unsafe_allow_html=True,
                )

            action = st.radio(
                "Acción",
                options=["Aceptar sugerencia", "Resolución personalizada", "Descartar (no es ambigua)"],
                key=f"amb_action_{i}",
                horizontal=True,
                label_visibility="collapsed",
            )

            custom_text = ""
            if action == "Resolución personalizada":
                custom_text = st.text_input(
                    "Tu resolución",
                    placeholder="Ej: tiempo de respuesta < 2 s en percentil 95",
                    key=f"amb_custom_{i}",
                )

            if action == "Aceptar sugerencia":
                resolutions_state[i] = {
                    "word": amb["word"],
                    "category": amb["category"],
                    "analyst_resolution": amb["suggestion"],
                    "status": "accepted",
                }
            elif action == "Resolución personalizada":
                resolutions_state[i] = {
                    "word": amb["word"],
                    "category": amb["category"],
                    "analyst_resolution": custom_text or amb["suggestion"],
                    "status": "custom",
                }
            # "Descartar" → no se agrega (el LLM tendrá libertad sobre ese término)

    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

    col_btn, col_skip = st.columns([2, 1])
    with col_btn:
        if st.button(
            "Continuar → Generar Test Cases",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("is_running", False),
        ):
            final_resolutions = list(resolutions_state.values())
            on_submit(final_resolutions)

    with col_skip:
        if st.button(
            "Saltar revisión",
            use_container_width=True,
            help="El LLM resolverá las ambigüedades automáticamente (assumption_made=True)",
            disabled=st.session_state.get("is_running", False),
        ):
            on_submit([])
