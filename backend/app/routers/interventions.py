from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, serializers
from ..database import get_db
from ..engine import service
from ..security import ensure_student_access, get_current_user, require_roles

router = APIRouter(prefix="/api/interventions", tags=["interventions"])


class SelectIn(BaseModel):
    student_id: int
    seed: int | None = Field(None, description="Optional RNG seed, to reproduce a selection exactly")


class AssignIn(BaseModel):
    student_id: int
    intervention: str = "faculty_support"
    note: str | None = None


class CompleteIn(BaseModel):
    answers: list[int] | None = None


class ResponseIn(BaseModel):
    post_score: float = Field(..., ge=0, le=100, description="Follow-up assessment score, percent")
    evaluate: bool = Field(True, description="Evaluate and update the policy immediately")


def _get(db: Session, user: models.User, assignment_id: int) -> models.InterventionAssignment:
    a = db.get(models.InterventionAssignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Intervention not found")
    ensure_student_access(db, user, a.student_id)
    return a


@router.get("/types")
def types(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [{"id": t.id, "code": t.code, "name": t.name, "description": t.description, "is_active": t.is_active}
            for t in db.query(models.InterventionType).order_by(models.InterventionType.id)]


@router.post("/select")
def select(body: SelectIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Re-estimate state if stale -> eligibility rules -> linear Thompson sampling -> record assignment."""
    ensure_student_access(db, user, body.student_id)
    result = service.select_intervention(db, body.student_id, user.id, seed=body.seed)
    db.commit()
    return result


@router.post("/assign")
def assign(body: AssignIn, db: Session = Depends(get_db),
           user: models.User = Depends(require_roles("faculty", "admin"))):
    """Faculty-recorded intervention (e.g. consultation). Marked selection_method=faculty_manual."""
    ensure_student_access(db, user, body.student_id)
    a = service.faculty_assign(db, body.student_id, body.intervention, body.note, user.id)
    db.commit()
    return serializers.assignment(a, detail=True)


@router.get("/{assignment_id}")
def detail(assignment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    a = _get(db, user, assignment_id)
    return serializers.assignment(a, detail=True, hide_answers=(user.role == "student" and a.status != "evaluated"))


@router.post("/{assignment_id}/access")
def access(assignment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    a = _get(db, user, assignment_id)
    service.mark_accessed(db, a, user.id)
    db.commit()
    return {"status": a.status}


@router.post("/{assignment_id}/complete")
def complete(assignment_id: int, body: CompleteIn, db: Session = Depends(get_db),
             user: models.User = Depends(get_current_user)):
    a = _get(db, user, assignment_id)
    if a.intervention_type.code == "faculty_support" and user.role == "student":
        raise HTTPException(status_code=403, detail="Faculty support is marked complete by the faculty member")
    out = service.complete(db, a, user.id, body.answers)
    db.commit()
    return out


@router.post("/{assignment_id}/response")
def response(assignment_id: int, body: ResponseIn, db: Session = Depends(get_db),
             user: models.User = Depends(get_current_user)):
    """Record the post-intervention follow-up score (same topic, 0-100). Optionally evaluate at once."""
    a = _get(db, user, assignment_id)
    resp = service.record_response(db, a, body.post_score, user.id)
    out = {"response_id": resp.id, "evaluated": False}
    if body.evaluate:
        out = {"response_id": resp.id, "evaluated": True,
               "evaluation": service.evaluate_response(db, a.id, user.id)}
    db.commit()
    return out


@router.post("/{assignment_id}/evaluate")
def evaluate(assignment_id: int, db: Session = Depends(get_db),
             user: models.User = Depends(require_roles("faculty", "admin"))):
    """Compute reward + category, update the Thompson sampling policy (once), reassess the state."""
    _get(db, user, assignment_id)
    out = service.evaluate_response(db, assignment_id, user.id)
    db.commit()
    return out
