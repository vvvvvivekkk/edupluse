# Testing Report

Environment: Python 3.13, PostgreSQL 16 (separate `edupulse_test` database), Node 22, headless Chromium.
Date of run: 1 November 2026.

## Summary

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration (pytest) on PostgreSQL 16 | `cd backend && python -m pytest -q` | **54 passed, 0 failed** |
| Same suite on SQLite | `TEST_DATABASE_URL=sqlite:///./test.db python -m pytest -q` | **54 passed, 0 failed** |
| Clean install from GitHub (new venv, only `requirements.txt`, empty DB, model retrained) | see below | **passed** — found and fixed a missing dependency (`python-multipart`) |
| Browser end-to-end (Playwright) | `cd frontend && python e2e/e2e_cycle.py` | **passed, 0 console errors** |
| New-student browser test | `python e2e/e2e_new_student.py` | **8 of 8 runs passed**; the teacher-meeting path occurred in 4 runs and passed |
| Frontend production build | `npm run build` | passed |
| Policy simulation vs baselines | `python -m scripts.simulate` | completed (see below) |

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

## End-to-end browser test

`frontend/e2e/e2e_cycle.py` drives the real UI: wrong-password error → student login → request
recommendation → complete practice → submit follow-up → policy update + state reassessment shown →
dashboard and history updated → faculty dashboard → student details → invalid record rejected in UI
→ valid record saved → analytics → access to an unassigned student blocked → admin overview, policy,
configuration. Screenshots in `docs/screenshots/`.

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
| `POST /api/auth/login` (bcrypt verification, slow by design) | 0.32 s |
| `POST /api/interventions/select` (state check + rules + LinTS + insert) | 0.035 s |
| `POST /api/interventions/{id}/complete` | 0.015 s |
| `POST /api/interventions/{id}/response` with evaluation (reward + policy version + RF reassessment) | 0.10 s |
| `GET /api/dashboard/summary` | 0.034 s |
| `GET /api/students` | 0.030 s |
| `GET /api/analytics` | 0.012 s |

Single measurements, not a benchmark. The full pytest suite (with a fresh database reseed per
integration test) runs in about 60 s. No load testing beyond the demonstration workload was performed.

## Known limitations

- Follow-up scores are entered manually (by student or faculty); there is no proctored follow-up quiz.
- Dashboard queries are computed per request without caching; fine for a class-sized deployment, would need aggregation for thousands of students.
- No frontend unit tests; the UI is covered by the end-to-end browser test.
