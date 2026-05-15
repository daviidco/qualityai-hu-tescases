"""Panel de revisión Human-in-the-Loop para resolución de ambigüedades."""

import streamlit as st


def render_hitl_review() -> None:
    """Muestra las tarjetas de ambigüedad y el botón de envío.

    Usa widgets sueltos (sin st.form) para que el radio dispare un rerun
    inmediato y el campo de texto personalizado aparezca/desaparezca dinámicamente.
    """
    from handlers import run_hitl_refine  # import local para evitar ciclo

    ambs = st.session_state.hitl_ambiguities
    if not ambs:
        return

    st.markdown(
        '<div style="background:#0e1e2e;border:1px solid #0e4f6b;border-radius:8px;'
        'padding:1rem 1.2rem;margin-bottom:1rem;">'
        '<div style="color:#00bcd4;font-weight:700;margin-bottom:0.25rem;">'
        "🧑‍💻 Revisión del Analista Requerida</div>"
        '<div style="color:#8b949e;font-size:0.85rem;">'
        "El detector encontró términos ambiguos. Resuelve cada uno antes de generar las historias."
        "</div></div>",
        unsafe_allow_html=True,
    )

    choices: dict[int, str] = {}
    customs: dict[int, str] = {}

    for idx, amb in enumerate(ambs):
        _render_amb_card(amb)

        choice = st.radio(
            f'Decisión para "{amb["word"]}"',
            options=["Aceptar sugerencia", "Resolución personalizada", "No es ambiguo — descartar"],
            key=f"radio_{idx}_{amb['word']}",
            horizontal=True,
            label_visibility="collapsed",
        )
        choices[idx] = choice

        if choice == "Resolución personalizada":
            customs[idx] = st.text_input(
                f'Resolución para "{amb["word"]}"',
                placeholder="Define un valor concreto y medible…",
                key=f"custom_{idx}_{amb['word']}",
            )

        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

    if st.button("Generar Historias →", type="primary", use_container_width=True, key="hitl_submit"):
        resolutions = _build_resolutions(ambs, choices, customs)
        if resolutions is not None:
            run_hitl_refine(resolutions)


def _render_amb_card(amb: dict) -> None:
    sev = amb.get("severity", "baja")
    badge = {"alta": "🔴 ALTA", "media": "🟡 MEDIA", "baja": "🟢 BAJA"}.get(sev, sev)
    st.markdown(
        f'<div class="hitl-card">'
        f'<div class="hitl-word">"{amb["word"]}"'
        f'  <span style="font-size:0.75rem;color:#475569;font-weight:400;">'
        f'{badge} · {amb.get("category", "").replace("_", " ")}</span></div>'
        f'<div class="hitl-meta">Contexto: <em>{amb.get("context", "")}</em></div>'
        f'<div class="hitl-suggestion">💡 {amb.get("suggestion", "")}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _build_resolutions(
    ambs: list[dict],
    choices: dict[int, str],
    customs: dict[int, str],
) -> list[dict] | None:
    """Construye la lista de resoluciones. Devuelve None si hay validación pendiente."""
    built = []
    for idx, amb in enumerate(ambs):
        word     = amb["word"]
        category = amb.get("category", "")
        choice   = choices[idx]

        if choice == "Aceptar sugerencia":
            built.append({
                "word": word, "category": category,
                "status": "resolved", "analyst_resolution": amb["suggestion"],
            })
        elif choice == "Resolución personalizada":
            text = customs.get(idx, "").strip()
            if not text:
                st.warning(f'Por favor escribe una resolución para "{word}" o elige otra opción.')
                return None
            built.append({
                "word": word, "category": category,
                "status": "resolved", "analyst_resolution": text,
            })
        else:
            built.append({
                "word": word, "category": category,
                "status": "dismissed", "analyst_resolution": "",
            })
    return built
