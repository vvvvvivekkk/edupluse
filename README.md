# EduPulse

**A Response-Adaptive Academic Intervention and Learning Analytics System for Higher Education**

EduPulse implements the complete response-adaptive cycle:

```
Student data → Random Forest state estimate → eligibility rules → linear Thompson sampling
→ intervention delivery → follow-up assessment → reward + response category
→ policy update (new version) → state reassessment → next intervention
```

Stack (as agreed in the brief): **React.js + Recharts** · **Python + FastAPI** · **scikit-learn + NumPy** · **PostgreSQL**.

---

## Contents

| Path | What it is |
|---|---|
| `backend/app/` | FastAPI application (routers, models, security, services) |
| `backend/app/ml/` | Synthetic data generator, feature construction, Random Forest training + inference |
| `backend/app/engine/` | Eligibility rules, linear Thompson sampling, reward evaluation, cycle orchestration |
| `backend/models/` | Trained model artifact + `model_card.json` (dataset, metrics) |
| `backend/scripts/seed.py` | Creates tables and loads demo data |
| `backend/scripts/simulate.py` | Simulation study: LinTS vs random vs fixed-rule baselines |
| `backend/tests/` | 66 automated tests (pytest) |
| `frontend/` | React application (9 screens), `src/test/` component tests (Vitest), `e2e/` browser tests (Playwright) |
| `docs/` | Design, data & model, API, testing report, UML diagrams, screenshots, simulation results |

Documentation index:

- `docs/DESIGN.md` — architecture, algorithms (exact formulas), configuration, decisions needing approval
- `docs/DATA_AND_MODEL.md` — dataset, features, labels, preprocessing, split, model selection, evaluation
- `docs/API.md` — REST API reference (full OpenAPI spec in `docs/openapi.json`, live Swagger at `/docs`)
- `docs/TESTING_REPORT.md` — test coverage mapped to brief §11.4, results, simulation
- `docs/UML.md` — the 8 required diagrams (PNG + SVG + Mermaid source in `docs/diagrams/`)
- `docs/REQUIREMENTS_CHECKLIST.md` — every requirement in the brief, with status and evidence (brief itself: `docs/EDUPULSE_Project_Brief_Requirements.docx`)
- `docs/EXPLAINED_SIMPLY.md` — plain-language walkthrough for presenting and defending the project

---

## Setup

### Requirements
- Python 3.11+ (developed on 3.13)
- Node.js 18+ (developed on 22)
- PostgreSQL 14+ (developed on 16)

### 1. Database

> Quick local run without PostgreSQL: set `DATABASE_URL=sqlite:///./edupulse.db` in `backend/.env` and skip this step. PostgreSQL is the intended database for the real deployment.

```bash
sudo -u postgres psql -c "CREATE USER edupulse WITH PASSWORD 'edupulse' CREATEDB;"
sudo -u postgres createdb -O edupulse edupulse
sudo -u postgres createdb -O edupulse edupulse_test   # for automated tests
```
Or with Docker (any OS):
```bash
docker run -d --name edupulse-pg -e POSTGRES_USER=edupulse -e POSTGRES_PASSWORD=edupulse -e POSTGRES_DB=edupulse -p 5432:5432 postgres:16
docker exec edupulse-pg psql -U edupulse -c "CREATE DATABASE edupulse_test;"
```

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edit SECRET_KEY and DATABASE_URL; loaded automatically at startup
python -m app.ml.train      # trains the Random Forest, writes models/ (already included)
python -m scripts.seed --reset
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173  (proxies /api to :8000)
```
Production build: `npm run build` → static files in `frontend/dist/`.

### Demo accounts (synthetic data)
| Role | Email | Password |
|---|---|---|
| Student | `student1@edupulse.edu` … `student16@edupulse.edu` (or roll number `EP26001` … `EP26016` as username) | `Student@123` |
| Faculty | `faculty1@edupulse.edu`, `faculty2@edupulse.edu` | `Faculty@123` |
| Admin | `admin@edupulse.edu` | `Admin@123` |

Change these before any real use.

---

## Demonstrating the full cycle (≈3 minutes)

1. Log in as **student1**. The dashboard shows the Random Forest estimate (High Support Need, with probabilities and the indicators behind it).
2. Click **Get my next recommendation**. The weakest topic (Recursion) is identified, rules decide which interventions are eligible, and linear Thompson sampling picks one. The page shows *why* (eligibility rule) and the eligible set.
3. Complete the activity (answer the practice questions, or mark the material/plan complete).
4. Enter a **follow-up score** (e.g. 72). The system computes learning gain, engagement change and reward, classifies the response, **updates the policy (v1 → v2)** and **reassesses the state**.
5. Back on the dashboard: new state, before/after chart, history row. Click **Get my next recommendation** again — the next selection uses the updated policy.
6. Log in as **faculty1**: state distribution, students needing review, response categories. Open a student to see sampled scores, the context vector and RNG seed for each decision (reproducible/auditable), add academic records, correct a mistaken record (with a reason, audited), or record faculty support. At the bottom of the dashboard, **Import academic records (CSV)**: download the template, *Check file*, then *Import* (nothing is stored if any row is invalid).
7. Repeat poor follow-ups (e.g. 10) for one student: after 2 consecutive *No Improvement* results, faculty support becomes eligible and the student appears under "needs review".
8. Log in as **admin**: policy versions and update history, posterior parameters per intervention, configuration (α, thresholds, λ, v), editable eligibility rules, users and role assignment, resources, audit log.

Reset demo data any time: `python -m scripts.seed --reset`.

---

## Running the tests
```bash
cd backend && python -m pytest -q          # 66 tests, uses edupulse_test DB (or TEST_DATABASE_URL=sqlite:///./test.db)
python -m scripts.simulate                 # regenerates docs/simulation_results.*
cd ../frontend && npm test                 # 20 component tests (Vitest + Testing Library, no server needed)
python e2e/e2e_cycle.py                    # browser test (API + dev server running, fresh seed)
python e2e/e2e_new_student.py              # new student: admin creates -> teacher adds marks -> full cycle (fresh seed)
python e2e/e2e_records_admin.py            # CSV import, record correction, role change, roll-number login (fresh seed)
# the browser test needs Playwright once:  pip install playwright && python -m playwright install chromium
```

---

## Important limitations (read before presenting results)

- **All data are synthetic.** Model metrics (accuracy 0.71, macro-F1 0.71, ROC-AUC 0.88) are *synthetic-data evaluation* only and are not evidence of real-world predictive accuracy.
- **Simulation results** (LinTS lower regret than baselines) hold under an *assumed* reward model and must not be presented as real-world effectiveness, nor included in a research paper as verified findings.
- The **state labels and thresholds**, **response thresholds**, **α**, and **eligibility rules** are proposed defaults and need project-owner approval (see `docs/DESIGN.md` §9).
- The reward `r` is an engineering measure; its relationship to actual learning has not been validated.
- Nothing here is a claim about patentability.
