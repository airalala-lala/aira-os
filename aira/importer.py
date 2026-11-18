"""Reads seed/import files, checks them, and works out what is new.

This file never talks to the database. It only:
  1. parses uploaded .json and .csv files into rows,
  2. validates every row (types, allowed values, impossible dates),
  3. compares rows with what is already stored, so nothing is imported twice
     and nothing existing is ever overwritten.

File formats
  * JSON:  {"tables": {"goals": [ {...}, {...} ], "module_settings": [ ... ]}}
  * CSV:   one table per file. The table is taken from the file name, e.g.
           04_body_measurements.csv or body_measurements.csv
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date

from aira import literature
from aira.timeutil import today_kl

MODULES = [
    "general", "phd", "fitness", "family", "business", "opportunities",
    "creator", "personal", "planner",
]

# Column types: "str", "int", "num", "bool", "date", "json". A "!" marks a required column.
SPECS: dict[str, dict[str, str]] = {
    "module_settings": {"module": "str!", "key": "str!", "value": "json!"},
    "goals": {
        "import_key": "str", "module": "str!", "title": "str!", "status": "str",
        "target_value": "num", "unit": "str", "target_date": "date", "notes": "str",
    },
    "research_phases": {
        "import_key": "str", "position": "int!", "title": "str!",
        "description": "str", "status": "str",
    },
    "supervisor_feedback": {
        "import_key": "str", "received_period": "str", "received_on": "date",
        "item": "str!", "status": "str", "notes": "str",
    },
    "thesis_milestones": {
        "import_key": "str", "position": "int!", "title": "str!", "due_date": "date",
        "status": "str", "completed_on": "date", "notes": "str",
    },
    "opportunities": {
        "import_key": "str", "kind": "str", "title": "str!", "organisation": "str",
        "country": "str", "target_year": "int", "url": "str", "deadline": "date",
        "deadline_source_url": "str", "stage": "str", "outcome": "str", "notes": "str",
    },
    "body_measurements": {
        "import_key": "str", "measured_on": "date!", "weight_kg": "num!", "notes": "str",
    },
    "workouts": {
        "import_key": "str!", "workout_date": "date!", "location": "str",
        "kind": "str", "status": "str!", "duration_min": "int", "notes": "str",
    },
    "strength_sets": {
        "import_key": "str", "workout_key": "str!", "position": "int!",
        "exercise_name": "str!", "set_number": "int", "reps": "int",
        "load_value": "num", "load_unit": "str", "load_basis": "str",
        "load_text": "str", "notes": "str",
    },
    "literature_sources": {
        "import_key": "str", "title": "str!", "authors": "str", "year": "int",
        "publication_date": "str", "doi": "str", "url": "str", "journal": "str",
        "source_type": "str", "research_country": "str", "methodology": "str",
        "theoretical_framework": "str", "key_findings": "str", "conclusions": "str",
        "limitations": "str", "relevance": "str", "gap_contribution": "str",
        "critical_notes": "str", "reading_status": "str", "date_read": "date",
        "tags": "str", "citation": "str", "abstract": "str", "open_access": "str",
        "summary_basis": "str", "summary_source": "str", "pii": "str", "scopus_eid": "str",
    },
    "cardio_entries": {
        "import_key": "str", "workout_key": "str!", "position": "int!",
        "activity": "str!", "distance_m": "num", "duration_seconds": "int",
        "duration_approximate": "bool", "settings_text": "str", "notes": "str",
    },
}

# Allowed values. These mirror the CHECK rules in the database.
ALLOWED: dict[str, dict[str, list[str]]] = {
    "module_settings": {"module": MODULES},
    "goals": {"module": MODULES, "status": ["active", "achieved", "paused", "dropped"]},
    "research_phases": {"status": ["planned", "in_progress", "completed"]},
    "supervisor_feedback": {"status": ["open", "addressed"]},
    "thesis_milestones": {"status": ["planned", "in_progress", "completed"]},
    "opportunities": {
        "kind": [
            "unspecified", "application", "internship_or_attachment",
            "visiting_researcher", "conference_or_symposium",
            "scholarship_or_fellowship", "funding", "collaboration",
        ],
        "stage": [
            "status_unconfirmed", "interested", "preparing", "submitted",
            "interview", "accepted", "rejected", "withdrawn", "closed",
        ],
    },
    "literature_sources": {
        "reading_status": literature.READING_STATUSES,
        "summary_basis": literature.SUMMARY_BASIS,
        "source_type": literature.SOURCE_TYPES,
    },
    "workouts": {
        "status": ["planned", "completed", "skipped"],
        "kind": ["strength", "rowing", "swimming", "kettlebell", "mixed", "recovery", "other"],
    },
    "strength_sets": {
        "load_unit": ["kg", "lb", "machine_units"],
        "load_basis": ["total", "per_side", "per_dumbbell"],
    },
}

# Values used when a column is left empty. These mirror the database defaults.
DEFAULTS: dict[str, dict[str, object]] = {
    "goals": {"status": "active"},
    "research_phases": {"status": "planned"},
    "supervisor_feedback": {"status": "open"},
    "thesis_milestones": {"status": "planned"},
    "opportunities": {"kind": "unspecified", "stage": "interested"},
    "cardio_entries": {"duration_approximate": False},
    "literature_sources": {"reading_status": "not_recorded"},
}

# Parents first, so sets and cardio entries can find their workout.
IMPORT_ORDER = [
    "module_settings", "goals", "research_phases", "supervisor_feedback",
    "thesis_milestones", "opportunities", "body_measurements", "workouts",
    "strength_sets", "cardio_entries", "literature_sources",
]

TABLE_LABELS = {
    "module_settings": "Settings and preferences",
    "goals": "Goals",
    "research_phases": "PhD research phases",
    "supervisor_feedback": "Supervisor feedback",
    "thesis_milestones": "Thesis milestones",
    "opportunities": "Opportunities",
    "body_measurements": "Weight records",
    "workouts": "Workout sessions",
    "strength_sets": "Strength sets",
    "cardio_entries": "Cardio entries",
    "literature_sources": "Literature sources",
}

_CSV_NAME = re.compile(r"^(?:\d+[a-z]?_)?([a-z_]+)\.csv$")


@dataclass
class TablePlan:
    table: str
    new_rows: list[dict] = field(default_factory=list)
    already_stored: int = 0


# ------------------------------------------------------------------ parsing


def _convert(value, kind: str):
    """Convert one cell to its proper type. Empty cells become None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if kind == "json":
        return value
    if kind == "str":
        if isinstance(value, (dict, list)):
            raise ValueError("expected text")
        return str(value)
    if kind == "int":
        if isinstance(value, bool):
            raise ValueError("expected a whole number")
        number = float(value)
        if number != int(number):
            raise ValueError("expected a whole number")
        return int(number)
    if kind == "num":
        if isinstance(value, bool):
            raise ValueError("expected a number")
        return float(value)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).lower()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"}:
            return False
        raise ValueError("expected true or false")
    if kind == "date":
        return date.fromisoformat(str(value)).isoformat()
    raise ValueError(f"unknown type {kind}")


