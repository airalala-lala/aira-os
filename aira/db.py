"""All reading and writing of AIRA OS data in Supabase.

Every function here runs as the signed-in user, so Row Level Security in the
database decides what can be seen or changed. Nothing is cached: each page run
reads fresh data, which is how your MacBook and iPhone stay in sync.
"""

from __future__ import annotations

from datetime import date, timedelta

from aira import fitness, literature
from aira.planning import AREAS, PRIORITIES, TIME_CATEGORIES
from aira.supabase_client import get_client
from aira.timeutil import parse_date, today_kl, utc_now_iso

TASK_AREAS = AREAS + ["planner"]  # "planner" = tasks made before version 2.0
WORKOUT_KINDS = ["strength", "rowing", "swimming", "kettlebell", "mixed", "recovery", "other"]
WORKOUT_KIND_LABELS = {
    "strength": "Strength", "rowing": "Rowing", "swimming": "Swimming",
    "kettlebell": "Kettlebell", "mixed": "Mixed", "recovery": "Recovery", "other": "Other",
}

TASK_STATUSES = ["todo", "in_progress", "done"]
STATUS_LABELS = {"todo": "To do", "in_progress": "In progress", "done": "Done"}


class DataError(Exception):
    """A database problem, already translated into plain language."""


def _explain(exc: Exception) -> str:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or exc)
    lowered = message.lower()
    if code == "42501" or "permission denied" in lowered:
        return (
            "The database refused this request (permission denied). This "
            "usually means the SQL migration was not run completely. Re-run "
            "supabase/migrations/0001_foundation.sql in the Supabase SQL Editor."
        )
    if code in {"PGRST205", "42P01"} or "could not find the table" in lowered:
        return (
            "A database table is missing. Run the migration files in "
            "supabase/migrations/ in number order in the Supabase SQL Editor "
            "(0001, 0002, 0003, then 0004). All four are needed."
        )
    if (code == "23505" or "duplicate key" in lowered) and "literature" in lowered:
        return "This source is already in your literature database (same DOI, Scopus ID, or title and year)."
    if code == "23505" or "duplicate key" in lowered:
        return (
            "The database refused a duplicate record. Nothing was overwritten. "
            "Reload the page and check the preview again."
        )
    if "row-level security" in lowered:
        return (
            "The database blocked this change because of its security rules. "
            "Sign out, sign in again, and retry."
        )
    if "jwt" in lowered and "expired" in lowered:
        return "Your session has expired. Sign out and sign in again."
    return (
        "Could not reach the database. Check your internet connection and "
        "that your Supabase project is not paused. "
        f"(Technical detail: {type(exc).__name__}: {message[:200]})"
    )


def _run(query):
    """Execute a Supabase query and return its rows, or raise DataError."""
    try:
        response = query.execute()
    except Exception as exc:
        raise DataError(_explain(exc)) from exc
    return response.data or []


# ----------------------------------------------------------------- profile


def get_profile() -> dict | None:
    rows = _run(get_client().table("profiles").select("*").limit(1))
    return rows[0] if rows else None


def save_profile(user_id: str, display_name: str) -> None:
    payload = {"id": user_id, "display_name": display_name.strip() or None}
    _run(get_client().table("profiles").upsert(payload))


# ------------------------------------------------------------------- tasks


def _sort_key(task: dict):
    due = parse_date(task.get("due_date"))
    # Tasks with a due date first (earliest first), then tasks without one.
    return (due is None, due or date.max, task.get("created_at") or "")


def list_tasks() -> list[dict]:
    rows = _run(get_client().table("tasks").select("*"))
    return sorted(rows, key=_sort_key)


def _clean_task_fields(
    title: str, module: str, due_date: date | None, notes: str, status: str,
    priority: str = "normal",
) -> dict:
    title = (title or "").strip()
    if not title:
        raise DataError("Please give the task a title.")
    if len(title) > 300:
        raise DataError("The title is too long (300 characters maximum).")
    if module not in TASK_AREAS:
        raise DataError("Please choose an area for this task.")
    if status not in TASK_STATUSES:
        raise DataError("Unknown task status.")
    if priority not in PRIORITIES:
        raise DataError("Unknown priority.")
    return {
        "title": title,
        "module": module,
        "due_date": due_date.isoformat() if due_date else None,
        "notes": (notes or "").strip() or None,
        "status": status,
        "priority": priority,
    }


