"""Read a diet-plan PDF and pull out daily targets (kcal, protein, carbs, fat) and meals with times.

This is rule-based, not magic: it works best on plans that list meals with a name or a time
(Breakfast, 8:00 AM, Lunch ...). The app always shows the result for review before saving.
No streamlit imports here, so it can be tested on its own.
"""
import io
import re

# (phrase, default time) - longer phrases first so "mid morning" wins over "morning"
MEAL_WORDS = [
    ("early morning", "06:30"), ("pre-workout", "17:30"), ("pre workout", "17:30"), ("post-workout", "19:00"), ("post workout", "19:00"),
    ("mid-morning", "10:30"), ("mid morning", "10:30"), ("midmorning", "10:30"), ("breakfast", "08:00"), ("brunch", "10:30"),
    ("lunch", "13:00"), ("evening snack", "16:30"), ("evening", "16:30"), ("snacks", "16:00"), ("snack", "16:00"),
    ("dinner", "20:00"), ("supper", "20:30"), ("before bed", "22:00"), ("bedtime", "22:00"), ("night", "21:30"),
]
SKIP_LINE = re.compile(r"^\s*(total|daily|target|goal|macros?|calories|kcal|protein|carb|fat|note|notes|water|page \d+)\b", re.I)
TIME_COLON = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", re.I)
TIME_AMPM = re.compile(r"\b(\d{1,2})(?:\.(\d{2}))?\s*(am|pm)\b", re.I)


def extract_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _to_24h(h, m, ap):
    h, m = int(h), int(m or 0)
    if ap:
        ap = ap.lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    return f"{h:02d}:{m:02d}"


def find_time(line):
    """First time of day in a line, as (HH:MM, span) or (None, None)."""
    for rx in (TIME_COLON, TIME_AMPM):
        m = rx.search(line)
        if m:
            g = m.groups()
            t = _to_24h(g[0], g[1], g[2])
            if t:
                return t, m.span()
    return None, None


def find_keyword(line):
    low = re.sub(r"^[\s\-•*·\d.)(]+", "", line.lower())
    for word, default in MEAL_WORDS:
        if low.startswith(word):
            return word, default
    return None, None


def parse_macros(text):
    t = text.lower()
    limits = {"kcal": (800, 6000), "p": (20, 400), "c": (20, 700), "f": (10, 250)}
    lead = r"(?:total|daily|target|goal|per day|day)[^\n]{0,30}?"
    pats = {
        "kcal": [lead + r"(\d{3,4})\s*(?:kcal|calories|cal)\b", r"(?:calories|calorie|kcal|energy)[^\d\n]{0,20}(\d{3,4})", r"(\d{3,4})\s*(?:kcal|calories|cal)\b"],
        "p": [lead + r"protein[^\d\n]{0,15}(\d{2,3})", r"protein[^\d\n]{0,20}(\d{2,3})", r"(\d{2,3})\s*g(?:rams?)?\s*(?:of\s*)?protein"],
        "c": [lead + r"carb\w*[^\d\n]{0,15}(\d{2,3})", r"carb\w*[^\d\n]{0,20}(\d{2,3})", r"(\d{2,3})\s*g(?:rams?)?\s*(?:of\s*)?carb"],
        "f": [lead + r"\bfats?\b[^\d\n]{0,15}(\d{2,3})", r"\bfats?\b[^\d\n]{0,20}(\d{2,3})", r"(\d{2,3})\s*g(?:rams?)?\s*(?:of\s*)?fats?\b"],
    }
    out = {}
    for key, plist in pats.items():
        lo, hi = limits[key]
        for i, p in enumerate(plist):
            vals = [int(v) for v in re.findall(p, t) if lo <= int(v) <= hi]
            if vals:
                # keyword-led patterns are the daily total; otherwise the largest value is the best guess
                out[key] = vals[0] if i == 0 else max(vals)
                break
    return out


def _clean(s):
    s = re.sub(r"^[\s\-•*·:–—,;|]+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—:;,|")
    return s


def parse_meals(text):
    meals, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        kw, default = find_keyword(line)
        tm, span = find_time(line)
        starts_meal = bool(kw) or (tm is not None and span[0] <= 12)
        if starts_meal and not SKIP_LINE.match(line):
            if cur:
                meals.append(cur)
            body = line
            if kw:
                body = re.sub(r"^[\s\-•*·\d.)(]*" + re.escape(kw), "", line, flags=re.I)
            if tm is not None:
                a, b = find_time(body)[1] or (None, None)
                if a is not None:
                    body = body[:a] + " " + body[b:]
                body = re.sub(r"\(\s*\)|\[\s*\]", " ", body)
            label = kw.title() if kw else ""
            cur = {"time": tm or default, "label": label, "parts": [_clean(body)] if _clean(body) else []}
        elif cur and not SKIP_LINE.match(line):
            cur["parts"].append(_clean(line))
    if cur:
        meals.append(cur)
    out = []
    for m in meals:
        body = ", ".join(p for p in m["parts"] if p)
        text_ = f"{m['label']}: {body}" if m["label"] and body else (m["label"] or body)
        text_ = text_[:300].strip()
        if text_:
            out.append({"time": m["time"], "text": text_})
    # give meals without any time a sensible spread across the day
    fallback = ["08:00", "10:30", "13:00", "16:00", "19:00", "21:30"]
    k = 0
    for m in out:
        if not m["time"]:
            m["time"] = fallback[min(k, len(fallback) - 1)]
            k += 1
    return sorted(out, key=lambda x: x["time"])


def parse_diet(text):
    return {"macros": parse_macros(text), "meals": parse_meals(text)}
