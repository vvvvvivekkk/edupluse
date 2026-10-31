"""Integration tests against the real API + database (the complete repeated cycle)."""
from app import models
from app.database import SessionLocal

STUDENT1 = 1


def run_cycle(client, h_student, h_faculty, student_id, post_score):
    sel = client.post("/api/interventions/select", json={"student_id": student_id}, headers=h_student)
    assert sel.status_code == 200, sel.text
    s = sel.json()
    assert s["selected"] in s["eligible"]
    aid = s["assignment_id"]
    detail = client.get(f"/api/interventions/{aid}", headers=h_student).json()
    if detail["intervention"] == "faculty_support":
        h = h_faculty  # only faculty can mark a consultation complete
        body = {}
    else:
        h = h_student
        qs = (detail["resource"] or {}).get("content", {}).get("questions")
        body = {"answers": [0] * len(qs)} if qs else {}
    assert client.post(f"/api/interventions/{aid}/access", headers=h_student).status_code == 200
    r = client.post(f"/api/interventions/{aid}/complete", json=body, headers=h)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/interventions/{aid}/response", json={"post_score": post_score}, headers=h_student)
    assert r.status_code == 200, r.text
    return s, r.json()["evaluation"]


# ------------------------------------------------------------------ auth & roles
def test_login_success_and_failure(client):
    r = client.post("/api/auth/login", json={"email": "faculty1@edupulse.edu", "password": "Faculty@123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "faculty"
    assert client.post("/api/auth/login", json={"email": "faculty1@edupulse.edu", "password": "nope"}).status_code == 401
    assert client.get("/api/students").status_code == 401


def test_passwords_are_hashed(seeded):
    db = SessionLocal()
    u = db.query(models.User).filter_by(email="admin@edupulse.edu").one()
    assert u.password_hash != "Admin@123" and u.password_hash.startswith("$2")
    db.close()


def test_student_sees_only_self(client, tokens):
    lst = client.get("/api/students", headers=tokens["student1"]).json()
    assert [s["id"] for s in lst] == [STUDENT1]
    assert client.get("/api/students/2", headers=tokens["student1"]).status_code == 403
    assert client.get("/api/students/2/interventions", headers=tokens["student1"]).status_code == 403


def test_faculty_sees_only_assigned(client, tokens):
    ids1 = {s["id"] for s in client.get("/api/students", headers=tokens["faculty1"]).json()}
    ids2 = {s["id"] for s in client.get("/api/students", headers=tokens["faculty2"]).json()}
    assert ids1 and ids2 and not ids1 & ids2
    other = next(iter(ids2))
    assert client.get(f"/api/students/{other}", headers=tokens["faculty1"]).status_code == 403


def test_role_restricted_endpoints(client, tokens):
    assert client.post(f"/api/students/{STUDENT1}/predict-state", headers=tokens["student1"]).status_code == 403
    assert client.get("/api/admin/users", headers=tokens["faculty1"]).status_code == 403
    assert client.get("/api/admin/users", headers=tokens["admin"]).status_code == 200


# ------------------------------------------------------------------ records validation
def test_academic_record_validation(client, tokens):
    h = tokens["faculty1"]
    base = {"student_id": STUDENT1, "record_type": "assessment_result", "assessment_title": "Quiz X", "topic_id": 1}
    assert client.post("/api/academic-records", json={**base}, headers=h).status_code == 422          # missing fields
    assert client.post("/api/academic-records", json={**base, "raw_score": 25, "max_score": 20},
                       headers=h).status_code == 422                                                   # out of range
    assert client.post("/api/academic-records", json={"student_id": STUDENT1, "record_type": "attendance",
                       "period_start": "2026-10-01", "period_end": "2026-10-07", "sessions_attended": 6,
                       "sessions_total": 5}, headers=h).status_code == 422
    ok = client.post("/api/academic-records", json={**base, "raw_score": 15, "max_score": 20}, headers=h)
    assert ok.status_code == 201
    # faculty2 is not assigned student1
    assert client.post("/api/academic-records", json={**base, "raw_score": 15, "max_score": 20},
                       headers=tokens["faculty2"]).status_code == 403


def test_state_requires_data(client, tokens):
    r = client.post("/api/admin/users", headers=tokens["admin"], json={
        "email": "new@edupulse.edu", "full_name": "New Student", "password": "Password1", "role": "student",
        "roll_number": "EP26999"})
    sid = r.json()["student_id"]
    r = client.post(f"/api/students/{sid}/predict-state", headers=tokens["admin"])
    assert r.status_code == 422 and "required indicator" in r.json()["detail"]


# ------------------------------------------------------------------ the cycle
def test_full_cycle_updates_policy_once_and_reassesses_state(client, tokens):
    db = SessionLocal()
    v_before = db.query(models.PolicyVersion).count()
    states_before = db.query(models.StudentState).filter_by(student_id=STUDENT1).count()
    db.close()

    sel, ev = run_cycle(client, tokens["student1"], tokens["faculty1"], STUDENT1, post_score=75)
    assert ev["category"] in ("positive", "partial", "no_improvement")
    assert ev["policy_update"]["to_version"] == ev["policy_update"]["from_version"] + 1
    assert ev["policy_update"]["arm"] == sel["selected"]

    aid = sel["assignment_id"]
    # duplicate submissions must not touch the policy again
    assert client.post(f"/api/interventions/{aid}/response", json={"post_score": 99},
                       headers=tokens["student1"]).status_code == 409
    assert client.post(f"/api/interventions/{aid}/evaluate", headers=tokens["faculty1"]).status_code == 409

    db = SessionLocal()
    assert db.query(models.PolicyVersion).count() == v_before + 1
    assert db.query(models.PolicyUpdate).filter_by(assignment_id=aid).count() == 1
    # state history is appended, not overwritten
    assert db.query(models.StudentState).filter_by(student_id=STUDENT1).count() == states_before + 1
    a = db.get(models.InterventionAssignment, aid)
    assert a.status == "evaluated" and a.response.reward is not None
    assert a.context["vector"] and a.sampled_scores and a.rng_seed is not None  # auditable decision
    # policy parameters of the chosen arm changed; the others did not
    pv = db.query(models.PolicyVersion).order_by(models.PolicyVersion.version.desc()).first()
    prev = db.query(models.PolicyVersion).filter_by(version=pv.version - 1).one()
    code_to_id = {t.code: t.id for t in db.query(models.InterventionType)}
    for code, tid in code_to_id.items():
        new = db.query(models.PolicyParameter).filter_by(policy_version_id=pv.id, intervention_type_id=tid).one()
        old = db.query(models.PolicyParameter).filter_by(policy_version_id=prev.id, intervention_type_id=tid).one()
        assert (new.A != old.A) == (code == sel["selected"])
    db.close()


def test_open_intervention_blocks_new_selection(client, tokens):
    assert client.post("/api/interventions/select", json={"student_id": STUDENT1},
                       headers=tokens["student1"]).status_code == 200
    assert client.post("/api/interventions/select", json={"student_id": STUDENT1},
                       headers=tokens["student1"]).status_code == 409


def test_response_requires_completion_and_valid_score(client, tokens):
    aid = client.post("/api/interventions/select", json={"student_id": STUDENT1},
                      headers=tokens["student1"]).json()["assignment_id"]
    assert client.post(f"/api/interventions/{aid}/response", json={"post_score": 70},
                       headers=tokens["student1"]).status_code == 409
    assert client.post(f"/api/interventions/{aid}/response", json={"post_score": 140},
                       headers=tokens["student1"]).status_code == 422
    # another student cannot submit for this intervention
    assert client.post(f"/api/interventions/{aid}/response", json={"post_score": 70},
                       headers=tokens["student2"]).status_code == 403


def test_repeated_cycles_and_no_improvement_escalation(client, tokens):
    """Three poor outcomes in a row -> faculty support becomes eligible; history is kept for all."""
    hs, hf = tokens["student1"], tokens["faculty1"]
    seen_faculty = False
    for _ in range(4):
        cur = client.get(f"/api/students/{STUDENT1}", headers=hs).json()
        pre = (cur["open_intervention"] or {}).get("pre_score")
        sel, ev = run_cycle(client, hs, hf, STUDENT1, post_score=10)  # clearly worse each time
        assert ev["category"] == "no_improvement"
        seen_faculty = seen_faculty or "faculty_support" in sel["eligible"]
    assert seen_faculty
    hist = client.get(f"/api/students/{STUDENT1}/interventions", headers=hs).json()
    assert len(hist) == 4 and all(h["category"] == "no_improvement" for h in hist)
    summ = client.get("/api/dashboard/summary", headers=hf).json()
    assert any(s["student_id"] == STUDENT1 for s in summ["students_needing_review"])


def test_dashboard_consistency_with_database(client, tokens):
    run_cycle(client, tokens["student1"], tokens["faculty1"], STUDENT1, post_score=80)
    summ = client.get("/api/dashboard/summary", headers=tokens["admin"]).json()
    db = SessionLocal()
    assert summ["student_count"] == db.query(models.StudentProfile).count()
    assert sum(summ["intervention_status"].values()) == db.query(models.InterventionAssignment).count()
    assert sum(summ["response_categories"].values()) == db.query(models.InterventionResponse).filter(
        models.InterventionResponse.category.isnot(None)).count()
    assert summ["admin"]["policy_updates"] == db.query(models.PolicyUpdate).count()
    db.close()
    an = client.get("/api/analytics", headers=tokens["admin"]).json()
    assert all(t["mean_reward"] is None for t in an["type_summary"])  # too few observations to compare


def test_admin_config_validation_and_audit(client, tokens):
    h = tokens["admin"]
    assert client.put("/api/admin/config", json={"reward_alpha": 1.5}, headers=h).status_code == 422
    assert client.put("/api/admin/config", json={"bogus": 1}, headers=h).status_code == 422
    r = client.put("/api/admin/config", json={"reward_alpha": 0.6}, headers=h)
    assert r.status_code == 200 and r.json()["policy_config"]["reward_alpha"] == 0.6
    log = client.get("/api/admin/audit", headers=h).json()
    assert any(e["action"] == "update_config" for e in log)


def test_faculty_manual_support_record(client, tokens):
    r = client.post("/api/interventions/assign", json={"student_id": STUDENT1, "intervention": "faculty_support",
                    "note": "Discuss recursion base cases"}, headers=tokens["faculty1"])
    assert r.status_code == 200 and r.json()["selection_method"] == "faculty_manual"
    aid = r.json()["id"]
    # students cannot mark faculty support complete
    assert client.post(f"/api/interventions/{aid}/complete", json={}, headers=tokens["student1"]).status_code == 403
    assert client.post(f"/api/interventions/{aid}/complete", json={}, headers=tokens["faculty1"]).status_code == 200
