"""Basic tests for the parts of AIRA OS that do not need Streamlit or Supabase.

Run them from the project folder with:   python3 -m unittest discover tests -v
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aira import fitness, importer, literature, opportunities, planning, timeutil, video_refs  # noqa: E402

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



class LiteratureTests(unittest.TestCase):
    def test_doi_is_cleaned(self):
        self.assertEqual(literature.normalize_doi("https://doi.org/10.1016/J.CMI.2014.11.015"), "10.1016/j.cmi.2014.11.015")
        self.assertEqual(literature.normalize_doi("doi: 10.1/ABC."), "10.1/abc")
        self.assertIsNone(literature.normalize_doi("not a doi"))
        self.assertIsNone(literature.normalize_doi(None))

    def test_duplicate_key_prefers_doi_then_eid_then_title(self):
        self.assertEqual(literature.source_key("https://doi.org/10.1/X", "2-s2.0-1", "T", 2020), "doi:10.1/x")
        self.assertEqual(literature.source_key(None, "2-s2.0-1", "T", 2020), "eid:2-s2.0-1")
        self.assertEqual(
            literature.source_key(None, None, "How Schools Do Policy!", 2012),
            literature.source_key(None, None, "how schools do policy", 2012),
        )

    def test_matrix_rows_import_as_literature_and_dedupe_by_doi(self):
        csv = (
            b"title,doi,year\n"
            b"Paper A,https://doi.org/10.1/A,2020\n"
            b"Paper A again,10.1/a,2020\n"
        )
        rows, problems = importer.parse_files({"literature_sources.csv": csv}, TODAY)
        self.assertEqual(rows["literature_sources"][0]["import_key"], "doi:10.1/a")
        self.assertEqual(len(problems), 1)  # the second row repeats the same DOI

    def test_reading_status_is_not_assumed(self):
        rows, _ = importer.parse_files({"literature_sources.csv": b"title\nPaper\n"}, TODAY)
        self.assertEqual(rows["literature_sources"][0]["reading_status"], "not_recorded")

    def test_non_matrix_excel_is_rejected_clearly(self):
        rows, problems = importer.parse_files({"x.xlsx": b"not really excel"}, TODAY)
        self.assertEqual(rows.get("literature_sources"), [])
        self.assertTrue(problems)

    def test_papers_processed_counts_only_date_read_this_week(self):
        read = [{"date_read": "2026-11-16"}, {"date_read": "2026-11-09"}, {"date_read": None}]
        summary = planning.week_summary([], [], {"papers": 5}, TODAY, read)
        self.assertEqual((summary["papers_done"], summary["papers_target"]), (1, 5))
        self.assertIsNone(planning.week_summary([], [], {}, TODAY, [])["papers_done"])



W = [
    {"id": "w1", "workout_date": "2026-10-12", "status": "completed"},
    {"id": "w2", "workout_date": "2026-10-31", "status": "completed"},
    {"id": "w3", "workout_date": "2026-11-20", "status": "planned"},
]
SETS = [
    {"workout_id": "w1", "exercise_name": "Lat pulldown", "set_number": 1, "reps": 12, "load_value": 27, "load_unit": "kg", "load_basis": None},
    {"workout_id": "w1", "exercise_name": "Lat pulldown", "set_number": 2, "reps": 6, "load_value": 32, "load_unit": "kg", "load_basis": None},
    {"workout_id": "w2", "exercise_name": "Lat pulldown", "set_number": 1, "reps": 8, "load_value": 32, "load_unit": "kg", "load_basis": None},
    {"workout_id": "w2", "exercise_name": "Chest press machine", "set_number": 1, "reps": 10, "load_value": 50, "load_unit": "lb", "load_basis": None},
    {"workout_id": "w2", "exercise_name": "Precor leg press", "set_number": 1, "reps": 10, "load_value": 20, "load_unit": "kg", "load_basis": "per_side"},
    {"workout_id": "w3", "exercise_name": "Lat pulldown", "set_number": 1, "reps": 10, "load_value": 40, "load_unit": "kg", "load_basis": None},
]


class FitnessTests(unittest.TestCase):
    def test_set_rows_are_cleaned_and_numbered(self):
        rows = [
            {"Exercise": "Leg press", "Reps": 15, "Load": 80, "Unit": "kg"},
            {"Exercise": "Leg press", "Reps": 15, "Load": 100, "Unit": "kg"},
            {"Exercise": "Lat pulldown", "Reps": 12, "Load": 27, "Unit": "kg"},
            {"Exercise": None, "Reps": None, "Load": None, "Unit": None},  # empty row ignored
            {"Exercise": None, "Reps": None, "Load": None, "Unit": "kg"},  # only the default unit: ignored
        ]
        clean, problems = fitness.clean_set_rows(rows)
        self.assertEqual(problems, [])
        self.assertEqual([(r["exercise_name"], r["position"], r["set_number"]) for r in clean],
                         [("Leg press", 1, 1), ("Leg press", 1, 2), ("Lat pulldown", 2, 1)])

    def test_set_rows_reject_bad_values(self):
        rows = [
            {"Exercise": "", "Reps": 10},
            {"Exercise": "Squat", "Reps": 0},
            {"Exercise": "Squat", "Load": 20, "Unit": None},
            {"Exercise": "Squat", "Reps": 8.5},
            {"Exercise": "Squat", "RPE": 11},
        ]
        clean, problems = fitness.clean_set_rows(rows)
        self.assertEqual((clean, len(problems)), ([], 5))

    def test_cardio_minutes_become_seconds(self):
        clean, problems = fitness.clean_cardio_rows([{"Activity": "Rowing", "Distance (m)": 1000, "Minutes": 5.5, "Approx.": True}])
        self.assertEqual(problems, [])
        self.assertEqual((clean[0]["duration_seconds"], clean[0]["duration_approximate"]), (330, True))

    def test_edits_keep_existing_rows(self):
        original = [{"id": "a"}, {"id": "b"}]
        clean = [{"id": "a", "reps": 9}, {"id": None, "reps": 5}]
        inserts, updates, deletes = fitness.diff_rows(clean, original)
        self.assertEqual(([u["id"] for u in updates], deletes, len(inserts)), (["a"], ["b"], 1))
        self.assertNotIn("id", inserts[0])

    def test_personal_bests_never_mix_units_or_planned_sessions(self):
        bests = {(b["exercise"], b["series"]): b for b in fitness.personal_bests(SETS, W)}
        self.assertEqual(bests[("Lat pulldown", "kg")]["load"], 32)   # 40 kg was only planned
        self.assertEqual(bests[("Lat pulldown", "kg")]["reps"], 8)    # tie on 32 kg -> more reps
        self.assertEqual(bests[("Chest press machine", "lb")]["load"], 50)
        self.assertIn(("Precor leg press", "kg per side"), bests)

    def test_exercise_history_uses_heaviest_set_per_session(self):
        history = fitness.exercise_history(SETS, W, "Lat pulldown")
        self.assertEqual([r["top"][("kg", "total")]["load"] for r in history], [32, 32])
        self.assertEqual(history[0]["sets"], ["27 kg × 12", "32 kg × 6"])

    def test_load_labels(self):
        self.assertEqual(fitness.load_label({"load_value": 20, "load_unit": "kg", "load_basis": "per_side"}), "20 kg per side")
        self.assertEqual(fitness.load_label({"load_value": 6, "load_unit": "kg", "load_basis": "per_dumbbell"}), "6 kg per dumbbell")
        self.assertEqual(fitness.load_label({"load_value": None, "load_text": "9–10 kg"}), "9–10 kg")

    def test_weekly_counts_leave_empty_weeks_empty(self):
        counts = fitness.weekly_counts(W, date(2026, 11, 2), 4)
        # Weeks of 12, 19 and 26 Oct and 2 Nov; 31 Oct is a Saturday in the 26 Oct week.
        self.assertEqual([c["count"] for c in counts], [1, None, 1, None])

    def test_moving_average_uses_recorded_entries_only(self):
        points = [(date(2026, 10, 1), 68.10), (date(2026, 10, 12), 67.25), (date(2026, 10, 31), 66.10)]
        avg = fitness.moving_average(points, 14)
        self.assertEqual(avg[1][1], round((68.10 + 67.25) / 2, 2))
        self.assertEqual(avg[2][1], 66.10)  # nothing else recorded in the 14 days before


    def test_weekly_plan_adds_only_today_onward_and_once(self):
        template = fitness.suggested_template(3)
        monday = date(2026, 11, 16)
        todo = fitness.sessions_to_add(template, monday, date(2026, 11, 18), [])
        self.assertEqual([t["date"] for t in todo], [date(2026, 11, 18), date(2026, 11, 20)])
        existing = [{"import_key": todo[0]["key"]}]
        self.assertEqual(len(fitness.sessions_to_add(template, monday, date(2026, 11, 18), existing)), 1)

    def test_planned_loads_come_from_last_recorded_set(self):
        latest = fitness.latest_loads(SETS, W)
        self.assertEqual(latest["Lat pulldown"]["load_value"], 32)  # 40 kg was only planned
        plan_sets, _ = fitness.session_details("strength_a", fitness.suggested_template(3), latest)
        pull = [x for x in plan_sets if x["exercise_name"] == "Lat pulldown"]
        self.assertEqual((len(pull), pull[0]["load_value"], pull[0]["reps"]), (3, 32, 10))
        back = [x for x in plan_sets if x["exercise_name"] == "Back extension"]
        self.assertIsNone(back[0]["load_value"])  # never recorded, so no load is invented



class OpportunityTests(unittest.TestCase):
    OPPS = [
        {"id": "a", "title": "Soon", "stage": "preparing", "deadline": "2026-11-30"},
        {"id": "b", "title": "Later", "stage": "interested", "deadline": "2027-01-31"},
        {"id": "c", "title": "No date", "stage": "interested", "deadline": None},
        {"id": "d", "title": "Done", "stage": "submitted", "deadline": "2026-11-20"},
        {"id": "e", "title": "Missed", "stage": "interested", "deadline": "2026-11-01"},
        {"id": "f", "title": "Dropped", "stage": "not_pursuing", "deadline": "2026-12-01"},
    ]

    def test_groups(self):
        g = opportunities.group(self.OPPS, date(2026, 11, 18))
        self.assertEqual([o["id"] for o in g["closing"]], ["a", "b"])
        self.assertEqual([o["id"] for o in g["applied"]], ["d"])
        self.assertEqual([o["id"] for o in g["watch"]], ["c"])
        self.assertEqual({o["id"] for o in g["past"]}, {"e", "f"})

    def test_closing_soon_ignores_applied_and_undated(self):
        soon = opportunities.closing_soon(self.OPPS, date(2026, 11, 18))
        self.assertEqual([o["id"] for o in soon], ["a"])

    def test_countdown(self):
        today = date(2026, 11, 18)
        self.assertEqual(opportunities.countdown({"deadline": "2026-11-30"}, today), "12 days left")
        self.assertEqual(opportunities.countdown({"deadline": "2026-11-18"}, today), "Closes today")
        self.assertEqual(opportunities.countdown({"deadline": None}, today), "Deadline not published")

    def test_import_needs_a_source_for_every_deadline(self):
        csv = b"title,deadline,deadline_source_url\nWith source,2027-01-31,https://example.org\nNo source,2027-01-31,\n"
        rows, problems = importer.parse_files({"opportunities.csv": csv}, date(2026, 11, 18))
        self.assertEqual((len(rows["opportunities"]), len(problems)), (1, 1))



class VideoReferenceTests(unittest.TestCase):
    def test_platform_detection(self):
        cases = {
            "https://www.tiktok.com/@a/video/123": "tiktok", "https://vt.tiktok.com/ZS123/": "tiktok",
            "https://www.instagram.com/reel/Cx1/": "instagram", "https://youtu.be/abc": "youtube",
            "https://www.youtube.com/shorts/abc": "youtube", "https://x.com/a/status/1": "x",
            "https://vimeo.com/1": "vimeo", "https://example.com/v": "other",
            "https://notyoutube.com/x": "other",
        }
        for url, platform in cases.items():
            self.assertEqual(video_refs.detect_platform(url), platform, url)

    def test_same_video_gets_same_key(self):
        k = video_refs.url_key
        self.assertEqual(k("https://youtu.be/abc?si=xyz"), k("https://www.youtube.com/shorts/abc"))
        self.assertEqual(k("https://www.youtube.com/watch?v=abc&t=10"), "youtube:abc")
        self.assertEqual(k("https://www.instagram.com/reel/Cx1/?igsh=123"), k("https://instagram.com/reel/Cx1"))
        self.assertEqual(k("https://www.tiktok.com/@a/video/1?is_from_webapp=1&_r=1"), k("https://www.tiktok.com/@a/video/1"))

    def test_clean_url(self):
        self.assertEqual(video_refs.clean_url("  tiktok.com/@a/video/1 "), "https://tiktok.com/@a/video/1")
        self.assertFalse(video_refs.is_valid_url(video_refs.clean_url("hello")))

    def test_metadata_from_oembed(self):
        def fetch(url, **kw):
            self.assertIn("youtube.com/oembed", url)
            return b'{"title":"Cell division in 60s","author_name":"Bio Channel","thumbnail_url":"https://i.ytimg.com/x.jpg"}', "application/json"
        meta = video_refs.fetch_metadata("https://youtu.be/abc", fetch)
        self.assertEqual((meta["status"], meta["title"], meta["creator"], meta["source"]),
                         ("retrieved", "Cell division in 60s", "Bio Channel", "YouTube oEmbed"))

    def test_failure_keeps_link_only(self):
        def fetch(url, **kw):
            raise OSError("offline")
        meta = video_refs.fetch_metadata("https://www.tiktok.com/@a/video/1", fetch)
        self.assertEqual((meta["status"], meta["title"]), ("not_available", None))

    def test_instagram_is_not_scraped(self):
        calls = []
        meta = video_refs.fetch_metadata("https://www.instagram.com/reel/Cx1/", lambda u, **k: calls.append(u))
        self.assertEqual((meta["status"], calls), ("not_available", []))

    def test_open_graph_fallback(self):
        page = b'<meta property="og:title" content="Osmosis &amp; you"><meta content="https://img/x.png" property="og:image">'
        meta = video_refs.fetch_metadata("https://example.com/v", lambda u, **k: (page, "text/html"))
        self.assertEqual((meta["title"], meta["thumbnail_url"]), ("Osmosis & you", "https://img/x.png"))

    def test_brief_uses_only_recorded_fields(self):
        refs = [
            {"title": "A", "platform": "tiktok", "hook": "Starts with a wrong answer", "analysis_basis": "watched_by_me"},
            {"title": "B", "platform": "instagram", "analysis_basis": "not_analysed"},
        ]
        brief = video_refs.build_brief(refs, "Osmosis", "Form 4", "60 seconds")
        self.assertIn("Hook and opening style: Starts with a wrong answer", brief)
        self.assertIn("Nothing recorded about this reference beyond its link", brief)
        self.assertNotIn("Editing", brief)

    def test_analysis_json_is_parsed(self):
        text = 'Here: {"hook":"Question first","editing":"Jump cuts"}'
        draft = video_refs.parse_analysis_json(text)
        self.assertEqual((draft["hook"], draft["editing"], draft["visuals"]), ("Question first", "Jump cuts", ""))
        with self.assertRaises(ValueError):
            video_refs.parse_analysis_json("no json")


if __name__ == "__main__":
    unittest.main()
