# AIRA OS 2.0: architecture and plan

Version 2.2 · updated 18 November 2026 · Phase 1 and Phase 2a deployed and tested; Phase 3 (Fitness Studio) built.

**Purpose:** help Aira protect her priorities, regain consistency and make meaningful progress without feeling overwhelmed. The app should make the next good action obvious, take under two minutes a day, and still be useful when it is only opened a few times a week.

## 1. What already existed, and what changed

Inspected before building: the version 0.2 project (login, a simple task list, backup, the import page and migrations 0001 to 0003) and the seed-data folder. Nothing was discarded.

| Area | Version 0.2 | Version 2.0 |
|---|---|---|
| Modules | Five, including a Personal Planner | Six: PhD Research Hub, Fitness Studio, Business & Boundaries, Weekly Life Review, Global Opportunities, Creator Lab. The planner's job moved into the home page and the Weekly Life Review |
| Home page | Task list and counts | Daily command centre: Top 3, focus today, timer, weekly progress, Restart mode |
| Look | Light only, teal | Ivory, sage, muted teal, dusty rose and gold; light and dark; bottom bar on phones |
| Database | Migrations 0001 to 0003 | Adds 0004 (command centre), 0005 (PhD Hub) and 0006 (Fitness Studio). Earlier files are unchanged, and none changes an existing record |
| Tests | None in the project | `tests/test_core.py` |

## 2. Stack decision

**Recommendation: stay with Python, Streamlit and Supabase for now.**

| | Streamlit (chosen) | Next.js web app on Vercel (alternative) |
|---|---|---|
| Who can maintain it | Readable Python, one file per page | JavaScript/TypeScript, a much steeper learning curve |
| Work already done | Kept | Rewritten from scratch |
| Phone experience | Works in Safari; bottom bar is done with styling; every tap makes a round trip to the server | Feels like a native app, can be installed, works briefly offline |
| Staying signed in | Sign in again after a reload or a long pause | Stays signed in |
| First load after a quiet day | Up to a minute while the free server wakes | Instant |
| Database and security | Supabase with Row Level Security | The same Supabase project, unchanged |

The two weak points of Streamlit (waking up, signing in again) work directly against the "under two minutes a day" goal. The database design does not depend on Streamlit, so the interface can be replaced later without moving any data. **Revisit this choice after the Fitness Studio phase**, when there is real experience of logging from the phone.

## 3. Architecture

```
 MacBook browser ─┐                            ┌─ Supabase Auth      (who are you?)
                  ├─► Streamlit app (Python) ──┼─ Supabase Postgres  (your records, protected by RLS)
 iPhone Safari ───┘    on Streamlit Cloud      └─ Supabase Storage   (private attachments)
                              ▲
                     Private GitHub repository (code only; no secrets, no personal data)
```

### Folder structure

```
aira-os/
├── app.py                      Entry point: settings check, login gate, menus
├── requirements.txt            Python packages
├── .env.example, .gitignore    Local settings template; keeps secrets out of GitHub
├── README.md                   Step-by-step setup guide
├── .streamlit/
│   ├── config.toml             Light and dark theme (no secrets)
│   └── secrets.toml.example    Template for the Streamlit Cloud "Secrets" box
├── aira/                       Shared code
│   ├── config.py               Reads settings; refuses secret/service-role keys
│   ├── supabase_client.py      One private Supabase connection per browser session
│   ├── auth.py                 Sign in, sign out, session checks
│   ├── db.py                   Every database read and write
│   ├── planning.py             Top 3, weekly summary and Restart logic (no database, fully tested)
│   ├── importer.py             Parses and validates import files; blocks duplicates
│   ├── literature.py           DOI cleaning, duplicate keys, Excel matrix reader
│   ├── fitness.py              Set cleaning, personal bests, weekly counts, weight average (no database)
│   ├── timeutil.py             Asia/Kuala_Lumpur date and time helpers
│   ├── modules.py              The six modules and the phone bottom bar
│   └── ui.py                   Colours, cards, meters, empty states
├── views/                      One file per page
│   ├── home.py                 Daily command centre
│   ├── settings.py             Profile, weekly targets, password, backup
│   ├── import_data.py          Upload, preview and import
│   ├── phd.py                  PhD Research Hub (Overview, Literature, Supervision, Timeline)
│   ├── fitness.py              Fitness Studio (Overview, Log, Progress, Weight, Plan)
│   └── business.py, review.py, opportunities.py, creator.py
├── supabase/
│   ├── migrations/             0001 to 0006, run in order, never edited after use
│   └── verify_security.sql     Read-only check of RLS and grants
├── tests/test_core.py          Basic tests
└── docs/ARCHITECTURE.md        This document
```