def add_task(
    title: str, module: str, due_date: date | None = None, notes: str = "",
    priority: str = "normal", pin_today: bool = False, meeting_id: str | None = None,
) -> None:
    payload = _clean_task_fields(title, module, due_date, notes, "todo", priority)
    if pin_today:
        payload["top3_date"] = today_kl().isoformat()
    if meeting_id:
        payload["meeting_id"] = meeting_id
    # user_id is filled in by the database itself from the signed-in user.
    _run(get_client().table("tasks").insert(payload))


def update_task(
    task_id: str, title: str, module: str, due_date: date | None, notes: str,
    status: str, priority: str = "normal",
) -> None:
    payload = _clean_task_fields(title, module, due_date, notes, status, priority)
    _run(get_client().table("tasks").update(payload).eq("id", task_id))


def set_task_status(task_id: str, status: str) -> None:
    if status not in TASK_STATUSES:
        raise DataError("Unknown task status.")
    _run(get_client().table("tasks").update({"status": status}).eq("id", task_id))


def pin_task(task_id: str, day: date | None) -> None:
    """Pin a task to a day's Top 3, or unpin it with day=None."""
    value = day.isoformat() if day else None
    _run(get_client().table("tasks").update({"top3_date": value}).eq("id", task_id))


def snooze_tasks(task_ids: list[str], until: date) -> int:
    """Hide tasks from suggestions until a date. Due dates are left untouched."""
    for task_id in task_ids:
        _run(
            get_client().table("tasks")
            .update({"snoozed_until": until.isoformat(), "top3_date": None})
            .eq("id", task_id)
        )
    return len(task_ids)


def delete_task(task_id: str) -> None:
    _run(get_client().table("tasks").delete().eq("id", task_id))


# ---------------------------------------------------------------- settings


def get_setting(module: str, key: str, default=None):
    rows = _run(
        get_client().table("module_settings").select("value")
        .eq("module", module).eq("key", key).limit(1)
    )
    return rows[0]["value"] if rows else default


def set_setting(module: str, key: str, value) -> None:
    table = get_client().table("module_settings")
    rows = _run(table.select("id").eq("module", module).eq("key", key).limit(1))
    if rows:
        _run(get_client().table("module_settings").update({"value": value}).eq("id", rows[0]["id"]))
    else:
        _run(get_client().table("module_settings").insert({"module": module, "key": key, "value": value}))


# -------------------------------------------------------------------- time


def _check_category(category: str) -> None:
    if category not in TIME_CATEGORIES:
        raise DataError("Unknown time category.")


def _check_minutes(minutes) -> int:
    if minutes is None or int(minutes) < 1 or int(minutes) > 1440:
        raise DataError("Minutes must be between 1 and 1440.")
    return int(minutes)


def list_time_entries(since: date) -> list[dict]:
    rows = _run(
        get_client().table("time_entries").select("*").gte("entry_date", since.isoformat())
    )
    return sorted(rows, key=lambda r: (r.get("entry_date") or "", r.get("created_at") or ""), reverse=True)


def running_timer() -> dict | None:
    rows = _run(get_client().table("time_entries").select("*").is_("minutes", "null").limit(1))
    return rows[0] if rows else None


def start_timer(category: str, note: str = "") -> None:
    _check_category(category)
    if running_timer() is not None:
        raise DataError("A timer is already running. Stop it first.")
    _run(get_client().table("time_entries").insert({
        "category": category,
        "entry_date": today_kl().isoformat(),
        "started_at": utc_now_iso(),
        "source": "timer",
        "note": (note or "").strip() or None,
    }))


def stop_timer(entry_id: str, minutes: int) -> None:
    payload = {"minutes": _check_minutes(minutes), "ended_at": utc_now_iso()}
    _run(get_client().table("time_entries").update(payload).eq("id", entry_id))


def add_time_entry(category: str, entry_date: date, minutes: int, note: str = "") -> None:
    _check_category(category)
    if entry_date > today_kl():
        raise DataError("Time cannot be logged for a future date.")
    _run(get_client().table("time_entries").insert({
        "category": category,
        "entry_date": entry_date.isoformat(),
        "minutes": _check_minutes(minutes),
        "source": "manual",
        "note": (note or "").strip() or None,
    }))


