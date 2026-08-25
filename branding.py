"""RCM Co-op branding shared across every page."""
from pathlib import Path

import streamlit as st

LOGO_PATH = str(Path(__file__).resolve().parent / "assets" / "rcm_logo.png")


def apply_logo():
    st.logo(LOGO_PATH, size="large", link="https://www.rcmcoop.com")