def _auto_key(table: str, row: dict) -> str:
    """A stable fingerprint for rows that arrive without an import_key."""
    canonical = json.dumps(row, sort_keys=True, default=str)
    return "auto:" + hashlib.sha1(f"{table}|{canonical}".encode()).hexdigest()[:20]


def _check_row(table: str, row: dict, where: str, today: date) -> list[str]:
    problems = []
    for column, allowed in ALLOWED.get(table, {}).items():
        if row.get(column) is not None and row[column] not in allowed:
            problems.append(
                f"{where}: '{row[column]}' is not allowed for {column} "
                f"(allowed: {', '.join(allowed)})"
            )
    if table == "body_measurements":
        if not 20 < row["weight_kg"] < 400:
            problems.append(f"{where}: weight_kg {row['weight_kg']} is not plausible")
        if date.fromisoformat(row["measured_on"]) > today:
            problems.append(f"{where}: measured_on is in the future")
    if table == "workouts" and row.get("status") == "completed":
        if date.fromisoformat(row["workout_date"]) > today:
            problems.append(f"{where}: a completed workout cannot be in the future")
    if table == "strength_sets":
        if row.get("reps") is not None and row["reps"] <= 0:
            problems.append(f"{where}: reps must be above zero")
        if row.get("load_value") is not None and row.get("load_unit") is None:
            problems.append(f"{where}: load_value needs a load_unit (kg, lb or machine_units)")
    if table == "thesis_milestones" and row.get("status") == "completed":
        if row.get("completed_on") is None:
            problems.append(f"{where}: a completed milestone needs completed_on")
    if table == "literature_sources":
        if row.get("year") is not None and not 1800 <= row["year"] <= today.year + 1:
            problems.append(f"{where}: year {row['year']} is not plausible")
        if row.get("date_read") and date.fromisoformat(row["date_read"]) > today:
            problems.append(f"{where}: date_read is in the future")
    if table == "opportunities" and row.get("deadline") and not row.get("deadline_source_url"):
        problems.append(f"{where}: a deadline needs deadline_source_url (where it came from)")
    return problems


def _parse_table(table: str, raw_rows: list, source: str, today: date):
    """Return (clean_rows, problems) for one table from one file."""
    problems: list[str] = []
    if table not in SPECS:
        return [], [f"{source}: unknown table '{table}'"]
    spec = SPECS[table]
    clean_rows = []
    for number, raw in enumerate(raw_rows, start=1):
        where = f"{source}, {table} row {number}"
        if not isinstance(raw, dict):
            problems.append(f"{where}: not a record")
            continue
        unknown = [str(c) for c in raw if c not in spec]
        if unknown:
            problems.append(f"{where}: unknown column(s) {', '.join(unknown)}")
            continue
        row, bad = {}, False
        for column, kind in spec.items():
            required = kind.endswith("!")
            try:
                value = _convert(raw.get(column), kind.rstrip("!"))
            except (ValueError, TypeError) as exc:
                problems.append(f"{where}: {column} = {raw.get(column)!r} ({exc})")
                bad = True
                continue
            if value is None:
                value = DEFAULTS.get(table, {}).get(column)
            if required and value is None:
                problems.append(f"{where}: {column} is required")
                bad = True
            row[column] = value
        if bad:
            continue
        row_problems = _check_row(table, row, where, today)
        if row_problems:
            problems.extend(row_problems)
            continue
        if table == "literature_sources":
            row["doi"] = literature.normalize_doi(row.get("doi")) or None
            if not row.get("import_key"):
                row["import_key"] = literature.source_key(
                    row.get("doi"), row.get("scopus_eid"), row["title"], row.get("year")
                )
        if "import_key" in spec and not row.get("import_key"):
            row["import_key"] = _auto_key(table, row)
        clean_rows.append(row)
    return clean_rows, problems


