"""Fitness logic: cleaning logged sets, weekly consistency, weight trend and
personal bests. Pure Python (no Streamlit, no database), so it can be tested.

Rules followed everywhere here:
  * loads are never converted between kg and lb, or between machines;
  * per-side and per-dumbbell loads are kept apart from total loads;
  * only recorded entries are used: nothing is estimated or filled in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from aira.timeutil import parse_date

LOAD_UNITS = ["kg", "lb", "machine_units"]
LOAD_UNIT_LABELS = {"kg": "kg", "lb": "lb", "machine_units": "machine units"}
LOAD_BASES = ["total", "per_side", "per_dumbbell"]
LOAD_BASIS_LABELS = {"total": "total", "per_side": "per side", "per_dumbbell": "per dumbbell"}
WORKOUT_KINDS = ["strength", "rowing", "swimming", "kettlebell", "mixed", "recovery", "other"]
WORKOUT_KIND_LABELS = {
    "strength": "Strength", "rowing": "Rowing", "swimming": "Swimming",
    "kettlebell": "Kettlebell", "mixed": "Mixed", "recovery": "Recovery", "other": "Other",
}


def _blank(value) -> bool:
    """True for None, empty text, NaN or NaT (what an empty table cell can hold)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    try:
        return value != value  # NaN and NaT are not equal to themselves
    except Exception:
        return False


def _number(value, kind=float):
    if _blank(value):
        return None
    number = float(value)
    if kind is int:
        if number != int(number):
            raise ValueError("must be a whole number")
        return int(number)
    return number


def load_label(row: dict) -> str:
    """'50 lb', '20 kg per side', '9–10 kg' (as written), or 'bodyweight / not recorded'."""
    if row.get("load_value") is not None:
        value = float(row["load_value"])
        text = f"{value:g} {LOAD_UNIT_LABELS.get(row.get('load_unit'), row.get('load_unit') or '')}".strip()
        if row.get("load_basis") in ("per_side", "per_dumbbell"):
            text += " " + LOAD_BASIS_LABELS[row["load_basis"]]
        return text
    if row.get("load_text"):
        return row["load_text"]
    return "no load recorded"


# ------------------------------------------------------------ logged rows


def clean_set_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Turn table rows from the logger into strength_sets rows.

    Empty rows are ignored. Exercises keep the order they were entered in;
    set numbers are filled in by order within each exercise when left blank.
    """
    clean, problems, order, counters = [], [], {}, {}
    for number, raw in enumerate(rows, start=1):
        name = "" if _blank(raw.get("Exercise")) else str(raw.get("Exercise")).strip()
        # Unit and basis alone do not count: new rows start with a default unit.
        values = [raw.get(k) for k in ("Set", "Reps", "Load", "RPE", "Notes")]
        if not name and all(_blank(v) for v in values):
            continue
        where = f"Exercise row {number}"
        if not name:
            problems.append(f"{where}: please name the exercise")
            continue
        try:
            set_no = _number(raw.get("Set"), int)
            reps = _number(raw.get("Reps"), int)
            load = _number(raw.get("Load"))
            rpe = _number(raw.get("RPE"))
        except (TypeError, ValueError) as exc:
            problems.append(f"{where} ({name}): {exc}")
            continue
        unit = None if _blank(raw.get("Unit")) else str(raw.get("Unit"))
        basis = None if _blank(raw.get("Basis")) else str(raw.get("Basis"))
        if reps is not None and reps <= 0:
            problems.append(f"{where} ({name}): reps must be above zero")
            continue
        if load is not None and load < 0:
            problems.append(f"{where} ({name}): load cannot be negative")
            continue
        if load is not None and unit not in LOAD_UNITS:
            problems.append(f"{where} ({name}): choose a unit (kg, lb or machine units) for the load")
            continue
        if unit is not None and unit not in LOAD_UNITS:
            problems.append(f"{where} ({name}): unknown unit")
            continue
        if basis is not None and basis not in LOAD_BASES:
            problems.append(f"{where} ({name}): unknown basis")
            continue
        if rpe is not None and not 1 <= rpe <= 10:
            problems.append(f"{where} ({name}): effort (RPE) must be between 1 and 10")
            continue
        key = name.lower()
        if key not in order:
            order[key] = len(order) + 1
        counters[key] = counters.get(key, 0) + 1
        clean.append({
            "id": raw.get("id") if not _blank(raw.get("id")) else None,
            "position": order[key],
            "exercise_name": name,
            "set_number": set_no if set_no is not None else counters[key],
            "reps": reps,
            "load_value": load,
            "load_unit": unit if load is not None or unit else None,
            "load_basis": basis,
            "rpe": rpe,
            "notes": None if _blank(raw.get("Notes")) else str(raw.get("Notes")).strip(),
        })
    return clean, problems


def clean_cardio_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Turn cardio table rows into cardio_entries rows. Minutes become seconds."""
    clean, problems = [], []
    for number, raw in enumerate(rows, start=1):
        activity = "" if _blank(raw.get("Activity")) else str(raw.get("Activity")).strip()
        values = [raw.get(k) for k in ("Distance (m)", "Minutes", "Settings", "Notes")]
        if not activity and all(_blank(v) for v in values):
            continue
        where = f"Cardio row {number}"
        if not activity:
            problems.append(f"{where}: please name the activity (for example Rowing)")
            continue
        try:
            distance = _number(raw.get("Distance (m)"))
            minutes = _number(raw.get("Minutes"))
        except (TypeError, ValueError) as exc:
            problems.append(f"{where} ({activity}): {exc}")
            continue
        if (distance is not None and distance < 0) or (minutes is not None and minutes < 0):
            problems.append(f"{where} ({activity}): values cannot be negative")
            continue
        clean.append({
            "id": raw.get("id") if not _blank(raw.get("id")) else None,
            "position": number,
            "activity": activity,
            "distance_m": distance,
            "duration_seconds": round(minutes * 60) if minutes is not None else None,
            "duration_approximate": bool(raw.get("Approx.")) if not _blank(raw.get("Approx.")) else False,
            "settings_text": None if _blank(raw.get("Settings")) else str(raw.get("Settings")).strip(),
            "notes": None if _blank(raw.get("Notes")) else str(raw.get("Notes")).strip(),
        })
    return clean, problems


