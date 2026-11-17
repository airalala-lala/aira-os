"""Loads and checks the app's settings (Supabase URL, key and allowed email).

Settings come from one of two places:
  * Streamlit Community Cloud: the app's "Secrets" box.
  * Your own MacBook: a file named .env in the project folder.

This file also refuses to start the app if a powerful "secret" or
"service_role" key was pasted by mistake. AIRA OS must only ever use the
low-privilege publishable key, so that Row Level Security always applies.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

import streamlit as st

try:  # python-dotenv is only needed when running on your own computer
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - fine on Streamlit Cloud
    pass


class ConfigError(Exception):
    """Raised when a setting is missing or unsafe."""


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    allowed_email: str  # lower-case; empty string means "not set"


def _read(name: str) -> str:
    """Read one setting from Streamlit secrets first, then from the environment."""
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        # No secrets file exists (normal when running locally with .env).
        pass
    return os.environ.get(name, "").strip()


def _jwt_role(key: str) -> str:
    """Return the 'role' inside a legacy JWT-style key, or '' if not readable."""
    parts = key.split(".")
    if len(parts) != 3:
        return ""
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return str(data.get("role", ""))
    except Exception:
        return ""


def check_key_is_safe(key: str) -> None:
    """Stop if the key is one that bypasses Row Level Security."""
    if key.startswith("sb_secret_") or _jwt_role(key) == "service_role":
        raise ConfigError(
            "The key you provided is a SECRET / service_role key. That key "
            "bypasses Row Level Security and must never be used in this app. "
            "Replace it with the PUBLISHABLE key (it starts with "
            "sb_publishable_), then delete and re-create the secret key in "
            "Supabase because it may have been exposed."
        )


def load_settings() -> Settings:
    url = _read("SUPABASE_URL").rstrip("/")
    # SUPABASE_ANON_KEY is accepted as a fallback name for older projects.
    key = _read("SUPABASE_PUBLISHABLE_KEY") or _read("SUPABASE_ANON_KEY")
    allowed_email = _read("ALLOWED_EMAIL").lower()

    missing = []
    if not url or "YOUR-PROJECT-REF" in url:
        missing.append("SUPABASE_URL")
    if not key or "REPLACE_ME" in key:
        missing.append("SUPABASE_PUBLISHABLE_KEY")
    if not allowed_email or allowed_email == "you@example.com":
        missing.append("ALLOWED_EMAIL")
    if missing:
        raise ConfigError("Missing settings: " + ", ".join(missing))

    if not url.startswith("https://"):
        raise ConfigError("SUPABASE_URL must start with https://")

    check_key_is_safe(key)
    return Settings(supabase_url=url, supabase_key=key, allowed_email=allowed_email)


def get_settings_or_stop() -> Settings:
    """Return the settings, or show a readable setup message and stop the page."""
    try:
        return load_settings()
    except ConfigError as exc:
        st.error(f"AIRA OS is not configured yet. {exc}")
        st.markdown(
            "**How to fix this**\n\n"
            "- **On Streamlit Community Cloud:** open your app, choose "
            "**Settings**, then **Secrets**, and paste the three lines from "
            "`.streamlit/secrets.toml.example` with your own values.\n"
            "- **On your MacBook:** copy `.env.example` to a new file named "
            "`.env` and fill in the three values.\n\n"
            "The step-by-step guide is in `README.md`."
        )
        st.stop()
        raise  # never reached; keeps type checkers happy
