"""Fitness Studio (Phase 3): overview, workout logger, progress, weight and weekly plan.

Every chart and number comes from what you recorded. Loads are shown exactly as
logged: kg stays kg, lb stays lb, per side and per dumbbell stay labelled, and
different machines are never compared with each other.
"""

import html
from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

from aira import db, fitness, ui
from aira.fitness import (
    LOAD_BASES, LOAD_BASIS_LABELS, LOAD_UNIT_LABELS, LOAD_UNITS,
    WORKOUT_KIND_LABELS, WORKOUT_KINDS,
)
from aira.timeutil import format_date, parse_date, today_kl

TODAY = today_kl()
STATUS_LABELS = {"completed": "Completed", "planned": "Planned", "skipped": "Skipped"}
CHART = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             margin=dict(l=0, r=10, t=10, b=10))
SAGE, TEAL, GOLD, ROSE = "#7C9A82", "#4F8A8B", "#A98545", "#B9848A"


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
        template = db.get_plan_template()
        if template:
            # Add this week's sessions from your weekly plan (today onward).
            db.fill_week_from_template(fitness.week_start(TODAY))
        return {
            "template": template,
            "workouts": db.list_all_workouts(),
            "sets": db.list_sets(),
            "cardio": db.list_cardio(),
            "weights": db.list_weights(),
            "goal": db.goal_weight(),
            "targets": db.get_setting("general", "weekly_targets", {}) or {},
            "prefs": db.get_setting("fitness", "workout_preferences", []) or [],
        }
    except db.DataError as exc:
        st.error(str(exc))
        st.info(
            "The Fitness Studio needs migration 0006. In Supabase, open the SQL Editor, "
            "run supabase/migrations/0006_fitness_studio.sql, then reload this page."
        )
        st.stop()


def _kind(w: dict) -> str:
    return WORKOUT_KIND_LABELS.get(w.get("kind"), "Workout")


def _summary(w: dict, sets: list[dict], cardio: list[dict]) -> str:
    names = []
    for s in sorted(sets, key=lambda x: x.get("position") or 0):
        if s["exercise_name"] not in names:
            names.append(s["exercise_name"])
    names += [c["activity"] for c in sorted(cardio, key=lambda x: x.get("position") or 0)]
    return ", ".join(names)


# ------------------------------------------------------------------ editors

SET_COLUMNS = {
    "id": None,  # hidden
    "Exercise": st.column_config.TextColumn(width="medium"),
    "Set": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
    "Reps": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
    "Load": st.column_config.NumberColumn(min_value=0.0, step=0.25, width="small"),
    "Unit": st.column_config.SelectboxColumn(options=LOAD_UNITS, width="small"),
    "Basis": st.column_config.SelectboxColumn(options=LOAD_BASES, width="small",
                                              help="per_side: plates on each side. per_dumbbell: one dumbbell."),
    "RPE": st.column_config.NumberColumn(min_value=1.0, max_value=10.0, step=0.5, width="small",
                                         help="How hard it felt, 1 to 10. Optional."),
    "As written": st.column_config.TextColumn(disabled=True, help="The original wording from an import."),
    "Notes": st.column_config.TextColumn(),
}
CARDIO_COLUMNS = {
    "id": None,
    "Activity": st.column_config.TextColumn(help="For example Rowing, Swimming (breaststroke), Treadmill"),
    "Distance (m)": st.column_config.NumberColumn(min_value=0.0, step=50.0),
    "Minutes": st.column_config.NumberColumn(min_value=0.0, step=0.5),
    "Approx.": st.column_config.CheckboxColumn(help="Tick if the time is approximate."),
    "Settings": st.column_config.TextColumn(help="Damper, level, incline… as you would write it"),
    "Notes": st.column_config.TextColumn(),
}


def _blank_sets(n: int = 4) -> list[dict]:
    return [{"id": None, "Exercise": None, "Set": None, "Reps": None, "Load": None, "Unit": "kg",
             "Basis": None, "RPE": None, "As written": "", "Notes": None} for _ in range(n)]


def _blank_cardio(n: int = 1) -> list[dict]:
    return [{"id": None, "Activity": None, "Distance (m)": None, "Minutes": None, "Approx.": False,
             "Settings": None, "Notes": None} for _ in range(n)]


def _records(edited) -> list[dict]:
    return edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)


