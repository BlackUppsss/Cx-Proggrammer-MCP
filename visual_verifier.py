"""
Visual Error Detection and Auto-Revision Engine for Omron CX-Programmer.
Inspects screenshots for:
1. Red power rail indicator (bright red vertical line indicating ladder rung syntax/connection errors).
2. Modal error/warning dialogs or stuck cursor states.
3. Automatically executes revisions (dismissing dialogs, rolling back bad edits via Ctrl+Z, repositioning).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from PIL import Image

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None


def switch_to_default_desktop():
    """Ensure current thread can access the interactive default desktop."""
    user32 = ctypes.windll.user32
    hDesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if hDesk:
        user32.SetThreadDesktop(hDesk)
    return hDesk


def close_desktop_handle(hDesk):
    if hDesk:
        ctypes.windll.user32.CloseDesktop(hDesk)


def find_cxp_hwnd() -> tuple[int | None, str]:
    """Locate CX-Programmer window handle on the interactive desktop."""
    hDesk = switch_to_default_desktop()
    found_hwnd = None
    found_title = ""

    if win32gui:
        def enum_cb(h, _):
            nonlocal found_hwnd, found_title
            if win32gui.IsWindowVisible(h):
                t = win32gui.GetWindowText(h)
                if "CX-Programmer" in t:
                    found_hwnd = h
                    found_title = t
        win32gui.EnumWindows(enum_cb, None)

    close_desktop_handle(hDesk)
    return found_hwnd, found_title


def detect_screenshot_errors(image_path: str | Path) -> dict[str, Any]:
    """
    Inspect a captured screenshot for CX-Programmer ladder diagram errors.
    In CX-Programmer:
    - An invalid or incomplete rung triggers a bright red color on the left power rail.
    - Rail normal color is black/gray.
    - Error red pixels: R > 180, G < 70, B < 70.
    """
    img_p = Path(image_path)
    if not img_p.exists():
        return {"has_error": False, "error": f"Image file not found: {img_p}"}

    img = Image.open(img_p).convert("RGB")
    w, h = img.size

    # Focus on ladder canvas area (X: 300..650, Y: 100..h-50)
    red_coords = []
    for y in range(100, h - 50):
        for x in range(300, min(w - 50, 650)):
            r, g, b = img.getpixel((x, y))
            if r > 180 and g < 70 and b < 70:
                red_coords.append((x, y))

    from collections import Counter
    x_counts = Counter(p[0] for p in red_coords)
    rail_errors = [x for x, count in x_counts.items() if count >= 25]

    has_error = len(rail_errors) > 0 or len(red_coords) > 100
    details = []
    if rail_errors:
        min_y = min(p[1] for p in red_coords if p[0] in rail_errors)
        max_y = max(p[1] for p in red_coords if p[0] in rail_errors)
        details.append(
            f"Red ladder rail error detected at X={rail_errors}, Y-span [{min_y}..{max_y}] ({len(red_coords)} red pixels). "
            f"The rung has an incomplete circuit, uncompleted function block, or syntax error."
        )
    elif len(red_coords) > 100:
        details.append(f"Excess red error pixels detected in canvas ({len(red_coords)} pixels).")

    return {
        "has_error": has_error,
        "error_type": "RED_RAIL_SYNTAX_ERROR" if has_error else None,
        "red_pixel_count": len(red_coords),
        "rail_columns": rail_errors,
        "details": details,
        "image_path": str(img_p),
    }


def auto_revise_ladder(
    max_steps: int = 5,
    screenshot_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Automatically revise active CX-Programmer errors:
    1. Bring CX-Programmer to foreground.
    2. Dismiss any stuck modal dialogs or edit prompts with Escape.
    3. Revert erroneous edits using Ctrl+Z step-by-step.
    4. Re-capture window screenshot and verify error clearance.
    """
    user32 = ctypes.windll.user32
    hDesk = switch_to_default_desktop()

    hwnd, title = find_cxp_hwnd()
    if not hwnd:
        close_desktop_handle(hDesk)
        return {"ok": False, "revised": False, "error": "CX-Programmer window not found."}

    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    actions = []

    # 1. Dismiss any open dialogs/prompts
    for _ in range(2):
        user32.keybd_event(0x1B, 0, 0, 0)  # VK_ESCAPE down
        time.sleep(0.04)
        user32.keybd_event(0x1B, 0, 2, 0)  # VK_ESCAPE up
        time.sleep(0.15)
    actions.append("Dismissed modal dialogs/prompts with Escape")

    # 2. Capture baseline before rollback
    default_brain = Path(r"C:\Users\ricou\.gemini\antigravity\brain\85540553-45af-482c-bf3e-b6320bb9837e")
    fallback_out = (default_brain if default_brain.exists() else Path.cwd()) / "real_cxp_screenshot.png"
    out_file = Path(screenshot_output_path or fallback_out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    pkg_script = Path(__file__).resolve().parent / "scripts" / "capture_window.ps1"
    ps_script = pkg_script if pkg_script.exists() else Path(r"C:\Users\ricou\capture_window.ps1")

    revised_successfully = False
    for step in range(1, max_steps + 1):
        # Send Ctrl+Z
        user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        user32.keybd_event(0x5A, 0, 0, 0)  # Z down
        time.sleep(0.04)
        user32.keybd_event(0x5A, 0, 2, 0)  # Z up
        user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
        time.sleep(0.3)
        actions.append(f"Sent Ctrl+Z (Undo) step {step}")

        # Capture and check
        if ps_script.exists():
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script), "-TitleContains", "CX-Programmer", "-OutputPath", str(out_file)],
                capture_output=True, text=True, check=False
            )
            diag = detect_screenshot_errors(out_file)
            if not diag["has_error"]:
                revised_successfully = True
                actions.append(f"Error cleared successfully after {step} undo step(s). Red pixels remaining: {diag['red_pixel_count']}.")
                break

    close_desktop_handle(hDesk)

    return {
        "ok": True,
        "revised": revised_successfully,
        "actions_taken": actions,
        "clean_image_path": str(out_file) if revised_successfully else None,
        "window_title": title,
    }


