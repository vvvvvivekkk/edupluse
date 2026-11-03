# Requirements Checklist

Section-by-section check of the project brief (`EDUPULSE_Project_Brief_Requirements.docx`, in this
folder) against what is implemented and how it was verified.

Legend: ✅ met · ⚠️ partly met / needs a decision · ❌ not done

Verification sources: **T** = automated pytest test (`backend/tests/`), **FT** = frontend component test
(`frontend/src/test/`), **E2E** = browser test (`frontend/e2e/e2e_cycle.py`, `e2e_new_student.py`,
`e2e_records_admin.py`), **S** = screenshot in `docs/screenshots/`, **D** = document in `docs/`.

Last checked: 3 November 2026 — backend 66/66 on PostgreSQL 16 (65 + 1 PostgreSQL-only skip on SQLite),
frontend 20/20, all three browser tests pass. The three gaps left open on 1 November (bulk import, role
assignment, frontend test framework) are now closed; see "Changes on 3 November" at the end.

---

## §1 Main idea — the complete cycle

| Requirement | Status | Where / evidence |
|---|---|---|
| Data → state estimation → selection → delivery → response → adaptive update → next intervention | ✅ | `engine/service.py`; T `test_full_cycle_…`, `test_repeated_cycles_…`; E2E both scripts |
| Does not stop after prediction; records intervention, follow-up, response, updates records and policy | ✅ | same |
| Intervention chosen by defined rules and policy, not randomly | ✅ | eligibility rules + Thompson sampling; T `test_never_selects_ineligible`, simulation (random baseline is worse) |

## §2 Objectives

| Objective | Status | Evidence |
|---|---|---|
| Centralised web app for academic information | ✅ | React + FastAPI + PostgreSQL |
| Random Forest classifier for academic state | ✅ | `ml/train.py`, `ml/state_model.py`; D `DATA_AND_MODEL.md` |
| Intervention engine with eligibility | ✅ | `engine/eligibility.py` |
| Thompson sampling using context and outcomes | ✅ | `engine/thompson.py` (linear TS) |
| Record interventions and measure responses | ✅ | `intervention_assignments`, `intervention_responses` |
| Update policy parameters from responses | ✅ | `evaluate_response`; T `test_update_matches_formula` |
| Maintain state + history across repeated cycles | ✅ | append-only tables; T `test_repeated_cycles_…` |
| Student and faculty dashboards | ✅ | S 02, 05, 07 |
| Evaluate model and test the workflow | ✅ | D `DATA_AND_MODEL.md`, `TESTING_REPORT.md` |
| Extensible (new interventions, indicators) | ✅ | admin can add intervention types; D `DESIGN.md` §10 |

## §3 Users and roles

| Requirement | Status | Evidence |
|---|---|---|
| **Student**: secure login | ✅ | bcrypt + JWT; T `test_login_success_and_failure` |
| view own info, state, recommendation, material/practice | ✅ | S 02, 03 |
| complete/acknowledge intervention, submit follow-up | ✅ | S 04; E2E |
| view progress, history, response trends | ✅ | S 05, 06 |
| only own records | ✅ | T `test_student_sees_only_self` |
| **Faculty**: view assigned students, indicators, states | ✅ | S 07, 08 |
| view interventions + outcomes, history | ✅ | S 08, new_student_06 |
| identify students needing support | ✅ | "may need additional support" box (high support need or ≥2 no-improvement) |
| recommend/record faculty support | ✅ | "Record faculty support"; T `test_faculty_manual_support_record`; E2E (teacher marks consultation held) |
| access restricted to authorised students | ✅ | T `test_faculty_sees_only_assigned`; E2E (403 shown) |
| **Admin**: manage user accounts | ✅ | Admin → Users (create, activate/deactivate); E2E new_student_01 |
| assign roles | ✅ | Admin → Users: role selector per user; a missing profile is created (student needs a roll number), existing profiles and history are kept, change audited with the previous role; admin cannot demote/deactivate self. T `test_admin_assigns_roles_and_profiles_are_created`, `test_admin_cannot_lock_themselves_out`; E2E records_admin; S records_04 |
| manage academic records and configuration | ✅ | add (form), bulk import (CSV), list and correct records with an audited reason on any student page; Admin → Configuration. T `test_correct_record_*`, `test_import_*`; S records_01–03 |
| manage intervention categories and resources | ✅ | Admin → Interventions |
| configure initial policy parameters | ✅ | λ, v in configuration + "Re-initialise policy" |
| view system statistics | ✅ | Admin → Overview (S 10) |
| no unaudited alteration of historical results | ✅ | intervention history is never editable; records that are evidence for an intervention result are locked (409); corrections of other records keep before/after + reason in `audit_logs`. T `test_records_behind_intervention_results_are_locked` |

