"""Academic-record entry, bulk CSV import and audited correction (admin, or faculty for their
assigned students). Records are validated; missing values are rejected, never coerced to zero.

Records that are evidence for an evaluated intervention (follow-up assessments, practice attempts
made inside an intervention) cannot be corrected here: changing them would silently alter a
historical intervention result."""
import csv
import io
from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..engine import service
from ..security import authorized_student_ids, ensure_student_access, get_current_user, require_roles
from ..serializers import iso
from ..services_common import audit

router = APIRouter(prefix="/api", tags=["academic records"])

RecordType = Literal["assessment_result", "attendance", "assignment", "practice"]
IMPORT_MAX_BYTES = 1_000_000
IMPORT_MAX_ROWS = 2000
IMPORT_COLUMNS = ["roll_number", "record_type", "assessment_title", "topic", "raw_score", "max_score",
                  "period_start", "period_end", "sessions_attended", "sessions_total", "assignment", "status",
                  "questions_attempted", "questions_correct"]


class AcademicRecordIn(BaseModel):
    student_id: int
    record_type: RecordType
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


class RecordCorrectionIn(BaseModel):
    """Only the measured values can be corrected; who/what the record is about cannot."""
    reason: str = Field(min_length=3, description="Why the record is being corrected (stored in the audit log)")
    raw_score: float | None = Field(None, ge=0)
    period_start: date | None = None
    period_end: date | None = None
    sessions_attended: int | None = Field(None, ge=0)
    sessions_total: int | None = Field(None, gt=0)
    status: Literal["submitted", "late", "missing"] | None = None
    questions_attempted: int | None = Field(None, gt=0)
    questions_correct: int | None = Field(None, ge=0)


CORRECTABLE = {
    "assessment_result": ["raw_score"],
    "attendance": ["period_start", "period_end", "sessions_attended", "sessions_total"],
    "assignment": ["status"],
    "practice": ["questions_attempted", "questions_correct"],
}
RECORD_MODELS = {
    "assessment_result": models.StudentAssessmentResult,
    "attendance": models.AttendanceRecord,
    "assignment": models.StudentAssignmentRecord,
    "practice": models.LearningActivityRecord,
}


def _validation_message(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, err['loc'])) + ': ' if err['loc'] else ''}"
                     f"{err['msg'].replace('Value error, ', '')}" for err in e.errors())


def _insert_record(db: Session, body: AcademicRecordIn, user: models.User):
    """Validate references and add one record (flushed, not committed). Returns the new row."""
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
    db.flush()
    return row