def _header_fields(prefix: str, w: dict | None = None) -> dict:
    w = w or {}
    c1, c2, c3 = st.columns(3)
    with c1:
        day = st.date_input("Date", value=parse_date(w.get("workout_date")) or TODAY,
                            format="DD/MM/YYYY", key=f"{prefix}_date")
        kind = st.selectbox("Type", WORKOUT_KINDS, format_func=WORKOUT_KIND_LABELS.get,
                            index=WORKOUT_KINDS.index(w["kind"]) if w.get("kind") in WORKOUT_KINDS else 0,
                            key=f"{prefix}_kind")
    with c2:
        statuses = ["completed", "planned", "skipped"]
        status = st.selectbox("Status", statuses, format_func=STATUS_LABELS.get,
                              index=statuses.index(w["status"]) if w.get("status") in statuses else 0,
                              key=f"{prefix}_status")
        minutes = st.number_input("Duration in minutes (optional)", min_value=1, max_value=600, step=5,
                                  value=w.get("duration_min"), key=f"{prefix}_minutes")
    with c3:
        location = st.text_input("Location (optional)", value=w.get("location") or "", key=f"{prefix}_location")
        rpe = st.number_input("Session effort, 1 to 10 (optional)", min_value=1.0, max_value=10.0, step=0.5,
                              value=float(w["rpe"]) if w.get("rpe") is not None else None, key=f"{prefix}_rpe")
    notes = st.text_input("Notes (optional)", value=w.get("notes") or "", key=f"{prefix}_notes")
    return {"workout_date": day, "kind": kind, "status": status, "duration_min": minutes,
            "location": location, "notes": notes, "rpe": rpe}


def _show_problems(problems: list[str]) -> None:
    st.error("Nothing was saved. Please fix: " + "; ".join(problems[:6]))


# ----------------------------------------------------------------- overview


def _overview(data: dict) -> None:
    workouts = data["workouts"]
    monday = fitness.week_start(TODAY)
    this_week = [w for w in workouts if (d := parse_date(w.get("workout_date"))) and monday <= d <= monday + timedelta(days=6)]
    done = [w for w in this_week if w.get("status") == "completed"]
    planned = [w for w in this_week if w.get("status") == "planned"]
    target = data["targets"].get("workouts")
    last = fitness.last_completed(workouts, TODAY)
    points = fitness.weight_points(data["weights"])

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            value = f"{len(done)} of {target:g} planned" if target else (f"{len(done)} completed" if done else "None recorded yet")
            ui.slot("This week", value, f"{len(planned)} more planned this week" if planned else "Nothing else planned")
    with col2:
        with st.container(border=True):
            if last:
                ago = (TODAY - last).days
                ui.slot("Last recorded workout", format_date(last),
                        "Today" if ago == 0 else f"{ago} day(s) ago")
            else:
                ui.slot("Last recorded workout", "None yet", "Log one in the Log tab.")
    with col3:
        with st.container(border=True):
            if points:
                day, kg = points[-1]
                ui.slot("Last recorded weight", f"{kg:.2f} kg", f"On {format_date(day)}. Not assumed to be today's weight.")
            else:
                ui.slot("Last recorded weight", "None yet", "Add one in the Weight tab.")

    if last and (TODAY - last).days >= 7:
        with st.container(border=True):
            st.markdown(
                f'<div class="aira-card-title">Gentle restart</div><div class="aira-card-text">'
                f"Your last recorded workout was {(TODAY - last).days} days ago. "
                "A short session still counts. Nothing is lost.</div>",
                unsafe_allow_html=True,
            )
            if st.button("Plan 15 minutes of easy rowing today", key="restart_row"):
                _act(lambda: db.log_workout(
                    {"workout_date": TODAY, "kind": "rowing", "status": "planned", "duration_min": 15,
                     "notes": "Restart session"}, [], []), "Added to today's plan.")

    ui.section("Consistency", "Completed workouts per week. Weeks with nothing recorded show no bar.")
    weeks = fitness.weekly_counts(workouts, TODAY, 12)
    if not any(w["count"] for w in weeks):
        ui.empty_state("No completed workouts in the last 12 weeks", "Workouts you log appear here.")
    else:
        fig = go.Figure(go.Bar(
            x=[f"{w['week'].day} {w['week']:%b}" for w in weeks], y=[w["count"] for w in weeks],
            marker_color=SAGE, hovertemplate="Week of %{x}: %{y} workout(s)<extra></extra>",
        ))
        if target:
            fig.add_hline(y=target, line_dash="dot", line_color=GOLD,
                          annotation_text=f"Your target: {target:g}", annotation_position="top left")
        fig.update_layout(height=230, yaxis=dict(dtick=1, rangemode="tozero"), **CHART)
        st.plotly_chart(fig, config={"displayModeBar": False}, key="fit_weeks")
        months = fitness.monthly_counts(workouts, TODAY, 6)
        st.caption("By month: " + " · ".join(
            f"{m['month']:%b} {m['count'] if m['count'] else 'none recorded'}" for m in months))

    if data["prefs"]:
        with st.expander("Your training preferences"):
            st.markdown("\n".join(f"- {p}" for p in data["prefs"]))