def capture_verify_and_revise(
    output_path: str | Path | None = None,
    auto_revise: bool = True,
) -> dict[str, Any]:
    """
    High-level verification tool:
    1. Captures fresh CX-Programmer screenshot.
    2. Runs visual ladder error detection (red rail check).
    3. If errors found and auto_revise=True, executes automatic revision.
    4. Returns complete report with images and status.
    """
    if not output_path:
        default_brain = Path(r"C:\Users\ricou\.gemini\antigravity\brain\85540553-45af-482c-bf3e-b6320bb9837e")
        out_file = (default_brain if default_brain.exists() else Path.cwd()) / "real_cxp_screenshot.png"
    else:
        out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    pkg_script = Path(__file__).resolve().parent / "scripts" / "capture_window.ps1"
    ps_script = pkg_script if pkg_script.exists() else Path(r"C:\Users\ricou\capture_window.ps1")
    if not ps_script.exists():
        return {"ok": False, "error": "capture_window.ps1 not found."}

    # 1. Capture initial screenshot
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script), "-TitleContains", "CX-Programmer", "-OutputPath", str(out_file)],
        capture_output=True, text=True, check=False
    )

    # 2. Check errors
    diag = detect_screenshot_errors(out_file)

    if not diag["has_error"]:
        return {
            "ok": True,
            "error_detected": False,
            "status": "CLEAN",
            "message": "Ladder diagram valid dan bebas dari error (tidak ada red rail).",
            "image_path": str(out_file),
            "red_pixels": diag["red_pixel_count"],
        }

    # 3. If errors detected
    report = {
        "ok": True,
        "error_detected": True,
        "initial_error_details": diag["details"],
        "initial_image_path": str(out_file),
        "status": "ERROR_DETECTED",
    }

    if auto_revise:
        # Save copy of error screenshot for before/after comparison
        err_copy = out_file.parent / f"{out_file.stem}_error{out_file.suffix}"
        import shutil
        try:
            shutil.copy(out_file, err_copy)
            report["error_snapshot"] = str(err_copy)
        except Exception:
            pass

        # Execute auto-revision
        revision_res = auto_revise_ladder(max_steps=5, screenshot_output_path=out_file)
        report["auto_revision"] = revision_res
        if revision_res.get("revised"):
            report["status"] = "REVISED_CLEAN"
            report["message"] = "Error syntax / red rail berhasil terdeteksi dan direvisi otomatis secara live."
            report["clean_image_path"] = revision_res["clean_image_path"]
        else:
            report["status"] = "REVISION_FAILED"
            report["message"] = "Error terdeteksi namun tidak dapat diselesaikan otomatis dengan undo."

    return report
