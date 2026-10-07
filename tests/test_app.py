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
    at.session_state["bld_day"] = split["days"][0]["id"]
    at.run()
    at.date_input(key="bld_date").set_value(dt.date(2026, 10, 5)).run()
    next(b for b in at.button if b.label == "Remove workout for this date").click().run()
    assert clients_by_name(env)["Anton"]["program"]["date_workouts"]["2026-10-05"] == []
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    program = clients_by_name(env)["Anton"]["program"]
    assert "2026-10-05" not in program["date_workouts"]
    saved = next(p for p in program["phases"] if p["id"] == split["id"])["days"]
    assert saved[0]["title"] == split["days"][0]["title"]
    assert len(saved[0]["exercises"]) == 2
    assert saved[0]["weekday"] == 0
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    again = clients_by_name(env)["Anton"]["program"]
    assert again == program
    import ast
    import datetime as dt
    tree = ast.parse(Path(APP).read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"phase_for", "workouts_for_date"}]
    ns = {"dobj": dt.date.fromisoformat, "now": lambda: dt.datetime(2026, 10, 5)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), APP, "exec"), ns)
    for date in ("2026-10-05", "2026-10-12", "2026-10-19"):
        assert ns["workouts_for_date"]({"program": program}, date)[0]["id"] == saved[0]["id"]
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
    at.session_state["bld_day"] = "__new__"
    at.run()
    at.text_input(key="bld_newname").set_value("Unfinished")
    next(b for b in at.button if b.label == "Cancel new day").click().run()
    assert at.session_state["bld_day"] != "__new__"
    assert not at.exception


def test_wrong_trainer_password_is_rejected(env):
    at = new_app()
    at.run()
    [b for b in at.button if b.label == "I am the trainer"][0].click().run()
    at.text_input[0].set_value("nope")
    at.button[0].click().run()
    assert at.session_state["trainer_ok"] is False
    assert any("not correct" in e.value for e in at.error)


def test_delete_saved_workout_removes_only_selected_template(env):
    at = trainer_seeded(env)
    at.radio(key="page").set_value("Workout builder").run()
    cid = at.session_state["bld_client"]
    before = store(env)[cid]["program"]
    phase = next(p for p in before["phases"] if p["id"] == at.session_state["bld_phase"])
    removed = phase["days"][0]["id"]
    retained = [d for d in phase["days"] if d["id"] != removed]
    at.session_state[f"saved_picker_{cid}_{phase['id']}"] = {"action": {"kind": "remove", "id": removed}}
    at.run()
    assert not at.exception
    after = store(env)[cid]["program"]
    assert next(p for p in after["phases"] if p["id"] == phase["id"])["days"] == retained
    assert all(d["id"] != removed for p in at.session_state["builder_drafts"][cid]["program"]["phases"] for d in p["days"])
    assert at.session_state["bld_day"] != removed


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
    assert not at.selectbox
    at.text_input(key="client_login_name").set_value("  aNtOn  ").run()
    next(t for t in at.text_input if t.label == "PIN").set_value("0000")
    [b for b in at.button if b.label == "Log in"][0].click().run()
    assert any("not correct" in e.value for e in at.error)
    next(t for t in at.text_input if t.label == "PIN").set_value(pins["Anton"])
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


def test_client_login_hides_roster_and_rejects_unknown_name(env):
    at = trainer_seeded(env)
    next(b for b in at.sidebar.button if b.label == "Lock trainer session").click().run()
    assert not at.selectbox
    visible = " ".join(x.value for x in at.markdown)
    assert "Anton" not in visible and "Dharan" not in visible
    at.text_input(key="client_login_name").set_value("Unknown person").run()
    next(t for t in at.text_input if t.label == "PIN").set_value("1234")
    next(b for b in at.button if b.label == "Log in").click().run()
    assert at.session_state["client_id"] is None
    assert at.session_state["tries"] == 1
    assert any(e.value == "That name or PIN is not correct." for e in at.error)


