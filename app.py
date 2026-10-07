"""Training Hub (Streamlit)

Trainer: password login, client programs (phases, days, exercises), exercise library with 3D
animation uploads, copy tools, diet, habits, coach notes, check-ins and photos.
Clients: starter PIN -> choose own PIN -> height / weight / diet / goal -> mobile-style app
(Home, Training, Habit, Nutrition, Profile).
Data: Supabase when configured, otherwise a local JSON file for testing.
"""
import copy
import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import uuid
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import requests
import streamlit as st

from dietpdf import extract_text, parse_diet

st.set_page_config(page_title="Training Hub", page_icon="🏋️", layout="wide")

# ----------------------------------------------------------------------------
# Settings and small helpers
# ----------------------------------------------------------------------------
def secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


TZ = ZoneInfo(secret("TIMEZONE", "America/Toronto"))
DATA_DIR = Path(os.environ.get("TH_DATA_DIR", Path(__file__).parent / "data"))
PALETTE = ["#4A94F2", "#F59E0B", "#A78BFA", "#34D399", "#F472B6", "#22D3EE", "#FB7185", "#FACC15", "#60A5FA", "#C084FC"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DIETS = ["Vegetarian", "Non-vegetarian", "Eggetarian", "Vegan", "No preference"]
GOALS = ["Fat loss", "Muscle gain"]
STYLES = ["General fitness", "Men's physique", "Bodybuilding"]
MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner", "Snacks"]
NAV = ["🏠", "🏋️", "🌿", "🍎", "👤"]
NAV_NAMES = {"🏠": "Home", "🏋️": "Training", "🌿": "Habit", "🍎": "Nutrition", "👤": "Profile"}
esc = html.escape


def now():
    return dt.datetime.now(TZ)


def today():
    return now().date().isoformat()


def uid():
    return uuid.uuid4().hex[:8]


def dobj(s):
    return dt.date.fromisoformat(s)


def starter_pin():
    return f"{secrets.randbelow(10000):04d}"


def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


ss = st.session_state
ss.setdefault("trainer_ok", False)
ss.setdefault("client_id", None)
ss.setdefault("mode", "client")

# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown(
    """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown { font-family: 'Inter', sans-serif; }
.stApp { background: #101114; }
[data-testid="stSidebar"] { background: #16171B; border-right: 1px solid #24262C; }
.block-container { padding-top: 1.4rem; max-width: 1200px; }
h1, h2, h3 { letter-spacing: -0.01em; }
.th-card { background: #1B1C21; border: 1px solid #25272E; border-radius: 22px; padding: 18px 20px; margin-bottom: 14px; }
.th-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin-bottom: 8px; }
.th-kl { color: #9AA0AA; } .th-kv { font-size: 2.4rem; font-weight: 600; line-height: 1.15; margin: 4px 0 10px; }
.th-pill { display: inline-block; border-radius: 999px; padding: 3px 11px; font-size: .88rem; font-weight: 600; }
.th-up { background: #123524; color: #5BE49B; } .th-dn { background: #3B1B1F; color: #FF8A91; } .th-neu { background: #2A2C33; color: #AEB4BE; }
.th-chip { display: inline-block; background: #2A2C33; border-radius: 12px; padding: 6px 13px; margin: 0 8px 8px 0; font-weight: 600; font-size: .95rem; }
.th-banner { min-height: 150px; border-radius: 26px; background: linear-gradient(135deg, #0A3F8F 0%, #1763D1 55%, #0B2E6B 100%); display: flex; flex-direction: column; justify-content: flex-end; padding: 18px 20px; margin: 4px 0 10px; }
.th-banner h2 { margin: 0 0 10px; padding: 0; font-size: 1.7rem; color: #E8EEF9; }
.th-tag { display: inline-block; border: 1px solid #6EA3F5; color: #CFE0FB; border-radius: 10px; padding: 4px 10px; font-size: .78rem; font-weight: 700; letter-spacing: .06em; width: fit-content; }
.th-head { background: linear-gradient(180deg, #4A94F2, #3A82E0); border-radius: 0 0 34px 34px; padding: 22px 20px 34px; margin: -1.4rem -1rem 16px; color: #fff; }
.th-head .d { letter-spacing: .12em; font-size: .8rem; opacity: .85; text-transform: uppercase; } .th-head .g { font-size: 1.5rem; font-weight: 600; margin-top: 4px; }
.th-head .t { text-align: center; font-weight: 600; font-size: 1.15rem; margin-bottom: 14px; }
.th-title { text-align: center; font-weight: 600; font-size: 1.2rem; margin: 2px 0 14px; }
.th-ring { border-radius: 50%; display: grid; place-items: center; flex-shrink: 0; }
.th-ring > div { border-radius: 50%; background: #1B1C21; display: grid; place-items: center; text-align: center; line-height: 1.1; }
.th-ring small { color: #9AA0AA; display: block; font-size: .72rem; }
.th-stat { display: grid; grid-template-columns: auto 1fr; gap: 16px; align-items: center; }
.th-macros { display: grid; grid-template-columns: repeat(3, 1fr); text-align: center; gap: 6px; }
.th-macros b { display: block; font-size: 1.05rem; } .th-macros span { color: #9AA0AA; font-size: .85rem; }
.th-note { color: #9AA0AA; font-size: .95rem; }
.th-empty { text-align: center; color: #9AA0AA; padding: 26px 8px; }
.th-bars { display: flex; gap: 8px; align-items: flex-end; height: 70px; margin-top: 8px; }
.th-bars div { flex: 1; text-align: center; font-size: .72rem; color: #9AA0AA; } .th-bars i { display: block; background: #4A94F2; border-radius: 6px 6px 2px 2px; min-height: 4px; margin-bottom: 4px; }
.th-av { width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 600; font-size: 1.2rem; background: #5B6BD6; }
.th-cc { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
.th-cc .th-card dl { margin: 8px 0 0; display: grid; gap: 4px; color: #9AA0AA; } .th-cc .th-card dl div { display: flex; justify-content: space-between; } .th-cc dd { margin: 0; color: #F2F3F5; font-weight: 600; }
.th-hero { background: linear-gradient(135deg, #14233F 0%, #1B1C21 100%); border: 1px solid #25272E; border-radius: 26px; padding: 34px 38px; margin-bottom: 18px; }
.th-hero .e { color: #6EA3F5; letter-spacing: .16em; font-weight: 700; font-size: .78rem; text-transform: uppercase; }
.th-hero h1 { font-size: clamp(1.9rem, 4.2vw, 3rem); font-weight: 600; line-height: 1.06; margin: 14px 0 16px; padding: 0; max-width: 18em; }
.th-hero p { color: #9AA0AA; max-width: 56ch; margin: 0; font-size: 1.05rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] { border-radius: 999px; }
@media (max-width: 800px) { .th-hero { padding: 24px 20px; } }
</style>""",
    unsafe_allow_html=True,
)

if not ss["trainer_ok"]:
    st.markdown(
        """<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 540px; padding-left: 1rem; padding-right: 1rem; padding-bottom: 120px; }
.st-key-bottomnav { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(14px + env(safe-area-inset-bottom, 0px)); z-index: 999;
  background: rgba(27,28,33,.96); border: 1px solid #2B2D35; border-radius: 32px; padding: 6px 8px; width: min(520px, 94vw); }
.st-key-bottomnav [role="radiogroup"] { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; width: 100%; }
.st-key-bottomnav label { justify-content: center; border-radius: 24px; padding: 10px 4px; margin: 0; cursor: pointer; }
.st-key-bottomnav label > div:first-child { display: none; }
.st-key-bottomnav label p { font-size: 1.4rem; text-align: center; }
.st-key-bottomnav label:has(input:checked) { background: #3A3C44; }
</style>""",
        unsafe_allow_html=True,
    )


def hero(eyebrow, title, text):
    st.markdown(
        f'<div class="th-hero"><div class="e">{esc(eyebrow)}</div><h1>{esc(title)}</h1><p>{esc(text)}</p></div>',
        unsafe_allow_html=True,
    )


def pill(text, kind="neu"):
    return f'<span class="th-pill th-{kind}">{esc(text)}</span>'


def kpi_cards(items):
    cards = "".join(f'<div class="th-card"><div class="th-kl">{esc(l)}</div><div class="th-kv">{esc(v)}</div>{p}</div>' for l, v, p in items)
    st.markdown(f'<div class="th-kpis">{cards}</div>', unsafe_allow_html=True)


def delta_pill(cur, prev, absolute=False):
    if cur is None:
        return pill("No check-ins yet")
    if prev is None or (prev == 0 and not absolute):
        return pill("New activity", "up") if prev == 0 and cur > 0 else pill("No prior data")
    if absolute:
        d = cur - prev
        if abs(d) < 0.05:
            return pill("No change vs prior period")
        return pill(f"{'↑ +' if d > 0 else '↓ '}{d:.1f} pts vs prior period", "up" if d > 0 else "dn")
    p = (cur - prev) / prev * 100
    if abs(p) < 0.05:
        return pill("No change vs prior period")
    return pill(f"{'↑ +' if p > 0 else '↓ '}{p:.1f}% vs prior period", "up" if p > 0 else "dn")


def ring_html(pct, top, bottom="", size=96):
    pct = max(0, min(100, pct))
    inner = size - 22
    return (f'<div class="th-ring" style="width:{size}px;height:{size}px;background:conic-gradient(#4A94F2 {pct * 3.6}deg,#2A2C33 0)">'
            f'<div style="width:{inner}px;height:{inner}px"><b style="font-size:1.25rem">{esc(str(top))}</b><small>{esc(bottom)}</small></div></div>')


# ----------------------------------------------------------------------------
# Storage backends
# ----------------------------------------------------------------------------
class LocalBackend:
    """data/store.json plus local folders. For testing; resets on Streamlit Cloud restarts."""

    kind = "local"

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = DATA_DIR / "store.json"

    def _read(self):
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {}

    def _write(self, rows):
        self.path.write_text(json.dumps(rows))

    def directory(self):
        return [{"id": k, "name": v["name"]} for k, v in self._read().items() if k.startswith("c_")]

    def all(self):
        return [v for k, v in self._read().items() if k.startswith("c_")]

    def get(self, rid):
        return self._read().get(rid)

    def put(self, row):
        rows = self._read()
        rows[row["id"]] = row
        self._write(rows)

    def delete(self, rid):
        rows = self._read()
        rows.pop(rid, None)
        self._write(rows)

    def _save_file(self, folder, name, data):
        d = DATA_DIR / folder
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_bytes(data)
        return p

    def upload_media(self, cid, filename, data, content_type):
        return str(self._save_file("media", f"{uid()}-{filename}", data))

    def upload_private(self, cid, filename, data, content_type):
        p = self._save_file(f"photos/{cid}", f"{uid()}-{filename}", data)
        return str(p.relative_to(DATA_DIR))

    def read_private(self, key):
        return (DATA_DIR / key).read_bytes()