# ---------------------------------------------------------------------- log


def _log(data: dict) -> None:
    workouts, all_sets, all_cardio = data["workouts"], data["sets"], data["cardio"]
    nonce = st.session_state.get("_log_nonce", 0)

    done_with_detail = [w for w in workouts if w.get("status") == "completed"
                        and any(s.get("workout_id") == w["id"] for s in all_sets + all_cardio)]
    if done_with_detail:
        with st.expander("Repeat a previous session", icon=":material/content_copy:"):
            pick = st.selectbox(
                "Copy the exercises from", done_with_detail[:30], key="repeat_pick",
                format_func=lambda w: f"{format_date(parse_date(w['workout_date']))} · {_kind(w)} · "
                + _summary(w, [s for s in all_sets if s["workout_id"] == w["id"]],
                           [c for c in all_cardio if c["workout_id"] == w["id"]])[:60],
            )
            st.caption("The loads and reps are copied as a starting point. Change them to what you actually did.")
            if st.button("Copy into the log below", key="repeat_go"):
                st.session_state["_log_prefill"] = {
                    "kind": pick.get("kind"), "location": pick.get("location"),
                    "sets": [{**r, "id": None, "As written": ""} for r in fitness.sets_to_rows(
                        [s for s in all_sets if s["workout_id"] == pick["id"]])],
                    "cardio": [{**r, "id": None} for r in fitness.cardio_to_rows(
                        [c for c in all_cardio if c["workout_id"] == pick["id"]])],
                }
                st.session_state["_log_nonce"] = nonce + 1
                st.rerun()

    prefill = st.session_state.get("_log_prefill") or {}
    with st.form(f"log_form_{nonce}"):
        st.markdown("**Session**")
        header = _header_fields(f"log{nonce}", {"kind": prefill.get("kind"), "location": prefill.get("location")})
        st.markdown("**Strength sets** · one row per set · add rows with **+**")
        sets_edit = st.data_editor(prefill.get("sets") or _blank_sets(), num_rows="dynamic", hide_index=True,
                                   column_config=SET_COLUMNS, key=f"log_sets_{nonce}")
        st.markdown("**Cardio** (optional)")
        cardio_edit = st.data_editor(prefill.get("cardio") or _blank_cardio(), num_rows="dynamic", hide_index=True,
                                     column_config=CARDIO_COLUMNS, key=f"log_cardio_{nonce}")
        st.caption("Units are kept as you enter them. Choose 'per_side' or 'per_dumbbell' when that is how you counted the weight.")
        if st.form_submit_button("Save workout", type="primary"):
            sets, p1 = fitness.clean_set_rows(_records(sets_edit))
            cardio, p2 = fitness.clean_cardio_rows(_records(cardio_edit))
            if p1 or p2:
                _show_problems(p1 + p2)
            else:
                st.session_state.pop("_log_prefill", None)
                st.session_state["_log_nonce"] = nonce + 1
                _act(lambda: db.log_workout(header, sets, cardio), "Workout saved.")

    ui.section("Past workouts")
    finished = [w for w in workouts if w.get("status") in ("completed", "skipped")]
    if not finished:
        ui.empty_state("No workouts recorded yet", "Your logged sessions will appear here.")
        return
    show_all = st.toggle(f"Show all {len(finished)}", key="fit_show_all") if len(finished) > 12 else True
    for w in finished if show_all else finished[:12]:
        _past_workout(w, [s for s in all_sets if s.get("workout_id") == w["id"]],
                      [c for c in all_cardio if c.get("workout_id") == w["id"]])


