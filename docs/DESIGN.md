# EduPulse — Design and Technical Specification

This document specifies what is implemented, with the exact formulas and parameters, so the
behaviour can be reviewed, reproduced and audited. Code references are relative to `backend/app/`.

## 1. Architecture

Modular monolith (no microservices), as preferred in brief §14.

| Layer | Technology | Location |
|---|---|---|
| Frontend | React 18, React Router, Recharts, Vite | `frontend/src` |
| API | FastAPI, Pydantic validation, OpenAPI docs | `main.py`, `routers/` |
| Security | bcrypt (passlib), JWT (HS256), role-based access | `security.py` |
| Cycle orchestration | Python service module | `engine/service.py` |
| ML | scikit-learn Random Forest, pandas | `ml/` |
| Adaptive selection | NumPy linear Thompson sampling | `engine/thompson.py` |
| Database | PostgreSQL via SQLAlchemy 2 | `models.py`, `database.py` |

See `UML.md` for component, deployment and architecture diagrams.

## 2. Roles and access control

| Role | Can see | Can do |
|---|---|---|
| Student | own records only | request recommendation, access/complete own interventions (not faculty support), submit follow-up |
| Faculty | assigned students only (`faculty_student_assignments`) | all of the above for assigned students, enter / bulk-import / correct records, re-estimate state, record faculty support, evaluate |
| Admin | everything | users and role assignment, faculty assignments, intervention types/resources, academic records (enter, import, correct), configuration, eligibility rules, policy re-initialisation, audit log |

Every student-scoped endpoint calls `ensure_student_access()`; out-of-scope access returns 403.
Passwords are bcrypt-hashed; JWTs expire (default 8 h). Database credentials come from environment variables.
Users sign in with their email, or (students) with their roll number as username.

**Role assignment**: an admin can change any user's role. If the new role needs a profile the user does
not have, it is created (a student role requires a roll number). Existing profiles are never deleted, so a
student's academic and intervention history survives a role change. An admin cannot remove their own
admin role or deactivate themselves (prevents lock-out). Every change is audited with the previous role.

## 3. Module 1 — Student-state estimation (Algorithm 1)

**Features** (`ml/features.py`), all on a 0–100 scale:

| Feature | Definition | Required |
|---|---|---|
| `latest_score` | most recent assessment, % | **yes** |
| `avg_score` | mean of all assessments, % | no |
| `attendance_pct` | Σ attended / Σ sessions | no |
| `assignment_completion_pct` | (submitted + late) / recorded assignments | no |
| `practice_accuracy_pct` | Σ correct / Σ attempted practice questions | no |
| `previous_result_pct` | previous academic result | no |

**Missing data**: never converted to zero. If the required feature is missing the API returns
422 ("record at least one assessment"). Optional missing features are imputed with the
training median *and* a missing-indicator column is added (`SimpleImputer(add_indicator=True)`);
the prediction stores the list of imputed features and the UI displays it.

**Output** (row in `student_states`, append-only): state, input features, imputed features,
class probabilities, explanation (indicators below the training median ranked by feature
importance), model version, timestamp. The UI states that the estimate is guidance, not a
judgment of ability.

**Reassessment**: the state is recomputed (a) after every evaluated intervention, because the
follow-up is stored as a new assessment result, (b) on demand by faculty/admin, and (c)
automatically before selection if any record is newer than the latest estimate ("stale").

Dataset, labels and evaluation: see `DATA_AND_MODEL.md`.

## 4. Module 2a — Eligibility (Algorithm 2)

Rule-based, no ML (`engine/eligibility.py`). Rules are stored as JSON in `system_config` and
editable by the admin (validated before saving; changes audited).

