"""Orchestrates the response-adaptive cycle against the database.

  estimate_state()          Algorithm 1  (Random Forest)          -> student_states (append-only)
  select_intervention()     Algorithms 2+3 (eligibility + LinTS)   -> intervention_assignments
  record_response()         Module 3     (post-intervention data)  -> intervention_responses
  evaluate_response()       Algorithm 4  (reward, category, policy update, THEN separate state reassessment)

Updating the POLICY (policy_versions/parameters/updates) and updating the STUDENT STATE
(student_states) are separate operations; evaluate_response performs both but in two
explicit steps and reports them separately.
"""
import secrets
from datetime import datetime, timezone

import numpy as np
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..ml.features import (FeatureValidationError, compute_indicators, engagement_index,
                           window_before)
from ..ml.state_model import load_model, predict_state
from ..services_common import ELIGIBILITY_RULES_KEY, audit, get_policy_config
from . import reward as rw
from .eligibility import DEFAULT_RULES, evaluate_eligibility, validate_rules
from .thompson import CONTEXT_FEATURES, DIM, ArmParams, build_context, select_arm

OPEN_STATUSES = ("assigned", "accessed", "completed")


def now():
    return datetime.now(timezone.utc)


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ config
def get_rules(db: Session) -> list[dict]:
    row = db.get(models.SystemConfig, ELIGIBILITY_RULES_KEY)
    return row.value["rules"] if row else DEFAULT_RULES


def set_rules(db: Session, rules: list[dict], user_id: int | None):
    arms = {t.code for t in db.query(models.InterventionType).all()}
    validate_rules(rules, arms)
    before = get_rules(db)
    row = db.get(models.SystemConfig, ELIGIBILITY_RULES_KEY)
    if row:
        row.value = {"rules": rules}
        row.updated_by = user_id
    else:
        db.add(models.SystemConfig(key=ELIGIBILITY_RULES_KEY, value={"rules": rules}, updated_by=user_id))
    audit(db, user_id, "update_eligibility_rules", "system_config", ELIGIBILITY_RULES_KEY,
          {"before": before, "after": rules})


# ------------------------------------------------------------------ policy storage
def current_policy_version(db: Session) -> models.PolicyVersion:
    pv = db.query(models.PolicyVersion).order_by(models.PolicyVersion.version.desc()).first()
    if pv is None:
        pv = create_initial_policy(db, user_id=None, reason="initial prior")
    return pv


def create_initial_policy(db: Session, user_id: int | None, reason: str) -> models.PolicyVersion:
    """Create a new version with prior parameters (A = lambda I, b = 0) for every arm.
    Used at first start and when an admin re-initialises the policy. Old versions are kept."""
    cfg = get_policy_config(db)
    last = db.query(func.max(models.PolicyVersion.version)).scalar() or 0
    pv = models.PolicyVersion(version=last + 1, reason=reason, lam=cfg["lints_lambda"], v=cfg["lints_v"],
                              dim=DIM, feature_names=CONTEXT_FEATURES, created_by=user_id)
    db.add(pv)
    db.flush()
    for t in db.query(models.InterventionType).all():
        p = ArmParams.prior(DIM, cfg["lints_lambda"])
        db.add(models.PolicyParameter(policy_version_id=pv.id, intervention_type_id=t.id,
                                      A=p.A.tolist(), b=p.b.tolist(), n_observations=0))
    db.flush()
    audit(db, user_id, "create_policy_version", "policy_versions", pv.version,
          {"reason": reason, "lambda": pv.lam, "v": pv.v})
    return pv


def load_params(db: Session, pv: models.PolicyVersion) -> dict[str, ArmParams]:
    rows = db.query(models.PolicyParameter, models.InterventionType).join(
        models.InterventionType, models.InterventionType.id == models.PolicyParameter.intervention_type_id
    ).filter(models.PolicyParameter.policy_version_id == pv.id).all()
    params = {t.code: ArmParams(A=np.array(p.A), b=np.array(p.b), n=p.n_observations) for p, t in rows}
    # an intervention type added after this version was created starts from the prior
    for t in db.query(models.InterventionType).all():
        params.setdefault(t.code, ArmParams.prior(pv.dim, pv.lam))
    return params


# ------------------------------------------------------------------ history helpers
def response_history(db: Session, student_id: int):
    return db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id == student_id,
        models.InterventionAssignment.status == "evaluated",
    ).order_by(models.InterventionAssignment.assigned_at.desc()).all()


