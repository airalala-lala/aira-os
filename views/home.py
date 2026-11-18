"""Home: the daily command centre.

Sections, top to bottom:
  1. Running timer (only while a timer is running)
  2. Restart card (after several quiet days, or when you ask for it)
  3. Today's Top 3
  4. My focus today (PhD focus, movement, one important task)
  5. This week (actual versus planned)
  6. All tasks

Every number comes from your own records. Suggestions are labelled as
suggestions, and anything not recorded is shown as missing.
"""

import html
from datetime import timedelta

import streamlit as st

from aira import db, planning, ui
from aira.planning import AREA_LABELS, AREAS, PRIORITIES, PRIORITY_LABELS, TIME_CATEGORIES
from aira.timeutil import (
    due_label,
    format_date,
    format_time,
    greeting,
    minutes_since,
    now_kl,
    parse_date,
    parse_timestamp,
    today_kl,
)

AREA_COLOURS = {
    "phd": "teal", "fitness": "sage", "family": "rose", "business": "gold",
}


# ------------------------------------------------------------------ helpers


def _act(action, message: str) -> None:
    """Run one database change, then reload the page with a short message."""
    try:
        action()
    except db.DataError as exc:
        st.error(str(exc))
        return
    st.session_state["_flash"] = message
    st.rerun()


def _load() -> dict:
    today = today_kl()
    since = today - timedelta(days=60)
    try:
        return {
            "today": today,
            "profile": db.get_profile(),
            "tasks": db.list_tasks(),
            "entries": db.list_time_entries(since),
            "running": db.running_timer(),
            "workouts": db.list_workouts(since),
            "targets": db.get_setting("general", "weekly_targets", {}) or {},
        }
    except db.DataError as exc:
        st.error(str(exc))
        if st.button("Try again"):
            st.rerun()
        st.stop()


def _task_badges(task: dict, today, extra: str = "") -> str:
    area = task.get("module")
    parts = [ui.badge(AREA_LABELS.get(area, "Other"), AREA_COLOURS.get(area, ""))]
    due = parse_date(task.get("due_date"))
    if due:
        parts.append(ui.badge(due_label(due, today), "rose" if due < today else ""))
    if task.get("priority") == "high":
        parts.append(ui.badge("High priority", "gold"))
    if extra:
        parts.append(ui.badge(extra))
    return "".join(parts)


# -------------------------------------------------------------------- timer


@st.fragment(run_every="30s")
def _timer_banner(running: dict) -> None:
    """Shows the running timer. Refreshes itself every 30 seconds."""
    elapsed = minutes_since(running.get("started_at"))
    label = AREA_LABELS.get(running.get("category"), "Other")
    started = format_time(parse_timestamp(running.get("started_at")))
    note = f" · {html.escape(running['note'])}" if running.get("note") else ""
    st.markdown(
        f'<div class="aira-timer"><b>{html.escape(label)} timer running</b><br>'
        f"Started {started} · {planning.format_minutes(elapsed)} so far{note}</div>",
        unsafe_allow_html=True,
    )

    if elapsed > planning.LONG_TIMER_MINUTES:
        st.caption(
            "This timer has been running for a long time. Enter the minutes "
            "you actually worked, so the record stays accurate."
        )
        with st.form("stop_long_timer"):
            worked = st.number_input(
                "Minutes actually worked", min_value=1, max_value=1440, value=None, step=5,
                key="long_timer_minutes",
            )
            if st.form_submit_button("Stop and save", type="primary"):
                if worked is None:
                    st.error("Please enter the minutes you worked.")
                else:
                    _act(lambda: db.stop_timer(running["id"], int(worked)), "Session saved.")
    else:
        if st.button(
            f"Stop and save ({planning.format_minutes(elapsed)})",
            type="primary", key="stop_timer",
        ):
            _act(lambda: db.stop_timer(running["id"], elapsed), "Session saved.")

    if st.button("Discard this timer", key="discard_timer"):
        _act(lambda: db.delete_time_entry(running["id"]), "Timer discarded. Nothing was logged.")


# ------------------------------------------------------------------ restart