def _past_workout(w: dict, sets: list[dict], cardio: list[dict]) -> None:
    wid = w["id"]
    label = f"{format_date(parse_date(w['workout_date']))} · {_kind(w)}"
    if w.get("status") == "skipped":
        label += " · skipped"
    if w.get("location"):
        label += f" · {w['location']}"
    with st.expander(label):
        bits = [x for x in [f"{w['duration_min']} min" if w.get("duration_min") else "",
                            f"effort {float(w['rpe']):g}/10" if w.get("rpe") is not None else "",
                            w.get("notes") or ""] if x]
        if bits:
            st.caption(" · ".join(bits))
        for c in sorted(cardio, key=lambda x: x.get("position") or 0):
            parts = [c["activity"]]
            if c.get("distance_m") is not None:
                parts.append(f"{float(c['distance_m']):g} m")
            if c.get("duration_seconds") is not None:
                parts.append(fitness.format_duration(c["duration_seconds"], c.get("duration_approximate")))
            if c.get("settings_text"):
                parts.append(c["settings_text"])
            st.markdown("- " + html.escape(" · ".join(parts)))
        grouped: dict[str, list] = {}
        for s in sorted(sets, key=lambda x: (x.get("position") or 0, x.get("set_number") or 0)):
            grouped.setdefault(s["exercise_name"], []).append(s)
        for name, items in grouped.items():
            text = ", ".join(f"{fitness.load_label(s)} × {s['reps']}" if s.get("reps") else fitness.load_label(s)
                             for s in items)
            st.markdown(f"- **{html.escape(name)}**: {html.escape(text)}")
        if not sets and not cardio:
            st.caption("No exercise details recorded.")

        if st.toggle("Edit this workout", key=f"wedit_{wid}"):
            with st.form(f"wform_{wid}"):
                header = _header_fields(f"w_{wid}", w)
                set_rows = fitness.sets_to_rows(sets) or _blank_sets(1)
                cardio_rows = fitness.cardio_to_rows(cardio) or _blank_cardio(1)
                sets_edit = st.data_editor(set_rows, num_rows="dynamic", hide_index=True,
                                           column_config=SET_COLUMNS, key=f"wsets_{wid}")
                cardio_edit = st.data_editor(cardio_rows, num_rows="dynamic", hide_index=True,
                                             column_config=CARDIO_COLUMNS, key=f"wcardio_{wid}")
                if st.form_submit_button("Save changes", type="primary"):
                    new_sets, p1 = fitness.clean_set_rows(_records(sets_edit))
                    new_cardio, p2 = fitness.clean_cardio_rows(_records(cardio_edit))
                    if p1 or p2:
                        _show_problems(p1 + p2)
                    else:
                        def save():
                            db.update_workout(wid, header)
                            db.save_workout_details(wid, new_sets, sets, new_cardio, cardio)
                        _act(save, "Workout updated.")
            ok = st.checkbox("Yes, delete this workout and all its sets", key=f"wdel_ok_{wid}")
            if st.button("Delete workout", key=f"wdel_{wid}", disabled=not ok):
                _act(lambda: db.delete_workout(wid), "Workout deleted.")


# ----------------------------------------------------------------- progress


