"""Administrator functions. Historical intervention results are never edited here; policy
re-initialisation creates a NEW version and is audited, old versions remain readable."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, serializers
from ..database import get_db
from ..engine import service
from ..engine.eligibility import RuleConfigError
from ..security import hash_password, require_roles
from ..services_common import audit, get_policy_config, set_policy_config

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_roles("admin")


class UserIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    role: Literal["student", "faculty", "admin"]
    roll_number: str | None = None
    department: str | None = None
    previous_result_pct: float | None = Field(None, ge=0, le=100)


class UserPatch(BaseModel):
    full_name: str | None = Field(None, min_length=1)
    role: Literal["student", "faculty", "admin"] | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8)
    # needed only when the new role requires a profile the user does not have yet
    roll_number: str | None = Field(None, min_length=1)
    department: str | None = None


class AssignStudentIn(BaseModel):
    faculty_id: int
    student_id: int


class TypeIn(BaseModel):
    code: str = Field(pattern=r"^[a-z_]+$")
    name: str
    description: str = ""
    is_active: bool = True


class TypePatch(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    is_active: bool | None = None


class ResourcePatch(BaseModel):
    title: str | None = Field(None, min_length=1)
    objective: str | None = None
    instructions: str | None = None
    url: str | None = None
    content: dict | None = None
    is_active: bool | None = None
    topic_id: int | None = None


class ResourceIn(BaseModel):
    intervention_type: str
    topic_id: int | None = None
    title: str
    objective: str = ""
    instructions: str = ""
    url: str | None = None
    content: dict = {}
    is_active: bool = True


class RulesIn(BaseModel):
    rules: list[dict]


class ReinitIn(BaseModel):
    reason: str = Field(min_length=3)


@router.get("/users")
def users(db: Session = Depends(get_db), _=Depends(admin_only)):
    return [serializers.user(u) for u in db.query(models.User).order_by(models.User.id)]


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), admin=Depends(admin_only)):
    u = models.User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password),
                    role=body.role)
    db.add(u)
    try:
        db.flush()
        if body.role == "student":
            if not body.roll_number:
                raise HTTPException(status_code=422, detail="roll_number is required for students")
            db.add(models.StudentProfile(user_id=u.id, roll_number=body.roll_number,
                                         previous_result_pct=body.previous_result_pct))
        elif body.role == "faculty":
            db.add(models.FacultyProfile(user_id=u.id, department=body.department or "CSE"))
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or roll number already exists")
    audit(db, admin.id, "create_user", "users", u.id, {"email": u.email, "role": u.role})
    db.commit()
    db.refresh(u)
    return serializers.user(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), admin=Depends(admin_only)):
    u = db.get(models.User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    changes = body.model_dump(exclude_none=True)
    roll_number, department = changes.pop("roll_number", None), changes.pop("department", None)
    if u.id == admin.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(status_code=422, detail="You cannot remove your own administrator access")
    new_role = changes.get("role")
    if new_role and new_role != u.role:
        changes["previous_role"] = u.role
        # Existing profiles (and the student's academic and intervention history) are always kept;
        # a profile is created only when the new role needs one the user does not have.
        if new_role == "student" and not u.student_profile:
            if not roll_number:
                raise HTTPException(status_code=422, detail="roll_number is required to give a user the student role")
            db.add(models.StudentProfile(user_id=u.id, roll_number=roll_number))
            changes["created_profile"] = f"student {roll_number}"
        elif new_role == "faculty" and not u.faculty_profile:
            db.add(models.FacultyProfile(user_id=u.id, department=department or "CSE"))
            changes["created_profile"] = "faculty"
    if "password" in changes:
        u.password_hash = hash_password(changes.pop("password"))
        changes["password"] = "(changed)"
    for k in ("full_name", "role", "is_active"):
        if k in changes:
            setattr(u, k, changes[k])
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Roll number already exists")
    audit(db, admin.id, "update_user", "users", u.id, changes)
    db.commit()
    db.refresh(u)
    return serializers.user(u)


@router.get("/faculty-assignments")
def faculty_assignments(db: Session = Depends(get_db), _=Depends(admin_only)):
    rows = db.query(models.FacultyStudentAssignment).all()
    return [{"id": r.id, "faculty_id": r.faculty_id, "student_id": r.student_id} for r in rows]


@router.post("/faculty-assignments", status_code=201)
def assign_student(body: AssignStudentIn, db: Session = Depends(get_db), admin=Depends(admin_only)):
    if not db.get(models.FacultyProfile, body.faculty_id) or not db.get(models.StudentProfile, body.student_id):
        raise HTTPException(status_code=404, detail="Faculty or student not found")
    db.add(models.FacultyStudentAssignment(faculty_id=body.faculty_id, student_id=body.student_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already assigned")
    audit(db, admin.id, "assign_student_to_faculty", "faculty_student_assignments", None, body.model_dump())
    db.commit()
    return {"ok": True}


@router.post("/intervention-types", status_code=201)
def create_type(body: TypeIn, db: Session = Depends(get_db), admin=Depends(admin_only)):
    t = models.InterventionType(**body.model_dump())
    db.add(t)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Code already exists")
    audit(db, admin.id, "create_intervention_type", "intervention_types", t.id, body.model_dump())
    db.commit()
    return {"id": t.id, "code": t.code, "note": "New arm starts from the prior in the current policy."}


@router.patch("/intervention-types/{type_id}")
def toggle_type(type_id: int, body: TypePatch, db: Session = Depends(get_db), admin=Depends(admin_only)):
    t = db.get(models.InterventionType, type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(t, k, v)
    audit(db, admin.id, "update_intervention_type", "intervention_types", t.id, changes)
    db.commit()
    return {"id": t.id, "code": t.code, "name": t.name, "is_active": t.is_active}


@router.get("/resources")
def resources(db: Session = Depends(get_db), _=Depends(admin_only)):
    return [serializers.resource(r, hide_answers=False) for r in db.query(models.LearningResource).order_by(models.LearningResource.id)]


@router.post("/resources", status_code=201)
def create_resource(body: ResourceIn, db: Session = Depends(get_db), admin=Depends(admin_only)):
    t = db.query(models.InterventionType).filter(models.InterventionType.code == body.intervention_type).first()
    if not t:
        raise HTTPException(status_code=422, detail="Unknown intervention type")
    data = body.model_dump()
    data.pop("intervention_type")
    r = models.LearningResource(intervention_type_id=t.id, **data)
    db.add(r)
    db.flush()
    audit(db, admin.id, "create_resource", "learning_resources", r.id, {"title": r.title})
    db.commit()
    return serializers.resource(r, hide_answers=False)


@router.patch("/resources/{resource_id}")
def update_resource(resource_id: int, body: ResourcePatch, db: Session = Depends(get_db), admin=Depends(admin_only)):
    r = db.get(models.LearningResource, resource_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    changes = body.model_dump(exclude_unset=True)  # topic_id may be set to null (= general resource)
    if changes.get("topic_id") is not None and not db.get(models.Topic, changes["topic_id"]):
        raise HTTPException(status_code=422, detail="Unknown topic_id")
    for k, v in changes.items():
        if v is None and k not in ("topic_id", "url"):
            raise HTTPException(status_code=422, detail=f"{k} cannot be empty")
        setattr(r, k, v)
    audit(db, admin.id, "update_resource", "learning_resources", r.id, changes)
    db.commit()
    return serializers.resource(r, hide_answers=False)


@router.get("/config")
def config(db: Session = Depends(get_db), _=Depends(admin_only)):
    return {"policy_config": get_policy_config(db), "eligibility_rules": service.get_rules(db)}


@router.put("/config")
def put_config(body: dict, db: Session = Depends(get_db), admin=Depends(admin_only)):
    try:
        cfg = set_policy_config(db, body, admin.id)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    db.commit()
    return {"policy_config": cfg,
            "note": "lints_lambda / lints_v apply to policy versions created after re-initialisation."}


@router.put("/eligibility-rules")
def put_rules(body: RulesIn, db: Session = Depends(get_db), admin=Depends(admin_only)):
    try:
        service.set_rules(db, body.rules, admin.id)
    except RuleConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))
    db.commit()
    return {"rules": body.rules}


@router.get("/policy")
def policy(db: Session = Depends(get_db), _=Depends(admin_only)):
    pv = service.current_policy_version(db)
    params = service.load_params(db, pv)
    import numpy as np
    arms = []
    for code, p in params.items():
        mu, _ = p.posterior(pv.v)
        arms.append({"intervention": code, "n_observations": p.n,
                     "posterior_mean_theta": dict(zip(pv.feature_names, np.round(mu, 4).tolist()))})
    versions = db.query(models.PolicyVersion).order_by(models.PolicyVersion.version.desc()).limit(50).all()
    updates = db.query(models.PolicyUpdate).order_by(models.PolicyUpdate.id.desc()).limit(50).all()
    vmap = {v.id: v.version for v in db.query(models.PolicyVersion).all()}
    return {"current_version": pv.version, "lambda": pv.lam, "v": pv.v, "context_features": pv.feature_names,
            "arms": arms,
            "versions": [{"version": v.version, "reason": v.reason, "created_at": v.created_at.isoformat()} for v in versions],
            "updates": [{"assignment_id": u.assignment_id, "reward": round(u.reward, 4),
                         "from_version": vmap.get(u.from_version_id), "to_version": vmap.get(u.to_version_id),
                         "created_at": u.created_at.isoformat()} for u in updates]}


@router.post("/policy/reinitialise")
def reinit(body: ReinitIn, db: Session = Depends(get_db), admin=Depends(admin_only)):
    """Start a fresh policy version from the prior (e.g. after changing lambda/v). History is kept."""
    pv = service.create_initial_policy(db, admin.id, f"re-initialised: {body.reason}")
    db.commit()
    return {"version": pv.version}


@router.get("/audit")
def audit_log(limit: int = 100, db: Session = Depends(get_db), _=Depends(admin_only)):
    rows = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(min(limit, 500)).all()
    return [{"id": r.id, "user_id": r.user_id, "action": r.action, "entity": r.entity, "entity_id": r.entity_id,
             "details": r.details, "created_at": r.created_at.isoformat()} for r in rows]
