"""PhD Research Hub (Phase 2a): overview, literature, supervision and timeline.

Source evidence (what a paper says, or what an exported summary says) is kept
apart from your own thinking (relevance, gap contribution, critical notes).
Progress is counted from completed milestones, never from invented percentages.
"""

import html
from datetime import date, datetime

import plotly.graph_objects as go
import streamlit as st

from aira import db, literature, ui
from aira.literature import READING_LABELS, READING_STATUSES, SOURCE_TYPE_LABELS, SOURCE_TYPES, SUMMARY_BASIS_LABELS
from aira.timeutil import due_label, format_date, parse_date, today_kl

TODAY = today_kl()


def _act(action, message: str) -> None:
    try:
        action()
    except db.DataError as exc:
        st.error(str(exc))
        return
    st.session_state["_flash"] = message
    st.rerun()


def _load() -> dict:
    try:
        return {
            "sources": db.list_sources(),
            "meetings": db.list_meetings(),
            "feedback": db.list_feedback(),
            "milestones": db.list_milestones(),
            "phases": db.list_research_phases(),
            "tasks": db.list_tasks(),
            "title": db.get_setting("phd", "working_title"),
            "supervisor": db.get_setting("phd", "supervisor"),
            "semesters": db.get_setting("phd", "semesters", []) or [],
        }
    except db.DataError as exc:
        st.error(str(exc))
        st.info(
            "The PhD Hub needs migration 0005. In Supabase, open the SQL Editor, "
            "run supabase/migrations/0005_phd_hub.sql, then reload this page."
        )
        st.stop()


# ------------------------------------------------------------------ overview


def _overview(data: dict) -> None:
    sources = data["sources"]
    open_feedback = [f for f in data["feedback"] if f.get("status") != "addressed"]
    actions = [t for t in data["tasks"] if t.get("meeting_id") and t.get("status") != "done"]
    milestones = data["milestones"]
    done = [m for m in milestones if m.get("status") == "completed"]
    upcoming = sorted(
        (m for m in milestones if m.get("status") != "completed" and m.get("due_date")),
        key=lambda m: m["due_date"],
    )

    if data["title"]:
        st.markdown(f"*{html.escape(str(data['title']))}*")
    if data["supervisor"]:
        st.caption(f"Supervisor: {data['supervisor']}")

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            if sources:
                read = sum(1 for s in sources if s.get("reading_status") == "read")
                ui.slot("Literature", f"{len(sources)} sources",
                        f"{read} marked as read · reading status not recorded for "
                        f"{sum(1 for s in sources if s.get('reading_status') == 'not_recorded')}")
            else:
                ui.slot("Literature", "No sources yet", "Add one, or import your matrix.")
    with col2:
        with st.container(border=True):
            ui.slot("Supervision", f"{len(open_feedback)} open feedback item(s)",
                    f"{len(actions)} open action item(s) from meetings")
    with col3:
        with st.container(border=True):
            if milestones:
                nxt = upcoming[0] if upcoming else None
                note = (f"Next: {nxt['title']} · {due_label(parse_date(nxt['due_date']), TODAY)}"
                        if nxt else "No planned dates set yet")
                ui.slot("Milestones", f"{len(done)} of {len(milestones)} completed", note)
            else:
                ui.slot("Milestones", "None recorded", "Add them in the Timeline tab.")

    if data["phases"]:
        ui.section("Research phases", "Current plans, not completed findings.")
        for phase in data["phases"]:
            status = db.MILESTONE_LABELS.get(phase.get("status"), "Planned")
            with st.expander(f"Phase {phase['position']}: {phase['title']} · {status}"):
                st.write(phase.get("description") or "")

    st.caption(
        "Coming next in the PhD Hub: synthesis board, research-problem evidence "
        "tracker, POL500 tracker and the PhD weekly planner."
    )


# ---------------------------------------------------------------- literature