def update_time_entry(entry_id: str, category: str, minutes: int, note: str = "") -> None:
    _check_category(category)
    payload = {"category": category, "minutes": _check_minutes(minutes), "note": (note or "").strip() or None}
    _run(get_client().table("time_entries").update(payload).eq("id", entry_id))


def delete_time_entry(entry_id: str) -> None:
    _run(get_client().table("time_entries").delete().eq("id", entry_id))


# ---------------------------------------------------------------- workouts


def list_workouts(since: date) -> list[dict]:
    rows = _run(
        get_client().table("workouts").select("*").gte("workout_date", since.isoformat())
    )
    return sorted(rows, key=lambda r: r.get("workout_date") or "", reverse=True)


def add_workout(
    workout_date: date, kind: str, status: str, duration_min: int | None = None,
    location: str = "", notes: str = "",
) -> None:
    if kind not in WORKOUT_KINDS:
        raise DataError("Unknown workout type.")
    if status not in ("planned", "completed"):
        raise DataError("A workout is either planned or completed.")
    if status == "completed" and workout_date > today_kl():
        raise DataError("A completed workout cannot be in the future.")
    _run(get_client().table("workouts").insert({
        "workout_date": workout_date.isoformat(),
        "kind": kind,
        "status": status,
        "duration_min": int(duration_min) if duration_min else None,
        "location": (location or "").strip() or None,
        "notes": (notes or "").strip() or None,
    }))


def set_workout_status(workout_id: str, status: str, workout_date: date | None = None) -> None:
    if status not in ("planned", "completed", "skipped"):
        raise DataError("Unknown workout status.")
    if status == "completed" and workout_date and workout_date > today_kl():
        raise DataError("A workout planned for a future day can be marked done on that day.")
    _run(get_client().table("workouts").update({"status": status}).eq("id", workout_id))


def delete_workout(workout_id: str) -> None:
    _run(get_client().table("workouts").delete().eq("id", workout_id))


# ----------------------------------------------------------------- fitness


def list_all_workouts() -> list[dict]:
    rows = _run(get_client().table("workouts").select("*"))
    return sorted(rows, key=lambda r: (r.get("workout_date") or "", r.get("created_at") or ""), reverse=True)


def list_sets() -> list[dict]:
    return _run(get_client().table("strength_sets").select("*"))


def list_cardio() -> list[dict]:
    return _run(get_client().table("cardio_entries").select("*"))


def _clean_workout(workout_date: date, kind: str, status: str, duration_min=None,
                   location: str = "", notes: str = "", rpe=None) -> dict:
    if workout_date is None:
        raise DataError("Please choose the date.")
    if kind not in fitness.WORKOUT_KINDS:
        raise DataError("Unknown workout type.")
    if status not in ("planned", "completed", "skipped"):
        raise DataError("Unknown workout status.")
    if status == "completed" and workout_date > today_kl():
        raise DataError("A completed workout cannot be in the future. Choose Planned instead.")
    if duration_min is not None and not 1 <= int(duration_min) <= 600:
        raise DataError("Duration must be between 1 and 600 minutes.")
    if rpe is not None and not 1 <= float(rpe) <= 10:
        raise DataError("Effort (RPE) must be between 1 and 10.")
    return {
        "workout_date": workout_date.isoformat(),
        "kind": kind,
        "status": status,
        "duration_min": int(duration_min) if duration_min else None,
        "location": (location or "").strip() or None,
        "notes": (notes or "").strip() or None,
        "rpe": float(rpe) if rpe is not None else None,
    }


def _set_payload(row: dict) -> dict:
    return {k: row[k] for k in (
        "position", "exercise_name", "set_number", "reps", "load_value",
        "load_unit", "load_basis", "rpe", "notes",
    )}


def _cardio_payload(row: dict) -> dict:
    return {k: row[k] for k in (
        "position", "activity", "distance_m", "duration_seconds",
        "duration_approximate", "settings_text", "notes",
    )}


