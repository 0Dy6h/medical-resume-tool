"""Layout measurement script for the jobs page.

Measures six viewport widths and asserts:
1. Zero horizontal overflow (scrollWidth == clientWidth)
2. Detail panel/drawer right edge within viewport
3. Job column width >= 220px (1440 only)
4. First row cell height <= 111px (1440 only)
5. Drawer closable with Esc + focus returns to trigger row (1440 only)

Self-cleaning: deletes the test account from the database on exit.

Usage (both services must be running):
  cd backend
  uv run --project . python scripts/measure_jobs_layout.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"
CHROMIUM_PATH = r"C:\Users\12035\AppData\Local\ms-playwright\chromium-1228\chrome-win64\chrome.exe"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"
TEST_USERNAME = "qa_layout_probe"
TEST_PASSWORD = "qa_probe_pass_123"
VIEWPORTS = [1280, 1366, 1440, 1536, 1680, 1920]


def register_and_login() -> str:
    """Register a test account and return the JWT token."""
    data = json.dumps(
        {"username": TEST_USERNAME, "password": TEST_PASSWORD}
    ).encode()

    try:
        req = urllib.request.Request(
            f"{BACKEND_URL}/api/auth/register",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            return body["token"]
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        # Already registered — login instead
        req = urllib.request.Request(
            f"{BACKEND_URL}/api/auth/login",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            return body["token"]


def cleanup_test_account() -> None:
    """Delete the test account and all related data from the database."""
    if not DB_PATH.exists():
        print(f"\nCleanup: database not found at {DB_PATH}, skipping.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE username = ?", (TEST_USERNAME,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        print(f"\nCleanup: test account '{TEST_USERNAME}' not found, nothing to delete.")
        return

    user_id = row[0]

    for table in ["job_statuses", "resume_drafts", "subscriptions", "profiles"]:
        cursor.execute(
            f"DELETE FROM {table} WHERE user_id = ?", (user_id,)
        )

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    print(
        f"\nCleanup: deleted test account '{TEST_USERNAME}' "
        f"(user_id={user_id}) from {DB_PATH}"
    )


def measure_viewport(page, width: int) -> dict:
    """Measure layout at the given viewport width."""
    page.set_viewport_size({"width": width, "height": 900})
    page.wait_for_timeout(600)

    is_desktop = width >= 1600

    # Close any open drawer
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    # Ensure table data is loaded
    page.wait_for_selector("table tbody tr[tabindex]", timeout=10000)
    page.wait_for_timeout(300)

    # 1. Zero horizontal overflow
    overflow = page.evaluate(
        """() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
        })"""
    )
    scroll_w = overflow["scrollWidth"]
    client_w = overflow["clientWidth"]
    zero_overflow = scroll_w == client_w

    # 2. Detail not cut off
    if is_desktop:
        detail_right = page.evaluate(
            """() => {
                const el = document.querySelector('.detail-panel');
                if (!el) return null;
                return el.getBoundingClientRect().right;
            }"""
        )
    else:
        # Open drawer by clicking first data row
        page.evaluate(
            "() => { const r = document.querySelector('table tbody tr[tabindex]'); if (r) r.click(); }"
        )
        try:
            page.wait_for_selector(".detail-drawer.open", timeout=5000)
            page.wait_for_timeout(400)
        except Exception:
            pass
        detail_right = page.evaluate(
            """() => {
                const el = document.querySelector('.detail-drawer.open');
                if (!el) return null;
                return el.getBoundingClientRect().right;
            }"""
        )
        # Close drawer for next measurement
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    detail_not_cut = detail_right is not None and detail_right <= width

    # 3 & 4: Only at 1440
    job_col_width = None
    cell_height = None
    if width == 1440:
        job_col_width = page.evaluate(
            """() => {
                const th = document.querySelector('table th');
                if (!th) return null;
                return th.getBoundingClientRect().width;
            }"""
        )
        cell_height = page.evaluate(
            """() => {
                const td = document.querySelector('table tbody tr[tabindex] td');
                if (!td) return null;
                return td.getBoundingClientRect().height;
            }"""
        )

    return {
        "width": width,
        "scroll_w": scroll_w,
        "client_w": client_w,
        "zero_overflow": zero_overflow,
        "detail_right": round(detail_right) if detail_right else None,
        "detail_not_cut": detail_not_cut,
        "job_col_width": round(job_col_width) if job_col_width else None,
        "cell_height": round(cell_height) if cell_height else None,
        "is_desktop": is_desktop,
    }


def test_drawer_esc(page) -> dict:
    """Test that the drawer can be closed with Esc and focus returns to trigger row."""
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(600)
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    page.wait_for_selector("table tbody tr[tabindex]", timeout=10000)
    page.wait_for_timeout(300)

    # Click first data row to open drawer
    page.evaluate(
        "() => { const r = document.querySelector('table tbody tr[tabindex]'); if (r) r.click(); }"
    )
    try:
        page.wait_for_selector(".detail-drawer.open", timeout=5000)
        page.wait_for_timeout(400)
    except Exception:
        return {"drawer_opened": False, "drawer_gone": False, "focus_returned": False}

    drawer_visible = page.evaluate(
        """() => document.querySelector('.detail-drawer.open') !== null"""
    )
    if not drawer_visible:
        return {"drawer_opened": False, "drawer_gone": False, "focus_returned": False}

    # Press Escape
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    drawer_gone = page.evaluate(
        """() => document.querySelector('.detail-drawer.open') === null"""
    )

    focus_returned = page.evaluate(
        """() => {
            const el = document.activeElement;
            if (!el) return false;
            return el.tagName === 'TR' && el.getAttribute('tabindex') === '-1';
        }"""
    )

    return {
        "drawer_opened": True,
        "drawer_gone": drawer_gone,
        "focus_returned": focus_returned,
    }


def test_fixed_positioning(page) -> dict:
    """Test that fixed-position elements are correctly viewport-relative.

    Checks at 1440px viewport:
    1. Drawer bottom <= window.innerHeight
    2. .drawer-body fits viewport and can scroll when content overflows
    3. Create-subscription dialog overlay covers entire viewport
    """
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(600)
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    page.wait_for_selector("table tbody tr[tabindex]", timeout=10000)
    page.wait_for_timeout(300)

    result: dict = {
        "drawer_bottom_ok": False,
        "drawer_scroll_ok": False,
        "dialog_overlay_ok": False,
    }

    # --- 1 & 2: Open drawer, check bottom + body scroll ---
    page.evaluate(
        "() => { const r = document.querySelector('table tbody tr[tabindex]'); if (r) r.click(); }"
    )
    try:
        page.wait_for_selector(".detail-drawer.open", timeout=5000)
        page.wait_for_timeout(400)
    except Exception:
        return result

    drawer_bottom = page.evaluate(
        """() => {
            const el = document.querySelector('.detail-drawer.open');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height) };
        }"""
    )
    vh = page.viewport_size["height"]
    result["drawer_bottom"] = drawer_bottom
    result["vh"] = vh
    result["drawer_bottom_ok"] = (
        drawer_bottom is not None and drawer_bottom["bottom"] <= vh
    )

    scroll_test = page.evaluate(
        """() => {
            const el = document.querySelector('.detail-drawer.open .drawer-body');
            if (!el) return null;
            const vh = window.innerHeight;
            const bodyFits = el.clientHeight <= vh;
            const hasOverflow = el.scrollHeight > el.clientHeight;
            let scrollWorks = true;
            if (hasOverflow) {
                const before = el.scrollTop;
                el.scrollTop = 50;
                scrollWorks = el.scrollTop !== before;
                el.scrollTop = before;
            }
            return {
                clientHeight: Math.round(el.clientHeight),
                scrollHeight: Math.round(el.scrollHeight),
                viewportHeight: vh,
                bodyFitsViewport: bodyFits,
                hasOverflow: hasOverflow,
                scrollWorks: scrollWorks,
            };
        }"""
    )
    result["scroll_test"] = scroll_test
    result["drawer_scroll_ok"] = (
        scroll_test is not None
        and scroll_test["bodyFitsViewport"]
        and (not scroll_test["hasOverflow"] or scroll_test["scrollWorks"])
    )

    # Close drawer
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    # --- 3: Open Create-subscription dialog, check overlay ---
    page.click(".subscriptions-panel button:has-text('新建')")
    try:
        page.wait_for_selector(".dialog-overlay", timeout=5000)
        page.wait_for_timeout(300)
    except Exception:
        result["dialog_bounds"] = None
        return result

    dialog_bounds = page.evaluate(
        """() => {
            const overlay = document.querySelector('.dialog-overlay');
            const dialog = document.querySelector('.dialog');
            if (!overlay || !dialog) return null;
            const vh = window.innerHeight;
            const vw = window.innerWidth;
            const o = overlay.getBoundingClientRect();
            const d = dialog.getBoundingClientRect();
            return {
                overlay: { top: Math.round(o.top), bottom: Math.round(o.bottom), left: Math.round(o.left), right: Math.round(o.right), width: Math.round(o.width), height: Math.round(o.height) },
                dialog: { top: Math.round(d.top), bottom: Math.round(d.bottom), left: Math.round(d.left), right: Math.round(d.right), width: Math.round(d.width), height: Math.round(d.height) },
                viewportHeight: vh,
                viewportWidth: vw,
                overlayCoversViewport: o.top <= 0 && o.bottom >= vh && o.left <= 0 && o.right >= vw,
                dialogFitsViewport: d.bottom <= vh,
            };
        }"""
    )
    result["dialog_bounds"] = dialog_bounds
    result["dialog_overlay_ok"] = (
        dialog_bounds is not None
        and dialog_bounds["overlayCoversViewport"]
        and dialog_bounds["dialogFitsViewport"]
    )

    # Close dialog
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    return result


def main() -> None:
    token = register_and_login()
    print(f"Registered and logged in as '{TEST_USERNAME}'")

    results: list[dict] = []
    esc_result: dict | None = None
    fixed_result: dict | None = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROMIUM_PATH,
                headless=True,
            )
            page = browser.new_page()

            # Set auth token in localStorage before any page script runs
            page.add_init_script(
                script=(
                    f"localStorage.setItem('auth_token', '{token}');"
                    f"localStorage.setItem('auth_username', '{TEST_USERNAME}');"
                )
            )

            # Navigate to frontend (token already in localStorage)
            page.goto(f"{FRONTEND_URL}/")
            page.wait_for_selector("button.nav-item", timeout=15000)
            # Navigate to the jobs page (default is overview)
            page.click("button.nav-item:has-text('岗位库')")
            page.wait_for_selector("table tbody tr[tabindex]", timeout=15000)

            for width in VIEWPORTS:
                result = measure_viewport(page, width)
                results.append(result)
                if width == 1440:
                    esc_result = test_drawer_esc(page)
                    fixed_result = test_fixed_positioning(page)

            browser.close()
    finally:
        cleanup_test_account()

    # Print results table
    print("\n" + "=" * 90)
    print("Jobs Layout Measurement Results")
    print("=" * 90)
    header = (
        f"{'Viewport':>8} | {'ScrollW':>8} | {'ClientW':>8} | {'Overflow':>8} | "
        f"{'DetailR':>8} | {'NotCut':>7} | {'JobColW':>8} | {'CellH':>6} | {'Mode':>7}"
    )
    print(header)
    print("-" * 90)

    all_pass = True
    for r in results:
        ov = "PASS" if r["zero_overflow"] else "FAIL"
        nc = "PASS" if r["detail_not_cut"] else "FAIL"
        mode = "desktop" if r["is_desktop"] else "drawer"
        jc = str(r["job_col_width"] or "-")
        ch = str(r["cell_height"] or "-")
        dr = str(r["detail_right"] or "-")

        print(
            f"{r['width']:>8} | {r['scroll_w']:>8} | {r['client_w']:>8} | {ov:>8} | "
            f"{dr:>8} | {nc:>7} | {jc:>8} | {ch:>6} | {mode:>7}"
        )

        if not r["zero_overflow"]:
            all_pass = False
        if not r["detail_not_cut"]:
            all_pass = False
        if r["job_col_width"] is not None and r["job_col_width"] < 220:
            all_pass = False
        if r["cell_height"] is not None and r["cell_height"] > 111:
            all_pass = False

    print("-" * 90)

    print("\nAssertions:")
    for r in results:
        w = r["width"]
        print(f"  [{w}px] Zero horizontal overflow: {'PASS' if r['zero_overflow'] else 'FAIL'}")
        print(f"  [{w}px] Detail not cut off:      {'PASS' if r['detail_not_cut'] else 'FAIL'}")

    r1440 = next(r for r in results if r["width"] == 1440)
    col_ok = r1440["job_col_width"] is not None and r1440["job_col_width"] >= 220
    cell_ok = r1440["cell_height"] is not None and r1440["cell_height"] <= 111
    print(f"  [1440px] Job column >= 220px:     {'PASS' if col_ok else 'FAIL'} (actual: {r1440['job_col_width']}px)")
    print(f"  [1440px] Cell height <= 111px:    {'PASS' if cell_ok else 'FAIL'} (actual: {r1440['cell_height']}px)")

    if esc_result:
        esc_ok = esc_result["drawer_gone"] and esc_result["focus_returned"]
        print(
            f"  [1440px] Drawer Esc close+focus:  {'PASS' if esc_ok else 'FAIL'} "
            f"(drawer gone: {esc_result['drawer_gone']}, focus returned: {esc_result['focus_returned']})"
        )
        if not esc_ok:
            all_pass = False

    if fixed_result:
        db = fixed_result.get("drawer_bottom")
        st = fixed_result.get("scroll_test")
        dg = fixed_result.get("dialog_bounds")
        print(f"  [1440px] Drawer bottom <= vh:    {'PASS' if fixed_result['drawer_bottom_ok'] else 'FAIL'} "
              f"(bottom={db['bottom'] if db else '-'}, vh={fixed_result.get('vh', '-')})")
        if st:
            print(f"  [1440px] Drawer-body scrollable: {'PASS' if fixed_result['drawer_scroll_ok'] else 'FAIL'} "
                  f"(clientH={st['clientHeight']}, scrollH={st['scrollHeight']}, "
                  f"fits={st['bodyFitsViewport']}, overflow={st['hasOverflow']}, scrollWorks={st['scrollWorks']})")
        if dg:
            print(f"  [1440px] Dialog overlay covers:  {'PASS' if fixed_result['dialog_overlay_ok'] else 'FAIL'} "
                  f"(overlay top={dg['overlay']['top']} bottom={dg['overlay']['bottom']} "
                  f"left={dg['overlay']['left']} right={dg['overlay']['right']}, "
                  f"dialog bottom={dg['dialog']['bottom']}, vh={dg['viewportHeight']})")
        if not fixed_result["drawer_bottom_ok"]:
            all_pass = False
        if not fixed_result["drawer_scroll_ok"]:
            all_pass = False
        if not fixed_result["dialog_overlay_ok"]:
            all_pass = False

    print(f"\nOverall: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
