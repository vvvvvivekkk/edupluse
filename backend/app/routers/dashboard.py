"""Dashboard + analytics data. Every number is computed from stored rows - nothing is hard-coded."""
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..engine import service
from ..security import authorized_student_ids, get_current_user

router = APIRouter(prefix="/api", tags=["dashboard"])

MIN_OBS_FOR_COMPARISON = 30  # per intervention type, before any effectiveness comparison is shown


def _scope(db, user):
    allowed = authorized_student_ids(db, user)
    q = db.query(models.StudentProfile.id)
    if allowed is not None:
        q = q.filter(models.StudentProfile.id.in_(allowed or [-1]))
    return [r[0] for r in q.all()]


@router.get("/dashboard/summary")
def summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ids = _scope(db, user)
    states = Counter()
    needs_review, repeated = [], []
    for sid in ids:
        st = service.latest_state(db, sid)
        states[st.state if st else "not_assessed"] += 1
        streak, _ = service.no_improvement_streak(db, sid)
        sp = db.get(models.StudentProfile, sid)
        if (st and st.state == "high_support_need") or streak >= 2:
            needs_review.append({"student_id": sid, "name": sp.user.full_name, "roll_number": sp.roll_number,
                                 "state": st.state if st else None, "no_improvement_streak": streak})
        if streak >= 2:
            repeated.append(sid)
    ia = db.query(models.InterventionAssignment).filter(models.InterventionAssignment.student_id.in_(ids or [-1]))
    status = Counter(a.status for a in ia)
    cats = Counter(a.response.category for a in ia if a.response and a.response.category)
    by_type = Counter(a.intervention_type.code for a in ia)
    out = {
        "role": user.role, "student_count": len(ids), "state_distribution": dict(states),
        "intervention_status": dict(status), "response_categories": dict(cats),
        "interventions_by_type": dict(by_type), "students_needing_review": needs_review,
        "repeated_no_improvement_count": len(repeated),
        "pending_faculty_support": [
            {"assignment_id": a.id, "student_id": a.student_id, "status": a.status}
            for a in ia if a.intervention_type.code == "faculty_support" and a.status in service.OPEN_STATUSES],
    }
    if user.role == "admin":
        out["admin"] = {
            "users_total": db.query(func.count(models.User.id)).scalar(),
            "users_by_role": dict(db.query(models.User.role, func.count(models.User.id)).group_by(models.User.role).all()),
            "policy_version": service.current_policy_version(db).version,
            "policy_updates": db.query(func.count(models.PolicyUpdate.id)).scalar(),
            "audit_events": db.query(func.count(models.AuditLog.id)).scalar(),
            "recent_activity": [{"action": a.action, "entity": a.entity, "entity_id": a.entity_id,
                                 "user_id": a.user_id, "at": a.created_at.isoformat()}
                                for a in db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(15)],
        }
    return out


@router.get("/analytics")
def analytics(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ids = _scope(db, user)
    rows = db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id.in_(ids or [-1])).order_by(models.InterventionAssignment.assigned_at).all()
    by_day = defaultdict(lambda: Counter())
    per_type = defaultdict(list)
    for a in rows:
        d = a.assigned_at.date().isoformat()
        by_day[d]["assigned"] += 1
        if a.response and a.response.category:
            by_day[d][a.response.category] += 1
            per_type[a.intervention_type.code].append(a.response.reward)
    outcomes_over_time = [{"date": d, **c} for d, c in sorted(by_day.items())]
    type_summary = []
    for code, rewards in per_type.items():
        enough = len(rewards) >= MIN_OBS_FOR_COMPARISON
        type_summary.append({"intervention": code, "n_evaluated": len(rewards),
                             "mean_reward": round(sum(rewards) / len(rewards), 4) if enough else None,
                             "sufficient_data": enough})
    # assessment score change per evaluated intervention
    changes = [{"assignment_id": a.id, "intervention": a.intervention_type.code,
                "pre": a.pre_indicators.get("topic_score"), "post": a.response.post_indicators.get("topic_score")}
               for a in rows if a.status == "evaluated"]
    # average assessment score over time (all results in scope)
    res = db.query(models.StudentAssessmentResult).filter(
        models.StudentAssessmentResult.student_id.in_(ids or [-1])).all()
    score_by_day = defaultdict(list)
    for r in res:
        score_by_day[r.recorded_at.date().isoformat()].append(r.score_pct)
    asg = db.query(models.StudentAssignmentRecord).filter(
        models.StudentAssignmentRecord.student_id.in_(ids or [-1])).all()
    return {
        "outcomes_over_time": outcomes_over_time,
        "intervention_counts": dict(Counter(a.intervention_type.code for a in rows)),
        "response_categories": dict(Counter(a.response.category for a in rows if a.response and a.response.category)),
        "score_changes": changes,
        "avg_score_over_time": [{"date": d, "avg_score": round(sum(v) / len(v), 1), "n": len(v)}
                                for d, v in sorted(score_by_day.items())],
        "assignment_status": dict(Counter(a.status for a in asg)),
        "type_summary": type_summary,
        "comparison_note": (f"Effectiveness is only summarised for intervention types with at least "
                            f"{MIN_OBS_FOR_COMPARISON} evaluated outcomes. Even then it is descriptive, "
                            "not causal evidence."),
    }
