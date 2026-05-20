"""Login page — URL: /login"""
import streamlit as st

st.set_page_config(
    page_title="QualityAI — Login",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Handle logout: clear session and stay on login page
if st.query_params.get("logout") == "1":
    st.session_state.clear()
    st.query_params.clear()

# Already authenticated → go to dashboard
if st.session_state.get("token"):
    st.switch_page("app.py")
    st.stop()

from state import init_state                # noqa: E402
from ui.sidebar import clear_sidebar        # noqa: E402
from ui.styles import inject_styles         # noqa: E402
from ui.login import render_login           # noqa: E402

inject_styles()
init_state()
clear_sidebar()
render_login()
