"""Inyección de CSS global."""

import streamlit as st

_CSS = """
<style>
  /* ── Tamaño base global ── */
  html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
  html, body, [class*="css"] { font-size: 17px !important; }
  body { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
  p, div, span, li, label { font-size: 1rem; }

  #MainMenu, footer { visibility: hidden; }
  /* Header: transparente y sin interceptar clics (para que el sidebar sea clickeable) */
  header[data-testid="stHeader"] {
    background: transparent !important;
    box-shadow: none !important;
    pointer-events: none !important;
  }
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  [data-testid="stAppDeployButton"],
  button[kind="header"],
  .stDeployButton { display: none !important; }
  /* ── Custom sidebar host ── */
  /* Streamlit native sidebar: off-screen para ocultar visualmente pero clickeable via JS */
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"] { display: none !important; }
  section[data-testid="stSidebar"] {
    position: fixed !important;
    left: -9999px !important;
    opacity: 0 !important;
    z-index: -1 !important;
  }
  /* Indent main content to clear our fixed custom sidebar (256 px expanded / 64 px mini) */
  .block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    padding-left: 280px !important;
    transition: padding-left 0.25s ease;
  }
  body.qa-mini .block-container { padding-left: 88px !important; }
  /* Login page: no sidebar injected, no indent needed */
  body:not(.qa-has-sb) .block-container { padding-left: 1.5rem !important; }

  /* ── Chat ── */
  [data-testid="stChatMessage"] {
    background: #161b22; border: 1px solid #21262d;
    border-radius: 10px; padding: 0.25rem 0.25rem;
  }
  [data-testid="stChatInput"] textarea {
    background: #161b22 !important; border: 1px solid #21262d !important;
    color: #e2e8f0 !important; border-radius: 8px;
  }

  /* ── Tarjetas de resultado ── */
  .result-card {
    background: #1a1f2e; border: 1px solid #21262d;
    border-radius: 8px; padding: 1rem 1.2rem; margin-top: 0.5rem;
  }
  .story-header {
    color: #00bcd4; font-size: 0.95rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.25rem;
  }
  .story-title { font-size: 1.2rem; font-weight: 600; color: #e2e8f0; margin-bottom: 0.6rem; }
  .story-narrative { color: #8b949e; font-size: 1.05rem; margin-bottom: 0.8rem; font-style: italic; }
  .ac-item { display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.4rem; font-size: 1.05rem; color: #c9d1d9; }
  .ac-check { color: #00bcd4; flex-shrink: 0; }
  .ac-neg   { color: #f97316; flex-shrink: 0; }
  .amb-tag {
    display: inline-block; background: #1e3a4a; border: 1px solid #0e4f6b;
    color: #00bcd4; font-size: 0.95rem; padding: 0.1rem 0.5rem;
    border-radius: 4px; margin-right: 0.35rem; margin-top: 0.25rem;
  }
  .metric-row { display: flex; gap: 1.5rem; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #21262d; }
  .metric-item  { font-size: 0.95rem; }
  .metric-label { color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
  .metric-value { color: #00bcd4; font-weight: 600; font-size: 1.1rem; }

  /* ── Tarjetas HITL ── */
  .hitl-card {
    background: #1a1f2e; border: 1px solid #0e4f6b;
    border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.75rem;
  }
  .hitl-word { font-size: 1.25rem; font-weight: 700; color: #00bcd4; }
  .hitl-meta { font-size: 1rem; color: #8b949e; margin-bottom: 0.4rem; }
  .hitl-suggestion {
    font-size: 1.05rem; color: #c9d1d9; background: #161b22;
    border-left: 3px solid #0e4f6b; padding: 0.35rem 0.75rem;
    border-radius: 0 4px 4px 0; margin-top: 0.4rem;
  }

  /* ── Misc ── */
  .status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #22c55e; display: inline-block; margin-right: 5px;
  }
</style>
"""


def inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
