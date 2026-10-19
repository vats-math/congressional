"""Tests for the hand-collected local data loader (app/local_data.py)."""
import csv
import shutil
from pathlib import Path

import pytest

from app import db, local_data
from app.local_data import (LOCAL_DIR, fetch_programs, load_local, parse_clock, parse_environment,
                            parse_weekday)

LOC_HEADER = "location_id,name,address,city,region,country,lat,lng\n"
LOC_OK = "park,Test Park,1 Main St,Testville,TS,United States,33.7,-84.3\n"
PROG_HEADER = ("id,name,organization,website,type,sport,location_id,min_age,max_age,skill_levels,cost_usd,"
               "stage,environment,status,status_note,last_verified,source_url,description\n")
GOOD = ("clinic,Test Clinic,Test Parks,https://x.org,recreation,tennis,park,12,18,beginner,0,"
        "intro_clinic,beginner_friendly;drop_in,open,,2026-05-01,https://x.org/src,A clinic\n")


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    return tmp_path


def files(tmp, programs=PROG_HEADER + GOOD, sessions="program_id,day,start,end,drop_in\n", locations=LOC_HEADER + LOC_OK):
    (tmp / "p.csv").write_text(programs, encoding="utf-8")
    (tmp / "s.csv").write_text(sessions, encoding="utf-8")
    (tmp / "l.csv").write_text(locations, encoding="utf-8")
    return dict(programs_path=tmp / "p.csv", sessions_path=tmp / "s.csv", locations_path=tmp / "l.csv")


@pytest.mark.parametrize("text,expected", [("16:30", 990), ("4:30 PM", 990), ("4:30pm", 990),
                                           ("12:00 PM", 720), ("12:15 AM", 15), ("0:00", 0)])
def test_parse_clock(text, expected):
    assert parse_clock(text) == expected


@pytest.mark.parametrize("bad", ["", "4pm", "25:00", "13:00 PM", "9:75"])
def test_parse_clock_rejects(bad):
    with pytest.raises(ValueError):
        parse_clock(bad)


def test_parse_weekday():
    assert parse_weekday("Tue") == 1 and parse_weekday("saturday") == 5
    with pytest.raises(ValueError):
        parse_weekday("funday")


def test_parse_environment_splits_known_and_unknown():
    assert parse_environment("drop_in; girls_only; cozy") == (["drop_in", "girls_only"], ["cozy"])


def test_load_and_fetch(tmp_db):
    sessions = ("program_id,day,start,end,drop_in\nclinic,Thu,5:00 PM,6:00 PM,no\nclinic,Tue,4:30 PM,5:30 PM,yes\n")
    report = load_local(**files(tmp_db, sessions=sessions))
    assert report["loaded"] and report["problems"] == [] and report["sessions"] == 2

    by_id = {p["id"]: p for p in fetch_programs()}
    c = by_id["clinic"]
    assert c["stage"] == "intro_clinic" and c["status"] == "open" and c["source_url"] == "https://x.org/src"
    assert c["environment"] == ["beginner_friendly", "drop_in"]
    assert c["last_verified"] == "2026-05-01" and c["last_checked"] == "2026-05-01"
    assert (c["lat"], c["lng"], c["city"]) == (33.7, -84.3, "Testville")  # inherited from the location
    assert c["cost_usd"] == 0
    assert [(s["weekday"], s["start_minute"], s["end_minute"], s["drop_in"]) for s in c["sessions"]] == [
        (1, 990, 1050, True), (3, 1020, 1080, False)]
    other = next(p for p in by_id.values() if p["id"] != "clinic")  # catalog rows still work
    assert other["stage"] is None and other["status"] == "unknown" and other["sessions"] == []


def test_blank_cost_is_null_even_if_text_says_free(tmp_db):
    row = GOOD.replace(",0,intro_clinic", ",,intro_clinic").replace("A clinic", '"Family friendly, free parking"')
    load_local(**files(tmp_db, programs=PROG_HEADER + row))
    clinic = next(p for p in fetch_programs() if p["id"] == "clinic")
    assert clinic["cost_usd"] is None and clinic["cost_label"] == "See website"