def test_nutrition_log_without_plan_and_planned_meal_alternative(env):
    at = trainer_seeded(env)
    rows = store(env)
    client = clients_by_name(env)["Anton"]
    client.update(onboarded=True, must_change_pin=False)
    client["diet"]["meals"] = []
    rows[client["id"]] = client
    (env / "store.json").write_text(json.dumps(rows))
    at.session_state["trainer_ok"] = False
    at.session_state["client_id"] = client["id"]
    at.session_state["mode"] = "client"
    at.session_state["nav"] = "🍎"
    at.run()
    assert not at.exception
    date = at.date_input(key="nut_date").value.isoformat()
    at.text_input(key=f"fn_Breakfast_{date}").set_value("Idli and sambar")
    at.button(key=f"FormSubmitter:food_Breakfast_{date}-Add food").click().run()
    saved = store(env)[client["id"]]
    assert saved["food_log"][0]["name"] == "Idli and sambar"
    assert saved["food_log"][0]["meal"] == "Breakfast"
    rows = store(env)
    rows[client["id"]]["diet"]["meals"] = [{"id": "test_meal", "time": "08:00", "text": "Oats and milk"}]
    (env / "store.json").write_text(json.dumps(rows))
    at.run()
    at.segmented_control(key="nut_mode").set_value("Plan").run()
    at.radio(key=f"meal_status_test_meal_{date}").set_value("Ate something else")
    at.text_area(key=f"meal_actual_test_meal_{date}").set_value("Eggs and toast")
    at.button(key=f"FormSubmitter:meal_response_test_meal_{date}-Save meal status").click().run()
    saved = store(env)[client["id"]]
    assert any(x.get("plan_ref") == "test_meal" and x["name"] == "Eggs and toast" for x in saved["food_log"])
    assert not any(e["k"] == "meal" and e["ref"] == "test_meal" for e in saved["events"])
    at.radio(key=f"meal_status_test_meal_{date}").set_value("Ate the planned meal")
    at.button(key=f"FormSubmitter:meal_response_test_meal_{date}-Save meal status").click().run()
    saved = store(env)[client["id"]]
    assert any(e["k"] == "meal" and e["ref"] == "test_meal" for e in saved["events"])
    assert not any(x.get("plan_ref") == "test_meal" for x in saved["food_log"])
    assert not at.exception


def test_activity_log_updates_same_day_without_assigned_habits(env):
    at = trainer_seeded(env)
    rows = store(env)
    client = clients_by_name(env)["Anton"]
    client.update(onboarded=True, must_change_pin=False, habits=[])
    rows[client["id"]] = client
    (env / "store.json").write_text(json.dumps(rows))
    at.session_state["trainer_ok"] = False
    at.session_state["mode"] = "client"
    at.session_state["client_id"] = client["id"]
    at.session_state["nav"] = "🌿"
    at.run()
    date = at.date_input(key="activity_date").value.isoformat()
    at.number_input(key=f"steps_{date}").set_value(7000)
    at.number_input(key=f"burned_{date}").set_value(350)
    next(b for b in at.button if b.label == "Save activity").click().run()
    assert not at.exception
    assert store(env)[client["id"]]["activity_log"] == [{"d": date, "steps": 7000, "burned_kcal": 350}]
    at.number_input(key=f"steps_{date}").set_value(8000)
    next(b for b in at.button if b.label == "Save activity").click().run()
    assert len(store(env)[client["id"]]["activity_log"]) == 1
    assert store(env)[client["id"]]["activity_log"][0]["steps"] == 8000
    assert not at.exception


def test_guided_workout_and_optional_bonus_completion(env):
    import datetime as dt
    at = trainer_seeded(env)
    client = clients_by_name(env)["Anton"]
    at.radio(key="page").set_value("Workout builder").run()
    at.selectbox(key="bld_client").set_value(client["id"]).run()
    split = next(p for p in client["program"]["phases"] if p["name"] == "Split program")
    at.selectbox(key="bld_phase").set_value(split["id"]).run()
    at.checkbox(key="bld_bonus").check().run()
    next(b for b in at.button if b.label == "ADD").click().run()
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    rows = store(env)
    client = rows[client["id"]]
    client.update(onboarded=True, must_change_pin=False)
    (env / "store.json").write_text(json.dumps(rows))
    at.session_state["trainer_ok"] = False
    at.session_state["mode"] = "client"
    at.session_state["client_id"] = client["id"]
    at.session_state["nav"] = "🏋️"
    at.run()
    at.segmented_control(key="train_day").set_value(0).run()
    date = (dt.date.today() - dt.timedelta(days=dt.date.today().weekday())).isoformat()
    next(b for b in at.button if b.label == "Start workout").click().run()
    next(b for b in at.button if b.label == "Mark exercise done and next").click().run()
    next(b for b in at.button if b.label == "Mark exercise done").click().run()
    next(b for b in at.button if b.label == "Complete workout").click().run()
    saved = store(env)[client["id"]]
    assert len([e for e in saved["events"] if e["d"] == date and e["k"] == "ex"]) == 2
    assert any(e["d"] == date and e["k"] == "workout" for e in saved["events"])
    assert not any(e["k"] == "bonus_workout" for e in saved["events"])
    next(b for b in at.button if b.label == "Start bonus workout").click().run()
    next(b for b in at.button if b.label == "Mark exercise done").click().run()
    next(b for b in at.button if b.label == "Complete bonus workout").click().run()
    saved = store(env)[client["id"]]
    assert any(e["d"] == date and e["k"] == "bonus_workout" for e in saved["events"])
    assert any(e.get("bonus") for e in saved["events"])
    assert not at.exception


