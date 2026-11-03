# Testing Report

Environment: Python 3.12 (Windows 11), PostgreSQL 16 in Docker (separate `edupulse_test` database), Node 20,
headless Chromium. Date of run: 3 November 2026. (The first round on 1 November used Python 3.13 and Node 22
and gave the same results for the 54 tests that existed then.)

## Summary

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration (pytest) on PostgreSQL 16 | `cd backend && python -m pytest -q` | **66 passed, 0 failed** |
| Same suite on SQLite | `TEST_DATABASE_URL=sqlite:///./test.db python -m pytest -q` | **65 passed, 1 skipped** (the concurrency test is PostgreSQL-only; SQLite serialises writers itself) |
| Frontend component tests (Vitest + Testing Library, jsdom) | `cd frontend && npm test` | **20 passed, 0 failed** |
| Clean install from GitHub (new venv, only `requirements.txt`, empty DB, model retrained) | see below | **passed** — found and fixed a missing dependency (`python-multipart`) |
| Browser end-to-end (Playwright) | `cd frontend && python e2e/e2e_cycle.py` | **4 of 4 runs passed, 0 console errors**; the faculty-support path occurred in 2 runs and passed |
| New-student browser test | `python e2e/e2e_new_student.py` | **4 of 4 runs passed** (self-study path each time this round; the teacher-meeting path passed in 4 of 8 runs on 1 November) |
| Import / correction / roles / username-login browser test | `python e2e/e2e_records_admin.py` | **4 of 4 runs passed, 0 page errors** |
| Frontend production build | `npm run build` | passed |
| Policy simulation vs baselines | `python -m scripts.simulate` | completed; output byte-identical to the 1 November results (seeded), so the changes did not alter algorithm behaviour (see below) |

## Coverage of brief §11.4 required tests

| Required test | Where | What is checked |
|---|---|---|
| Valid and invalid academic inputs | `test_api::test_academic_record_validation`, e2e | missing fields 422, score > max 422, attended > total 422, valid 201; validation message shown in UI |
| Missing values | `test_eligibility_and_model::test_required_feature_missing_is_rejected`, `test_prediction_reports_imputed_features`, `test_api::test_state_requires_data`, `test_thompson::test_missing_context_uses_fallback_not_zero`, `test_missing_indicator_never_satisfies_comparison` | required missing → 422; optional missing → imputed and reported, never 0 |
| Model inference | `test_prediction_reports_imputed_features`, `test_monotone_sanity`, `test_model_card_has_separate_test_evaluation` | valid probabilities, version, sensible ordering, separate test evaluation, RF ≫ baseline |
| Eligibility filtering | 8 tests in `test_eligibility_and_model` | every row of the brief's eligibility table, exclusions X1/X2, fallbacks F0/F1, rule validation |
| Intervention selection | `test_thompson::test_never_selects_ineligible`, `test_empty_eligible_raises`, `test_exploitation_after_evidence`, `test_exploration_of_uncertain_arm`, `test_same_seed_reproduces_selection` | only eligible arms (500 draws), exploration, exploitation, reproducibility |
| Reward calculation | `test_reward` (7 tests) | gain formula, clipping, engagement common components, α weighting, fallback r = g |
| Pre-intervention score of 100 | `test_reward::test_learning_gain_pre_100_edge_case` | g = 0 at ceiling; drop penalised |
| Response classification | `test_reward::test_classification_thresholds` | boundary values for all three categories |
| Policy updates | `test_thompson::test_update_matches_formula`, `test_posterior_converges_to_true_parameters`, `test_api::test_full_cycle_…` | A += xxᵀ, b += r x exactly; posterior converges; only the chosen arm changes; version +1 |
| Database persistence | `test_api::test_full_cycle_…` | assignment, response, policy version, policy update, new state all stored; context/seed stored |
| Duplicate response submissions | `test_api::test_full_cycle_…` | second response 409, second evaluate 409, exactly one policy update |
| User-role permissions | `test_student_sees_only_self`, `test_faculty_sees_only_assigned`, `test_role_restricted_endpoints`, `test_response_requires_completion_and_valid_score`, `test_faculty_manual_support_record`, e2e | cross-student 403, unassigned faculty 403, role endpoints 403, student cannot complete faculty support |
| Dashboard data consistency | `test_api::test_dashboard_consistency_with_database` | dashboard counts equal DB counts; no effectiveness claim with insufficient data |
| Complete repeated intervention cycle | `test_api::test_repeated_cycles_and_no_improvement_escalation`, e2e | 4 cycles; streak triggers faculty-support eligibility; history keeps all 4; student flagged for review |
| (additional) Security | `test_passwords_are_hashed`, `test_login_success_and_failure` | bcrypt hashes; wrong password 401; no token 401 |
| (additional) Audit | `test_admin_config_validation_and_audit` | invalid α / unknown key rejected; change audited |
| (additional) Bulk import (brief §10 stage 1 "imports") | `test_records_admin::test_import_dry_run_then_import`, `test_import_is_all_or_nothing_with_row_errors`, `test_import_rejects_bad_files`, e2e | dry run stores nothing; 7 kinds of bad row each reported with its row number; one bad row → nothing stored; duplicate inside the file; wrong header, empty file, non-UTF-8 → 422; students 403; import audited; state marked stale |
| (additional) Record correction (brief §9 "create or update", §3.3) | `test_correct_record_is_audited_and_reassesses_state`, `test_correct_record_validation_and_permissions`, `test_records_behind_intervention_results_are_locked`, e2e | before/after + reason audited; new state row appended; out-of-range, missing reason, wrong field → 422; other faculty / student → 403; follow-up score behind an evaluated result → 409 and the result is unchanged |
| (additional) Username login (Screen 1 "email or username") | `test_login_with_roll_number_as_username`, frontend `auth.test.jsx`, e2e | roll number (any case) works; wrong password / unknown user 401; empty 422 |
| (additional) Role assignment (brief §3.3) | `test_admin_assigns_roles_and_profiles_are_created`, `test_admin_cannot_lock_themselves_out`, e2e | profile created when needed; roll number required and unique; profiles kept on role change; audited with previous role; admin cannot demote or deactivate themselves |
| (additional) Input validation on admin endpoints | `test_config_rejects_non_numeric_and_out_of_range`, `test_resource_and_type_patches_are_validated` | strings/booleans, non-integer counts, out-of-range percentages and thresholds, unknown topic, wrong types → 422 |
| (additional) Concurrent policy updates | `test_concurrent_evaluations_do_not_lose_policy_updates` (PostgreSQL) | 6 evaluations released at the same instant: no errors, unbroken version chain, all 6 observations in the final policy. The test was checked to be meaningful: with the lock disabled, 5 of 6 fail with a duplicate version number |

