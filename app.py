"""FPRFC dashboard — entry point and navigation.

Run with:  streamlit run app.py

Each page lives in `views/`; the shared palette, helpers and CSS are in `common.py`.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from common import STYLE

BASE = Path(__file__).parent
LOGO_PATH = BASE / "assets" / "logo.png"

st.set_page_config(page_title="FPRFC Dashboard", page_icon=str(LOGO_PATH), layout="wide")
st.markdown(STYLE, unsafe_allow_html=True)

pages = st.navigation(
    [
        st.Page("views/membership.py", title="Membership", icon=":material/groups:"),
        st.Page("views/merchandise.py", title="Merchandise", icon=":material/shopping_bag:"),
    ]
)

pages.run()
