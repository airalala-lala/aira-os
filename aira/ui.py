"""Shared look and feel: colours, page headers, cards, meters and empty states.

Colours are defined once as CSS variables, with a light set and a dark set.
The app follows the device's light or dark setting.
"""

from __future__ import annotations

import html

import streamlit as st

from aira.modules import BOTTOM_NAV, get_module

_CSS = """
<style>
:root {
    --aira-bg: #FBF8F1;      /* warm ivory */
    --aira-bg2: #F3EEE3;
    --aira-card: #FFFDF8;
    --aira-line: #E6DFD0;
    --aira-text: #2C2A26;
    --aira-muted: #6F6A60;
    --aira-sage: #7C9A82;
    --aira-sage-deep: #55735C;
    --aira-teal: #4F8A8B;
    --aira-rose: #B9848A;
    --aira-gold: #A98545;
    --aira-track: #ECE5D6;
    --aira-button: #55735C;
}
@media (prefers-color-scheme: dark) {
    :root {
        --aira-bg: #1D1F1C;
        --aira-bg2: #252824;
        --aira-card: #2A2D29;
        --aira-line: #3A3E38;
        --aira-text: #ECE8DF;
        --aira-muted: #A8A397;
        --aira-sage: #9DB8A2;
        --aira-sage-deep: #9DB8A2;
        --aira-teal: #7FB3B3;
        --aira-rose: #D9B0B3;
        --aira-gold: #D1B279;
        --aira-track: #383C36;
        --aira-button: #6E8F76;
    }
}

/* Page background and width */
.stApp { background: var(--aira-bg); }
[data-testid="stSidebar"] { background: var(--aira-bg2); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 1080px;
    padding-top: 3.5rem;
    padding-bottom: 4rem;
}

/* Main buttons in sage green (overrides the theme colour, which some
   Streamlit versions ignore in dark mode) */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {
    background-color: var(--aira-button) !important;
    border-color: var(--aira-button) !important;
    color: #FFFFFF !important;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover { filter: brightness(1.08); }

/* Tabs and choices in sage as well */
button[data-baseweb="tab"][aria-selected="true"] p { color: var(--aira-button) !important; }
[data-baseweb="tab-highlight"] { background-color: var(--aira-button) !important; }

/* Headings */
.aira-eyebrow {
    font-size: 0.74rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--aira-gold); font-weight: 600; margin-bottom: 0.2rem;
}
.aira-title {
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 2rem; font-weight: 600; line-height: 1.2;
    color: var(--aira-text); margin: 0;
}
.aira-subtitle { color: var(--aira-muted); margin-top: 0.3rem; font-size: 0.98rem; }
.aira-section {
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 1.25rem; font-weight: 600; color: var(--aira-text);
    margin: 1.9rem 0 0.15rem 0;
}
.aira-section-note { color: var(--aira-muted); font-size: 0.88rem; margin-bottom: 0.6rem; }

/* Sign-in card */
.st-key-login_card { max-width: 420px; margin: 7vh auto 0 auto; }
.st-key-login_card [data-testid="stFormSubmitButton"] button { width: 100%; }
.aira-brand {
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 2.2rem; font-weight: 600; color: var(--aira-sage-deep); text-align: center;
}
.aira-brand-sub { text-align: center; color: var(--aira-muted); margin-bottom: 1.2rem; }

/* Cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px; background: var(--aira-card); border-color: var(--aira-line);
}
.aira-card-title { font-weight: 650; font-size: 1rem; color: var(--aira-text); }
.aira-card-text {
    color: var(--aira-muted); font-size: 0.9rem; line-height: 1.45; margin: 0.25rem 0 0.6rem 0;
}
.aira-slot-label {
    font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--aira-muted); font-weight: 600;
}
.aira-slot-value { font-size: 1.02rem; font-weight: 600; color: var(--aira-text); margin: 0.2rem 0; }
.aira-slot-note { font-size: 0.86rem; color: var(--aira-muted); }

/* Badges */
.aira-badge {
    display: inline-block; font-size: 0.7rem; font-weight: 600;
    padding: 0.12rem 0.55rem; border-radius: 999px; margin-right: 0.3rem;
    color: var(--aira-muted); border: 1px solid var(--aira-line); background: transparent;
}
.aira-badge.sage { color: var(--aira-sage-deep); border-color: var(--aira-sage); }
.aira-badge.teal { color: var(--aira-teal); border-color: var(--aira-teal); }
.aira-badge.rose { color: var(--aira-rose); border-color: var(--aira-rose); }
.aira-badge.gold { color: var(--aira-gold); border-color: var(--aira-gold); }

/* Empty states */
.aira-empty {
    border: 1px dashed var(--aira-line); border-radius: 16px; background: transparent;
    padding: 1.3rem 1.2rem; text-align: center; color: var(--aira-muted); font-size: 0.92rem;
}
.aira-empty strong { color: var(--aira-text); display: block; margin-bottom: 0.2rem; }

/* Meters (actual versus planned) */
.aira-meter { margin: 0.25rem 0 1rem 0; }
.aira-meter-head { display: flex; justify-content: space-between; gap: 1rem; align-items: baseline; }
.aira-meter-label { font-weight: 600; color: var(--aira-text); font-size: 0.95rem; }
.aira-meter-value { color: var(--aira-muted); font-size: 0.88rem; text-align: right; }
.aira-meter-track {
    height: 8px; border-radius: 999px; background: var(--aira-track); margin-top: 0.4rem; overflow: hidden;
}
.aira-meter-fill { height: 100%; border-radius: 999px; background: var(--aira-sage); }
.aira-meter-fill.teal { background: var(--aira-teal); }
.aira-meter-fill.rose { background: var(--aira-rose); }
.aira-meter-fill.gold { background: var(--aira-gold); }

/* Week strip: which days have any record */
.aira-days { display: flex; gap: 0.4rem; margin: 0.2rem 0 0.4rem 0; }
.aira-day {
    flex: 1; text-align: center; font-size: 0.72rem; color: var(--aira-muted);
    border: 1px solid var(--aira-line); border-radius: 10px; padding: 0.35rem 0;
}
.aira-day.logged { background: var(--aira-sage); border-color: var(--aira-sage); color: #FFFFFF; }
.aira-day.future { opacity: 0.45; border-style: dashed; }

/* Timer banner */
.aira-timer {
    border-left: 4px solid var(--aira-gold); background: var(--aira-card);
    border-radius: 12px; padding: 0.8rem 1rem; color: var(--aira-text);
}
.aira-timer b { font-size: 1.05rem; }

/* Bottom navigation: phones only */
.st-key-bottomnav { display: none; }
@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"], .block-container {
        padding-left: 1rem; padding-right: 1rem; padding-top: 3.2rem; padding-bottom: 6.5rem;
    }
    .aira-title { font-size: 1.6rem; }
    .st-key-login_card { margin-top: 3vh; }
    .st-key-bottomnav {
        display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
        justify-content: space-around; align-items: center; gap: 0 !important;
        position: fixed; left: 0; right: 0; bottom: 0; z-index: 999;
        width: 100% !important; max-width: 100% !important;
        background: var(--aira-card); border-top: 1px solid var(--aira-line);
        /* Right side kept clear for the Streamlit Cloud buttons in the corner */
        padding: 0.35rem 7.5rem calc(0.35rem + env(safe-area-inset-bottom)) 0.25rem !important;
    }
    .st-key-bottomnav > div { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
    .st-key-bottomnav a {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 0.1rem; padding: 0.2rem 0; font-size: 0.68rem;
    }
    .st-key-bottomnav a p { font-size: 0.68rem; margin: 0; }
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    parts = []
    if eyebrow:
        parts.append(f'<div class="aira-eyebrow">{html.escape(eyebrow)}</div>')
    parts.append(f'<h1 class="aira-title">{html.escape(title)}</h1>')
    if subtitle:
        parts.append(f'<div class="aira-subtitle">{html.escape(subtitle)}</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def section(title: str, note: str = "") -> None:
    text = f'<div class="aira-section">{html.escape(title)}</div>'
    if note:
        text += f'<div class="aira-section-note">{html.escape(note)}</div>'
    st.markdown(text, unsafe_allow_html=True)


def empty_state(title: str, text: str) -> None:
    """A clearly labelled 'nothing here yet' box. Never shows invented data."""
    st.markdown(
        f'<div class="aira-empty"><strong>{html.escape(title)}</strong>'
        f"{html.escape(text)}</div>",
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "") -> str:
    """HTML for a small pill label. kind: '', 'sage', 'teal', 'rose' or 'gold'."""
    css = f"aira-badge {kind}".strip()
    return f'<span class="{css}">{html.escape(text)}</span>'


def slot(label: str, value: str, note: str = "") -> None:
    """A small labelled block used inside the 'My focus today' cards."""
    text = (
        f'<div class="aira-slot-label">{html.escape(label)}</div>'
        f'<div class="aira-slot-value">{html.escape(value)}</div>'
    )
    if note:
        text += f'<div class="aira-slot-note">{html.escape(note)}</div>'
    st.markdown(text, unsafe_allow_html=True)


def meter(label: str, value_text: str, fraction: float | None = None, colour: str = "") -> None:
    """One 'actual versus planned' row. With fraction=None no bar is drawn."""
    bar = ""
    if fraction is not None:
        width = max(0.0, min(1.0, fraction)) * 100
        bar = (
            '<div class="aira-meter-track">'
            f'<div class="aira-meter-fill {colour}" style="width:{width:.0f}%"></div></div>'
        )
    st.markdown(
        '<div class="aira-meter"><div class="aira-meter-head">'
        f'<span class="aira-meter-label">{html.escape(label)}</span>'
        f'<span class="aira-meter-value">{html.escape(value_text)}</span></div>{bar}</div>',
        unsafe_allow_html=True,
    )


def week_strip(days: list[dict]) -> None:
    """Seven small boxes: filled = something recorded, outlined = no entries."""
    cells = "".join(
        f'<div class="aira-day {day["state"]}">{day["date"]:%a}<br>{day["date"].day}</div>'
        for day in days
    )
    st.markdown(f'<div class="aira-days">{cells}</div>', unsafe_allow_html=True)


def module_card(module: dict) -> None:
    """One card for one of the six modules."""
    with st.container(border=True):
        status = (
            badge("Ready", "sage")
            if module["built"]
            else badge(f"Not built yet · {module['phase']}")
        )
        st.markdown(
            f'<div class="aira-card-title">{html.escape(module["title"])}</div>'
            f'<div class="aira-card-text">{html.escape(module["summary"])}</div>'
            f"{status}",
            unsafe_allow_html=True,
        )
        st.page_link(module["path"], label="Open", icon=module["icon"])


def module_placeholder(key: str) -> None:
    """The honest 'this module is not built yet' page."""
    module = get_module(key)
    page_header(module["title"], module["summary"], eyebrow=module["phase"])
    st.write("")
    empty_state(
        "This module is not built yet",
        f"It is planned for {module['phase']}. No numbers are shown here "
        "until they come from your own records.",
    )
    section("Planned for this module")
    st.markdown("\n".join(f"- {item}" for item in module["planned"]))


def bottom_nav() -> None:
    """A fixed bar of five links at the bottom of the screen on phones."""
    with st.container(key="bottomnav", horizontal=True):
        for item in BOTTOM_NAV:
            st.page_link(item["path"], label=item["label"], icon=item["icon"])