def _source_fields(prefix: str, source: dict | None = None) -> dict:
    """All editable fields of a source, grouped. Returns the values entered."""
    s = source or {}
    k = lambda name: f"{prefix}_{name}"
    v = {}
    st.markdown("**Details**")
    v["title"] = st.text_area("Title", value=s.get("title") or "", height=70, key=k("title"))
    c1, c2 = st.columns(2)
    with c1:
        v["authors"] = st.text_input("Authors", value=s.get("authors") or "", key=k("authors"))
        v["year"] = st.number_input("Year", min_value=1800, max_value=TODAY.year + 1, step=1,
                                    value=s.get("year"), key=k("year"))
        v["journal"] = st.text_input("Journal or publisher", value=s.get("journal") or "", key=k("journal"))
        types = [None] + SOURCE_TYPES
        v["source_type"] = st.selectbox(
            "Type", types, index=types.index(s.get("source_type")) if s.get("source_type") in types else 0,
            format_func=lambda t: SOURCE_TYPE_LABELS.get(t, "Not set"), key=k("type"),
        )
    with c2:
        v["doi"] = st.text_input("DOI", value=s.get("doi") or "", key=k("doi"))
        v["url"] = st.text_input("URL", value=s.get("url") or "", key=k("url"))
        v["research_country"] = st.text_input("Research country", value=s.get("research_country") or "", key=k("country"))
        v["publication_date"] = st.text_input("Publication date (as written)", value=s.get("publication_date") or "", key=k("pubdate"))
    v["citation"] = st.text_area("Citation / reference", value=s.get("citation") or "", height=70, key=k("citation"))

    st.markdown("**What the source says**")
    v["methodology"] = st.text_area("Methodology", value=s.get("methodology") or "", key=k("method"))
    v["theoretical_framework"] = st.text_input("Theoretical framework", value=s.get("theoretical_framework") or "", key=k("framework"))
    v["key_findings"] = st.text_area("Key findings", value=s.get("key_findings") or "", key=k("findings"))
    v["conclusions"] = st.text_area("Conclusions", value=s.get("conclusions") or "", key=k("conclusions"))
    v["limitations"] = st.text_area("Limitations", value=s.get("limitations") or "", key=k("limitations"))
    v["abstract"] = st.text_area("Abstract", value=s.get("abstract") or "", key=k("abstract"))

    st.markdown("**My thinking**")
    v["relevance"] = st.text_area("Relevance to my PhD", value=s.get("relevance") or "", key=k("relevance"))
    v["gap_contribution"] = st.text_area("Research gap contribution", value=s.get("gap_contribution") or "", key=k("gap"))
    v["critical_notes"] = st.text_area("My critical notes", value=s.get("critical_notes") or "", key=k("notes"))
    v["tags"] = st.text_input("Tags (separate with commas)", value=s.get("tags") or "", key=k("tags"))

    st.markdown("**Reading**")
    c1, c2 = st.columns(2)
    with c1:
        v["reading_status"] = st.selectbox(
            "Reading status", READING_STATUSES, format_func=READING_LABELS.get,
            index=READING_STATUSES.index(s["reading_status"]) if s.get("reading_status") in READING_STATUSES else 0,
            key=k("status"),
        )
    with c2:
        v["date_read"] = st.date_input("Date read", value=parse_date(s.get("date_read")),
                                       max_value=TODAY, format="DD/MM/YYYY", key=k("dateread"))
    return v


def _tags(source: dict) -> list[str]:
    return [t.strip() for t in (source.get("tags") or "").split(",") if t.strip()]