def _progress(data: dict) -> None:
    workouts, sets, cardio = data["workouts"], data["sets"], data["cardio"]
    names = fitness.exercise_names(sets, workouts)
    st.caption(
        "Each exercise and machine is tracked on its own. Loads are never converted "
        "between kg and lb, or between different machines."
    )
    if not names:
        ui.empty_state("No strength sets recorded yet", "Log a workout with sets to see progress here.")
    else:
        name = st.selectbox("Exercise", [n for n, _ in names], key="prog_exercise",
                            format_func=lambda n: f"{n} ({dict(names)[n]} session(s))")
        history = fitness.exercise_history(sets, workouts, name)
        keys = sorted({k for row in history for k in row["top"]}, key=str)
        if keys and any(len([r for r in history if k in r["top"]]) > 0 for k in keys):
            fig = go.Figure()
            for i, key in enumerate(keys):
                rows = [r for r in history if key in r["top"]]
                fig.add_trace(go.Scatter(
                    x=[r["date"] for r in rows], y=[r["top"][key]["load"] for r in rows],
                    mode="lines+markers", name=f"Heaviest set ({fitness.series_label(key)})",
                    line=dict(color=[TEAL, SAGE, GOLD, ROSE][i % 4]),
                    customdata=[" · ".join(r["sets"]) for r in rows],
                    hovertemplate="%{x|%d %b %Y}<br>%{customdata}<extra></extra>",
                ))
            fig.update_layout(height=260, legend=dict(orientation="h", y=-0.2),
                              yaxis=dict(title=None, rangemode="tozero"), **CHART)
            st.plotly_chart(fig, config={"displayModeBar": False}, key="prog_chart")
        st.dataframe([{"Date": format_date(r["date"]), "Sets": " · ".join(r["sets"])} for r in reversed(history)],
                     hide_index=True, key="prog_table")

        ui.section("Personal bests", "Heaviest recorded set for each exercise, per unit.")
        bests = fitness.personal_bests(sets, workouts)
        if bests:
            st.dataframe([{
                "Exercise": b["exercise"], "Measured in": b["series"],
                "Heaviest": f"{b['load']:g}", "Reps": b["reps"] or "", "Date": format_date(b["date"]),
            } for b in bests], hide_index=True, key="pb_table")
        else:
            st.caption("No sets with a recorded load yet.")

    ui.section("Rowing")
    rows = fitness.cardio_log(cardio, workouts, "row")
    if rows:
        st.dataframe([{
            "Date": format_date(r["date"]), "Activity": r["activity"],
            "Distance (m)": f"{float(r['distance_m']):g}" if r.get("distance_m") is not None else "not recorded",
            "Time": fitness.format_duration(r.get("duration_seconds"), r.get("duration_approximate")),
            "Settings": r.get("settings_text") or "",
        } for r in rows], hide_index=True, key="row_table")
    else:
        ui.empty_state("No rowing recorded yet", "Rowing you log appears here.")

    ui.section("Swimming")
    swims = fitness.cardio_log(cardio, workouts, "swim")
    if swims:
        total = sum(float(r["distance_m"]) for r in swims if r.get("distance_m") is not None)
        st.caption(f"{len(swims)} swim(s) recorded" + (f" · {total:g} m in total where distance was recorded" if total else ""))
        st.dataframe([{
            "Date": format_date(r["date"]), "Activity": r["activity"],
            "Distance (m)": f"{float(r['distance_m']):g}" if r.get("distance_m") is not None else "not recorded",
            "Time": fitness.format_duration(r.get("duration_seconds"), r.get("duration_approximate")),
        } for r in swims], hide_index=True, key="swim_table")
    else:
        ui.empty_state("No swimming recorded yet",
                       "Log a cardio row with an activity such as 'Swimming (breaststroke)' and it appears here.")


# ------------------------------------------------------------------- weight


