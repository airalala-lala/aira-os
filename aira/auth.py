"""Sign-in, sign-out and "who is signed in?" for AIRA OS.

Nothing personal is shown until Supabase Auth confirms the email and password.
There is no sign-up form anywhere in this app: the single account is created
by hand in the Supabase dashboard (see README.md).
"""

from __future__ import annotations

import time

import streamlit as st

from aira import APP_NAME
from aira.config import Settings
from aira.supabase_client import forget_client, get_client

_FAILS_KEY = "_aira_failed_logins"
_LOCK_KEY = "_aira_locked_until"
_MAX_FAILS = 5
_LOCK_SECONDS = 60


def current_session():
    """Return the signed-in Supabase session, or None.

    Asking Supabase for the session on every page run also renews the access
    token automatically when it is about to expire.
    """
    try:
        return get_client().auth.get_session()
    except Exception:
        return None


def current_user():
    session = current_session()
    return session.user if session else None


def current_user_id() -> str | None:
    user = current_user()
    return str(user.id) if user else None


def current_user_email() -> str:
    user = current_user()
    return (user.email or "") if user else ""


def sign_out() -> None:
    """End the session on Supabase and forget everything in this browser tab."""
    try:
        get_client().auth.sign_out()
    except Exception:
        pass  # even if the network call fails, we still forget the session locally
    forget_client()
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _try_sign_in(email: str, password: str, settings: Settings) -> str | None:
    """Attempt to sign in. Returns None on success or a message to display."""
    generic = "That email or password is not correct."
    email = email.strip().lower()
    if not email or not password:
        return "Please enter both your email and your password."

    # Only the owner's email may sign in. Other emails get the same generic
    # message, so the app never reveals which address is the right one.
    if email != settings.allowed_email:
        return generic

    try:
        result = get_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        text = str(exc).lower()
        if "invalid login" in text or "invalid_credentials" in text:
            return generic
        if "not confirmed" in text:
            return (
                "This account's email is not confirmed yet. In Supabase, open "
                "Authentication, then Users, and confirm the user."
            )
        if "rate limit" in text or "too many" in text:
            return "Too many attempts. Please wait a few minutes and try again."
        return (
            "Could not reach Supabase to sign you in. Check your internet "
            "connection, and that your Supabase project is not paused. "
            f"(Technical detail: {type(exc).__name__})"
        )

    session = getattr(result, "session", None)
    user = getattr(result, "user", None)
    if session is None or user is None:
        return generic

    # Second check after sign-in, in case another account exists in the project.
    if (user.email or "").lower() != settings.allowed_email:
        sign_out()
        return generic
    return None


def render_login(settings: Settings) -> None:
    """Draw the sign-in screen."""
    with st.container(key="login_card"):
        st.markdown(
            f'<div class="aira-brand">{APP_NAME}</div>'
            '<div class="aira-brand-sub">Private dashboard. Sign in to continue.</div>',
            unsafe_allow_html=True,
        )

        locked_until = st.session_state.get(_LOCK_KEY, 0)
        if time.time() < locked_until:
            wait = int(locked_until - time.time()) + 1
            st.warning(f"Too many failed attempts. Try again in {wait} seconds.")
            return

        with st.form("login_form"):
            email = st.text_input("Email", autocomplete="username")
            password = st.text_input(
                "Password", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button("Sign in", type="primary")

        if submitted:
            problem = _try_sign_in(email, password, settings)
            if problem is None:
                st.session_state.pop(_FAILS_KEY, None)
                st.session_state.pop(_LOCK_KEY, None)
                st.rerun()
            fails = st.session_state.get(_FAILS_KEY, 0) + 1
            st.session_state[_FAILS_KEY] = fails
            if fails >= _MAX_FAILS:
                st.session_state[_LOCK_KEY] = time.time() + _LOCK_SECONDS
                st.session_state[_FAILS_KEY] = 0
            st.error(problem)

        st.caption(
            "Forgot your password? Reset it in the Supabase dashboard: "
            "Authentication, then Users."
        )