def parse_files(files: dict[str, bytes], today: date | None = None):
    """Parse uploaded files. Returns (rows_by_table, problems)."""
    today = today or today_kl()
    rows_by_table: dict[str, list[dict]] = {}
    problems: list[str] = []

    for name in sorted(files):
        if name.lower().endswith(".xlsx"):
            raw_rows, errs = literature.read_matrix_xlsx(
                files[name], f"Literature review matrix export ({name})"
            )
            problems.extend(f"{name}: {e}" for e in errs)
            rows, errs = _parse_table("literature_sources", raw_rows, name, today)
            rows_by_table.setdefault("literature_sources", []).extend(rows)
            problems.extend(errs)
            continue
        try:
            text = files[name].decode("utf-8-sig")
        except UnicodeDecodeError:
            problems.append(f"{name}: not a UTF-8 text file")
            continue
        lower = name.lower()

        if lower.endswith(".json"):
            try:
                document = json.loads(text)
            except json.JSONDecodeError as exc:
                problems.append(f"{name}: not valid JSON ({exc})")
                continue
            tables = document.get("tables") if isinstance(document, dict) else None
            if not isinstance(tables, dict):
                problems.append(f'{name}: expected a "tables" section')
                continue
            for table, raw_rows in tables.items():
                if not isinstance(raw_rows, list):
                    problems.append(f"{name}: table '{table}' must be a list")
                    continue
                rows, errs = _parse_table(table, raw_rows, name, today)
                rows_by_table.setdefault(table, []).extend(rows)
                problems.extend(errs)

        elif lower.endswith(".csv"):
            match = _CSV_NAME.match(lower)
            table = match.group(1) if match else ""
            if table not in SPECS or table == "module_settings":
                problems.append(
                    f"{name}: the file name must end with a table name, for "
                    "example body_measurements.csv or 05b_strength_sets.csv"
                )
                continue
            raw_rows = list(csv.DictReader(io.StringIO(text)))
            rows, errs = _parse_table(table, raw_rows, name, today)
            rows_by_table.setdefault(table, []).extend(rows)
            problems.extend(errs)
        else:
            problems.append(f"{name}: only .json, .csv and .xlsx files can be imported")

    # The same record must not appear twice within the uploaded files.
    for table, rows in rows_by_table.items():
        seen: set = set()
        for row in rows:
            ident = (
                (row["module"], row["key"])
                if table == "module_settings"
                else row["import_key"]
            )
            if ident in seen:
                problems.append(f"{table}: '{ident}' appears more than once in the files")
            seen.add(ident)
    return rows_by_table, problems


# ----------------------------------------------------------------- planning


def build_plan(
    rows_by_table: dict[str, list[dict]],
    existing_keys: dict[str, set],
    existing_settings: set,
):
    """Split rows into new and already-stored. Returns (plans, problems).

    existing_keys:     {table: {import_key, ...}} read from the database
    existing_settings: {(module, key), ...} read from the database
    """
    plans: list[TablePlan] = []
    problems: list[str] = []

    workout_keys = set(existing_keys.get("workouts", set()))
    workout_keys |= {row["import_key"] for row in rows_by_table.get("workouts", [])}

    for table in IMPORT_ORDER:
        rows = rows_by_table.get(table, [])
        if not rows:
            continue
        plan = TablePlan(table=table)
        for row in rows:
            if table == "module_settings":
                stored = (row["module"], row["key"]) in existing_settings
            else:
                stored = row["import_key"] in existing_keys.get(table, set())
            if stored:
                plan.already_stored += 1
                continue
            if "workout_key" in row and row["workout_key"] not in workout_keys:
                problems.append(
                    f"{table}: '{row['import_key']}' refers to workout "
                    f"'{row['workout_key']}', which is not in the files or the database"
                )
                continue
            plan.new_rows.append(row)
        plans.append(plan)
    return plans, problems


def rows_for_insert(plan: TablePlan, workout_ids: dict[str, str]) -> list[dict]:
    """Final rows for the database: workout_key is swapped for the real workout_id."""
    if plan.table not in {"strength_sets", "cardio_entries"}:
        return [dict(row) for row in plan.new_rows]
    ready = []
    for row in plan.new_rows:
        row = dict(row)
        row["workout_id"] = workout_ids[row.pop("workout_key")]
        ready.append(row)
    return ready