def sets_to_rows(sets: list[dict]) -> list[dict]:
    """Stored sets -> rows for the logger table (used for editing and 'repeat')."""
    ordered = sorted(sets, key=lambda s: (s.get("position") or 0, s.get("set_number") or 0))
    return [{
        "id": s.get("id"),
        "Exercise": s.get("exercise_name"),
        "Set": s.get("set_number"),
        "Reps": s.get("reps"),
        "Load": float(s["load_value"]) if s.get("load_value") is not None else None,
        "Unit": s.get("load_unit"),
        "Basis": s.get("load_basis"),
        "RPE": float(s["rpe"]) if s.get("rpe") is not None else None,
        "As written": s.get("load_text") or "",
        "Notes": s.get("notes") or "",
    } for s in ordered]


def cardio_to_rows(entries: list[dict]) -> list[dict]:
    ordered = sorted(entries, key=lambda c: c.get("position") or 0)
    return [{
        "id": c.get("id"),
        "Activity": c.get("activity"),
        "Distance (m)": float(c["distance_m"]) if c.get("distance_m") is not None else None,
        "Minutes": round(c["duration_seconds"] / 60, 2) if c.get("duration_seconds") is not None else None,
        "Approx.": bool(c.get("duration_approximate")),
        "Settings": c.get("settings_text") or "",
        "Notes": c.get("notes") or "",
    } for c in ordered]


