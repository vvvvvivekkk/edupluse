"""End-to-end UI test of the full cycle in a real (headless) browser.

Prerequisites: API on :8000 with freshly seeded data, Vite dev server on :5173.
    pip install playwright && python -m playwright install chromium
    python e2e/e2e_cycle.py            # screenshots go to ../docs/screenshots
"""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
errors = []


def login(page, email, pw):
    page.goto(f"{BASE}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(pw)
    page.get_by_role("button", name="Sign in").click()


def shot(page, name):
    page.add_style_tag(content=".topbar{position:static !important}")
    page.wait_for_timeout(1800)  # let chart animations finish
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # wrong password -> error message
    login(page, "student1@edupulse.edu", "wrong")
    expect(page.get_by_role("alert")).to_contain_text("Incorrect")
    shot(page, "01_login_error")

    # ---- student: full cycle
    login(page, "student1@edupulse.edu", "Student@123")
    expect(page).to_have_url(f"{BASE}/student")
    expect(page.get_by_text("Academic state")).to_be_visible()
    shot(page, "02_student_dashboard")
    page.get_by_role("button", name="Get my next recommendation").click()
    page.wait_for_url("**/interventions/*")
    page.wait_for_selector("text=Why this was selected")
    shot(page, "03_intervention_assigned")
    # complete whatever was selected
    if page.locator(".quiz fieldset").count():
        for fs in page.locator(".quiz fieldset").all():
            fs.locator("input[type=radio]").nth(1).check()
        page.get_by_role("button", name="Submit practice answers").click()
    else:
        page.get_by_role("button", name="Mark as completed").click()
    page.wait_for_selector("text=Follow-up assessment")
    page.get_by_label("Follow-up score (%)").fill("72")
    page.get_by_role("button", name="Submit and evaluate").click()
    page.wait_for_selector("text=Policy updated")
    shot(page, "04_response_evaluated")
    page.get_by_role("link", name="Back to dashboard").click()
    page.wait_for_selector("text=Before and after each intervention")
    shot(page, "05_student_dashboard_after")
    page.get_by_role("link", name="History").first.click()
    page.wait_for_selector("text=Intervention history")
    shot(page, "06_history")
    page.get_by_role("button", name="Log out").click()

    # ---- faculty
    login(page, "faculty1@edupulse.edu", "Faculty@123")
    page.wait_for_url(f"{BASE}/faculty")
    page.wait_for_selector("text=State distribution")
    shot(page, "07_faculty_dashboard")
    page.locator("table a").first.click()
    page.wait_for_selector("text=Estimated academic state")
    shot(page, "08_student_detail")
    page.get_by_role("button", name="Show form").click()
    page.get_by_label("Assessment title").fill("Quiz 5: OOP")
    page.locator("select").nth(1).select_option(label="Object-Oriented Basics")
    page.get_by_label("Score").fill("25")
    page.get_by_label("Out of").fill("20")
    page.get_by_role("button", name="Save record").click()
    expect(page.locator(".alert.error")).to_contain_text("cannot exceed")   # validation shown in UI
    page.get_by_label("Score").fill("14")
    page.get_by_role("button", name="Save record").click()
    expect(page.locator(".alert.ok")).to_be_visible()
    page.goto(f"{BASE}/analytics")
    page.wait_for_selector("text=Effectiveness by intervention type")
    shot(page, "09_analytics")
    # student URL access control: faculty1 must not open a faculty2 student
    page.goto(f"{BASE}/students/2")
    expect(page.get_by_role("alert")).to_contain_text("not authorised")
    page.get_by_role("button", name="Log out").click()

    # ---- admin
    login(page, "admin@edupulse.edu", "Admin@123")
    page.wait_for_url(f"{BASE}/admin")
    page.wait_for_selector("text=Recent system activity")
    shot(page, "10_admin_overview")
    page.get_by_role("tab", name="Policy").click()
    page.wait_for_selector("text=Policy-update history")
    shot(page, "11_admin_policy")
    page.get_by_role("tab", name="Configuration").click()
    page.wait_for_selector("text=Eligibility rules (JSON)")
    shot(page, "12_admin_config")
    browser.close()

real_errors = [e for e in errors if "status of 4" not in e]  # expected 401/403/422 responses are logged by the browser
print("screenshots:", sorted(x.name for x in OUT.glob("*.png")))
print("console errors:", real_errors or "none")
sys.exit(1 if real_errors else 0)
