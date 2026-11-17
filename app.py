"""AIRA OS - the file Streamlit runs first.

Order of events on every page load:
  1. Check that the settings exist and that the key is a safe one.
  2. If nobody is signed in, show ONLY the sign-in screen and stop.
  3. Otherwise build the menu and show the chosen page.
     Desktop: sidebar. Phone: the same sidebar plus a bottom bar.
"""

import streamlit as st

from aira import APP_NAME, APP_VERSION, auth, config, ui
from aira.modules import MODULES

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="auto",
)
ui.inject_css()

settings = config.get_settings_or_stop()

# ---- The gate: nothing below this line runs unless you are signed in ----
if auth.current_session() is None:
    auth.render_login(settings)
    st.stop()

pages = {
    "": [
        st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    ],
    "Modules": [
        st.Page(m["path"], title=m["title"], icon=m["icon"]) for m in MODULES
    ],
    "Account": [
        st.Page("views/import_data.py", title="Import data", icon=":material/upload:"),
        st.Page("views/settings.py", title="Settings", icon=":material/settings:"),
    ],
}
navigation = st.navigation(pages)

with st.sidebar:
    st.caption(f"Signed in as {auth.current_user_email()}")
    if st.button("Sign out", icon=":material/logout:"):
        auth.sign_out()
        st.rerun()
    st.caption(f"{APP_NAME} v{APP_VERSION}")

navigation.run()
ui.bottom_nav()
