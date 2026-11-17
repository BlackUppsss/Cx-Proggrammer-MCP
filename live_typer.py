"""
Live Keyboard Typing Automation for Omron CX-Programmer.
Physically types ladder logic instructions into the active CX-Programmer window
with human-like pacing so the user can visibly watch the ladder being built step-by-step.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any
import pyautogui
import win32gui
import win32con


def find_cxp_window() -> tuple[int, str] | None:
    """Find visible CX-Programmer top-level window."""
    hwnds = []

    def enum_cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if "CX-Programmer" in t:
                hwnds.append((h, t))

    win32gui.EnumWindows(enum_cb, None)
    return hwnds[0] if hwnds else None


def focus_cx_programmer() -> tuple[bool, str]:
    """Bring CX-Programmer window to the foreground."""
    win = find_cxp_window()
    if not win:
        return False, "Jendela CX-Programmer tidak ditemukan di layar. Buka CX-Programmer terlebih dahulu."
    hwnd, title = win
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True, title
    except Exception as exc:
        return False, f"Gagal memfokuskan jendela CX-Programmer: {exc}"


def live_type_ladder(
    instructions: list[str],
    insert_new_rung: bool = True,
    comment: str = "",
    typing_speed: float = 0.10,
    take_screenshot_after: bool = True,
) -> dict[str, Any]:
    """
    Live type a list of ladder instructions into CX-Programmer using standard shortcuts:
    - Shift + Ctrl + I: Insert new rung
    - 'c': NO contact (LD / AND)
    - '/': NC contact (LDNOT / ANDNOT)
    - 'o': Output coil (OUT)
    - 'i': Instruction block (TIM, CNT, MOV, etc.)
    """
    focused, msg = focus_cx_programmer()
    if not focused:
        return {"ok": False, "error": msg}

    # Set safety pause
    pyautogui.PAUSE = max(0.05, typing_speed)

    # 1. Insert new rung if requested
    if insert_new_rung:
        pyautogui.hotkey("ctrl", "shift", "i")
        time.sleep(0.4)

    # 2. Type instructions one by one
    executed_steps = []
    for inst in instructions:
        parts = inst.strip().split()
        if not parts:
            continue
        cmd = parts[0].upper()
        addr = parts[1] if len(parts) > 1 else ""
        rest = " ".join(parts[2:]) if len(parts) > 2 else ""

        if cmd in ("LD", "AND"):
            pyautogui.press("c")
            time.sleep(0.25)
            pyautogui.write(addr, interval=typing_speed)
            time.sleep(0.15)
            pyautogui.press("enter")
            time.sleep(0.15)
            pyautogui.press("enter")  # Confirm comment dialog
            executed_steps.append(f"Contact NO: {cmd} {addr}")
            time.sleep(0.3)

        elif cmd in ("LDNOT", "ANDNOT"):
            pyautogui.press("/")
            time.sleep(0.25)
            pyautogui.write(addr, interval=typing_speed)
            time.sleep(0.15)
            pyautogui.press("enter")
            time.sleep(0.15)
            pyautogui.press("enter")
            executed_steps.append(f"Contact NC: {cmd} {addr}")
            time.sleep(0.3)

        elif cmd in ("OUT", "SET", "RST", "RSET"):
            pyautogui.press("o")
            time.sleep(0.25)
            # If SET or RST, type instruction via 'i' or 'o'
            if cmd in ("SET", "RST", "RSET"):
                pyautogui.press("esc")
                time.sleep(0.15)
                pyautogui.press("i")
                time.sleep(0.25)
                pyautogui.write(f"{cmd} {addr}", interval=typing_speed)
                time.sleep(0.15)
                pyautogui.press("enter")
                time.sleep(0.15)
                pyautogui.press("enter")
            else:
                pyautogui.write(addr, interval=typing_speed)
                time.sleep(0.15)
                pyautogui.press("enter")
                time.sleep(0.15)
                pyautogui.press("enter")
            executed_steps.append(f"Coil/Output: {cmd} {addr}")
            time.sleep(0.3)

        elif cmd.startswith("OR"):
            is_nc = "NOT" in cmd
            key = "/" if is_nc else "c"
            pyautogui.press(key)
            time.sleep(0.25)
            pyautogui.write(addr, interval=typing_speed)
            time.sleep(0.15)
            pyautogui.press("enter")
            time.sleep(0.15)
            pyautogui.press("enter")
            executed_steps.append(f"Branch Contact: {cmd} {addr}")
            time.sleep(0.3)

        elif cmd in ("TIM", "TIMX", "CNT", "CNTX", "MOV", "DIFU", "DIFD", "KEEP"):
            pyautogui.press("i")
            time.sleep(0.25)
            inst_text = f"{cmd} {addr} {rest}".strip()
            pyautogui.write(inst_text, interval=typing_speed)
            time.sleep(0.15)
            pyautogui.press("enter")
            time.sleep(0.15)
            pyautogui.press("enter")
            executed_steps.append(f"Special Instruction: {inst_text}")
            time.sleep(0.3)

    # 3. Optional Screenshot & Visual Verification after typing
    verification_res = None
    if take_screenshot_after:
        time.sleep(0.5)
        out_file = Path(r"C:\Users\ricou\.gemini\antigravity\brain\85540553-45af-482c-bf3e-b6320bb9837e\real_cxp_screenshot.png")
        try:
            from visual_verifier import capture_verify_and_revise
            verification_res = capture_verify_and_revise(output_path=out_file, auto_revise=True)
        except Exception:
            ps_script = Path(r"C:\Users\ricou\capture_window.ps1")
            if ps_script.exists():
                import subprocess
                subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script), "-TitleContains", "CX-Programmer", "-OutputPath", str(out_file)], capture_output=True, text=True, check=False)
                verification_res = {"ok": True, "image_path": str(out_file)}

    return {
        "ok": True,
        "message": f"Berhasil mengetik {len(executed_steps)} instruksi secara live di CX-Programmer.",
        "steps": executed_steps,
        "verification": verification_res,
        "image_path": (verification_res.get("clean_image_path") or verification_res.get("image_path")) if verification_res else None,
    }