def log_workout(header: dict, sets: list[dict], cardio: list[dict], import_key: str | None = None) -> str:
    """Save a workout with its sets and cardio entries.
    If any part fails, the whole workout is removed again so nothing half-saved remains."""
    payload = _clean_workout(**header)
    if import_key:
        payload["import_key"] = import_key
    created = _run(get_client().table("workouts").insert(payload))
    if not created:
        raise DataError("The workout could not be saved. Please try again.")
    workout_id = created[0]["id"]
    try:
        if sets:
            _run(get_client().table("strength_sets").insert(
                [{**_set_payload(r), "workout_id": workout_id} for r in sets]))
        if cardio:
            _run(get_client().table("cardio_entries").insert(
                [{**_cardio_payload(r), "workout_id": workout_id} for r in cardio]))
    except DataError:
        try:
            delete_workout(workout_id)  # undo the half-saved workout
        except DataError:
            pass
        raise
    return workout_id


def update_workout(workout_id: str, header: dict) -> None:
    _run(get_client().table("workouts").update(_clean_workout(**header)).eq("id", workout_id))


def move_workout(workout_id: str, new_date: date, status: str) -> None:
    if new_date is None:
        raise DataError("Please choose the new date.")
    if status == "completed" and new_date > today_kl():
        raise DataError("A completed workout cannot be moved into the future.")
    _run(get_client().table("workouts").update({"workout_date": new_date.isoformat()}).eq("id", workout_id))


def save_workout_details(workout_id: str, sets: list[dict], original_sets: list[dict],
                         cardio: list[dict], original_cardio: list[dict]) -> None:
    """Apply edits to a workout's sets and cardio: update changed rows, add new
    rows, delete removed rows. Imported rows keep their import key."""
    for table, rows, original, shape in (
        ("strength_sets", sets, original_sets, _set_payload),
        ("cardio_entries", cardio, original_cardio, _cardio_payload),
    ):
        inserts, updates, deletes = fitness.diff_rows(rows, original)
        for row in updates:
            _run(get_client().table(table).update(shape(row)).eq("id", row["id"]))
        if inserts:
            _run(get_client().table(table).insert([{**shape(r), "workout_id": workout_id} for r in inserts]))
        for row_id in deletes:
            _run(get_client().table(table).delete().eq("id", row_id))


# ------------------------------------------------------------- weekly plan


def get_plan_template() -> dict | None:
    return get_setting("fitness", "weekly_template")


def save_plan_template(template: dict) -> None:
    days = template.get("days") or []
    seen = set()
    for day in days:
        if day.get("session") not in fitness.SESSION_TYPES:
            raise DataError("Unknown session type in the weekly plan.")
        if not 0 <= int(day.get("weekday", -1)) <= 6:
            raise DataError("Unknown day in the weekly plan.")
        if day["weekday"] in seen:
            raise DataError("Each day can hold one planned session. Please remove the duplicate day.")
        seen.add(day["weekday"])
        if day.get("minutes") is not None and not 1 <= int(day["minutes"]) <= 600:
            raise DataError("Minutes must be between 1 and 600.")
    set_setting("fitness", "weekly_template", template)


def _handled_plan_keys() -> list[str]:
    return list(get_setting("fitness", "plan_keys_added", []) or [])


def fill_week_from_template(monday: date, workouts: list[dict] | None = None,
                            sets: list[dict] | None = None) -> int:
    """Add this week's planned sessions from the weekly template (today onward).
    A session that was added once is never added again, even if you removed it."""
    template = get_plan_template()
    if not template:
        return 0
    workouts = list_all_workouts() if workouts is None else workouts
    sets = list_sets() if sets is None else sets
    handled = _handled_plan_keys()
    todo = [x for x in fitness.sessions_to_add(template, monday, today_kl(), workouts)
            if x["key"] not in handled]
    if not todo:
        return 0
    latest = fitness.latest_loads(sets, workouts)
    for item in todo:
        spec = fitness.SESSION_TYPES[item["session"]]
        plan_sets, plan_cardio = fitness.session_details(item["session"], template, latest)
        header = {"workout_date": item["date"], "kind": spec["kind"], "status": "planned",
                  "duration_min": item.get("minutes") or spec["minutes"],
                  "notes": spec["label"] + " · from your weekly plan"}
        try:
            log_workout(header, plan_sets, plan_cardio, import_key=item["key"])
        except DataError:
            # Already added from another device at the same moment: nothing to do.
            pass
        handled.append(item["key"])
    cutoff = (monday - timedelta(weeks=10)).isoformat()
    set_setting("fitness", "plan_keys_added", [k for k in handled if k.split(":")[1] >= cutoff])
    return len(todo)