## §4 Core modules

| Module requirement | Status | Evidence |
|---|---|---|
| **M1** inputs: id, scores, attendance, completion, practice, previous results | ✅ | `ml/features.py` (6 features) |
| validate missing/invalid; never treat missing as zero | ✅ | T `test_required_feature_missing_is_rejected`, `test_prediction_reports_imputed_features` |
| store prediction, timestamp, model version | ✅ | `student_states` |
| 3 categories: Normal / Attention Needed / High Support Need | ✅ | |
| labels defined with a training procedure; dataset + evaluation documented | ✅ / ⚠️ | D `DATA_AND_MODEL.md`. Thresholds are proposed defaults → **owner must approve** |
| output incl. explanation; guidance, not a judgment | ✅ | concerns list + disclaimer on every state card |
| **M2** four intervention types | ✅ | material, practice, study plan, faculty support (25 resources seeded) |
| configurable, documented eligibility policy | ✅ | rules as JSON, editable by admin; D `DESIGN.md` §4 |
| Thompson sampling: context, eligible set, history, parameters, uncertainty | ✅ | linear TS; T exploration/exploitation tests |
| never selects ineligible intervention | ✅ | T (500 draws), simulation (0 of 54 000) |
| output: id, state, context, eligible, selected, timestamp, policy version, explanation; reproducible | ✅ | stored per assignment incl. RNG seed; T `test_same_seed_reproduces_selection`; S 03 (faculty view) |
| **M3** record assignment, access, completion, pre/post indicators | ✅ | status lifecycle + timestamps |
| explicit thresholds for Positive / Partial / No Improvement | ✅ / ⚠️ | 0.30 / 0.05, configurable → **owner must approve** |
| not based on clicking alone | ✅ | category needs a follow-up score; completion alone gives none |
| learning-gain formula + pre = 100 handled | ✅ | T `test_learning_gain_pre_100_edge_case` |
| pre/post comparable | ✅ | same topic, same 0–100 scale, checked before evaluation |
| combined reward; engagement defined, normalised, missing handled, bounded; α configurable | ✅ | D `DESIGN.md` §6 |
| reward not presented as validated | ✅ | stated in README, DESIGN, EXPLAINED_SIMPLY |
| **M4** student dashboard items (state, indicators, current intervention, resources, pending, history, responses, charts) | ✅ | S 02, 05 |
| faculty dashboard items (counts, distribution, needs support, trends, history, response summaries, repeated no-improvement, follow-up recommendations, charts) | ✅ | S 07, 09 |
| admin dashboard (users, counts, interventions, activity, configuration, policy history) | ✅ | S 10, 11, 12 |
| only stored data, no invented statistics | ✅ | T `test_dashboard_consistency_with_database` |

## §5 Algorithms

| Requirement | Status | Evidence |
|---|---|---|
| RF trained on labelled data; synthetic results labelled as such | ✅ | model card + all docs |
| accuracy, precision, recall, F1, confusion matrix on separate test set | ✅ | D `DATA_AND_MODEL.md` §7 |
| RF suitability checked, not chosen only because specified | ✅ | compared with LR, tree, baseline; LR tie reported honestly |
| eligibility: rules, exclusions, non-empty check, fallback | ✅ | X1, X2, F0, F1; T 8 tests |
| linear TS: posterior, updates, initialisation, regularisation specified; tested | ✅ | D `DESIGN.md` §5; T `test_thompson.py` (10 tests) |
| response evaluation; state update and policy update kept separate | ✅ | two explicit steps, reported separately |

