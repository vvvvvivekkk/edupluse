"""Relational schema for EduPulse.

Groups (brief section 7):
  7.1 users, student_profiles, faculty_profiles, faculty_student_assignments
  7.2 topics, assessments, student_assessment_results, attendance_records,
      assignments, student_assignment_records, learning_activity_records
  -   student_states (Random Forest predictions, append-only)
  7.3 intervention_types, learning_resources, intervention_assignments, intervention_responses
  7.4 policy_versions, policy_parameters, policy_updates
  -   system_config, audit_logs
"""
from datetime import datetime, date, timezone

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- 7.1 users
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # student | faculty | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student_profile = relationship("StudentProfile", back_populates="user", uselist=False)
    faculty_profile = relationship("FacultyProfile", back_populates="user", uselist=False)

    __table_args__ = (CheckConstraint("role in ('student','faculty','admin')", name="ck_user_role"),)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    roll_number: Mapped[str] = mapped_column(String(50), unique=True)
    program: Mapped[str] = mapped_column(String(100), default="B.Tech")
    year: Mapped[int] = mapped_column(Integer, default=1)
    # Previous academic result as a percentage (e.g. previous semester), optional
    previous_result_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    user = relationship("User", back_populates="student_profile")


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department: Mapped[str] = mapped_column(String(100), default="CSE")

    user = relationship("User", back_populates="faculty_profile")


class FacultyStudentAssignment(Base):
    __tablename__ = "faculty_student_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty_profiles.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    __table_args__ = (UniqueConstraint("faculty_id", "student_id"),)


# ------------------------------------------------------- 7.2 academic records
class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    course: Mapped[str] = mapped_column(String(100), default="Programming Fundamentals")


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    kind: Mapped[str] = mapped_column(String(20), default="quiz")  # quiz | exam | follow_up
    max_score: Mapped[float] = mapped_column(Float, default=100.0)
    held_on: Mapped[date] = mapped_column(Date, default=date.today)


class StudentAssessmentResult(Base):
    __tablename__ = "student_assessment_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"))
    raw_score: Mapped[float] = mapped_column(Float)
    score_pct: Mapped[float] = mapped_column(Float)  # normalised 0-100 for comparability
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    assessment = relationship("Assessment")
    __table_args__ = (CheckConstraint("score_pct >= 0 and score_pct <= 100", name="ck_score_range"),)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    sessions_attended: Mapped[int] = mapped_column(Integer)
    sessions_total: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        CheckConstraint("sessions_total > 0 and sessions_attended >= 0 and sessions_attended <= sessions_total",
                        name="ck_attendance"),
    )


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    due_date: Mapped[date] = mapped_column(Date)


class StudentAssignmentRecord(Base):
    __tablename__ = "student_assignment_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    status: Mapped[str] = mapped_column(String(20))  # submitted | late | missing
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id"),
        CheckConstraint("status in ('submitted','late','missing')", name="ck_assign_status"),
    )


class LearningActivityRecord(Base):
    """Practice-question attempts (also produced when a student completes a practice intervention)."""
    __tablename__ = "learning_activity_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    activity_type: Mapped[str] = mapped_column(String(30), default="practice")
    questions_attempted: Mapped[int] = mapped_column(Integer)
    questions_correct: Mapped[int] = mapped_column(Integer)
    intervention_assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("intervention_assignments.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        CheckConstraint("questions_attempted > 0 and questions_correct >= 0 and "
                        "questions_correct <= questions_attempted", name="ck_practice"),
    )


# ------------------------------------------------------------ student state
class StudentState(Base):
    """Append-only history of Random Forest state estimates."""
    __tablename__ = "student_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    state: Mapped[str] = mapped_column(String(30))  # normal | attention_needed | high_support_need
    features: Mapped[dict] = mapped_column(JSON)
    imputed_features: Mapped[list] = mapped_column(JSON, default=list)
    probabilities: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ----------------------------------------------------- 7.3 interventions