def replan_rest_of_week(monday: date) -> int:
    """Remove planned (not done or skipped) sessions from your weekly plan for
    today onward in this week, then add them again from the current template."""
    today = today_kl()
    workouts = list_all_workouts()
    prefix = f"plan:{monday.isoformat()}:"
    removable = [w for w in workouts if (w.get("import_key") or "").startswith(prefix)
                 and w.get("status") == "planned" and (parse_date(w.get("workout_date")) or today) >= today]
    for w in removable:
        delete_workout(w["id"])
    keys = {w["import_key"] for w in removable}
    future_keys = {fitness.plan_key(monday, d) for d in range(7) if monday + timedelta(days=d) >= today}
    set_setting("fitness", "plan_keys_added",
                [k for k in _handled_plan_keys() if k not in keys and k not in future_keys])
    return fill_week_from_template(monday)


def list_weights() -> list[dict]:
    rows = _run(get_client().table("body_measurements").select("*"))
    return sorted(rows, key=lambda r: r.get("measured_on") or "", reverse=True)


def _clean_weight(measured_on: date, weight_kg, waist_cm=None, hip_cm=None, notes: str = "") -> dict:
    if measured_on is None:
        raise DataError("Please choose the date.")
    if measured_on > today_kl():
        raise DataError("A measurement cannot be dated in the future.")
    if weight_kg is None and waist_cm is None and hip_cm is None:
        raise DataError("Please enter at least one measurement.")
    if weight_kg is not None and not 20 < float(weight_kg) < 400:
        raise DataError("Please check the weight.")
    for label, value in (("waist", waist_cm), ("hip", hip_cm)):
        if value is not None and not 30 < float(value) < 250:
            raise DataError(f"Please check the {label} measurement.")
    return {
        "measured_on": measured_on.isoformat(),
        "weight_kg": round(float(weight_kg), 2) if weight_kg is not None else None,
        "waist_cm": round(float(waist_cm), 1) if waist_cm is not None else None,
        "hip_cm": round(float(hip_cm), 1) if hip_cm is not None else None,
        "notes": (notes or "").strip() or None,
    }


def add_weight(measured_on: date, weight_kg, waist_cm=None, hip_cm=None, notes: str = "") -> None:
    _run(get_client().table("body_measurements").insert(
        _clean_weight(measured_on, weight_kg, waist_cm, hip_cm, notes)))


def update_weight(entry_id: str, measured_on: date, weight_kg, waist_cm=None, hip_cm=None, notes: str = "") -> None:
    _run(get_client().table("body_measurements").update(
        _clean_weight(measured_on, weight_kg, waist_cm, hip_cm, notes)).eq("id", entry_id))


def delete_weight(entry_id: str) -> None:
    _run(get_client().table("body_measurements").delete().eq("id", entry_id))


def goal_weight() -> dict | None:
    """The fitness goal measured in kg (for example 'Reach goal weight: 50 kg'), if recorded."""
    rows = _run(get_client().table("goals").select("*").eq("module", "fitness").eq("unit", "kg"))
    rows = [r for r in rows if r.get("target_value") is not None and r.get("status") == "active"]
    return rows[0] if rows else None


def set_goal_weight(value) -> None:
    if value is None or not 30 < float(value) < 300:
        raise DataError("Please check the goal weight.")
    current = goal_weight()
    if current:
        _run(get_client().table("goals").update({"target_value": float(value)}).eq("id", current["id"]))
    else:
        _run(get_client().table("goals").insert({
            "module": "fitness", "title": "Reach goal weight", "status": "active",
            "target_value": float(value), "unit": "kg",
        }))


# --------------------------------------------------------------- literature

LITERATURE_TEXT_FIELDS = [
    "authors", "publication_date", "url", "journal", "research_country", "methodology",
    "theoretical_framework", "key_findings", "conclusions", "limitations", "relevance",
    "gap_contribution", "critical_notes", "tags", "citation", "abstract",
]


def list_sources() -> list[dict]:
    rows = _run(get_client().table("literature_sources").select("*"))
    return sorted(rows, key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))