def _restart_card(data: dict, last_activity) -> None:
    today = data["today"]
    with st.container(border=True, key="restart_card"):
        if last_activity:
            quiet = (today - last_activity).days
            intro = f"Your last entry was {format_date(last_activity)}, {quiet} days ago."
        else:
            intro = "A fresh start."
        st.markdown(
            '<div class="aira-card-title">Restart today</div>'
            f'<div class="aira-card-text">{html.escape(intro)} '
            "Two small things are enough for today. Everything else can wait, "
            "and nothing has been deleted.</div>",
            unsafe_allow_html=True,
        )

        phd_task = planning.restart_phd_action(data["tasks"], today)
        col1, col2 = st.columns(2)
        with col1:
            if phd_task:
                ui.slot("One PhD action", phd_task["title"], "Your earliest open PhD task")
                if st.button("Start a PhD focus timer", key="restart_focus",
                             disabled=data["running"] is not None):
                    _act(lambda: db.start_timer("phd", phd_task["title"]), "Timer started.")
            else:
                ui.slot("One PhD action", "No PhD task recorded yet",
                        "Write one small step you could finish today.")
                with st.form("restart_phd", clear_on_submit=True):
                    title = st.text_input("One small PhD step", max_chars=300, key="restart_phd_title")
                    if st.form_submit_button("Add and pin to today"):
                        _act(lambda: db.add_task(title, "phd", pin_today=True), "Added to today.")
        with col2:
            ui.slot("One short movement option", "Choose whichever feels doable",
                    "Suggestions only. Log it afterwards if you do it.")
            st.markdown("\n".join(f"- {option}" for option in planning.SHORT_EXERCISE_OPTIONS))

        waiting = planning.postponable_tasks(data["tasks"], today)
        if waiting:
            st.caption(
                f"{len(waiting)} overdue non-essential task(s) can be set aside for 7 days. "
                "Their due dates stay as they are and nothing is marked done."
            )
            if st.button(f"Postpone these {len(waiting)} task(s) for 7 days", key="restart_postpone"):
                ids = [task["id"] for task in waiting]
                _act(lambda: db.snooze_tasks(ids, today + timedelta(days=7)), "Postponed for 7 days.")

        if st.button("Show my full dashboard", key="restart_exit"):
            st.session_state["_restart_off"] = today.isoformat()
            st.session_state.pop("_restart_on", None)
            st.rerun()


# -------------------------------------------------------------------- top 3


def _top3(data: dict, picks: list[dict]) -> None:
    today = data["today"]
    ui.section("Today's Top 3", "Pinned by you first, then suggestions. PhD and fitness come before non-urgent business.")
    if not picks:
        ui.empty_state(
            "No priorities yet",
            "Add a task below. Once tasks exist, three manageable priorities appear here.",
        )
        return
    for pick in picks:
        task = pick["task"]
        source = "Pinned by you" if pick["source"] == "pinned" else f"Suggested · {pick['reason']}"
        with st.container(border=True):
            st.markdown(
                f'<div class="aira-card-title">{html.escape(task["title"])}</div>'
                f'<div style="margin-top:0.35rem">{_task_badges(task, today, source)}</div>',
                unsafe_allow_html=True,
            )
            # One row of buttons that stays a row on a phone.
            with st.container(horizontal=True, gap="small"):
                if st.button("Done", key=f"top_done_{task['id']}", type="primary"):
                    _act(lambda t=task: db.set_task_status(t["id"], "done"), "Marked as done.")
                if pick["source"] == "pinned":
                    if st.button("Unpin", key=f"top_unpin_{task['id']}"):
                        _act(lambda t=task: db.pin_task(t["id"], None), "Unpinned.")
                else:
                    if st.button("Pin", key=f"top_pin_{task['id']}"):
                        _act(lambda t=task: db.pin_task(t["id"], today), "Pinned to today.")
                if st.button("Not today", key=f"top_skip_{task['id']}"):
                    _act(
                        lambda t=task: db.snooze_tasks([t["id"]], today + timedelta(days=1)),
                        "Set aside until tomorrow.",
                    )


# -------------------------------------------------------------------- focus