## 4. Database schema

### Conventions for every table

- `id uuid` primary key; `user_id uuid` filled in by the database from the signed-in user, with a foreign key to `auth.users`.
- `created_at`, `updated_at` as `timestamptz` (UTC in the database, Malaysia time on screen). Calendar days such as `entry_date` are stored as Malaysia-time dates.
- Row Level Security on, four "own rows only" policies, access granted to `authenticated` only and nothing to `anon`.
- `check` lists on status fields; `import_key` with a uniqueness rule on tables that accept imports.

### Built now (migrations 0001 to 0006)

| Table | Purpose | Key columns |
|---|---|---|
| `profiles` | Display name | `display_name`, `timezone` |
| `tasks` | Every task, in any area | `title`, `module` (area), `status`, `priority`, `due_date`, `top3_date` (pinned to a day), `snoozed_until`, `completed_at`, `notes` |
| `time_entries` | Focus sessions and logged time; also the business time log | `category`, `entry_date`, `started_at`, `ended_at`, `minutes`, `source` (timer or manual), `note`, `task_id` |
| `module_settings` | Settings and preferences as key and JSON value | `module`, `key`, `value`. Weekly targets live at `general / weekly_targets` |
| `goals` | Long-term goals | `module`, `title`, `status`, `target_value`, `unit`, `target_date` |
| `research_phases` | The three phases of the PhD | `position`, `title`, `description`, `status` |
| `supervisor_feedback` | Feedback items | `received_period`, `received_on`, `item`, `status` |
| `thesis_milestones` | Prospectus to graduation | `position`, `title`, `due_date`, `status`, `completed_on` |
| `opportunities` | Applications and opportunities | `kind`, `title`, `organisation`, `url`, `deadline`, `deadline_source_url`, `stage`, `outcome` |
| `body_measurements` | Weight and optional measurements | `measured_on`, `weight_kg`, `waist_cm`, `hip_cm`, `notes` (at least one measurement per row) |
| `workouts` | One session, planned, completed or skipped | `workout_date`, `kind`, `status`, `duration_min`, `location`, `rpe` (session effort 1 to 10), `notes` |
| `strength_sets` | One row per set | `workout_id`, `exercise_name`, `set_number`, `reps`, `load_value`, `load_unit` (kg, lb, machine_units), `load_basis` (total, per_side, per_dumbbell), `load_text` (original wording), `rpe` |
| `cardio_entries` | Rowing, treadmill, swimming | `workout_id`, `activity`, `distance_m`, `duration_seconds`, `duration_approximate`, `settings_text` |
| `literature_sources` | Literature review database | `title`, `authors`, `year`, `doi`, `url`, `journal`, `source_type`, `research_country`; source evidence: `methodology`, `theoretical_framework`, `key_findings`, `conclusions`, `limitations`, `abstract`; my thinking: `relevance`, `gap_contribution`, `critical_notes`, `tags`; `reading_status`, `date_read`, `citation`; provenance: `summary_source`, `summary_basis` (full text or abstract only), `pii`, `scopus_eid` |
| `supervisor_meetings` | Supervision log | `meeting_date`, `title`, `feedback`, `decisions`, `notes`. Action items are PhD `tasks` with `meeting_id`, so they reach Today's Top 3 |

