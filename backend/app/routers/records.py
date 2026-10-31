"""Academic-record entry (admin, or faculty for their assigned students). Records are validated;
missing values are rejected, never coerced to zero."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import ensure_student_access, get_current_user, require_roles
from ..services_common import audit

router = APIRouter(prefix="/api", tags=["academic records"])


class AcademicRecordIn(BaseModel):
    student_id: int
    record_type: Literal["assessment_result", "attendance", "assignment", "practice"]
    # assessment_result
    assessment_title: str | None = None
    topic_id: int | None = None
    raw_score: float | None = Field(None, ge=0)
    max_score: float | None = Field(None, gt=0)
    # attendance
    period_start: date | None = None
    period_end: date | None = None
    sessions_attended: int | None = Field(None, ge=0)
    sessions_total: int | None = Field(None, gt=0)
    # assignment
    assignment_id: int | None = None
    status: Literal["submitted", "late", "missing"] | None = None
    # practice
    questions_attempted: int | None = Field(None, gt=0)
    questions_correct: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def check_required(self):
        need = {
            "assessment_result": ["assessment_title", "topic_id", "raw_score", "max_score"],
            "attendance": ["period_start", "period_end", "sessions_attended", "sessions_total"],
            "assignment": ["assignment_id", "status"],
            "practice": ["topic_id", "questions_attempted", "questions_correct"],
        }[self.record_type]
        missing = [f for f in need if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Missing required fields for {self.record_type}: {', '.join(missing)}")
        if self.record_type == "assessment_result" and self.raw_score > self.max_score:
            raise ValueError("raw_score cannot exceed max_score")
        if self.record_type == "attendance":
            if self.sessions_attended > self.sessions_total:
                raise ValueError("sessions_attended cannot exceed sessions_total")
            if self.period_end < self.period_start:
                raise ValueError("period_end must be on or after period_start")
        if self.record_type == "practice" and self.questions_correct > self.questions_attempted:
            raise ValueError("questions_correct cannot exceed questions_attempted")
        return self


@router.post("/academic-records", status_code=201)
def create_record(body: AcademicRecordIn, db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles("faculty", "admin"))):
    ensure_student_access(db, user, body.student_id)
    if body.topic_id is not None and not db.get(models.Topic, body.topic_id):
        raise HTTPException(status_code=422, detail="Unknown topic_id")
    t = body.record_type
    if t == "assessment_result":
        a = models.Assessment(title=body.assessment_title, topic_id=body.topic_id, kind="quiz",
                              max_score=body.max_score)
        db.add(a)
        db.flush()
        row = models.StudentAssessmentResult(student_id=body.student_id, assessment_id=a.id, raw_score=body.raw_score,
                                             score_pct=round(100 * body.raw_score / body.max_score, 2),
                                             recorded_by=user.id)
    elif t == "attendance":
        row = models.AttendanceRecord(student_id=body.student_id, period_start=body.period_start,
                                      period_end=body.period_end, sessions_attended=body.sessions_attended,
                                      sessions_total=body.sessions_total)
    elif t == "assignment":
        if not db.get(models.Assignment, body.assignment_id):
            raise HTTPException(status_code=422, detail="Unknown assignment_id")
        row = models.StudentAssignmentRecord(student_id=body.student_id, assignment_id=body.assignment_id,
                                             status=body.status)
    else:
        row = models.LearningActivityRecord(student_id=body.student_id, topic_id=body.topic_id,
                                            questions_attempted=body.questions_attempted,
                                            questions_correct=body.questions_correct)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This record already exists (e.g. assignment already recorded)")
    audit(db, user.id, "create_academic_record", t, row.id, body.model_dump(mode="json", exclude_none=True))
    db.commit()
    return {"id": row.id, "record_type": t,
            "note": "State may now be stale; it will be re-estimated before the next selection."}


@router.get("/topics")
def topics(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [{"id": t.id, "name": t.name, "course": t.course} for t in db.query(models.Topic).order_by(models.Topic.id)]


@router.get("/assignments")
def assignments(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [{"id": a.id, "title": a.title, "topic_id": a.topic_id, "due_date": a.due_date.isoformat()}
            for a in db.query(models.Assignment).order_by(models.Assignment.due_date)]
