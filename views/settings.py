"""Settings: your display name, password, and a downloadable backup."""

import csv
import io
import json

import streamlit as st

from aira import APP_VERSION, auth, db, ui
from aira.supabase_client import get_client
from aira.timeutil import format_timestamp, now_kl


def _profile_section() -> None:
    ui.section("Profile")
    try:
        profile = db.get_profile() or {}
    except db.DataError as exc:
        st.error(str(exc))
        return
    with st.form("profile_form"):
        name = st.text_input(
            "Display name (used in the greeting on the home page)",
            value=profile.get("display_name") or "",
            max_chars=80,
        )
        if st.form_submit_button("Save profile", type="primary"):
            try:
                db.save_profile(auth.current_user_id(), name)
            except db.DataError as exc:
                st.error(str(exc))
            else:
                st.success("Profile saved.")
    st.caption("Timezone: Asia/Kuala_Lumpur (fixed for this app).")


TARGET_FIELDS = [
    ("phd_hours", "PhD focused hours per week"),
    ("workouts", "Workouts per week"),
    ("family_hours", "Personal and family hours per week"),
    ("business_hours_limit", "Business hours per week (your upper limit)"),
]


def _targets_section() -> None:
    ui.section(
        "Weekly targets and business limit",
        "Used on the home page to show actual versus planned. Leave a box empty for no target.",
    )
    try:
        targets = db.get_setting("general", "weekly_targets", {}) or {}
    except db.DataError as exc:
        st.error(str(exc))
        return
    with st.form("targets_form"):
        values = {}
        for key, label in TARGET_FIELDS:
            current = targets.get(key)
            values[key] = st.number_input(
                label, min_value=0.0, max_value=100.0, step=0.5,
                value=float(current) if isinstance(current, (int, float)) else None,
                key=f"target_{key}",
            )
        if st.form_submit_button("Save targets", type="primary"):
            cleaned = {key: value for key, value in values.items() if value}
            try:
                db.set_setting("general", "weekly_targets", cleaned)
            except db.DataError as exc:
                st.error(str(exc))
            else:
                st.success("Targets saved.")


def _password_section() -> None:
    ui.section("Change password")
    with st.form("password_form", clear_on_submit=True):
        new_password = st.text_input(
            "New password", type="password", autocomplete="new-password"
        )
        repeat = st.text_input(
            "Repeat new password", type="password", autocomplete="new-password"
        )
        if st.form_submit_button("Update password"):
            if len(new_password) < 12:
                st.error("Please use at least 12 characters.")
            elif new_password != repeat:
                st.error("The two passwords do not match.")
            else:
                try:
                    get_client().auth.update_user({"password": new_password})
                except Exception as exc:
                    st.error(
                        "Supabase did not accept the new password. You can "
                        "also change it in the Supabase dashboard under "
                        "Authentication, then Users. "
                        f"(Technical detail: {str(exc)[:200]})"
                    )
                else:
                    st.success("Password updated.")


def _tasks_csv(tasks: list[dict]) -> str:
    columns = [
        "id", "title", "module", "status", "priority", "due_date", "notes",
        "completed_at", "created_at", "updated_at",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(tasks)
    return buffer.getvalue()


def _backup_section() -> None:
    ui.section("Backup and export")
    st.write(
        "Download a copy of everything currently stored in AIRA OS. Keep the "
        "file somewhere private. It contains your personal records."
    )
    if st.button("Prepare backup"):
        try:
            st.session_state["_backup"] = db.export_everything()
            st.session_state["_backup_time"] = now_kl()
        except db.DataError as exc:
            st.error(str(exc))

    backup = st.session_state.get("_backup")
    if backup is not None:
        stamp = st.session_state["_backup_time"]
        file_stamp = f"{stamp:%Y-%m-%d_%H%M}"
        payload = {
            "app": "AIRA OS",
            "version": APP_VERSION,
            "exported_at": stamp.isoformat(),
            "timezone": "Asia/Kuala_Lumpur",
            "tables": backup,
        }
        total = sum(len(rows) for rows in backup.values())
        st.caption(
            f"Prepared {format_timestamp(stamp)} · {total} record(s) "
            f"across {len(backup)} table(s)"
        )
        col1, col2 = st.columns(2)
        col1.download_button(
            "Download full backup (JSON)",
            data=json.dumps(payload, indent=2, default=str),
            file_name=f"aira-os-backup_{file_stamp}.json",
            mime="application/json",
        )
        col2.download_button(
            "Download tasks (CSV for Excel)",
            data=_tasks_csv(backup["tasks"]),
            file_name=f"aira-os-tasks_{file_stamp}.csv",
            mime="text/csv",
        )
    st.caption(
        "To load records from files, use the Import data page. One-click "
        "restore from a backup arrives in a later phase."
    )


ui.page_header("Settings", f"Signed in as {auth.current_user_email()}")
_profile_section()
_targets_section()
_password_section()
_backup_section()
