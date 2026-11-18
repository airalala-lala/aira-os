# AIRA OS 2.0: setup guide (Phase 1)

This guide gets you from nothing to a working, private dashboard on your MacBook and iPhone. You do not need to install Python or use the Terminal. Everything happens in three websites: Supabase, GitHub and Streamlit Community Cloud.

Allow about 40 minutes. Do the parts in order.

> Button names on these websites change from time to time. If a label is slightly different from what is written here, look for the closest match.

**What Phase 1 gives you**

- A sign-in screen. Nothing personal is visible without your email and password.
- **Today's Top 3:** tasks you pinned, then suggestions. PhD and fitness come before non-urgent business.
- **My focus today:** a PhD focus timer, today's workout, and one important task.
- **This week:** actual versus planned for PhD hours, workouts, business hours and family time, counted only from what you logged.
- **Restart today:** after three quiet days, one small PhD action and one short movement option instead of a list of overdue work.
- Tasks, time entries and workouts that you can add, edit and delete.
- Settings (name, weekly targets, business limit, password), backup download and data import.
- The six modules are shown honestly as "Not built yet" until each one is built.

**Already set up an earlier version?** Nothing needs to be deleted. Run any migration files you have not run yet (step A2), then replace the files in your GitHub repository with the new ones (step B2). Your database records are not touched.

---

## Part A: Supabase (your database and login)

### A1. Create a new project

1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **New project**.
3. Fill in:
   - **Name:** `aira-os`
   - **Database password:** click **Generate a password**, then copy it into your password manager. You will rarely need it, but you cannot see it again later.
   - **Region:** `Southeast Asia (Singapore)`
4. If you see a tick-box about automatically exposing new tables to the Data API, leave it **unticked**. The migration files grant access deliberately.
5. Click **Create new project** and wait a minute or two until it finishes setting up.

Use a brand-new project for AIRA OS. Do not reuse a project that holds anything else, so your personal records stay separate.

### A2. Create the database tables

There are seven SQL files in the `supabase/migrations` folder. Run them **in number order**, one at a time.

1. In the left sidebar, click **SQL Editor**.
2. Click **New query** (or the **+** button).
3. On your MacBook, open `supabase/migrations/0001_foundation.sql` in TextEdit. Select everything (Cmd+A) and copy (Cmd+C).
4. Paste into the Supabase query box (Cmd+V).
5. Click **Run**. If Supabase warns that the query contains destructive operations, that is expected (it removes old security rules before re-creating them). Confirm.
6. You should see **Success. No rows returned**.
7. Repeat steps 2 to 6 for each of these, in this order:
   - `0002_storage.sql`
   - `0003_history_tables.sql`
   - `0004_command_centre.sql`
   - `0005_phd_hub.sql`
   - `0006_fitness_studio.sql`
   - `0007_global_opportunities.sql`

Every file is safe to run more than once. If you ever re-run an older file, run the later ones again afterwards too, in order.

### A3. Check the security rules

1. New query again. Paste the contents of `supabase/verify_security.sql` and click **Run**.
2. The editor shows the result of the last query. You should see fifteen rows, one per table, each with grantee `authenticated`. There must be **no row with grantee `anon`**.
3. Then open **Table Editor** in the left sidebar. None of the tables should show an "RLS disabled" or "Unrestricted" warning.

### A4. Create your one user account

1. In the left sidebar, click **Authentication**, then **Users**.
2. Click **Add user**, then **Create new user**.
3. Enter your email address and a strong password of at least 12 characters. Save it in your password manager.
4. Make sure **Auto Confirm User** is ticked.
5. Click **Create user**.

### A5. Switch off public sign-ups

This makes sure nobody else can ever create an account in your project.

1. Still under **Authentication**, open **Sign In / Providers** (on some screens it is under **Configuration**).
2. Find **Allow new users to sign up** and turn it **off**.
3. Click **Save**.

### A6. Copy your two connection values