def sources_read_since(since: date) -> list[dict]:
    return _run(
        get_client().table("literature_sources").select("id,date_read")
        .gte("date_read", since.isoformat())
    )


def _clean_source(fields: dict) -> dict:
    title = (fields.get("title") or "").strip()
    if not title:
        raise DataError("Please give the source a title.")
    year = fields.get("year")
    if year is not None and not 1800 <= int(year) <= today_kl().year + 1:
        raise DataError("Please check the year.")
    status = fields.get("reading_status") or "not_recorded"
    if status not in literature.READING_STATUSES:
        raise DataError("Unknown reading status.")
    source_type = fields.get("source_type") or None
    if source_type is not None and source_type not in literature.SOURCE_TYPES:
        raise DataError("Unknown source type.")
    date_read = fields.get("date_read")
    if date_read and date_read > today_kl():
        raise DataError("The date read cannot be in the future.")
    doi = literature.normalize_doi(fields.get("doi"))
    if fields.get("doi") and not doi:
        raise DataError("That DOI does not look right. It should start with 10.")
    payload = {
        "title": title,
        "year": int(year) if year is not None else None,
        "doi": doi,
        "source_type": source_type,
        "reading_status": status,
        "date_read": date_read.isoformat() if date_read else None,
    }
    for name in LITERATURE_TEXT_FIELDS:
        value = fields.get(name)
        payload[name] = (str(value).strip() or None) if value is not None else None
    if doi and not payload["url"]:
        payload["url"] = f"https://doi.org/{doi}"
    return payload


def find_duplicate_source(payload: dict, sources: list[dict], ignore_id: str | None = None):
    """Return an existing source with the same DOI, or the same title and year."""
    title = literature.normalize_title(payload.get("title"))
    for source in sources:
        if source.get("id") == ignore_id:
            continue
        if payload.get("doi") and literature.normalize_doi(source.get("doi")) == payload["doi"]:
            return source
        if (literature.normalize_title(source.get("title")) == title
                and (source.get("year") or None) == (payload.get("year") or None)):
            return source
    return None


def add_source(fields: dict, existing: list[dict]) -> None:
    payload = _clean_source(fields)
    duplicate = find_duplicate_source(payload, existing)
    if duplicate:
        raise DataError(f"This looks like a source you already have: \"{duplicate['title']}\".")
    payload["import_key"] = literature.source_key(payload["doi"], None, payload["title"], payload["year"])
    _run(get_client().table("literature_sources").insert(payload))


def update_source(source_id: str, fields: dict, existing: list[dict]) -> None:
    payload = _clean_source(fields)
    duplicate = find_duplicate_source(payload, existing, ignore_id=source_id)
    if duplicate:
        raise DataError(f"Another source already has this DOI or title and year: \"{duplicate['title']}\".")
    _run(get_client().table("literature_sources").update(payload).eq("id", source_id))


def delete_source(source_id: str) -> None:
    _run(get_client().table("literature_sources").delete().eq("id", source_id))


# ------------------------------------------------------------- supervision


def list_meetings() -> list[dict]:
    rows = _run(get_client().table("supervisor_meetings").select("*"))
    return sorted(rows, key=lambda r: r.get("meeting_date") or "", reverse=True)


def _clean_meeting(meeting_date: date, title: str, feedback: str, decisions: str, notes: str) -> dict:
    if meeting_date is None:
        raise DataError("Please enter the meeting date.")
    if meeting_date > today_kl():
        raise DataError("A meeting record cannot be in the future. Add a task for an upcoming meeting instead.")
    clean = lambda v: (v or "").strip() or None
    return {
        "meeting_date": meeting_date.isoformat(), "title": clean(title),
        "feedback": clean(feedback), "decisions": clean(decisions), "notes": clean(notes),
    }


def add_meeting(meeting_date: date, title: str, feedback: str, decisions: str, notes: str) -> None:
    _run(get_client().table("supervisor_meetings").insert(
        _clean_meeting(meeting_date, title, feedback, decisions, notes)))


def update_meeting(meeting_id: str, meeting_date: date, title: str, feedback: str, decisions: str, notes: str) -> None:
    _run(get_client().table("supervisor_meetings").update(
        _clean_meeting(meeting_date, title, feedback, decisions, notes)).eq("id", meeting_id))