def _weight(data: dict) -> None:
    entries = data["weights"]
    points = fitness.weight_points(entries)
    goal = data["goal"]
    goal_kg = float(goal["target_value"]) if goal else None

    if points:
        first_day, first_kg = points[0]
        last_day, last_kg = points[-1]
        line = f"**{last_kg:.2f} kg** on {format_date(last_day)}"
        if len(points) > 1:
            change = last_kg - first_kg
            line += f" · {change:+.2f} kg since your first record ({format_date(first_day)})"
        st.markdown(line)
        if (TODAY - last_day).days > 7:
            st.caption("This is your last recorded weight, not necessarily today's.")

        avg = fitness.moving_average(points, 14)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[d for d, _ in points], y=[w for _, w in points], mode="markers",
                                 name="Recorded", marker=dict(color=TEAL, size=8),
                                 hovertemplate="%{x|%d %b %Y}: %{y:.2f} kg<extra></extra>"))
        if len(points) > 1:
            fig.add_trace(go.Scatter(x=[d for d, _ in avg], y=[w for _, w in avg], mode="lines",
                                     name="14-day average of recorded entries", line=dict(color=SAGE, width=2),
                                     hovertemplate="%{x|%d %b %Y}: %{y:.2f} kg<extra></extra>"))
        if goal_kg:
            fig.add_hline(y=goal_kg, line_dash="dot", line_color=GOLD,
                          annotation_text=f"Goal {goal_kg:g} kg", annotation_position="bottom left")
        fig.update_layout(height=280, legend=dict(orientation="h", y=-0.2), yaxis=dict(title="kg"), **CHART)
        st.plotly_chart(fig, config={"displayModeBar": False}, key="weight_chart")
    else:
        ui.empty_state("No weight recorded yet", "Add your first entry below.")

    with st.expander("Add a measurement", icon=":material/add:", expanded=not points):
        with st.form("add_weight", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                day = st.date_input("Date", value=TODAY, max_value=TODAY, format="DD/MM/YYYY", key="new_w_date")
                kg = st.number_input("Weight (kg)", min_value=20.0, max_value=399.0, step=0.05,
                                     value=None, format="%.2f", key="new_w_kg")
            with c2:
                waist = st.number_input("Waist (cm, optional)", min_value=31.0, max_value=249.0, step=0.5,
                                        value=None, key="new_w_waist")
                hip = st.number_input("Hip (cm, optional)", min_value=31.0, max_value=249.0, step=0.5,
                                      value=None, key="new_w_hip")
            notes = st.text_input("Notes (optional)", key="new_w_notes")
            if st.form_submit_button("Save", type="primary"):
                _act(lambda: db.add_weight(day, kg, waist, hip, notes), "Measurement saved.")

    with st.expander("Goal weight"):
        with st.form("goal_form"):
            new_goal = st.number_input("Goal weight (kg)", min_value=31.0, max_value=299.0, step=0.5,
                                       value=goal_kg, key="goal_kg")
            if st.form_submit_button("Save goal"):
                _act(lambda: db.set_goal_weight(new_goal), "Goal saved.")

    if entries:
        ui.section("All entries")
        for e in entries:
            eid = e["id"]
            parts = [f"{float(e['weight_kg']):.2f} kg" if e.get("weight_kg") is not None else "",
                     f"waist {float(e['waist_cm']):g} cm" if e.get("waist_cm") is not None else "",
                     f"hip {float(e['hip_cm']):g} cm" if e.get("hip_cm") is not None else ""]
            with st.expander(f"{format_date(parse_date(e['measured_on']))} · " + " · ".join(p for p in parts if p)):
                with st.form(f"wt_{eid}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        day = st.date_input("Date", value=parse_date(e["measured_on"]), max_value=TODAY,
                                            format="DD/MM/YYYY", key=f"wt_date_{eid}")
                        kg = st.number_input("Weight (kg)", min_value=20.0, max_value=399.0, step=0.05, format="%.2f",
                                             value=float(e["weight_kg"]) if e.get("weight_kg") is not None else None,
                                             key=f"wt_kg_{eid}")
                    with c2:
                        waist = st.number_input("Waist (cm)", min_value=31.0, max_value=249.0, step=0.5,
                                                value=float(e["waist_cm"]) if e.get("waist_cm") is not None else None,
                                                key=f"wt_waist_{eid}")
                        hip = st.number_input("Hip (cm)", min_value=31.0, max_value=249.0, step=0.5,
                                              value=float(e["hip_cm"]) if e.get("hip_cm") is not None else None,
                                              key=f"wt_hip_{eid}")
                    notes = st.text_input("Notes", value=e.get("notes") or "", key=f"wt_notes_{eid}")
                    if st.form_submit_button("Save changes"):
                        _act(lambda: db.update_weight(eid, day, kg, waist, hip, notes), "Entry updated.")
                ok = st.checkbox("Yes, delete this entry", key=f"wt_del_ok_{eid}")
                if st.button("Delete entry", key=f"wt_del_{eid}", disabled=not ok):
                    _act(lambda: db.delete_weight(eid), "Entry deleted.")


# --------------------------------------------------------------------- plan


SESSION_LABELS = {k: v["label"] for k, v in fitness.SESSION_TYPES.items()}


def _template_editor(base: dict, data: dict, first_time: bool) -> None:
    """Edit which session falls on which day, and the exercises in each strength session."""
    by_day = {int(d["weekday"]): d for d in base.get("days") or []}
    rows = [{"Day": fitness.WEEKDAYS[i],
             "Session": SESSION_LABELS.get(by_day[i]["session"]) if i in by_day else None,
             "Minutes": by_day[i].get("minutes") if i in by_day else None} for i in range(7)]
    st.caption("Leave a day's session empty for a rest day.")
    days_edit = st.data_editor(rows, hide_index=True, key="tpl_days", column_config={
        "Day": st.column_config.TextColumn(disabled=True, width="small"),
        "Session": st.column_config.SelectboxColumn(options=list(SESSION_LABELS.values())),
        "Minutes": st.column_config.NumberColumn(min_value=1, max_value=600, step=5, width="small"),
    })
    sessions = {k: dict(v) for k, v in (base.get("sessions") or {}).items()}
    for key in ("strength_a", "strength_b"):
        st.markdown(f"**{SESSION_LABELS[key]} exercises**")
        current = (sessions.get(key) or fitness.SESSION_TYPES[key]).get("exercises") or []
        edited = st.data_editor(
            [{"Exercise": e.get("name"), "Sets": e.get("sets"), "Reps": e.get("reps")} for e in current],
            num_rows="dynamic", hide_index=True, key=f"tpl_{key}", column_config={
                "Exercise": st.column_config.TextColumn(help="Use the same name as in your log, so the last load is found."),
                "Sets": st.column_config.NumberColumn(min_value=1, max_value=10, step=1, width="small"),
                "Reps": st.column_config.NumberColumn(min_value=1, max_value=100, step=1, width="small"),
            })
        sessions.setdefault(key, {"cardio": fitness.SESSION_TYPES[key]["cardio"]})
        sessions[key]["exercises"] = [
            {"name": str(r["Exercise"]).strip(), "sets": int(r["Sets"] or 3), "reps": int(r["Reps"]) if r.get("Reps") == r.get("Reps") and r.get("Reps") else None}
            for r in _records(edited) if r.get("Exercise") and str(r["Exercise"]).strip() and r.get("Exercise") == r.get("Exercise")
        ]
    st.caption("Loads are filled in from the last time you recorded each exercise.")

    label_to_key = {v: k for k, v in SESSION_LABELS.items()}
    new_days = []
    for i, r in enumerate(_records(days_edit)):
        label = r.get("Session")
        if label and label == label and label in label_to_key:
            minutes = r.get("Minutes")
            minutes = int(minutes) if minutes and minutes == minutes else fitness.SESSION_TYPES[label_to_key[label]]["minutes"]
            new_days.append({"weekday": i, "session": label_to_key[label], "minutes": minutes})
    template = {"days": new_days, "sessions": {**{k: {"exercises": [dict(e) for e in v["exercises"]],
                                                       "cardio": [dict(c) for c in v["cardio"]]}
                                                   for k, v in fitness.SESSION_TYPES.items()},
                                                **sessions}}
    monday = fitness.week_start(TODAY)
    if first_time:
        if st.button("Use this as my weekly plan", type="primary", key="tpl_use"):
            def start():
                db.save_plan_template(template)
                db.fill_week_from_template(monday)
            _act(start, "Weekly plan saved. This week's sessions are ready to tick.")
    else:
        with st.container(horizontal=True, gap="small"):
            if st.button("Save my weekly plan", type="primary", key="tpl_save"):
                _act(lambda: db.save_plan_template(template),
                     "Weekly plan saved. It applies to the days not planned yet.")
            if st.button("Save and update the rest of this week", key="tpl_replan"):
                def replan():
                    db.save_plan_template(template)
                    db.replan_rest_of_week(monday)
                _act(replan, "Weekly plan saved, and the rest of this week updated.")


def _plan(data: dict) -> None:
    workouts, all_sets, all_cardio = data["workouts"], data["sets"], data["cardio"]
    template = data["template"]

    if not template:
        target = data["targets"].get("workouts")
        suggested = fitness.suggested_template(target)
        latest = fitness.latest_loads(all_sets, workouts)
        with st.container(border=True):
            st.markdown(
                '<div class="aira-card-title">Your weekly plan</div><div class="aira-card-text">'
                + html.escape(
                    f"Suggested from your target of {target:g} workouts a week" if target
                    else "Suggested for 3 workouts a week (set your own target in Settings)")
                + ". Once you use it, each week's sessions appear here by themselves and you just tick them off. "
                "Loads come from the last time you recorded each exercise.</div>",
                unsafe_allow_html=True,
            )
            for day in suggested["days"]:
                spec = fitness.SESSION_TYPES[day["session"]]
                st.markdown(f"**{fitness.WEEKDAYS[day['weekday']]} · {spec['label']}** · about {day['minutes']} min")
                plan_sets, plan_cardio = fitness.session_details(day["session"], suggested, latest)
                lines = [f"{c['activity']}: {c['duration_seconds'] // 60} min" for c in plan_cardio if c.get("duration_seconds")]
                lines += fitness.prescription(plan_sets)
                if lines:
                    st.caption(" · ".join(lines) if len(lines) < 2 else "\n".join(f"- {x}" for x in lines))
            with st.expander("Adjust before using"):
                _template_editor(suggested, data, first_time=True)
            if st.button("Use this plan", type="primary", key="tpl_use_quick"):
                monday = fitness.week_start(TODAY)

                def start():
                    db.save_plan_template(suggested)
                    db.fill_week_from_template(monday)
                _act(start, "Weekly plan saved. This week's sessions are ready to tick.")

    which = st.radio("Week", ["This week", "Next week"], horizontal=True, key="plan_week",
                     label_visibility="collapsed")
    monday = fitness.week_start(TODAY) + timedelta(weeks=1 if which == "Next week" else 0)
    if template and which == "Next week":
        try:
            if db.fill_week_from_template(monday):
                st.rerun()
        except db.DataError as exc:
            st.error(str(exc))

    st.caption("Ticking **Done** records the session as planned. If you lifted different weights or reps, "
               "edit it afterwards in the Log tab.")

    for offset in range(7):
        day = monday + timedelta(days=offset)
        items = [w for w in workouts if parse_date(w.get("workout_date")) == day]
        heading = f"{day:%a} {day.day} {day:%b}" + ("  ·  today" if day == TODAY else "")
        st.markdown(f"**{heading}**")
        if not items:
            st.caption("Rest or free day")
            continue
        for w in items:
            wid = w["id"]
            status = w.get("status")
            title = (w.get("notes") or "").replace(" · from your weekly plan", "") or _kind(w)
            if w.get("duration_min"):
                title += f" · {w['duration_min']} min"
            with st.container(border=True):
                if status == "skipped":
                    st.markdown(f"{ui.badge('Skipped')} {html.escape(title)}", unsafe_allow_html=True)
                    if st.button("Undo skip", key=f"pl_unskip_{wid}"):
                        _act(lambda: db.set_workout_status(wid, "planned"), "Back in the plan.")
                    continue
                done = status == "completed"
                ticked = st.checkbox(f"**{title}**", value=done, key=f"pl_tick_{wid}",
                                     disabled=day > TODAY and not done,
                                     help="Can be ticked on the day." if day > TODAY else None)
                if ticked != done:
                    _act(lambda: db.set_workout_status(wid, "completed" if ticked else "planned", day),
                         "Well done. Recorded." if ticked else "Marked as not done.")
                w_sets = [x for x in all_sets if x.get("workout_id") == wid]
                w_cardio = [x for x in all_cardio if x.get("workout_id") == wid]
                lines = [f"{c['activity']}: {c['duration_seconds'] // 60} min" for c in
                         sorted(w_cardio, key=lambda c: c.get("position") or 0) if c.get("duration_seconds")]
                lines += fitness.prescription(w_sets)
                if lines:
                    st.caption("\n".join(f"- {x}" for x in lines))
                if status == "planned":
                    with st.container(horizontal=True, gap="small"):
                        if st.button("Skip", key=f"pl_skip_{wid}"):
                            _act(lambda: db.set_workout_status(wid, "skipped"), "Skipped. No problem.")
                        if st.button("Remove", key=f"pl_del_{wid}"):
                            _act(lambda: db.delete_workout(wid), "Removed from the plan.")
                    if st.toggle("Move to another day", key=f"pl_move_{wid}"):
                        with st.container(horizontal=True, gap="small"):
                            new_day = st.date_input("New day", value=day, format="DD/MM/YYYY",
                                                    key=f"pl_newday_{wid}", label_visibility="collapsed")
                            if st.button("Move", key=f"pl_moveok_{wid}"):
                                _act(lambda: db.move_workout(wid, new_day, status), "Moved.")

    with st.expander("Add a one-off session", icon=":material/add:"):
        with st.form("plan_add", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                day = st.date_input("Day", value=max(TODAY, monday), format="DD/MM/YYYY", key="plan_day")
                kind = st.selectbox("Session", WORKOUT_KINDS, format_func=WORKOUT_KIND_LABELS.get, key="plan_kind")
            with c2:
                minutes = st.number_input("Target minutes (optional)", min_value=1, max_value=600, step=5,
                                          value=None, key="plan_minutes")
                notes = st.text_input("What you plan to do (optional)", key="plan_notes")
            if st.form_submit_button("Add", type="primary"):
                _act(lambda: db.log_workout({"workout_date": day, "kind": kind, "status": "planned",
                                             "duration_min": minutes, "notes": notes}, [], []),
                     "Added to your plan.")

    if template:
        with st.expander("Change my weekly plan", icon=":material/edit_calendar:"):
            _template_editor(template, data, first_time=False)


# --------------------------------------------------------------------- main


def main() -> None:
    ui.page_header("Fitness Studio", "Consistency, not perfection. Everything here is what you recorded.",
                   eyebrow="Phase 3")
    flash = st.session_state.pop("_flash", None)
    if flash:
        st.toast(flash)
    data = _load()
    overview, log, progress, weight, plan = st.tabs(["Overview", "Log", "Progress", "Weight", "Plan"])
    with overview:
        _overview(data)
    with log:
        _log(data)
    with progress:
        _progress(data)
    with weight:
        _weight(data)
    with plan:
        _plan(data)


main()