def _matches(source: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(str(source.get(f) or "") for f in (
        "title", "authors", "journal", "abstract", "methodology", "key_findings",
        "conclusions", "critical_notes", "relevance", "gap_contribution", "tags", "research_country",
    )).lower()
    return all(word in haystack for word in query.lower().split())


def _close_source() -> None:
    """Close the open source and clear the table's row selection."""
    st.session_state.pop("_lit_open", None)
    st.session_state["_lit_nonce"] = st.session_state.get("_lit_nonce", 0) + 1


def _source_detail(source: dict, sources: list[dict]) -> None:
    sid = source["id"]
    with st.container(border=True):
        badges = [ui.badge(READING_LABELS.get(source.get("reading_status"), "Not recorded"), "teal")]
        if source.get("year"):
            badges.append(ui.badge(str(source["year"])))
        if source.get("summary_basis"):
            badges.append(ui.badge(f"Summary from {SUMMARY_BASIS_LABELS[source['summary_basis']].lower()}", "gold"))
        badges += [ui.badge(t, "sage") for t in _tags(source)]
        st.markdown(
            f'<div class="aira-card-title">{html.escape(source["title"])}</div>'
            f'<div style="margin-top:0.35rem">{"".join(badges)}</div>',
            unsafe_allow_html=True,
        )
        meta = " · ".join(x for x in [source.get("authors"), source.get("journal")] if x)
        if meta:
            st.caption(meta)
        if source.get("url"):
            st.markdown(f"[Open the paper]({source['url']})")

        with st.container(horizontal=True, gap="small"):
            if source.get("reading_status") != "read" or not source.get("date_read"):
                if st.button("Mark as read today", type="primary", key=f"read_{sid}"):
                    fields = {**source, "reading_status": "read", "date_read": TODAY,
                              "year": source.get("year")}
                    _act(lambda: db.update_source(sid, fields, sources), "Marked as read today.")
            if st.button("Close", key=f"close_{sid}"):
                _close_source()
                st.rerun()

        if source.get("summary_source"):
            st.caption(
                f"Methodology, findings and conclusions below came from: {source['summary_source']}. "
                "They are not your own notes."
                + (" This summary was made from the abstract only." if source.get("summary_basis") == "abstract" else "")
            )
        for label, field in (("Methodology", "methodology"), ("Key findings", "key_findings"),
                             ("Conclusions", "conclusions"), ("Limitations", "limitations")):
            if source.get(field):
                st.markdown(f"**{label}:** {source[field]}")
        if any(source.get(f) for f in ("relevance", "gap_contribution", "critical_notes")):
            st.markdown("**My thinking**")
            for label, field in (("Relevance", "relevance"), ("Gap contribution", "gap_contribution"),
                                 ("Critical notes", "critical_notes")):
                if source.get(field):
                    st.markdown(f"*{label}:* {source[field]}")
        if source.get("abstract"):
            with st.expander("Abstract"):
                st.write(source["abstract"])

        with st.expander("Edit this source", icon=":material/edit:"):
            with st.form(f"edit_source_{sid}"):
                values = _source_fields(f"src_{sid}", source)
                if st.form_submit_button("Save changes", type="primary"):
                    _act(lambda: db.update_source(sid, values, sources), "Source updated.")
            confirm = st.checkbox("Yes, delete this source permanently", key=f"delsrc_ok_{sid}")
            if st.button("Delete source", key=f"delsrc_{sid}", disabled=not confirm):
                _close_source()
                _act(lambda: db.delete_source(sid), "Source deleted.")


def _literature(data: dict) -> None:
    sources = data["sources"]

    with st.expander("Add a source", icon=":material/add:"):
        with st.form("add_source", clear_on_submit=True):
            title = st.text_area("Title", height=70, key="new_src_title")
            c1, c2 = st.columns(2)
            with c1:
                authors = st.text_input("Authors (optional)", key="new_src_authors")
                year = st.number_input("Year (optional)", min_value=1800, max_value=TODAY.year + 1,
                                       step=1, value=None, key="new_src_year")
            with c2:
                doi = st.text_input("DOI (optional)", key="new_src_doi")
                status = st.selectbox("Reading status", READING_STATUSES, index=1,
                                      format_func=READING_LABELS.get, key="new_src_status")
            tags = st.text_input("Tags (optional, separate with commas)", key="new_src_tags")
            st.caption("You can add findings, notes and everything else after saving.")
            if st.form_submit_button("Save source", type="primary"):
                fields = {"title": title, "authors": authors, "year": year, "doi": doi,
                          "reading_status": status, "tags": tags}
                _act(lambda: db.add_source(fields, sources), "Source saved.")
    st.page_link("views/import_data.py", label="Import a literature matrix (.xlsx) or CSV", icon=":material/upload:")

    if not sources:
        ui.empty_state("No sources yet", "Add a source above, or import your literature review matrix.")
        return

    # Filters
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        query = st.text_input("Search", placeholder="Words in the title, findings, notes or tags",
                              key="lit_query")
    with c2:
        status = st.selectbox("Reading status", ["all"] + READING_STATUSES,
                              format_func=lambda s: "All" if s == "all" else READING_LABELS[s],
                              key="lit_status")
    with c3:
        all_tags = sorted({t for s in sources for t in _tags(s)}, key=str.lower)
        tag = st.selectbox("Tag", ["all"] + all_tags, format_func=lambda t: "All" if t == "all" else t,
                           key="lit_tag")

    shown = [
        s for s in sources
        if _matches(s, query)
        and (status == "all" or s.get("reading_status") == status)
        and (tag == "all" or tag in _tags(s))
    ]
    st.caption(f"Showing {len(shown)} of {len(sources)} sources. Tap a row to open it.")

    open_id = st.session_state.get("_lit_open")
    opened = next((s for s in sources if s["id"] == open_id), None)
    if opened:
        _source_detail(opened, sources)

    if not shown:
        ui.empty_state("No matches", "Try fewer words, or set the filters back to All.")
        return
    table = [
        {
            "Title": s["title"],
            "Year": s.get("year"),
            "Status": READING_LABELS.get(s.get("reading_status"), ""),
            "Summary from": SUMMARY_BASIS_LABELS.get(s.get("summary_basis"), ""),
            "Tags": s.get("tags") or "",
        }
        for s in shown
    ]
    event = st.dataframe(
        table, hide_index=True, on_select="rerun", selection_mode="single-row",
        key=f"lit_table_{st.session_state.get('_lit_nonce', 0)}_{len(shown)}_{query}_{status}_{tag}",
        column_config={
            "Title": st.column_config.TextColumn(width="large"),
            "Year": st.column_config.NumberColumn(format="%d", width="small"),
        },
    )
    rows = getattr(getattr(event, "selection", None), "rows", None) or []
    if rows and shown[rows[0]]["id"] != open_id:
        st.session_state["_lit_open"] = shown[rows[0]]["id"]
        st.rerun()


# ------------------------------------------------------------- supervision


def _supervision(data: dict) -> None:
    feedback = data["feedback"]
    meetings = data["meetings"]
    tasks = data["tasks"]

    ui.section("Feedback to address", "Tick an item when you have addressed it.")
    if not feedback:
        ui.empty_state("No feedback recorded", "Feedback items appear here once recorded or imported.")
    for item in feedback:
        done = item.get("status") == "addressed"
        period = item.get("received_period") or ""
        ticked = st.checkbox(f"{item['item']}" + (f"  ({period})" if period else ""),
                             value=done, key=f"fb_{item['id']}")
        if ticked != done:
            _act(lambda i=item, t=ticked: db.set_feedback_status(i["id"], "addressed" if t else "open", i.get("notes") or ""),
                 "Feedback updated.")

    ui.section("Supervisor meetings")
    with st.expander("Record a meeting", icon=":material/add:"):
        with st.form("add_meeting", clear_on_submit=True):
            meeting_date = st.date_input("Meeting date", value=TODAY, max_value=TODAY,
                                         format="DD/MM/YYYY", key="new_mt_date")
            title = st.text_input("Topic (optional)", key="new_mt_title")
            fb = st.text_area("Feedback", key="new_mt_feedback")
            decisions = st.text_area("Decisions", key="new_mt_decisions")
            notes = st.text_area("Other notes", key="new_mt_notes")
            st.caption("Add action items with deadlines after saving. They become PhD tasks.")
            if st.form_submit_button("Save meeting", type="primary"):
                _act(lambda: db.add_meeting(meeting_date, title, fb, decisions, notes), "Meeting saved.")

    if not meetings:
        ui.empty_state("No meetings recorded yet", "Record your next supervision meeting above.")
        return

    for meeting in meetings:
        mid = meeting["id"]
        actions = [t for t in tasks if t.get("meeting_id") == mid]
        open_count = sum(1 for t in actions if t.get("status") != "done")
        label = f"{format_date(parse_date(meeting['meeting_date']))}"
        if meeting.get("title"):
            label += f" · {meeting['title']}"
        if actions:
            label += f" · {open_count} open action(s)"
        with st.expander(label):
            for name, field in (("Feedback", "feedback"), ("Decisions", "decisions"), ("Notes", "notes")):
                if meeting.get(field):
                    st.markdown(f"**{name}:** {meeting[field]}")

            st.markdown("**Action items**")
            if not actions:
                st.caption("None yet.")
            for task in actions:
                is_done = task.get("status") == "done"
                due = parse_date(task.get("due_date"))
                text = task["title"] + (f"  ({due_label(due, TODAY)})" if due and not is_done else "")
                ticked = st.checkbox(text, value=is_done, key=f"act_{task['id']}")
                if ticked != is_done:
                    _act(lambda t=task, d=ticked: db.set_task_status(t["id"], "done" if d else "todo"),
                         "Action item updated.")
            with st.form(f"add_action_{mid}", clear_on_submit=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    action = st.text_input("New action item", key=f"act_title_{mid}")
                with c2:
                    deadline = st.date_input("Deadline (optional)", value=None, format="DD/MM/YYYY",
                                             key=f"act_due_{mid}")
                if st.form_submit_button("Add action item"):
                    _act(lambda: db.add_task(action, "phd", deadline, meeting_id=mid), "Action item added.")

            if st.toggle("Edit or delete this meeting", key=f"mt_edit_{mid}"):
                with st.form(f"edit_meeting_{mid}"):
                    md = st.date_input("Meeting date", value=parse_date(meeting["meeting_date"]),
                                       max_value=TODAY, format="DD/MM/YYYY", key=f"mt_date_{mid}")
                    mt = st.text_input("Topic", value=meeting.get("title") or "", key=f"mt_title_{mid}")
                    mf = st.text_area("Feedback", value=meeting.get("feedback") or "", key=f"mt_fb_{mid}")
                    mdc = st.text_area("Decisions", value=meeting.get("decisions") or "", key=f"mt_dec_{mid}")
                    mn = st.text_area("Other notes", value=meeting.get("notes") or "", key=f"mt_notes_{mid}")
                    if st.form_submit_button("Save changes", type="primary"):
                        _act(lambda: db.update_meeting(mid, md, mt, mf, mdc, mn), "Meeting updated.")
                ok = st.checkbox("Yes, delete this meeting (its action items stay as tasks)", key=f"mt_del_ok_{mid}")
                if st.button("Delete meeting", key=f"mt_del_{mid}", disabled=not ok):
                    _act(lambda: db.delete_meeting(mid), "Meeting deleted.")


# ----------------------------------------------------------------- timeline


def _semester_rows(saved: list) -> list[dict]:
    rows = []
    for i in range(6):
        item = saved[i] if i < len(saved) and isinstance(saved[i], dict) else {}
        rows.append({
            "Semester": item.get("label") or f"Semester {i + 1}",
            "Start": parse_date(item.get("start")),
            "End": parse_date(item.get("end")),
        })
    return rows


def _timeline_chart(milestones: list[dict], semesters: list[dict]) -> None:
    planned = [m for m in milestones if m.get("due_date")]
    actual = [m for m in milestones if m.get("completed_on")]
    bands = [s for s in semesters if parse_date(s.get("start")) and parse_date(s.get("end"))]
    if not planned and not actual and not bands:
        ui.empty_state(
            "No dates yet",
            "Add planned dates to your milestones, or enter your semester dates below, "
            "and the timeline chart appears here.",
        )
        return

    titles = [m["title"] for m in milestones][::-1]
    fig = go.Figure()
    shades = ["rgba(124,154,130,0.16)", "rgba(79,138,139,0.12)"]
    for i, sem in enumerate(bands):
        fig.add_vrect(x0=sem["start"], x1=sem["end"], fillcolor=shades[i % 2], line_width=0,
                      annotation_text=sem.get("label") or f"Semester {i + 1}",
                      annotation_position="top left", annotation_font_size=10)
    if planned:
        fig.add_trace(go.Scatter(
            x=[m["due_date"] for m in planned], y=[m["title"] for m in planned], mode="markers",
            name="Planned", marker=dict(symbol="diamond-open", size=13, color="#4F8A8B", line=dict(width=2)),
            hovertemplate="%{y}<br>Planned %{x|%d %b %Y}<extra></extra>",
        ))
    if actual:
        fig.add_trace(go.Scatter(
            x=[m["completed_on"] for m in actual], y=[m["title"] for m in actual], mode="markers",
            name="Completed", marker=dict(symbol="circle", size=11, color="#55735C"),
            hovertemplate="%{y}<br>Completed %{x|%d %b %Y}<extra></extra>",
        ))
    fig.add_vline(x=TODAY.isoformat(), line_width=1, line_dash="dot", line_color="#A98545")
    fig.update_layout(
        height=max(260, 34 * len(titles) + 80), margin=dict(l=0, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(categoryorder="array", categoryarray=titles, title=None),
        xaxis=dict(type="date", title=None),
        legend=dict(orientation="h", y=-0.15), showlegend=bool(planned or actual),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, key="phd_timeline")


def _timeline(data: dict) -> None:
    milestones = data["milestones"]
    done = [m for m in milestones if m.get("status") == "completed"]
    progress = [m for m in milestones if m.get("status") == "in_progress"]
    if milestones:
        st.markdown(
            f"**{len(done)} of {len(milestones)} milestones completed** · {len(progress)} in progress"
        )
    _timeline_chart(milestones, data["semesters"])

    ui.section("Milestones", "Planned date, status and the date it was actually completed.")
    if not milestones:
        ui.empty_state("No milestones yet", "Add your first milestone below.")
    for m in milestones:
        mid = m["id"]
        planned = parse_date(m.get("due_date"))
        actual = parse_date(m.get("completed_on"))
        status = m.get("status") or "planned"
        label = f"{m['title']} · {db.MILESTONE_LABELS.get(status, status)}"
        if status == "completed" and actual:
            label += f" {format_date(actual)}"
        elif planned:
            label += f" · {due_label(planned, TODAY)}"
        else:
            label += " · no planned date"
        with st.expander(label):
            with st.form(f"ms_{mid}"):
                title = st.text_input("Milestone", value=m["title"], key=f"ms_title_{mid}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_planned = st.date_input("Planned date", value=planned, format="DD/MM/YYYY", key=f"ms_plan_{mid}")
                with c2:
                    new_status = st.selectbox(
                        "Status", db.MILESTONE_STATUSES, format_func=db.MILESTONE_LABELS.get,
                        index=db.MILESTONE_STATUSES.index(status) if status in db.MILESTONE_STATUSES else 0,
                        key=f"ms_status_{mid}",
                    )
                with c3:
                    new_actual = st.date_input("Actual completion date", value=actual, max_value=TODAY,
                                               format="DD/MM/YYYY", key=f"ms_actual_{mid}")
                clear = st.checkbox("Remove the planned date", key=f"ms_clear_{mid}")
                notes = st.text_area("Notes", value=m.get("notes") or "", height=70, key=f"ms_notes_{mid}")
                if st.form_submit_button("Save", type="primary"):
                    _act(lambda: db.update_milestone(mid, title, None if clear else new_planned,
                                                     new_status, new_actual, notes), "Milestone saved.")
            ok = st.checkbox("Yes, delete this milestone", key=f"ms_del_ok_{mid}")
            if st.button("Delete milestone", key=f"ms_del_{mid}", disabled=not ok):
                _act(lambda: db.delete_milestone(mid), "Milestone deleted.")

    with st.expander("Add a milestone", icon=":material/add:"):
        with st.form("add_milestone", clear_on_submit=True):
            title = st.text_input("Milestone", key="new_ms_title")
            planned = st.date_input("Planned date (optional)", value=None, format="DD/MM/YYYY", key="new_ms_plan")
            if st.form_submit_button("Add milestone"):
                position = max([m.get("position") or 0 for m in milestones] or [0]) + 1
                _act(lambda: db.add_milestone(title, planned, position), "Milestone added.")

    ui.section("Semester dates", "Enter the dates from your USM academic calendar. Leave a row empty if not known yet.")
    edited = st.data_editor(
        _semester_rows(data["semesters"]), hide_index=True, key="semesters_editor",
        column_config={
            "Semester": st.column_config.TextColumn(),
            "Start": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "End": st.column_config.DateColumn(format="DD/MM/YYYY"),
        },
    )
    if st.button("Save semester dates", key="save_semesters"):
        records = edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)

        def _iso(value):
            if value is None or value != value:  # empty cell (None, NaN or NaT)
                return None
            if isinstance(value, datetime):
                value = value.date()
            if not isinstance(value, date):
                value = parse_date(value)
            return value.isoformat() if value else None

        cleaned = []
        for row in records:
            start, end = _iso(row.get("Start")), _iso(row.get("End"))
            if start and end and end < start:
                st.error(f"{row.get('Semester')}: the end date is before the start date.")
                return
            cleaned.append({"label": (row.get("Semester") or "").strip() or None, "start": start, "end": end})
        _act(lambda: db.set_setting("phd", "semesters", cleaned), "Semester dates saved.")


# --------------------------------------------------------------------- main


def main() -> None:
    ui.page_header("PhD Research Hub", "Literature, supervision and your thesis timeline.", eyebrow="Phase 2")
    flash = st.session_state.pop("_flash", None)
    if flash:
        st.toast(flash)
    data = _load()
    overview, lit, supervision, timeline = st.tabs(["Overview", "Literature", "Supervision", "Timeline"])
    with overview:
        _overview(data)
    with lit:
        _literature(data)
    with supervision:
        _supervision(data)
    with timeline:
        _timeline(data)


main()
