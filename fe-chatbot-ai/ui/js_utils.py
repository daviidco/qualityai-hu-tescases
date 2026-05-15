"""Puentes JavaScript via components.html (corren en iframe → acceden al DOM padre)."""

import json

import streamlit.components.v1 as components


_SIDEBAR_JS = """
<script>
(function() {
    var pd = window.parent.document;

    function doToggle() {
        var btn = pd.querySelector('[data-testid="collapsedControl"] button')
                || pd.querySelector('[data-testid="stSidebarCollapseButton"] button');
        if (btn) btn.click();
    }

    // Detectar estado: collapsedControl existe solo cuando el sidebar está colapsado
    var collapsed = !!pd.querySelector('[data-testid="collapsedControl"]');

    var b = pd.getElementById('qa-sidebar-btn');
    if (!b) {
        b = pd.createElement('button');
        b.id = 'qa-sidebar-btn';
        b.title = 'Mostrar/ocultar menú';
        b.style.cssText =
            'position:fixed!important;top:10px!important;left:10px!important;'
            + 'z-index:999999999!important;background:#161b22!important;'
            + 'border:1px solid #21262d!important;border-radius:6px!important;'
            + 'color:#8b949e!important;font-size:1.1rem!important;'
            + 'padding:5px 10px!important;cursor:pointer!important;'
            + 'box-shadow:0 2px 8px rgba(0,0,0,0.4)!important;line-height:1!important;';
        b.addEventListener('mouseover', function() {
            b.style.background='#1e2d3d'; b.style.color='#00bcd4'; b.style.borderColor='#0e4f6b';
        });
        b.addEventListener('mouseout', function() {
            b.style.background='#161b22'; b.style.color='#8b949e'; b.style.borderColor='#21262d';
        });
        b.onclick = doToggle;
        pd.body.appendChild(b);
    }

    // Actualizar ícono en cada rerun (esta función se llama en cada render de Streamlit)
    b.textContent = collapsed ? '☰' : '✕';
})();
</script>
"""


def inject_sidebar_toggle() -> None:
    components.html(_SIDEBAR_JS, height=0, scrolling=False)



# ── Navegación de historial con ↑ / ↓ ────────────────────────────────────────

def inject_history_nav(history: list[str]) -> None:
    history_json = json.dumps(history)
    components.html(f"""
<script>
(function() {{
    var p    = window.parent;
    var pdoc = p.document;

    // Actualizar historial en cada render (la función de captura siempre lee esto)
    p.__qaHist = {history_json};
    var newLen = p.__qaHist.length;
    if (newLen > (p.__qaLastLen || 0)) {{ p.__qaIdx = -1; }}
    p.__qaLastLen = newLen;

    // Registrar listener de documento UNA SOLA VEZ en el padre.
    // La fase de captura (true) intercepta el evento antes de que llegue al textarea,
    // independientemente de si React recreó el elemento entre reruns.
    if (p.__qaDocListener) return;
    p.__qaDocListener = true;

    function setVal(el, val) {{
        // Usar el setter nativo del prototipo para eludir el estado interno de React
        var setter = Object.getOwnPropertyDescriptor(
            p.HTMLTextAreaElement.prototype, 'value'
        ).set;
        setter.call(el, val);
        // InputEvent con bubbles activa el onChange de React
        el.dispatchEvent(new p.InputEvent('input', {{ bubbles: true, cancelable: true }}));
        setTimeout(function() {{ el.selectionStart = el.selectionEnd = el.value.length; }}, 0);
    }}

    pdoc.addEventListener('keydown', function(e) {{
        // Solo actuar cuando el foco está en el chat input
        var el = pdoc.activeElement;
        if (!el || el.getAttribute('data-testid') !== 'stChatInputTextArea') return;

        var hist = p.__qaHist || [];
        var idx  = typeof p.__qaIdx === 'number' ? p.__qaIdx : -1;

        if (e.key === 'ArrowUp') {{
            // Iniciar navegación solo desde input vacío; continuar si ya navega
            if (idx < 0 && el.value !== '') return;
            if (!hist.length) return;
            e.preventDefault();
            p.__qaIdx = Math.min(idx + 1, hist.length - 1);
            setVal(el, hist[p.__qaIdx]);
        }} else if (e.key === 'ArrowDown') {{
            if (idx < 0) return;
            e.preventDefault();
            p.__qaIdx = idx - 1;
            setVal(el, p.__qaIdx < 0 ? '' : hist[p.__qaIdx]);
        }}
    }}, true); // captura = true → se ejecuta antes que los listeners del textarea
}})();
</script>
""", height=0, scrolling=False)


# ── Modal de Rate Limit ───────────────────────────────────────────────────────

def inject_rate_limit_modal(retry_in: str) -> None:
    components.html(f"""
<script>
(function() {{
    var pdoc = window.parent.document;
    if (pdoc.getElementById('qa-rate-overlay')) return;

    var overlay = pdoc.createElement('div');
    overlay.id = 'qa-rate-overlay';
    overlay.style.cssText =
        'position:fixed!important;top:0!important;left:0!important;'
        + 'right:0!important;bottom:0!important;background:rgba(0,0,0,0.7)!important;'
        + 'z-index:999999998!important;display:flex!important;'
        + 'align-items:center!important;justify-content:center!important;'
        + 'backdrop-filter:blur(4px)!important;';

    var modal = pdoc.createElement('div');
    modal.style.cssText =
        'background:#1a1f2e!important;border:1px solid #f97316!important;'
        + 'border-radius:12px!important;padding:2rem 2.5rem!important;'
        + 'max-width:480px!important;width:90%!important;'
        + 'box-shadow:0 8px 32px rgba(249,115,22,0.2)!important;text-align:center!important;';
    modal.innerHTML =
        '<div style="font-size:3rem;margin-bottom:0.5rem;">&#9201;</div>'
        + '<div style="font-size:1.2rem;font-weight:700;color:#f97316;margin-bottom:0.5rem;">'
        +   'L&iacute;mite de tokens alcanzado</div>'
        + '<div style="font-size:0.9rem;color:#c9d1d9;line-height:1.6;margin-bottom:1.25rem;">'
        +   'La API de Groq alcanz&oacute; su l&iacute;mite diario de tokens.<br>'
        +   'Por favor, intenta de nuevo en:</div>'
        + '<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:1.25rem;">'
        +   '{retry_in}</div>'
        + '<button style="background:#0e4f6b;border:1px solid #00bcd4;color:#00bcd4;'
        +   'padding:0.5rem 2rem;border-radius:8px;font-size:0.9rem;font-weight:600;cursor:pointer;">'
        +   'Entendido</button>';

    modal.querySelector('button').onclick = function() {{ overlay.remove(); }};
    overlay.appendChild(modal);
    pdoc.body.appendChild(overlay);
}})();
</script>
""", height=0, scrolling=False)