@router.post("/academic-records", status_code=201)
def create_record(body: AcademicRecordIn, db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles("faculty", "admin"))):
    ensure_student_access(db, user, body.student_id)
    try:
        row = _insert_record(db, body, user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This record already exists (e.g. assignment already recorded)")
    audit(db, user.id, "create_academic_record", body.record_type, row.id,
          body.model_dump(mode="json", exclude_none=True))
    db.commit()
    return {"id": row.id, "record_type": body.record_type,
            "note": "State may now be stale; it will be re-estimated before the next selection."}


# ------------------------------------------------------------------ bulk import
def _parse_import(db: Session, user: models.User, text: str) -> tuple[list[AcademicRecordIn], list[dict]]:
    """Validate every CSV row. Returns (valid records, errors); row numbers count the header as row 1."""
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in (reader.fieldnames or [])]
    if "record_type" not in header or not ({"roll_number", "student_id"} & set(header)):
        raise HTTPException(status_code=422, detail=(
            "CSV header must contain record_type and roll_number (or student_id). "
            f"Supported columns: {', '.join(IMPORT_COLUMNS)}"))
    reader.fieldnames = header
    allowed = authorized_student_ids(db, user)
    by_roll = {sp.roll_number.lower(): sp.id for sp in db.query(models.StudentProfile)}
    student_ids = set(by_roll.values())
    topics = {t.name.lower(): t.id for t in db.query(models.Topic)}
    topic_ids = set(topics.values())
    assignments = {a.title.lower(): a.id for a in db.query(models.Assignment)}
    assignment_ids = set(assignments.values())
    existing_asg = {(r.student_id, r.assignment_id) for r in db.query(models.StudentAssignmentRecord)}

    def lookup(value, by_name, ids, what):
        if value.isdigit() and int(value) in ids:
            return int(value)
        if value.lower() in by_name:
            return by_name[value.lower()]
        raise ValueError(f"unknown {what} '{value}'")

    records, errors = [], []
    for n, raw in enumerate(reader, start=2):
        if n - 1 > IMPORT_MAX_ROWS:
            raise HTTPException(status_code=413, detail=f"At most {IMPORT_MAX_ROWS} rows per import")
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if not any(row.values()):
            continue  # blank line
        try:
            data = {k: v for k, v in row.items() if v and k not in ("roll_number", "topic", "assignment")}
            if row.get("roll_number"):
                if row["roll_number"].lower() not in by_roll:
                    raise ValueError(f"unknown roll_number '{row['roll_number']}'")
                data["student_id"] = by_roll[row["roll_number"].lower()]
            elif row.get("student_id") and not (row["student_id"].isdigit() and int(row["student_id"]) in student_ids):
                raise ValueError(f"unknown student_id '{row['student_id']}'")
            if row.get("topic"):
                data["topic_id"] = lookup(row["topic"], topics, topic_ids, "topic")
            if row.get("assignment"):
                data["assignment_id"] = lookup(row["assignment"], assignments, assignment_ids, "assignment")
            rec = AcademicRecordIn(**data)
            if allowed is not None and rec.student_id not in allowed:
                raise ValueError("you are not authorised to add records for this student")
            if rec.topic_id is not None and rec.topic_id not in topic_ids:
                raise ValueError(f"unknown topic_id {rec.topic_id}")
            if rec.record_type == "assignment":
                if rec.assignment_id not in assignment_ids:
                    raise ValueError(f"unknown assignment_id {rec.assignment_id}")
                key = (rec.student_id, rec.assignment_id)
                if key in existing_asg:
                    raise ValueError("this assignment is already recorded for the student")
                existing_asg.add(key)
            records.append(rec)
        except ValidationError as e:
            errors.append({"row": n, "error": _validation_message(e)})
        except ValueError as e:
            errors.append({"row": n, "error": str(e)})
    return records, errors


@router.post("/academic-records/import")
async def import_records(file: UploadFile = File(..., description="CSV file, UTF-8, one record per row"),
                         dry_run: bool = Query(False, description="Validate only; store nothing"),
                         db: Session = Depends(get_db),
                         user: models.User = Depends(require_roles("faculty", "admin"))):
    """Bulk-import academic records from CSV. All-or-nothing: if any row is invalid, nothing is stored
    and every row error is reported. Columns: roll_number (or student_id), record_type, then the fields
    of that record type; `topic` and `assignment` accept a name/title or an id."""
    content = await file.read(IMPORT_MAX_BYTES + 1)
    if len(content) > IMPORT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV file is larger than 1 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV file must be UTF-8 encoded")
    records, errors = _parse_import(db, user, text)
    summary = {"rows": len(records) + len(errors), "valid": len(records), "errors": errors,
               "by_type": dict(Counter(r.record_type for r in records)),
               "students": len({r.student_id for r in records})}
    if dry_run:
        return {"dry_run": True, "imported": 0, **summary}
    if errors:
        raise HTTPException(status_code=422, detail=[
            {"loc": ["row", e["row"]], "msg": f"Row {e['row']}: {e['error']}", "type": "import"} for e in errors])
    if not records:
        raise HTTPException(status_code=422, detail="The CSV file contains no records")
    try:
        ids = [_insert_record(db, r, user).id for r in records]
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A record in the file already exists; nothing was imported")
    audit(db, user.id, "import_academic_records", "academic_records", None,
          {"filename": file.filename, "count": len(ids), "by_type": summary["by_type"],
           "student_ids": sorted({r.student_id for r in records})})
    db.commit()
    return {"dry_run": False, "imported": len(ids), **summary,
            "note": "Affected students' states will be re-estimated before their next selection."}


# ------------------------------------------------------------------ listing and correction
def _locked(record_type: str, row) -> bool:
    if record_type == "assessment_result":
        return row.assessment.kind == "follow_up"
    if record_type == "practice":
        return row.intervention_assignment_id is not None
    return False