## Frontend component tests

`frontend/src/test/` (Vitest, React Testing Library, jsdom; the API is mocked at `fetch`):

| File | What is checked |
|---|---|
| `api.test.js` | readable error messages from API details; bearer token + JSON headers; file uploads sent as FormData without a forced content type; server error text surfaced |
| `auth.test.jsx` | login validation without an API call; server error shown; student/faculty/admin each land on their own home route; a student is redirected away from `/admin`, `/faculty`, `/analytics` and another student's page; no session → login |
| `components.test.jsx` | missing indicators shown as "no data", never 0%; state card shows probabilities, explanation, imputation note, "update pending" and the not-a-judgment disclaimer; history table columns (date, intervention, reason, status, before/after, response, faculty-recorded); CSV import only possible after a clean check, row errors listed; template download; analytics shows "insufficient data" instead of an effectiveness claim |

## End-to-end browser test

`frontend/e2e/e2e_cycle.py` drives the real UI: wrong-password error → student login → request
recommendation → complete practice → submit follow-up → policy update + state reassessment shown →
dashboard and history updated → faculty dashboard → student details → invalid record rejected in UI
→ valid record saved → analytics → access to an unassigned student blocked → admin overview, policy,
configuration. If Thompson sampling picks faculty support for the student, the script switches to the
faculty member to mark the consultation held (this path was not handled before, so the script could fail at
random). Screenshots in `docs/screenshots/`.

## Import, correction and roles (browser)