def no_improvement_streak(db: Session, student_id: int) -> tuple[int, str | None]:
    """Number of consecutive most-recent evaluated interventions with 'no_improvement'
    and the intervention code of the most recent one if it failed."""
    streak, last_failed = 0, None
    for i, a in enumerate(response_history(db, student_id)):
        if a.response and a.response.category == "no_improvement":
            streak += 1
            if i == 0:
                last_failed = a.intervention_type.code
        else:
            break
    return streak, last_failed


def latest_state(db: Session, student_id: int) -> models.StudentState | None:
    return db.query(models.StudentState).filter(models.StudentState.student_id == student_id).order_by(
        models.StudentState.created_at.desc(), models.StudentState.id.desc()).first()


# ------------------------------------------------------------------ Algorithm 1
def estimate_state(db: Session, student_id: int, user_id: int | None) -> models.StudentState:
    ind = compute_indicators(db, student_id)
    try:
        pred = predict_state(ind["features"])
    except FeatureValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    st = models.StudentState(student_id=student_id, state=pred["state"], features=ind["features"],
                             imputed_features=pred["imputed_features"], probabilities=pred["probabilities"],
                             explanation=pred["explanation"], model_version=pred["model_version"])
    db.add(st)
    db.flush()
    audit(db, user_id, "predict_state", "student_states", st.id,
          {"student_id": student_id, "state": st.state, "model_version": st.model_version})
    return st


def state_is_stale(db: Session, student_id: int, st: models.StudentState | None) -> bool:
    if st is None:
        return True
    t = aware(st.created_at)
    tables = [(models.StudentAssessmentResult, models.StudentAssessmentResult.recorded_at),
              (models.AttendanceRecord, models.AttendanceRecord.recorded_at),
              (models.StudentAssignmentRecord, models.StudentAssignmentRecord.recorded_at),
              (models.LearningActivityRecord, models.LearningActivityRecord.recorded_at)]
    for model, col in tables:
        latest = db.query(func.max(col)).filter(model.student_id == student_id).scalar()
        if latest and aware(latest) > t:
            return True
    return False


# ------------------------------------------------------------------ Algorithms 2 + 3
def selection_context(db: Session, student_id: int, st: models.StudentState) -> dict:
    ind = compute_indicators(db, student_id)
    per_topic = ind["per_topic"]
    # target topic = topic with the lowest latest score (else the latest assessed topic)
    scored = [t for t in per_topic if t["latest_score"] is not None]
    target = min(scored, key=lambda t: t["latest_score"]) if scored else None
    streak, last_failed = no_improvement_streak(db, student_id)
    ctx = {
        "state": st.state,
        "latest_score": ind["features"]["latest_score"],
        "topic_id": target["topic_id"] if target else ind["latest_topic_id"],
        "topic": target["topic"] if target else None,
        "topic_score": target["latest_score"] if target else ind["features"]["latest_score"],
        "topic_mastery": (target or {}).get("practice_accuracy_pct"),
        "attendance_pct": ind["features"]["attendance_pct"],
        "assignment_completion_pct": ind["features"]["assignment_completion_pct"],
        "practice_accuracy_pct": ind["features"]["practice_accuracy_pct"],
        "no_improvement_streak": streak,
    }
    return {"ctx": ctx, "features": ind["features"], "last_failed": last_failed}


def open_assignment(db: Session, student_id: int):
    return db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id == student_id,
        models.InterventionAssignment.status.in_(OPEN_STATUSES)).first()


def pick_resource(db: Session, type_id: int, topic_id: int | None):
    q = db.query(models.LearningResource).filter(models.LearningResource.intervention_type_id == type_id,
                                                 models.LearningResource.is_active.is_(True))
    res = q.filter(models.LearningResource.topic_id == topic_id).first() if topic_id else None
    return res or q.filter(models.LearningResource.topic_id.is_(None)).first() or q.first()


