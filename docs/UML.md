# UML and Design Diagrams

All diagrams reflect the implemented system. Each is provided as PNG and SVG in `diagrams/`, with editable Mermaid source in `diagrams/src/` (render at https://mermaid.live or with mermaid-cli).

## 1. Use Case Diagram

![1. Use Case Diagram](diagrams/01_use_case.png)

<details><summary>Mermaid source</summary>

```mermaid
flowchart LR
  S([Student]):::actor
  F([Faculty Member]):::actor
  A([Administrator]):::actor
  subgraph EP[EduPulse System]
    UC1((Log in))
    UC2((View own academic state<br/>and indicators))
    UC3((Request next recommendation))
    UC4((Access / complete<br/>intervention))
    UC5((Submit follow-up<br/>assessment))
    UC6((View progress and<br/>intervention history))
    UC7((View assigned students))
    UC8((Enter, import and correct<br/>academic records))
    UC9((Re-estimate state))
    UC10((Review interventions<br/>and outcomes))
    UC11((Record faculty support))
    UC12((Evaluate response))
    UC13((Manage users and roles))
    UC14((Manage interventions<br/>and resources))
    UC15((Configure policy and<br/>eligibility rules))
    UC16((View system statistics<br/>and audit log))
  end
  S --- UC1 & UC2 & UC3 & UC4 & UC5 & UC6
  F --- UC1 & UC7 & UC8 & UC9 & UC10 & UC11 & UC12 & UC6
  A --- UC1 & UC13 & UC14 & UC15 & UC16 & UC8
  classDef actor fill:#eaeefe,stroke:#3b5bdb,color:#1d2433
```
</details>

## 2. Class Diagram

![2. Class Diagram](diagrams/02_class.png)

Persistence classes map 1:1 to SQLAlchemy models in `backend/app/models.py`; `AcademicRecord` groups the four record tables. Service classes are the modules in `app/ml` and `app/engine`.

<details><summary>Mermaid source</summary>

```mermaid
classDiagram
  direction LR
  class User {
    +int id
    +str email
    +str password_hash
    +str role
    +bool is_active
  }
  class StudentProfile {
    +int id
    +str roll_number
    +float previous_result_pct
  }
  class FacultyProfile {
    +int id
    +str department
  }
  class AcademicRecord {
    <<abstract>>
    StudentAssessmentResult
    AttendanceRecord
    StudentAssignmentRecord
    LearningActivityRecord
  }
  class StudentState {
    +str state
    +dict features
    +list imputed_features
    +dict probabilities
    +str model_version
  }
  class InterventionType {
    +str code
    +str name
    +bool is_active
  }
  class LearningResource {
    +str title
    +str url
    +dict content
  }
  class InterventionAssignment {
    +int id
    +dict context
    +list eligible
    +dict sampled_scores
    +int rng_seed
    +dict pre_indicators
    +str status
  }
  class InterventionResponse {
    +dict post_indicators
    +float learning_gain
    +float engagement_change
    +float reward
    +str category
  }
  class AdaptivePolicy {
    <<PolicyVersion + PolicyParameter>>
    +int version
    +float lam
    +float v
    +A[d x d] per arm
    +b[d] per arm
  }
  class PolicyUpdate {
    +float reward
    +list context_vector
  }
  class StateModel {
    <<service: app.ml.state_model>>
    +predict_state(features) dict
  }
  class EligibilityEngine {
    <<service: app.engine.eligibility>>
    +evaluate_eligibility(ctx, rules, cfg) dict
  }
  class LinearThompsonSampler {
    <<service: app.engine.thompson>>
    +build_context(...) ndarray
    +select_arm(params, eligible, x, v, rng)
  }
  class ArmParams {
    +ndarray A
    +ndarray b
    +int n
    +posterior(v)
    +updated(x, r) ArmParams
  }
  class RewardEvaluator {
    <<service: app.engine.reward>>
    +learning_gain(pre, post)
    +engagement_change(pre, post)
    +combined_reward(g, e, alpha)
    +classify(r)
  }
  User "1" -- "0..1" StudentProfile
  User "1" -- "0..1" FacultyProfile
  FacultyProfile "*" -- "*" StudentProfile : assigned
  StudentProfile "1" -- "*" AcademicRecord
  StudentProfile "1" -- "*" StudentState
  StudentProfile "1" -- "*" InterventionAssignment
  InterventionType "1" -- "*" LearningResource
  InterventionType "1" -- "*" InterventionAssignment
  InterventionAssignment "1" -- "0..1" InterventionResponse
  InterventionAssignment "*" --> "1" StudentState : based on
  InterventionAssignment "*" --> "1" AdaptivePolicy : selected under
  PolicyUpdate "0..1" --> "1" InterventionAssignment
  AdaptivePolicy "1" *-- "*" ArmParams
  StateModel ..> StudentState : creates
  LinearThompsonSampler ..> ArmParams : samples
  RewardEvaluator ..> InterventionResponse : fills
```
</details>

## 3. Sequence Diagram — one complete cycle

![3. Sequence Diagram — one complete cycle](diagrams/03_sequence.png)

<details><summary>Mermaid source</summary>

```mermaid
sequenceDiagram
  autonumber
  actor St as Student
  participant UI as React frontend
  participant API as FastAPI
  participant SVC as Cycle service
  participant RF as Random Forest
  participant EL as Eligibility rules
  participant TS as Linear Thompson sampling
  participant DB as PostgreSQL

  St->>UI: Get my next recommendation
  UI->>API: POST /api/interventions/select
  API->>SVC: select_intervention(student)
  SVC->>DB: latest state + academic records
  alt state missing or stale
    SVC->>RF: predict_state(features)
    RF-->>SVC: state, probabilities, explanation
    SVC->>DB: INSERT student_states
  end
  SVC->>EL: evaluate_eligibility(context, rules)
  EL-->>SVC: eligible set + reasons (or fallback)
  SVC->>DB: current policy version (A, b per arm)
  SVC->>TS: select_arm(params, eligible, x, seed)
  TS-->>SVC: chosen arm + sampled scores
  SVC->>DB: INSERT intervention_assignments (context, seed, pre-indicators)
  API-->>UI: selected intervention
  St->>UI: complete activity
  UI->>API: POST /interventions/{id}/complete
  API->>DB: status=completed (+ practice record)
  St->>UI: enter follow-up score
  UI->>API: POST /interventions/{id}/response
  API->>SVC: record_response + evaluate_response
  SVC->>DB: INSERT follow-up result, intervention_responses
  SVC->>SVC: g, e, r, category
  SVC->>DB: new policy_version, policy_parameters, policy_updates (once)
  SVC->>RF: reassess state (separate step)
  SVC->>DB: INSERT student_states
  API-->>UI: category, policy v(n)→v(n+1), new state
```
</details>

## 4. Activity Diagram — eligibility, fallback and response classification

![4. Activity Diagram — eligibility, fallback and response classification](diagrams/04_activity.png)

<details><summary>Mermaid source</summary>

```mermaid
flowchart TD
  A([Start: selection requested]) --> B{Open intervention exists?}
  B -- yes --> B1[Reject 409: finish current one first] --> Z([End])
  B -- no --> C{State missing or older<br/>than latest record?}
  C -- yes --> C1{Required indicator present?}
  C1 -- no --> C2[Reject 422: record an assessment first] --> Z
  C1 -- yes --> C3[Random Forest estimates state<br/>impute + flag missing optional data] --> D
  C -- no --> D[Build context: state, weakest topic,<br/>mastery, engagement, no-improvement streak]
  D --> E[Evaluate eligibility rules R1-R5]
  E --> F[Apply exclusions X1 failed arm, X2 inactive]
  F --> G{Eligible set empty?}
  G -- yes --> G1{State Normal?}
  G1 -- yes --> G2[F0: no intervention indicated] --> Z
  G1 -- no --> G3[F1 fallback: practice + material] --> H
  G -- no --> H[Linear Thompson sampling over eligible arms]
  H --> I[Record assignment with context, seed,<br/>sampled scores, pre-indicators]
  I --> J[Student completes activity]
  J --> K[Follow-up score on same topic, 0-100]
  K --> L{Comparable? same topic, valid range,<br/>not already recorded}
  L -- no --> L1[Reject 409/422]
  L -- yes --> M[g = normalised gain, e = engagement change<br/>r = alpha g + 1-alpha e]
  M --> N{r ≥ positive threshold?}
  N -- yes --> N1[Positive]
  N -- no --> O{r ≥ partial threshold?}
  O -- yes --> O1[Partial]
  O -- no --> O2[No Improvement]
  N1 & O1 & O2 --> P[Update chosen arm: A += x xᵀ, b += r x<br/>new policy version, once per intervention]
  P --> Q[Reassess student state with new result]
  Q --> Z
```
</details>

## 5. Component Diagram

![5. Component Diagram](diagrams/05_component.png)

<details><summary>Mermaid source</summary>

```mermaid
flowchart LR
  subgraph FE[React frontend · Vite · Recharts]
    P1[Login] --- P2[Student dashboard] --- P3[Intervention + follow-up]
    P4[Faculty dashboard] --- P5[Student details] --- P6[History]
    P7[Admin interface] --- P8[Analytics]
    APIC[api.js · bearer token]
  end
  subgraph BE[FastAPI backend]
    R1[auth router]:::r
    R2[students router]:::r
    R3[records router]:::r
    R4[interventions router]:::r
    R5[dashboard router]:::r
    R6[admin router]:::r
    SEC[security · bcrypt + JWT + RBAC]
    SVC[engine.service · cycle orchestration]
    AUD[audit + config service]
  end
  subgraph ML[ML / adaptive layer · scikit-learn · NumPy]
    FEAT[ml.features · feature construction]
    RFM[ml.state_model · Random Forest]
    ELIG[engine.eligibility · rules]
    LINTS[engine.thompson · linear TS]
    REW[engine.reward · response evaluation]
  end
  DB[(PostgreSQL)]
  MODEL[[models/state_model.joblib<br/>model_card.json]]
  APIC -- REST/JSON --> R1 & R2 & R3 & R4 & R5 & R6
  R1 & R2 & R3 & R4 & R5 & R6 --> SEC
  R2 & R4 --> SVC
  SVC --> FEAT & RFM & ELIG & LINTS & REW
  RFM --> MODEL
  SVC & R3 & R5 & R6 & AUD --> DB
  classDef r fill:#eaeefe,stroke:#3b5bdb
```
</details>

## 6. Deployment Diagram

![6. Deployment Diagram](diagrams/06_deployment.png)

Intended production layout. In development the Vite dev server serves the frontend and proxies `/api` to Uvicorn.

<details><summary>Mermaid source</summary>

```mermaid
flowchart LR
  subgraph Client[User device]
    BR[Web browser]
  end
  subgraph Web[Web server · e.g. Nginx]
    STATIC[React build · static files<br/>frontend/dist]
    PROXY[Reverse proxy /api → :8000<br/>HTTPS termination]
  end
  subgraph App[Application server · Python 3.11+]
    UV[Uvicorn / Gunicorn workers]
    FAST[FastAPI app]
    ART[[Model artifact<br/>state_model.joblib]]
  end
  subgraph Data[Database server]
    PG[(PostgreSQL 14+<br/>edupulse DB)]
  end
  BR -- HTTPS --> STATIC
  BR -- HTTPS /api --> PROXY --> UV --> FAST
  FAST -- loads at startup --> ART
  FAST -- SQLAlchemy / psycopg2 · TCP 5432 --> PG
```
</details>

## 7. System Architecture Diagram

![7. System Architecture Diagram](diagrams/07_architecture.png)

<details><summary>Mermaid source</summary>

```mermaid
flowchart TB
  U[Student / Faculty / Admin browser] --> FE[React.js frontend]
  FE -->|REST + JWT| API[FastAPI backend · auth, validation, RBAC]
  API --> S1
  subgraph SVC[Application services]
    S1[1 · Student-state estimation<br/>Random Forest] --> S2[2 · Intervention eligibility<br/>configurable rules]
    S2 --> S3[3 · Adaptive selection<br/>linear Thompson sampling]
    S3 --> S4[4 · Delivery<br/>resources, practice, plans, faculty]
    S4 --> S5[5 · Response evaluation<br/>g, e, reward, category]
    S5 --> S6[6 · Policy update<br/>A += xxᵀ, b += r·x]
    S5 --> S7[7 · State reassessment]
    S6 -.next selection.-> S3
    S7 -.next selection.-> S2
  end
  S1 & S2 & S3 & S5 & S6 & S7 <--> DB[(PostgreSQL<br/>records · states · interventions ·<br/>responses · policy versions · audit)]
  API --> DASH[Dashboard + analytics queries] --> DB
```
</details>

## 8. Database ER Diagram

![8. Database ER Diagram](diagrams/08_er.png)

Key columns shown for the central tables; full definitions in `backend/app/models.py`.

<details><summary>Mermaid source</summary>

```mermaid
erDiagram
  users ||--o| student_profiles : has
  users ||--o| faculty_profiles : has
  faculty_profiles ||--o{ faculty_student_assignments : supervises
  student_profiles ||--o{ faculty_student_assignments : "assigned to"
  topics ||--o{ assessments : covers
  topics ||--o{ assignments : covers
  assessments ||--o{ student_assessment_results : "results of"
  student_profiles ||--o{ student_assessment_results : earns
  student_profiles ||--o{ attendance_records : has
  assignments ||--o{ student_assignment_records : "status of"
  student_profiles ||--o{ student_assignment_records : has
  student_profiles ||--o{ learning_activity_records : does
  student_profiles ||--o{ student_states : "estimated as"
  intervention_types ||--o{ learning_resources : provides
  student_profiles ||--o{ intervention_assignments : receives
  intervention_types ||--o{ intervention_assignments : "type of"
  learning_resources |o--o{ intervention_assignments : delivers
  student_states ||--o{ intervention_assignments : "basis of"
  policy_versions ||--o{ intervention_assignments : "selected under"
  intervention_assignments ||--o| intervention_responses : "measured by"
  intervention_assignments ||--o{ learning_activity_records : produces
  policy_versions ||--o{ policy_parameters : contains
  intervention_types ||--o{ policy_parameters : "arm of"
  intervention_assignments ||--o| policy_updates : triggers
  users ||--o{ audit_logs : performs

  users { int id PK
    string email UK
    string password_hash
    string role
    bool is_active }
  student_profiles { int id PK
    int user_id FK
    string roll_number UK
    float previous_result_pct }
  student_states { int id PK
    int student_id FK
    string state
    json features
    json probabilities
    string model_version
    timestamp created_at }
  intervention_assignments { int id PK
    int student_id FK
    int intervention_type_id FK
    int student_state_id FK
    int policy_version_id FK
    json context
    json eligible
    json sampled_scores
    int rng_seed
    json pre_indicators
    string status }
  intervention_responses { int id PK
    int assignment_id FK,UK
    json post_indicators
    float learning_gain
    float engagement_change
    float reward
    string category }
  policy_versions { int id PK
    int version UK
    float lam
    float v
    json feature_names }
  policy_parameters { int id PK
    int policy_version_id FK
    int intervention_type_id FK
    json A
    json b
    int n_observations }
  policy_updates { int id PK
    int assignment_id FK,UK
    int from_version_id FK
    int to_version_id FK
    float reward
    json context_vector }
```
</details>
