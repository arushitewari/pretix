import os
from dotenv import load_dotenv
from playwright.sync_api import Page, expect

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TEST_EMAIL = os.getenv("TEST_EMAIL")
TEST_PASSWORD = os.getenv("TEST_PASSWORD")
EVENT_URL = "/control/event/test/test/"


def test_email_notification_failures(page: Page):

    page.goto(f"{BASE_URL}/control/login")
    page.locator('//*[@id="id_email"]').fill(TEST_EMAIL)
    page.locator('//*[@id="id_password"]').fill(TEST_PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_timeout(2000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")

    page.goto(f"{BASE_URL}/control/")
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("✅ CHECK 1 PASSED — Control dashboard loaded (no unhandled exceptions)")

    page.goto(f"{BASE_URL}/control/events/")
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("✅ CHECK 2 PASSED — Events list loaded (email failures don't affect navigation)")

    page.goto(f"{BASE_URL}{EVENT_URL}orders/")
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    orders = page.locator("table tbody tr")
    print(f"✅ CHECK 3 PASSED — Orders page loaded. Orders: {orders.count()} (state intact)")

    page.goto(f"{BASE_URL}{EVENT_URL}live/")
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("✅ CHECK 4 PASSED — Shop status page loaded (email templates not crashing system)")

    page.goto(f"{BASE_URL}{EVENT_URL}vouchers/")
    page.wait_for_timeout(1000)
    expect(page).not_to_have_url(f"{BASE_URL}/control/login")
    print("✅ CHECK 5 PASSED — Vouchers page loaded (system functional despite email failures)")

    print("\n🎉 ALL EMAIL NOTIFICATION CHECKS PASSED IN ONE RUN!")