def select_intervention(db: Session, student_id: int, user_id: int | None, seed: int | None = None) -> dict:
    existing = open_assignment(db, student_id)
    if existing:
        raise HTTPException(status_code=409, detail=(
            f"Student already has an open intervention (#{existing.id}, {existing.status}). "
            "Complete and evaluate it before selecting the next one."))
    st = latest_state(db, student_id)
    reassessed = False
    if state_is_stale(db, student_id, st):
        st = estimate_state(db, student_id, user_id)
        reassessed = True
    cfg = get_policy_config(db)
    sc = selection_context(db, student_id, st)
    ctx = sc["ctx"]
    active = {t.code for t in db.query(models.InterventionType).filter(models.InterventionType.is_active.is_(True))}
    elig = evaluate_eligibility(ctx, get_rules(db), cfg, active, sc["last_failed"])
    pv = current_policy_version(db)

    base = {"student_id": student_id, "state": st.state, "state_id": st.id, "state_reassessed": reassessed,
            "context": ctx, "eligible": elig["eligible"], "eligibility": elig,
            "policy_version": pv.version}
    if not elig["eligible"]:
        audit(db, user_id, "select_intervention_none", "students", student_id, {"reason": elig["fallback"]})
        return {**base, "selected": None, "assignment_id": None,
                "message": "No intervention is indicated by the configured rules for the current state."}

    _, card = load_model()
    x = build_context(ctx, st.state, ctx["no_improvement_streak"], card["training_medians"])
    seed = seed if seed is not None else secrets.randbelow(2**31 - 1)
    rng = np.random.default_rng(seed)
    params = load_params(db, pv)
    chosen, details = select_arm(params, elig["eligible"], x, pv.v, rng)

    itype = db.query(models.InterventionType).filter(models.InterventionType.code == chosen).one()
    resource = pick_resource(db, itype.id, ctx["topic_id"])
    start, end = window_before(now(), cfg["engagement_window_days"])
    pre = {"topic_id": ctx["topic_id"], "topic_score": ctx["topic_score"], "features": sc["features"],
           "engagement": engagement_index(db, student_id, start, end, cfg["engagement_window_days"])}
    a = models.InterventionAssignment(
        student_id=student_id, intervention_type_id=itype.id, topic_id=ctx["topic_id"],
        resource_id=resource.id if resource else None, student_state_id=st.id, policy_version_id=pv.id,
        context={"indicators": ctx, "vector": x.tolist(), "vector_features": CONTEXT_FEATURES},
        eligible=elig["eligible"], eligibility_reasons=elig, sampled_scores=details, rng_seed=seed,
        selection_method="linear_thompson", pre_indicators=pre, status="assigned", assigned_by=user_id)
    db.add(a)
    db.flush()
    audit(db, user_id, "assign_intervention", "intervention_assignments", a.id,
          {"student_id": student_id, "selected": chosen, "eligible": elig["eligible"],
           "policy_version": pv.version, "seed": seed})
    return {**base, "selected": chosen, "assignment_id": a.id, "sampled_scores": details,
            "rng_seed": seed, "context_vector": dict(zip(CONTEXT_FEATURES, [round(v, 4) for v in x])),
            "explanation": elig["reasons"][chosen], "resource_id": a.resource_id,
            "selected_at": a.assigned_at.isoformat()}


def faculty_assign(db: Session, student_id: int, code: str, note: str | None, user_id: int) -> models.InterventionAssignment:
    """Faculty-recorded intervention (e.g. a consultation). Human decision, recorded as such."""
    if open_assignment(db, student_id):
        raise HTTPException(status_code=409, detail="Student already has an open intervention")
    itype = db.query(models.InterventionType).filter(models.InterventionType.code == code,
                                                     models.InterventionType.is_active.is_(True)).first()
    if not itype:
        raise HTTPException(status_code=422, detail=f"Unknown or inactive intervention '{code}'")
    st = latest_state(db, student_id)
    if state_is_stale(db, student_id, st):
        st = estimate_state(db, student_id, user_id)
    cfg = get_policy_config(db)
    sc = selection_context(db, student_id, st)
    ctx = sc["ctx"]
    _, card = load_model()
    x = build_context(ctx, st.state, ctx["no_improvement_streak"], card["training_medians"])
    pv = current_policy_version(db)
    resource = pick_resource(db, itype.id, ctx["topic_id"])
    start, end = window_before(now(), cfg["engagement_window_days"])
    a = models.InterventionAssignment(
        student_id=student_id, intervention_type_id=itype.id, topic_id=ctx["topic_id"],
        resource_id=resource.id if resource else None, student_state_id=st.id, policy_version_id=pv.id,
        context={"indicators": ctx, "vector": x.tolist(), "vector_features": CONTEXT_FEATURES},
        eligible=[code], eligibility_reasons={"reasons": {code: ["Recorded by faculty member"]}},
        sampled_scores={}, rng_seed=0, selection_method="faculty_manual",
        pre_indicators={"topic_id": ctx["topic_id"], "topic_score": ctx["topic_score"],
                        "features": sc["features"], "engagement": engagement_index(db, student_id, start, end, cfg["engagement_window_days"])},
        status="assigned", assigned_by=user_id, faculty_note=note)
    db.add(a)
    db.flush()
    audit(db, user_id, "faculty_assign_intervention", "intervention_assignments", a.id,
          {"student_id": student_id, "code": code, "note": note})
    return a