def test_reload_replaces_not_duplicates(tmp_db):
    sessions = "program_id,day,start,end,drop_in\nclinic,Tue,4:30 PM,5:30 PM,yes\n"
    kw = files(tmp_db, sessions=sessions)
    load_local(**kw)
    load_local(**kw)
    assert len(next(p for p in fetch_programs() if p["id"] == "clinic")["sessions"]) == 1
    kw = files(tmp_db, programs=PROG_HEADER, sessions=sessions)  # remove the program from the CSV
    load_local(**kw)
    assert all(p["id"] != "clinic" for p in fetch_programs())


def test_bad_rows_are_reported_not_loaded(tmp_db):
    bad_stage = GOOD.replace("clinic,Test", "a,Test").replace("intro_clinic", "super_elite")
    no_date = GOOD.replace("clinic,Test", "b,Test").replace("2026-05-01", "")
    bad_status = GOOD.replace("clinic,Test", "c,Test").replace(",open,", ",maybe,")
    sessions = ("program_id,day,start,end,drop_in\n"
                "clinic,Tue,6:00 PM,5:00 PM,no\n"   # ends before start
                "ghost,Tue,4:00 PM,5:00 PM,no\n"    # matches no program
                "a,Tue,4:00 PM,5:00 PM,no\n")       # belongs to a skipped program: ignored quietly
    report = load_local(**files(tmp_db, programs=PROG_HEADER + GOOD + bad_stage + no_date + bad_status, sessions=sessions))
    assert report["programs"] == 1 and report["sessions"] == 0
    assert len(report["problems"]) == 5


def test_location_without_coordinates_skips_its_programs_once(tmp_db):
    locations = LOC_HEADER + "park,Test Park,1 Main St,Testville,TS,United States,,\n"
    report = load_local(**files(tmp_db, locations=locations, sessions="program_id,day,start,end,drop_in\nclinic,Tue,4:30 PM,5:30 PM,no\n"))
    assert report["programs"] == 0 and report["sessions"] == 0
    assert len(report["problems"]) == 2  # one for the location, one summary for its programs


def test_old_program_extras_table_is_upgraded(tmp_db):
    conn = db.connect()
    conn.execute("CREATE TABLE program_extras (opportunity_id TEXT PRIMARY KEY, stage TEXT NOT NULL, "
                 "environment TEXT NOT NULL DEFAULT '', last_verified TEXT NOT NULL)")
    conn.commit()
    conn.close()
    assert load_local(**files(tmp_db))["loaded"]
    assert next(p for p in fetch_programs() if p["id"] == "clinic")["status"] == "open"


def test_example_rows_and_missing_files_are_skipped(tmp_db):
    row = GOOD.replace("clinic,Test", "example-x,Test")
    report = load_local(programs_path=files(tmp_db, programs=PROG_HEADER + row)["programs_path"],
                        sessions_path=tmp_db / "none.csv", locations_path=tmp_db / "l.csv")
    assert report["programs"] == 0 and report["problems"] == []


def test_dry_run_changes_nothing(tmp_db):
    report = load_local(**files(tmp_db), dry_run=True)
    assert report["programs"] == 1 and not report["loaded"]
    assert not (tmp_db / "test.db").exists()


def test_shipped_forsyth_data_loads_once_coordinates_exist(tmp_db):
    """The real CSVs must be internally consistent: fill every missing coordinate with a dummy and load."""
    work = tmp_db / "local"
    shutil.copytree(LOCAL_DIR, work)
    rows = list(csv.DictReader((work / "locations.csv").open(encoding="utf-8")))
    for r in rows:
        r["lat"], r["lng"] = r["lat"] or "34.2", r["lng"] or "-84.1"
    with (work / "locations.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report = load_local(work / "programs.csv", work / "sessions.csv", work / "locations.csv")
    assert report["loaded"] and report["problems"] == []
    programs = {p["id"]: p for p in fetch_programs() if p["stage"]}
    assert len(programs) == 33 and report["sessions"] == 42
    assert all(p["source_url"].startswith("https://") and p["last_verified"] == "2026-10-19" for p in programs.values())
    # a spot check straight from the source page: Matt Community Park U12 Girls, Tue/Thu 6:30-7:30 PM
    s = programs["ufa-rec-matt-park-u12g"]["sessions"]
    assert [(x["weekday"], x["start_minute"], x["end_minute"]) for x in s] == [(1, 1110, 1170), (3, 1110, 1170)]