A running timer is a `time_entries` row whose `minutes` is still empty; the database allows only one at a time. Loads are stored exactly as logged: pounds stay pounds, per-side stays per side, and the machine stays part of the exercise name.

How the tables requested in the brief map onto this design: *Users* → `auth.users` + `profiles`; *Projects* → the area on each task and setting (a separate projects table is added only if a module needs sub-projects); *Focus sessions* and *Business time logs* → `time_entries`; *Exercise sets* → `strength_sets`; *Weight entries* → `body_measurements`; *Milestones* → `thesis_milestones`.

### Planned (one migration per phase)

| Phase | Tables | Notes |
|---|---|---|
| 2b PhD Hub | `themes`, `source_themes` (stance: supports, contradicts, mixed), `gap_claims` + `claim_evidence` (policy, curriculum, teacher knowledge, implementation and theoretical gaps, each claim linked to real sources), `course_items` (POL500), `weekly_plans`, `attachments` (PDFs), RIS/BibTeX import that fills missing authors and journals by DOI | Literature, meetings and timeline were built in 2a |
| 8 Polish | optional `habit_logs` and `meal_logs` (meals, protein estimates, hydration) | No diagnoses, no invented precision |
| 4 Business | `tasks` gains `delegated_to`, `waiting_on`; `day_closures` (End Business Day) | Time comes from `time_entries` |
| 5 Review | `weekly_reviews` (week start, six answers, next week's top three, saved summary) | One per week |
| 6 Opportunities | `opportunities` gains eligibility, required documents, contact, follow-up date; `events` (conference radar: organiser, location, dates, abstract and registration deadlines, fees, funding, official URL, verification date, status) | Deadlines require a source link |
| 7 Creator | `content_items`, `content_scripts`, `content_metrics` | Metrics entered by hand |

## 5. Authentication and access control

Four independent layers, each of which would have to fail for data to leak:

1. **Login gate.** `app.py` draws only the sign-in form until Supabase confirms a session.
2. **One account, no sign-up.** The single user is created by hand in Supabase, public sign-ups are switched off, and the app accepts only the email in `ALLOWED_EMAIL`.
3. **Row Level Security.** Every table returns only rows whose `user_id` is the signed-in user. Sets and cardio entries must also belong to one of that user's own workouts.
4. **Least-privilege key.** The app holds only the publishable key. The secret (service-role) key is never used, and the app refuses to start if one is pasted in.

The Supabase connection is kept per browser session, never in a shared cache. Storage uses a private bucket with per-user folders. No direct database connection string is used.

## 6. How MacBook and iPhone stay in sync

Both devices read the same database, so there is nothing to synchronise. A record saved on one device appears on the other after a reload or **Refresh**. A timer is a database row, so it can be started on the MacBook and stopped on the iPhone, and it survives a closed tab.

## 7. Limitations of this hosting

| Limitation | Effect | Mitigation |
|---|---|---|
| Streamlit Community Cloud sleeps after about 12 hours without visits | First visit takes up to a minute | Accept for now; see section 2 |
| Sign-in does not survive a reload or a long pause | Sign in again, sometimes after the phone was locked | Let Safari save the password; "remember this device" is a later option |
| Free Supabase projects pause after about a week of low activity | Connection error until **Resume** is pressed; data is kept | Open the app weekly, or upgrade |
| Free Supabase plan has not included automatic backups | A mistake is not automatically recoverable | Download a backup from Settings regularly |
| Limit on apps deployed from private repositories | May apply if another private app already exists | Records are protected by Supabase login and RLS either way |
| The phone bottom bar relies on styling Streamlit's layout | It may need adjusting after a Streamlit update | The side menu always works |
| Dark mode follows the device setting | No in-app switch | Change the device setting |

## 8. Development phases

| Phase | What gets built | Done when |
|---|---|---|
| **1. Foundation and daily command centre** (built) | Login, new design, Top 3, focus timer and time log, quick workout log, weekly progress with targets and business limit, Restart mode, tasks, backup, import | README Part D passes on both devices |
| **2a. PhD Research Hub** (built) | Literature manager with Excel matrix and CSV import, search, tags and duplicate checks; supervisor meeting log with action items; feedback checklist; timeline with planned and actual dates, semester bands and chart; "papers processed" on Home | README Part F passes |
| **2b. PhD Research Hub** | Synthesis board, research-problem evidence tracker, POL500 tracker, PhD weekly planner, PDF attachments, Mendeley RIS/BibTeX import | A real paper can be found again by theme |
| **3. Fitness Studio** (built) | Workout logger with sets and cardio in editable tables, "repeat a previous session", edit and delete; progress per exercise and machine; personal bests per unit; rowing and swimming logs; weight chart with 14-day average and goal line; optional waist and hip; weekly plan with done, skip, remove and move; consistency chart by week and month; gentle restart after 7 quiet days | README Part G passes |
| **4. Business & Boundaries** | Business task list with delegation and waiting-on, time summaries, allocation across areas, End Business Day | The weekly limit warning is driven by a full week of real logs |
| *Checkpoint* | Test persistence across sessions and devices; revisit the stack decision | |
| **5. Weekly Life Review** | Six questions, summary from recorded data, saved reflections, week comparison | A Sunday review takes under ten minutes |
| **6. Global Opportunities** | Application tracker, conference and symposium radar, entered by hand | Every deadline shows its source and verification date |
| **7. Creator Lab** | Idea bank, scripts, production status, calendar, manual metrics | A video can be followed from idea to published |
| **8. Polish** | Nutrition and habits, search, one-click restore, optional MFA and "remember this device", live opportunity discovery only if a legitimate source is configured and tested | |

## 9. Screen-by-screen plan

### Built in Phase 1

| Screen | What it shows | What you can do |
|---|---|---|
| **Sign in** | Brand and a form | Sign in. Five wrong attempts pause the form for a minute |
| **Home** | Timer banner (only while running); Restart card (after three quiet days or on request); Today's Top 3; My focus today (PhD focus, movement, one important task); This week (actual versus planned, with a strip showing which days have entries); All tasks | Pin, complete or set aside a priority; start and stop a timer; log time; plan or log a workout; add, edit and delete tasks and time entries |
| **Settings** | Profile, weekly targets and business limit, password, backup | Save targets; download JSON and CSV backups |
| **Import data** | Preview split into new and already stored | Import only what is new, after ticking a confirmation |
| **PhD Research Hub** (Phase 2a) | Overview (counts, research phases); Literature (search, filters, table, source detail with evidence kept apart from my thinking); Supervision (feedback checklist, meetings, action items); Timeline (milestones, chart, semester dates) | Add, edit, delete and import sources; mark read today; record meetings and action items; set planned and actual milestone dates |
| **Fitness Studio** (Phase 3) | Overview (this week, last workout, last recorded weight, consistency); Log (session and set tables, repeat, past workouts); Progress (chart, history, personal bests, rowing, swimming); Weight (chart, entries, goal); Plan (this or next week, day by day) | Log, edit and delete workouts and sets; add, edit and delete measurements; plan, move, skip and complete sessions |
| **Other four module pages** | "Not built yet" with the planned features | Nothing yet |

Navigation: sidebar on desktop; on a phone, the same menu plus a bottom bar (Home, PhD, Fitness, Business, Review).

### Planned

| Screen | Contents |
|---|---|
| **PhD · Synthesis** | Themes with their sources, contradictory findings side by side, my interpretation shown separately from source evidence |
| **PhD · Research problem** | The five gaps, each with claims and the sources that support them |
| **PhD · POL500 and weekly plan** | Assignments, readings, deadlines; weekly targets, blockers, reflection |
| **Business** | Task list, time this week against the limit, allocation across areas, End Business Day |
| **Weekly Review** | Six questions, the week's recorded numbers, past weeks |
| **Opportunities** | Application tracker; conference radar with official links |
| **Creator Lab** | Idea bank, pipeline, calendar |

## 10. How the home page decides things

**Today's Top 3.** Tasks you pinned for today come first and are labelled "Pinned by you". Remaining places are filled with suggestions, labelled "Suggested" with the reason. A suggestion scores higher when it is overdue or due soon, high priority, or in PhD or fitness. Business tasks that are neither urgent (due by tomorrow) nor high priority score lower, so they wait behind PhD and fitness. Tasks set aside with "Not today" or by Restart are left out until their date. There are no productivity scores.

**This week.** Actual figures are sums of your own time entries and completed workouts for Monday to Sunday. If nothing was logged, the line says so; it is never shown as zero hours worked. Planned figures are the targets you set. "Research papers processed" counts sources whose **date read** falls in the week.

**Restart mode.** Appears when the most recent record of any kind is three or more days old, or when you press **Restart today**. It shows one PhD action (your earliest open PhD task) and a short list of movement options, which are suggestions only. It can postpone overdue tasks for seven days, but only tasks that are not PhD, fitness or family, not high priority and not pinned. Postponing changes only the "set aside until" date: due dates, history and status are untouched, and nothing is deleted or marked done.

**Timers.** Stopping saves the elapsed minutes. A timer that has run for more than three hours asks for the minutes actually worked instead of saving the elapsed time.

## 11. Rules about data honesty

- No sample or invented records are ever inserted.
- Every number on screen is counted from rows you entered. Missing is shown as missing.
- Suggestions are labelled as suggestions and kept apart from your own choices.
- Historical imported records, current entries, suggestions and estimates are kept distinguishable: imported rows carry an `import_key`, approximate durations carry a flag, and unclear loads keep their original wording.
- Deadlines and outcomes are stored only when you enter them, and deadlines need a source link.
- No medical or nutritional diagnoses.
- This dashboard is separate from the RR Services operational system and does not connect to it.

## 12. How imports work

1. Files (JSON or CSV) are uploaded on the **Import data** page from your own device. They are read in memory and never stored on the server or in GitHub.
2. `aira/importer.py` validates every row: column names, types, allowed values, plausible weights, no completed workout or measurement dated in the future, and every set linked to a known workout.
3. The page compares each row's `import_key` with what is already stored and shows a preview split into "new" and "already stored".
4. Nothing is written until you tick the confirmation box. Only new rows are inserted, as the signed-in user, under Row Level Security. Existing rows are never updated or replaced.
5. The database enforces the same uniqueness rule, so a duplicate cannot get in even if the app had a bug.

## 13. Literature import notes

- The matrix export (`Literature_review_matrix.xlsx`, 18 Nov 2026) has 52 sources: 51 with a DOI and one identified by its Scopus EID. It has no authors, journal names or tags; those fields stay empty until filled by hand or from a Mendeley export.
- Its Methods, Results and Conclusions columns are summaries from the export, not Aira's notes. They are stored as source evidence and labelled with `summary_source`. 37 of the 52 were summarised from the abstract only (`summary_basis = abstract`); the page says so.
- Reading status is imported as "Not recorded", because the file does not say which papers have been read.
- Publication dates are kept as written; two are issue dates in late 2026 and January 2027.

## 14. Fitness rules

- A personal best is the heaviest recorded set for an exercise **within one unit and basis** (kg, lb, kg per side, kg per dumbbell, machine units). Ties go to the set with more reps. Planned and skipped sessions never count.
- Each exercise name is its own series, so "Leg press", "Icarian leg press" and "Precor leg press" are never compared.
- The weight line is a 14-day average of the entries actually recorded in that window. Days without an entry are not filled in.
- The weekly consistency chart counts completed workouts only. Weeks with nothing recorded show no bar.
- A planned session can only be marked done on or after its day.
- Editing a workout updates changed sets, adds new ones and deletes removed ones. Imported sets keep their import key, so re-importing the seed files never duplicates them.

