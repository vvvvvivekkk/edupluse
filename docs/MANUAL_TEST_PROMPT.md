# Manual test prompt

Paste the text below into Claude Code (with Claude in Chrome connected) on the machine where the
project runs. It updates the project, resets the demo data, walks through a brand-new student and a
teacher in the browser, and then checks the result against the requirements.

---

```text
Test the EduPulse project end to end in the browser and check it against the requirements.

SETUP
1. In the project folder, run: git pull
2. Activate the backend virtual environment and run: pip install -r backend/requirements.txt
   (a new package, python-dotenv, was added - backend/.env now loads automatically).
3. Stop any running backend/frontend servers. In backend/, run: python -m scripts.seed --reset
4. Start the backend (cd backend; uvicorn app.main:app --port 8000) and the frontend
   (cd frontend; npm run dev). Confirm http://localhost:8000/api/health returns {"status":"ok"}.

Note: students cannot sign themselves up. Per the brief (section 3.3) only the admin creates
accounts, so "registering a new student" means the admin creates the account.

PART A - ADMIN REGISTERS A NEW STUDENT  (http://localhost:5173)
1. Log in as admin@edupulse.edu / Admin@123.
2. Users tab -> create: Full name "Test Student", Email newstudent@edupulse.edu,
   Initial password NewStudent@1, Role Student, Roll number EP26100. Click Create.
   EXPECT: "User created." and the new row in the table.
3. Faculty assignments tab -> Faculty "Dr. Ravi Kumar", Student "Test Student" -> Assign.
   EXPECT: "Assigned." Log out.

PART B - NEW STUDENT WITH NO DATA
1. Log in as newstudent@edupulse.edu / NewStudent@1.
   EXPECT: dashboard opens; every indicator says "no data"; Academic state says "No state estimate yet".
2. Click "Get my next recommendation".
   EXPECT: a red message saying the required indicator "Latest assessment score" is missing.
   This is correct: the system refuses to guess without data. Log out.

PART C - TEACHER ADDS DATA AND SELECTS SUPPORT
1. Log in as faculty1@edupulse.edu / Faculty@123.
   EXPECT: "Test Student" appears in the Students table.
2. Open Test Student -> "Add academic record" -> Show form.
   a. Record type "Assessment result": title "Quiz 4: Recursion", Topic Recursion,
      Score 25, Out of 20 -> Save. EXPECT: error "raw_score cannot exceed max_score".
   b. Change Score to 8 -> Save. EXPECT: green "Record saved".
   c. Record type "Attendance": any From/To dates in the last two weeks, Sessions attended 3,
      Total sessions 5 -> Save. EXPECT: green "Record saved".
3. Click "Re-estimate state". EXPECT: a state badge (likely "High Support Need") with
   percentages and reasons.
4. Click "Select next intervention". EXPECT: an intervention page with "Why this was selected",
   a "Sampled scores" table and a context vector. Note which intervention was chosen.
5. Go back and try "Select next intervention" again.
   EXPECT: it is disabled / refused because an intervention is already open. Log out.

PART D - STUDENT COMPLETES THE INTERVENTION
1. Log in as the new student. Click "Open activity".
   - Practice questions: answer all and submit. Material or study plan: "Mark as completed".
   - If it is Faculty Support: EXPECT the student cannot complete it ("Your faculty member marks
     this complete"). Log in as faculty1, open the student, "View / update" -> "Mark consultation
     held", then log back in as the student and click "Submit follow-up assessment".
2. Enter follow-up score 65 -> "Submit and evaluate".
   EXPECT: Before/After scores, learning gain, reward, a response category (Positive / Partial /
   No Improvement), "Policy updated vX -> vY" and a reassessed state.
3. Try to submit the follow-up again (refresh the page). EXPECT: no form, or an error saying a
   response was already recorded. Log out.

PART E - TEACHER CHECKS THE RESULT
1. Log in as faculty1. Open Test Student.
   EXPECT: intervention history row with status "evaluated", Before 40%, After 65%, a category;
   the before/after chart shows the change.
2. Open Analytics. EXPECT: charts reflect the new outcome; the "Effectiveness by intervention type"
   table says "insufficient data" (fewer than 30 outcomes).
3. Try to open http://localhost:5173/students/2 . EXPECT: "You are not authorised to view this student"
   (student 2 belongs to the other teacher).

PART F - ADMIN CHECKS
1. Log in as admin. Policy tab: EXPECT the policy version increased and a new row in
   "Policy-update history". Audit log tab: EXPECT entries for create_user, create_academic_record,
   assign_intervention, record_response, policy_update.

PART G - REQUIREMENTS CHECK
1. Read docs/REQUIREMENTS_CHECKLIST.md and the original brief
   docs/EDUPULSE_Project_Brief_Requirements.docx.
2. For each section, confirm what you saw in Parts A-F matches the checklist. Flag anything
   marked as met that you could not confirm, and anything in the brief the checklist misses.
3. Run the automated tests too: cd backend; python -m pytest -q  (expect 54 passed).

REPORT
Give me a short table: each Part (A-G), pass or fail, and what was different from EXPECT if it
failed. Take a screenshot at the end of Parts B, C, D and E. Do not change any code - only report.
```
