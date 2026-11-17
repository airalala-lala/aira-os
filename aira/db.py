"""All reading and writing of AIRA OS data in Supabase.

Every function here runs as the signed-in user, so Row Level Security in the
database decides what can be seen or changed. Nothing is cached: each page run
reads fresh data, which is how your MacBook and iPhone stay in sync.
"""

from __future__ import annotations

from datetime import date

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
    priority: str = "normal", pin_today: bool = False,
) -> None:
    payload = _clean_task_fields(title, module, due_date, notes, "todo", priority)
    if pin_today:
        payload["top3_date"] = today_kl().isoformat()
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


def set_workout_status(workout_id: str, status: str) -> None:
    if status not in ("planned", "completed", "skipped"):
        raise DataError("Unknown workout status.")
    _run(get_client().table("workouts").update({"status": status}).eq("id", workout_id))


def delete_workout(workout_id: str) -> None:
    _run(get_client().table("workouts").delete().eq("id", workout_id))


# ------------------------------------------------------------------ import

HISTORY_TABLES = [
    "module_settings", "goals", "research_phases", "supervisor_feedback",
    "thesis_milestones", "opportunities", "body_measurements", "workouts",
    "strength_sets", "cardio_entries",
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
