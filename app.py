import sys
import os
from pathlib import Path
import streamlit as st  # top-level import so Pylance resolves when venv is active

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Basic page config
st.set_page_config(page_title="Market Predictor Pro", layout="wide")

# Load custom CSS if present
def load_css():
    css_path = PROJECT_ROOT / "styles" / "style.css"
    if css_path.exists():
        with css_path.open("r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.sidebar.info("Optional: styles/style.css not found; using default theme.")

load_css()

# App header (always visible so Home is never blank)
st.title("🚀 Market Predictor Pro")

st.markdown(
    """
    Use the sidebar to open pages like Screener, Sector, Single Stock, and Watchlist.
    This Home page renders by default so the app is never blank.
    """,
    help="Pages are in the 'pages/' folder and appear in Streamlit's sidebar automatically."
)

# Optional quick links to pages folder files (helps navigation in dev)
pages_dir = PROJECT_ROOT / "pages"
if pages_dir.exists():
    page_files = sorted(p for p in pages_dir.glob("*.py"))
    if page_files:
        with st.expander("Available pages", expanded=False):
            for p in page_files:
                st.write(f"- {p.name}")
else:
    st.warning("No 'pages/' directory found. Create one for additional pages.")