1. Click **Project Settings** (the cog icon), then **API Keys**.
2. Under **Publishable key**, copy the value that starts with `sb_publishable_`. Paste it into a temporary note.
   - If you only see a **Create new API keys** button, click it first.
   - **Never copy the Secret key** (`sb_secret_...`) or the legacy `service_role` key. AIRA OS does not need them and refuses to start if you paste one in.
3. Find your **Project URL**. It is in **Project Settings**, under **Data API** (or behind the **Connect** button at the top of the page). It looks like `https://abcdefghijklmnop.supabase.co`. Copy it into the same note.

---

## Part B: GitHub (where the code lives)

### B1. Create a private repository

1. Go to [github.com](https://github.com) and sign in.
2. Click the **+** at the top right, then **New repository**.
3. **Repository name:** `aira-os`
4. Choose **Private**.
5. Do not tick any of the "Add a README", ".gitignore" or "license" options.
6. Click **Create repository**.

### B2. Upload the project files

1. On your MacBook, double-click `aira-os.zip` to unzip it. You get a folder named `aira-os`.
2. Open that folder in Finder.
3. Press **Cmd + Shift + .** (full stop). Hidden files such as `.streamlit`, `.gitignore` and `.env.example` now appear, slightly greyed out. This step matters: without it the theme file is left behind.
4. On the GitHub page for your new repository, click the link **uploading an existing file**.
5. In Finder, click inside the `aira-os` folder, press **Cmd + A** to select everything, and drag it all onto the GitHub page. Use Chrome if Safari does not keep the folders.
6. Wait for the upload list to finish. Check that it includes `app.py`, `requirements.txt`, and paths beginning with `aira/`, `views/`, `supabase/` and `.streamlit/`.
7. Click **Commit changes**.
8. Press **Cmd + Shift + .** again in Finder to hide the hidden files.

Your repository's front page should now show `app.py` at the top level, not inside another folder. If you see only a single `aira-os` folder, the files went in one level too deep: delete the repository and repeat B2, dragging the *contents* of the folder rather than the folder itself.

---

## Part C: Streamlit Community Cloud (where the app runs)

### C1. Create the app

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
2. Click **Create app**, then **Deploy a public app from GitHub** (the name is misleading; it also handles private repositories).
3. Fill in:
   - **Repository:** `your-github-username/aira-os`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** choose something not easily guessed, for example `aira-os-` followed by a few random letters.
4. Click **Advanced settings**.
   - **Python version:** `3.12`
   - **Secrets:** paste the three lines below, replacing the values with your own. Keep the quote marks.

```toml
SUPABASE_URL = "https://YOUR-PROJECT-REF.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_REPLACE_ME"
ALLOWED_EMAIL = "you@example.com"
```

   `ALLOWED_EMAIL` must be exactly the email you used in step A4.

5. Click **Save**, then **Deploy**. The first start takes two to five minutes while packages install.

If Streamlit cannot see your private repository, click your profile picture, open **Settings**, and grant access to private repositories under **Linked accounts**.

### C2. Check who can open the app

1. On [share.streamlit.io](https://share.streamlit.io), find `aira-os`, click the **⋮** menu, then **Settings**, then **Sharing**.
2. If it offers **Only specific people can view this app**, choose that. This adds Streamlit's own sign-in as an extra outer door.
3. If Streamlit says you have reached the limit for private apps, it is acceptable to leave the app viewable by link. A visitor who finds the address sees only the sign-in screen, and your records are protected by Supabase login and Row Level Security either way.

---

## Part D: Test it

Work through this list. Every line should behave as described.

| # | Do this | You should see |
|---|---|---|
| 1 | Open your app's address on your MacBook | Only the AIRA OS sign-in card. No menu, no data |
| 2 | Sign in with a wrong password | "That email or password is not correct." |
| 3 | Sign in with the right email and password | The home page, with "No priorities yet" and "No tasks yet" boxes |
| 4 | Look at "This week" | Every line says nothing is logged and no target is set. No numbers are invented |
| 5 | Open **Add a task**, type a title, choose area **PhD**, click **Save task** | The task appears under "Today's Top 3" marked "Suggested" |
| 6 | Add a second task with area **Business** and no due date | It appears below the PhD task |
| 7 | Click **Start PhD focus** | A gold "PhD timer running" banner appears at the top |
| 8 | Wait a minute, then click **Stop and save** | Under "This week", PhD focused hours shows "1 min logged" |
| 9 | Open **Plan or log a workout**, leave status as Completed, click **Save workout** | "Movement" shows "Done today", and workouts completed shows 1 |
| 10 | Open **Settings**, enter a display name and click **Save profile**; enter weekly targets and click **Save targets**; go back to **Home** | The greeting has your name and "This week" shows bars against your targets |
| 11 | On your iPhone, open the same address in Safari and sign in | The same tasks and numbers, and a bar of five buttons along the bottom of the screen |
| 12 | On the iPhone, click **Done** on a Top 3 task | It leaves the Top 3 |
| 13 | On the MacBook, click **Refresh** at the bottom of the home page | The change made on the iPhone is there |
| 14 | Click **Restart today** at the bottom of the home page | A calm card with one PhD action and one short movement option. Click **Show my full dashboard** to go back |
| 15 | Open a task under "All tasks", tick **Yes, delete this task permanently**, click **Delete task** | The task is gone |
| 16 | **Settings → Prepare backup → Download full backup (JSON)** | A file downloads containing your records |
| 17 | Click **Sign out** in the sidebar | Back to the sign-in card |

Times and dates on screen should be Malaysia time. The colours follow your device: ivory in light mode, dark in dark mode.

When these pass, tell me "Phase 1 works" and we start the PhD Research Hub. If any line fails, tell me its number and what you saw instead. A screenshot helps most for lines 11 and 14, because the phone layout is the part I could not test here.

## Part E: import your personal history (after Part D passes)

Your history (goals, PhD details, weight records, workouts and individual sets) is prepared as files in a separate folder, `aira-os-seed-data`. That folder stays on your MacBook and is **not** uploaded to GitHub.

1. Read `PREVIEW.md` in the `aira-os-seed-data` folder. It lists every record, and one decision for you about which workout history to import.
2. Open AIRA OS, sign in, and click **Import data** in the sidebar.
3. Click **Browse files**, open the `aira-os-seed-data` folder, and select the nine `.json` and `.csv` files (leave out the two `.md` files).
4. The number of new records should match the total at the top of `PREVIEW.md`, with 0 already stored. Open each row to check the detail.
5. Tick the confirmation box and click **Import**.
6. To prove duplicates are blocked, upload the same nine files again. It should say everything is already stored.

After the import, the home page will probably open on the **Restart today** card, because your most recent recorded workout is 31 October. That is expected. Click **Show my full dashboard** to see everything.

The imported records are saved and included in your backup download. The screens for viewing, charting and editing them arrive with each module (PhD Hub in Phase 2, Fitness Studio in Phase 3). Until then you can see and edit them in Supabase under **Table Editor**.

## Part F: PhD Research Hub (Phase 2a)

### F1. Update the database

1. In Supabase, open **SQL Editor**, then **New query**.
2. Paste the contents of `supabase/migrations/0005_phd_hub.sql` and click **Run**. You should see **Success. No rows returned**.

### F2. Update the app

Upload the whole project to GitHub again, the same way as before: open the repository's front page, **Add file → Upload files**, drag in everything from the unzipped `aira-os` folder (with hidden files showing), and **Commit changes**. Wait about two minutes for Streamlit to update.

### F3. Import your literature matrix

1. Open AIRA OS and click **Import data** in the sidebar.
2. Click **Browse files** and choose your `Literature_review_matrix.xlsx`.
3. The preview should show **52 new records** under Literature sources.
4. Tick the confirmation box and click **Import**.

The Excel file stays on your MacBook. Only its rows go into your private database.

### F4. Test it

| # | Do this | You should see |
|---|---|---|
| 1 | Open **PhD Research Hub** | Four tabs: Overview, Literature, Supervision, Timeline. Overview shows 52 sources, 7 open feedback items and 0 of 9 milestones completed |
| 2 | **Literature** tab: type `Malaysia` in Search | The table shows only matching sources |
| 3 | Tap a row in the table | That source opens above the table, with a note saying where its summaries came from |
| 4 | Tap **Mark as read today** | On Home, "Research papers processed" shows 1 recorded |
| 5 | Open **Edit this source**, write something in **My critical notes**, add a tag, **Save changes** | Your note appears under "My thinking", separate from the source's findings |
| 6 | **Add a source** with the same DOI as one you have | "This looks like a source you already have" |
| 7 | **Supervision** tab: tick one feedback item | It stays ticked after a refresh |
| 8 | **Record a meeting**, then add an action item with a deadline | The action item also appears as a PhD task on Home |
| 9 | **Timeline** tab: give one milestone a planned date and **Save** | A chart appears with that milestone |
| 10 | Enter your semester dates and **Save semester dates** | Shaded semester bands appear on the chart |
| 11 | In **Settings**, set **Research papers processed per week** | Home shows papers against your target |

## Part G: Fitness Studio (Phase 3)

### G1. Update the database

In Supabase, open **SQL Editor**, then **New query**. Paste the contents of `supabase/migrations/0006_fitness_studio.sql` and click **Run**. You should see **Success. No rows returned**.

### G2. Update the app

Upload the whole project to GitHub again, the same way as before, and wait about two minutes.

### G3. Test it

| # | Do this | You should see |
|---|---|---|
| 1 | Open **Fitness Studio** | Five tabs: Overview, Log, Progress, Weight, Plan. Overview shows your last recorded workout (31 Oct) and last recorded weight (66.10 kg), labelled as not today's weight |
| 2 | **Weight** tab | A chart of your 7 weights, a 14-day average line and a dotted 50 kg goal line |
| 3 | **Log** tab: open **Repeat a previous session**, choose 31 Oct, tap **Copy into the log below** | The table fills with that session's exercises. Change any reps or loads, then **Save workout** |
| 4 | **Progress** tab: choose **Precor leg press** | Its history, with loads shown as "kg per side" |
| 5 | **Personal bests** | One row per exercise and unit. Chest press stays in lb |
| 6 | **Plan** tab: read the suggested weekly plan and tap **Use this plan** (or **Adjust before using** first) | This week's sessions from today onward appear, each with its exercises and your last recorded loads. Tick **Done** on the day. Next week fills itself when you open it |
| 7 | Open a past workout in **Log**, switch on **Edit this workout**, change one number, **Save changes** | Only that set changes |

Only enter real sessions and measurements. Delete any test entries you make.

## Part H: Global Opportunities (Phase 6)

### H1. Update the database

In Supabase, open **SQL Editor**, then **New query**. Paste the contents of `supabase/migrations/0007_global_opportunities.sql` and click **Run**. You should see **Success. No rows returned**.

### H2. Update the app

Upload the whole project to GitHub again, the same way as before, and wait about two minutes.

### H3. Import the opportunities

1. Open AIRA OS and click **Import data**.
2. Choose `07_opportunities_2027.json` from the new `aira-os-seed-data` folder.
3. The preview should show **13 new records**. Tick the box and click **Import**.

### H4. Test it

| # | Do this | You should see |
|---|---|---|
| 1 | Open **Global Opportunities** | Four tabs: Closing soon, Applied, Watch list, Past. A yellow note lists deadlines in the next 14 days |
| 2 | **Closing soon** | Each card shows days left, where and when, fit, next step and an **Official page** button |
| 3 | On **Home** | A "Deadlines coming up" list for anything closing within 14 days |
| 4 | Tap **Applied** on something you have really submitted | It moves to the Applied tab with today's date, and leaves the Home reminder |
| 5 | In **Applied**, tap **Accepted** or **Not successful** when you hear back | It moves to Past |
| 6 | **Add an opportunity** with a deadline but no source link | "Please add the link where you found the deadline" |

### Add it to your iPhone Home Screen

In Safari, open the app, tap the **Share** button, then **Add to Home Screen**. It then opens like an app. Let Safari save your password so signing in is one tap.

---

## Troubleshooting

| What you see | Likely cause | Fix |
|---|---|---|
| "AIRA OS is not configured yet. Missing settings: …" | The Secrets box is empty or a name is misspelt | Streamlit app **Settings → Secrets**. Paste the three lines again, check the names exactly, **Save** |
| "The key you provided is a SECRET / service_role key" | The wrong key was pasted | Replace it with the `sb_publishable_` key. Then in Supabase, delete that secret key and create a new one, since it has been pasted somewhere it should not be |
| "That email or password is not correct" with the right password | `ALLOWED_EMAIL` does not match the Supabase user's email | Make them identical, including spelling |
| "A database table is missing" | A migration was not run | Repeat step A2. All seven files are needed, in number order |
| "The database refused this request (permission denied)" | A migration only partly ran | Run all seven files again in order; it is safe to repeat |
| No bar of buttons at the bottom on iPhone | The phone layout needs adjusting | Use the **>** arrow at the top left to open the menu, and send me a screenshot |
| A timer was left running overnight | You forgot to stop it | The banner asks for the minutes you actually worked, or click **Discard this timer** |
| "Could not reach the database" or "Could not reach Supabase" | The Supabase project is paused after a quiet week, or there is no internet | Supabase dashboard → your project → **Resume project** |
| "This app has gone to sleep" | Streamlit pauses apps that have had no visits for about 12 hours | Click the wake-up button and wait up to a minute |
| "ModuleNotFoundError" on the Streamlit page | `requirements.txt` is not at the top level of the repository | Check step B2: `app.py` and `requirements.txt` must sit side by side |
| The app looks plain, with default colours | The hidden `.streamlit` folder was not uploaded | In GitHub: **Add file → Create new file**, name it `.streamlit/config.toml`, paste the contents of that file from your unzipped folder, commit |
| Asked to sign in again after a reload | Expected. Sign-in lasts for one open tab | Let your browser save the password |

To see detailed error logs: on your app page, click **Manage app** at the bottom right.

---

## Optional: run it on your MacBook

Not needed for normal use. Only do this if you want to try changes before they go live.

1. Install Python 3.12 from [python.org/downloads](https://www.python.org/downloads/).
2. Open **Terminal** (Cmd + Space, type `Terminal`, press Return).
3. Type `cd ` (with a space after it), drag the `aira-os` folder onto the Terminal window, and press Return.
4. Run these three lines one at a time:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5. Run `cp .env.example .env`, then `open -e .env`, replace the three placeholder values with your own, and save.
6. Run `streamlit run app.py`. Your browser opens the app at `http://localhost:8501`.
7. Press **Ctrl + C** in Terminal to stop it.

The `.env` file is listed in `.gitignore`. Never upload it to GitHub.

### Run the basic tests

The tests check the logic behind the Top 3, weekly progress, Restart mode and the importer. They need no internet and no database:

```bash
python3 -m unittest discover tests -v
```

You should see `OK` at the end.

---

## Safety rules for this project

- The only key the app ever uses is the **publishable** key.
- Secrets live in exactly two places: the Streamlit **Secrets** box and, optionally, the `.env` file on your MacBook. Never in GitHub.
- Migration files are run once, in number order, and are not edited afterwards. Changes come as new numbered files.
- Backup files contain your personal records. Keep them out of the GitHub folder.

The full design for all six modules, the database plan and the screen-by-screen plan are in `docs/ARCHITECTURE.md`.
