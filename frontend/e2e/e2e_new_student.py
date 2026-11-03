"""End-to-end test: a brand-new student, from account creation to an evaluated intervention.

Flow: admin creates the student and assigns a faculty member -> student logs in (no data yet,
recommendation is correctly refused) -> faculty adds marks + attendance, re-estimates state and
selects an intervention -> student completes it and submits a follow-up -> faculty sees the outcome.

Prerequisites: API on :8000 with freshly seeded data, Vite dev server on :5173.
    python e2e/e2e_new_student.py        # screenshots: ../docs/screenshots/new_student_*.png
"""
import sys
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[1].parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
NAME, EMAIL, PASSWORD, ROLL = "Test Student", "newstudent@edupulse.edu", "NewStudent@1", "EP26100"
errors = []


def login(page, email, pw):
    page.goto(f"{BASE}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(pw)
    page.get_by_role("button", name="Sign in").click()


def logout(page):
    page.get_by_role("button", name="Log out").click()
    page.wait_for_url(f"{BASE}/login")


def shot(page, name):
    page.add_style_tag(content=".topbar{position:static !important}")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / f"new_student_{name}.png"), full_page=True)
    print("  screenshot", name)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))

    print("1. Admin creates the student account and assigns a faculty member")
    login(page, "admin@edupulse.edu", "Admin@123")
    page.wait_for_url(f"{BASE}/admin")
    page.get_by_role("tab", name="Users").click()
    page.get_by_label("Full name").fill(NAME)
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Initial password").fill(PASSWORD)
    page.locator("form.record-form").get_by_label("Role").select_option("student")
    page.get_by_label("Roll number").fill(ROLL)
    page.get_by_role("button", name="Create").click()
    expect(page.locator(".alert.ok")).to_contain_text("User created")
    expect(page.get_by_role("cell", name=EMAIL)).to_be_visible()
    shot(page, "01_admin_created")
    page.get_by_role("tab", name="Faculty assignments").click()
    page.get_by_label("Faculty").select_option(label="Dr. Ravi Kumar")
    page.get_by_label("Student").select_option(label=NAME)
    page.get_by_role("button", name="Assign").click()
    expect(page.locator(".alert.ok")).to_contain_text("Assigned")
    logout(page)

    print("2. New student logs in - no records yet, so no recommendation is possible")
    login(page, EMAIL, PASSWORD)
    page.wait_for_url(f"{BASE}/student")
    expect(page.get_by_text("No state estimate yet")).to_be_visible()
    page.get_by_role("button", name="Get my next recommendation").click()
    expect(page.locator(".alert.error")).to_contain_text("required indicator")
    shot(page, "02_student_no_data")
    logout(page)

    print("3. Faculty adds marks and attendance, estimates state, selects an intervention")
    login(page, "faculty1@edupulse.edu", "Faculty@123")
    page.wait_for_url(f"{BASE}/faculty")
    page.locator("table").get_by_role("link", name=NAME).click()
    page.wait_for_selector("text=Estimated academic state")
    page.get_by_role("button", name="Show form").click()
    page.get_by_label("Assessment title").fill("Quiz 4: Recursion")
    page.get_by_label("Topic").select_option(label="Recursion")
    page.get_by_label("Score", exact=True).fill("8")
    page.get_by_label("Out of").fill("20")
    page.get_by_role("button", name="Save record").click()
    expect(page.locator(".alert.ok")).to_be_visible()
    page.get_by_label("Record type").select_option("attendance")
    page.get_by_label("From", exact=True).fill((date.today() - timedelta(days=13)).isoformat())
    page.get_by_label("To", exact=True).fill((date.today() - timedelta(days=7)).isoformat())
    page.get_by_label("Sessions attended").fill("3")
    page.get_by_label("Total sessions").fill("5")
    page.get_by_role("button", name="Save record").click()
    expect(page.locator(".alert.ok")).to_be_visible()
    page.get_by_role("button", name="Re-estimate state").click()
    expect(page.locator(".alert.info")).to_contain_text("re-estimated")
    shot(page, "03_faculty_added_records")
    page.get_by_role("button", name="Select next intervention").click()
    page.wait_for_url("**/interventions/*")
    page.wait_for_selector("text=Sampled scores")
    shot(page, "04_faculty_view_of_selection")
    logout(page)

    print("4. Student completes the intervention and submits the follow-up")
    login(page, EMAIL, PASSWORD)
    page.wait_for_url(f"{BASE}/student")
    page.get_by_role("link", name="Open activity").click()
    page.wait_for_selector("text=Why this was selected")
    if page.locator(".quiz fieldset").count():
        for fs in page.locator(".quiz fieldset").all():
            fs.locator("input[type=radio]").first.check()
        page.get_by_role("button", name="Submit practice answers").click()
    elif page.get_by_role("button", name="Mark as completed").count():
        page.get_by_role("button", name="Mark as completed").click()
    else:
        # Faculty support was selected: the student sees it but cannot mark it complete.
        expect(page.get_by_text("Your faculty member marks this complete")).to_be_visible()
        shot(page, "04b_student_sees_faculty_support")
        print("   faculty support chosen -> teacher marks the consultation as held")
        logout(page)
        login(page, "faculty1@edupulse.edu", "Faculty@123")
        page.locator("table").get_by_role("link", name=NAME).click()
        page.get_by_role("link", name="View / update").click()
        page.get_by_role("button", name="Mark consultation held").click()
        page.wait_for_selector("text=Follow-up assessment")
        logout(page)
        login(page, EMAIL, PASSWORD)
        page.get_by_role("link", name="Submit follow-up assessment").click()
    page.wait_for_selector("text=Follow-up assessment")
    page.get_by_label("Follow-up score (%)").fill("65")
    page.get_by_role("button", name="Submit and evaluate").click()
    page.wait_for_selector("text=Policy updated")
    shot(page, "05_student_evaluated")
    logout(page)

    print("5. Faculty checks the outcome")
    login(page, "faculty1@edupulse.edu", "Faculty@123")
    page.locator("table").get_by_role("link", name=NAME).click()
    page.wait_for_selector("text=Intervention history")
    expect(page.locator("table").last).to_contain_text("evaluated")
    shot(page, "06_faculty_sees_outcome")
    browser.close()

print("page errors:", errors or "none")
print("NEW-STUDENT FLOW PASSED" if not errors else "FAILED")
sys.exit(1 if errors else 0)
