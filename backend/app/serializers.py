"""Convert ORM rows to JSON-friendly dicts for API responses."""
from . import models
from .engine.reward import CATEGORY_LABELS
from .ml.state_model import STATE_LABELS


def iso(dt):
    return dt.isoformat() if dt else None


def user(u: models.User) -> dict:
    d = {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
         "created_at": iso(u.created_at)}
    if u.student_profile:
        d["student_id"] = u.student_profile.id
    if u.faculty_profile:
        d["faculty_id"] = u.faculty_profile.id
    return d


def state(s: models.StudentState | None) -> dict | None:
    if s is None:
        return None
    return {"id": s.id, "student_id": s.student_id, "state": s.state, "state_label": STATE_LABELS[s.state],
            "features": s.features, "imputed_features": s.imputed_features, "probabilities": s.probabilities,
            "explanation": s.explanation, "model_version": s.model_version, "created_at": iso(s.created_at)}


def student(sp: models.StudentProfile) -> dict:
    return {"id": sp.id, "user_id": sp.user_id, "name": sp.user.full_name, "email": sp.user.email,
            "roll_number": sp.roll_number, "program": sp.program, "year": sp.year,
            "previous_result_pct": sp.previous_result_pct}


def resource(r: models.LearningResource | None, hide_answers=True) -> dict | None:
    if r is None:
        return None
    content = dict(r.content or {})
    if hide_answers and "questions" in content:
        content["questions"] = [{"q": q["q"], "options": q["options"]} for q in content["questions"]]
    return {"id": r.id, "title": r.title, "objective": r.objective, "instructions": r.instructions,
            "url": r.url, "content": content, "topic_id": r.topic_id,
            "intervention_type": r.intervention_type.code if r.intervention_type else None,
            "is_active": r.is_active}


def response(resp: models.InterventionResponse | None) -> dict | None:
    if resp is None:
        return None
    return {"id": resp.id, "post_indicators": resp.post_indicators, "submitted_at": iso(resp.submitted_at),
            "learning_gain": resp.learning_gain, "engagement_change": resp.engagement_change,
            "reward": resp.reward, "category": resp.category,
            "category_label": CATEGORY_LABELS.get(resp.category) if resp.category else None,
            "evidence": resp.evidence, "evaluated_at": iso(resp.evaluated_at)}


def assignment(a: models.InterventionAssignment, detail=False, hide_answers=True) -> dict:
    reasons = (a.eligibility_reasons or {}).get("reasons", {})
    d = {"id": a.id, "student_id": a.student_id, "intervention": a.intervention_type.code,
         "intervention_name": a.intervention_type.name, "topic_id": a.topic_id,
         "topic": a.topic.name if a.topic else None, "status": a.status,
         "selection_method": a.selection_method, "assigned_at": iso(a.assigned_at),
         "accessed_at": iso(a.accessed_at), "completed_at": iso(a.completed_at),
         "eligible": a.eligible, "reason": reasons.get(a.intervention_type.code, []),
         "pre_score": (a.pre_indicators or {}).get("topic_score"),
         "post_score": (a.response.post_indicators or {}).get("topic_score") if a.response else None,
         "category": a.response.category if a.response else None,
         "category_label": CATEGORY_LABELS.get(a.response.category) if a.response and a.response.category else None,
         "reward": a.response.reward if a.response else None,
         "policy_version_id": a.policy_version_id, "faculty_note": a.faculty_note}
    if detail:
        d.update({"context": a.context, "eligibility": a.eligibility_reasons, "sampled_scores": a.sampled_scores,
                  "rng_seed": a.rng_seed, "pre_indicators": a.pre_indicators,
                  "resource": resource(a.resource, hide_answers), "response": response(a.response),
                  "description": a.intervention_type.description})
    return d
