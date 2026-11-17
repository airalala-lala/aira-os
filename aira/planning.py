"""The thinking behind the home screen. Pure Python: no Streamlit, no database.

Everything here works only from records that already exist. Nothing is
estimated or invented: when there is no record, the result says "missing".
"""

from __future__ import annotations

from datetime import date, timedelta

from aira.timeutil import parse_date, parse_timestamp

# Life areas a task or a block of time can belong to.
AREAS = ["phd", "fitness", "family", "business", "opportunities", "creator", "personal"]
AREA_LABELS = {
    "phd": "PhD",
    "fitness": "Fitness",
    "family": "Family",
    "business": "Business",
    "opportunities": "Opportunities",
    "creator": "Creator Lab",
    "personal": "Personal",
    "planner": "Personal",  # older tasks created before version 2.0
    "other": "Other",
}
TIME_CATEGORIES = ["phd", "fitness", "family", "business", "opportunities", "creator", "other"]
PRIORITIES = ["high", "normal", "low"]
PRIORITY_LABELS = {"high": "High", "normal": "Normal", "low": "Low"}

PROTECTED_AREAS = {"phd", "fitness"}          # these come first
ESSENTIAL_AREAS = {"phd", "fitness", "family"}  # never postponed by Restart
RESTART_AFTER_DAYS = 3
LONG_TIMER_MINUTES = 180

# Short movement options offered in Restart mode. They are suggestions only.
SHORT_EXERCISE_OPTIONS = [
    "10 minutes of easy rowing",
    "A 15-minute walk",
    "A short kettlebell set at home",
    "20 minutes of easy breaststroke",
]


def week_bounds(today: date) -> tuple[date, date]:
    """Monday and Sunday of the week containing 'today'."""
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def is_open(task: dict) -> bool:
    return task.get("status") != "done"


def is_snoozed(task: dict, today: date) -> bool:
    until = parse_date(task.get("snoozed_until"))
    return until is not None and until > today


def is_pinned_today(task: dict, today: date) -> bool:
    return parse_date(task.get("top3_date")) == today


def _score(task: dict, today: date) -> tuple[int, str]:
    """How strongly a task is suggested, and the main reason in plain words."""
    score, reasons = 0, []
    area = task.get("module")
    priority = task.get("priority") or "normal"
    due = parse_date(task.get("due_date"))
    days = (due - today).days if due else None
    urgent = days is not None and days <= 1

    if days is not None:
        if days < 0:
            score += 50
            reasons.append("Overdue")
        elif days == 0:
            score += 45
            reasons.append("Due today")
        elif days == 1:
            score += 40
            reasons.append("Due tomorrow")
        elif days <= 7:
            score += 25
            reasons.append("Due this week")
        elif days <= 14:
            score += 10
    if priority == "high":
        score += 20
        reasons.append("High priority")
    elif priority == "low":
        score -= 10
    if area in PROTECTED_AREAS:
        score += 30
        reasons.append("PhD first" if area == "phd" else "Health first")
    if area == "business" and not urgent and priority != "high":
        score -= 40  # non-urgent business waits behind PhD and fitness
    if area == "creator" and not urgent and priority != "high":
        score -= 15

    return score, (reasons[0] if reasons else "Next in line")


def suggest_top3(tasks: list[dict], today: date, limit: int = 3) -> list[dict]:
    """Up to three priorities for today.

    Tasks you pinned for today always come first and are marked 'pinned'.
    Remaining places are filled with suggestions, marked 'suggested'.
    """
    open_tasks = [t for t in tasks if is_open(t)]
    pinned = [t for t in open_tasks if is_pinned_today(t, today)]
    pinned.sort(key=lambda t: t.get("created_at") or "")
    picks = [
        {"task": t, "source": "pinned", "reason": "Chosen by you"}
        for t in pinned[:limit]
    ]

    scored = []
    for task in open_tasks:
        if is_pinned_today(task, today) or is_snoozed(task, today):
            continue
        score, reason = _score(task, today)
        due = parse_date(task.get("due_date"))
        scored.append((-score, due or date.max, task.get("created_at") or "", task, reason))
    scored.sort(key=lambda item: item[:3])

    for _, _, _, task, reason in scored:
        if len(picks) >= limit:
            break
        picks.append({"task": task, "source": "suggested", "reason": reason})
    return picks