`frontend/e2e/e2e_records_admin.py`:
1. Faculty checks a 5-row CSV: the UI lists *row 5: raw_score cannot exceed max_score* and *row 6: not
   authorised* (another faculty member's student), and the Import button stays disabled.
2. The corrected 3-row file is checked and imported (2 students).
3. Faculty opens a student and corrects the imported quiz from 13/20 to 17/20 with a reason; the table updates
   and the state is re-estimated.
4. Admin creates a user and changes their role to faculty (profile created); the audit log shows
   `correct_academic_record`, `import_academic_records` and `update_user`.
5. A student signs in with roll number `EP26002` as username.

Screenshots: `screenshots/records_*.png`.

## New-student flow (browser)

`frontend/e2e/e2e_new_student.py`, run on SQLite:
1. Admin creates *Test Student* (Admin → Users) and assigns them to a faculty member.
2. The student logs in: every indicator shows "no data", and asking for a recommendation shows
   *"required indicator 'Latest assessment score' is missing"* — the system refuses to guess.
3. The teacher adds a quiz result (8/20 on Recursion) and attendance (3/5), re-estimates the state
   (High Support Need) and selects an intervention.
4. The student completes it. If **faculty support** was selected, the student sees it but cannot
   mark it done; the teacher marks the consultation held, then the student submits the follow-up.
5. The follow-up (65%) is evaluated, the policy updates, and the teacher sees the result in the history.

Because Thompson sampling is random among the allowed options, the test was run 8 times: all passed,
covering both the self-study path and the teacher-meeting path. Screenshots: `screenshots/new_student_*.png`.

## Adaptive selection: simulation vs baselines (brief §12)

> **SIMULATION RESULTS under an assumed reward model — not real-world evidence. Do not include in a research paper as verified findings.**

30 runs × 600 rounds; all policies use the same simulated students, eligibility rules and hidden reward model (`backend/scripts/simulate.py`).

| Policy | Mean reward | Mean reward (last 100) | Cumulative regret (mean ± sd) | Ineligible picks |
|---|---|---|---|---|
| Linear Thompson sampling | 0.261 | 0.273 | 24.3 ± 3.4 | 0 |
| Random among eligible | 0.227 | 0.231 | 46.4 ± 1.7 | 0 |
| Fixed rule (priority order) | 0.185 | 0.187 | 72.5 ± 3.1 | 0 |

What this verifies: the algorithm never selects ineligible interventions (0 of 54 000 decisions),
it learns (reward rises and regret grows more slowly than for either baseline), and it handles the
cold start (all arms start from the prior). What it does **not** show: that real students would
benefit, since the reward model is invented for testing.

## Model evaluation

See `DATA_AND_MODEL.md` §7 (synthetic-data evaluation: accuracy 0.715, macro-F1 0.710, ROC-AUC 0.880).

## Performance (demonstration workload)

Measured with `curl` against a single Uvicorn worker, PostgreSQL 16, 16 seeded students:

| Request | Time |
|---|---|
| `POST /api/auth/login` (bcrypt verification, slow by design), email or roll number | 0.37 s |
| `POST /api/interventions/select` (state check + rules + LinTS + insert) | 0.074 s |
| `POST /api/interventions/{id}/complete` | 0.020 s |
| `POST /api/interventions/{id}/response` with evaluation (reward + policy version + RF reassessment) | 0.14 s |
| `GET /api/dashboard/summary` | 0.12 s |
| `GET /api/students` | 0.12 s |
| `GET /api/analytics` | 0.027 s |
| `GET /api/students/{id}/academic-records` | 0.035 s |
| `POST /api/academic-records/import?dry_run=true`, 192 rows | 0.022 s |
| `POST /api/academic-records/import`, 192 rows | 0.48 s |
| `PATCH /api/academic-records/{type}/{id}` (correction + state re-estimate) | 0.098 s |

Measured with a Python HTTP client against a single Uvicorn worker on a Windows laptop, PostgreSQL 16 in
Docker, 16 seeded students; median of 5 requests (1 for the state-changing cycle calls). Not a benchmark. The full pytest suite (with a fresh database reseed per
integration test) runs in about 2.5 minutes on this machine. No load testing beyond the demonstration workload was performed.

## Known limitations

- Follow-up scores are entered manually (by student or faculty); there is no proctored follow-up quiz.
- Dashboard queries are computed per request without caching; fine for a class-sized deployment, would need aggregation for thousands of students.
- Frontend component tests cover the shared components, login/routing, CSV import and analytics; the larger
  pages (dashboards, intervention detail, admin) are covered by the three browser tests rather than unit tests.
- Bulk import accepts CSV only (no Excel); spreadsheets must be saved as CSV UTF-8.
