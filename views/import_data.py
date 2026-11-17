"""Import data: upload seed files, preview them, then import only what is new.

Safety rules of this page:
  * Nothing is written until you tick the confirmation box and press Import.
  * Records already in the database are skipped, never replaced.
  * Everything is inserted as the signed-in user, under Row Level Security.
  * The uploaded files are read in memory only. They are not saved on the server.
"""

import streamlit as st

from aira import db, importer, ui


def _existing_state():
    """Read which records are already stored. Returns (keys_by_table, settings)."""
    keys = {
        table: db.existing_import_keys(table)
        for table in importer.IMPORT_ORDER
        if table != "module_settings"
    }
    return keys, db.existing_setting_keys()


def _run_import(plans) -> dict:
    """Insert the new rows, parents first. Returns {table: number inserted}."""
    done = {}
    workout_ids = {}
    for plan in plans:
        if not plan.new_rows:
            continue
        if plan.table in {"strength_sets", "cardio_entries"} and not workout_ids:
            workout_ids = db.workout_ids_by_import_key()
        rows = importer.rows_for_insert(plan, workout_ids)
        done[plan.table] = db.insert_rows(plan.table, rows)
    return done


def _show_stored_counts() -> None:
    ui.section("Currently stored")
    counts = {table: db.count_rows(table) for table in importer.IMPORT_ORDER}
    if not any(counts.values()):
        ui.empty_state("Nothing imported yet", "The history tables are empty.")
        return
    st.dataframe(
        [
            {"Records": importer.TABLE_LABELS[table], "Stored": counts[table]}
            for table in importer.IMPORT_ORDER
        ],
        hide_index=True,
    )


def main() -> None:
    ui.page_header(
        "Import data",
        "Upload your seed files, check the preview, then import. "
        "Existing records are never replaced.",
    )

    result = st.session_state.pop("_import_result", None)
    if result is not None:
        total = sum(result.values())
        st.success(f"Import finished. {total} new record(s) added.")
        st.dataframe(
            [
                {"Records": importer.TABLE_LABELS[table], "Added": number}
                for table, number in result.items()
            ],
            hide_index=True,
        )

    try:
        existing_keys, existing_settings = _existing_state()
    except db.DataError as exc:
        st.error(str(exc))
        st.info(
            "This page needs migration 0003. In Supabase, open the SQL Editor "
            "and run supabase/migrations/0003_history_tables.sql, then reload."
        )
        return

    uploads = st.file_uploader(
        "Choose all the files from your aira-os-seed-data folder (.json and .csv)",
        type=["json", "csv"],
        accept_multiple_files=True,
    )

    if not uploads:
        try:
            _show_stored_counts()
        except db.DataError as exc:
            st.error(str(exc))
        return

    files = {upload.name: upload.getvalue() for upload in uploads}
    rows_by_table, problems = importer.parse_files(files)
    plans, plan_problems = importer.build_plan(
        rows_by_table, existing_keys, existing_settings
    )
    problems = problems + plan_problems

    if problems:
        st.error(
            f"{len(problems)} problem(s) found. Nothing has been imported. "
            "Fix the files and upload them again."
        )
        for problem in problems[:50]:
            st.markdown(f"- {problem}")
        return

    new_total = sum(len(plan.new_rows) for plan in plans)
    skipped_total = sum(plan.already_stored for plan in plans)

    ui.section("Preview")
    col1, col2 = st.columns(2)
    col1.metric("New records to add", new_total)
    col2.metric("Already stored (will be skipped)", skipped_total)

    for plan in plans:
        label = (
            f"{importer.TABLE_LABELS[plan.table]}: {len(plan.new_rows)} new, "
            f"{plan.already_stored} already stored"
        )
        with st.expander(label):
            if plan.new_rows:
                st.dataframe(plan.new_rows, hide_index=True)
            else:
                st.caption("Nothing new in this table.")

    if new_total == 0:
        st.info("Everything in these files is already stored. Nothing to import.")
        return

    confirm = st.checkbox(
        f"I have checked the preview. Add these {new_total} record(s)."
    )
    if st.button("Import", type="primary", disabled=not confirm):
        try:
            st.session_state["_import_result"] = _run_import(plans)
        except db.DataError as exc:
            st.error(
                f"The import stopped part-way: {exc} Records added before the "
                "problem are kept. It is safe to upload the same files again; "
                "only the missing records will be added."
            )
        else:
            st.rerun()


main()