class SupabaseBackend:
    """One JSON row per client (plus one 'lib' row). Animations in a public bucket, photos in a private one."""

    kind = "supabase"
    MEDIA_BUCKET = "videos"
    PRIVATE_BUCKET = "photos"

    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.h = {"apikey": key, "Authorization": f"Bearer {key}"}

    def _rest(self, method, query="", **kw):
        r = requests.request(method, f"{self.url}/rest/v1/app_rows{query}",
                             headers={**self.h, "Content-Type": "application/json", **kw.pop("headers", {})}, timeout=20, **kw)
        r.raise_for_status()
        return r.json() if r.text else None

    def directory(self):
        return self._rest("GET", "?select=id,name:data->>name&id=like.c_*&order=id")

    def all(self):
        return [r["data"] for r in self._rest("GET", "?select=data&id=like.c_*")]

    def get(self, rid):
        rows = self._rest("GET", f"?id=eq.{quote(rid)}&select=data")
        return rows[0]["data"] if rows else None

    def put(self, row):
        self._rest("POST", "?on_conflict=id", json={"id": row["id"], "data": row},
                   headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def delete(self, rid):
        self._rest("DELETE", f"?id=eq.{quote(rid)}")

    def _upload(self, bucket, path, data, ctype):
        r = requests.post(f"{self.url}/storage/v1/object/{bucket}/{quote(path)}",
                          headers={**self.h, "Content-Type": ctype or "application/octet-stream", "x-upsert": "true"}, data=data, timeout=300)
        r.raise_for_status()

    def upload_media(self, cid, filename, data, content_type):
        path = f"{cid}/{uid()}-{filename}"
        self._upload(self.MEDIA_BUCKET, path, data, content_type)
        return f"{self.url}/storage/v1/object/public/{self.MEDIA_BUCKET}/{quote(path)}"

    def upload_private(self, cid, filename, data, content_type):
        path = f"{cid}/{uid()}-{filename}"
        self._upload(self.PRIVATE_BUCKET, path, data, content_type)
        return path

    def read_private(self, key):
        r = requests.get(f"{self.url}/storage/v1/object/{self.PRIVATE_BUCKET}/{quote(key)}", headers=self.h, timeout=60)
        r.raise_for_status()
        return r.content


@st.cache_resource
def get_backend():
    sb = secret("supabase")
    if sb and sb.get("url") and sb.get("service_key"):
        return SupabaseBackend(sb["url"], sb["service_key"])
    return LocalBackend()


B = get_backend()


@st.cache_data(ttl=8, show_spinner=False)
def load_all(_kind):
    return sorted(B.all(), key=lambda c: (c.get("created", ""), c["name"]))


def save_client(c):
    B.put(c)
    load_all.clear()


@st.cache_data(ttl=300, show_spinner=False)
def photo_bytes(key):
    return B.read_private(key)


# ----------------------------------------------------------------------------
# Exercise library
# ----------------------------------------------------------------------------
LIB_GROUPS = ["Chest", "Back", "Shoulders", "Biceps", "Triceps", "Legs", "Glutes", "Calves", "Abs", "Fat loss", "Muscle gain", "Cardio", "Other"]
GROUP_LABELS = {"Back": "Lats / Back"}
BUILDER_CATS = ["All", "Chest", "Triceps", "Back", "Biceps", "Shoulders", "Legs", "Abs", "Fat loss", "Muscle gain", "Glutes", "Calves", "Cardio", "Other"]


def glabel(g):
    return GROUP_LABELS.get(g, g)


def normalize_link(u):
    u = (u or "").strip()
    m = re.match(r"https?://(?:www\.|m\.)?youtube\.com/shorts/([\w-]{6,})", u)
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else u


def in_cat(l, g):
    return g == "All" or l.get("group") == g or g in (l.get("tags") or [])


def yt_search(name):
    return "https://www.youtube.com/results?search_query=" + quote(f"{name} exercise form")
# name, group, equipment, sets, reps, rest, target, coaching cue
DEFAULT_EXERCISES = [
    ("Dumbbell Bench Press", "Chest", "Dumbbells, flat bench", "3", "8", "2 min", "", "Shoulder blades pinched, press up and slightly in, lower under control."),
    ("Dumbbell Incline Bench Press", "Chest", "Dumbbells, incline bench", "3", "8", "2 min", "", "Press from chest level to over the shoulders, feet planted."),
    ("Wide Grip Lat Pulldown", "Back", "Lat pulldown machine", "3", "8", "2 min", "", "Chest up, drive elbows down to your sides, no swinging."),
    ("Reverse Grip Lateral Pulldown Machine", "Back", "Pulldown machine", "3", "8", "2 min", "", "Underhand grip, pull to the upper chest, lean back slightly."),
    ("Neutral Grip Seated Row Machine", "Back", "Row machine", "3", "8", "2 min", "", "Chest tall, pull elbows back and squeeze the shoulder blades."),
    ("Dumbbell Seated Shoulder Press", "Shoulders", "Dumbbells, bench", "3", "12", "2 min", "", "Brace your core and press overhead without arching your back."),
    ("Dumbbell Seated Lateral Raise", "Shoulders", "Dumbbells, bench", "3", "15", "2 min", "", "Slight elbow bend, lift out to shoulder height, lower slowly."),
    ("Dumbbell Shrug", "Shoulders", "Dumbbells", "3", "15", "1 min", "", "Lift straight up toward the ears, pause, lower. No rolling."),
    ("Cable Triceps Pushdown (V Bar)", "Triceps", "Cable machine, V bar", "3", "15", "1 min", "", "Elbows pinned to your ribs, straighten fully, slow return."),
    ("Cable Overhead Triceps Extension (Rope)", "Triceps", "Cable machine, rope", "3", "15", "2 min", "", "Elbows close to your head, extend fully, ribs down."),
    ("Dumbbell Biceps Curl", "Biceps", "Dumbbells", "3", "15", "2 min", "", "Elbows by your sides, curl up, lower slowly."),
    ("Cable One Arm Neutral Grip Biceps Curl", "Biceps", "Cable machine", "3", "15", "1 min", "", "Keep the elbow still, curl with the palm facing in."),
    ("Dumbbell Goblet Squat", "Legs", "Dumbbell", "3", "8", "2 min", "", "Hold the weight at your chest, sit between your hips, stay tall."),
    ("Angled Leg Press Machine", "Legs", "Leg press machine", "3", "8", "1 min", "", "Feet shoulder-width, lower deep, press without a hard lockout."),
    ("Seated Leg Extension", "Legs", "Leg extension machine", "3", "10", "2 min", "", "Pad on the lower shins, extend and squeeze the quads."),
    ("Seated Leg Curl", "Legs", "Leg curl machine", "3", "10", "2 min", "", "Pad snug above the heels, curl smoothly, resist on the way back."),
    ("Dumbbell Walking Lunge", "Legs", "Dumbbells", "3", "12", "2 min", "Body weight", "Long step, back knee near the floor, stay tall."),
    ("Dumbbell Hip Thrust", "Glutes", "Dumbbell, bench", "3", "15", "2 min", "", "Upper back on the bench, drive hips up, squeeze at the top."),
    ("Glute Bridge Two Legs on Floor", "Glutes", "Mat", "3", "15", "1 min", "", "Feet flat, push through the heels, squeeze the glutes."),
    ("Dumbbell Standing Calf Raise", "Calves", "Dumbbells, step", "3", "15", "1 min", "", "Rise onto your toes with straight knees, full stretch at the bottom."),
    ("Barbell Seated Calf Raise", "Calves", "Barbell, bench", "3", "15", "2 min", "", "Weight over the knees, lift heels high, pause, lower to a full stretch."),
]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


# name, group, extra categories, equipment, sets, reps, rest, target, coaching cue
STARTER_EXTRA = [
    ("Push-up", "Chest", ["Fat loss"], "Bodyweight", "3", "12", "1 min", "Body weight", "Body in one line, lower the chest to the floor, press up without sagging."),
    ("Machine Chest Press", "Chest", [], "Chest press machine", "3", "10", "2 min", "", "Handles at mid-chest height, press forward, return slowly."),
    ("Cable Chest Fly", "Chest", [], "Cable machine", "3", "12", "1 min", "", "Soft elbows, bring the handles together in a hugging arc."),
    ("Decline Dumbbell Press", "Chest", [], "Dumbbells, decline bench", "3", "10", "2 min", "", "Lower to the lower chest, press up and slightly in."),
    ("Incline Dumbbell Fly", "Chest", [], "Dumbbells, incline bench", "3", "12", "1 min", "", "Open wide with soft elbows, feel the stretch, squeeze together."),
    ("Barbell Bench Press", "Chest", ["Muscle gain"], "Barbell, flat bench", "4", "6", "2 min", "", "Bar to the mid-chest, feet planted, press up in a steady line."),
    ("Bench Triceps Dips", "Triceps", [], "Bench", "3", "12", "1 min", "Body weight", "Hands on the bench edge, lower with elbows back, press up."),
    ("EZ Bar Skull Crusher", "Triceps", [], "EZ bar, bench", "3", "10", "2 min", "", "Lower the bar toward your forehead, elbows steady, extend."),
    ("Dumbbell Overhead Triceps Extension", "Triceps", [], "Dumbbell", "3", "12", "1 min", "", "Hold the weight overhead, lower behind the head, extend up."),
    ("Close-Grip Push-up", "Triceps", ["Fat loss"], "Bodyweight", "3", "12", "1 min", "Body weight", "Hands under the shoulders, elbows close to the ribs."),
    ("Pull-up", "Back", ["Muscle gain"], "Pull-up bar", "3", "8", "2 min", "Body weight", "Start from a full hang, pull the chest to the bar, lower with control."),
    ("Seated Cable Row", "Back", [], "Cable machine", "3", "12", "2 min", "", "Chest tall, pull to the stomach, squeeze the shoulder blades."),
    ("One Arm Dumbbell Row", "Back", [], "Dumbbell, bench", "3", "10", "1 min", "", "Flat back, pull the elbow toward the hip, lower slowly."),
    ("Straight Arm Pulldown", "Back", [], "Cable machine", "3", "12", "1 min", "", "Arms nearly straight, sweep the bar down to your thighs."),
    ("Barbell Bent-Over Row", "Back", ["Muscle gain"], "Barbell", "4", "8", "2 min", "", "Hinge at the hips, flat back, pull the bar to the lower ribs."),
    ("Conventional Deadlift", "Back", ["Muscle gain", "Legs"], "Barbell", "3", "5", "3 min", "", "Bar over mid-foot, flat back, push the floor away."),
    ("Dumbbell Hammer Curl", "Biceps", [], "Dumbbells", "3", "12", "1 min", "", "Palms facing in, curl without swinging."),
    ("EZ Bar Curl", "Biceps", [], "EZ bar", "3", "10", "1 min", "", "Elbows by your sides, curl up, lower slowly."),
    ("Incline Dumbbell Curl", "Biceps", [], "Dumbbells, incline bench", "3", "12", "1 min", "", "Arms hang behind the body, curl without moving the shoulders."),
    ("Preacher Curl", "Biceps", [], "Preacher bench, EZ bar", "3", "10", "1 min", "", "Upper arms flat on the pad, curl up, stretch fully at the bottom."),
    ("Dumbbell Front Raise", "Shoulders", [], "Dumbbells", "3", "12", "1 min", "", "Lift to shoulder height with a straight body, lower slowly."),
    ("Reverse Pec Deck Fly", "Shoulders", [], "Pec deck machine", "3", "15", "1 min", "", "Arms wide, lead with the elbows, squeeze the rear shoulders."),
    ("Barbell Overhead Press", "Shoulders", ["Muscle gain"], "Barbell", "4", "6", "2 min", "", "Brace, press the bar straight overhead, head through at the top."),
    ("Arnold Press", "Shoulders", [], "Dumbbells", "3", "10", "2 min", "", "Rotate the palms as you press, control the way down."),
    ("Face Pull", "Shoulders", [], "Cable machine, rope", "3", "15", "1 min", "", "Pull the rope toward your face, elbows high, squeeze the rear shoulders."),
    ("Barbell Back Squat", "Legs", ["Muscle gain"], "Barbell, rack", "4", "6", "2 min", "", "Brace, sit down between the hips, drive up through the whole foot."),
    ("Barbell Romanian Deadlift", "Legs", ["Muscle gain", "Glutes"], "Barbell", "3", "8", "2 min", "", "Push the hips back, flat back, feel the hamstrings stretch."),
    ("Bulgarian Split Squat", "Legs", ["Glutes"], "Dumbbells, bench", "3", "10", "2 min", "", "Back foot on the bench, drop straight down, drive through the front heel."),
    ("Hack Squat Machine", "Legs", [], "Hack squat machine", "3", "10", "2 min", "", "Feet shoulder-width, lower deep, press without a hard lockout."),
    ("Bodyweight Squat", "Legs", ["Fat loss"], "Bodyweight", "3", "20", "1 min", "Body weight", "Sit back and down, chest up, stand tall."),
    ("Dumbbell Step-up", "Legs", ["Fat loss", "Glutes"], "Dumbbells, box", "3", "12", "1 min", "", "Drive through the lead heel, stand fully, step down slowly."),
    ("Crunch", "Abs", [], "Mat", "3", "20", "1 min", "Body weight", "Curl the ribs toward the hips, do not pull on your neck."),
    ("Plank", "Abs", [], "Mat", "3", "45 sec", "1 min", "Body weight", "Body in a straight line, squeeze glutes and abs, keep breathing."),
    ("Hanging Knee Raise", "Abs", [], "Pull-up bar", "3", "12", "1 min", "Body weight", "Lift the knees by curling the pelvis, lower without swinging."),
    ("Cable Crunch", "Abs", ["Muscle gain"], "Cable machine, rope", "3", "15", "1 min", "", "Kneel, curl the ribs to the hips, keep the hips still."),
    ("Russian Twist", "Abs", [], "Mat", "3", "20", "1 min", "Body weight", "Lean back slightly, rotate the chest side to side."),
    ("Bicycle Crunch", "Abs", ["Fat loss"], "Mat", "3", "20", "1 min", "Body weight", "Opposite elbow to knee, slow and controlled."),
    ("Ab Wheel Rollout", "Abs", [], "Ab wheel", "3", "10", "1 min", "Body weight", "Roll out with abs braced, do not let the lower back sag."),
    ("Mountain Climber", "Abs", ["Fat loss"], "Mat", "3", "30 sec", "45 sec", "Body weight", "Plank position, drive the knees in quickly, hips low."),
    ("Burpee", "Fat loss", [], "Bodyweight", "4", "12", "45 sec", "Body weight", "Drop to the floor, push up, jump up, repeat at a steady pace."),
    ("Jump Rope", "Fat loss", ["Cardio"], "Jump rope", "5", "1 min", "30 sec", "", "Light jumps on the balls of your feet, wrists turn the rope."),
    ("Kettlebell Swing", "Fat loss", ["Glutes"], "Kettlebell", "4", "20", "1 min", "", "Hinge, snap the hips forward, let the bell float to chest height."),
    ("Jumping Jacks", "Fat loss", ["Cardio"], "Bodyweight", "3", "40", "30 sec", "Body weight", "Land softly, keep a steady rhythm."),
    ("Treadmill Incline Walk", "Fat loss", ["Cardio"], "Treadmill", "1", "20 min", "", "", "Moderate incline, steady pace, no holding the rails."),
    ("Rowing Machine Intervals", "Fat loss", ["Cardio"], "Rowing machine", "6", "250 m", "1 min", "", "Legs, then body, then arms. Return in the reverse order."),
    ("Battle Rope Waves", "Fat loss", [], "Battle ropes", "4", "30 sec", "45 sec", "", "Stay low, alternate arms for fast, even waves."),
]


def default_library():
    base = [{"id": "lib_" + slug(n), "name": n, "group": g, "tags": [], "equipment": eq, "sets": s, "reps": r, "rest": rest, "target": t, "cue": cue, "media": "", "video": ""}
            for n, g, eq, s, r, rest, t, cue in DEFAULT_EXERCISES]
    extra = [{"id": "lib_" + slug(n), "name": n, "group": g, "tags": tags, "equipment": eq, "sets": s, "reps": r, "rest": rest, "target": t, "cue": cue, "media": "", "video": ""}
             for n, g, tags, eq, s, r, rest, t, cue in STARTER_EXTRA]
    return base + extra


def add_starters(lib):
    have = {re.sub(r"[^a-z0-9]", "", l["name"].lower()) for l in lib}
    n = 0
    for d in default_library():
        if re.sub(r"[^a-z0-9]", "", d["name"].lower()) not in have:
            lib.append(d)
            n += 1
    return n


@st.cache_data(ttl=8, show_spinner=False)
def _lib_cached(_kind):
    row = B.get("lib")
    return row["exercises"] if row else None


def get_lib(create=False):
    lib = _lib_cached(B.kind)
    if lib is None:
        lib = default_library()
        if create:
            save_lib(lib)
    for l in lib:
        if l.get("group") not in LIB_GROUPS:
            l["group"] = "Other"
    return lib


def save_lib(lib):
    B.put({"id": "lib", "exercises": lib})
    _lib_cached.clear()


def ex_from_lib(l, sets=None, reps=None):
    return {"id": uid(), "lib_id": l["id"], "name": l["name"], "group": l.get("group", ""), "sets": sets or l["sets"], "reps": reps or l["reps"],
            "rest": l.get("rest", ""), "target": l.get("target", ""), "notes": l.get("cue", ""), "video": "", "media": ""}


def clone_ex(e):
    n = copy.deepcopy(e)
    n["id"] = uid()
    return n


def clone_day(d):
    n = copy.deepcopy(d)
    n["id"] = uid()
    n["exercises"] = [clone_ex(e) for e in d["exercises"]]
    return n


def clone_phase(p):
    n = copy.deepcopy(p)
    n["id"] = uid()
    n["days"] = [clone_day(d) for d in p["days"]]
    return n


# ----------------------------------------------------------------------------
# Clients, programs, security
# ----------------------------------------------------------------------------
def hash_pin(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 120_000).hex()


def set_pin(c, pin, must_change=False):
    c["pin_salt"] = uid() + uid()
    c["pin_hash"] = hash_pin(pin, c["pin_salt"])
    c["must_change_pin"] = must_change


def pin_ok(c, pin):
    return bool(c.get("pin_hash")) and hmac.compare_digest(hash_pin(pin, c["pin_salt"]), c["pin_hash"])


def new_phase(name="Program", weeks=0, days=None):
    return {"id": uid(), "name": name, "weeks": weeks, "days": days or []}


def new_day(title, exercises=None, weekday=-1):
    return {"id": uid(), "title": title, "weekday": weekday, "exercises": exercises or []}


def new_client(name, trainer=""):
    pin = starter_pin()
    c = {"id": "c_" + uid(), "name": name, "trainer": trainer, "created": today(), "pin_hash": "", "pin_salt": "", "must_change_pin": True,
         "onboarded": False, "profile": {"height_cm": 0, "weight_kg": 0, "diet": "", "goal": "", "style": "", "notes": ""},
         "program": {"start": today(), "phases": [new_phase()]},
         "diet": {"macros": {"kcal": 2200, "p": 160, "c": 220, "f": 70}, "meals": []},
         "habits": [], "events": [], "weights": [], "checkins": [], "food_log": [], "photos": [], "coach_notes": []}
    set_pin(c, pin, must_change=True)
    return c, pin


def phase_for(c, on=None):
    """(phase, week number inside the phase, overall week) for a date."""
    phases = c["program"]["phases"]
    if not phases:
        return None, 0, 0
    on = on or now().date()
    active = c["program"].get("active_phase")
    if active:
        chosen = next((p for p in phases if p["id"] == active), None)
        if chosen:
            return chosen, 1, max(1, (on - dobj(c["program"]["start"])).days // 7 + 1)
    split = next((p for p in phases if "general" not in p.get("name", "").lower() and p.get("days")), None)
    if split:
        return split, 1, max(1, (on - dobj(c["program"]["start"])).days // 7 + 1)
    week = max(0, (on - dobj(c["program"]["start"])).days // 7)
    acc = 0
    for ph in phases:
        w = int(ph.get("weeks") or 0)
        if w == 0 or week < acc + w:
            return ph, week - acc + 1, week + 1
        acc += w
    return phases[-1], week - acc + 1, week + 1



def workouts_for_date(c, on):
    """Date assignments replace the regular schedule; an empty list is a rest day."""
    on = dobj(on) if isinstance(on, str) else on
    overrides = c["program"].get("date_workouts", {})
    if on.isoformat() in overrides:
        return overrides[on.isoformat()]
    phase, _, _ = phase_for(c, on)
    return [d for d in (phase["days"] if phase else []) if d["weekday"] in (on.weekday(), -1)]


def builder_date_action(action):
    if not ss.get("trainer_ok"):
        return
    cid = ss.get("bld_client")
    current = B.get(cid)
    if not current:
        return
    date = ss["bld_date"].isoformat()
    overrides = current["program"].setdefault("date_workouts", {})
    if action == "restore":
        overrides.pop(date, None)
    elif action == "remove":
        overrides[date] = []
    else:
        draft = builder_draft(cid)
        phase = next((p for p in draft["program"]["phases"] if p["id"] == ss.get("bld_phase")), None)
        day = next((d for d in (phase["days"] if phase else []) if d["id"] == ss.get("bld_day")), None)
        if not day or not day["exercises"]:
            ss["_bld_msg"] = ("error", "Select a saved workout with exercises first.")
            return
        assigned = copy.deepcopy(day)
        assigned["id"] = uid()
        for exercise in assigned["exercises"] + assigned.get("bonus_exercises", []):
            exercise["id"] = uid()
        overrides[date] = [assigned]
        split = next((p for p in current["program"]["phases"] if "general" not in p.get("name", "").lower() and p["days"]), None)
        if split:
            current["program"]["active_phase"] = split["id"]
    save_client(current)
    draft = builder_draft(cid)
    draft["program"]["date_workouts"] = copy.deepcopy(overrides)
    ss["_bld_msg"] = ("ok", f"Workout for {current['name']} on {date} updated. Regular workouts remain saved.")


def seed_clients():
    lib = {l["name"]: l for l in get_lib(create=True)}
    names = ["Anton", "Dharan", "Rekha", "Divya", "Venky", "Sheethal", "Varshni", "Swetha", "Guhan", "Kevin"]
    existing = {c["name"].lower() for c in load_all(B.kind)}
    out = []

    def ex(name, **kw):
        e = ex_from_lib(lib[name])
        e.update(kw)
        return e

    def split_program():
        general = new_day("General · Full body", [ex(n, sets="3", reps="15") for n in [
            "Dumbbell Bench Press", "Wide Grip Lat Pulldown", "Dumbbell Seated Shoulder Press", "Angled Leg Press Machine",
            "Dumbbell Biceps Curl", "Cable Triceps Pushdown (V Bar)"]])
        days = [
            new_day("Day 1 · Chest", [ex("Dumbbell Bench Press"), ex("Dumbbell Incline Bench Press")], 0),
            new_day("Day 2 · Triceps", [ex("Cable Triceps Pushdown (V Bar)"), ex("Cable Overhead Triceps Extension (Rope)")], 1),
            new_day("Day 3 · Lat", [ex("Wide Grip Lat Pulldown"), ex("Reverse Grip Lateral Pulldown Machine"), ex("Neutral Grip Seated Row Machine")], 2),
            new_day("Day 4 · Biceps", [ex("Dumbbell Biceps Curl"), ex("Cable One Arm Neutral Grip Biceps Curl")], 3),
            new_day("Day 5 · Shoulder & Legs", [ex("Dumbbell Seated Shoulder Press"), ex("Dumbbell Seated Lateral Raise"), ex("Dumbbell Shrug"),
                                                  ex("Angled Leg Press Machine"), ex("Seated Leg Extension"), ex("Seated Leg Curl")], 4),
        ]
        return [new_phase("General", 0, [general]), new_phase("Split program", 0, days)]

    def screenshot_program():
        return [new_phase("Programme", 0, [
            new_day("Upper body gym 1", [ex(n) for n in ["Dumbbell Bench Press", "Wide Grip Lat Pulldown", "Dumbbell Seated Shoulder Press",
                                                         "Cable Triceps Pushdown (V Bar)", "Dumbbell Shrug", "Cable One Arm Neutral Grip Biceps Curl"]], 0),
            new_day("Lower body gym 1", [ex(n) for n in ["Angled Leg Press Machine", "Seated Leg Curl", "Seated Leg Extension",
                                                         "Glute Bridge Two Legs on Floor", "Dumbbell Standing Calf Raise"]], 1),
            new_day("Upper body gym 2", [ex(n) for n in ["Dumbbell Seated Lateral Raise", "Neutral Grip Seated Row Machine", "Dumbbell Incline Bench Press",
                                                         "Reverse Grip Lateral Pulldown Machine", "Cable Overhead Triceps Extension (Rope)", "Dumbbell Biceps Curl"]], 3),
            new_day("Lower gym 2", [ex(n) for n in ["Dumbbell Goblet Squat", "Dumbbell Hip Thrust", "Dumbbell Walking Lunge", "Seated Leg Curl",
                                                    "Barbell Seated Calf Raise"]], 4)])]

    for n in names:
        if n.lower() in existing:
            continue
        c, pin = new_client(n)
        if n in ("Anton", "Dharan"):
            c["program"]["phases"] = split_program()
        elif n in ("Rekha", "Divya"):
            c["program"]["phases"] = screenshot_program()
        save_client(c)
        out.append((n, pin))
    return out


# ----------------------------------------------------------------------------
# Calendar helpers
# ----------------------------------------------------------------------------
def ics_escape(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_ics(title, desc, start, minutes, daily=False):
    f = "%Y%m%dT%H%M%S"
    end = start + dt.timedelta(minutes=minutes)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TrainingHub//EN", "BEGIN:VEVENT", f"UID:{uid()}@traininghub",
             f"DTSTAMP:{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", f"DTSTART:{start.strftime(f)}", f"DTEND:{end.strftime(f)}"]
    if daily:
        lines.append("RRULE:FREQ=DAILY")
    return "\r\n".join(lines + [f"SUMMARY:{ics_escape(title)}", f"DESCRIPTION:{ics_escape(desc)}", "END:VEVENT", "END:VCALENDAR"])


def google_link(title, desc, start, minutes, daily=False):
    f = "%Y%m%dT%H%M%S"
    end = start + dt.timedelta(minutes=minutes)
    url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={quote(title)}&details={quote(desc)}&dates={start.strftime(f)}/{end.strftime(f)}"
    return url + ("&recur=" + quote("RRULE:FREQ=DAILY") if daily else "")


def calendar_buttons(key, title, desc, start, minutes, daily=False):
    a, b = st.columns(2)
    a.link_button("Google Calendar", google_link(title, desc, start, minutes, daily), width="stretch")
    b.download_button("Apple / Outlook (.ics)", make_ics(title, desc, start, minutes, daily), file_name=re.sub(r"\W+", "_", title)[:40] + ".ics",
                      mime="text/calendar", key=key, width="stretch")


def next_at(hhmm):
    h, m = [int(x) for x in (hhmm or "08:00").split(":")]
    d = now().replace(hour=h, minute=m, second=0, microsecond=0, tzinfo=None)
    return d if d > now().replace(tzinfo=None) else d + dt.timedelta(days=1)


def fmt_time(hhmm):
    h, m = [int(x) for x in hhmm.split(":")]
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


# ----------------------------------------------------------------------------
# Exercise display helpers
# ----------------------------------------------------------------------------
def n_sets(e):
    m = re.match(r"\s*(\d+)", str(e.get("sets", "")))
    return int(m.group(1)) if m else 3


def chips_html(e):
    parts = [f"{e['sets']} sets", f"{e['reps']} reps"]
    if e.get("target"):
        parts.append(e["target"])
    if e.get("rest"):
        parts.append(f"{e['rest']} rest")
    return "".join(f'<span class="th-chip">{esc(str(p))}</span>' for p in parts)


def show_media(src):
    """Shows an animation (gif/webp), an uploaded video, a YouTube link, or a plain 'Watch demo' button."""
    m = re.match(r"https?://(?:www\.|m\.)?youtube\.com/shorts/([\w-]{6,})", src.strip())
    if m:
        src = f"https://www.youtube.com/watch?v={m.group(1)}"
    if re.search(r"\.(gif|webp|png|jpe?g)(\?|$)", src, re.I):
        st.image(src, width="stretch")
    elif re.search(r"youtu|\.(mp4|webm|mov)(\?|$)", src, re.I) or not src.startswith("http"):
        st.video(src)
    else:
        st.link_button("Watch demo", src)


def media_sources(e, lib_map):
    """Order of preference: this client's animation, this client's link, library animation, library link."""
    lm = lib_map.get(e.get("lib_id"), {})
    return [x for x in [e.get("media"), (e.get("video") or "").strip(), lm.get("media"), (lm.get("video") or "").strip()] if x]


def render_media(e, lib_map, compact=False):
    srcs = media_sources(e, lib_map)
    if srcs:
        show_media(srcs[0])
    elif not compact:
        st.markdown(f'<div class="th-card th-empty">Video not added yet<br><span class="th-note">{esc(e.get("group", ""))}</span></div>', unsafe_allow_html=True)


def has_media(e, lib_map):
    return bool(media_sources(e, lib_map))


def upload_media(cid, f):
    with st.spinner("Uploading…"):
        return B.upload_media(cid, re.sub(r"[^\w.\-]+", "_", f.name), f.getvalue(), f.type)


# ----------------------------------------------------------------------------
# Events (what clients tick off)
# ----------------------------------------------------------------------------
def event_set(c, d, kind, ref, on, label="", **extra):
    c["events"] = [e for e in c["events"] if not (e["d"] == d and e["k"] == kind and e["ref"] == ref)]
    if on:
        c["events"].append({"d": d, "k": kind, "ref": ref, "label": label, **extra})


def toggle_event(cid, kind, ref, label, key):
    c = B.get(cid)
    if c:
        event_set(c, today(), kind, ref, ss[key], label)
        save_client(c)


def is_done(c, d, kind, ref):
    return any(e["d"] == d and e["k"] == kind and e["ref"] == ref for e in c["events"])


def day_done(c, d, day):
    ids = {e["id"] for e in day["exercises"]}
    return bool(ids) and all(is_done(c, d, "ex", eid) for eid in ids)


def streak(c):
    days = {e["d"] for e in c["events"] if e["k"] == "ex"}
    d = now().date()
    if d.isoformat() not in days:
        d -= dt.timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n


def client_color(clients, c):
    ids = [x["id"] for x in clients]
    return PALETTE[ids.index(c["id"]) % len(PALETTE)] if c["id"] in ids else PALETTE[0]


# ----------------------------------------------------------------------------
# Client app: onboarding
# ----------------------------------------------------------------------------
def client_login():
    st.markdown('<div class="th-head"><div class="t">Training Hub</div><div class="d">Welcome</div><div class="g">Log in to your plan</div></div>', unsafe_allow_html=True)
    try:
        directory = B.directory()
    except Exception as exc:
        st.error(f"Could not reach the database: {exc}")
        return
    if not directory:
        st.markdown('<div class="th-card th-empty">No clients have been set up yet.<br>Ask your trainer to add you.</div>', unsafe_allow_html=True)
    else:
        with st.container(border=True):
            name = st.text_input("Your name", key="client_login_name", placeholder="Type the name your trainer registered")
            pin = st.text_input("PIN", type="password", max_chars=4, placeholder="4-digit PIN")
            if ss.get("tries", 0) >= 5:
                st.error("Too many wrong PINs. Ask your trainer to reset it.")
            elif st.button("Log in", type="primary", width="stretch", disabled=not name.strip()):
                normalized = " ".join(name.split()).casefold()
                candidates = [d for d in directory if " ".join(d["name"].split()).casefold() == normalized]
                matches = []
                for entry in candidates:
                    c = B.get(entry["id"])
                    if c and pin_ok(c, pin):
                        matches.append(c)
                if len(matches) == 1:
                    ss["client_id"], ss["tries"] = matches[0]["id"], 0
                    st.rerun()
                else:
                    ss["tries"] = ss.get("tries", 0) + 1
                    st.error("That name or PIN is not correct.")
    if st.button("I am the trainer", type="tertiary"):
        ss["mode"] = "trainer"
        st.rerun()


def onboarding(c):
    first = c["name"].split()[0]
    if c.get("must_change_pin"):
        st.markdown(f'<div class="th-head"><div class="t">Welcome, {esc(first)}</div><div class="d">Step 1 of 2</div><div class="g">Create your own PIN</div></div>', unsafe_allow_html=True)
        with st.form("newpin"):
            p1 = st.text_input("New 4-digit PIN", type="password", max_chars=4)
            p2 = st.text_input("Repeat PIN", type="password", max_chars=4)
            if st.form_submit_button("Save PIN", type="primary", width="stretch"):
                if not re.fullmatch(r"\d{4}", p1 or ""):
                    st.error("Use exactly 4 digits.")
                elif p1 != p2:
                    st.error("The PINs do not match.")
                elif pin_ok(c, p1):
                    st.error("Choose a different PIN from the one your trainer gave you.")
                else:
                    set_pin(c, p1, False)
                    save_client(c)
                    st.rerun()
        return
    st.markdown(f'<div class="th-head"><div class="t">Welcome, {esc(first)}</div><div class="d">Step 2 of 2</div><div class="g">Tell us about you</div></div>', unsafe_allow_html=True)
    p = c["profile"]
    with st.form("about"):
        a, b = st.columns(2)
        h = a.number_input("Height (cm)", 100.0, 250.0, float(p.get("height_cm") or 165.0), 0.5)
        w = b.number_input("Weight (kg)", 25.0, 300.0, float(p.get("weight_kg") or 65.0), 0.1)
        diet = st.selectbox("Preferred diet", DIETS, index=DIETS.index(p["diet"]) if p.get("diet") in DIETS else None, placeholder="Choose one…")
        goal = st.radio("Your goal", GOALS, index=GOALS.index(p["goal"]) if p.get("goal") in GOALS else None, horizontal=True)
        style = st.radio("Training style", STYLES, index=STYLES.index(p["style"]) if p.get("style") in STYLES else None)
        notes = st.text_area("Anything your trainer should know? (injuries, allergies, schedule)", p.get("notes", ""))
        if st.form_submit_button("Continue to my plan", type="primary", width="stretch"):
            if not (diet and goal and style):
                st.error("Please choose your diet, goal and training style.")
            else:
                c["profile"] = {"height_cm": h, "weight_kg": w, "diet": diet, "goal": goal, "style": style, "notes": notes}
                c["weights"] = [x for x in c["weights"] if x["d"] != today()] + [{"d": today(), "w": round(w, 1)}]
                c["onboarded"] = True
                save_client(c)
                st.rerun()


# ----------------------------------------------------------------------------
# Client app: tabs
# ----------------------------------------------------------------------------
def go_nav(target):
    ss["nav"] = target


def start_workout(day_id, date=None, bonus=False):
    ss["gw"] = {"day": day_id, "date": date or today(), "bonus": bonus, "i": 0, "sets": {}, "w": {}}


def tab_home(c, lib_map):
    t = now()
    first = c["name"].split()[0]
    st.markdown(f'<div class="th-head"><div class="t">Training Hub</div><div class="d">{t:%A, %b} {t.day}</div><div class="g">Hi {esc(first)}</div></div>', unsafe_allow_html=True)
    phase, wk, overall = phase_for(c)
    tasks = []
    if phase:
        for d in workouts_for_date(c, t.date()):
            if d["exercises"] and not day_done(c, today(), d):
                tasks.append(f"Workout: {d['title']} · {len(d['exercises'])} exercises")
    last = c["checkins"][-1]["d"] if c["checkins"] else None
    if not last or (t.date() - dobj(last)).days >= 7:
        tasks.append("Weekly check-in is due")
    with st.container(border=True):
        if tasks:
            st.markdown("**Today's tasks**")
            for x in tasks:
                st.markdown(f"• {x}")
            st.button("Open training", on_click=go_nav, args=("🏋️",), type="primary")
        else:
            st.markdown("**No tasks**")
            st.caption("You have nothing left to complete today.")
    with st.container(border=True):
        st.markdown(f"**Your programme**")
        st.caption(f"Trainer: {c.get('trainer') or 'Not assigned yet'}")
        if phase:
            st.markdown(f"{esc(phase['name'])} · week {wk}" if phase.get("weeks") else f"{esc(phase['name'])} · week {overall}")
        p = c["profile"]
        chips = [x for x in [p.get("goal"), p.get("style"), p.get("diet")] if x]
        if chips:
            st.markdown("".join(f'<span class="th-chip">{esc(x)}</span>' for x in chips), unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**Notes from your coach**")
        notes = c["coach_notes"][-3:][::-1]
        if not notes:
            st.caption("No notes yet. They will show here when your coach adds one.")
        for n in notes:
            st.markdown(f"{n['text']}")
            st.caption(n["d"])


def toggle_training_exercise(cid, date, day_id, ref, label, key):
    c = B.get(cid)
    if c:
        event_set(c, date, "ex", ref, ss[key], label)
        if not ss[key]:
            event_set(c, date, "workout", day_id, False, "")
        save_client(c)


def complete_training_day(cid, date, day_id):
    c = B.get(cid)
    day = next((d for d in workouts_for_date(c, date) if d["id"] == day_id), None) if c else None
    if day and day["exercises"] and all(is_done(c, date, "ex", e["id"]) for e in day["exercises"]):
        event_set(c, date, "workout", day_id, True, day["title"])
        save_client(c)


def workout_card(c, d, lib_map, sel_date, editable):
    exs = d["exercises"]
    if exs:
        st.button("Start workout", key=f"sw_{d['id']}", type="primary", width="stretch", on_click=start_workout, args=(d["id"], sel_date), disabled=not editable)
    st.markdown(f'<div class="th-banner"><h2>{esc(d["title"])}</h2><span class="th-tag">{len(exs)} EXERCISES</span></div>', unsafe_allow_html=True)
    start = (now() + dt.timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0, tzinfo=None)
    desc = "\n".join(f"{e['name']} {e['sets']}x{e['reps']}" for e in exs) or "Workout"
    with st.expander("Add to calendar"):
        calendar_buttons(f"ics_{d['id']}_{sel_date}", f"{c['name']} · {d['title']}", desc, start, 60)
    if not exs:
        st.caption("No exercises in this workout yet.")
    for i, e in enumerate(exs):
        done = is_done(c, sel_date, "ex", e["id"])
        with st.expander(f"{i + 1}. {e['name']}{'  ✅' if done else ''}"):
            render_media(e, lib_map)
            st.markdown(chips_html(e), unsafe_allow_html=True)
            if e.get("notes"):
                st.markdown("**Notes**")
                st.caption(e["notes"])
            if editable:
                key = f"ex_{sel_date}_{e['id']}"
                st.checkbox("Exercise done", value=done, key=key, on_change=toggle_training_exercise, args=(c["id"], sel_date, d["id"], e["id"], e["name"], key))
    st.markdown("**Bonus workout**")
    bonus = d.get("bonus_exercises", [])
    for exercise in bonus:
        st.write(f"{exercise['name']} · {exercise['sets']}×{exercise['reps']}")
    if bonus:
        st.button("Start bonus workout", key=f"bonus_start_{d['id']}", on_click=start_workout, args=(d["id"], sel_date, True), disabled=not editable)
    else:
        st.caption("Your trainer has not added bonus exercises for this day.")
    if is_done(c, sel_date, "workout", d["id"]):
        st.success("Workout completed for the day.")
    elif exs and editable:
        st.button("Complete workout", key=f"complete_{d['id']}_{sel_date}", on_click=complete_training_day,
                  args=(c["id"], sel_date, d["id"]), disabled=not all(is_done(c, sel_date, "ex", e["id"]) for e in exs))
    if is_done(c, sel_date, "bonus_workout", d["id"]):
        st.success("Bonus workout completed.")


def training_day_changed():
    ss["train_selected"] = ss.get("train_day")


def tab_training(c, lib_map):
    if ss.get("gw"):
        return guided_workout(c, lib_map)
    st.markdown('<div class="th-title">Training</div>', unsafe_allow_html=True)
    phase, wk, overall = phase_for(c)
    if not phase:
        st.markdown('<div class="th-card th-empty">Your trainer has not added a workout plan yet.</div>', unsafe_allow_html=True)
        return
    st.caption(f"{phase['name']} · week {wk if phase.get('weeks') else overall}")
    td = now().date()
    monday = td - dt.timedelta(days=td.weekday())
    dates = [monday + dt.timedelta(days=i) for i in range(7)]

    def lab(i):
        done = any(day_done(c, dates[i].isoformat(), dy) for dy in workouts_for_date(c, dates[i]))
        return f"{WEEKDAYS[i]} {dates[i].day}{' ✓' if done else ''}"

    sel = st.segmented_control("Day", list(range(7)), format_func=lab, default=ss.get("train_selected", td.weekday()), key="train_day", on_change=training_day_changed, label_visibility="collapsed")
    sel = td.weekday() if sel is None else sel
    sel_date = dates[sel].isoformat()
    editable = sel_date <= td.isoformat()
    todays = workouts_for_date(c, sel_date)
    if not todays:
        st.markdown('<div class="th-card th-empty">NO WORKOUTS ON THIS DAY</div>', unsafe_allow_html=True)
    for d in todays:
        workout_card(c, d, lib_map, sel_date, editable)

    week_ex = [e for date in dates for d in workouts_for_date(c, date) for e in d["exercises"]]
    done_week = sum(1 for e in c["events"] if e["k"] == "ex" and not e.get("bonus") and e["d"] >= monday.isoformat() and e["d"] <= dates[6].isoformat())
    with st.container(border=True):
        h1, h2 = st.columns([2, 1])
        h1.markdown("**Training progress**")
        h2.markdown(pill(f"{done_week} / {len(week_ex)} this week"), unsafe_allow_html=True)
        a, b = st.columns([2, 1])
        nxt = next((d for d in workouts_for_date(c, td) if not day_done(c, today(), d)), None)
        a.markdown(f"**Next session**  \n{nxt['title'] if nxt else 'All done. You are all caught up.'}")
        b.markdown(f"**{streak(c)}**  \nday streak")
    with st.container(border=True):
        st.markdown("**🔥 Streak rewards**")
        st.write("🔓 Build your workout streak to unlock premium diets 🥗 and workouts 💪.")



def guided_workout(c, lib_map):
    gw = ss["gw"]
    phase, _, _ = phase_for(c)
    date = gw.get("date", today())
    bonus = gw.get("bonus", False)
    day = next((d for d in workouts_for_date(c, date) if d["id"] == gw["day"]), None)
    exercises = day.get("bonus_exercises" if bonus else "exercises", []) if day else []
    if not exercises:
        ss["gw"] = None
        st.rerun()
    exs, i = exercises, min(gw["i"], len(exercises) - 1)
    e = exs[i]
    st.markdown(f'<div class="th-title">{esc(day["title"])}</div>', unsafe_allow_html=True)
    st.progress((i) / len(exs), text=f"Exercise {i + 1} of {len(exs)}")
    st.subheader(e["name"])
    render_media(e, lib_map)
    st.markdown(chips_html(e), unsafe_allow_html=True)
    if e.get("notes"):
        st.caption(e["notes"])
    st.markdown("**Sets**")

    def set_cb(eid, n, key):
        cur = set(ss["gw"]["sets"].get(eid, []))
        (cur.add if ss[key] else cur.discard)(n)
        ss["gw"]["sets"][eid] = sorted(cur)

    def weight_cb(eid, key):
        ss["gw"]["w"][eid] = ss[key]

    for n in range(n_sets(e)):
        key = f"gws_{e['id']}_{n}"
        st.checkbox(f"Set {n + 1} done", value=n in gw["sets"].get(e["id"], []), key=key, on_change=set_cb, args=(e["id"], n, key))
    wkey = f"gww_{e['id']}"
    st.text_input("Weight used (optional)", value=gw["w"].get(e["id"], ""), key=wkey, placeholder="e.g. 20 kg", on_change=weight_cb, args=(e["id"], wkey))

    def move(delta):
        ss["gw"]["i"] = max(0, min(len(exs) - 1, ss["gw"]["i"] + delta))

    def mark_done():
        cc = B.get(c["id"])
        event_set(cc, date, "ex", e["id"], True, ("Bonus: " if bonus else "") + e["name"], bonus=bonus,
                  sets=len(ss["gw"]["sets"].get(e["id"], [])) or n_sets(e), w=ss["gw"]["w"].get(e["id"], ""))
        save_client(cc)
        move(1)

    def finish():
        cc = B.get(c["id"])
        if not all(is_done(cc, date, "ex", exercise["id"]) for exercise in exs):
            return
        event_set(cc, date, "bonus_workout" if bonus else "workout", day["id"], True, day["title"])
        save_client(cc)
        ss["gw"] = None
        ss["_toast"] = "Bonus workout completed." if bonus else "Workout completed for the day."

    a, b, d_ = st.columns(3)
    a.button("Back", on_click=move, args=(-1,), disabled=i == 0, width="stretch")
    b.button("Mark exercise done and next" if i < len(exs) - 1 else "Mark exercise done", on_click=mark_done, type="primary", width="stretch")
    d_.button("Exit", on_click=lambda: ss.__setitem__("gw", None), width="stretch")
    if all(is_done(c, date, "ex", exercise["id"]) for exercise in exs):
        st.button("Complete bonus workout" if bonus else "Complete workout", on_click=finish, type="primary", width="stretch")
    else:
        st.caption("Mark each exercise done to complete the workout.")



def activity_progress(c):
    st.subheader("Daily activity")
    date = st.date_input("Activity date", value=now().date(), max_value=now().date(), key="activity_date").isoformat()
    entry = next((x for x in c.get("activity_log", []) if x["d"] == date), {})
    st.caption("Enter steps and calories burned from your watch, phone or activity tracker. These are recorded values, not automatic measurements.")
    with st.form(f"activity_{date}"):
        steps = st.number_input("Steps walked or run", min_value=0, max_value=200000, value=int(entry.get("steps", 0)), key=f"steps_{date}")
        burned = st.number_input("Calories burned (kcal)", min_value=0, max_value=20000, value=int(entry.get("burned_kcal", 0)), key=f"burned_{date}")
        if st.form_submit_button("Save activity", type="primary"):
            cc = B.get(c["id"])
            entries = cc.setdefault("activity_log", [])
            entries[:] = [x for x in entries if x["d"] != date]
            entries.append({"d": date, "steps": steps, "burned_kcal": burned})
            save_client(cc)
            st.rerun()
    history = sorted(c.get("activity_log", []), key=lambda x: x["d"])
    if history:
        last = history[-1]
        a, b = st.columns(2)
        a.metric("Steps · " + last["d"], f"{last['steps']:,}")
        b.metric("Calories burned · " + last["d"], f"{last['burned_kcal']:,} kcal")
        frame = pd.DataFrame(history[-30:]).assign(date=lambda f: pd.to_datetime(f["d"])).set_index("date")
        st.caption("Progress on recorded days (up to the last 30 entries)")
        st.line_chart(frame[["steps"]], y_label="Steps")
        st.line_chart(frame[["burned_kcal"]], y_label="Calories burned")
    else:
        st.info("Save your first activity entry to start tracking progress.")


def nutrition_progress(c):
    st.markdown("**Diet progress · last 7 days**")
    start = now().date() - dt.timedelta(days=6)
    logged_days = {x["d"] for x in c.get("food_log", []) if start.isoformat() <= x["d"] <= today()}
    planned = {(x["d"], x["ref"]) for x in c["events"] if x["k"] == "meal" and start.isoformat() <= x["d"] <= today()}
    alternatives = {(x["d"], x["plan_ref"]) for x in c.get("food_log", []) if x.get("plan_ref") and start.isoformat() <= x["d"] <= today()}
    a, b, d = st.columns(3)
    a.metric("Days with food entries", len(logged_days))
    b.metric("Planned meals eaten", len(planned))
    d.metric("Meals replaced", len(alternatives))
    st.caption("Meal entries and completion records track your diet. Calories burned and steps are tracked in Habit.")


def tab_habit(c):
    st.markdown('<div class="th-title">Habit</div>', unsafe_allow_html=True)
    activity_progress(c)
    st.subheader("Daily habits")
    habits = c["habits"]
    if not habits:
        st.markdown('<div class="th-card th-empty">Your trainer has not assigned any habits yet.</div>', unsafe_allow_html=True)
        return
    td = now().date()
    days = [td - dt.timedelta(days=i) for i in range(6, -1, -1)]
    logged = {(e["d"], e["ref"]) for e in c["events"] if e["k"] == "habit"}
    counts = [sum((d.isoformat(), h["id"]) in logged for h in habits) for d in days]
    pct = round(sum(counts) / (len(habits) * 7) * 100)
    st.markdown(f'<div class="th-card th-stat">{ring_html(pct, f"{pct}%", "weekly")}<div><b>Weekly progress</b><div class="th-note">{sum(counts)} of {len(habits) * 7} habit check-ins</div></div></div>', unsafe_allow_html=True)
    bars = "".join(f'<div><i style="height:{max(4, n / len(habits) * 56):.0f}px"></i>{d:%a}</div>' for d, n in zip(days, counts))
    st.markdown(f'<div class="th-card"><b>Last 7 days</b><div class="th-bars">{bars}</div></div>', unsafe_allow_html=True)
    st.markdown("**Today**")
    for h in habits:
        key = f"hb_{today()}_{h['id']}"
        with st.container(border=True):
            st.checkbox(f"{h['name']}" + (f" · {h['target']}" if h.get("target") else ""), value=(today(), h["id"]) in logged, key=key,
                        on_change=toggle_event, args=(c["id"], "habit", h["id"], h["name"], key))


def totals_for(c, d):
    t = {"kcal": 0.0, "p": 0.0, "c": 0.0, "f": 0.0}
    for x in c["food_log"]:
        if x["d"] == d:
            for k in t:
                t[k] += fnum(x.get(k))
    return t



def save_meal_response(cid, date, meal, status, actual, slot):
    c = B.get(cid)
    if not c:
        return
    if status == "Ate something else" and not actual.strip():
        return False
    event_set(c, date, "meal", meal["id"], status == "Ate the planned meal", meal["text"])
    logs = c.setdefault("food_log", [])
    logs[:] = [x for x in logs if not (x.get("d") == date and x.get("plan_ref") == meal["id"])]
    if status == "Ate something else":
        logs.append({"id": uid(), "d": date, "meal": slot, "name": actual.strip(), "plan_ref": meal["id"],
                     "planned": meal["text"], "kcal": 0, "p": 0, "c": 0, "f": 0, "nutrition_unknown": True})
    save_client(c)
    return True


def tab_nutrition(c):
    st.markdown('<div class="th-title">Nutrition</div>', unsafe_allow_html=True)
    d = st.date_input("Date", value=now().date(), max_value=now().date(), key="nut_date").isoformat()
    mode = st.segmented_control("View", ["Log", "Plan"], default="Log", key="nut_mode", label_visibility="collapsed") or "Log"
    mac = c["diet"]["macros"]
    nutrition_progress(c)
    with st.expander("Trainer’s suggestions"):
        if c["diet"]["meals"]:
            st.write(f"Daily targets: {mac['kcal']} kcal · Protein {mac['p']} g · Carbs {mac['c']} g · Fat {mac['f']} g")
            st.caption("Open Plan to view your trainer’s meals and record whether you followed them.")
        else:
            st.info("Your trainer has not added diet suggestions yet. You can still record your meals in Log.")
    if mode == "Plan":
        st.markdown(f'<div class="th-card"><b>Daily targets</b><div class="th-macros" style="margin-top:12px"><div><b>{mac["kcal"]}</b><span>kcal</span></div><div><b>{mac["p"]} g</b><span>Protein</span></div><div><b>{mac["c"]} g</b><span>Carbs</span></div></div><div class="th-note" style="margin-top:10px">Fat {mac["f"]} g · Diet: {esc(c["profile"].get("diet") or "not set")}</div></div>', unsafe_allow_html=True)
        meals = c["diet"]["meals"]
        if not meals:
            st.markdown('<div class="th-card th-empty">Your trainer has not added a meal plan yet.</div>', unsafe_allow_html=True)
        for m in meals:
            with st.container(border=True):
                st.markdown(f"**{fmt_time(m['time'])} · {m['text']}**")
                replacement = next((x for x in c.get("food_log", []) if x.get("d") == d and x.get("plan_ref") == m["id"]), None)
                statuses = ["Not recorded", "Ate the planned meal", "Ate something else"]
                current_status = "Ate the planned meal" if is_done(c, d, "meal", m["id"]) else "Ate something else" if replacement else "Not recorded"
                with st.form(f"meal_response_{m['id']}_{d}"):
                    status = st.radio("Meal status", statuses, index=statuses.index(current_status), key=f"meal_status_{m['id']}_{d}")
                    slot = st.selectbox("Meal", MEAL_SLOTS, index=MEAL_SLOTS.index(replacement["meal"]) if replacement and replacement["meal"] in MEAL_SLOTS else 0, key=f"meal_slot_{m['id']}_{d}")
                    actual = st.text_area("What did you eat instead?", value=replacement["name"] if replacement else "", key=f"meal_actual_{m['id']}_{d}", placeholder="Fill this in if you ate something else.")
                    if st.form_submit_button("Save meal status", type="primary"):
                        if save_meal_response(c["id"], d, m, status, actual, slot):
                            st.rerun()
                        else:
                            st.error("Enter what you ate instead.")
                if replacement:
                    st.caption("Recorded instead: " + replacement["name"])
                with st.expander("Reminder"):
                    calendar_buttons(f"ics_m_{m['id']}", f"Meal: {m['text']}", f"Daily meal reminder from {c.get('trainer') or 'your trainer'}", next_at(m["time"]), 20, True)
        return
    st.caption("Record what you ate for breakfast, lunch, dinner or snacks. A trainer meal plan is not required; calories and macros are optional.")
    t = totals_for(c, d)
    if any(x.get("d") == d and x.get("nutrition_unknown") for x in c.get("food_log", [])):
        st.caption("Nutrition totals include only the calories and macros you entered; unestimated foods are excluded.")
    pc = lambda a, b: round(a / b * 100) if b else 0
    st.markdown(
        f'<div class="th-card th-stat">{ring_html(pc(t["kcal"], mac["kcal"]), f"{t["kcal"]:.0f}", "cal")}'
        f'<div class="th-macros"><div><b>{pc(t["c"], mac["c"])}%</b><span>{t["c"]:.0f} g Carbs</span></div><div><b>{pc(t["f"], mac["f"])}%</b><span>{t["f"]:.0f} g Fat</span></div>'
        f'<div><b>{pc(t["p"], mac["p"])}%</b><span>{t["p"]:.0f} g Protein</span></div></div></div>', unsafe_allow_html=True)
    for slot in MEAL_SLOTS:
        items = [x for x in c["food_log"] if x["d"] == d and x["meal"] == slot]
        with st.expander(f"{slot} · {len(items)} entries", expanded=True):
            for x in items:
                a, b = st.columns([5, 1])
                a.markdown(f"**{x['name']}**")
                a.caption("Calories and macros not entered" if x.get("nutrition_unknown") else f"{fnum(x.get('kcal')):.0f} kcal · P {fnum(x.get('p')):.0f} · C {fnum(x.get('c')):.0f} · F {fnum(x.get('f')):.0f}")
                if b.button("✕", key=f"fd_{x['id']}"):
                    cc = B.get(c["id"])
                    cc["food_log"] = [y for y in cc["food_log"] if y["id"] != x["id"]]
                    save_client(cc)
                    st.rerun()
            with st.form(f"food_{slot}_{d}", clear_on_submit=True):
                nm = st.text_input("What did you eat?", placeholder="For example: idli, sambar and coffee", key=f"fn_{slot}_{d}")
                with st.expander("Calories and macros (optional client entry)"):
                    a, b, c2, d2 = st.columns(4)
                kc = a.number_input("kcal", 0, 5000, 0, key=f"fk_{slot}_{d}")
                pr = b.number_input("Protein g", 0, 500, 0, key=f"fp_{slot}_{d}")
                cb = c2.number_input("Carbs g", 0, 800, 0, key=f"fc_{slot}_{d}")
                ft = d2.number_input("Fat g", 0, 500, 0, key=f"ff_{slot}_{d}")
                if st.form_submit_button("Add food", type="primary"):
                    if nm.strip():
                        cc = B.get(c["id"])
                        cc["food_log"].append({"id": uid(), "d": d, "meal": slot, "name": nm.strip(), "kcal": kc, "p": pr, "c": cb, "f": ft, "nutrition_unknown": not any((kc, pr, cb, ft))})
                        save_client(cc)
                        st.rerun()
                    else:
                        st.error("Enter a food name.")


def tab_profile(c):
    st.markdown('<div class="th-title">Profile</div>', unsafe_allow_html=True)
    p = c["profile"]
    st.markdown(f'<div class="th-card" style="display:flex;gap:14px;align-items:center"><div class="th-av">{esc(c["name"][0].upper())}</div><div><b>{esc(c["name"])}</b><div class="th-note">Trainer: {esc(c.get("trainer") or "Not assigned")}</div></div></div>', unsafe_allow_html=True)
    with st.expander("Check-in", expanded=False):
        with st.form("checkin"):
            en = st.slider("Energy (1 low – 5 high)", 1, 5, 4)
            sl = st.slider("Sleep (1 poor – 5 great)", 1, 5, 4)
            so = st.text_input("Soreness or pain")
            nt = st.text_area("Notes for your trainer")
            if st.form_submit_button("Send check-in", type="primary"):
                cc = B.get(c["id"])
                cc["checkins"].append({"d": today(), "energy": en, "sleep": sl, "sore": so or "None", "notes": nt})
                save_client(cc)
                st.rerun()
        for k in c["checkins"][-4:][::-1]:
            st.caption(f"{k['d']} · energy {k['energy']} · sleep {k['sleep']} · {k.get('sore', '')}")
    with st.expander("Gallery"):
        st.caption("Only you and your trainer can see these photos.")
        with st.form("photo", clear_on_submit=True):
            pose = st.selectbox("Pose", ["Front", "Side", "Back"])
            up = st.file_uploader("Photo", type=["jpg", "jpeg", "png", "webp"])
            if st.form_submit_button("Upload photo", type="primary") and up is not None:
                key = B.upload_private(c["id"], re.sub(r"[^\w.\-]+", "_", up.name), up.getvalue(), up.type)
                cc = B.get(c["id"])
                cc["photos"].append({"id": uid(), "d": today(), "pose": pose, "key": key})
                save_client(cc)
                st.rerun()
        pics = c["photos"][-6:][::-1]
        if pics:
            cols = st.columns(3)
            for i, ph in enumerate(pics):
                try:
                    cols[i % 3].image(photo_bytes(ph["key"]), caption=f"{ph['pose']} · {ph['d']}", width="stretch")
                except Exception:
                    cols[i % 3].caption("Photo unavailable")
    with st.expander("My details"):
        with st.form("details"):
            a, b = st.columns(2)
            h = a.number_input("Height (cm)", 100.0, 250.0, float(p.get("height_cm") or 165.0), 0.5)
            w = b.number_input("Weight (kg)", 25.0, 300.0, float(c["weights"][-1]["w"] if c["weights"] else p.get("weight_kg") or 65.0), 0.1)
            diet = st.selectbox("Preferred diet", DIETS, index=DIETS.index(p["diet"]) if p.get("diet") in DIETS else 0)
            goal = st.radio("Goal", GOALS, index=GOALS.index(p["goal"]) if p.get("goal") in GOALS else 0, horizontal=True)
            style = st.radio("Training style", STYLES, index=STYLES.index(p["style"]) if p.get("style") in STYLES else 0)
            if st.form_submit_button("Save details", type="primary"):
                cc = B.get(c["id"])
                cc["profile"].update(height_cm=h, weight_kg=w, diet=diet, goal=goal, style=style)
                cc["weights"] = [x for x in cc["weights"] if x["d"] != today()] + [{"d": today(), "w": round(w, 1)}]
                cc["weights"].sort(key=lambda x: x["d"])
                save_client(cc)
                st.rerun()
    if len(c["weights"]) >= 2:
        df = pd.DataFrame(c["weights"]).rename(columns={"d": "date", "w": "weight"})
        df["date"] = pd.to_datetime(df["date"])
        with st.container(border=True):
            st.markdown("**Body weight (kg)**")
            st.altair_chart(alt.Chart(df).mark_line(point=True, color="#4A94F2", strokeWidth=2.4).encode(
                x=alt.X("date:T", title=None), y=alt.Y("weight:Q", scale=alt.Scale(zero=False), title=None), tooltip=["date:T", "weight"]).properties(height=200), width="stretch")
    if st.button("Log out", width="stretch"):
        ss["client_id"] = None
        ss["gw"] = None
        st.rerun()


def client_flow():
    if not ss.get("client_id"):
        return client_login()
    c = B.get(ss["client_id"])
    if not c:
        ss["client_id"] = None
        st.rerun()
    if c.get("must_change_pin") or not c.get("onboarded"):
        return onboarding(c)
    if ss.get("_toast"):
        st.toast(ss.pop("_toast"))
    lib_map = {l["id"]: l for l in get_lib()}
    ss.setdefault("nav", "🏠")
    with st.container(key="bottomnav"):
        st.radio("Menu", NAV, key="nav", horizontal=True, label_visibility="collapsed", format_func=lambda x: x)
    page = ss["nav"]
    {"🏠": lambda: tab_home(c, lib_map), "🏋️": lambda: tab_training(c, lib_map), "🌿": lambda: tab_habit(c),
     "🍎": lambda: tab_nutrition(c), "👤": lambda: tab_profile(c)}[page]()


# ----------------------------------------------------------------------------
# Trainer: overview
# ----------------------------------------------------------------------------
def frames(clients):
    ev, wt, ci = [], [], []
    for c in clients:
        ev += [{"client": c["name"], "trainer": c.get("trainer", ""), "date": e["d"], "type": e["k"], "item": e.get("label", "")} for e in c["events"]]
        wt += [{"client": c["name"], "date": w["d"], "weight": w["w"]} for w in c["weights"]]
        ci += [{"client": c["name"], "date": k["d"], "energy": k["energy"], "sleep": k["sleep"], "soreness": k.get("sore", ""), "notes": k.get("notes", "")} for k in c["checkins"]]
    mk = lambda rows, cols: pd.DataFrame(rows, columns=cols).assign(date=lambda d: pd.to_datetime(d["date"]))
    return (mk(ev, ["client", "trainer", "date", "type", "item"]), mk(wt, ["client", "date", "weight"]), mk(ci, ["client", "date", "energy", "sleep", "soreness", "notes"]))


def in_range(df, a, b):
    return df[(df["date"] >= pd.Timestamp(a)) & (df["date"] <= pd.Timestamp(b))]


def to_csv(df):
    out = df.copy()
    if "date" in out:
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.to_csv(index=False).encode()


def pin_notice():
    if ss.get("_pins"):
        st.warning("Starter PINs are shown only once. Give each client their PIN. They will choose their own at first login.")
        df = pd.DataFrame(ss["_pins"], columns=["Client", "Starter PIN"])
        st.dataframe(df, hide_index=True, width="stretch")
        a, b = st.columns([1, 4])
        a.download_button("Download PINs", df.to_csv(index=False).encode(), "starter-pins.csv", "text/csv")
        if b.button("I have saved them. Hide this list"):
            ss["_pins"] = None
            st.rerun()


def seed_button(label="Set up my 10 clients"):
    if st.button(label, type="primary"):
        made = seed_clients()
        ss["_pins"] = (ss.get("_pins") or []) + made
        ss["_reset_sel"] = True
        st.rerun()


def page_overview(clients, sel_ids, start, end):
    pin_notice()
    if not clients:
        hero("Training programs", "Start with your client list.", "One click adds Anton, Dharan, Rekha, Divya, Venky, Sheethal, Varshni, Swetha, Guhan and Kevin with the plans you described. You can edit everything afterwards.")
        seed_button()
        st.caption("Or open **Manage clients** to add people one by one.")
        return
    cs = [c for c in clients if c["id"] in sel_ids]
    hero("Training programs", "Find the progress story behind every client.", "Training, habits, check-ins and body weight for your whole roster in one place.")
    if not cs:
        st.info("Pick at least one client in the sidebar to see charts.")
        return
    ev, wt, ci = frames(cs)
    length = (end - start).days + 1
    p_end, p_start = start - dt.timedelta(days=1), start - dt.timedelta(days=length)
    cur_ev, prev_ev = in_range(ev, start, end), in_range(ev, p_start, p_end)
    cur_ci, prev_ci = in_range(ci, start, end), in_range(ci, p_start, p_end)
    n_ex, p_ex = int((cur_ev.type == "ex").sum()), int((prev_ev.type == "ex").sum())
    n_hab, p_hab = int((cur_ev.type == "habit").sum()), int((prev_ev.type == "habit").sum())
    active = cur_ev.client.nunique()
    en = cur_ci.energy.mean() if len(cur_ci) else None
    pen = prev_ci.energy.mean() if len(prev_ci) else None
    kpi_cards([("Active clients", f"{active} / {len(cs)}", pill("All clients active", "up") if active == len(cs) else pill("Clients with activity")),
               ("Exercises completed", f"{n_ex:,}", delta_pill(n_ex, p_ex)), ("Habits logged", f"{n_hab:,}", delta_pill(n_hab, p_hab)),
               ("Average energy score", "—" if en is None else f"{en:.1f}", delta_pill(en, pen, True))])

    st.header("Explore by client")
    cards = []
    for c in cs:
        n = int(((cur_ev.client == c["name"]) & (cur_ev.type == "ex")).sum())
        p = c["profile"]
        lw = c["weights"][-1]["w"] if c["weights"] else None
        lc = c["checkins"][-1]["d"] if c["checkins"] else None
        since = f"{(now().date() - dobj(lc)).days} days ago" if lc else "None yet"
        ph, wk, ov = phase_for(c)
        tags = "".join(f'<span class="th-chip">{esc(x)}</span>' for x in [p.get("goal"), p.get("style")] if x)
        cards.append(f'<div class="th-card"><div style="display:flex;gap:12px;align-items:center"><div class="th-av" style="background:{client_color(clients, c)}">{esc(c["name"][0].upper())}</div>'
                     f'<div><b>{esc(c["name"])}</b><br><span class="th-note">Trainer: {esc(c.get("trainer") or "Not assigned")}</span></div></div>'
                     f'<div style="margin-top:10px">{tags}</div><dl><div><dt>Programme</dt><dd>{esc(ph["name"]) if ph else "—"}</dd></div><div><dt>Exercises in period</dt><dd>{n}</dd></div>'
                     f'<div><dt>Weight</dt><dd>{"—" if lw is None else f"{lw} kg"}</dd></div><div><dt>Height</dt><dd>{p.get("height_cm") or "—"} cm</dd></div>'
                     f'<div><dt>Diet</dt><dd>{esc(p.get("diet") or "—")}</dd></div><div><dt>Last check-in</dt><dd>{since}</dd></div></dl></div>')
    st.markdown(f'<div class="th-cc">{"".join(cards)}</div>', unsafe_allow_html=True)

    names = [c["name"] for c in cs]
    scale = alt.Scale(domain=names, range=[client_color(clients, c) for c in cs])
    st.header("Client movement")
    l, r = st.columns([1.9, 1])
    with l.container(border=True):
        st.subheader("Body weight by client (kg)")
        w = in_range(wt, start, end)
        if len(w) < 2:
            st.caption("Clients' weigh-ins will appear here.")
        else:
            st.altair_chart(alt.Chart(w).mark_line(point=True, strokeWidth=2.2).encode(x=alt.X("date:T", title=None), y=alt.Y("weight:Q", title="kg", scale=alt.Scale(zero=False)),
                            color=alt.Color("client:N", scale=scale, legend=alt.Legend(orient="top", title=None)), tooltip=["client", "date:T", "weight"]).properties(height=300), width="stretch")
    with r.container(border=True):
        st.subheader(f"Training position · {end:%b %d}")
        tot = pd.DataFrame({"client": names, "exercises": [int(((cur_ev.client == n) & (cur_ev.type == "ex")).sum()) for n in names]})
        st.altair_chart(alt.Chart(tot).mark_bar(cornerRadiusEnd=6).encode(y=alt.Y("client:N", sort="-x", title=None), x=alt.X("exercises:Q", title=None),
                        color=alt.Color("client:N", scale=scale, legend=None), tooltip=["client", "exercises"]).properties(height=300), width="stretch")
    with st.container(border=True):
        st.subheader("Training volume per week")
        ex_only = cur_ev[cur_ev.type == "ex"].copy()
        if ex_only.empty:
            st.caption("No completed exercises in this period yet.")
        else:
            ex_only["week"] = ex_only["date"].dt.to_period("W").dt.start_time
            wk_ = ex_only.groupby(["week", "client"]).size().reset_index(name="exercises")
            wk_["label"] = wk_["week"].dt.strftime("%b %d")
            st.altair_chart(alt.Chart(wk_).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(x=alt.X("label:O", sort=list(wk_.sort_values("week")["label"].unique()), title=None, axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("exercises:Q", title="Exercises"), xOffset="client:N", color=alt.Color("client:N", scale=scale, legend=alt.Legend(orient="top", title=None)),
                            tooltip=["client", "label", "exercises"]).properties(height=280), width="stretch")

    st.header("Attention and exceptions")
    recent = ci[(ci.date > pd.Timestamp(end) - pd.Timedelta(days=7)) & (ci.date <= pd.Timestamp(end))].client.nunique()
    pct = round(recent / len(cs) * 100)
    low = int((cur_ci.energy <= 2).sum())
    l, r = st.columns([1, 2.2])
    l.markdown(f'<div class="th-card"><b>Check-in health</b><div style="font-size:3rem;font-weight:600;color:#6EA3F5;margin:10px 0 4px">{pct}%</div><div class="th-note" style="margin-bottom:12px">{recent} of {len(cs)} clients checked in during the 7 days to {end:%b %d}</div>'
               f'{pill("On track", "up") if pct >= 80 else pill("Follow up needed", "dn")}<div class="th-note" style="margin-top:12px">{low} low-energy check-ins in this period</div></div>', unsafe_allow_html=True)
    with r.container(border=True):
        st.subheader("Weekly check-in energy")
        if cur_ci.empty:
            st.caption("No weekly check-ins in this period.")
        else:
            cc = cur_ci.assign(flag=lambda d: d.energy.apply(lambda v: "Low energy (1–2)" if v <= 2 else "Healthy (3–5)"))
            st.altair_chart(alt.Chart(cc).mark_circle(size=190, opacity=.9).encode(x=alt.X("date:T", title=None), y=alt.Y("energy:Q", scale=alt.Scale(domain=[0.5, 5.5]), title="Energy"),
                            color=alt.Color("flag:N", scale=alt.Scale(domain=["Healthy (3–5)", "Low energy (1–2)"], range=["#34D399", "#FB7185"]), legend=alt.Legend(orient="top", title=None)),
                            tooltip=["client", "date:T", "energy", "sleep", "soreness"]).properties(height=240), width="stretch")

    st.header("Recent client activity")
    rows = [(r_.date, r_.client, {"ex": "Exercise done", "workout": "Workout completed", "bonus_workout": "Bonus workout completed", "meal": "Meal on plan", "habit": "Habit"}.get(r_.type, r_.type), r_["item"]) for _, r_ in cur_ev.iterrows()]
    rows += [(r_.date, r_.client, "Weigh-in", f"{r_.weight} kg") for _, r_ in in_range(wt, start, end).iterrows()]
    rows += [(r_.date, r_.client, "Check-in", f"Energy {r_.energy} · Sleep {r_.sleep}") for _, r_ in cur_ci.iterrows()]
    act = pd.DataFrame(rows, columns=["Date", "Client", "Activity", "Detail"]).sort_values("Date", ascending=False).head(15)
    act["Date"] = pd.to_datetime(act["Date"]).dt.strftime("%b %d, %Y")
    st.dataframe(act, hide_index=True, width="stretch")
    st.header("Download center")
    d1, d2, d3 = st.columns(3)
    d1.download_button("Download activity", to_csv(cur_ev), "activity.csv", "text/csv", width="stretch")
    d2.download_button("Download weigh-ins", to_csv(in_range(wt, start, end)), "weigh-ins.csv", "text/csv", width="stretch")
    d3.download_button("Download check-ins", to_csv(cur_ci), "check-ins.csv", "text/csv", width="stretch")


# ----------------------------------------------------------------------------
# Trainer: manage clients
# ----------------------------------------------------------------------------
def apply_day_form(c, d, updates, title, weekday):
    d["title"], d["weekday"] = title.strip() or d["title"], weekday
    new, acts = [], []
    for e, vals, up, act in updates:
        e.update(vals)
        if up is not None:
            try:
                e["media"] = upload_media(c["id"], up)
            except Exception as exc:
                st.error(f"Upload failed for {e['name']}: {exc}")
        if act == "Remove":
            continue
        new.append(e)
        acts.append(act)
        if act == "Duplicate":
            new.append(clone_ex(e))
            acts.append("Keep")
    i = 0
    while i < len(new):
        if acts[i] == "Move up" and i > 0:
            new[i], new[i - 1] = new[i - 1], new[i]
            acts[i], acts[i - 1] = acts[i - 1], acts[i]
        elif acts[i] == "Move down" and i < len(new) - 1:
            new[i], new[i + 1] = new[i + 1], new[i]
            acts[i], acts[i + 1] = acts[i + 1], acts[i]
            i += 1
        i += 1
    d["exercises"] = new


def day_editor(c, ph, d, clients, lib):
    wd = "Any day" if d["weekday"] == -1 else WEEKDAYS[d["weekday"]]
    with st.expander(f"{d['title']} · {wd} · {len(d['exercises'])} exercises"):
        with st.form(f"day_{d['id']}"):
            a, b = st.columns([3, 1.3])
            title = a.text_input("Day name", d["title"], key=f"dn_{d['id']}")
            wdsel = b.selectbox("Day of week", [-1] + list(range(7)), index=d["weekday"] + 1, format_func=lambda x: "Any day" if x == -1 else WEEKDAYS[x], key=f"dw_{d['id']}")
            updates = []
            for i, e in enumerate(d["exercises"]):
                st.markdown(f"**{i + 1}. {e['name']}**")
                k = e["id"]
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1.4])
                vals = {"name": c1.text_input("Name", e["name"], key=f"n_{k}"), "sets": c2.text_input("Sets", e["sets"], key=f"s_{k}"),
                        "reps": c3.text_input("Reps", e["reps"], key=f"r_{k}"), "rest": c4.text_input("Rest", e.get("rest", ""), key=f"rs_{k}")}
                c5, c6 = st.columns(2)
                vals["target"] = c5.text_input("Weight / target", e.get("target", ""), key=f"t_{k}")
                vals["video"] = c6.text_input("Video link (optional)", e.get("video", ""), key=f"v_{k}")
                vals["notes"] = st.text_input("Coaching notes", e.get("notes", ""), key=f"no_{k}")
                lm = next((x for x in lib if x["id"] == e.get("lib_id")), None)
                state = ("own animation" if e.get("media") else "own link" if (e.get("video") or "").strip() else "library animation" if lm and lm.get("media")
                         else "library link" if lm and (lm.get("video") or "").strip() else "no video yet")
                up = st.file_uploader(f"3D animation or video for this client ({state}). Gif, webp, mp4", type=["gif", "webp", "mp4", "mov", "webm"], key=f"u_{k}")
                act = st.selectbox("Action", ["Keep", "Move up", "Move down", "Duplicate", "Remove"], key=f"a_{k}")
                updates.append((e, vals, up, act))
            if st.form_submit_button("Save day", type="primary"):
                apply_day_form(c, d, updates, title, wdsel)
                save_client(c)
                st.rerun()
        st.markdown("**Add exercises**")
        g1, g2, g3 = st.columns([1.2, 2.4, 1])
        grp = g1.selectbox("Category", ["All"] + LIB_GROUPS, format_func=glabel, key=f"lg_{d['id']}")
        opts = [x for x in lib if in_cat(x, grp)]
        pick = g2.selectbox("Exercise from library", [x["id"] for x in opts], format_func=lambda i: next(x["name"] for x in opts if x["id"] == i), key=f"lp_{d['id']}") if opts else None
        if g3.button("Add", key=f"la_{d['id']}", disabled=pick is None, width="stretch"):
            d["exercises"].append(ex_from_lib(next(x for x in lib if x["id"] == pick)))
            save_client(c)
            st.rerun()
        if st.button("Add a blank exercise", key=f"lb_{d['id']}"):
            d["exercises"].append({"id": uid(), "lib_id": "", "name": "New exercise", "group": "", "sets": "3", "reps": "15", "rest": "1 min", "target": "", "notes": "", "video": "", "media": ""})
            save_client(c)
            st.rerun()
        st.markdown("**Copy or remove this day**")
        others = [x for x in clients if x["id"] != c["id"]]
        tg = st.multiselect("Copy this day to other clients", [x["id"] for x in others], format_func=lambda i: next(x["name"] for x in others if x["id"] == i), key=f"cp_{d['id']}")
        r1, r2, r3 = st.columns(3)
        if r1.button("Copy to selected clients", key=f"cpb_{d['id']}", disabled=not tg, width="stretch"):
            for t in others:
                if t["id"] in tg:
                    tph, _, _ = phase_for(t)
                    if tph is None:
                        tph = new_phase()
                        t["program"]["phases"].append(tph)
                    tph["days"].append(clone_day(d))
                    save_client(t)
            st.success(f"Copied to {len(tg)} client(s).")
        if r2.button("Duplicate day", key=f"dd_{d['id']}", width="stretch"):
            ph["days"].append(clone_day(d))
            save_client(c)
            st.rerun()
        if r3.button("Remove day", key=f"rd_{d['id']}", width="stretch"):
            ph["days"] = [x for x in ph["days"] if x["id"] != d["id"]]
            save_client(c)
            st.rerun()


def program_editor(c, clients, lib):
    prog = c["program"]
    with st.form(f"pstart_{c['id']}"):
        a, b = st.columns([2, 1])
        start = a.date_input("Programme start date", dobj(prog["start"]))
        if b.form_submit_button("Save start date"):
            prog["start"] = start.isoformat()
            save_client(c)
            st.rerun()
    ph_now, wk, ov = phase_for(c)
    if ph_now:
        st.caption(f"Today the client is in: {ph_now['name']} (week {ov} of the programme).")
    for ph in prog["phases"]:
        with st.container(border=True):
            with st.form(f"ph_{ph['id']}"):
                a, b, s = st.columns([3, 1.3, 1])
                nm = a.text_input("Phase name", ph["name"], key=f"pn_{ph['id']}")
                wk_ = b.number_input("Weeks (0 = ongoing)", 0, 52, int(ph.get("weeks") or 0), key=f"pw_{ph['id']}")
                s.write("")
                if s.form_submit_button("Save phase"):
                    ph["name"], ph["weeks"] = nm.strip() or ph["name"], wk_
                    save_client(c)
                    st.rerun()
            for d in ph["days"]:
                day_editor(c, ph, d, clients, lib)
            a, b, e_ = st.columns(3)
            if a.button("Add workout day", key=f"ad_{ph['id']}", width="stretch"):
                ph["days"].append(new_day(f"Day {len(ph['days']) + 1}"))
                save_client(c)
                st.rerun()
            if b.button("Duplicate phase", key=f"dp_{ph['id']}", width="stretch"):
                prog["phases"].append(clone_phase(ph))
                save_client(c)
                st.rerun()
            if e_.button("Remove phase", key=f"rp_{ph['id']}", width="stretch", disabled=len(prog["phases"]) <= 1):
                prog["phases"] = [x for x in prog["phases"] if x["id"] != ph["id"]]
                save_client(c)
                st.rerun()
    if st.button("Add a phase (for example, the next block)", key=f"np_{c['id']}"):
        prog["phases"].append(new_phase(f"Phase {len(prog['phases']) + 1}"))
        save_client(c)
        st.rerun()
    others = [x for x in clients if x["id"] != c["id"]]
    st.markdown("**Copy this whole programme**")
    tg = st.multiselect("Copy all phases and days to", [x["id"] for x in others], format_func=lambda i: next(x["name"] for x in others if x["id"] == i), key=f"cpa_{c['id']}")
    mode = st.radio("How", ["Add to their existing programme", "Replace their programme"], horizontal=True, key=f"cpm_{c['id']}")
    if st.button("Copy programme", key=f"cpg_{c['id']}", disabled=not tg):
        for t in others:
            if t["id"] in tg:
                phases = [clone_phase(p) for p in prog["phases"]]
                if mode.startswith("Replace"):
                    t["program"] = {"start": prog["start"], "phases": phases}
                else:
                    t["program"]["phases"] += phases
                save_client(t)
        st.success(f"Copied to {len(tg)} client(s).")


def clean_time(t):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", str(t or ""))
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return "12:00"


def diet_pdf_import(c, clients):
    st.markdown("**Fill the diet plan from a PDF**")
    n = ss.setdefault(f"dpdf_n_{c['id']}", 0)
    up = st.file_uploader("Drop a diet plan PDF here", type=["pdf"], key=f"dpdf_{c['id']}_{n}",
                          help="Works best when each meal has a name (Breakfast, Lunch) or a time (8:00 AM).")
    pkey = f"dpp_{c['id']}"
    if up is None:
        ss.pop(pkey, None)
        return
    sig = f"{up.name}-{up.size}"
    if ss.get(pkey, {}).get("sig") != sig:
        try:
            text = extract_text(up.getvalue())
        except Exception as exc:
            st.error(f"Could not read that PDF: {exc}")
            return
        if not text.strip():
            st.warning("This PDF has no text I can read (it may be a scan or a photo). Export it again as a text PDF, or type the plan below.")
            return
        ss[pkey] = {"sig": sig, "text": text, **parse_diet(text)}
    pr = ss[pkey]
    if not pr["meals"] and not pr["macros"]:
        st.warning("I could not find meals or targets in this PDF. See what I read below, and add the meals by hand.")
    else:
        st.success(f"Found {len(pr['meals'])} meal(s)" + (" and daily targets. Check them, then apply." if pr["macros"] else ". No daily targets found, so the current ones stay."))
    cur = c["diet"]["macros"]
    k = f"{pkey}_{pr['sig']}"
    m1, m2, m3, m4 = st.columns(4)
    kcal = m1.number_input("Calories", 0, 10000, int(pr["macros"].get("kcal", cur["kcal"])), key=f"pk_{k}")
    pro = m2.number_input("Protein (g)", 0, 1000, int(pr["macros"].get("p", cur["p"])), key=f"pp_{k}")
    carb = m3.number_input("Carbs (g)", 0, 1500, int(pr["macros"].get("c", cur["c"])), key=f"pc_{k}")
    fat = m4.number_input("Fat (g)", 0, 1000, int(pr["macros"].get("f", cur["f"])), key=f"pf_{k}")
    df = pd.DataFrame(pr["meals"] or [{"time": "08:00", "text": ""}], columns=["time", "text"]).rename(columns={"time": "Time (24h, like 13:00)", "text": "Meal"})
    edited = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key=f"pe_{k}")
    mode = st.radio("How to apply", ["Replace the current meals", "Add to the current meals"], horizontal=True, key=f"pm_{pkey}")
    others = [x for x in clients if x["id"] != c["id"]]
    also = st.multiselect("Also apply to these clients", [x["id"] for x in others], format_func=lambda i: next(x["name"] for x in others if x["id"] == i), key=f"pa_{pkey}")
    with st.expander("What I read from the PDF"):
        st.text(pr["text"][:6000])
    if st.button(f"Apply to {c['name']}'s diet plan", type="primary", key=f"pb_{pkey}"):
        meals = [{"time": clean_time(r.iloc[0]), "text": str(r.iloc[1]).strip()} for _, r in edited.iterrows() if str(r.iloc[1]).strip() not in ("", "nan", "None")]
        for t in [c] + [x for x in others if x["id"] in also]:
            t["diet"]["macros"] = {"kcal": kcal, "p": pro, "c": carb, "f": fat}
            base = [] if mode.startswith("Replace") else t["diet"]["meals"]
            t["diet"]["meals"] = sorted(base + [{"id": uid(), "time": m["time"], "text": m["text"]} for m in meals], key=lambda q: q["time"])
            save_client(t)
        ss[f"dpdf_n_{c['id']}"] = n + 1
        ss.pop(pkey, None)
        ss["_toast_t"] = f"Diet plan applied to {1 + len(also)} client(s)."
        st.rerun()


def page_manage(clients):
    pin_notice()
    hero("Client management", "Build every plan in one place.", "Programmes, copy tools, diet, habits, coach notes and check-ins for each client.")
    a, b = st.columns([1, 1])
    with a.expander("Add a client", expanded=not clients):
        with st.form("add_client", clear_on_submit=True):
            name = st.text_input("Client name")
            trainer = st.text_input("Assigned trainer")
            if st.form_submit_button("Add client", type="primary"):
                if not name.strip():
                    st.error("Enter the client's name.")
                else:
                    c, pin = new_client(name.strip(), trainer.strip())
                    save_client(c)
                    ss["_pins"] = (ss.get("_pins") or []) + [(c["name"], pin)]
                    ss["manage_pick"] = c["id"]
                    ss["_add_sel"] = c["id"]
                    st.rerun()
    with b:
        seed_button("Add my 10 clients (skips names that exist)")
    if not clients:
        return
    ids = [c["id"] for c in clients]
    if ss.get("manage_pick") not in ids:
        ss["manage_pick"] = ids[0]
    cid = st.selectbox("Client", ids, key="manage_pick", format_func=lambda i: next(c["name"] for c in clients if c["id"] == i))
    c = next(x for x in clients if x["id"] == cid)
    lib = get_lib(create=True)
    t_prof, t_prog, t_diet, t_notes, t_check = st.tabs(["Profile", "Programme", "Diet and habits", "Coach notes", "Check-ins and photos"])

    with t_prof:
        with st.form(f"profile_{cid}"):
            a, b = st.columns(2)
            name = a.text_input("Client name", c["name"])
            trainer = b.text_input("Assigned trainer", c.get("trainer", ""))
            if st.form_submit_button("Save", type="primary"):
                c["name"], c["trainer"] = name.strip() or c["name"], trainer.strip()
                save_client(c)
                st.rerun()
        p = c["profile"]
        st.markdown("".join(f'<span class="th-chip">{esc(str(x))}</span>' for x in [f"{p.get('height_cm') or '—'} cm", f"{c['weights'][-1]['w'] if c['weights'] else '—'} kg",
                    p.get("diet") or "Diet not set", p.get("goal") or "Goal not set", p.get("style") or "Style not set"]), unsafe_allow_html=True)
        if p.get("notes"):
            st.caption(f"Client notes: {p['notes']}")
        st.markdown("**Access**")
        st.caption("Clients log in with their name and PIN. Resetting creates a new starter PIN they must replace at next login.")
        if st.button("Reset PIN", key=f"rp_{cid}"):
            pin = starter_pin()
            set_pin(c, pin, True)
            save_client(c)
            ss["_pins"] = (ss.get("_pins") or []) + [(c["name"], pin)]
            st.rerun()
        st.markdown("**Danger zone**")
        sure = st.checkbox(f"Yes, delete {c['name']} and all their history", key=f"sure_{cid}")
        if st.button("Delete client", disabled=not sure, key=f"del_{cid}"):
            B.delete(cid)
            load_all.clear()
            st.rerun()

    with t_prog:
        program_editor(c, clients, lib)

    with t_diet:
        if ss.get("_toast_t"):
            st.success(ss.pop("_toast_t"))
        diet_pdf_import(c, clients)
        st.markdown("**Targets and meals**")
        with st.form(f"diet_{cid}"):
            m = c["diet"]["macros"]
            m1, m2, m3, m4 = st.columns(4)
            kcal = m1.number_input("Calories", 0, 10000, int(m["kcal"]), key=f"mk_{cid}")
            pr = m2.number_input("Protein (g)", 0, 1000, int(m["p"]), key=f"mp_{cid}")
            cb = m3.number_input("Carbs (g)", 0, 1500, int(m["c"]), key=f"mc_{cid}")
            ft = m4.number_input("Fat (g)", 0, 1000, int(m["f"]), key=f"mf_{cid}")
            rows = []
            for meal in c["diet"]["meals"]:
                x, y, z = st.columns([1, 4, 1])
                tm = x.time_input("Time", dt.time.fromisoformat(meal["time"]), key=f"mt_{meal['id']}", label_visibility="collapsed")
                tx = y.text_input("Meal", meal["text"], key=f"mx_{meal['id']}", label_visibility="collapsed")
                gone = z.checkbox("Remove", key=f"mr_{meal['id']}")
                rows.append((meal, tm, tx, gone))
            if st.form_submit_button("Save nutrition plan", type="primary"):
                c["diet"]["macros"] = {"kcal": kcal, "p": pr, "c": cb, "f": ft}
                c["diet"]["meals"] = sorted([dict(me, time=tm.strftime("%H:%M"), text=tx.strip() or me["text"]) for me, tm, tx, gone in rows if not gone], key=lambda q: q["time"])
                save_client(c)
                st.rerun()
        if st.button("Add a meal", key=f"am_{cid}"):
            c["diet"]["meals"].append({"id": uid(), "time": "12:00", "text": "New meal"})
            save_client(c)
            st.rerun()
        st.markdown("**Habits**")
        with st.form(f"habits_{cid}"):
            hrows = []
            for h in c["habits"]:
                x, y, z = st.columns([3, 3, 1])
                hn = x.text_input("Habit", h["name"], key=f"hn_{h['id']}", label_visibility="collapsed")
                ht = y.text_input("Target", h.get("target", ""), key=f"ht_{h['id']}", label_visibility="collapsed", placeholder="Target, e.g. 8,000 steps")
                gone = z.checkbox("Remove", key=f"hr_{h['id']}")
                hrows.append((h, hn, ht, gone))
            if st.form_submit_button("Save habits", type="primary"):
                c["habits"] = [dict(h, name=hn.strip() or h["name"], target=ht) for h, hn, ht, gone in hrows if not gone]
                save_client(c)
                st.rerun()
        if st.button("Add a habit", key=f"ah_{cid}"):
            c["habits"].append({"id": uid(), "name": "Steps", "target": "8,000 steps"})
            save_client(c)
            st.rerun()

    with t_notes:
        with st.form(f"note_{cid}", clear_on_submit=True):
            txt = st.text_area("New note for this client")
            if st.form_submit_button("Send note", type="primary") and txt.strip():
                c["coach_notes"].append({"id": uid(), "d": today(), "text": txt.strip()})
                save_client(c)
                st.rerun()
        for n in c["coach_notes"][::-1]:
            x, y = st.columns([6, 1])
            x.markdown(f"{n['text']}  \n<span class='th-note'>{n['d']}</span>", unsafe_allow_html=True)
            if y.button("Delete", key=f"dn2_{n['id']}"):
                c["coach_notes"] = [q for q in c["coach_notes"] if q["id"] != n["id"]]
                save_client(c)
                st.rerun()

    with t_check:
        if c["checkins"]:
            st.dataframe(pd.DataFrame(c["checkins"][::-1]).rename(columns={"d": "Date", "energy": "Energy", "sleep": "Sleep", "sore": "Soreness", "notes": "Notes"}), hide_index=True, width="stretch")
        else:
            st.caption("No check-ins yet.")
        if c["photos"]:
            cols = st.columns(4)
            for i, ph in enumerate(c["photos"][::-1][:12]):
                try:
                    cols[i % 4].image(photo_bytes(ph["key"]), caption=f"{ph['pose']} · {ph['d']}", width="stretch")
                except Exception:
                    cols[i % 4].caption("Photo unavailable")
        else:
            st.caption("No progress photos yet.")


# ----------------------------------------------------------------------------
# Trainer: exercise library
# ----------------------------------------------------------------------------
def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def page_library():
    hero("Exercise library", "One place for every exercise and its animation.", "Upload a 3D anatomy animation once and it shows for every client who has that exercise. You can still override it for one client.")
    lib = get_lib(create=True)
    have = sum(1 for l in lib if l.get("media"))
    links = sum(1 for l in lib if not l.get("media") and (l.get("video") or "").strip())
    st.markdown(f'<div class="th-card"><b>{len(lib)} exercises</b> · {have} with an animation · {links} with a link only · {len(lib) - have - links} with nothing yet</div>', unsafe_allow_html=True)
    st.caption("Use animations you made or have a licence to use. Do not upload clips copied from another app.")
    if st.button("Add the extra starter exercises (chest, triceps, back, biceps, shoulders, legs, abs, fat loss, muscle gain)"):
        n_added = add_starters(lib)
        save_lib(lib)
        st.success(f"Added {n_added} new exercise(s)." if n_added else "You already have all the starter exercises.")
        st.rerun() if n_added else None
    with st.expander("Bulk upload animations (match by file name)"):
        st.caption("Name each file after the exercise, for example Dumbbell Bench Press.gif. Matching ignores capitals and spacing.")
        files = st.file_uploader("Files", type=["gif", "webp", "mp4", "mov", "webm"], accept_multiple_files=True, key="bulk")
        if st.button("Match and upload", disabled=not files):
            by = {norm(l["name"]): l for l in lib}
            ok, miss = 0, []
            for f in files:
                l = by.get(norm(Path(f.name).stem))
                if l:
                    l["media"] = upload_media("lib", f)
                    ok += 1
                else:
                    miss.append(f.name)
            save_lib(lib)
            st.success(f"Uploaded {ok} animation(s).")
            if miss:
                st.warning("No match for: " + ", ".join(miss))
    with st.expander("Paste YouTube links for many exercises at once"):
        st.caption("Use this until you have your own animations. One exercise per line: the exercise name, a comma, then the link. Your own animation, once uploaded, shows instead of the link.")
        st.code("\n".join(f"{l['name']}, " for l in lib), language=None)
        txt = st.text_area("Your lines", key="bulk_links", height=200, placeholder="Dumbbell Bench Press, https://www.youtube.com/watch?v=...")
        apply_clicked = st.button("Apply links")
        if apply_clicked and not txt.strip():
            st.warning("Paste at least one line first.")
        if apply_clicked and txt.strip():
            by = {norm(l["name"]): l for l in lib}
            ok, miss = 0, []
            for line in txt.splitlines():
                if not line.strip():
                    continue
                m = re.match(r"^(.*?)\s*(?:\||,|\t)\s*(https?://\S+)\s*$", line.strip())
                l = by.get(norm(m.group(1))) if m else None
                if l:
                    l["video"] = m.group(2)
                    ok += 1
                else:
                    miss.append(line.strip()[:50])
            if ok:
                save_lib(lib)
            st.success(f"Saved {ok} link(s).") if ok else st.warning("No lines matched an exercise name.")
            if miss:
                st.warning("Could not match: " + "; ".join(miss))
    with st.expander("Add a new exercise"):
        with st.form("newlib", clear_on_submit=True):
            a, b = st.columns([3, 1.4])
            nm = a.text_input("Name")
            grp = b.selectbox("Main category", LIB_GROUPS, format_func=glabel)
            tags_new = st.multiselect("Also show under", LIB_GROUPS, format_func=glabel, key="newlib_tags")
            eq = st.text_input("Equipment")
            s, r, rs, tg = st.columns(4)
            sets, reps = s.text_input("Sets", "3"), r.text_input("Reps", "12")
            rest, tgt = rs.text_input("Rest", "1 min"), tg.text_input("Weight / target")
            cue = st.text_input("Coaching cue")
            vid = st.text_input("YouTube or video link (optional)")
            if st.form_submit_button("Add to library", type="primary") and nm.strip():
                lib.append({"id": "lib_" + slug(nm) + "_" + uid()[:4], "name": nm.strip(), "group": grp, "equipment": eq, "sets": sets, "reps": reps, "rest": rest, "target": tgt, "cue": cue, "media": "", "video": normalize_link(vid), "tags": [t for t in tags_new if t != grp]})
                save_lib(lib)
                st.rerun()
    clients = load_all(B.kind)
    basket = ss.setdefault("general_basket", [])
    with st.expander(f"Build a General workout ({len(basket)} selected)", expanded=True):
        if clients:
            target = st.selectbox("Client for General workout", [c["id"] for c in clients], format_func=lambda i: next(c["name"] for c in clients if c["id"] == i))
            selected = st.multiselect("Selected exercises — remove any you do not want", [l["id"] for l in lib], default=basket, format_func=lambda i: next(l["name"] for l in lib if l["id"] == i))
            ss["general_basket"] = selected
            if st.button("Send selection to General draft", disabled=not selected):
                draft = builder_draft(target)
                phase = next((p for p in draft["program"]["phases"] if p["name"] == "General"), None)
                if phase is None:
                    phase = new_phase("General", 0, [])
                    draft["program"]["phases"].insert(0, phase)
                phase["days"] = [new_day("General · Full body", [ex_from_lib(l) for i in selected for l in lib if l["id"] == i])]
                ss["bld_client"], ss["bld_phase"] = target, phase["id"]
                ss["bld_day"] = phase["days"][0]["id"]
                st.success("General draft ready. Open Workout builder, review it, and press Apply.")
        else:
            st.info("Add a client first.")
    q = st.text_input("Search", placeholder="Search exercises…")
    for grp in LIB_GROUPS:
        items = [l for l in lib if l["group"] == grp and (not q or q.lower() in l["name"].lower())]
        if not items:
            continue
        st.subheader(glabel(grp))
        for l in items:
            if st.button("Select for General", key=f"general_pick_{l['id']}", disabled=l["id"] in ss.get("general_basket", [])):
                ss["general_basket"].append(l["id"])
                st.rerun()
            with st.expander(f"{l['name']}  ·  {l['sets']}×{l['reps']}  ·  {'🎬 animation' if l.get('media') else '🔗 link' if (l.get('video') or '').strip() else '— no video'}"):
                with st.form(f"lib_{l['id']}"):
                    a, b = st.columns([3, 1.4])
                    nm = a.text_input("Name", l["name"], key=f"ln_{l['id']}")
                    gp = b.selectbox("Main category", LIB_GROUPS, index=LIB_GROUPS.index(l["group"]) if l["group"] in LIB_GROUPS else 0, format_func=glabel, key=f"lgp_{l['id']}")
                    tg_ = st.multiselect("Also show under", LIB_GROUPS, default=[t for t in (l.get("tags") or []) if t in LIB_GROUPS], format_func=glabel, key=f"ltg_{l['id']}")
                    eq = st.text_input("Equipment", l.get("equipment", ""), key=f"le_{l['id']}")
                    s, r, rs, tg = st.columns(4)
                    sets, reps = s.text_input("Sets", l["sets"], key=f"ls_{l['id']}"), r.text_input("Reps", l["reps"], key=f"lr_{l['id']}")
                    rest, tgt = rs.text_input("Rest", l.get("rest", ""), key=f"lrs_{l['id']}"), tg.text_input("Weight / target", l.get("target", ""), key=f"lt_{l['id']}")
                    cue = st.text_input("Coaching cue", l.get("cue", ""), key=f"lc_{l['id']}")
                    vid = st.text_input("YouTube or video link (used until you upload an animation)", l.get("video", ""), key=f"lv_{l['id']}")
                    up = st.file_uploader("Upload or replace the animation (gif, webp, mp4)", type=["gif", "webp", "mp4", "mov", "webm"], key=f"lu_{l['id']}")
                    gone = st.checkbox("Delete from library", key=f"lx_{l['id']}")
                    if st.form_submit_button("Save", type="primary"):
                        if gone:
                            lib[:] = [x for x in lib if x["id"] != l["id"]]
                        else:
                            l.update(name=nm.strip() or l["name"], group=gp, equipment=eq, sets=sets, reps=reps, rest=rest, target=tgt, cue=cue, video=normalize_link(vid), tags=[t for t in tg_ if t != gp])
                            if up is not None:
                                l["media"] = upload_media("lib", up)
                        save_lib(lib)
                        st.rerun()
                if l.get("media") or (l.get("video") or "").strip():
                    show_media(l.get("media") or l["video"].strip())


# ----------------------------------------------------------------------------
# Trainer shell
# ----------------------------------------------------------------------------
def trainer_login():
    hero("Trainer login", "Welcome back, coach.", "Sign in to build programmes and follow every client.")
    left, _ = st.columns([1, 1.4])
    with left:
        with st.container(border=True):
            pw_set = secret("TRAINER_PASSWORD")
            if not pw_set:
                st.error("No trainer password is set yet. Add TRAINER_PASSWORD to the app's Secrets (see the README), then reload.")
            else:
                with st.form("login"):
                    pw = st.text_input("Trainer password", type="password")
                    if st.form_submit_button("Log in", type="primary"):
                        if hmac.compare_digest(pw.encode(), str(pw_set).encode()):
                            ss["trainer_ok"] = True
                            st.rerun()
                        else:
                            st.error("That password is not correct.")
        if st.button("Back to client login", type="tertiary"):
            ss["mode"] = "client"
            st.rerun()


# ----------------------------------------------------------------------------
# Trainer: workout builder (browse by category, tick or ADD exercises into a client's day)
# ----------------------------------------------------------------------------
def find_or_create_day(t, title, weekday):
    ph, _, _ = phase_for(t)
    if ph is None:
        ph = new_phase()
        t["program"]["phases"].append(ph)
    for d in ph["days"]:
        if d["title"].strip().lower() == title.strip().lower():
            return d
    d = new_day(title, [], weekday)
    ph["days"].append(d)
    return d


def add_to_day(day, lib_ids, libmap, sets, reps):
    added = skipped = 0
    for i in lib_ids:
        l = libmap.get(i)
        if not l:
            continue
        if any(e.get("lib_id") == i for e in day["exercises"]):
            skipped += 1
            continue
        day["exercises"].append(ex_from_lib(l, sets or None, reps or None))
        added += 1
    return added, skipped


def builder_draft(cid):
    drafts = ss.setdefault("builder_drafts", {})
    if cid not in drafts:
        c = B.get(cid)
        if not c:
            return None
        drafts[cid] = copy.deepcopy(c)
    program = drafts[cid]["program"]
    phases = program.setdefault("phases", [])
    for p in phases:
        p["name"] = "General" if "general" in p.get("name", "").lower() else "Split program"
    for name in ("General", "Split program"):
        if not any(p["name"] == name for p in phases):
            phases.append(new_phase(name, 0, []))
    return drafts[cid]


def builder_apply():
    cid = ss.get("bld_client")
    draft = builder_draft(cid)
    current = B.get(cid)
    if not draft or not current:
        return
    program = copy.deepcopy(draft["program"])
    split = next((p for p in program["phases"] if p["name"] == "Split program" and p["days"]), None)
    selected = next(p for p in program["phases"] if p["id"] == ss.get("bld_phase"))
    program["active_phase"] = split["id"] if selected["name"] == "General" and split else selected["id"]
    phase = next(p for p in program["phases"] if p["id"] == ss.get("bld_phase"))
    program.pop("general_until", None)
    program.pop("resume_phase", None)
    program["date_workouts"] = copy.deepcopy(current["program"].get("date_workouts", {}))
    day = next((d for d in phase["days"] if d["id"] == ss.get("bld_day")), None)
    assigned_date = None
    if day:
        selected_date = ss.get("bld_date") or now().date()
        assigned_date = selected_date
        if phase["name"] == "General":
            program["date_workouts"][assigned_date.isoformat()] = [copy.deepcopy(day)]
        else:
            day["weekday"] = ss.get("bld_target_weekday", selected_date.weekday())
            program["date_workouts"].pop(assigned_date.isoformat(), None)
    current["program"] = program
    save_client(current)
    draft["program"] = copy.deepcopy(program)
    copied_names = []
    if day:
        for target_id in ss.get("bld_also", []):
            if target_id == cid:
                continue
            target = B.get(target_id)
            if not target:
                continue
            target_phase = next((p for p in target["program"]["phases"] if
                ("General" if "general" in p.get("name", "").lower() else "Split program") == phase["name"]), None)
            if target_phase is None:
                target_phase = new_phase(phase["name"], 0, [])
                target["program"]["phases"].append(target_phase)
            copied_day = copy.deepcopy(day)
            copied_day["id"] = uid()
            for exercise in copied_day["exercises"] + copied_day.get("bonus_exercises", []):
                exercise["id"] = uid()
            match = next((n for n, d in enumerate(target_phase["days"]) if
                d["title"].strip().lower() == day["title"].strip().lower()), None)
            if match is None:
                target_phase["days"].append(copied_day)
            else:
                target_phase["days"][match] = copied_day
            save_client(target)
            ss.get("builder_drafts", {}).pop(target_id, None)
            copied_names.append(target["name"])
    ss["_bld_msg"] = ("ok", f"Applied workout plan to {current['name']}. Removed exercises are removed from the client plan too.")
    if assigned_date and phase["name"] != "General":
        ss["_bld_msg"] = ("ok", f"Saved {day['title']} for every {WEEKDAYS[day['weekday']]}. It repeats each week automatically.")
    elif assigned_date:
        ss["_bld_msg"] = ("ok", f"Saved {day['title']} and assigned it to {current['name']} on {assigned_date:%A, %b %d}.")
    if copied_names:
        ss["_bld_msg"] = ("ok", ss["_bld_msg"][1] + f" Copied {day['title']} to {', '.join(copied_names)}.")


def builder_add(lib_ids):
    libmap = {l["id"]: l for l in get_lib()}
    c = builder_draft(ss.get("bld_client") or "")
    if not c or not lib_ids:
        return
    phase = next((p for p in c["program"]["phases"] if p["id"] == ss.get("bld_phase")), None)
    if phase is None:
        ss["_bld_msg"] = ("error", "Pick a phase first.")
        return
    sets, reps = (ss.get("bld_sets") or "").strip(), (ss.get("bld_reps") or "").strip()
    new_day_made = ss.get("bld_day") == "__new__"
    if new_day_made:
        name = (ss.get("bld_newname") or "").strip()
        if not name:
            ss["_bld_msg"] = ("error", "Type a name for the new day first, for example Chest day.")
            return
        day = new_day(name, [], ss.get("bld_newwd", -1))
        phase["days"].append(day)
    else:
        day = next((d for d in phase["days"] if d["id"] == ss.get("bld_day")), None)
        if day is None:
            ss["_bld_msg"] = ("error", "Pick a day first.")
            return
    target_day = {"exercises": day.setdefault("bonus_exercises", [])} if ss.get("bld_bonus") else day
    added, skipped = add_to_day(target_day, lib_ids, libmap, sets, reps)
    names = [c["name"]]
    for i in lib_ids:
        ss[f"bsel_{i}"] = False
    if new_day_made:
        ss["bld_day"] = day["id"]
        ss["bld_newname"] = ""
    msg = f"Added {added} exercise(s) to {day['title']} for {', '.join(names)}."
    if skipped:
        msg += f" Skipped {skipped} that were already in the day."
    ss["_bld_msg"] = ("ok", msg)


def builder_cancel_new_day():
    c = builder_draft(ss.get("bld_client") or "")
    phase = next((p for p in c["program"]["phases"] if p["id"] == ss.get("bld_phase")), None) if c else None
    ss["bld_day"] = phase["days"][0]["id"] if phase and phase["days"] else "__new__"
    ss["bld_newname"] = ""
    ss["bld_newwd"] = -1
    for key in list(ss):
        if key.startswith("bsel_"):
            ss[key] = False



import streamlit.components.v2 as components_v2

saved_workout_dropdown = components_v2.component(
    "saved_workout_dropdown",
    html='<div class="picker"></div>',
    css="""
.picker {font-family:sans-serif;color:#f2f3f5;}
label {display:block;font-size:14px;margin-bottom:8px;}
details {background:#262730;border:1px solid #444650;border-radius:8px;}
summary {padding:10px 12px;cursor:pointer;list-style:none;}
summary::after {content:"▾";float:right;}
.menu {max-height:280px;overflow:auto;padding:4px;border-top:1px solid #444650;}
.row {display:flex;align-items:center;border-radius:5px;}
.row:hover {background:#353741;}
button {font:inherit;color:inherit;border:0;background:transparent;cursor:pointer;}
.choose {flex:1;text-align:left;padding:10px;}
.remove {font-size:20px;padding:6px 12px;color:#ff9090;}
button:focus-visible,summary:focus-visible {outline:2px solid #4a94f2;}
""",
    js="""
export default function({data,parentElement,setTriggerValue}) {
 const root=parentElement.querySelector('.picker'); root.replaceChildren();
 const label=document.createElement('label');label.textContent='Saved workout';
 const details=document.createElement('details'), summary=document.createElement('summary');
 summary.textContent=data.options.find(o=>o.id===data.selected)?.label || 'Choose workout';
 details.append(summary);
 const menu=document.createElement('div');menu.className='menu';
 for(const option of data.options){
  const row=document.createElement('div');row.className='row';
  const choose=document.createElement('button');choose.type='button';choose.className='choose';choose.textContent=option.label;
  choose.onclick=()=>{details.open=false;setTriggerValue('action',{kind:'select',id:option.id});};row.append(choose);
  if(option.id!=='__new__'){
   const remove=document.createElement('button');remove.type='button';remove.className='remove';remove.textContent='×';
   remove.title='Remove saved workout';remove.setAttribute('aria-label','Remove '+option.label);
   remove.onclick=e=>{e.stopPropagation();setTriggerValue('action',{kind:'remove',id:option.id});};row.append(remove);
  }menu.append(row);
 }
 details.append(menu);root.append(label,details);
 const close=e=>{if(!e.composedPath().includes(details))details.open=false;};
 const escape=e=>{if(e.key==='Escape')details.open=false;};
 document.addEventListener('click',close);root.addEventListener('keydown',escape);
 return ()=>{document.removeEventListener('click',close);root.removeEventListener('keydown',escape);};
}
""",
)

def builder_day_label(phase, day_id):
    if day_id == "__new__":
        return "＋ Create workout…"
    day = next(d for d in phase["days"] if d["id"] == day_id)
    title = re.sub(r"^Day\\s+\\d+\\s*[·:–-]\\s*", "", day["title"], flags=re.I)
    return f"{title} · {len(day['exercises'])} exercises"


def builder_delete_saved_workout(day_id):
    if not ss.get("trainer_ok"):
        return
    cid = ss.get("bld_client")
    current = B.get(cid)
    draft = builder_draft(cid)
    if not current or not draft:
        return
    phase_id = ss.get("bld_phase")
    title = None
    for row in (current, draft):
        for phase in row["program"]["phases"]:
            if phase["id"] == phase_id:
                day = next((d for d in phase["days"] if d["id"] == day_id), None)
                if day:
                    title = day["title"]
                phase["days"] = [d for d in phase["days"] if d["id"] != day_id]
    save_client(current)
    if ss.get("bld_day") == day_id:
        ss.pop("bld_day", None)
    ss["_bld_msg"] = ("ok", f"Removed saved workout: {title or 'workout'}. Date-specific assignments remain unchanged.")


def builder_reset_draft():
    ss.get("builder_drafts", {}).pop(ss.get("bld_client"), None)
    ss.pop("bld_day", None)
    ss["bld_newname"] = ""
    for key in list(ss):
        if key.startswith("bsel_"):
            ss[key] = False
    ss["_bld_msg"] = ("ok", "Draft changes cancelled. Saved workouts remain unchanged.")


def builder_phase_changed():
    ss.pop("bld_day", None)
    ss["bld_cat"] = "All"
    ss["bld_q"] = ""


def builder_weekday_changed():
    chosen = ss.get("bld_date") or now().date()
    ss["bld_date"] = chosen - dt.timedelta(days=chosen.weekday()) + dt.timedelta(days=ss["bld_target_weekday"])


def builder_date_changed():
    ss["bld_target_weekday"] = ss["bld_date"].weekday()


def builder_remove(day_id, ex_id):
    c = builder_draft(ss.get("bld_client") or "")
    if not c:
        return
    for p in c["program"]["phases"]:
        for d in p["days"]:
            if d["id"] == day_id:
                d["exercises"] = [e for e in d["exercises"] if e["id"] != ex_id]
                d["bonus_exercises"] = [e for e in d.get("bonus_exercises", []) if e["id"] != ex_id]


def lib_set_link(lid, key):
    lib = get_lib()
    for l in lib:
        if l["id"] == lid:
            l["video"] = normalize_link(ss.get(key, ""))
    save_lib(lib)


def page_builder(clients):
    hero("Workout builder", "Pick exercises and add them to a client's day.", "Choose a category, tick the exercises you want, and add them to a client's day in one click. Or press ADD on a single exercise.")
    if ss.get("_bld_msg"):
        kind, msg = ss.pop("_bld_msg")
        (st.success if kind == "ok" else st.error)(msg)
    if not clients:
        st.info("Add your clients first (Overview, then Set up my 10 clients), then come back.")
        return
    lib = get_lib(create=True)
    ids = [c["id"] for c in clients]
    if ss.get("bld_client") not in ids:
        ss["bld_client"] = ids[0]
    a, b, c3 = st.columns([1.1, 1.2, 1.5])
    cid = a.selectbox("Client", ids, key="bld_client", format_func=lambda i: next(x["name"] for x in clients if x["id"] == i))
    client = builder_draft(cid)
    phases = client["program"]["phases"]
    pids = [p["id"] for p in phases]
    cur, _, _ = phase_for(client)
    if ss.get("bld_phase") not in pids:
        ss["bld_phase"] = (cur or phases[0])["id"]
    pid = b.selectbox("Phase", pids, key="bld_phase", on_change=builder_phase_changed, format_func=lambda i: next(p["name"] for p in phases if p["id"] == i))
    phase = next(p for p in phases if p["id"] == pid)
    dopts = [d["id"] for d in phase["days"]] + ["__new__"]
    if ss.get("bld_day") not in dopts:
        ss["bld_day"] = dopts[0]
    dlabel = lambda i: builder_day_label(phase, i)
    with c3:
        result = saved_workout_dropdown(
            key=f"saved_picker_{cid}_{pid}",
            data={"selected": ss["bld_day"], "options": [{"id": i, "label": dlabel(i)} for i in dopts]},
            on_action_change=lambda: None,
        )
    action = result.action
    if action and action.get("id") in dopts:
        if action.get("kind") == "remove" and action["id"] != "__new__":
            builder_delete_saved_workout(action["id"])
        elif action.get("kind") == "select":
            ss["bld_day"] = action["id"]
        st.rerun()
    did = ss["bld_day"]
    if did == "__new__":
        n1, n2 = st.columns([2, 1])
        n1.text_input("New day name", key="bld_newname", placeholder="Chest day")
        n2.selectbox("Day of week", [-1] + list(range(7)), key="bld_newwd", format_func=lambda x: "Any day" if x == -1 else WEEKDAYS[x])
        st.button("Cancel new day", on_click=builder_cancel_new_day)
    st.button("Cancel workout changes", on_click=builder_reset_draft)
    st.caption("General replaces only the selected date. Your regular split workouts remain saved.")
    st.caption("Add and remove exercises in your draft, then press Apply to update the client page.")
    ss.setdefault("bld_date", now().date())
    context = (cid, pid, did)
    if ss.get("_weekday_context") != context:
        selected_day = next((d for d in phase["days"] if d["id"] == did), None)
        if phase["name"] != "General" and selected_day and selected_day.get("weekday", -1) >= 0:
            chosen = ss["bld_date"]
            ss["bld_date"] = chosen - dt.timedelta(days=chosen.weekday()) + dt.timedelta(days=selected_day["weekday"])
        ss["_weekday_context"] = context
    ss["bld_target_weekday"] = ss["bld_date"].weekday()
    st.selectbox("Day", list(range(7)), key="bld_target_weekday", format_func=lambda i: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][i], on_change=builder_weekday_changed)
    if phase["name"] == "General":
        st.caption(f"General replaces only {ss['bld_date']:%A, %b %d}. To choose another week, open the optional date controls.")
    else:
        st.caption("Apply saves this workout for the selected weekday. The split schedule repeats every week automatically.")
    st.button("Apply workout to client", type="primary", on_click=builder_apply, disabled=did == "__new__")
    with st.expander("Optional: remove or replace a workout for one date", expanded=False):
        st.date_input("Workout date", key="bld_date", on_change=builder_date_changed)
        st.caption("These controls change only this date. The regular weekly split schedule continues.")
        st.caption("Select General or Split program and a workout above. Replace assigns it only to this date; Remove leaves this date without a workout.")
        x, y, z = st.columns(3)
        x.button("Replace this date with selected workout", on_click=builder_date_action, args=("replace",), disabled=did == "__new__")
        y.button("Remove workout for this date", on_click=builder_date_action, args=("remove",))
        z.button("Restore regular workout for this date", on_click=builder_date_action, args=("restore",))
        assigned = workouts_for_date(client, ss["bld_date"])
        st.caption("Assigned: " + (", ".join(d["title"] for d in assigned) if assigned else "No workout"))

    others = [x for x in clients if x["id"] != cid]
    oids = [x["id"] for x in others]
    ss["bld_also"] = [i for i in ss.get("bld_also", []) if i in oids]
    o1, o2, o3 = st.columns([2, 1, 1])
    o1.multiselect("Also copy this day to clients", oids, key="bld_also",
        format_func=lambda i: next(x["name"] for x in others if x["id"] == i))
    o1.caption("Apply also copies the selected day to these clients in the same phase. A day with the same name is replaced; their other days and active phase stay as they are.")
    o2.text_input("Sets for added exercises", key="bld_sets", placeholder="library default")
    o3.text_input("Reps for added exercises", key="bld_reps", placeholder="library default")
    st.checkbox("Add selected exercises as bonus workout", key="bld_bonus")
    if did != "__new__":
        day = next(d for d in phase["days"] if d["id"] == did)
        for e in day.get("bonus_exercises", []):
            bx, by = st.columns([6, 1])
            bx.write(f"Bonus: {e['name']} · {e['sets']}×{e['reps']}")
            by.button("✕", key=f"bonus_remove_{e['id']}", on_click=builder_remove, args=(day["id"], e["id"]))
        with st.expander(f"In this day now ({len(day['exercises'])})", expanded=bool(day["exercises"])):
            if not day["exercises"]:
                st.caption("Nothing here yet.")
            for n, e in enumerate(day["exercises"], 1):
                x, y = st.columns([6, 1])
                x.markdown(f"{n}. {e['name']} · {e['sets']}×{e['reps']}")
                y.button("✕", key=f"brm_{e['id']}", on_click=builder_remove, args=(day["id"], e["id"]))

    cats = [g for g in BUILDER_CATS if g == "All" or any(in_cat(l, g) for l in lib)]
    cat = st.pills("Category", cats, default=None if "bld_cat" in ss else "All", key="bld_cat", format_func=lambda g: f"{glabel(g)} ({sum(1 for l in lib if in_cat(l, g))})") or "All"
    q = st.text_input("Search", key="bld_q", placeholder="Search exercises…")
    items = [l for l in lib if in_cat(l, cat) and (not q or q.lower() in l["name"].lower())]
    sel = [l["id"] for l in items if ss.get(f"bsel_{l['id']}")]
    st.button(f"Add selected ({len(sel)}) to the day", key="bld_batch_top", type="primary", disabled=not sel, on_click=builder_add, args=(sel,))
    if not items:
        st.caption("No exercises in this category yet. Add some in the Exercise library.")
    for l in items:
        with st.container(border=True):
            c1, c2, c3_, c4, c5 = st.columns([0.5, 3.4, 1.2, 0.8, 1], vertical_alignment="center")
            c1.checkbox("Select", key=f"bsel_{l['id']}", label_visibility="collapsed")
            extra = ", ".join(glabel(t) for t in [l["group"]] + list(l.get("tags") or []) if t != cat)
            c2.markdown(f"**{l['name']}**  \n<span class='th-note'>{l['sets']}×{l['reps']} · {l.get('rest') or '—'} rest · {esc(extra)}</span>", unsafe_allow_html=True)
            link = normalize_link(l.get("video") or "")
            if link:
                c3_.link_button("▶ Watch", link, width="stretch")
            elif l.get("media"):
                c3_.caption("🎬 animation")
            else:
                c3_.link_button("🔎 Find", yt_search(l["name"]), width="stretch")
            with c4.popover("🔗", help="Paste or change the YouTube link"):
                lk = f"blk_{l['id']}"
                st.text_input("YouTube link", value=l.get("video", ""), key=lk)
                st.button("Save link", key=f"bls_{l['id']}", on_click=lib_set_link, args=(l["id"], lk))
            c5.button("ADD", key=f"badd_{l['id']}", type="primary", on_click=builder_add, args=([l["id"]],), width="stretch")
    if len(items) > 8:
        st.button(f"Add selected ({len(sel)}) to the day", key="bld_batch_bot", type="primary", disabled=not sel, on_click=builder_add, args=(sel,))


def trainer_app():
    try:
        clients = load_all(B.kind)
    except Exception as exc:
        st.error(f"Could not reach the database: {exc}")
        st.stop()
    ids = [c["id"] for c in clients]
    if ss.pop("_reset_sel", False):
        ss["sel_widget"] = ids
    if "_add_sel" in ss:
        ss["sel_widget"] = list(ss.get("sel_widget", [])) + [ss.pop("_add_sel")]
    ss.setdefault("sel_widget", ids)
    ss["sel_widget"] = [i for i in ss["sel_widget"] if i in ids]
    with st.sidebar:
        st.markdown("### Training Hub")
        st.caption("Coaching dashboard")
        st.divider()
        page = st.radio("Workspace", ["Overview", "Manage clients", "Workout builder", "Exercise library"], key="page")
        sel, rng = ids, None
        if page == "Overview":
            sel = st.multiselect("Clients", ids, key="sel_widget", format_func=lambda i: next(c["name"] for c in clients if c["id"] == i))
            rng = st.date_input("Reporting period", value=(now().date() - dt.timedelta(days=89), now().date()), key="period")
        st.divider()
        if st.button("Lock trainer session", width="stretch"):
            ss["trainer_ok"] = False
            ss["mode"] = "client"
            st.rerun()
        st.caption(("Database: Supabase" if B.kind == "supabase" else "Local test mode (data resets on restart)") + f" · {now():%b %d, %Y}")
    if page == "Overview":
        start, end = (rng[0], rng[1]) if isinstance(rng, (list, tuple)) and len(rng) == 2 else (now().date() - dt.timedelta(days=89), now().date())
        page_overview(clients, sel, start, end)
    elif page == "Manage clients":
        page_manage(clients)
    elif page == "Workout builder":
        page_builder(clients)
    else:
        page_library()


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------
if ss["trainer_ok"]:
    trainer_app()
elif ss["mode"] == "trainer":
    trainer_login()
else:
    client_flow()