def delete_meeting(meeting_id: str) -> None:
    _run(get_client().table("supervisor_meetings").delete().eq("id", meeting_id))


def list_feedback() -> list[dict]:
    rows = _run(get_client().table("supervisor_feedback").select("*"))
    return sorted(rows, key=lambda r: (r.get("received_period") or "", r.get("import_key") or "", r.get("created_at") or ""))


def set_feedback_status(feedback_id: str, status: str, notes: str = "") -> None:
    if status not in ("open", "addressed"):
        raise DataError("Unknown status.")
    _run(get_client().table("supervisor_feedback").update(
        {"status": status, "notes": (notes or "").strip() or None}).eq("id", feedback_id))


def list_research_phases() -> list[dict]:
    rows = _run(get_client().table("research_phases").select("*"))
    return sorted(rows, key=lambda r: r.get("position") or 0)


# --------------------------------------------------------------- milestones

MILESTONE_STATUSES = ["planned", "in_progress", "completed"]
MILESTONE_LABELS = {"planned": "Planned", "in_progress": "In progress", "completed": "Completed"}


def list_milestones() -> list[dict]:
    rows = _run(get_client().table("thesis_milestones").select("*"))
    return sorted(rows, key=lambda r: (r.get("position") or 0, r.get("created_at") or ""))


def _clean_milestone(title, planned, status, actual, notes) -> dict:
    title = (title or "").strip()
    if not title:
        raise DataError("Please give the milestone a name.")
    if status not in MILESTONE_STATUSES:
        raise DataError("Unknown milestone status.")
    if status == "completed" and actual is None:
        raise DataError("Please enter the date it was actually completed.")
    if actual is not None and actual > today_kl():
        raise DataError("The actual completion date cannot be in the future.")
    return {
        "title": title,
        "due_date": planned.isoformat() if planned else None,
        "status": status,
        "completed_on": actual.isoformat() if (actual and status == "completed") else None,
        "notes": (notes or "").strip() or None,
    }


def add_milestone(title, planned, position: int) -> None:
    payload = _clean_milestone(title, planned, "planned", None, "")
    payload["position"] = position
    _run(get_client().table("thesis_milestones").insert(payload))


def update_milestone(milestone_id, title, planned, status, actual, notes) -> None:
    _run(get_client().table("thesis_milestones").update(
        _clean_milestone(title, planned, status, actual, notes)).eq("id", milestone_id))


def delete_milestone(milestone_id: str) -> None:
    _run(get_client().table("thesis_milestones").delete().eq("id", milestone_id))


# ------------------------------------------------------------------ import

HISTORY_TABLES = [
    "module_settings", "goals", "research_phases", "supervisor_feedback",
    "thesis_milestones", "opportunities", "body_measurements", "workouts",
    "strength_sets", "cardio_entries", "literature_sources", "supervisor_meetings",
]


def existing_import_keys(table: str) -> set:
    """The import_key of every row already stored in a table."""
    rows = _run(get_client().table(table).select("import_key"))
    return {row["import_key"] for row in rows if row.get("import_key")}


def existing_setting_keys() -> set:
    rows = _run(get_client().table("module_settings").select("module,key"))
    return {(row["module"], row["key"]) for row in rows}


def workout_ids_by_import_key() -> dict:
    rows = _run(get_client().table("workouts").select("id,import_key"))
    return {row["import_key"]: row["id"] for row in rows if row.get("import_key")}


def insert_rows(table: str, rows: list[dict]) -> int:
    """Insert new rows only. This never updates or replaces an existing row."""
    for start in range(0, len(rows), 200):
        _run(get_client().table(table).insert(rows[start : start + 200]))
    return len(rows)


def count_rows(table: str) -> int:
    return len(_run(get_client().table(table).select("id")))


# ------------------------------------------------------------------ backup


def export_everything() -> dict:
    """Return every record that currently exists, for a downloadable backup."""
    backup = {
        "profiles": _run(get_client().table("profiles").select("*")),
        "tasks": _run(get_client().table("tasks").select("*")),
    }
    for table in HISTORY_TABLES + ["time_entries"]:
        try:
            backup[table] = _run(get_client().table(table).select("*"))
        except DataError:
            # That migration has not been run yet, so this table does not exist.
            continue
    return backup
