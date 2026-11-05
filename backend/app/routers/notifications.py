"""Notifications and reminders. Derived on request from stored interventions and states - there is no
notification table, so nothing can drift out of sync with the records. Each item has a stable id so the
client can remember which ones the user has already read."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, serializers
from ..database import get_db
from ..engine import service
from ..ml.state_model import STATE_LABELS
from ..security import authorized_student_ids, get_current_user

router = APIRouter(prefix="/api", tags=["notifications"])

MAX_ITEMS = 25
RECENT_RESULTS = 5  # evaluated results kept per student (students) / in total (staff)


def _item(id_, kind, title, body, at, link, action=False):
    return {"id": id_, "kind": kind, "title": title, "body": body, "at": serializers.iso(at), "link": link,
            "action_required": action}


def _topic(a):
    return a.topic.name if a.topic else "General"


def _student_items(db, sid):
    out = []
    rows = db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id == sid).order_by(
        models.InterventionAssignment.assigned_at.desc()).all()
    for a in rows:
        name, link = a.intervention_type.name, f"/interventions/{a.id}"
        if a.status == "assigned":
            note = f" Note from your faculty member: {a.faculty_note}" if a.faculty_note else ""
            out.append(_item(f"assigned-{a.id}", "assigned", f"New activity: {name}",
                             f"Assigned on {_topic(a)}. Open it to get started.{note}", a.assigned_at, link, True))
        elif a.status == "accessed":
            if a.intervention_type.code == "faculty_support":
                body = "Your faculty member will mark this complete after the consultation."
            else:
                body = f"You opened this activity on {_topic(a)}. Finish it to unlock the follow-up assessment."
            out.append(_item(f"pending-{a.id}", "reminder", f"Pending: {name}", body,
                             a.accessed_at or a.assigned_at, link, a.intervention_type.code != "faculty_support"))
        elif a.status == "completed":
            out.append(_item(f"followup-{a.id}", "followup", f"Follow-up assessment due: {_topic(a)}",
                             f"You completed {name}. Record your follow-up score to see how much it helped.",
                             a.completed_at or a.assigned_at, link, True))
    evaluated = [a for a in rows if a.status == "evaluated" and a.response and a.response.category]
    for a in evaluated[:RECENT_RESULTS]:
        r = a.response
        pre, post = (a.pre_indicators or {}).get("topic_score"), (r.post_indicators or {}).get("topic_score")
        change = f" ({round(pre)}% → {round(post)}%)" if pre is not None and post is not None else ""
        label = {"positive": "Positive", "partial": "Partial", "no_improvement": "No Improvement"}[r.category]
        out.append(_item(f"result-{a.id}", "result", f"Result: {label}",
                         f"{a.intervention_type.name} on {_topic(a)}{change}.", r.evaluated_at or r.submitted_at, link))
    states = db.query(models.StudentState).filter(models.StudentState.student_id == sid).order_by(
        models.StudentState.created_at.desc()).limit(2).all()
    if len(states) == 2 and states[0].state != states[1].state:
        cur, prev = states
        out.append(_item(f"state-{cur.id}", "state", f"Academic state updated: {STATE_LABELS[cur.state]}",
                         f"Changed from {STATE_LABELS[prev.state]} after your latest records.", cur.created_at,
                         "/student"))
    return out


def _staff_items(db, ids):
    out = []
    if not ids:
        return out
    names = {sp.id: sp.user.full_name for sp in
             db.query(models.StudentProfile).filter(models.StudentProfile.id.in_(ids)).all()}
    for sid in ids:
        st = service.latest_state(db, sid)
        streak, _ = service.no_improvement_streak(db, sid)
        if streak >= 2:
            out.append(_item(f"streak-{sid}-{streak}", "review", f"{names[sid]} needs review",
                             f"{streak} interventions in a row showed no improvement. Faculty support is now eligible.",
                             st.created_at if st else None, f"/students/{sid}", True))
        elif st and st.state == "high_support_need":
            out.append(_item(f"high-{st.id}", "review", f"{names[sid]} needs review",
                             "Estimated state is High Support Need.", st.created_at, f"/students/{sid}", True))
    open_rows = db.query(models.InterventionAssignment).filter(
        models.InterventionAssignment.student_id.in_(ids),
        models.InterventionAssignment.status.in_(service.OPEN_STATUSES)).all()
    for a in open_rows:
        who, link = names[a.student_id], f"/interventions/{a.id}"
        if a.intervention_type.code == "faculty_support" and a.status != "completed":
            out.append(_item(f"consult-{a.id}", "assigned", f"Consultation pending: {who}",
                             "Mark the faculty support session as held once it has taken place.",
                             a.assigned_at, link, True))
        elif a.status == "completed":
            out.append(_item(f"followup-{a.id}", "followup", f"Awaiting follow-up: {who}",
                             f"Completed {a.intervention_type.name} on {_topic(a)}; the follow-up score is not recorded yet.",
                             a.completed_at or a.assigned_at, link))
    recent = db.query(models.InterventionAssignment).join(models.InterventionResponse).filter(
        models.InterventionAssignment.student_id.in_(ids), models.InterventionResponse.category.isnot(None)).order_by(
        models.InterventionResponse.evaluated_at.desc()).limit(RECENT_RESULTS).all()
    for a in recent:
        label = {"positive": "Positive", "partial": "Partial", "no_improvement": "No Improvement"}[a.response.category]
        out.append(_item(f"result-{a.id}", "result", f"{names[a.student_id]}: {label}",
                         f"{a.intervention_type.name} on {_topic(a)}.",
                         a.response.evaluated_at or a.response.submitted_at, f"/interventions/{a.id}"))
    return out


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Newest first; items that need the user to do something are flagged with action_required."""
    if user.role == "student":
        items = _student_items(db, user.student_profile.id) if user.student_profile else []
    else:
        allowed = authorized_student_ids(db, user)
        if allowed is None:
            allowed = [r[0] for r in db.query(models.StudentProfile.id).all()]
        items = _staff_items(db, allowed)
    items.sort(key=lambda i: i["at"] or "", reverse=True)
    return items[:MAX_ITEMS]
