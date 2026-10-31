from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, serializers
from ..database import get_db
from ..engine import service
from ..ml.features import compute_indicators
from ..security import authorized_student_ids, ensure_student_access, get_current_user, require_roles

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("")
def list_students(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Students the caller may see (student: self; faculty: assigned; admin: all) with latest state."""
    allowed = authorized_student_ids(db, user)
    q = db.query(models.StudentProfile)
    if allowed is not None:
        q = q.filter(models.StudentProfile.id.in_(allowed or [-1]))
    out = []
    for sp in q.order_by(models.StudentProfile.roll_number).all():
        st = service.latest_state(db, sp.id)
        streak, _ = service.no_improvement_streak(db, sp.id)
        open_a = service.open_assignment(db, sp.id)
        out.append({**serializers.student(sp), "state": serializers.state(st),
                    "no_improvement_streak": streak,
                    "open_intervention": serializers.assignment(open_a) if open_a else None})
    return out


@router.get("/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    sp = ensure_student_access(db, user, student_id)
    ind = compute_indicators(db, student_id)
    streak, _ = service.no_improvement_streak(db, student_id)
    open_a = service.open_assignment(db, student_id)
    st = service.latest_state(db, student_id)
    return {**serializers.student(sp), "indicators": ind["features"], "per_topic": ind["per_topic"],
            "state": serializers.state(st), "state_is_stale": service.state_is_stale(db, student_id, st),
            "no_improvement_streak": streak,
            "open_intervention": serializers.assignment(open_a, detail=True) if open_a else None}


@router.get("/{student_id}/state")
def get_state(student_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ensure_student_access(db, user, student_id)
    return serializers.state(service.latest_state(db, student_id))


@router.post("/{student_id}/predict-state")
def predict(student_id: int, db: Session = Depends(get_db),
            user: models.User = Depends(require_roles("faculty", "admin"))):
    """Run Random Forest inference on the student's current records and store the result."""
    ensure_student_access(db, user, student_id)
    st = service.estimate_state(db, student_id, user.id)
    db.commit()
    return serializers.state(st)


@router.get("/{student_id}/interventions")
def history(student_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ensure_student_access(db, user, student_id)
    rows = db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id == student_id).order_by(
        models.InterventionAssignment.assigned_at.desc()).all()
    return [serializers.assignment(a) for a in rows]


@router.get("/{student_id}/progress")
def progress(student_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ensure_student_access(db, user, student_id)
    results = db.query(models.StudentAssessmentResult).filter(
        models.StudentAssessmentResult.student_id == student_id).order_by(
        models.StudentAssessmentResult.recorded_at).all()
    states = db.query(models.StudentState).filter(models.StudentState.student_id == student_id).order_by(
        models.StudentState.created_at).all()
    asg = db.query(models.StudentAssignmentRecord, models.Assignment).join(
        models.Assignment, models.Assignment.id == models.StudentAssignmentRecord.assignment_id).filter(
        models.StudentAssignmentRecord.student_id == student_id).order_by(models.Assignment.due_date).all()
    done = 0
    completion = []
    for i, (rec, a) in enumerate(asg, 1):
        done += rec.status in ("submitted", "late")
        completion.append({"assignment": a.title, "due_date": a.due_date.isoformat(), "status": rec.status,
                           "cumulative_completion_pct": round(100 * done / i, 1)})
    level = {"normal": 0, "attention_needed": 1, "high_support_need": 2}
    evaluated = db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id == student_id,
        models.InterventionAssignment.status == "evaluated").order_by(models.InterventionAssignment.assigned_at).all()
    return {
        "assessments": [{"date": serializers.iso(r.recorded_at), "title": r.assessment.title,
                         "kind": r.assessment.kind, "topic_id": r.assessment.topic_id,
                         "score_pct": r.score_pct} for r in results],
        "states": [{"date": serializers.iso(s.created_at), "state": s.state, "level": level[s.state]} for s in states],
        "assignments": completion,
        "interventions": [{"id": a.id, "date": serializers.iso(a.assigned_at), "intervention": a.intervention_type.code,
                           "pre": a.pre_indicators.get("topic_score"),
                           "post": a.response.post_indicators.get("topic_score"),
                           "reward": a.response.reward, "category": a.response.category} for a in evaluated],
    }
