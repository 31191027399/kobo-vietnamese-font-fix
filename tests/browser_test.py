from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


output = Path(os.environ.get("BROWSER_TEST_SCREENSHOT", "/tmp/kobo-installer-simple.png"))
base_url = os.environ.get("BROWSER_TEST_URL", "http://127.0.0.1:8765/")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    errors = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    page.get_by_role("heading", name="Kobo Vietnamese Installer").wait_for()
    page.get_by_text("Kobo ready").wait_for()
    assert "Firmware 4.38.23697" in page.locator("#device-detail").inner_text()
    assert "20 fonts" in page.locator("#build-facts").inner_text()
    assert page.get_by_role("button", name="Install Vietnamese support").is_enabled()
    assert page.locator("#action-phase").inner_text() == "Ready"
    assert page.locator("#action-percent").inner_text() == "0%"
    page.select_option("#language-select", "vi")
    assert page.locator("h1").inner_text() == "Bộ cài tiếng Việt cho Kobo"
    assert page.get_by_role("button", name="Cài hỗ trợ tiếng Việt").is_enabled()
    assert page.locator("#action-phase").inner_text() == "Sẵn sàng"
    page.select_option("#language-select", "en")
    assert page.locator("h1").inner_text() == "Kobo Vietnamese Installer"
    assert page.get_by_text("Advanced options").is_visible()
    page.get_by_text("Advanced options").click()
    assert page.get_by_text("Vietnamese language pack", exact=True).is_visible()
    assert page.get_by_text("Adds Extra: vi to Kobo’s Language and dictionaries list", exact=False).is_visible()
    assert page.get_by_text("KOReader dictionary", exact=True).is_visible()
    assert page.get_by_text("Repair a KoboRoot.tgz only").is_visible()
    assert page.get_by_role("button", name="Repair KoboRoot.tgz only").is_disabled()
    page.screenshot(path=str(output), full_page=True)
    assert not errors, errors
    browser.close()