class InterventionType(Base):
    __tablename__ = "intervention_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LearningResource(Base):
    __tablename__ = "learning_resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    intervention_type_id: Mapped[int] = mapped_column(ForeignKey("intervention_types.id"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # For practice sets: {"questions":[{"q":..,"options":[..],"answer":i}, ...]}
    # For study plans: {"days":[{"day":1,"task":".."}, ...]}
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    intervention_type = relationship("InterventionType")


class InterventionAssignment(Base):
    __tablename__ = "intervention_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    intervention_type_id: Mapped[int] = mapped_column(ForeignKey("intervention_types.id"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("learning_resources.id"), nullable=True)
    student_state_id: Mapped[int] = mapped_column(ForeignKey("student_states.id"))
    policy_version_id: Mapped[int] = mapped_column(ForeignKey("policy_versions.id"))
    # Everything needed to reproduce / audit the selection decision:
    context: Mapped[dict] = mapped_column(JSON)          # raw indicators + context vector
    eligible: Mapped[list] = mapped_column(JSON)         # eligible intervention codes
    eligibility_reasons: Mapped[dict] = mapped_column(JSON)
    sampled_scores: Mapped[dict] = mapped_column(JSON)   # sampled expected reward per eligible arm
    rng_seed: Mapped[int] = mapped_column(Integer)
    selection_method: Mapped[str] = mapped_column(String(30), default="linear_thompson")
    pre_indicators: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    faculty_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    intervention_type = relationship("InterventionType")
    resource = relationship("LearningResource")
    topic = relationship("Topic")
    response = relationship("InterventionResponse", back_populates="assignment", uselist=False)

    __table_args__ = (
        CheckConstraint("status in ('assigned','accessed','completed','evaluated','cancelled')",
                        name="ck_ia_status"),
    )


class InterventionResponse(Base):
    __tablename__ = "intervention_responses"
    id: Mapped[int] = mapped_column(primary_key=True)
    # unique => one response per intervention: duplicate submissions are rejected by the DB too
    assignment_id: Mapped[int] = mapped_column(ForeignKey("intervention_assignments.id"), unique=True)
    post_indicators: Mapped[dict] = mapped_column(JSON)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    learning_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    engagement_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment = relationship("InterventionAssignment", back_populates="response")


# ---------------------------------------------------------- 7.4 policy
class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    reason: Mapped[str] = mapped_column(String(200))
    lam: Mapped[float] = mapped_column(Float)
    v: Mapped[float] = mapped_column(Float)
    dim: Mapped[int] = mapped_column(Integer)
    feature_names: Mapped[list] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PolicyParameter(Base):
    """Per-arm sufficient statistics of linear Thompson sampling for one policy version.
    A (d x d matrix) and b (d vector) are stored as JSON lists."""
    __tablename__ = "policy_parameters"
    id: Mapped[int] = mapped_column(primary_key=True)
    policy_version_id: Mapped[int] = mapped_column(ForeignKey("policy_versions.id"), index=True)
    intervention_type_id: Mapped[int] = mapped_column(ForeignKey("intervention_types.id"))
    A: Mapped[list] = mapped_column(JSON)
    b: Mapped[list] = mapped_column(JSON)
    n_observations: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("policy_version_id", "intervention_type_id"),)


class PolicyUpdate(Base):
    __tablename__ = "policy_updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    # unique => a given intervention can update the policy at most once
    assignment_id: Mapped[int] = mapped_column(ForeignKey("intervention_assignments.id"), unique=True)
    intervention_type_id: Mapped[int] = mapped_column(ForeignKey("intervention_types.id"))
    from_version_id: Mapped[int] = mapped_column(ForeignKey("policy_versions.id"))
    to_version_id: Mapped[int] = mapped_column(ForeignKey("policy_versions.id"))
    reward: Mapped[float] = mapped_column(Float)
    context_vector: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ------------------------------------------------------- config & audit
class SystemConfig(Base):
    __tablename__ = "system_config"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