def _record_out(record_type: str, row, titles: dict) -> dict:
    d = {"record_type": record_type, "id": row.id, "student_id": row.student_id,
         "recorded_at": iso(row.recorded_at), "locked": _locked(record_type, row)}
    if record_type == "assessment_result":
        d.update(title=row.assessment.title, kind=row.assessment.kind, topic_id=row.assessment.topic_id,
                 raw_score=row.raw_score, max_score=row.assessment.max_score, score_pct=row.score_pct)
    elif record_type == "attendance":
        d.update(period_start=row.period_start.isoformat(), period_end=row.period_end.isoformat(),
                 sessions_attended=row.sessions_attended, sessions_total=row.sessions_total)
    elif record_type == "assignment":
        d.update(assignment_id=row.assignment_id, title=titles.get(row.assignment_id), status=row.status)
    else:
        d.update(topic_id=row.topic_id, activity_type=row.activity_type,
                 questions_attempted=row.questions_attempted, questions_correct=row.questions_correct,
                 intervention_assignment_id=row.intervention_assignment_id)
    return d


@router.get("/students/{student_id}/academic-records")
def list_records(student_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """All stored academic records of one student, newest first. `locked` records are evidence for an
    intervention result and cannot be corrected."""
    ensure_student_access(db, user, student_id)
    titles = {a.id: a.title for a in db.query(models.Assignment)}
    out = []
    for rt, model in RECORD_MODELS.items():
        for row in db.query(model).filter(model.student_id == student_id):
            out.append(_record_out(rt, row, titles))
    return sorted(out, key=lambda r: (r["recorded_at"] or "", r["id"]), reverse=True)


@router.patch("/academic-records/{record_type}/{record_id}")
def correct_record(record_type: RecordType, record_id: int, body: RecordCorrectionIn,
                   db: Session = Depends(get_db), user: models.User = Depends(require_roles("faculty", "admin"))):
    """Correct a mistaken academic record. The reason and before/after values go to the audit log, and
    the student's state is re-estimated from the corrected data (a new, separate state row)."""
    row = db.get(RECORD_MODELS[record_type], record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    ensure_student_access(db, user, row.student_id)
    if _locked(record_type, row):
        raise HTTPException(status_code=409, detail=(
            "This record is evidence for an intervention result and cannot be changed; "
            "historical intervention outcomes are preserved as recorded."))
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    not_allowed = set(changes) - set(CORRECTABLE[record_type])
    if not_allowed:
        raise HTTPException(status_code=422, detail=(
            f"Fields {sorted(not_allowed)} cannot be corrected on a {record_type} record; "
            f"correctable: {CORRECTABLE[record_type]}"))
    if not changes or any(v is None for v in changes.values()):
        raise HTTPException(status_code=422, detail="Provide at least one new value (values cannot be cleared)")
    titles = {a.id: a.title for a in db.query(models.Assignment)}
    before = _record_out(record_type, row, titles)
    current = {"student_id": row.student_id, "record_type": record_type}
    if record_type == "assessment_result":
        current.update(assessment_title=row.assessment.title, topic_id=row.assessment.topic_id,
                       raw_score=row.raw_score, max_score=row.assessment.max_score)
    else:
        current.update({k: getattr(row, k) for k in CORRECTABLE[record_type]})
        if record_type == "assignment":
            current["assignment_id"] = row.assignment_id
        if record_type == "practice":
            current["topic_id"] = row.topic_id
    try:
        AcademicRecordIn(**{**current, **changes})  # same validation rules as a new record
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_validation_message(e))
    for k, v in changes.items():
        setattr(row, k, v)
    if record_type == "assessment_result":
        row.score_pct = round(100 * row.raw_score / row.assessment.max_score, 2)
    db.flush()
    after = _record_out(record_type, row, titles)
    audit(db, user.id, "correct_academic_record", record_type, row.id,
          {"reason": body.reason, "before": before, "after": after})
    reassessed = None
    try:
        reassessed = service.estimate_state(db, row.student_id, user.id).state
    except HTTPException:
        pass  # e.g. no assessment yet: the state cannot be estimated, the correction still stands
    db.commit()
    return {"record": after, "state_reassessed": reassessed}


@router.get("/topics")
def topics(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [{"id": t.id, "name": t.name, "course": t.course} for t in db.query(models.Topic).order_by(models.Topic.id)]


@router.get("/assignments")
def assignments(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [{"id": a.id, "title": a.title, "topic_id": a.topic_id, "due_date": a.due_date.isoformat()}
            for a in db.query(models.Assignment).order_by(models.Assignment.due_date)]
