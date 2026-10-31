"""Feature construction from stored academic records.

All features are on a 0-100 percentage scale so they are comparable across sources.
Missing data are returned as None (never silently turned into 0). The model pipeline
imputes them with the training median AND adds a missing-indicator column, and the
prediction record lists which features were imputed.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models

FEATURE_NAMES = [
    "latest_score",               # most recent assessment, %
    "avg_score",                  # mean of all assessments, %
    "attendance_pct",             # sessions attended / total, %
    "assignment_completion_pct",  # submitted (or late) / recorded assignments, %
    "practice_accuracy_pct",      # correct / attempted practice questions, %
    "previous_result_pct",        # previous academic result, %
]
REQUIRED_FEATURES = ["latest_score"]

FEATURE_LABELS = {
    "latest_score": "Latest assessment score",
    "avg_score": "Average assessment score",
    "attendance_pct": "Attendance",
    "assignment_completion_pct": "Assignment completion",
    "practice_accuracy_pct": "Practice accuracy",
    "previous_result_pct": "Previous academic result",
}


class FeatureValidationError(ValueError):
    pass


def _pct(n, d):
    return round(100.0 * n / d, 2) if d else None


def compute_indicators(db: Session, student_id: int, until: datetime | None = None) -> dict:
    """Return raw indicators + per-topic breakdown for one student (optionally as of a time)."""
    def before(q, col):
        return q.filter(col <= until) if until else q

    student = db.get(models.StudentProfile, student_id)
    results = before(db.query(models.StudentAssessmentResult).filter(
        models.StudentAssessmentResult.student_id == student_id),
        models.StudentAssessmentResult.recorded_at).order_by(
        models.StudentAssessmentResult.recorded_at).all()
    att = before(db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.student_id == student_id), models.AttendanceRecord.recorded_at).all()
    asg = before(db.query(models.StudentAssignmentRecord).filter(
        models.StudentAssignmentRecord.student_id == student_id),
        models.StudentAssignmentRecord.recorded_at).all()
    prac = before(db.query(models.LearningActivityRecord).filter(
        models.LearningActivityRecord.student_id == student_id),
        models.LearningActivityRecord.recorded_at).all()

    # per-topic mastery: latest score per topic and practice accuracy per topic
    topic_scores: dict[int, list[float]] = {}
    for r in results:
        topic_scores.setdefault(r.assessment.topic_id, []).append(r.score_pct)
    topic_practice: dict[int, list[int]] = {}
    for p in prac:
        t = topic_practice.setdefault(p.topic_id, [0, 0])
        t[0] += p.questions_correct
        t[1] += p.questions_attempted
    topics = {t.id: t.name for t in db.query(models.Topic).all()}
    per_topic = []
    for tid in set(topic_scores) | set(topic_practice):
        scores = topic_scores.get(tid, [])
        pr = topic_practice.get(tid)
        per_topic.append({
            "topic_id": tid, "topic": topics.get(tid, str(tid)),
            "latest_score": scores[-1] if scores else None,
            "practice_accuracy_pct": _pct(pr[0], pr[1]) if pr else None,
        })

    indicators = {
        "latest_score": results[-1].score_pct if results else None,
        "avg_score": round(sum(r.score_pct for r in results) / len(results), 2) if results else None,
        "attendance_pct": _pct(sum(a.sessions_attended for a in att), sum(a.sessions_total for a in att)),
        "assignment_completion_pct": _pct(sum(1 for a in asg if a.status in ("submitted", "late")), len(asg)),
        "practice_accuracy_pct": _pct(sum(p.questions_correct for p in prac),
                                      sum(p.questions_attempted for p in prac)),
        "previous_result_pct": student.previous_result_pct if student else None,
    }
    return {"features": indicators, "per_topic": per_topic,
            "latest_topic_id": results[-1].assessment.topic_id if results else None}


def validate_features(features: dict) -> list[str]:
    """Raise if required data are missing or out of range; return list of missing optional features."""
    for name in REQUIRED_FEATURES:
        if features.get(name) is None:
            raise FeatureValidationError(
                f"Cannot estimate state: required indicator '{FEATURE_LABELS[name]}' is missing. "
                "Record at least one assessment result first.")
    missing = []
    for name in FEATURE_NAMES:
        v = features.get(name)
        if v is None:
            missing.append(name)
            continue
        if not isinstance(v, (int, float)) or v != v or not 0 <= v <= 100:
            raise FeatureValidationError(f"Indicator '{name}' has invalid value {v!r} (expected 0-100)")
    return missing


PRACTICE_SESSIONS_TARGET_PER_WEEK = 2


def engagement_index(db: Session, student_id: int, start: datetime, end: datetime,
                     window_days: int = 14) -> dict:
    """Engagement components over a window (each 0-100, None if no data in the window):
      attendance_pct            sessions attended / total
      assignment_completion_pct submitted-or-late / recorded
      practice_activity_pct     min(100, 100 * sessions / (2 per week * window_days/7))
    The practice rate is normalised by the nominal observation window length (not elapsed
    time), so a short or long elapsed period does not distort the rate.
    `index` = mean of available components (for display). The reward uses only components
    available in BOTH the pre and post windows (see reward.engagement_change)."""
    def win(q, col):
        return q.filter(col >= start, col <= end)

    att = win(db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.student_id == student_id), models.AttendanceRecord.recorded_at).all()
    asg = win(db.query(models.StudentAssignmentRecord).filter(
        models.StudentAssignmentRecord.student_id == student_id),
        models.StudentAssignmentRecord.recorded_at).all()
    prac = win(db.query(models.LearningActivityRecord).filter(
        models.LearningActivityRecord.student_id == student_id),
        models.LearningActivityRecord.recorded_at).all()
    parts = {
        "attendance_pct": _pct(sum(a.sessions_attended for a in att), sum(a.sessions_total for a in att)),
        "assignment_completion_pct": _pct(sum(1 for a in asg if a.status in ("submitted", "late")), len(asg)),
        "practice_activity_pct": (round(min(100.0, 100.0 * len(prac) /
                                            (PRACTICE_SESSIONS_TARGET_PER_WEEK * window_days / 7.0)), 2)
                                  if prac else None),
    }
    vals = [v for v in parts.values() if v is not None]
    return {"components": parts, "index": round(sum(vals) / len(vals), 2) if vals else None,
            "window_start": start.isoformat(), "window_end": end.isoformat()}


def window_before(t: datetime, days: int):
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t - timedelta(days=days), t