def test_general_category_swap_changes_only_assigned_date(env):
    import copy
    at = trainer_seeded(env)
    client = clients_by_name(env)["Anton"]
    at.radio(key="page").set_value("Workout builder").run()
    at.selectbox(key="bld_client").set_value(client["id"]).run()
    general = client["program"]["phases"][0]
    at.selectbox(key="bld_phase").set_value(general["id"]).run()
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    rows = store(env)
    client = rows[client["id"]]
    date = next(iter(client["program"]["date_workouts"]))
    original_phases = copy.deepcopy(client["program"]["phases"])
    original = copy.deepcopy(client["program"]["date_workouts"][date][0])
    client.update(onboarded=True, must_change_pin=False)
    (env / "store.json").write_text(json.dumps(rows))
    at.session_state["trainer_ok"] = False
    at.session_state["mode"] = "client"
    at.session_state["client_id"] = client["id"]
    at.session_state["nav"] = "🏋️"
    at.run()
    old = original["exercises"][0]
    import datetime as dt
    at.segmented_control(key="train_day").set_value(dt.date.fromisoformat(date).weekday()).run()
    at.button(key=f"swap_{date}_{old['id']}").click().run()
    assert any("Chest" in x.value for x in at.subheader)
    candidates = [e for e in rows["lib"]["exercises"] if e["group"] == "Chest" and e["id"] not in {x.get("lib_id") for x in original["exercises"]}]
    chosen = candidates[0]
    at.button(key=f"swap_choice_{chosen['id']}").click().run()
    saved = store(env)[client["id"]]
    swapped = saved["program"]["date_workouts"][date][0]["exercises"][0]
    assert swapped["lib_id"] == chosen["id"]
    assert swapped["sets"] == old["sets"] and swapped["reps"] == old["reps"]
    assert saved["program"]["phases"] == original_phases
    assert list(saved["program"]["date_workouts"]) == [date]
    assert not at.exception


def test_copy_general_to_thursday_friday_preserves_source_and_weekly_split(env):
    import datetime as dt
    import copy
    at = trainer_seeded(env)
    client = clients_by_name(env)["Anton"]
    at.radio(key="page").set_value("Workout builder").run()
    at.selectbox(key="bld_client").set_value(client["id"]).run()
    general = client["program"]["phases"][0]
    at.selectbox(key="bld_phase").set_value(general["id"]).run()
    at.date_input(key="bld_date").set_value(dt.date(2026, 10, 7)).run()
    next(b for b in at.button if b.label == "Apply workout to client").click().run()
    before = copy.deepcopy(store(env)[client["id"]]["program"])
    at.multiselect(key="bld_copy_days").set_value([3, 4]).run()
    next(b for b in at.button if b.label == "Copy workout to selected days").click().run()
    after = store(env)[client["id"]]["program"]
    assert after["phases"] == before["phases"]
    assert after["date_workouts"]["2026-10-07"] == before["date_workouts"]["2026-10-07"]
    for date in ("2026-10-08", "2026-10-09"):
        copied = after["date_workouts"][date]
        assert len(copied) == 1 and copied[0]["allow_swaps"]
        assert [e["name"] for e in copied[0]["exercises"]] == [e["name"] for e in general["days"][0]["exercises"]]
    assert after["date_workouts"]["2026-10-08"][0]["id"] != after["date_workouts"]["2026-10-09"][0]["id"]
    next(b for b in at.button if b.label == "Copy workout to selected days").click().run()
    assert len(store(env)[client["id"]]["program"]["date_workouts"]["2026-10-08"]) == 1
    assert not at.exception


