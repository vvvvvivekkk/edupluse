"""Create tables and load demo data.

    python -m scripts.seed            # keeps existing data if already seeded
    python -m scripts.seed --reset    # drops and recreates all tables first

Demo data are SYNTHETIC (generated with app/ml/synthetic.py). No intervention history is
invented: every intervention, response and policy update shown in the app comes from
actually running the cycle.
"""
import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.engine import service  # noqa: E402
from app.ml.synthetic import generate_students  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seed_content import INTERVENTION_TYPES, MATERIAL, PRACTICE, TOPICS, study_plan  # noqa: E402

DEMO_PASSWORD_STUDENT = "Student@123"
DEMO_PASSWORD_FACULTY = "Faculty@123"
DEMO_PASSWORD_ADMIN = "Admin@123"
N_STUDENTS = 16

FIRST = ["Aarav", "Diya", "Rohan", "Ananya", "Kiran", "Meera", "Arjun", "Sneha", "Vikram", "Priya",
         "Rahul", "Kavya", "Siddharth", "Lakshmi", "Nikhil", "Ishita", "Varun", "Pooja", "Aditya", "Neha"]
LAST = ["Sharma", "Reddy", "Iyer", "Patel", "Rao", "Nair", "Gupta", "Kumar", "Das", "Menon"]


def ago(days, hours=0):
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours)


