# Training Hub (Streamlit version)

A coaching app in the HubFit style. It runs on its own web address (not on Claude), with a real trainer login, a database, 3D animation uploads, and a phone-style app for your clients.

**You do the setup once, in about 30 minutes. It costs nothing on the free plans.**

## What is inside

**Clients see** a phone-style app with five tabs (🏠 Home, 🏋️ Training, 🌿 Habit, 🍎 Nutrition, 👤 Profile):
- Training: a week strip, the workout for each day with exercise animation, sets, reps, rest and notes, a **Start workout** mode that walks through each exercise and set, and calendar links.
- Habit: weekly progress and daily habit check-offs.
- Nutrition: record breakfast, lunch, dinner and snacks even without a trainer plan; calories and macros are optional. In Plan, mark an assigned meal as eaten or record what you ate instead, with daily reminders.
- Profile: weekly check-in, progress photo gallery (private), body-weight chart, and their details.
- **First login:** the client types their registered name and enters the starter PIN you gave them, chooses their own PIN, then enters height, weight, preferred diet, goal (fat loss or muscle gain) and training style (general fitness, men's physique or bodybuilding).

**You (the trainer) get**
- **Overview** dashboard with charts, check-in alerts and downloads.
- **Manage clients**: for each client, a programme made of **phases** (for example "Week 1 · General", then "Split programme"), each phase holding **days** with a weekday, each day holding exercises. You can:
  - add exercises from the **library**, or a blank one
  - edit sets, reps, rest, weight, notes and video link
  - **duplicate**, **move up or down**, or remove any exercise
  - **duplicate a day**, **copy a day to other clients**, **copy a whole programme** to other clients (add or replace)
  - set diet targets and meals, habits, coach notes, and see check-ins and photos
- **Exercise library**: the 21 exercises from your screenshots with their sets, reps and rest, ready to use. Upload a 3D animation for an exercise **once** and it shows for every client who has it. You can also override the animation for one client.

## Your 10 clients

On the empty Overview page, click **Set up my 10 clients**. It creates Anton, Dharan, Rekha, Divya, Venky, Sheethal, Varshni, Swetha, Guhan and Kevin:
- **Anton and Dharan**: Week 1 "General" (six exercises, 3 sets of 15 reps), then a split programme: Day 1 chest, Day 2 triceps, Day 3 lat, Day 4 biceps, Day 5 shoulder and legs (Monday to Friday). The programme starts today, so week 2 begins on its own after 7 days.
- **Rekha and Divya**: the four workouts from your screenshots (Upper body gym 1, Lower body gym 1, Upper body gym 2, Lower gym 2).
- **The other six**: empty programmes for you to fill in. Use **Copy** to speed this up.

You get a one-time list of **starter PINs**. Give each client theirs. Reset a PIN any time under Manage clients, Profile.

## Workout builder (pick exercises and add them to a client's day)

Open **Workout builder** in the sidebar.
1. Choose the **client**, the **phase** and the **day**. Pick "New day" to create one, for example "Chest day", and choose its weekday.
2. Tap a category: **Chest, Triceps, Lats / Back, Biceps, Shoulders, Legs, Abs, Fat loss, Muscle gain** (and Glutes, Calves, Cardio, Other). The number shows how many exercises are in each.
3. Each exercise shows its sets, reps and rest, its **YouTube link** (▶ Watch, or 🔎 Find to search YouTube), a 🔗 button to paste or change the link, and an **ADD** button.
4. Press **ADD** to add one exercise, or **tick** several (for example any 5 of your 10 chest exercises) and press **Add selected**. They land in the day you chose.
5. Optional: type sets and reps to use for the exercises you add, for example 3 and 15. Leave them empty to use each exercise's own numbers.
6. Optional: choose **Also add to these clients** to put the same exercises into the same-named day for other clients in one go.

An exercise that is already in the day is skipped, so you never add it twice by accident. You can remove exercises from the day right in the builder.

Your library starts with your 21 screenshot exercises plus about 45 more starters (chest, triceps, back, biceps, shoulders, legs, abs, fat loss, muscle gain). They have no YouTube links yet. Use 🔎 Find to search, then paste the link with 🔗. If your library was created earlier, open **Exercise library** and press **Add the extra starter exercises**.

An exercise can sit in more than one category. For example Barbell Bench Press shows under Chest and under Muscle gain. Set this under Exercise library, "Also show under".

## Two shortcuts you asked for

**YouTube links until you have your own videos.** Open **Exercise library**.
- Click **Paste YouTube links for many exercises at once**. The box lists every exercise name. Paste one line per exercise, the name then a comma then the link, and click **Apply links**.
- Or open one exercise and paste its YouTube link in that exercise's form.
- A link in the library shows for **every client** who has that exercise. To give one client a different video, paste a link in that client's exercise under Manage clients, Programme. When you later upload your own animation, it shows instead of the link.

**Drop a diet PDF to fill the diet plan.** Open **Manage clients**, pick the client, open **Diet and habits**, and drop the PDF in the box at the top.
- The app reads the daily targets (calories, protein, carbs, fat) and the meals with their times.
- You see everything in a table first. Fix anything, choose to replace or add to the current meals, tick other clients if the same plan applies to them, then click **Apply**.
- It works best when each meal has a name (Breakfast, Lunch, Dinner) or a time (8:00 AM). It cannot read scanned photos of a page. If a PDF has no readable text, the app tells you.
- A plan with several days or options on one PDF will come out as one long list of meals. Edit it in the table before you apply.

## Step 1: Put the files on GitHub

1. Create a free account at github.com.
2. Click **New repository**, name it `training-hub`, choose **Private**.
3. Click **uploading an existing file**, drag in everything from this folder (`app.py`, `dietpdf.py`, `requirements.txt`, `.gitignore`, and the `.streamlit` folder with `config.toml`), then **Commit changes**.
4. Do **not** upload a file called `secrets.toml`. Your real passwords go into Streamlit in Step 3.

## Step 2: Create the database (Supabase)

1. Create a free account at supabase.com and click **New project**. Pick a strong database password and the region closest to you.
2. Open **SQL Editor, New query**, paste this, and click **Run**:

```sql
create table if not exists app_rows (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table app_rows enable row level security;
```

3. Open **Storage** and create **two** buckets:
   - `videos`, with **Public bucket** switched **on** (for exercise animations)
   - `photos`, with **Public bucket** switched **off** (for progress photos, so only the app can read them)
4. Open **Project Settings, then API**. Copy the **Project URL** and the **service_role** key (the long secret one, not "anon"). Keep the service_role key private.

## Step 3: Publish the app (Streamlit Community Cloud)

1. Go to share.streamlit.io and sign in with GitHub.
2. Click **Create app**, choose your `training-hub` repository, branch `main`, main file `app.py`.
3. Open **Advanced settings, then Secrets**, and paste (with your own values):

```toml
TRAINER_PASSWORD = "choose-a-long-password-only-you-know"
TIMEZONE = "America/Toronto"

[supabase]
url = "https://YOUR-PROJECT-ID.supabase.co"
service_key = "YOUR-SERVICE-ROLE-KEY"
```

4. Click **Deploy**. You get an address like `your-name.streamlit.app`. That is the link you send to clients.

## First use

1. Open your app, tap **I am the trainer**, and log in.
2. On Overview, click **Set up my 10 clients** and save the starter PINs.
3. Open **Exercise library**. Until you have your own animations, use **Paste YouTube links for many exercises at once**: one line per exercise (`Dumbbell Bench Press, https://youtu.be/...`). The link then shows for every client who has that exercise. When you upload an animation for an exercise (one at a time, or with **Bulk upload** where each file is named after the exercise, for example `Dumbbell Bench Press.gif`), the animation shows instead of the link. A link or animation you add to one client's exercise always wins for that client.
4. Open **Manage clients** to adjust anyone's plan. Fill in the six empty clients by adding exercises from the library or copying a day or whole programme.
5. Send each client the link and their starter PIN.

## Good to know

- **Animations:** only upload animations you made or have a licence to use. The app does not include any animation files.
- **Files:** uploads are limited to 50 MB each (the Supabase free limit).
- **Privacy:** a client who logs in sees only their own data. Progress photos are stored in a private bucket and are only read by the app on the server. The login screen has a typed name field and does not show the client list.
- **PIN guessing:** after 5 wrong PINs in one visit, that visit is locked. Use 4 digits that are not obvious.
- **Steps from the phone:** the app cannot read a phone's step counter. Clients can log steps as a habit tick instead.
- **Sleeping apps:** free Streamlit apps sleep after a few quiet days and wake with one click. Free Supabase projects pause after about a week of no use. You can restart a paused project from the Supabase dashboard and nothing is lost.
- **Backups:** use the Download buttons on Overview now and then, and export the `app_rows` table from Supabase.
- **Timezone:** "today" follows `TIMEZONE`. Change it in Secrets if you move.

## Running it on your own computer (optional)

```
pip install -r requirements.txt
streamlit run app.py
```

Without Supabase settings it runs in local test mode and saves to a `data` folder. Add `.streamlit/secrets.toml` with `TRAINER_PASSWORD` to log in as trainer.

### Workout drafts and Apply

In Workout builder, add or remove exercises, then press **Apply workout to client**.
Until you apply, the client keeps their current plan. Apply publishes the selected
phase and the revised plan, including removals. Existing exercise completion
history is retained. General and Split program are shown without week labels.
Choose General and Apply whenever a client needs it between split workouts.
General stays active until you choose Split program and Apply again. You decide
the duration; there is no automatic timer. Both plans remain saved.

In Exercise library, use **Select for General** across categories, review the
selection basket, and press **Send selection to General draft**. This replaces
the General draft's exercises with your selection. Open Workout builder to
review the draft and Apply it. Drafts last for the current trainer session;
apply before closing the app. These changes are prepared for later deployment.

### Client activity and diet progress

Habit includes daily manual entry of steps and calories burned from a tracker, with charts for the last 30 recorded days. Saving the same date updates its entry. Nutrition shows seven-day food logging, planned meal completion and substitutions. Trainer suggestions display assigned diet targets separately from optional client calorie entries.

### Guided and bonus workouts

Clients can start a workout on today's or a past selected day, mark each exercise done and move to the next, then complete the session. Bonus exercises appear below the main workout and have separate completion. In Workout builder, select **Add selected exercises as bonus workout**, add exercises and Apply. Main and bonus completions appear in the trainer's recent client activity.

### Returning to the app

Clients can check **Keep me signed in on this device** when logging in on their own phone or computer. The app remembers that device for up to 30 days across page refreshes and reopening. **Profile → Log out** removes that device's access. Resetting or changing the client PIN invalidates existing remembered logins. Private browsing or clearing browser storage requires signing in again. Persistent data storage through Supabase is needed to keep sessions across server restarts; local test storage can reset on Streamlit Cloud.