def test_trainer_preview_skips_onboarding_without_changing_client(env):
    import copy
    at = trainer_seeded(env)
    client = clients_by_name(env)["Anton"]
    before = copy.deepcopy(store(env))
    at.radio(key="page").set_value("Manage clients").run()
    at.selectbox(key="manage_pick").set_value(client["id"]).run()
    at.button(key=f"preview_{client['id']}").click().run()
    assert not at.exception
    assert not any(b.label in ("Save PIN", "Continue to my plan") for b in at.button)
    for page in ("Training", "Habit", "Nutrition", "Profile"):
        at.radio(key="preview_nav").set_value(page).run()
        assert not at.exception
        if page == "Training":
            at.segmented_control(key="preview_training_day").set_value(0).run()
            assert any("Chest" in x.value for x in at.markdown)
            at.segmented_control(key="preview_training_day").set_value(1).run()
            assert any("Triceps" in x.value for x in at.markdown)
            assert not at.exception
    assert store(env) == before
    next(b for b in at.button if b.label == "Back to trainer").click().run()
    assert not at.exception
    assert "trainer_preview" not in at.session_state


def test_preview_removes_one_duplicate_workout_for_one_date(env):
    import copy
    at = trainer_seeded(env)
    rows = store(env)
    client = clients_by_name(env)["Dharan"]
    split = client["program"]["phases"][1]
    duplicate = copy.deepcopy(split["days"][0])
    duplicate["id"] = "extra_chest"
    for i, e in enumerate(duplicate["exercises"]):
        e["id"] = f"extra_ex_{i}"
    split["days"].append(duplicate)
    client["program"]["active_phase"] = split["id"]
    rows[client["id"]] = client
    (env / "store.json").write_text(json.dumps(rows))
    st.cache_data.clear()
    at.radio(key="page").set_value("Manage clients").run()
    at.selectbox(key="manage_pick").set_value(client["id"]).run()
    at.button(key=f"preview_{client['id']}").click().run()
    at.radio(key="preview_nav").set_value("Training").run()
    at.segmented_control(key="preview_training_day").set_value(0).run()
    import datetime as dt
    chosen = at.date_input(key="preview_week").value
    date = (chosen - dt.timedelta(days=chosen.weekday())).isoformat()
    at.button(key=f"preview_remove_{date}_extra_chest").click().run()
    saved = store(env)[client["id"]]["program"]
    assert len(saved["date_workouts"][date]) == 1
    assert saved["date_workouts"][date][0]["id"] == split["days"][0]["id"]
    assert saved["phases"][1] == split
    assert not at.exception


def test_split_class_swap_is_category_filtered_and_date_only(env):
    import datetime as dt
    import copy
    at = trainer_seeded(env)
    rows = store(env)
    client = clients_by_name(env)["Anton"]
    split = client["program"]["phases"][1]
    client["program"]["active_phase"] = split["id"]
    client.update(onboarded=True, must_change_pin=False)
    before = copy.deepcopy(client["program"]["phases"])
    rows[client["id"]] = client
    (env / "store.json").write_text(json.dumps(rows))
    at.session_state["trainer_ok"] = False
    at.session_state["mode"] = "client"
    at.session_state["client_id"] = client["id"]
    at.session_state["nav"] = "🏋️"
    at.run()
    at.segmented_control(key="train_day").set_value(0).run()
    date = (dt.date.today() - dt.timedelta(days=dt.date.today().weekday())).isoformat()
    old = split["days"][0]["exercises"][0]
    button = at.button(key=f"swap_{date}_{old['id']}")
    assert button.label == "Change class"
    button.click().run()
    assigned_button = at.button(key=f"swap_choice_{old['lib_id']}")
    assert assigned_button.disabled
    assert assigned_button.label == "Already in workout list"
    assert any(x.value == "Already in this workout list" for x in at.caption)
    used = {e.get("lib_id") for e in split["days"][0]["exercises"]}
    choice = next(e for e in rows["lib"]["exercises"] if e["group"] == "Chest" and e["id"] not in used)
    at.button(key=f"swap_choice_{choice['id']}").click().run()
    saved = store(env)[client["id"]]["program"]
    assert saved["phases"] == before
    assert saved["date_workouts"][date][0]["exercises"][0]["lib_id"] == choice["id"]
    assert not at.exception


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

