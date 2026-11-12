"""
Omron Multi-Model Hardware Profile & Instruction Validation Engine.
Supports CP1E, CP1L, CP1H, CP2E, CJ2M, and modular Omron PLCs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HardwareProfile:
    name: str
    family: str
    cpu: str
    memory_areas: dict[str, tuple[int, int]]
    supports_binary_timers: bool = True
    supports_extended_memory: bool = False
    em_banks: int = 0
    max_em_index: int = 32767
    notes: str = ""


# Standard Omron Hardware Profiles
PROFILES: dict[str, HardwareProfile] = {
    "CP1E": HardwareProfile(
        name="CP1E",
        family="CP1E",
        cpu="NA",
        memory_areas={
            "CIO": (0, 199),
            "W": (0, 99),
            "H": (0, 49),
            "D": (0, 7999),
            "T": (0, 255),
            "C": (0, 255),
            "A": (0, 699),
        },
        supports_binary_timers=False,
        supports_extended_memory=False,
        notes="Omron CP1E compact series (E20, N30, NA20). BCD timers only."
    ),
    "CP1L": HardwareProfile(
        name="CP1L",
        family="CP1L",
        cpu="M",
        memory_areas={
            "CIO": (0, 299),
            "W": (0, 511),
            "H": (0, 511),
            "D": (0, 32767),
            "T": (0, 4095),
            "C": (0, 4095),
            "A": (0, 959),
        },
        supports_binary_timers=True,
        supports_extended_memory=False,
        notes="Omron CP1L series (L10, L20, M30, M40). Supports TIMX/CNTX."
    ),
    "CP1H": HardwareProfile(
        name="CP1H",
        family="CP1H",
        cpu="X",
        memory_areas={
            "CIO": (0, 6143),
            "W": (0, 511),
            "H": (0, 511),
            "D": (0, 32767),
            "T": (0, 4095),
            "C": (0, 4095),
            "A": (0, 959),
        },
        supports_binary_timers=True,
        supports_extended_memory=False,
        notes="Omron CP1H high-speed series (X, XA with built-in analog). Supports TIMX/CNTX."
    ),
    "CP2E": HardwareProfile(
        name="CP2E",
        family="CP2E",
        cpu="N",
        memory_areas={
            "CIO": (0, 6143),
            "W": (0, 511),
            "H": (0, 1535),
            "D": (0, 32767),
            "T": (0, 4095),
            "C": (0, 4095),
            "A": (0, 959),
        },
        supports_binary_timers=True,
        supports_extended_memory=False,
        notes="Omron CP2E compact IoT/Ethernet series. Supports TIMX/CNTX, H up to 1535."
    ),
    "CJ2M": HardwareProfile(
        name="CJ2M",
        family="CJ2M",
        cpu="CPU31",
        memory_areas={
            "CIO": (0, 6143),
            "W": (0, 511),
            "H": (0, 511),
            "D": (0, 32767),
            "T": (0, 4095),
            "C": (0, 4095),
            "A": (0, 959),
        },
        supports_binary_timers=True,
        supports_extended_memory=True,
        em_banks=4,
        max_em_index=32767,
        notes="Omron CJ2M modular series. Supports EM banks (E0..E3) and TIMX/CNTX."
    ),
}

# Regex patterns for memory addresses
PATTERN_BIT = re.compile(r"^(W|H|A|CIO)?(\d+)\.(\d{1,2})$", re.I)
PATTERN_WORD = re.compile(r"^(D|H|A|W)(\d+)$", re.I)
PATTERN_TIMER = re.compile(r"^T(\d{1,4})$", re.I)
PATTERN_COUNTER = re.compile(r"^C(\d{1,4})$", re.I)
PATTERN_EM = re.compile(r"^E([0-9A-F])?_?(\d+)$", re.I)


def detect_hardware_profile(cxt_text_or_lines: str | list[str]) -> HardwareProfile:
    """Detect PLC model from CXT Config line, defaulting to CP1E if unspecified."""
    lines = cxt_text_or_lines if isinstance(cxt_text_or_lines, list) else cxt_text_or_lines.splitlines()
    for line in lines[:80]:
        if "Config:=" in line or "DEV:" in line:
            m = re.search(r"DEV:([A-Za-z0-9_-]+)", line)
            if m:
                dev = m.group(1).upper()
                for key, prof in PROFILES.items():
                    if key in dev or dev in key:
                        return prof
    return PROFILES["CP1E"]


def parse_address_info(address: str) -> dict[str, Any]:
    """Parse address string into components."""
    addr = address.strip()
    m = PATTERN_TIMER.match(addr)
    if m:
        return {"area": "T", "index": int(m.group(1)), "is_bit": True}
    m = PATTERN_COUNTER.match(addr)
    if m:
        return {"area": "C", "index": int(m.group(1)), "is_bit": True}
    m = PATTERN_EM.match(addr)
    if m:
        bank_str = m.group(1) or "0"
        bank = int(bank_str, 16) if bank_str.isalnum() else 0
        return {"area": "E", "bank": bank, "index": int(m.group(2)), "is_bit": False}
    m = PATTERN_BIT.match(addr)
    if m:
        area = m.group(1).upper() if m.group(1) else "CIO"
        return {"area": area, "word": int(m.group(2)), "bit": int(m.group(3)), "is_bit": True}
    m = PATTERN_WORD.match(addr)
    if m:
        return {"area": m.group(1).upper(), "index": int(m.group(2)), "is_bit": False}
    return {"area": "UNKNOWN", "raw": addr}


def validate_address(address: str, profile: HardwareProfile | str = "CP1E") -> bool:
    """Validate that memory address exists within the hardware model boundaries."""
    prof = PROFILES.get(profile.upper(), PROFILES["CP1E"]) if isinstance(profile, str) else profile
    info = parse_address_info(address)
    area = info.get("area")

    if area == "E":
        if not prof.supports_extended_memory:
            return False
        bank = info.get("bank", 0)
        idx = info.get("index", 0)
        return 0 <= bank < prof.em_banks and 0 <= idx <= prof.max_em_index

    if area not in prof.memory_areas:
        return False

    min_val, max_val = prof.memory_areas[area]
    if "index" in info:
        return min_val <= info["index"] <= max_val
    if "word" in info:
        return min_val <= info["word"] <= max_val and 0 <= info["bit"] <= 15
    return False


def strip_function_code(mnemonic: str) -> str:
    """Strip function code from mnemonic: TIMX(550) -> TIMX, DIFU(013) -> DIFU."""
    return re.sub(r"\(\d+\)$", "", mnemonic.strip().upper())


def validate_rung_instructions(instructions: list[str], profile: HardwareProfile | str = "CP1E") -> list[str]:
    """Validate rung IL mnemonic instructions against hardware model rules."""
    prof = PROFILES.get(profile.upper(), PROFILES["CP1E"]) if isinstance(profile, str) else profile
    errors = []
    cnt_count = 0

    for line in instructions:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("'"):
            continue

        parts = line_clean.split()
        raw_cmd = parts[0]
        cmd = strip_function_code(raw_cmd)

        if not prof.supports_binary_timers:
            if cmd in {"TIMX", "TIMHX", "TMHHX"}:
                errors.append(f"{prof.name} does not support binary timer '{cmd}'. Use standard BCD 'TIM' instead!")
            elif cmd in {"CNTX", "CNTRX"}:
                errors.append(f"{prof.name} does not support binary counter '{cmd}'. Use standard BCD 'CNT' instead!")

        if cmd in {"CNT", "CNTX"}:
            cnt_count += 1
            if len(parts) < 3:
                errors.append(f"Instruction {cmd} requires 2 operands (Number & Set Value): {line_clean}")

        if cmd in {"AND", "LD", "OR"} and len(parts) > 1 and parts[1].upper() == "NOT":
            errors.append(f"NC contacts must not contain spaces ('{parts[0]} NOT'). Use '{parts[0]}NOT' instead!")

    if cnt_count > 1:
        errors.append("Multiple CNT instructions in a single rung detected. Split into separate rungs.")

    return errors
