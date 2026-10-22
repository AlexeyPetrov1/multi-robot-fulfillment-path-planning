"""The mission bench is also available from the warehouse dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from frontend.relay_workbench import render_workbench

st.set_page_config(page_title="Передача грузов", layout="wide")
render_workbench()