def diff_rows(clean: list[dict], original: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Split edited rows into (to_insert, to_update, ids_to_delete)."""
    original_ids = {r["id"] for r in original if r.get("id")}
    kept = {r["id"] for r in clean if r.get("id") in original_ids}
    inserts = [{k: v for k, v in r.items() if k != "id"} for r in clean if r.get("id") not in original_ids]
    updates = [r for r in clean if r.get("id") in original_ids]
    deletes = sorted(original_ids - kept)
    return inserts, updates, deletes


# ------------------------------------------------------------ consistency


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_counts(workouts: list[dict], today: date, weeks: int = 12) -> list[dict]:
    """Completed workouts per week (Monday start) for the last N weeks.
    'count' is None for a week with no completed workout recorded."""
    current = week_start(today)
    starts = [current - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    counts = {s: 0 for s in starts}
    for w in workouts:
        day = parse_date(w.get("workout_date"))
        if w.get("status") == "completed" and day and week_start(day) in counts:
            counts[week_start(day)] += 1
    return [{"week": s, "count": counts[s] or None} for s in starts]


def monthly_counts(workouts: list[dict], today: date, months: int = 6) -> list[dict]:
    keys = []
    year, month = today.year, today.month
    for _ in range(months):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    keys.reverse()
    counts = {k: 0 for k in keys}
    for w in workouts:
        day = parse_date(w.get("workout_date"))
        if w.get("status") == "completed" and day and (day.year, day.month) in counts:
            counts[(day.year, day.month)] += 1
    return [{"month": date(y, m, 1), "count": counts[(y, m)] or None} for y, m in keys]


def last_completed(workouts: list[dict], today: date) -> date | None:
    days = [parse_date(w.get("workout_date")) for w in workouts if w.get("status") == "completed"]
    days = [d for d in days if d and d <= today]
    return max(days) if days else None


# ----------------------------------------------------------------- weight


def weight_points(entries: list[dict]) -> list[tuple[date, float]]:
    points = []
    for e in entries:
        day = parse_date(e.get("measured_on"))
        if day and e.get("weight_kg") is not None:
            points.append((day, float(e["weight_kg"])))
    return sorted(points)


def moving_average(points: list[tuple[date, float]], window_days: int = 14) -> list[tuple[date, float]]:
    """For each recorded day, the mean of the entries in the preceding window
    (including that day). Uses recorded entries only; no gaps are filled."""
    result = []
    for day, _ in points:
        window = [w for d, w in points if day - timedelta(days=window_days - 1) <= d <= day]
        result.append((day, round(sum(window) / len(window), 2)))
    return result


# --------------------------------------------------------------- progress


def _workout_dates(workouts: list[dict]) -> dict:
    return {w["id"]: parse_date(w.get("workout_date")) for w in workouts
            if w.get("status") == "completed" and w.get("id")}


def exercise_names(sets: list[dict], workouts: list[dict]) -> list[tuple[str, int]]:
    """(exercise name, number of sessions) for exercises in completed workouts."""
    dates = _workout_dates(workouts)
    sessions: dict[str, set] = {}
    for s in sets:
        if s.get("workout_id") in dates:
            sessions.setdefault(s["exercise_name"], set()).add(s["workout_id"])
    return sorted(((n, len(ids)) for n, ids in sessions.items()), key=lambda x: (-x[1], x[0].lower()))


def series_key(s: dict) -> tuple:
    return (s.get("load_unit"), s.get("load_basis") or "total")


def series_label(key: tuple) -> str:
    unit, basis = key
    text = LOAD_UNIT_LABELS.get(unit, unit or "")
    if basis in ("per_side", "per_dumbbell"):
        text += " " + LOAD_BASIS_LABELS[basis]
    return text


def exercise_history(sets: list[dict], workouts: list[dict], name: str) -> list[dict]:
    """One row per session for an exercise: date, the sets as written, and the
    heaviest recorded load per unit and basis (never converted)."""
    dates = _workout_dates(workouts)
    by_session: dict[str, list[dict]] = {}
    for s in sets:
        if s.get("exercise_name") == name and s.get("workout_id") in dates:
            by_session.setdefault(s["workout_id"], []).append(s)
    rows = []
    for wid, items in by_session.items():
        items.sort(key=lambda s: s.get("set_number") or 0)
        top = {}
        for s in items:
            if s.get("load_value") is None:
                continue
            key = series_key(s)
            if key not in top or float(s["load_value"]) > top[key]["load"]:
                top[key] = {"load": float(s["load_value"]), "reps": s.get("reps")}
        rows.append({
            "date": dates[wid],
            "sets": [f"{load_label(s)} × {s['reps']}" if s.get("reps") else load_label(s) for s in items],
            "top": top,
        })
    return sorted(rows, key=lambda r: r["date"])


def personal_bests(sets: list[dict], workouts: list[dict]) -> list[dict]:
    """Heaviest recorded load for each exercise, per unit and basis.
    Ties go to the set with more reps, then the earlier date."""
    dates = _workout_dates(workouts)
    best: dict[tuple, dict] = {}
    for s in sets:
        if s.get("workout_id") not in dates or s.get("load_value") is None:
            continue
        key = (s["exercise_name"],) + series_key(s)
        candidate = (float(s["load_value"]), s.get("reps") or 0)
        current = best.get(key)
        if current is None or candidate > (current["load"], current["reps"] or 0) or (
            candidate == (current["load"], current["reps"] or 0) and dates[s["workout_id"]] < current["date"]
        ):
            best[key] = {
                "exercise": s["exercise_name"],
                "series": series_label(series_key(s)),
                "load": float(s["load_value"]),
                "reps": s.get("reps"),
                "date": dates[s["workout_id"]],
            }
    return sorted(best.values(), key=lambda b: (b["exercise"].lower(), b["series"]))


def cardio_log(entries: list[dict], workouts: list[dict], keyword: str) -> list[dict]:
    """Completed cardio entries whose activity contains a word (e.g. 'row', 'swim')."""
    dates = _workout_dates(workouts)
    rows = [
        {**c, "date": dates[c["workout_id"]]}
        for c in entries
        if c.get("workout_id") in dates and keyword.lower() in (c.get("activity") or "").lower()
    ]
    return sorted(rows, key=lambda r: r["date"], reverse=True)


def format_duration(seconds, approximate: bool = False) -> str:
    if seconds is None:
        return "not recorded"
    minutes, secs = divmod(int(seconds), 60)
    text = f"{minutes}:{secs:02d}"
    return ("about " + text) if approximate else text


def to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_date(value)
