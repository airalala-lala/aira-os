"""Creates the connection to Supabase.

Important security detail: the connection is stored in st.session_state, which
is private to ONE browser session. It is deliberately NOT stored with
st.cache_resource, because a cached connection would be shared by every
visitor to the app and would leak the signed-in user's access.

The connection uses the publishable key only. After sign-in, Supabase attaches
the user's personal access token to every request, so the database's Row Level
Security rules decide what can be read or changed.
"""

from __future__ import annotations

import streamlit as st
from supabase import Client, create_client

from aira.config import load_settings

_CLIENT_KEY = "_aira_supabase_client"


def get_client() -> Client:
    """Return this browser session's own Supabase connection."""
    if _CLIENT_KEY not in st.session_state:
        settings = load_settings()
        st.session_state[_CLIENT_KEY] = create_client(
            settings.supabase_url, settings.supabase_key
        )
    return st.session_state[_CLIENT_KEY]


def forget_client() -> None:
    """Throw away this session's connection (used when signing out)."""
    st.session_state.pop(_CLIENT_KEY, None)
