"""Bulk import, record correction, username login, role assignment, config/patch validation, and
concurrent policy updates."""
import threading

import pytest

from app import models
from app.database import SessionLocal, engine
from app.engine import service
from conftest import login
from test_api import STUDENT1, run_cycle

HEADER = ("roll_number,record_type,assessment_title,topic,raw_score,max_score,period_start,period_end,"
          "sessions_attended,sessions_total,assignment,status,questions_attempted,questions_correct\n")


def upload(client, h, csv_text, dry_run=False):
    return client.post(f"/api/academic-records/import?dry_run={str(dry_run).lower()}", headers=h,
                       files={"file": ("records.csv", csv_text.encode(), "text/csv")})


def count_records(student_id):
    db = SessionLocal()
    n = sum(db.query(m).filter(m.student_id == student_id).count() for m in (
        models.StudentAssessmentResult, models.AttendanceRecord, models.StudentAssignmentRecord,
        models.LearningActivityRecord))
    db.close()
    return n


# ------------------------------------------------------------------ bulk import (brief §10 stage 1)
GOOD_ROWS = (
    "EP26001,assessment_result,Quiz 5: OOP,Object-Oriented Basics,14,20,,,,,,,,\n"
    "EP26001,attendance,,,,,2026-10-20,2026-10-26,4,5,,,,\n"
    "EP26001,assignment,,,,,,,,,Assignment 5: Object-Oriented Basics,late,,\n"
    "ep26003,practice,,Loops,,,,,,,,,10,7\n"
)


def test_import_dry_run_then_import(client, tokens):
    h = tokens["faculty1"]  # student1 and student3 are both assigned to faculty1
    before = count_records(STUDENT1)
    r = upload(client, h, HEADER + GOOD_ROWS, dry_run=True)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["dry_run"] and d["valid"] == 4 and d["errors"] == [] and d["imported"] == 0
    assert d["by_type"] == {"assessment_result": 1, "attendance": 1, "assignment": 1, "practice": 1}
    assert count_records(STUDENT1) == before  # dry run stores nothing

    r = upload(client, h, HEADER + GOOD_ROWS)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 4 and r.json()["students"] == 2
    assert count_records(STUDENT1) == before + 3
    # imported data mark the state as stale, so the next selection re-estimates it
    assert client.get(f"/api/students/{STUDENT1}", headers=h).json()["state_is_stale"] is True
    log = client.get("/api/admin/audit", headers=tokens["admin"]).json()
    assert any(e["action"] == "import_academic_records" and e["details"]["count"] == 4 for e in log)


def test_import_is_all_or_nothing_with_row_errors(client, tokens):
    h = tokens["faculty1"]
    before = count_records(STUDENT1)
    bad = (GOOD_ROWS
           + "EP26001,assessment_result,Quiz,Loops,25,20,,,,,,,,\n"          # row 6: score > max
           + "EP26001,assessment_result,Quiz,,10,20,,,,,,,,\n"               # row 7: topic missing
           + "EP26999,attendance,,,,,2026-10-20,2026-10-26,4,5,,,,\n"         # row 8: unknown student
           + "EP26002,practice,,Loops,,,,,,,,,10,7\n"                        # row 9: not faculty1's student
           + "EP26001,assignment,,,,,,,,,Assignment 1: Loops,submitted,,\n"  # row 10: already recorded
           + "EP26001,attendance,,,,,2026-10-20,2026-10-26,,5,,,,\n"         # row 11: missing value
           + "EP26001,practice,,Nonexistent,,,,,,,,,10,7\n")                 # row 12: unknown topic
    r = upload(client, h, HEADER + bad, dry_run=True)
    assert r.status_code == 200
    errs = {e["row"]: e["error"] for e in r.json()["errors"]}
    assert sorted(errs) == [6, 7, 8, 9, 10, 11, 12], errs
    assert "cannot exceed" in errs[6] and "topic_id" in errs[7] and "unknown roll_number" in errs[8]
    assert "not authorised" in errs[9] and "already recorded" in errs[10] and "sessions_attended" in errs[11]

    r = upload(client, h, HEADER + bad)
    assert r.status_code == 422
    assert len(r.json()["detail"]) == 7
    assert count_records(STUDENT1) == before  # nothing from the valid rows was stored either


def test_import_rejects_bad_files(client, tokens):
    h = tokens["admin"]
    assert upload(client, h, "name,score\nx,1\n").status_code == 422           # wrong header
    assert upload(client, h, HEADER).status_code == 422                        # no records
    dup = "EP26001,assignment,,,,,,,,,Assignment 5: Object-Oriented Basics,late,,\n"
    r = upload(client, h, HEADER + dup + dup, dry_run=True)                    # duplicate inside the file
    assert [e["row"] for e in r.json()["errors"]] == [3]
    r = client.post("/api/academic-records/import", headers=h,
                    files={"file": ("x.csv", b"\xff\xfe\x00bad", "text/csv")})
    assert r.status_code == 422
    assert upload(client, tokens["student1"], HEADER + GOOD_ROWS).status_code == 403  # students cannot import


