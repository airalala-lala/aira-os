"""Creator Lab (Phase 7): Bio with Teacher Aira.

The content tracker and launch plan live in their own Claude pages, so this
page links to them instead of keeping a second copy that could go out of date.
The links are saved in your private database, not in the code on GitHub.
"""

import streamlit as st

from aira import db, ui, video_library_ui

LINKS = [
    ("tracker_url", "Content Tracker", "Progress of every video: idea, scripted, recorded, edited, published.",
     ":material/table_chart:"),
    ("launch_plan_url", "Launch Plan", "Scripts, content calendar and fact-checks.", ":material/description:"),
]


def main() -> None:
    ui.page_header("Creator Lab", "Bio with Teacher Aira", eyebrow="Phase 7")
    flash = st.session_state.pop("_flash", None)
    if flash:
        st.toast(flash)
    overview, library = st.tabs(["Tracker and plan", "Video Inspiration Library"])
    with overview:
        _links()
    with library:
        video_library_ui.render()


def _links() -> None:
    try:
        saved = {key: db.get_setting("creator", key) for key, *_ in LINKS}
    except db.DataError as exc:
        st.error(str(exc))
        st.stop()

    columns = st.columns(len(LINKS))
    for column, (key, title, text, icon) in zip(columns, LINKS):
        with column:
            with st.container(border=True):
                ui.slot(title, "Ready" if saved.get(key) else "Link not added yet", text)
                if saved.get(key):
                    st.link_button(f"Open {title}", saved[key], icon=icon, type="primary")

    st.caption(
        "These open in Claude, where you can update them or ask Claude about your progress. "
        "Only you can open them unless you share them."
    )

    with st.expander("Add or change the links", icon=":material/link:", expanded=not all(saved.values())):
        with st.form("creator_links"):
            values = {}
            for key, title, *_ in LINKS:
                values[key] = st.text_input(f"{title} link", value=saved.get(key) or "",
                                            placeholder="https://claude.ai/artifact/…", key=f"cl_{key}")
            if st.form_submit_button("Save links", type="primary"):
                bad = [v for v in values.values() if v.strip() and not v.strip().startswith("https://")]
                if bad:
                    st.error("Each link should start with https://")
                else:
                    try:
                        for key, value in values.items():
                            db.set_setting("creator", key, value.strip())
                    except db.DataError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["_flash"] = "Links saved."
                        st.rerun()


main()
