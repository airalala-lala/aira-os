"""Optional: ask Claude (Anthropic API) to draft a video concept or analysis.

This only works when you add ANTHROPIC_API_KEY to the app's Secrets. The key
stays on the server: it is never sent to your browser or written to GitHub.
Without a key, the app shows the brief for you to copy into a Claude chat.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from aira.config import optional_setting

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"


class ClaudeError(Exception):
    """A problem reaching Claude, in plain language."""


def is_configured() -> bool:
    return bool(optional_setting("ANTHROPIC_API_KEY"))


def ask(prompt: str, max_tokens: int = 4000, timeout: float = 120.0, opener=urllib.request.urlopen) -> str:
    key = optional_setting("ANTHROPIC_API_KEY")
    if not key:
        raise ClaudeError("No Anthropic API key is set in the app's Secrets.")
    body = json.dumps({
        "model": optional_setting("ANTHROPIC_MODEL") or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    request = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json",
    })
    try:
        with opener(request, timeout=timeout) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode()).get("error", {}).get("message", "")
        except Exception:
            pass
        if exc.code == 401:
            raise ClaudeError("The Anthropic API key was not accepted. Check it in the app's Secrets.") from exc
        if exc.code == 429:
            raise ClaudeError("Too many requests or no credit left. Wait a minute, or check your Anthropic billing.") from exc
        raise ClaudeError(f"Claude could not answer (error {exc.code}). {detail}".strip()) from exc
    except Exception as exc:
        raise ClaudeError(f"Could not reach Claude ({type(exc).__name__}). Try again in a moment.") from exc
    parts = [block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"]
    text = "\n".join(p for p in parts if p).strip()
    if not text:
        raise ClaudeError("Claude returned an empty answer. Try again.")
    return text