def _focus_today(data: dict, picks: list[dict]) -> None:
    today = data["today"]
    busy = data["running"] is not None
    ui.section("My focus today")
    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            logged = planning.minutes_on(data["entries"], "phd", today)
            ui.slot(
                "PhD focus session",
                planning.format_minutes(logged) + " today" if logged else "Nothing logged today",
                "Start a timer, or log time afterwards.",
            )
            if st.button("Start PhD focus", key="start_phd", type="primary", disabled=busy):
                _act(lambda: db.start_timer("phd"), "Timer started.")

    with col2:
        with st.container(border=True):
            todays = [w for w in data["workouts"] if parse_date(w.get("workout_date")) == today]
            done = [w for w in todays if w.get("status") == "completed"]
            planned = [w for w in todays if w.get("status") == "planned"]
            if done:
                kinds = ", ".join(db.WORKOUT_KIND_LABELS.get(w.get("kind"), "Workout") for w in done)
                ui.slot("Movement", f"Done today: {kinds}", "Recorded by you.")
            elif planned:
                workout = planned[0]
                ui.slot("Movement", "Planned: " + db.WORKOUT_KIND_LABELS.get(workout.get("kind"), "Workout"),
                        "Mark it done when finished.")
                if st.button("Mark done", key=f"wo_done_{workout['id']}", type="primary"):
                    _act(lambda: db.set_workout_status(workout["id"], "completed"), "Workout recorded.")
            else:
                ui.slot("Movement", "Nothing planned today", "Plan or log a session below, or take a recovery day.")

    with col3:
        with st.container(border=True):
            other = [p for p in picks if p["task"].get("module") not in planning.PROTECTED_AREAS]
            if other:
                task = other[0]["task"]
                ui.slot("One important task", task["title"], AREA_LABELS.get(task.get("module"), "Other"))
            else:
                ui.slot("One important task", "None selected", "Pin a personal or professional task to today.")

    with st.expander("Plan or log a workout", icon=":material/fitness_center:"):
        with st.form("workout_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                kind = st.selectbox("Type", db.WORKOUT_KINDS, format_func=db.WORKOUT_KIND_LABELS.get, key="wo_kind")
                when = st.date_input("Date", value=today, format="DD/MM/YYYY", key="wo_date")
            with c2:
                status = st.selectbox(
                    "Status", ["completed", "planned"],
                    format_func={"completed": "Completed", "planned": "Planned"}.get,
                    key="wo_status",
                )
                minutes = st.number_input("Minutes (optional)", min_value=1, max_value=600, value=None, step=5, key="wo_minutes")
            location = st.text_input("Location (optional)", max_chars=100, key="wo_location")
            notes = st.text_input("Notes (optional)", max_chars=300, key="wo_notes")
            if st.form_submit_button("Save workout", type="primary"):
                _act(lambda: db.add_workout(when, kind, status, minutes, location, notes), "Workout saved.")

    with st.expander("Start another timer or log time", icon=":material/timer:"):
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox("Area", TIME_CATEGORIES, format_func=AREA_LABELS.get, key="timer_area")
        with c2:
            st.write("")
            if st.button("Start timer", key="start_other", disabled=busy):
                _act(lambda: db.start_timer(category), "Timer started.")
        with st.form("manual_time", clear_on_submit=True):
            st.caption("Log time you already spent")
            c1, c2, c3 = st.columns(3)
            with c1:
                area = st.selectbox("Area", TIME_CATEGORIES, format_func=AREA_LABELS.get, key="mt_area")
            with c2:
                when = st.date_input("Date", value=today, max_value=today, format="DD/MM/YYYY", key="mt_date")
            with c3:
                minutes = st.number_input("Minutes", min_value=1, max_value=1440, value=None, step=5, key="mt_minutes")
            note = st.text_input("Note (optional)", max_chars=300, key="mt_note")
            if st.form_submit_button("Save time"):
                _act(lambda: db.add_time_entry(area, when, minutes, note), "Time saved.")


# --------------------------------------------------------------------- week


def _hours_row(label: str, minutes, target_hours, colour: str, limit: bool = False) -> None:
    word = "limit" if limit else "planned"
    if minutes is None and target_hours is None:
        ui.meter(label, "Nothing logged · no target set")
    elif minutes is None:
        ui.meter(label, f"Nothing logged · {target_hours:g} h {word}", 0.0, colour)
    elif target_hours is None:
        ui.meter(label, f"{planning.format_minutes(minutes)} logged · no target set")
    else:
        ui.meter(
            label,
            f"{planning.format_minutes(minutes)} of {target_hours:g} h {word}",
            minutes / (target_hours * 60),
            colour,
        )


def _this_week(data: dict) -> None:
    summary = planning.week_summary(data["entries"], data["workouts"], data["targets"], data["today"])
    ui.section(
        "This week",
        f"{format_date(summary['week_start'])} to {format_date(summary['week_end'])} · actual versus planned",
    )
    ui.week_strip(summary["days"])
    missing = sum(1 for day in summary["days"] if day["state"] == "missing")
    if missing:
        st.caption(
            f"{missing} day(s) so far have no entries. They are shown as missing, not as zero."
        )

    _hours_row("PhD focused hours", summary["phd_minutes"], summary["phd_target_hours"], "teal")

    done, target = summary["workouts_done"], summary["workouts_target"]
    if done is None and target is None:
        ui.meter("Workouts completed", "None recorded · no target set")
    elif target is None:
        ui.meter("Workouts completed", f"{done} recorded · no target set")
    else:
        ui.meter("Workouts completed", f"{done or 0} of {target:g} planned", (done or 0) / target)

    ui.meter("Research papers processed", "Not tracked yet · arrives with the PhD Hub")
    _hours_row("Business hours", summary["business_minutes"], summary["business_limit_hours"], "gold", limit=True)
    _hours_row("Personal and family time", summary["family_minutes"], summary["family_target_hours"], "rose")

    if planning.business_over_limit(summary):
        st.info(
            "Business time is past the limit you chose for this week. "
            "It may be a good moment to close it for today."
        )
    st.page_link("views/settings.py", label="Set weekly targets and business limit", icon=":material/tune:")

    week_entries = [
        e for e in data["entries"]
        if e.get("minutes") is not None
        and summary["week_start"] <= (parse_date(e.get("entry_date")) or summary["week_end"] + timedelta(days=1)) <= summary["week_end"]
    ]
    if week_entries:
        with st.expander(f"This week's time entries ({len(week_entries)})"):
            for entry in week_entries:
                _time_entry_row(entry)


def _time_entry_row(entry: dict) -> None:
    entry_id = entry["id"]
    label = (
        f"{format_date(parse_date(entry.get('entry_date')))} · "
        f"{AREA_LABELS.get(entry.get('category'), 'Other')} · "
        f"{planning.format_minutes(entry.get('minutes'))}"
    )
    with st.form(f"time_{entry_id}"):
        st.markdown(f"**{label}**")
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox(
                "Area", TIME_CATEGORIES, format_func=AREA_LABELS.get,
                index=TIME_CATEGORIES.index(entry["category"]) if entry.get("category") in TIME_CATEGORIES else 0,
                key=f"te_area_{entry_id}",
            )
        with c2:
            minutes = st.number_input(
                "Minutes", min_value=1, max_value=1440, value=int(entry["minutes"]), step=5,
                key=f"te_min_{entry_id}",
            )
        note = st.text_input("Note", value=entry.get("note") or "", max_chars=300, key=f"te_note_{entry_id}")
        remove = st.checkbox("Delete this entry instead", key=f"te_del_{entry_id}")
        if st.form_submit_button("Save"):
            if remove:
                _act(lambda: db.delete_time_entry(entry_id), "Entry deleted.")
            else:
                _act(lambda: db.update_time_entry(entry_id, category, minutes, note), "Entry updated.")


# -------------------------------------------------------------------- tasks


def _add_task_form() -> None:
    with st.expander("Add a task", icon=":material/add:"):
        with st.form("add_task", clear_on_submit=True):
            title = st.text_input("Title", max_chars=300, key="new_title")
            c1, c2, c3 = st.columns(3)
            with c1:
                area = st.selectbox("Area", AREAS, format_func=AREA_LABELS.get, key="new_area")
            with c2:
                priority = st.selectbox("Priority", PRIORITIES, index=1, format_func=PRIORITY_LABELS.get, key="new_priority")
            with c3:
                due = st.date_input("Due date (optional)", value=None, format="DD/MM/YYYY", key="new_due")
            pin = st.checkbox("Pin to today's Top 3", key="new_pin")
            notes = st.text_area("Notes (optional)", height=70, key="new_notes")
            if st.form_submit_button("Save task", type="primary"):
                _act(lambda: db.add_task(title, area, due, notes, priority, pin), "Task saved.")


def _task_row(task: dict, today) -> None:
    task_id = task["id"]
    due = parse_date(task.get("due_date"))
    label = task["title"]
    if task.get("status") == "done":
        label = f"Done · {label}"
    elif planning.is_snoozed(task, today):
        label = f"{label} · postponed until {format_date(parse_date(task['snoozed_until']))}"
    elif due:
        label = f"{label} · {due_label(due, today)}"
    areas = AREAS if task.get("module") in AREAS else AREAS + [task.get("module") or "planner"]

    with st.expander(label):
        with st.form(f"edit_{task_id}"):
            title = st.text_input("Title", value=task["title"], max_chars=300, key=f"t_title_{task_id}")
            c1, c2, c3 = st.columns(3)
            with c1:
                area = st.selectbox(
                    "Area", areas, format_func=AREA_LABELS.get,
                    index=areas.index(task.get("module")) if task.get("module") in areas else 0,
                    key=f"t_area_{task_id}",
                )
            with c2:
                status = st.selectbox(
                    "Status", db.TASK_STATUSES, format_func=db.STATUS_LABELS.get,
                    index=db.TASK_STATUSES.index(task["status"]) if task.get("status") in db.TASK_STATUSES else 0,
                    key=f"t_status_{task_id}",
                )
            with c3:
                priority = st.selectbox(
                    "Priority", PRIORITIES, format_func=PRIORITY_LABELS.get,
                    index=PRIORITIES.index(task["priority"]) if task.get("priority") in PRIORITIES else 1,
                    key=f"t_priority_{task_id}",
                )
            new_due = st.date_input("Due date", value=due, format="DD/MM/YYYY", key=f"t_due_{task_id}")
            remove_due = st.checkbox("Remove the due date", value=False, key=f"t_nodue_{task_id}")
            pinned = st.checkbox(
                "Pinned to today's Top 3", value=planning.is_pinned_today(task, today),
                key=f"t_pin_{task_id}",
            )
            notes = st.text_area("Notes", value=task.get("notes") or "", height=70, key=f"t_notes_{task_id}")
            if st.form_submit_button("Save changes", type="primary"):
                def save():
                    db.update_task(task_id, title, area, None if remove_due else new_due, notes, status, priority)
                    if pinned != planning.is_pinned_today(task, today):
                        db.pin_task(task_id, today if pinned else None)
                _act(save, "Changes saved.")

        confirm = st.checkbox("Yes, delete this task permanently", key=f"confirm_{task_id}")
        if st.button("Delete task", key=f"delete_{task_id}", disabled=not confirm):
            _act(lambda: db.delete_task(task_id), "Task deleted.")


def _all_tasks(data: dict) -> None:
    today = data["today"]
    tasks = data["tasks"]
    open_tasks = [t for t in tasks if planning.is_open(t)]
    done_tasks = [t for t in tasks if not planning.is_open(t)]
    ui.section("All tasks")
    _add_task_form()
    if not tasks:
        ui.empty_state(
            "No tasks yet",
            "Add your first task above. It is saved to your database and "
            "appears on every device you sign in on.",
        )
        return
    if not open_tasks:
        ui.empty_state("Nothing open", "Every task you have recorded is done.")
    for task in open_tasks:
        _task_row(task, today)
    if done_tasks and st.toggle(f"Show completed tasks ({len(done_tasks)})", key="show_done"):
        for task in done_tasks:
            _task_row(task, today)


# --------------------------------------------------------------------- main


def main() -> None:
    data = _load()
    today = data["today"]
    name = (data["profile"] or {}).get("display_name") or ""
    ui.page_header(
        f"{greeting()}, {name}" if name else greeting(),
        f"{format_date(today)} · {format_time(now_kl())} Malaysia time",
        eyebrow="AIRA OS",
    )

    flash = st.session_state.pop("_flash", None)
    if flash:
        st.toast(flash)

    if data["running"]:
        _timer_banner(data["running"])

    last_activity = planning.last_activity_date(
        data["tasks"], data["entries"], data["workouts"], today
    )
    dismissed = st.session_state.get("_restart_off") == today.isoformat()
    restart = st.session_state.get("_restart_on") or (
        planning.needs_restart(last_activity, today) and not dismissed
    )

    picks = planning.suggest_top3(data["tasks"], today)

    if restart:
        _restart_card(data, last_activity)
    else:
        _top3(data, picks)

    _focus_today(data, picks)
    _this_week(data)

    if not restart:
        _all_tasks(data)
        st.write("")
        with st.container(horizontal=True, gap="small"):
            if st.button("Restart today", icon=":material/restart_alt:", key="restart_enter"):
                st.session_state["_restart_on"] = True
                st.rerun()
            if st.button("Refresh", icon=":material/refresh:", key="refresh"):
                st.rerun()
    st.caption("Connected to your database. This page shows only what you have recorded.")


main()