# ------------------------------------------------------------------ record listing and correction
def test_correct_record_is_audited_and_reassesses_state(client, tokens):
    h = tokens["faculty1"]
    recs = client.get(f"/api/students/{STUDENT1}/academic-records", headers=h).json()
    quiz = next(r for r in recs if r["record_type"] == "assessment_result" and not r["locked"])
    states_before = len(client.get(f"/api/students/{STUDENT1}/progress", headers=h).json()["states"])

    r = client.patch(f"/api/academic-records/assessment_result/{quiz['id']}", headers=h,
                     json={"raw_score": 19, "reason": "Marking error corrected after re-check"})
    assert r.status_code == 200, r.text
    assert r.json()["record"]["score_pct"] == 95.0 and r.json()["state_reassessed"]
    states_after = len(client.get(f"/api/students/{STUDENT1}/progress", headers=h).json()["states"])
    assert states_after == states_before + 1  # new state row appended, old one kept
    log = client.get("/api/admin/audit", headers=tokens["admin"]).json()
    entry = next(e for e in log if e["action"] == "correct_academic_record")
    assert entry["details"]["before"]["raw_score"] == quiz["raw_score"] and entry["details"]["after"]["raw_score"] == 19
    assert entry["details"]["reason"].startswith("Marking error")


def test_correct_record_validation_and_permissions(client, tokens):
    h = tokens["faculty1"]
    recs = client.get(f"/api/students/{STUDENT1}/academic-records", headers=h).json()
    quiz = next(r for r in recs if r["record_type"] == "assessment_result")
    att = next(r for r in recs if r["record_type"] == "attendance")
    url = f"/api/academic-records/assessment_result/{quiz['id']}"
    assert client.patch(url, headers=h, json={"raw_score": 25, "reason": "typo fix"}).status_code == 422  # > max 20
    assert client.patch(url, headers=h, json={"raw_score": 10}).status_code == 422                       # no reason
    assert client.patch(url, headers=h, json={"reason": "nothing to change"}).status_code == 422
    assert client.patch(url, headers=h, json={"status": "late", "reason": "wrong field"}).status_code == 422
    assert client.patch(f"/api/academic-records/attendance/{att['id']}", headers=h,
                        json={"sessions_attended": 9, "reason": "typo fix"}).status_code == 422          # > total 5
    assert client.patch(url, headers=tokens["student1"], json={"raw_score": 20, "reason": "pls"}).status_code == 403
    assert client.patch(url, headers=tokens["faculty2"], json={"raw_score": 20, "reason": "x y z"}).status_code == 403
    assert client.patch("/api/academic-records/attendance/999999", headers=h,
                        json={"sessions_attended": 1, "reason": "missing"}).status_code == 404
    # a student may list only their own records
    assert client.get(f"/api/students/{STUDENT1}/academic-records", headers=tokens["student1"]).status_code == 200
    assert client.get("/api/students/2/academic-records", headers=tokens["student1"]).status_code == 403


def test_records_behind_intervention_results_are_locked(client, tokens):
    sel, ev = run_cycle(client, tokens["student1"], tokens["faculty1"], STUDENT1, post_score=70)
    recs = client.get(f"/api/students/{STUDENT1}/academic-records", headers=tokens["admin"]).json()
    follow_up = next(r for r in recs if r["record_type"] == "assessment_result" and r["kind"] == "follow_up")
    assert follow_up["locked"]
    r = client.patch(f"/api/academic-records/assessment_result/{follow_up['id']}", headers=tokens["admin"],
                     json={"raw_score": 100, "reason": "trying to rewrite history"})
    assert r.status_code == 409
    hist = client.get(f"/api/students/{STUDENT1}/interventions", headers=tokens["admin"]).json()
    assert hist[0]["post_score"] == 70  # the evaluated result is unchanged


# ------------------------------------------------------------------ login with username
def test_login_with_roll_number_as_username(client):
    r = client.post("/api/auth/login", json={"email": "ep26001", "password": "Student@123"})
    assert r.status_code == 200 and r.json()["user"]["student_id"] == STUDENT1
    assert client.post("/api/auth/login", json={"email": "EP26001", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody", "password": "Student@123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "", "password": ""}).status_code == 422


# ------------------------------------------------------------------ role assignment (brief §3.3)
def test_admin_assigns_roles_and_profiles_are_created(client, tokens):
    h = tokens["admin"]
    u = client.post("/api/admin/users", headers=h, json={"email": "ta@edupulse.edu", "full_name": "Teaching Asst",
                                                          "password": "Password1", "role": "admin"}).json()
    r = client.patch(f"/api/admin/users/{u['id']}", headers=h, json={"role": "faculty", "department": "Maths"})
    assert r.status_code == 200 and r.json()["role"] == "faculty" and r.json()["faculty_id"]
    fid = r.json()["faculty_id"]
    assert client.patch(f"/api/admin/users/{u['id']}", headers=h, json={"role": "student"}).status_code == 422
    assert client.patch(f"/api/admin/users/{u['id']}", headers=h,
                        json={"role": "student", "roll_number": "EP26001"}).status_code == 409  # roll number taken
    r = client.patch(f"/api/admin/users/{u['id']}", headers=h, json={"role": "student", "roll_number": "EP26500"})
    assert r.status_code == 200 and r.json()["role"] == "student" and r.json()["student_id"]
    # profiles are kept when the role changes again, so no history is lost
    r = client.patch(f"/api/admin/users/{u['id']}", headers=h, json={"role": "faculty"})
    assert r.json()["faculty_id"] == fid and r.json()["student_id"]
    tok = login(client, "ta@edupulse.edu", "Password1")
    assert client.get("/api/students", headers=tok).json() == []  # new faculty: no students assigned yet
    log = client.get("/api/admin/audit", headers=h).json()
    assert any(e["action"] == "update_user" and e["details"].get("previous_role") == "student" for e in log)