## §6–7 Architecture and database

| Requirement | Status | Evidence |
|---|---|---|
| React frontend, Recharts | ✅ | |
| Python + FastAPI backend | ✅ | |
| scikit-learn, NumPy | ✅ | |
| PostgreSQL | ✅ | primary database; SQLite also works for quick local runs (brief §14 allows it for prototypes) |
| modular, not microservices | ✅ | |
| all listed tables (users … policy_versions) | ✅ | `models.py`; S ER diagram in D `UML.md` |
| PK/FK, validation, timestamps, consistent ids, history retrieval, policy info preserved, restricted access, minimal personal data | ✅ | constraints in `models.py` |
| no plaintext passwords | ✅ | T `test_passwords_are_hashed` |

## §8 Screens

| Screen | Status | Evidence |
|---|---|---|
| 1 Login — email **or username** (students: roll number), validation, role redirect, errors | ✅ | S 01; T `test_login_with_roll_number_as_username`; FT `auth.test.jsx` (validation, error, redirect per role) |
| 2 Student dashboard | ✅ | S 02, 05 |
| 3 Faculty dashboard | ✅ | S 07 |
| 4 Student details (incl. academic-record list and correction) | ✅ | S 08, records_03 |
| 5 Intervention details | ✅ | S 03 |
| 6 Follow-up assessment / response (validates ownership) | ✅ | S 04; T `test_response_requires_completion_and_valid_score` |
| 7 Intervention history | ✅ | S 06 |
| 8 Administrator interface | ✅ | S 10–12 |
| 9 Analytics (no effectiveness claims without enough data) | ✅ | S 09; minimum 30 outcomes per type before any comparison |

## §9 API

| Requirement | Status | Evidence |
|---|---|---|
| all 13 example endpoints | ✅ | same paths implemented; D `API.md` |
| `POST api/academic-records` "Create **or update**" | ✅ | create: `POST /api/academic-records`; bulk: `POST /api/academic-records/import`; update: `PATCH /api/academic-records/{type}/{id}` (audited correction) |
| validation, authorisation, useful errors, documentation | ✅ | Swagger at `/docs`, `openapi.json`; admin PATCH bodies and configuration values are typed and range-checked (T `test_config_rejects_non_numeric_and_out_of_range`, `test_resource_and_type_patches_are_validated`) |
| duplicate responses cannot update policy twice | ✅ | T `test_full_cycle_…`; row lock + UNIQUE constraint |
| simultaneous evaluations of different students all update the policy (none lost) | ✅ | PostgreSQL advisory lock; T `test_concurrent_evaluations_do_not_lose_policy_updates` (fails 5/6 without the lock) |

## §10 End-to-end workflow (main acceptance requirement)

| Stage | Status | Evidence |
|---|---|---|
| 1 Data entry by admin/faculty | ✅ | forms in UI + API; E2E new_student_03 |
| 1 … "or imports" | ✅ | CSV import on the faculty dashboard (and API): template download, check first (dry run), all-or-nothing, per-row errors, faculty limited to assigned students, audited. T `test_import_*`; FT `ImportRecords`; E2E records_admin; S records_01, records_02 |
| 2 Validation | ✅ | |
| 3 State estimation | ✅ | |
| 4 Eligibility | ✅ | |
| 5 Adaptive selection | ✅ | |
| 6 Delivery | ✅ | |
| 7 Response collection | ✅ | |
| 8 Response evaluation | ✅ | |
| 9 Policy update | ✅ | |
| 10 State reassessment | ✅ | |
| 11 Next intervention | ✅ | |
| 12 Dashboard update | ✅ | |

## §11–12 Data, testing and evaluation

