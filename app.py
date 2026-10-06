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
    week = max(0, (on - dobj(c["program"]["start"])).days // 7)
    acc = 0
    for ph in phases:
        w = int(ph.get("weeks") or 0)
        if w == 0 or week < acc + w:
            return ph, week - acc + 1, week + 1
        acc += w
    return phases[-1], week - acc + 1, week + 1


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
        return [new_phase("Week 1 · General", 1, [general]), new_phase("Split programme", 0, days)]

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
    return any(e["d"] == d and e["k"] == "ex" and e["ref"] in ids for e in c["events"])


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
        names = {d["id"]: d["name"] for d in directory}
        with st.container(border=True):
            cid = st.selectbox("Your name", list(names), index=None, placeholder="Select your name…", format_func=lambda i: names[i])
            pin = st.text_input("PIN", type="password", max_chars=4, placeholder="4-digit PIN")
            if ss.get("tries", 0) >= 5:
                st.error("Too many wrong PINs. Ask your trainer to reset it.")
            elif st.button("Log in", type="primary", width="stretch", disabled=cid is None):
                c = B.get(cid)
                if c and pin_ok(c, pin):
                    ss["client_id"], ss["tries"] = cid, 0
                    st.rerun()
                else:
                    ss["tries"] = ss.get("tries", 0) + 1
                    st.error("That PIN is not correct.")
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


def start_workout(day_id):
    ss["gw"] = {"day": day_id, "i": 0, "sets": {}, "w": {}}


def tab_home(c, lib_map):
    t = now()
    first = c["name"].split()[0]
    st.markdown(f'<div class="th-head"><div class="t">Training Hub</div><div class="d">{t:%A, %b} {t.day}</div><div class="g">Hi {esc(first)}</div></div>', unsafe_allow_html=True)
    phase, wk, overall = phase_for(c)
    tasks = []
    if phase:
        for d in phase["days"]:
            if d["weekday"] in (t.weekday(), -1) and d["exercises"] and not day_done(c, today(), d):
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


def workout_card(c, d, lib_map, sel_date, editable):
    exs = d["exercises"]
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
                st.checkbox("Done today", value=done, key=key, on_change=toggle_event, args=(c["id"], "ex", e["id"], e["name"], key))
    if editable and exs:
        st.button("Start workout", key=f"sw_{d['id']}", type="primary", width="stretch", on_click=start_workout, args=(d["id"],))


def tab_training(c, lib_map):
    if ss.get("gw"):
        return guided_workout(c, lib_map)
    st.markdown('<div class="th-title">Training</div>', unsafe_allow_html=True)
    phase, wk, overall = phase_for(c)
    if not phase or not phase["days"]:
        st.markdown('<div class="th-card th-empty">Your trainer has not added a workout plan yet.</div>', unsafe_allow_html=True)
        return
    st.caption(f"{phase['name']} · week {wk if phase.get('weeks') else overall}")
    td = now().date()
    monday = td - dt.timedelta(days=td.weekday())
    dates = [monday + dt.timedelta(days=i) for i in range(7)]

    def lab(i):
        done = any(day_done(c, dates[i].isoformat(), dy) for dy in phase["days"])
        return f"{WEEKDAYS[i]} {dates[i].day}{' ✓' if done else ''}"

    sel = st.segmented_control("Day", list(range(7)), format_func=lab, default=td.weekday(), key="train_day", label_visibility="collapsed")
    sel = td.weekday() if sel is None else sel
    sel_date = dates[sel].isoformat()
    editable = sel_date == td.isoformat()
    todays = [d for d in phase["days"] if d["weekday"] in (sel, -1)]
    if not todays:
        st.markdown('<div class="th-card th-empty">NO WORKOUTS ON THIS DAY</div>', unsafe_allow_html=True)
    for d in todays:
        workout_card(c, d, lib_map, sel_date, editable)

    week_ex = [e for d in phase["days"] if d["weekday"] != -1 for e in d["exercises"]]
    done_week = sum(1 for e in c["events"] if e["k"] == "ex" and e["d"] >= monday.isoformat() and e["d"] <= dates[6].isoformat())
    with st.container(border=True):
        h1, h2 = st.columns([2, 1])
        h1.markdown("**Training progress**")
        h2.markdown(pill(f"{done_week} / {len(week_ex)} this week"), unsafe_allow_html=True)
        a, b = st.columns([2, 1])
        nxt = next((d for d in phase["days"] if d["weekday"] in (td.weekday(), -1) and not day_done(c, today(), d)), None)
        a.markdown(f"**Next session**  \n{nxt['title'] if nxt else 'All done. You are all caught up.'}")
        b.markdown(f"**{streak(c)}**  \nday streak")


def guided_workout(c, lib_map):
    gw = ss["gw"]
    phase, _, _ = phase_for(c)
    day = next((d for d in (phase["days"] if phase else []) if d["id"] == gw["day"]), None)
    if not day or not day["exercises"]:
        ss["gw"] = None
        st.rerun()
    exs, i = day["exercises"], min(gw["i"], len(day["exercises"]) - 1)
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

    def finish():
        cc = B.get(c["id"])
        n = 0
        for ex_ in exs:
            sets_done = len(ss["gw"]["sets"].get(ex_["id"], []))
            if sets_done:
                event_set(cc, today(), "ex", ex_["id"], True, ex_["name"], sets=sets_done, w=ss["gw"]["w"].get(ex_["id"], ""))
                n += 1
        save_client(cc)
        ss["gw"] = None
        ss["_toast"] = f"Workout saved. {n} exercises logged."

    a, b, d_ = st.columns(3)
    a.button("Back", on_click=move, args=(-1,), disabled=i == 0, width="stretch")
    if i < len(exs) - 1:
        b.button("Next", on_click=move, args=(1,), type="primary", width="stretch")
    else:
        b.button("Finish", on_click=finish, type="primary", width="stretch")
    d_.button("Exit", on_click=lambda: ss.__setitem__("gw", None), width="stretch")


def tab_habit(c):
    st.markdown('<div class="th-title">Habit</div>', unsafe_allow_html=True)
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


def tab_nutrition(c):
    st.markdown('<div class="th-title">Nutrition</div>', unsafe_allow_html=True)
    mode = st.segmented_control("View", ["Log", "Plan"], default="Log", key="nut_mode", label_visibility="collapsed") or "Log"
    mac = c["diet"]["macros"]
    if mode == "Plan":
        st.markdown(f'<div class="th-card"><b>Daily targets</b><div class="th-macros" style="margin-top:12px"><div><b>{mac["kcal"]}</b><span>kcal</span></div><div><b>{mac["p"]} g</b><span>Protein</span></div><div><b>{mac["c"]} g</b><span>Carbs</span></div></div><div class="th-note" style="margin-top:10px">Fat {mac["f"]} g · Diet: {esc(c["profile"].get("diet") or "not set")}</div></div>', unsafe_allow_html=True)
        meals = c["diet"]["meals"]
        if not meals:
            st.markdown('<div class="th-card th-empty">Your trainer has not added a meal plan yet.</div>', unsafe_allow_html=True)
        for m in meals:
            with st.container(border=True):
                key = f"meal_{today()}_{m['id']}"
                st.checkbox(f"{fmt_time(m['time'])} · {m['text']}", value=is_done(c, today(), "meal", m["id"]), key=key,
                            on_change=toggle_event, args=(c["id"], "meal", m["id"], m["text"], key))
                with st.expander("Reminder"):
                    calendar_buttons(f"ics_m_{m['id']}", f"Meal: {m['text']}", f"Daily meal reminder from {c.get('trainer') or 'your trainer'}", next_at(m["time"]), 20, True)
        return
    d = st.date_input("Date", value=now().date(), max_value=now().date(), key="nut_date").isoformat()
    t = totals_for(c, d)
    pc = lambda a, b: round(a / b * 100) if b else 0
    st.markdown(
        f'<div class="th-card th-stat">{ring_html(pc(t["kcal"], mac["kcal"]), f"{t["kcal"]:.0f}", "cal")}'
        f'<div class="th-macros"><div><b>{pc(t["c"], mac["c"])}%</b><span>{t["c"]:.0f} g Carbs</span></div><div><b>{pc(t["f"], mac["f"])}%</b><span>{t["f"]:.0f} g Fat</span></div>'
        f'<div><b>{pc(t["p"], mac["p"])}%</b><span>{t["p"]:.0f} g Protein</span></div></div></div>', unsafe_allow_html=True)
    for slot in MEAL_SLOTS:
        items = [x for x in c["food_log"] if x["d"] == d and x["meal"] == slot]
        with st.expander(f"{slot} · {sum(fnum(x.get('kcal')) for x in items):.0f} kcal"):
            for x in items:
                a, b = st.columns([5, 1])
                a.markdown(f"**{x['name']}**  \n{fnum(x.get('kcal')):.0f} kcal · P {fnum(x.get('p')):.0f} · C {fnum(x.get('c')):.0f} · F {fnum(x.get('f')):.0f}")
                if b.button("✕", key=f"fd_{x['id']}"):
                    cc = B.get(c["id"])
                    cc["food_log"] = [y for y in cc["food_log"] if y["id"] != x["id"]]
                    save_client(cc)
                    st.rerun()
            with st.form(f"food_{slot}_{d}", clear_on_submit=True):
                nm = st.text_input("Food", key=f"fn_{slot}_{d}")
                a, b, c2, d2 = st.columns(4)
                kc = a.number_input("kcal", 0, 5000, 0, key=f"fk_{slot}_{d}")
                pr = b.number_input("Protein g", 0, 500, 0, key=f"fp_{slot}_{d}")
                cb = c2.number_input("Carbs g", 0, 800, 0, key=f"fc_{slot}_{d}")
                ft = d2.number_input("Fat g", 0, 500, 0, key=f"ff_{slot}_{d}")
                if st.form_submit_button("Add food", type="primary"):
                    if nm.strip():
                        cc = B.get(c["id"])
                        cc["food_log"].append({"id": uid(), "d": d, "meal": slot, "name": nm.strip(), "kcal": kc, "p": pr, "c": cb, "f": ft})
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
    rows = [(r_.date, r_.client, {"ex": "Exercise done", "meal": "Meal on plan", "habit": "Habit"}.get(r_.type, r_.type), r_["item"]) for _, r_ in cur_ev.iterrows()]
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
    q = st.text_input("Search", placeholder="Search exercises…")
    for grp in LIB_GROUPS:
        items = [l for l in lib if l["group"] == grp and (not q or q.lower() in l["name"].lower())]
        if not items:
            continue
        st.subheader(glabel(grp))
        for l in items:
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


def builder_add(lib_ids):
    libmap = {l["id"]: l for l in get_lib()}
    c = B.get(ss.get("bld_client") or "")
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
    added, skipped = add_to_day(day, lib_ids, libmap, sets, reps)
    save_client(c)
    names = [c["name"]]
    for tid in ss.get("bld_also") or []:
        t = B.get(tid)
        if t:
            add_to_day(find_or_create_day(t, day["title"], day["weekday"]), lib_ids, libmap, sets, reps)
            save_client(t)
            names.append(t["name"])
    for i in lib_ids:
        ss[f"bsel_{i}"] = False
    if new_day_made:
        ss["bld_day"] = day["id"]
        ss["bld_newname"] = ""
    msg = f"Added {added} exercise(s) to {day['title']} for {', '.join(names)}."
    if skipped:
        msg += f" Skipped {skipped} that were already in the day."
    ss["_bld_msg"] = ("ok", msg)


def builder_remove(day_id, ex_id):
    c = B.get(ss.get("bld_client") or "")
    if not c:
        return
    for p in c["program"]["phases"]:
        for d in p["days"]:
            if d["id"] == day_id:
                d["exercises"] = [e for e in d["exercises"] if e["id"] != ex_id]
    save_client(c)


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
    client = next(x for x in clients if x["id"] == cid)
    phases = client["program"]["phases"]
    pids = [p["id"] for p in phases]
    cur, _, _ = phase_for(client)
    if ss.get("bld_phase") not in pids:
        ss["bld_phase"] = (cur or phases[0])["id"]
    pid = b.selectbox("Phase", pids, key="bld_phase", format_func=lambda i: next(p["name"] for p in phases if p["id"] == i))
    phase = next(p for p in phases if p["id"] == pid)
    dopts = [d["id"] for d in phase["days"]] + ["__new__"]
    if ss.get("bld_day") not in dopts:
        ss["bld_day"] = dopts[0]
    dlabel = lambda i: "＋ New day…" if i == "__new__" else (lambda d: f"{d['title']} · {len(d['exercises'])} exercises")(next(d for d in phase["days"] if d["id"] == i))
    did = c3.selectbox("Day", dopts, key="bld_day", format_func=dlabel)
    if did == "__new__":
        n1, n2 = st.columns([2, 1])
        n1.text_input("New day name", key="bld_newname", placeholder="Chest day")
        n2.selectbox("Day of week", [-1] + list(range(7)), key="bld_newwd", format_func=lambda x: "Any day" if x == -1 else WEEKDAYS[x])
    others = [x for x in clients if x["id"] != cid]
    oids = [x["id"] for x in others]
    ss["bld_also"] = [i for i in ss.get("bld_also", []) if i in oids]
    o1, o2, o3 = st.columns([2, 1, 1])
    o1.multiselect("Also add to these clients (same day name)", oids, key="bld_also", format_func=lambda i: next(x["name"] for x in others if x["id"] == i))
    o2.text_input("Sets for added exercises", key="bld_sets", placeholder="library default")
    o3.text_input("Reps for added exercises", key="bld_reps", placeholder="library default")
    if did != "__new__":
        day = next(d for d in phase["days"] if d["id"] == did)
        with st.expander(f"In this day now ({len(day['exercises'])})", expanded=bool(day["exercises"])):
            if not day["exercises"]:
                st.caption("Nothing here yet.")
            for n, e in enumerate(day["exercises"], 1):
                x, y = st.columns([6, 1])
                x.markdown(f"{n}. {e['name']} · {e['sets']}×{e['reps']}")
                y.button("✕", key=f"brm_{e['id']}", on_click=builder_remove, args=(day["id"], e["id"]))

    cats = [g for g in BUILDER_CATS if g == "All" or any(in_cat(l, g) for l in lib)]
    cat = st.pills("Category", cats, default="All", key="bld_cat", format_func=lambda g: f"{glabel(g)} ({sum(1 for l in lib if in_cat(l, g))})") or "All"
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
