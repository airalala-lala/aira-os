"""Basic tests for the parts of AIRA OS that do not need Streamlit or Supabase.

Run them from the project folder with:   python3 -m unittest discover tests -v
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aira import importer, planning, timeutil  # noqa: E402

TODAY = date(2026, 11, 17)  # a Tuesday


def task(title, area="personal", due=None, priority="normal", **extra):
    base = {
        "id": title, "title": title, "module": area, "status": "todo",
        "priority": priority, "due_date": due.isoformat() if due else None,
        "created_at": "2026-11-01T00:00:00+00:00",
    }
    base.update(extra)
    return base


class Top3Tests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(planning.suggest_top3([], TODAY), [])

    def test_phd_and_fitness_come_before_non_urgent_business(self):
        tasks = [
            task("Invoice template", "business", TODAY + timedelta(days=5)),
            task("Read one paper", "phd"),
            task("Row 10 minutes", "fitness"),
            task("Reply to supplier", "business"),
        ]
        picks = planning.suggest_top3(tasks, TODAY)
        titles = [p["task"]["title"] for p in picks]
        self.assertEqual(set(titles[:2]), {"Read one paper", "Row 10 minutes"})

    def test_urgent_business_is_not_pushed_down(self):
        tasks = [task("Pay supplier", "business", TODAY), task("Tidy notes", "personal")]
        self.assertEqual(planning.suggest_top3(tasks, TODAY)[0]["task"]["title"], "Pay supplier")

    def test_pinned_first_and_labelled(self):
        tasks = [
            task("Overdue PhD", "phd", TODAY - timedelta(days=3)),
            task("My choice", "personal", top3_date=TODAY.isoformat()),
        ]
        picks = planning.suggest_top3(tasks, TODAY)
        self.assertEqual(picks[0]["task"]["title"], "My choice")
        self.assertEqual(picks[0]["source"], "pinned")
        self.assertEqual(picks[1]["source"], "suggested")

    def test_done_and_snoozed_are_left_out_and_limit_is_three(self):
        tasks = [task(f"T{i}", "phd") for i in range(5)]
        tasks.append(task("Finished", "phd", status="done"))
        tasks.append(task("Later", "phd", snoozed_until=(TODAY + timedelta(days=2)).isoformat()))
        titles = [p["task"]["title"] for p in planning.suggest_top3(tasks, TODAY)]
        self.assertEqual(len(titles), 3)
        self.assertNotIn("Finished", titles)
        self.assertNotIn("Later", titles)

    def test_snooze_ends_on_its_date(self):
        t = task("Back", "phd", snoozed_until=TODAY.isoformat())
        self.assertFalse(planning.is_snoozed(t, TODAY))


class WeekTests(unittest.TestCase):
    def test_week_bounds(self):
        self.assertEqual(planning.week_bounds(TODAY), (date(2026, 11, 16), date(2026, 11, 22)))

    def test_missing_is_not_zero(self):
        summary = planning.week_summary([], [], {}, TODAY)
        self.assertIsNone(summary["phd_minutes"])
        self.assertIsNone(summary["workouts_done"])
        self.assertIsNone(summary["phd_target_hours"])
        states = [d["state"] for d in summary["days"]]
        self.assertEqual(states, ["missing", "missing"] + ["future"] * 5)

    def test_actuals_come_only_from_records(self):
        entries = [
            {"category": "phd", "minutes": 50, "entry_date": "2026-11-16"},
            {"category": "phd", "minutes": 40, "entry_date": "2026-11-17"},
            {"category": "phd", "minutes": 99, "entry_date": "2026-11-10"},   # last week
            {"category": "phd", "minutes": None, "entry_date": "2026-11-17"},  # running timer
            {"category": "business", "minutes": 200, "entry_date": "2026-11-17"},
        ]
        workouts = [
            {"status": "completed", "workout_date": "2026-11-16"},
            {"status": "planned", "workout_date": "2026-11-17"},
        ]
        targets = {"phd_hours": 10, "business_hours_limit": 3, "workouts": 3}
        summary = planning.week_summary(entries, workouts, targets, TODAY)
        self.assertEqual(summary["phd_minutes"], 90)
        self.assertEqual(summary["workouts_done"], 1)
        self.assertEqual(summary["business_minutes"], 200)
        self.assertTrue(planning.business_over_limit(summary))
        self.assertEqual([d["state"] for d in summary["days"]][:2], ["logged", "logged"])

    def test_not_over_limit_without_a_limit(self):
        entries = [{"category": "business", "minutes": 900, "entry_date": "2026-11-17"}]
        self.assertFalse(planning.business_over_limit(planning.week_summary(entries, [], {}, TODAY)))

    def test_format_minutes(self):
        self.assertEqual(planning.format_minutes(150), "2 h 30 min")
        self.assertEqual(planning.format_minutes(120), "2 h")
        self.assertEqual(planning.format_minutes(45), "45 min")


class RestartTests(unittest.TestCase):
    def test_new_empty_app_never_needs_restart(self):
        self.assertIsNone(planning.last_activity_date([], [], [], TODAY))
        self.assertFalse(planning.needs_restart(None, TODAY))

    def test_restart_after_quiet_days(self):
        entries = [{"entry_date": "2026-11-13", "minutes": 30, "category": "phd"}]
        last = planning.last_activity_date([], entries, [], TODAY)
        self.assertEqual(last, date(2026, 11, 13))
        self.assertTrue(planning.needs_restart(last, TODAY))
        self.assertFalse(planning.needs_restart(date(2026, 11, 15), TODAY))

    def test_only_non_essential_overdue_tasks_can_be_postponed(self):
        old = TODAY - timedelta(days=4)
        tasks = [
            task("PhD overdue", "phd", old),
            task("Family overdue", "family", old),
            task("Business overdue", "business", old),
            task("Business urgent", "business", old, priority="high"),
            task("Creator overdue", "creator", old),
            task("Business future", "business", TODAY + timedelta(days=2)),
            task("Business done", "business", old, status="done"),
        ]
        titles = {t["title"] for t in planning.postponable_tasks(tasks, TODAY)}
        self.assertEqual(titles, {"Business overdue", "Creator overdue"})

    def test_restart_phd_action_is_earliest_open_phd_task(self):
        tasks = [
            task("Later", "phd", TODAY + timedelta(days=9)),
            task("Sooner", "phd", TODAY + timedelta(days=2)),
            task("Not PhD", "business", TODAY),
        ]
        self.assertEqual(planning.restart_phd_action(tasks, TODAY)["title"], "Sooner")
        self.assertIsNone(planning.restart_phd_action([], TODAY))


class TimeTests(unittest.TestCase):
    def test_due_labels(self):
        self.assertEqual(timeutil.due_label(TODAY, TODAY), "Due today")
        self.assertEqual(timeutil.due_label(TODAY - timedelta(days=3), TODAY), "Overdue by 3 days")

    def test_database_times_are_shown_in_malaysia_time(self):
        stamp = timeutil.parse_timestamp("2026-11-10T06:45:00Z")
        self.assertEqual(timeutil.format_timestamp(stamp), "10 Nov 2026, 2:45 PM")
        self.assertEqual(timeutil.format_time(stamp), "2:45 PM")


class ImporterTests(unittest.TestCase):
    def test_rejects_bad_rows(self):
        files = {
            "body_measurements.csv": b"measured_on,weight_kg\n2026-12-01,66\n2026-10-01,abc\n",
            "strength_sets.csv": b"workout_key,position,exercise_name,load_value,load_unit\nw,1,Squat,20,stone\n",
        }
        rows, problems = importer.parse_files(files, TODAY)
        self.assertEqual(len(problems), 3)
        self.assertEqual(rows["body_measurements"], [])

    def test_units_and_basis_are_kept_as_written(self):
        csv = (
            b"import_key,workout_key,position,exercise_name,set_number,reps,load_value,load_unit,load_basis\n"
            b"k1,w,1,Chest press machine,1,10,50,lb,\n"
            b"k2,w,2,Leg press,1,10,20,kg,per_side\n"
        )
        rows, problems = importer.parse_files({"strength_sets.csv": csv}, TODAY)
        self.assertEqual(problems, [])
        self.assertEqual((rows["strength_sets"][0]["load_value"], rows["strength_sets"][0]["load_unit"]), (50.0, "lb"))
        self.assertEqual(rows["strength_sets"][1]["load_basis"], "per_side")

    def test_already_stored_rows_are_skipped(self):
        csv = b"import_key,measured_on,weight_kg\na,2026-10-01,68.10\nb,2026-10-12,67.25\n"
        rows, _ = importer.parse_files({"body_measurements.csv": csv}, TODAY)
        plans, problems = importer.build_plan(rows, {"body_measurements": {"a"}}, set())
        self.assertEqual(problems, [])
        self.assertEqual((len(plans[0].new_rows), plans[0].already_stored), (1, 1))

    def test_deadline_needs_a_source(self):
        files = {"opportunities.csv": b"title,deadline\nSome conference,2027-03-01\n"}
        _, problems = importer.parse_files(files, TODAY)
        self.assertEqual(len(problems), 1)


if __name__ == "__main__":
    unittest.main()