# ------------------------------------------------------------------ Module 3
def mark_accessed(db: Session, a: models.InterventionAssignment, user_id: int):
    if a.status == "assigned":
        a.status = "accessed"
        a.accessed_at = now()
        audit(db, user_id, "access_intervention", "intervention_assignments", a.id)


def complete(db: Session, a: models.InterventionAssignment, user_id: int, answers: list[int] | None) -> dict:
    if a.status not in ("assigned", "accessed"):
        raise HTTPException(status_code=409, detail=f"Intervention is already {a.status}")
    result = None
    qs = (a.resource.content or {}).get("questions") if a.resource else None
    if a.intervention_type.code == "targeted_practice" and qs:
        if answers is None or len(answers) != len(qs):
            raise HTTPException(status_code=422, detail=f"Provide answers for all {len(qs)} practice questions")
        correct = sum(1 for q, ans in zip(qs, answers) if q["answer"] == ans)
        db.add(models.LearningActivityRecord(student_id=a.student_id, topic_id=a.topic_id or a.resource.topic_id,
                                             activity_type="practice", questions_attempted=len(qs),
                                             questions_correct=correct, intervention_assignment_id=a.id))
        result = {"correct": correct, "attempted": len(qs)}
    a.status = "completed"
    a.completed_at = now()
    if not a.accessed_at:
        a.accessed_at = a.completed_at
    audit(db, user_id, "complete_intervention", "intervention_assignments", a.id, {"practice": result})
    return {"status": a.status, "practice_result": result}


