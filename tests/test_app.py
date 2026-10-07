"""Smoke tests for Training Hub. Run from the project folder with:  pytest -q

They drive the real app through Streamlit's AppTest harness against a temporary local data folder.
They do not touch Supabase and cannot test file uploads or how the pages look in a browser.
"""
import json
import sys
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")
sys.path.insert(0, str(ROOT))


def test_date_override_replace_remove_restore_and_trainer_guard():
    import ast
    import copy
    import datetime as dt
    source = ast.parse(Path(APP).read_text())
    names = {"phase_for", "workouts_for_date", "builder_date_action"}
    module = ast.Module(body=[n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    general = {"id": "g", "title": "Full body", "weekday": -1, "exercises": [{"id": "ge"}]}
    chest = {"id": "ch", "title": "Chest", "weekday": 0, "exercises": [{"id": "ce"}]}
    client = {"id": "c_a", "name": "Anton", "program": {"start": "2026-10-01", "phases": [
        {"id": "gp", "name": "General", "days": [general]},
        {"id": "sp", "name": "Split program", "days": [chest]}]}}
    draft = copy.deepcopy(client)
    state = {"trainer_ok": True, "bld_client": "c_a", "bld_phase": "gp", "bld_day": "g", "bld_date": dt.date(2026, 10, 12)}
    backend = type("Backend", (), {"get": lambda self, cid: client})()
    ns = {"copy": copy, "dobj": dt.date.fromisoformat, "now": lambda: dt.datetime(2026, 10, 12),
          "ss": state, "B": backend, "builder_draft": lambda cid: draft, "uid": lambda: "new",
          "save_client": lambda c: None}
    exec(compile(module, APP, "exec"), ns)
    resolve, action = ns["workouts_for_date"], ns["builder_date_action"]
    assert resolve(client, "2026-10-12") == [chest]
    action("replace")
    assert resolve(client, "2026-10-12")[0]["title"] == "Full body"
    assert resolve(client, "2026-10-19") == [chest]
    assert client["program"]["phases"][0]["days"][0] == general
    action("remove")
    assert resolve(client, "2026-10-12") == []
    action("restore")
    assert resolve(client, "2026-10-12") == [chest]
    state["trainer_ok"] = False
    action("remove")
    assert resolve(client, "2026-10-12") == [chest]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    st.cache_resource.clear()
    st.cache_data.clear()
    return tmp_path


def new_app():
    at = AppTest.from_file(APP, default_timeout=120)
    at.secrets["TRAINER_PASSWORD"] = "pw"
    return at


def store(env):
    return json.loads((env / "store.json").read_text())


def clients_by_name(env):
    return {v["name"]: v for k, v in store(env).items() if k.startswith("c_")}


def trainer_seeded(env):
    at = new_app()
    at.run()
    [b for b in at.button if b.label == "I am the trainer"][0].click().run()
    at.text_input[0].set_value("pw")
    at.button[0].click().run()
    [b for b in at.button if b.label == "Set up my 10 clients"][0].click().run()
    assert not at.exception
    return at


def test_builder_apply_replaces_removed_monday(env):
    import datetime as dt
    at = trainer_seeded(env)
    at.radio(key="page").set_value("Workout builder").run()
    anton = clients_by_name(env)["Anton"]
    at.selectbox(key="bld_client").set_value(anton["id"]).run()
    split = next(p for p in anton["program"]["phases"] if p["name"] == "Split program")
    at.selectbox(key="bld_phase").set_value(split["id"]).run()
    at.selectbox(key="bld_day").set_value(split["days"][0]["id"]).run()
    at.date_input(key="bld_date").set_value(dt.date(2026, 10, 5)).run()
    next(b for b in at.button if b.label == "Remove workout for this date").click().run()
    assert clients_by_name(env)["Anton"]["program"]["date_workouts"]["2026-10-05"] == []
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    saved = clients_by_name(env)["Anton"]["program"]["date_workouts"]["2026-10-05"]
    assert saved[0]["title"] == split["days"][0]["title"]
    assert len(saved[0]["exercises"]) == 2
    assert not at.exception


def test_general_applies_only_to_chosen_date_and_cancel_is_available(env):
    import datetime as dt
    at = trainer_seeded(env)
    at.radio(key="page").set_value("Workout builder").run()
    anton = clients_by_name(env)["Anton"]
    at.selectbox(key="bld_client").set_value(anton["id"]).run()
    general = next(p for p in anton["program"]["phases"] if p["name"] == "General")
    split = next(p for p in anton["program"]["phases"] if p["name"] == "Split program")
    at.selectbox(key="bld_phase").set_value(general["id"]).run()
    assert any(b.label == "Cancel workout changes" for b in at.button)
    at.selectbox(key="bld_target_weekday").set_value(4).run()
    assert at.date_input(key="bld_date").value.weekday() == 4
    at.date_input(key="bld_date").set_value(dt.date(2026, 10, 15)).run()
    assert at.selectbox(key="bld_target_weekday").value == 3
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    program = clients_by_name(env)["Anton"]["program"]
    assert program["active_phase"] == split["id"]
    assert list(program["date_workouts"]) == ["2026-10-15"]
    assert program["date_workouts"]["2026-10-15"][0]["title"] == general["days"][0]["title"]
    assert not at.exception
    at.selectbox(key="bld_day").set_value("__new__").run()
    at.text_input(key="bld_newname").set_value("Unfinished")
    next(b for b in at.button if b.label == "Cancel new day").click().run()
    assert at.selectbox(key="bld_day").value != "__new__"
    assert not at.exception


def test_wrong_trainer_password_is_rejected(env):
    at = new_app()
    at.run()
    [b for b in at.button if b.label == "I am the trainer"][0].click().run()
    at.text_input[0].set_value("nope")
    at.button[0].click().run()
    assert at.session_state["trainer_ok"] is False
    assert any("not correct" in e.value for e in at.error)


def test_seed_creates_the_ten_clients_and_plans(env):
    trainer_seeded(env)
    by = clients_by_name(env)
    assert set(by) == {"Anton", "Dharan", "Rekha", "Divya", "Venky", "Sheethal", "Varshni", "Swetha", "Guhan", "Kevin"}
    anton = by["Anton"]["program"]["phases"]
    assert [p["name"] for p in anton] == ["General", "Split program"]
    assert len(anton[0]["days"][0]["exercises"]) == 6
    assert all(e["sets"] == "3" and e["reps"] == "15" for e in anton[0]["days"][0]["exercises"])
    assert [d["title"].split(" · ")[1] for d in anton[1]["days"]] == ["Chest", "Triceps", "Lat", "Biceps", "Shoulder & Legs"]
    assert [len(d["exercises"]) for d in by["Rekha"]["program"]["phases"][0]["days"]] == [6, 5, 6, 5]
    assert by["Venky"]["program"]["phases"][0]["days"] == []
    assert len(store(env)["lib"]["exercises"]) >= 60


def test_client_first_login_pin_change_and_onboarding(env):
    at = trainer_seeded(env)
    pins = dict(at.session_state["_pins"])
    anton_id = clients_by_name(env)["Anton"]["id"]
    [b for b in at.sidebar.button if b.label == "Lock trainer session"][0].click().run()
    at.selectbox[0].set_value(anton_id).run()
    at.text_input[0].set_value("0000")
    [b for b in at.button if b.label == "Log in"][0].click().run()
    assert any("not correct" in e.value for e in at.error)
    at.text_input[0].set_value(pins["Anton"])
    [b for b in at.button if b.label == "Log in"][0].click().run()
    assert any(b.label == "Save PIN" for b in at.button)
    at.text_input[0].set_value("4821")
    at.text_input[1].set_value("4821")
    [b for b in at.button if b.label == "Save PIN"][0].click().run()
    at.number_input[0].set_value(172.0)
    at.number_input[1].set_value(78.5)
    at.selectbox[0].select("Non-vegetarian")
    at.radio[0].set_value("Fat loss")
    at.radio[1].set_value("Men's physique")
    [b for b in at.button if b.label == "Continue to my plan"][0].click().run()
    a = clients_by_name(env)["Anton"]
    assert a["onboarded"] and not a["must_change_pin"]
    assert a["profile"]["goal"] == "Fat loss" and a["profile"]["height_cm"] == 172.0
    for tab in ["🏠", "🏋️", "🌿", "🍎", "👤"]:
        at.session_state["nav"] = tab
        at.run()
        assert not at.exception, tab


def test_builder_adds_selected_exercises_to_a_new_day(env):
    at = trainer_seeded(env)
    venky = clients_by_name(env)["Venky"]["id"]
    chest = [l for l in store(env)["lib"]["exercises"] if l["group"] == "Chest" or "Chest" in l.get("tags", [])]
    at.sidebar.radio(key="page").set_value("Workout builder").run()
    at.selectbox(key="bld_client").set_value(venky).run()
    at.session_state["bld_cat"] = "Chest"
    at.run()
    at.text_input(key="bld_newname").set_value("Chest day").run()
    for l in chest[:3]:
        at.checkbox(key=f"bsel_{l['id']}").check().run()
    [b for b in at.button if b.label.startswith("Add selected")][0].click().run()
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    days = clients_by_name(env)["Venky"]["program"]["phases"][0]["days"]
    assert [d["title"] for d in days] == ["Chest day"]
    assert [e["name"] for e in days[0]["exercises"]] == [l["name"] for l in chest[:3]]
    # adding the same exercise again is skipped
    at.button(key=f"badd_{chest[0]['id']}").click().run()
    assert len(clients_by_name(env)["Venky"]["program"]["phases"][0]["days"][0]["exercises"]) == 3


def test_copy_day_to_another_client(env):
    at = trainer_seeded(env)
    by = clients_by_name(env)
    anton, venky = by["Anton"], by["Venky"]["id"]
    day_id = anton["program"]["phases"][0]["days"][0]["id"]
    at.sidebar.radio(key="page").set_value("Manage clients").run()
    at.selectbox(key="manage_pick").set_value(anton["id"]).run()
    at.multiselect(key=f"cp_{day_id}").set_value([venky]).run()
    at.button(key=f"cpb_{day_id}").click().run()
    copied = clients_by_name(env)["Venky"]["program"]["phases"][0]["days"]
    assert len(copied) == 1 and len(copied[0]["exercises"]) == 6 and copied[0]["id"] != day_id


SAMPLE_PLAN = """Daily targets: 1800 kcal | Protein 120 g | Carbs 180 g | Fat 55 g
Breakfast (8:00 AM)
3 egg whites + 1 whole egg omelette
Lunch 1:00 PM
1 cup brown rice, 150 g grilled chicken
Dinner 8 pm
2 chapati, dal, vegetables
"""


def test_diet_text_parser():
    from dietpdf import parse_diet

    r = parse_diet(SAMPLE_PLAN)
    assert r["macros"] == {"kcal": 1800, "p": 120, "c": 180, "f": 55}
    assert [(m["time"], m["text"].split(":")[0]) for m in r["meals"]] == [("08:00", "Breakfast"), ("13:00", "Lunch"), ("20:00", "Dinner")]
    only_times = parse_diet("7:00 AM Oats with banana\n1:00 PM Chicken curry with rice")
    assert [m["time"] for m in only_times["meals"]] == ["07:00", "13:00"] and only_times["macros"] == {}


def test_builder_draft_apply_and_remove(env):
    at = trainer_seeded(env)
    at.sidebar.radio[0].set_value("Workout builder").run()
    cid = at.session_state["bld_client"]
    before = store(env)[cid]["program"]
    add = next(b for b in at.button if b.label == "ADD")
    add.click().run()
    assert not at.exception
    assert store(env)[cid]["program"] == before
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    assert not at.exception
    applied = store(env)[cid]["program"]
    assert applied["active_phase"] == at.session_state["bld_phase"]
    count = sum(len(d["exercises"]) for p in applied["phases"] for d in p["days"])
    next(b for b in at.button if b.label == "✕").click().run()
    assert sum(len(d["exercises"]) for p in store(env)[cid]["program"]["phases"] for d in p["days"]) == count
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    assert not at.exception
    assert sum(len(d["exercises"]) for p in store(env)[cid]["program"]["phases"] for d in p["days"]) == count - 1


def test_general_library_basket(env):
    at = trainer_seeded(env)
    at.sidebar.radio(key="page").set_value("Exercise library").run()
    next(b for b in at.button if b.label == "Select for General").click().run()
    assert len(at.session_state["general_basket"]) == 1
    next(b for b in at.button if b.label == "Select for General" and not b.disabled).click().run()
    assert len(at.session_state["general_basket"]) == 2
    next(b for b in at.button if b.label == "Send selection to General draft").click().run()
    assert not at.exception
    cid = at.session_state["bld_client"]
    draft = at.session_state["builder_drafts"][cid]
    general = next(p for p in draft["program"]["phases"] if p["name"] == "General")
    assert len(general["days"][0]["exercises"]) == 2


def test_general_switch_is_manual_and_keeps_split(env):
    at = trainer_seeded(env)
    cid = clients_by_name(env)["Dharan"]["id"]
    at.sidebar.radio(key="page").set_value("Workout builder").run()
    at.selectbox(key="bld_client").set_value(cid).run()
    phases = store(env)[cid]["program"]["phases"]
    general, split = phases
    at.selectbox(key="bld_phase").set_value(general["id"]).run()
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    program = store(env)[cid]["program"]
    assert program["active_phase"] == split["id"]
    assert program["date_workouts"][at.date_input(key="bld_date").value.isoformat()][0]["title"] == general["days"][0]["title"]
    assert "general_until" not in program
    assert program["phases"][1] == split
    assert not any("how many days" in x.label for x in at.selectbox)
    at.selectbox(key="bld_phase").set_value(split["id"]).run()
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    assert store(env)[cid]["program"]["active_phase"] == split["id"]
    assert not at.exception

