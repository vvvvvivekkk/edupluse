"""End-to-end test: bulk CSV import, audited record correction, role assignment and username login.

Flow: faculty checks a CSV with errors (nothing imported) -> fixes it and imports -> corrects a mistaken
quiz score with a reason -> admin changes a user's role and sees both operations in the audit log ->
a student signs in with their roll number as username.

Prerequisites: API on :8000 with freshly seeded data, Vite dev server on :5173.
    python e2e/e2e_records_admin.py      # screenshots: ../docs/screenshots/records_*.png
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[1].parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
HEADER = ("roll_number,record_type,assessment_title,topic,raw_score,max_score,period_start,period_end,"
          "sessions_attended,sessions_total,assignment,status,questions_attempted,questions_correct\n")
GOOD = ("EP26001,assessment_result,Quiz 5: Object-Oriented Basics,Object-Oriented Basics,13,20,,,,,,,,\n"
        "EP26003,attendance,,,,,2026-10-20,2026-10-26,4,5,,,,\n"
        "EP26001,practice,,Recursion,,,,,,,,,10,6\n")
BAD = GOOD + ("EP26001,assessment_result,Quiz 6,Loops,25,20,,,,,,,,\n"
              "EP26002,attendance,,,,,2026-10-20,2026-10-26,4,5,,,,\n")
errors = []


def csv_file(name, text):
    p = Path(tempfile.gettempdir()) / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def login(page, ident, pw):
    page.goto(f"{BASE}/login")
    page.get_by_label("Email or username").fill(ident)
    page.get_by_label("Password").fill(pw)
    page.get_by_role("button", name="Sign in").click()


def logout(page):
    page.get_by_role("button", name="Log out").click()
    page.wait_for_url(f"{BASE}/login")


def shot(page, name):
    page.add_style_tag(content=".topbar{position:static !important}")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / f"records_{name}.png"), full_page=True)
    print("  screenshot", name)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))

    print("1. Faculty checks a CSV with errors: rows are reported, nothing can be imported")
    login(page, "faculty1@edupulse.edu", "Faculty@123")
    page.wait_for_url(f"{BASE}/faculty")
    card = page.locator("section.card", has_text="Import academic records (CSV)")
    card.get_by_role("button", name="Show").click()
    page.get_by_label("CSV file").set_input_files(csv_file("edupulse_bad.csv", HEADER + BAD))
    page.get_by_role("button", name="Check file").click()
    expect(page.get_by_role("status")).to_contain_text("5 rows checked: 3 valid, 2 with errors")
    expect(card.get_by_role("cell", name="raw_score cannot exceed max_score")).to_be_visible()
    expect(card.get_by_role("cell", name="you are not authorised to add records for this student")).to_be_visible()
    expect(page.get_by_role("button", name="Import")).to_be_disabled()
    shot(page, "01_import_errors")

    print("2. Faculty fixes the file and imports it")
    page.get_by_label("CSV file").set_input_files(csv_file("edupulse_good.csv", HEADER + GOOD))
    page.get_by_role("button", name="Check file").click()
    page.get_by_role("button", name="Import 3 records").click()
    expect(card.locator(".alert.ok").last).to_contain_text("Imported 3 records for 2 student(s)")
    shot(page, "02_import_done")

    print("3. Faculty corrects a mistaken quiz score (with a reason); the state is re-estimated")
    page.locator("table").get_by_role("link", name="Aarav Sharma").click()
    page.wait_for_selector("text=Estimated academic state")
    records = page.locator("section.card", has_text="Academic records (")
    records.get_by_role("button", name="Show / correct").click()
    row = records.locator("tr", has_text="Quiz 5: Object-Oriented Basics")
    expect(row).to_contain_text("13/20")
    row.get_by_role("button", name="Correct").click()
    records.get_by_label("Score").fill("17")
    records.get_by_label("Reason for correction").fill("Marking error found on re-check")
    records.get_by_role("button", name="Save correction").click()
    expect(records.locator(".alert.ok")).to_contain_text("Record corrected")
    expect(records.locator("tr", has_text="Quiz 5: Object-Oriented Basics")).to_contain_text("17/20")
    shot(page, "03_record_corrected")
    logout(page)

    print("4. Admin creates a user, then assigns them the faculty role; audit log shows everything")
    login(page, "admin@edupulse.edu", "Admin@123")
    page.wait_for_url(f"{BASE}/admin")
    page.get_by_role("tab", name="Users").click()
    page.get_by_label("Full name").fill("Lab Assistant")
    page.get_by_label("Email").fill("lab@edupulse.edu")
    page.get_by_label("Initial password").fill("LabAssist@1")
    page.locator("form.record-form").get_by_label("Role").select_option("admin")
    page.get_by_role("button", name="Create").click()
    expect(page.locator(".alert.ok")).to_contain_text("User created")
    page.get_by_label("Role of Lab Assistant").select_option("faculty")
    page.get_by_placeholder("Department").fill("Labs")
    page.get_by_role("button", name="Apply").click()
    expect(page.locator(".alert.ok")).to_contain_text("Lab Assistant is now faculty")
    expect(page.locator("tr", has_text="lab@edupulse.edu")).to_contain_text("faculty")
    shot(page, "04_role_changed")
    page.get_by_role("tab", name="Audit log").click()
    for action in ("correct_academic_record", "import_academic_records", "update_user"):
        expect(page.get_by_role("cell", name=action, exact=True).first).to_be_visible()
    shot(page, "05_audit_log")
    logout(page)

    print("5. A student signs in with their roll number as username")
    login(page, "EP26002", "Student@123")
    page.wait_for_url(f"{BASE}/student")
    expect(page.get_by_role("link", name="My dashboard")).to_be_visible()
    browser.close()

print("page errors:", errors or "none")
print("RECORDS/ADMIN FLOW PASSED" if not errors else "FAILED")
sys.exit(1 if errors else 0)