def record_response(db: Session, a: models.InterventionAssignment, post_score: float, user_id: int) -> models.InterventionResponse:
    """Store the follow-up assessment. Validates ownership/state and comparability."""
    existing = db.query(models.InterventionResponse).filter(
        models.InterventionResponse.assignment_id == a.id).first()
    if existing is not None or a.status == "evaluated":
        raise HTTPException(status_code=409, detail="A response has already been recorded for this intervention")
    if a.status != "completed":
        raise HTTPException(status_code=409, detail="The intervention must be completed before a follow-up is recorded")
    if post_score is None or not 0 <= post_score <= 100:
        raise HTTPException(status_code=422, detail="Follow-up score must be a percentage between 0 and 100")
    if a.pre_indicators.get("topic_score") is None:
        raise HTTPException(status_code=422, detail="No comparable pre-intervention score was stored")
    cfg = get_policy_config(db)
    topic_id = a.topic_id
    # The follow-up is stored as a normal assessment on the SAME topic and SAME 0-100 scale
    # as the pre-intervention score, so both measurements are comparable and the student's
    # academic record (and thus later state reassessment) reflects it.
    topic = db.get(models.Topic, topic_id) if topic_id else None
    assess = models.Assessment(title=f"Follow-up: {topic.name if topic else 'topic'} (intervention #{a.id})",
                               topic_id=topic_id, kind="follow_up", max_score=100)
    db.add(assess)
    db.flush()
    db.add(models.StudentAssessmentResult(student_id=a.student_id, assessment_id=assess.id, raw_score=post_score,
                                          score_pct=post_score, recorded_by=user_id))
    t_now = now()
    post_eng = engagement_index(db, a.student_id, aware(a.assigned_at), t_now, cfg["engagement_window_days"])
    resp = models.InterventionResponse(
        assignment_id=a.id, submitted_by=user_id,
        post_indicators={"topic_id": topic_id, "topic_score": post_score, "assessment_id": assess.id,
                         "engagement": post_eng, "observation_window_days": cfg["engagement_window_days"]})
    db.add(resp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A response has already been recorded for this intervention")
    db.refresh(a)  # make a.response reflect the new row
    audit(db, user_id, "record_response", "intervention_responses", resp.id,
          {"assignment_id": a.id, "post_score": post_score})
    return resp


# ------------------------------------------------------------------ Algorithm 4
def evaluate_response(db: Session, assignment_id: int, user_id: int | None) -> dict:
    # Lock the assignment row so two concurrent evaluations cannot both update the policy.
    a = db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.id == assignment_id).with_for_update().first()
    if a is None:
        raise HTTPException(status_code=404, detail="Intervention not found")
    resp = db.query(models.InterventionResponse).filter(
        models.InterventionResponse.assignment_id == a.id).first()
    if a.status == "evaluated" or (resp and resp.evaluated_at):
        raise HTTPException(status_code=409, detail="Already evaluated - the policy is not updated twice")
    if resp is None:
        raise HTTPException(status_code=409, detail="No follow-up response recorded yet")
    cfg = get_policy_config(db)
    pre, post = a.pre_indicators, resp.post_indicators
    if pre.get("topic_id") != post.get("topic_id"):
        raise HTTPException(status_code=422, detail="Pre and post measurements are on different topics")
    try:
        g = rw.learning_gain(pre["topic_score"], post["topic_score"])
    except rw.ComparabilityError as e:
        raise HTTPException(status_code=422, detail=str(e))
    e, e_components = rw.engagement_change(pre["engagement"]["components"], post["engagement"]["components"])
    r, alpha_eff = rw.combined_reward(g, e, cfg["reward_alpha"])
    category = rw.classify(r, cfg["positive_threshold"], cfg["partial_threshold"])

    resp.learning_gain, resp.engagement_change, resp.reward, resp.category = g, e, r, category
    resp.evaluated_at = now()
    resp.evidence = {"pre_score": pre["topic_score"], "post_score": post["topic_score"],
                     "pre_engagement": pre["engagement"]["components"], "post_engagement": post["engagement"]["components"],
                     "engagement_components_compared": e_components,
                     "alpha_configured": cfg["reward_alpha"], "alpha_effective": alpha_eff,
                     "thresholds": {"positive": cfg["positive_threshold"], "partial": cfg["partial_threshold"]},
                     "formula": "g=(post-pre)/(100-pre); e=mean common-component change/100; r=alpha*g+(1-alpha)*e"}
    a.status = "evaluated"

    # Step 1 - POLICY update (new immutable version; previous version kept for audit/restore)
    cur = current_policy_version(db)
    params = load_params(db, cur)
    code = a.intervention_type.code
    x = np.array(a.context["vector"])
    params[code] = params[code].updated(x, r)
    new_pv = models.PolicyVersion(version=cur.version + 1, reason=f"update from intervention #{a.id}",
                                  lam=cur.lam, v=cur.v, dim=cur.dim, feature_names=cur.feature_names,
                                  created_by=user_id)
    db.add(new_pv)
    db.flush()
    types = {t.code: t.id for t in db.query(models.InterventionType).all()}
    for c, p in params.items():
        db.add(models.PolicyParameter(policy_version_id=new_pv.id, intervention_type_id=types[c],
                                      A=p.A.tolist(), b=p.b.tolist(), n_observations=p.n))
    db.add(models.PolicyUpdate(assignment_id=a.id, intervention_type_id=types[code], from_version_id=cur.id,
                               to_version_id=new_pv.id, reward=r, context_vector=x.tolist()))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Policy was already updated for this intervention")
    audit(db, user_id, "policy_update", "policy_versions", new_pv.version,
          {"assignment_id": a.id, "arm": code, "reward": r, "from": cur.version})

    # Step 2 - STUDENT STATE reassessment (separate operation: uses the new follow-up result)
    new_state = estimate_state(db, a.student_id, user_id)
    return {
        "assignment_id": a.id, "intervention": code,
        "learning_gain": round(g, 4), "engagement_change": None if e is None else round(e, 4),
        "reward": round(r, 4), "category": category, "category_label": rw.CATEGORY_LABELS[category],
        "policy_update": {"from_version": cur.version, "to_version": new_pv.version, "arm": code,
                          "arm_observations": params[code].n},
        "state_reassessment": {"state_id": new_state.id, "state": new_state.state,
                               "model_version": new_state.model_version},
    }