def seed(reset=False):
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(models.User).count():
        print("Database already seeded. Use --reset to start over.")
        return
    rng = random.Random(7)

    topics = {}
    for name in TOPICS:
        t = models.Topic(name=name)
        db.add(t)
        db.flush()
        topics[name] = t
    types = {}
    for code, name, desc in INTERVENTION_TYPES:
        it = models.InterventionType(code=code, name=name, description=desc)
        db.add(it)
        db.flush()
        types[code] = it
    for name, t in topics.items():
        url, obj = MATERIAL[name]
        db.add(models.LearningResource(intervention_type_id=types["targeted_material"].id, topic_id=t.id,
                                       title=f"{name}: concept guide", objective=obj, url=url,
                                       instructions="Read the linked material, then try the examples yourself. "
                                                    "Mark the activity complete when you have finished."))
        db.add(models.LearningResource(intervention_type_id=types["targeted_practice"].id, topic_id=t.id,
                                       title=f"{name}: practice set", objective=f"Reinforce {name.lower()}.",
                                       instructions="Answer all questions, then submit.",
                                       content={"questions": PRACTICE[name]}))
        db.add(models.LearningResource(intervention_type_id=types["study_plan"].id, topic_id=t.id,
                                       title=f"7-day plan: {name}", objective="Build consistent study habits.",
                                       instructions="Follow one task per day. Mark complete after day 7.",
                                       content=study_plan(name)))
    db.add(models.LearningResource(intervention_type_id=types["faculty_support"].id, topic_id=None,
                                   title="Faculty consultation", objective="Get targeted guidance from your faculty member.",
                                   instructions="Your faculty member will contact you to schedule a consultation. "
                                                "They mark this complete once it has taken place."))

    admin = models.User(email="admin@edupulse.edu", full_name="System Administrator",
                        password_hash=hash_password(DEMO_PASSWORD_ADMIN), role="admin")
    db.add(admin)
    faculty = []
    for i, (name, dept) in enumerate([("Dr. Ravi Kumar", "CSE"), ("Dr. Anita Desai", "AI & ML")], 1):
        u = models.User(email=f"faculty{i}@edupulse.edu", full_name=name,
                        password_hash=hash_password(DEMO_PASSWORD_FACULTY), role="faculty")
        db.add(u)
        db.flush()
        fp = models.FacultyProfile(user_id=u.id, department=dept)
        db.add(fp)
        db.flush()
        faculty.append(fp)

    assignments = []
    for k, name in enumerate(TOPICS):
        a = models.Assignment(title=f"Assignment {k + 1}: {name}", topic_id=topics[name].id,
                              due_date=date.today() - timedelta(days=28 - 6 * k))
        db.add(a)
        db.flush()
        assignments.append(a)
    quiz_topics = TOPICS[:4]
    quizzes = {}
    for k, name in enumerate(quiz_topics):
        q = models.Assessment(title=f"Quiz {k + 1}: {name}", topic_id=topics[name].id, kind="quiz",
                              max_score=20, held_on=date.today() - timedelta(days=26 - 7 * k))
        db.add(q)
        db.flush()
        quizzes[name] = q

    pw_hash = hash_password(DEMO_PASSWORD_STUDENT)
    df = generate_students(N_STUDENTS, seed=2026).reset_index(drop=True)
    # make student1 a clear demo case: weak in Recursion, average elsewhere, lower engagement
    df.loc[0, ["avg_score", "latest_score", "attendance_pct", "assignment_completion_pct",
               "practice_accuracy_pct", "previous_result_pct"]] = [52, 38, 70, 60, 45, 58]
    for i, row in df.iterrows():
        name = f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}"
        u = models.User(email=f"student{i + 1}@edupulse.edu", full_name=name, password_hash=pw_hash, role="student")
        db.add(u)
        db.flush()
        prev = row["previous_result_pct"]
        sp = models.StudentProfile(user_id=u.id, roll_number=f"EP26{i + 1:03d}", program="B.Tech CSE", year=2,
                                   previous_result_pct=None if prev != prev else float(prev))
        db.add(sp)
        db.flush()
        db.add(models.FacultyStudentAssignment(faculty_id=faculty[i % 2].id, student_id=sp.id))

        avg = row["avg_score"]
        for k, tname in enumerate(quiz_topics):
            target = row["latest_score"] if k == len(quiz_topics) - 1 else avg + rng.uniform(-8, 8)
            pct = max(0.0, min(100.0, float(target)))
            raw = round(pct / 100 * 20 * 2) / 2
            db.add(models.StudentAssessmentResult(student_id=sp.id, assessment_id=quizzes[tname].id,
                                                  raw_score=raw, score_pct=round(100 * raw / 20, 2),
                                                  recorded_at=ago(26 - 7 * k)))
        att = row["attendance_pct"]
        if att == att:
            for w in range(4):
                total = 5
                attended = max(0, min(total, round(total * float(att) / 100 + rng.uniform(-0.6, 0.6))))
                db.add(models.AttendanceRecord(student_id=sp.id, period_start=date.today() - timedelta(days=28 - 7 * w),
                                               period_end=date.today() - timedelta(days=22 - 7 * w),
                                               sessions_attended=attended, sessions_total=total,
                                               recorded_at=ago(22 - 7 * w)))
        comp = row["assignment_completion_pct"]
        if comp == comp:
            for k, a in enumerate(assignments[:4]):
                p = float(comp) / 100
                status = "submitted" if rng.random() < p else ("late" if rng.random() < 0.3 else "missing")
                db.add(models.StudentAssignmentRecord(student_id=sp.id, assignment_id=a.id, status=status,
                                                      recorded_at=ago(27 - 6 * k)))
        prac = row["practice_accuracy_pct"]
        if prac == prac:
            for k, tname in enumerate(quiz_topics[:3]):
                attempted = 10
                correct = max(0, min(attempted, round(attempted * float(prac) / 100 + rng.uniform(-1, 1))))
                db.add(models.LearningActivityRecord(student_id=sp.id, topic_id=topics[tname].id,
                                                     questions_attempted=attempted, questions_correct=correct,
                                                     recorded_at=ago(24 - 7 * k)))
    db.flush()
    service.current_policy_version(db)  # creates policy v1 (priors)
    for sp in db.query(models.StudentProfile).all():
        service.estimate_state(db, sp.id, admin.id)
    db.commit()
    print(f"Seeded {N_STUDENTS} students, 2 faculty, 1 admin, policy v1.")
    print(f"  admin@edupulse.edu / {DEMO_PASSWORD_ADMIN}")
    print(f"  faculty1@edupulse.edu, faculty2@edupulse.edu / {DEMO_PASSWORD_FACULTY}")
    print(f"  student1..{N_STUDENTS}@edupulse.edu / {DEMO_PASSWORD_STUDENT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    seed(ap.parse_args().reset)