def test_admin_cannot_lock_themselves_out(client, tokens):
    h = tokens["admin"]
    me = client.get("/api/auth/me", headers=h).json()
    assert client.patch(f"/api/admin/users/{me['id']}", headers=h, json={"role": "faculty"}).status_code == 422
    assert client.patch(f"/api/admin/users/{me['id']}", headers=h, json={"is_active": False}).status_code == 422
    assert client.patch(f"/api/admin/users/{me['id']}", headers=h, json={"full_name": "Admin"}).status_code == 200


# ------------------------------------------------------------------ input validation on admin endpoints
def test_config_rejects_non_numeric_and_out_of_range(client, tokens):
    h = tokens["admin"]
    for body in ({"reward_alpha": "high"}, {"reward_alpha": True}, {"no_improvement_streak": 1.5},
                 {"engagement_window_days": 0}, {"low_score_threshold": 140}, {"positive_threshold": 2}):
        assert client.put("/api/admin/config", json=body, headers=h).status_code == 422, body
    r = client.put("/api/admin/config", json={"no_improvement_streak": 3.0}, headers=h)
    assert r.status_code == 200 and r.json()["policy_config"]["no_improvement_streak"] == 3


def test_resource_and_type_patches_are_validated(client, tokens):
    h = tokens["admin"]
    assert client.patch("/api/admin/resources/1", headers=h, json={"topic_id": 9999}).status_code == 422
    assert client.patch("/api/admin/resources/1", headers=h, json={"title": None}).status_code == 422
    assert client.patch("/api/admin/resources/1", headers=h, json={"is_active": "maybe"}).status_code == 422
    r = client.patch("/api/admin/resources/1", headers=h, json={"topic_id": None})
    assert r.status_code == 200 and r.json()["topic_id"] is None
    assert client.patch("/api/admin/intervention-types/1", headers=h, json={"is_active": "nope"}).status_code == 422
    assert client.patch("/api/admin/intervention-types/1", headers=h, json={"is_active": False}).json()["is_active"] is False


# ------------------------------------------------------------------ concurrency
@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="SQLite serialises writers itself")
def test_concurrent_evaluations_do_not_lose_policy_updates(client, tokens):
    """Several students' responses evaluated at the same moment: every update must be applied, in an
    unbroken version chain (vN -> vN+1 -> ...), with none rejected or lost."""
    h = tokens["admin"]
    aids = []
    for s in client.get("/api/students", headers=h).json():
        if len(aids) == 6:
            break
        aid = client.post("/api/interventions/select", json={"student_id": s["id"]}, headers=h).json()["assignment_id"]
        if aid is None:
            continue  # no intervention indicated for this student's state
        qs = (client.get(f"/api/interventions/{aid}", headers=h).json()["resource"] or {}).get("content", {}).get("questions")
        assert client.post(f"/api/interventions/{aid}/complete", headers=h,
                           json={"answers": [0] * len(qs)} if qs else {}).status_code == 200
        assert client.post(f"/api/interventions/{aid}/response", headers=h,
                           json={"post_score": 70, "evaluate": False}).status_code == 200
        aids.append(aid)
    db = SessionLocal()
    v0 = service.current_policy_version(db).version
    db.close()

    barrier, errors = threading.Barrier(len(aids)), []

    def evaluate(aid):
        s = SessionLocal()
        try:
            barrier.wait()
            service.evaluate_response(s, aid, None)
            s.commit()
        except Exception as e:  # noqa: BLE001 - collected and asserted below
            errors.append(repr(e))
            s.rollback()
        finally:
            s.close()

    threads = [threading.Thread(target=evaluate, args=(a,)) for a in aids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    db = SessionLocal()
    vmap = {v.id: v.version for v in db.query(models.PolicyVersion)}
    ups = db.query(models.PolicyUpdate).filter(models.PolicyUpdate.assignment_id.in_(aids)).all()
    chain = sorted((vmap[u.from_version_id], vmap[u.to_version_id]) for u in ups)
    assert chain == [(v0 + i, v0 + i + 1) for i in range(len(aids))]
    final = db.query(models.PolicyVersion).filter_by(version=v0 + len(aids)).one()
    total_n = sum(p.n_observations for p in db.query(models.PolicyParameter).filter_by(policy_version_id=final.id))
    assert total_n == len(aids)  # every observation is in the latest policy
    db.close()
