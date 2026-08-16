import pytest
from playwright.sync_api import Page, expect


@pytest.mark.critical
@pytest.mark.reliability
def test_stable_checkout_confirms_on_first_attempt(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/?scenario=stable")
    page.get_by_role("button", name="Complete order").click()

    expect(page.get_by_text("Order confirmed", exact=True)).to_be_visible()
    expect(page.get_by_text("Confirmation VXP-2048 · attempt 1")).to_be_visible()


@pytest.mark.reliability
def test_transient_checkout_recovers_on_second_attempt(
    page: Page, base_url: str
) -> None:
    page.goto(f"{base_url}/?scenario=transient")
    page.get_by_role("button", name="Complete order").click()
    expect(
        page.get_by_text("Payment service temporarily unavailable", exact=True)
    ).to_be_visible()

    page.get_by_role("button", name="Try checkout again").click()
    expect(page.get_by_text("Order confirmed", exact=True)).to_be_visible()
    expect(page.get_by_text("Confirmation VXP-2048 · attempt 2")).to_be_visible()


@pytest.mark.critical
@pytest.mark.reliability
def test_critical_failure_is_persistent_and_visible(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/?scenario=critical-failure")
    page.get_by_role("button", name="Complete order").click()
    expect(page.get_by_text("Payment authorization failed", exact=True)).to_be_visible()
    expect(page.get_by_text("Attempt 1 preserved as critical-failure")).to_be_visible()

    page.get_by_role("button", name="Try checkout again").click()
    expect(page.get_by_text("Attempt 2 preserved as critical-failure")).to_be_visible()
