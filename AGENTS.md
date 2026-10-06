# Training Hub: project handoff

Read this first. It is the context from the conversation where this app was designed and built.

## What this is

A coaching app for one personal trainer (the owner, not a developer) and his clients. It runs on Streamlit Community Cloud with Supabase for data. Clients use it on their phones. The owner builds their plans on a laptop.

- **Trainer side** (password from Streamlit secrets): Overview dashboard, Manage clients, Workout builder, Exercise library.
- **Client side** (name + PIN): a phone-style app with five tabs (Home, Training, Habit, Nutrition, Profile), styled like the HubFit app (dark blue, rounded cards, bottom nav).

The owner's clients: Anton, Dharan, Rekha, Divya, Venky, Sheethal, Varshni, Swetha, Guhan, Kevin. The "Set up my 10 clients" button creates them with starter plans (see Decisions below).

## Files

- `app.py` is the whole app (about 2,000 lines). Sections in order: settings and helpers, CSS, storage backends, exercise library, clients/programs/security, calendar helpers, exercise display, events, client app (onboarding and tabs), trainer overview, trainer manage, diet PDF import, workout builder, exercise library page, trainer shell, entry point.
- `dietpdf.py`: rule-based PDF diet reader (no Streamlit imports). Extracts daily targets and meals with times.
- `tests/test_app.py`: smoke tests using Streamlit's `AppTest`. Run `pip install -r requirements.txt -r requirements-dev.txt` then `pytest -q`. All 6 pass.
- `.streamlit/config.toml`: dark theme and 50 MB upload limit. `.streamlit/secrets.toml.example`: shows the secrets the app needs. Never commit real secrets.
- `README.md`: owner-facing setup guide (GitHub, Supabase, Streamlit). Keep it accurate and non-technical when you change behaviour.

## Run locally

```
pip install -r requirements.txt
streamlit run app.py
```

Without Supabase secrets it uses a local JSON store in `data/` (git-ignored). For trainer login locally, create `.streamlit/secrets.toml` with `TRAINER_PASSWORD = "..."`. Set `TH_DATA_DIR` to change the data folder.

## Data model

Storage is a table `app_rows(id text primary key, data jsonb)` in Supabase (or `data/store.json` locally). One row per client (id starts with `c_`) plus one row `lib` for the exercise library.

Client row: `name, trainer, created, pin_hash, pin_salt, must_change_pin, onboarded, profile{height_cm, weight_kg, diet, goal, style, notes}, program{start, phases[{id, name, weeks (0 = ongoing), days[{id, title, weekday (-1 = any, 0 = Mon), exercises[{id, lib_id, name, group, sets, reps, rest, target, notes, video, media}]}]}], diet{macros{kcal,p,c,f}, meals[{id,time,text}]}, habits[], events[{d,k,ref,label,...}], weights[], checkins[], food_log[], photos[], coach_notes[]`.

- `events` are what clients tick off: `k` is `ex`, `meal` or `habit`; `d` is the date in the configured timezone.
- Library item: `id, name, group, tags[], equipment, sets, reps, rest, target, cue, media, video`. `tags` lets one exercise appear under several categories. Video precedence for display: client animation, client link, library animation, library link.
- Phases switch automatically by week number from `program.start`.

## Security model (keep it)

- Trainer password is compared on the server against `st.secrets["TRAINER_PASSWORD"]`.
- Clients get a random starter PIN from the trainer (shown once), must choose their own PIN at first login, then fill in height, weight, diet, goal (Fat loss or Muscle gain) and style. PINs are stored as salted PBKDF2 hashes. 5 wrong PINs per session locks that session.
- A client only ever loads their own row. The login screen lists names only.
- Progress photos go to a **private** Supabase bucket (`photos`) and are read server-side by the app. Exercise animations go to a public bucket (`videos`).
- The Supabase `service_role` key stays server-side in Streamlit secrets. Row-level security is on with no policies.

## Conventions and gotchas

- Needs Streamlit 1.50 or newer: uses `width="stretch"`, `st.pills`, `st.segmented_control`, `type="tertiary"`.
- Widget state disappears when a widget is not rendered in a run. Guided-workout progress therefore lives in `ss["gw"]` (updated through `on_change` callbacks), not in widget keys.
- Callbacks (`on_click`) are used where state must change before the next render (builder ADD, workout stepper).
- Never set a widget's session state after the widget has been created in the same run. The code uses `_add_sel`, `_reset_sel` and callbacks for this.
- Writes are whole-row, last-writer-wins. Only one client edits their own row at a time, which is fine for this scale.
- All user text shown with `unsafe_allow_html=True` must go through `esc()`.
- Dates and "today" use `TIMEZONE` from secrets (default `America/Toronto`).

## Decisions and assumptions that need the owner's confirmation

1. Anton and Dharan: Week 1 "General" uses six exercises chosen by the assistant (bench, lat pulldown, shoulder press, leg press, curl, triceps pushdown), all 3 sets of 15. The split days (Chest, Triceps, Lat, Biceps, Shoulder and Legs, Monday to Friday) use the library's default sets and reps, and have only 2 to 6 exercises each.
2. Rekha and Divya: the four screenshot workouts, scheduled Mon, Tue, Thu, Fri. The order of some exercises inside a day was guessed.
3. No trainer name is assigned to any client yet.
4. About 45 starter exercises were added beyond the 21 from the owner's screenshots. Names and coaching cues are original. None has a video link.

## Not tested

- The Supabase backend (REST calls and Storage uploads/reads). Written carefully but never run against a real project.
- File uploads (animations, photos, diet PDF in the real browser). The diet reader is tested on generated PDFs only.
- Visual layout on real phones. The bottom nav is pinned with CSS targeting `.st-key-bottomnav`, which depends on Streamlit's DOM and may need tuning.
- Streamlit Community Cloud deployment.

## Do not

- Do not commit `.streamlit/secrets.toml`, keys, or the `data/` folder.
- Do not add exercise animations copied from other apps (the HubFit screenshots were only a design reference). The owner must upload animations he made or is licensed to use.
- Do not read a phone's step counter (not possible from a web app). Steps are a habit tick.

## Likely next steps

1. Deploy: GitHub, then Supabase (table SQL plus buckets `videos` public and `photos` private), then Streamlit Community Cloud with secrets. See `README.md`.
2. Add YouTube links for the exercises (Exercise library, or the link button in the Workout builder).
3. Fill in the six empty client programs using the Workout builder and the copy tools.
4. Ideas the owner has not asked for yet: notifications or reminders, a rest timer in the guided workout, a plan-templates feature, an export of one client's full history.
