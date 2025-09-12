import sys
import os

# Add project root to Python path globally
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

import streamlit as st

def load_css():
    with open('styles/style.css') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="TradingView Pro Screener", layout="wide")
load_css()

# Rest of your app code...