# ------------------------------------------------------------- weekly view


def _in_week(value, start: date, end: date) -> bool:
    day = parse_date(value)
    return day is not None and start <= day <= end


def week_summary(
    time_entries: list[dict], workouts: list[dict], targets: dict, today: date
) -> dict:
    """Actual versus planned for the current week, from recorded data only.

    'actual' is None when nothing was recorded. That is shown as missing,
    which is different from a recorded zero.
    """
    start, end = week_bounds(today)
    finished = [
        e for e in time_entries
        if e.get("minutes") is not None and _in_week(e.get("entry_date"), start, end)
    ]

    def minutes_for(category: str):
        values = [e["minutes"] for e in finished if e.get("category") == category]
        return sum(values) if values else None

    done_workouts = [
        w for w in workouts
        if w.get("status") == "completed" and _in_week(w.get("workout_date"), start, end)
    ]

    def target(key: str):
        value = (targets or {}).get(key)
        return value if isinstance(value, (int, float)) and value > 0 else None

    logged_days = {parse_date(e.get("entry_date")) for e in finished}
    logged_days |= {parse_date(w.get("workout_date")) for w in done_workouts}
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        state = "future" if day > today else ("logged" if day in logged_days else "missing")
        days.append({"date": day, "state": state})

    return {
        "week_start": start,
        "week_end": end,
        "phd_minutes": minutes_for("phd"),
        "phd_target_hours": target("phd_hours"),
        "workouts_done": len(done_workouts) if done_workouts else None,
        "workouts_target": target("workouts"),
        "business_minutes": minutes_for("business"),
        "business_limit_hours": target("business_hours_limit"),
        "family_minutes": minutes_for("family"),
        "family_target_hours": target("family_hours"),
        "days": days,
    }


def business_over_limit(summary: dict) -> bool:
    limit = summary.get("business_limit_hours")
    minutes = summary.get("business_minutes")
    return bool(limit and minutes and minutes > limit * 60)


def minutes_on(time_entries: list[dict], category: str, day: date):
    values = [
        e["minutes"] for e in time_entries
        if e.get("minutes") is not None
        and e.get("category") == category
        and parse_date(e.get("entry_date")) == day
    ]
    return sum(values) if values else None


def format_minutes(minutes) -> str:
    if minutes is None:
        return ""
    hours, rest = divmod(int(minutes), 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    if hours:
        return f"{hours} h"
    return f"{rest} min"


# ----------------------------------------------------------------- restart


def last_activity_date(
    tasks: list[dict], time_entries: list[dict], workouts: list[dict], today: date
):
    """The most recent day on which anything was recorded, or None."""
    days = []
    for task in tasks:
        for column in ("completed_at", "created_at"):
            stamp = parse_timestamp(task.get(column))
            if stamp:
                days.append(stamp.date())
    days += [parse_date(e.get("entry_date")) for e in time_entries]
    days += [
        parse_date(w.get("workout_date")) for w in workouts
        if w.get("status") == "completed"
    ]
    days = [d for d in days if d is not None and d <= today]
    return max(days) if days else None


def needs_restart(last_activity, today: date) -> bool:
    """True after several quiet days. A brand-new, empty app never needs one."""
    return last_activity is not None and (today - last_activity).days >= RESTART_AFTER_DAYS


def restart_phd_action(tasks: list[dict], today: date):
    """One PhD task to restart with: the earliest-due open one, or None."""
    phd = [t for t in tasks if is_open(t) and t.get("module") == "phd"]
    phd.sort(key=lambda t: (parse_date(t.get("due_date")) or date.max, t.get("created_at") or ""))
    return phd[0] if phd else None


def postponable_tasks(tasks: list[dict], today: date) -> list[dict]:
    """Overdue tasks that may be postponed: not PhD, fitness or family, not
    high priority and not pinned for today. Nothing is deleted or completed."""
    result = []
    for task in tasks:
        due = parse_date(task.get("due_date"))
        if not is_open(task) or due is None or due >= today:
            continue
        if task.get("module") in ESSENTIAL_AREAS or task.get("priority") == "high":
            continue
        if is_pinned_today(task, today) or is_snoozed(task, today):
            continue
        result.append(task)
    return result
