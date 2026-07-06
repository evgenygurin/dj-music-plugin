"""Playwright screenshot runner for exported Prefab previews.

Opens each ``artifacts/previews/*.html`` in a headless Chromium and writes
a full-page PNG to ``artifacts/screenshots/*.png``. Bundled HTML fully
inlines React + Prefab renderer, so no network is needed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
PREVIEWS = ROOT / "artifacts" / "previews"
SHOTS = ROOT / "artifacts" / "screenshots"
CHROMIUM = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

PAGES = [
    "set_view",
    "transition_score",
    "library_audit",
    "score_pool_matrix",
    "library_dashboard",
    "camelot_wheel",
    "render_studio",
]


async def _shoot_one(browser, name: str) -> None:
    html = PREVIEWS / f"{name}.html"
    out = SHOTS / f"{name}.png"
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        device_scale_factor=2,
    )
    page = await context.new_page()
    url = html.as_uri()
    await page.goto(url)
    # Wait for Prefab renderer to mount components.
    await page.wait_for_load_state("networkidle", timeout=45_000)
    await page.wait_for_timeout(2500)
    await page.screenshot(path=str(out), full_page=True)
    print(f"[ok] {name}.png  ({out.stat().st_size // 1024} KB)")
    await context.close()


async def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            executable_path=str(CHROMIUM),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        for name in PAGES:
            await _shoot_one(browser, name)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