| Requirement | Status | Evidence |
|---|---|---|
| synthetic data rules documented; not presented as real-world accuracy | ✅ | D `DATA_AND_MODEL.md` §2 |
| dataset source, permissions, features, labels, preprocessing, split, model selection, results | ✅ | D `DATA_AND_MODEL.md` |
| intervention evaluation definitions (completion, outcomes, window, formula, thresholds, update) | ✅ | D `DESIGN.md` §6 |
| all §11.4 required tests | ✅ | D `TESTING_REPORT.md` (table maps each one) |
| adaptive-selection evaluation vs random and fixed-rule baselines | ✅ | D `simulation_results.md` (labelled simulation) |
| application performance (API, DB, auth, errors, response times, consistency) | ✅ | D `TESTING_REPORT.md` |

## §13 Security and privacy

| Requirement | Status |
|---|---|
| password hashing, auth + RBAC, restricted records, input validation, protected endpoints, DB credentials from environment, token expiry, audit records, minimal personal data, no cross-student exposure | ✅ |
| no automatic high-stakes decisions; faculty oversight | ✅ (suggestions only; faculty review list) |

## §14 System requirements

| Requirement | Status | Notes |
|---|---|---|
| recommended stack incl. OpenAPI docs, Git/GitHub | ✅ | github.com/vvvvvivekkk/edupluse |
| "Suitable Python **and frontend** testing frameworks" | ✅ | Python: pytest (66 tests). Frontend: Vitest + React Testing Library (20 component tests, `npm test`) and Playwright browser tests (3 scripts) |

## §15 UML

All 8 required diagrams: ✅ — D `UML.md`, `diagrams/` (PNG, SVG, Mermaid source).

## §16 Technical constraints

| Constraint | Status |
|---|---|
| Thompson sampling not replaced by random selection | ✅ |
| not only fixed rules called "adaptive" | ✅ |
| response tracking and policy update present | ✅ |
| no hard-coded dashboard statistics | ✅ |
| no claim the model improves performance | ✅ |
| no claim synthetic results prove real-world effectiveness | ✅ |
| no unverified simulation results presented as findings | ✅ (all labelled) |
| stack not silently changed | ✅ |
| no plaintext passwords | ✅ |
| classifier does not make high-stakes decisions | ✅ |
| no patentability claim | ✅ |

## §17 Handover items

Source code ✅ · database schema + seed script ✅ · setup instructions ✅ (README) · UML ✅ (use-case diagram updated for import/correction) · API documentation ✅ · testing report ✅.

---

## Open items for the project owner

1. **Approve defaults**: state-label thresholds, response thresholds (0.30 / 0.05), α = 0.7, eligibility rules R1–R5 (see `DESIGN.md` §9).
2. **Real data**: all evaluation is synthetic; a real labelled dataset is needed before any real-world claims.
3. **Student self-registration** is intentionally absent: the brief makes account creation an admin task (§3.3).
4. **Import format**: CSV only (UTF-8). Confirm whether Excel upload or a student-information-system feed is needed.
5. **Username**: students may sign in with their roll number; faculty and admins use their email. Confirm this is the intended "username".

## Changes on 3 November 2026

| Gap or issue found in review | Fix |
|---|---|
| §10 stage 1 "imports" not implemented | CSV bulk import (API + faculty-dashboard UI), dry run, all-or-nothing, per-row errors, audited |
| §9 "create **or update**" / §6 "forms for entering or updating" / §3.3 "manage academic records": records could only be created | record list + audited correction with mandatory reason; state re-estimated; intervention evidence locked |
| §3.3 "assign roles" limited | role change creates the needed profile; self-lockout prevented |
| §8 Screen 1 "email or username": email only | students can sign in with their roll number |
| §14 frontend testing framework missing | Vitest + Testing Library, 20 component tests |
| Admin PATCH endpoints accepted untyped bodies; config accepted non-numeric values | typed Pydantic bodies; numeric/range/integer checks on configuration |
| Two students evaluated at the same moment: one request failed and its policy update was lost (found in review, reproduced in a test) | PostgreSQL advisory lock around policy-version creation; student row lock on selection |
| `e2e_cycle.py` failed at random when Thompson sampling picked faculty support | script now handles the faculty-support path |
| `scripts/simulate.py` crashed on Windows while writing results (platform default encoding) and left `simulation_results.md` truncated | result and model-card files are read/written as UTF-8 |
