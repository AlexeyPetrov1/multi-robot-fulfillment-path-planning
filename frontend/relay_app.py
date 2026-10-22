"""Launch with: streamlit run frontend/relay_app.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from frontend.relay_workbench import render_workbench

st.set_page_config(page_title="Диспетчер передачи грузов", layout="wide")
render_workbench()
