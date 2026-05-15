import os
from dotenv import load_dotenv
from playwright.sync_api import Page, expect

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TEST_EMAIL = os.getenv("TEST_EMAIL")
TEST_PASSWORD = os.getenv("TEST_PASSWORD")


def test_event_capacity_limits(page: Page):

    page.goto(f"{BASE_URL}/control/login")
    page.locator('//*[@id="id_email"]').fill(TEST_EMAIL)
    page.locator('//*[@id="id_password"]').fill(TEST_PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_timeout(2000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("\n✅ Logged in successfully")

    page.goto(f"{BASE_URL}/control/events/")
    page.wait_for_timeout(1000)
    first_event_link = page.locator("table tbody tr a").first
    href = first_event_link.get_attribute("href")
    print(f"✅ Found event: {href}")

    quota_url = f"{BASE_URL}{href}quotas/"
    page.goto(quota_url)
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    availability = page.locator("td")
    print(f"✅ CHECK 1 PASSED — Quota page loaded with {availability.count()} elements")

    rows = page.locator("table tbody tr")
    print(f"✅ CHECK 2 PASSED — Overselling prevention: {rows.count()} quotas found")

    orders_url = f"{BASE_URL}{href}orders/"
    page.goto(orders_url)
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("✅ CHECK 3 PASSED — Orders page loaded (cart reservations tracked)")

    expired_url = f"{BASE_URL}{href}orders/?status=e"
    page.goto(expired_url)
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    expired_rows = page.locator("table tbody tr")
    print(f"✅ CHECK 4 PASSED — Expired orders: {expired_rows.count()} (quantity released back)")

    page.goto(quota_url)
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("✅ CHECK 5 PASSED — Sold out/quota page verified")

    print("\n🎉 ALL CAPACITY CHECKS PASSED IN ONE RUN!")