Context indicators: `state`, `topic_score` (latest score on the student's weakest topic),
`topic_mastery` (practice accuracy on that topic), `attendance_pct`, `assignment_completion_pct`,
`no_improvement_streak` (consecutive most-recent *No Improvement* results).

Default rules (thresholds reference configurable parameters, defaults in brackets):

| Rule | Condition | Eligible |
|---|---|---|
| R1 | topic_score < low_score (60) **and** topic_mastery < weak_mastery (55) | material, practice |
| R1b | topic_score < 60 **and** topic_mastery not yet measured | material, practice |
| R2 | topic_score < 60 **and** topic_mastery ≥ 55 | practice |
| R3 | attendance < 75 **or** completion < 70 | study plan |
| R4 | no_improvement_streak ≥ 2 | faculty support, material, study plan |
| R5 | state = high_support_need | faculty support |

Eligible set = union of interventions of all matching rules. A missing indicator never satisfies a numeric comparison.

Exclusions: **X1** the intervention that just produced *No Improvement* is removed while the streak is
active (unless it is the only option); **X2** inactive intervention types are removed.

Fallbacks: **F0** state Normal and nothing matched → no intervention ("no intervention indicated").
**F1** non-Normal state and nothing matched → practice + material.

## 5. Module 2b — Linear Thompson sampling (Algorithm 3)

Disjoint linear model per intervention ("arm"), `engine/thompson.py`.
Reference: Agrawal & Goyal (2013).

**Context vector** x ∈ ℝ⁸: `[1, latest_score/100, attendance/100, completion/100,
practice_accuracy/100, 1{attention_needed}, 1{high_support_need}, min(streak,3)/3]`.
Missing values use training medians (never 0).

**Model**: r = xᵀθₖ + ε. **Prior**: θₖ ~ N(0, (v²/λ) I).

**Sufficient statistics** per arm: Aₖ = λI + Σ xxᵀ, bₖ = Σ r x.

**Posterior**: θₖ ~ N(μₖ = Aₖ⁻¹bₖ, v² Aₖ⁻¹).

**Selection**: for each *eligible* arm draw θ̃ₖ from the posterior, score sₖ = xᵀθ̃ₖ, choose argmax.
Ineligible arms are never scored. Wide posteriors (few observations) give occasional high draws
(exploration); arms with high observed reward have high μₖ (exploitation).

**Update** (after reward r for chosen arm k, using the context x stored at selection time):
Aₖ ← Aₖ + xxᵀ, bₖ ← bₖ + r x. Only the chosen arm changes.

**Defaults**: λ = 1.0, v = 0.5 (configurable; take effect in policy versions created after re-initialisation).

**Auditability**: each assignment stores the context (raw + vector), eligible set and reasons,
sampled score / posterior mean / posterior SD / n for every eligible arm, the RNG seed and the
policy version. Re-running `select_arm` with the same parameters and seed reproduces the choice
(tested).

**Faculty-recorded support** (`POST /api/interventions/assign`) is a human decision, stored with
`selection_method = faculty_manual`. Its outcome is a valid (x, r) observation for that arm and
updates the policy the same way.

## 6. Module 3 — Response tracking and evaluation (Algorithm 4)

Lifecycle: `assigned → accessed → completed → evaluated` (or `cancelled`). Only one open
intervention per student at a time (409 otherwise).

**Completion**: practice sets require answers to all questions (stored as a practice activity
record); material and plans are marked complete by the student; faculty support only by faculty.
Completion alone never produces a response category.

**Pre-indicators** (stored at assignment): topic score on the target topic, all features,
engagement components over the window [assigned − W, assigned], W = 14 days.

**Post-indicators**: follow-up score on the **same topic, same 0–100 scale**, stored as a regular
`follow_up` assessment; engagement components over [assigned, follow-up].

**Comparability checks**: same topic id, both scores in [0, 100], intervention completed,
no previous response (also enforced by a UNIQUE constraint).

**Normalised learning gain** g = (post − pre)/(100 − pre). Edge case pre = 100 (formula undefined):
g = 0 if post = 100, else (post − 100)/100. g clipped to [−1, 1].

**Engagement change** e = mean over components present in **both** windows of (post − pre)/100,
clipped to [−1, 1]. Components: attendance %, assignment completion %, practice activity %
(= min(100, 100 · sessions / (2 per week × W/7)), normalised by the nominal window length).
If no component is comparable, e is undefined.

**Reward** r = α g + (1 − α) e, α = 0.7 (configurable, 0–1). If e is undefined, r = g
(recorded as α_effective = 1). r ∈ [−1, 1] by construction.

**Categories**: Positive r ≥ 0.30 · Partial 0.05 ≤ r < 0.30 · No Improvement r < 0.05.

**Idempotency**: the evaluation locks the assignment row (`SELECT … FOR UPDATE`), refuses if
already evaluated, and `policy_updates.assignment_id` is UNIQUE — a duplicate submission can
never update the policy twice (tested).

**Concurrency**: policy versions form a single chain (v1 → v2 → …). When several students' responses
are evaluated at the same moment, each evaluation takes a transaction-scoped PostgreSQL advisory lock
(`pg_advisory_xact_lock`, `service.lock_policy`) before reading the current version, so every update is
applied on top of the previous one and none is lost or rejected (tested with 6 simultaneous evaluations;
without the lock 5 of 6 failed on the unique version number). Selecting an intervention row-locks the
student, so two simultaneous requests cannot open two interventions.

**Policy vs state** (brief §5 Algorithm 4): evaluation performs two explicit, separate steps —
(1) policy update: new immutable `policy_versions` row with all arm parameters, one
`policy_updates` row; (2) state reassessment: new `student_states` row. The API response reports
both separately.

## 7. Data model

See `UML.md` (ER diagram) and `models.py`. Principles:
- historical rows are never overwritten (states, assignments, responses, policy versions are append-only);
- each policy version stores the full A and b of every arm as JSON (8×8 floats per arm), so any version can be inspected or restored;
- CHECK constraints for score ranges, attendance, statuses; UNIQUE constraints for one response / one policy update per intervention;
- all important operations write to `audit_logs` (logins, record entry, predictions, assignments, responses, policy updates, configuration changes, user changes);
- minimal personal data: name, email, roll number, programme, year.

**Academic-record entry, import and correction** (`routers/records.py`):
- Entry: one record at a time (`POST /api/academic-records`), validated (required fields, ranges, references).
- Bulk import (`POST /api/academic-records/import`, CSV): every row goes through the same validation and
  authorisation (faculty: assigned students only). It is all-or-nothing: if any row fails, nothing is
  stored and every row error is listed. A dry run (`?dry_run=true`) validates without storing; the UI always
  checks first. Students are identified by roll number; topics and assignments by name or id.
- Correction (`PATCH /api/academic-records/{type}/{id}`): only measured values can change (score,
  attendance counts/dates, assignment status, practice counts), never whose record it is. A reason is
  mandatory and the before/after values are written to `audit_logs`. The student's state is then
  re-estimated as a new `student_states` row (old estimates are kept).
- Records that are evidence for an intervention result (follow-up assessments; practice done inside an
  intervention) are **locked** (409) — historical intervention results cannot be altered. Intervention
  pre/post indicators are snapshots stored with the assignment/response, so correcting an ordinary record
  later never changes an evaluated result.

## 8. Configuration

`system_config` (admin UI → Configuration): `reward_alpha`, `positive_threshold`,
`partial_threshold`, `lints_lambda`, `lints_v`, `low_score_threshold`, `weak_mastery_threshold`,
`low_attendance_threshold`, `low_completion_threshold`, `no_improvement_streak`,
`engagement_window_days`, plus the eligibility rules JSON. All changes are validated and audited.
New intervention types can be added by the admin; they start from the prior.

## 9. Decisions that need project-owner approval

These are reasonable defaults chosen to make the system work end to end; the brief says they
must be agreed with the project owner.

1. **State labels**: derived from a hidden end-of-term outcome (≥60 Normal, 45–60 Attention, <45 High support) in synthetic data. Real labels need a real dataset and an agreed definition.
2. **Response thresholds** (0.30 / 0.05) and **α = 0.7**.
3. **Eligibility rules** R1–R5, exclusions and fallbacks, and their thresholds.
4. **Engagement measure** (three components, common-component comparison, 14-day window).
5. **Follow-up measurement**: currently a score entered by the student or faculty. A proctored follow-up quiz would be more reliable.
6. **Model choice**: in cross-validation Logistic Regression (macro-F1 0.736) and Random Forest (0.732) are statistically tied. Random Forest is kept as agreed; see `DATA_AND_MODEL.md` §6.
7. **Prior λ, v** for Thompson sampling.

## 10. Extensibility

- New intervention type: admin → Interventions (or `POST /api/admin/intervention-types`), add resources, reference it in a rule.
- New academic indicator: add to `ml/features.py`, retrain, optionally add to the context vector (requires policy re-initialisation because the dimension changes).
- New rule: edit the JSON in admin → Configuration.
