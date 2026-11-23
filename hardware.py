"""
Omron Multi-Model Hardware Profile & Instruction Validation Engine.
Supports CP1E, CP1L, CP1H, CP2E, CJ1M, CJ1G, CJ1H, CJ2M, CJ2H, CS1G, CS1H, CS1D,
CPM1A, CPM2A, CQM1H, C200H, NSJ, CVM1, and FQM1 Omron PLCs (reverse-engineered from CX-P.exe & CX-Pdata.dll).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
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


# Complete Omron Hardware Profiles (verified against CX-P.exe / CX-Pdata.dll / CPSFiles)
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
        notes="Omron CP1E compact series (E10..E60, N14..N60, NA20). BCD timers only.",
    ),
    "CP1L": HardwareProfile(
        name="CP1L",
        family="CP1L",
        cpu="M",
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
        notes="Omron CP1L / CP1L-E series (L10, L14, L20, M30, M40, M60, EL, EM). Supports TIMX/CNTX.",
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
        notes="Omron CP1H / CP1H-E high-speed series (X, XA, Y, EX). Supports TIMX/CNTX.",
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
        notes="Omron CP2E / CP2E-N / CP2E-ENT compact IoT series (E, S, N). Supports TIMX/CNTX, H up to 1535.",
    ),
    "CJ1M": HardwareProfile(
        name="CJ1M",
        family="CJ1",
        cpu="CPU13",
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
        em_banks=1,
        max_em_index=32767,
        notes="Omron CJ1M modular series (CPU11..13, CPU21..23). Supports EM bank E0 and TIMX/CNTX.",
    ),
    "CJ1G": HardwareProfile(
        name="CJ1G",
        family="CJ1",
        cpu="CPU45",
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
        em_banks=3,
        max_em_index=32767,
        notes="Omron CJ1G / CJ1G-H modular series (CPU42..45). Supports EM banks and TIMX/CNTX.",
    ),
    "CJ1H": HardwareProfile(
        name="CJ1H",
        family="CJ1",
        cpu="CPU67",
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
        em_banks=13,
        max_em_index=32767,
        notes="Omron CJ1H-H high-speed modular series (CPU64..67). Supports up to 13 EM banks.",
    ),
    "CJ2M": HardwareProfile(
        name="CJ2M",
        family="CJ2",
        cpu="CPU31",
        memory_areas={
            "CIO": (0, 6143),
            "W": (0, 511),
            "H": (0, 1535),
            "D": (0, 32767),
            "T": (0, 4095),
            "C": (0, 4095),
            "A": (0, 1471),
        },
        supports_binary_timers=True,
        supports_extended_memory=True,
        em_banks=4,
        max_em_index=32767,
        notes="Omron CJ2M modular series (CPU11..15, CPU31..35). Supports EM banks (E0..E3) and TIMX/CNTX.",
    ),
    "CJ2H": HardwareProfile(
        name="CJ2H",
        family="CJ2",
        cpu="CPU64-EIP",
        memory_areas={
            "CIO": (0, 6143),
            "W": (0, 511),
            "H": (0, 1535),
            "D": (0, 32767),
            "T": (0, 4095),
            "C": (0, 4095),
            "A": (0, 1471),
        },
        supports_binary_timers=True,
        supports_extended_memory=True,
        em_banks=25,
        max_em_index=32767,
        notes="Omron CJ2H flagship modular series (CPU64..68). Supports up to 25 EM banks and TIMX/CNTX.",
    ),
    "CS1G": HardwareProfile(
        name="CS1G",
        family="CS1",
        cpu="CPU45",
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
        em_banks=3,
        max_em_index=32767,
        notes="Omron CS1G / CS1G-H rack series (CPU42..45). Supports EM banks and TIMX/CNTX.",
    ),
    "CS1H": HardwareProfile(
        name="CS1H",
        family="CS1",
        cpu="CPU67",
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
        em_banks=13,
        max_em_index=32767,
        notes="Omron CS1H / CS1H-H rack series (CPU63..67). Supports up to 13 EM banks and TIMX/CNTX.",
    ),
    "CS1D": HardwareProfile(
        name="CS1D",
        family="CS1",
        cpu="CPU67",
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
        em_banks=13,
        max_em_index=32767,
        notes="Omron CS1D-H / CS1D-S duplex redundant rack series.",
    ),
    "CPM1A": HardwareProfile(
        name="CPM1A",
        family="C",
        cpu="CPU",
        memory_areas={
            "CIO": (0, 255),
            "IR": (0, 255),
            "H": (0, 19),
            "HR": (0, 19),
            "D": (0, 6655),
            "DM": (0, 6655),
            "T": (0, 127),
            "C": (0, 127),
            "A": (0, 15),
            "AR": (0, 15),
            "LR": (0, 15),
        },
        supports_binary_timers=False,
        supports_extended_memory=False,
        notes="Omron CPM1 / CPM1A legacy compact series. BCD timers only.",
    ),
    "CPM2A": HardwareProfile(
        name="CPM2A",
        family="C",
        cpu="CPU",
        memory_areas={
            "CIO": (0, 255),
            "IR": (0, 255),
            "H": (0, 19),
            "HR": (0, 19),
            "D": (0, 6655),
            "DM": (0, 6655),
            "T": (0, 255),
            "C": (0, 255),
            "A": (0, 27),
            "AR": (0, 27),
            "LR": (0, 15),
        },
        supports_binary_timers=False,
        supports_extended_memory=False,
        notes="Omron CPM2A / CPM2C legacy compact series. BCD timers only.",
    ),
    "CQM1H": HardwareProfile(
        name="CQM1H",
        family="C",
        cpu="CPU51",
        memory_areas={
            "CIO": (0, 255),
            "IR": (0, 255),
            "H": (0, 99),
            "HR": (0, 99),
            "D": (0, 6655),
            "DM": (0, 6655),
            "T": (0, 511),
            "C": (0, 511),
            "A": (0, 27),
            "AR": (0, 27),
            "LR": (0, 63),
        },
        supports_binary_timers=False,
        supports_extended_memory=True,
        em_banks=1,
        max_em_index=6143,
        notes="Omron CQM1 / CQM1H modular series. BCD timers only.",
    ),
    "C200H": HardwareProfile(
        name="C200H",
        family="C",
        cpu="CPU01",
        memory_areas={
            "CIO": (0, 511),
            "IR": (0, 511),
            "H": (0, 99),
            "HR": (0, 99),
            "D": (0, 6655),
            "DM": (0, 6655),
            "T": (0, 511),
            "C": (0, 511),
            "A": (0, 27),
            "AR": (0, 27),
            "LR": (0, 63),
        },
        supports_binary_timers=False,
        supports_extended_memory=True,
        em_banks=3,
        max_em_index=6143,
        notes="Omron C200HS / C200HE / C200HG / C200HX series. BCD timers only.",
    ),
    "NSJ": HardwareProfile(
        name="NSJ",
        family="NSJ",
        cpu="G5D",
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
        em_banks=3,
        max_em_index=32767,
        notes="Omron NSJ integrated HMI + CJ PLC controller.",
    ),
    "CVM1": HardwareProfile(
        name="CVM1",
        family="CV",
        cpu="CPU21",
        memory_areas={
            "CIO": (0, 2555),
            "D": (0, 24575),
            "T": (0, 1023),
            "C": (0, 1023),
            "A": (0, 511),
        },
        supports_binary_timers=False,
        supports_extended_memory=True,
        em_banks=8,
        max_em_index=32765,
        notes="Omron CV500 / CV1000 / CV2000 / CVM1(-V2) series.",
    ),
    "FQM1": HardwareProfile(
        name="FQM1",
        family="FQM1",
        cpu="MMP",
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
        notes="Omron FQM1 flexible motion controller series.",
    ),
}

# Explicit prefix alias mapping for CX-P.exe DEV:<string> tokens
DEV_ALIASES: list[tuple[str, str]] = [
    ("CP1E", "CP1E"),
    ("CP1L", "CP1L"),
    ("CP1H", "CP1H"),
    ("CP2E", "CP2E"),
    ("CJ1M", "CJ1M"),
    ("CJ1G", "CJ1G"),
    ("CJ1H", "CJ1H"),
    ("CJ2M", "CJ2M"),
    ("CJ2H", "CJ2H"),
    ("CS1G", "CS1G"),
    ("CS1H", "CS1H"),
    ("CS1D", "CS1D"),
    ("CPM1", "CPM1A"),
    ("CPM2", "CPM2A"),
    ("CQM1", "CQM1H"),
    ("C200H", "C200H"),
    ("NSJ", "NSJ"),
    ("CV", "CVM1"),
    ("FQM1", "FQM1"),
]

# Regex patterns for memory addresses (CS/CJ/CP + C-series legacy)
PATTERN_BIT = re.compile(r"^(W|H|HR|A|AR|LR|IR|CIO)?(\d+)\.(\d{1,2})$", re.I)
PATTERN_WORD = re.compile(r"^(D|DM|H|HR|A|AR|LR|IR|W|CIO)(\d+)$", re.I)
PATTERN_TIMER = re.compile(r"^(?:TIM|T)(\d{1,4})$", re.I)
PATTERN_COUNTER = re.compile(r"^(?:CNT|C)(\d{1,4})$", re.I)
PATTERN_EM = re.compile(r"^E([0-9A-F]{1,2})?_?(\d+)(?:\.(\d{1,2}))?$", re.I)


def detect_hardware_profile(cxt_text_or_lines: str | list[str]) -> HardwareProfile:
    """Detect PLC model and CPU from CXT Config line, defaulting to CP1E if unspecified."""
    lines = cxt_text_or_lines if isinstance(cxt_text_or_lines, list) else cxt_text_or_lines.splitlines()
    for line in lines[:120]:
        if "Config:=" in line or "DEV:" in line:
            m = re.search(r"DEV:([A-Za-z0-9_-]+)", line)
            if m:
                dev = m.group(1).upper()
                cpu_m = re.search(r"CPU:([A-Za-z0-9_-]+)", line)
                detected_cpu = cpu_m.group(1).upper() if cpu_m else None
                for prefix, prof_key in DEV_ALIASES:
                    if dev == prefix or dev.startswith(prefix):
                        base = PROFILES[prof_key]
                        if detected_cpu and detected_cpu != base.cpu:
                            return replace(base, cpu=detected_cpu)
                        return base
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
        bit = int(m.group(3)) if m.group(3) is not None else None
        return {"area": "E", "bank": bank, "index": int(m.group(2)), "bit": bit, "is_bit": bit is not None}
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
    if isinstance(profile, str):
        prof = detect_hardware_profile(f"DEV:{profile.upper()}")
    else:
        prof = profile

    info = parse_address_info(address)
    area = info.get("area")

    if area == "E":
        if not prof.supports_extended_memory:
            return False
        bank = info.get("bank", 0)
        idx = info.get("index", 0)
        bit = info.get("bit")
        bit_ok = True if bit is None else (0 <= bit <= 15)
        return 0 <= bank < prof.em_banks and 0 <= idx <= prof.max_em_index and bit_ok

    if area not in prof.memory_areas:
        return False

    min_val, max_val = prof.memory_areas[area]
    if "index" in info:
        return min_val <= info["index"] <= max_val
    if "word" in info:
        return min_val <= info["word"] <= max_val and 0 <= info["bit"] <= 15
    return False


def strip_function_code(mnemonic: str) -> str:
    """Strip function code and @/! prefixes from mnemonic: @MOV(021) -> MOV, TIMX(550) -> TIMX."""
    cleaned = mnemonic.strip().upper().lstrip("@!%")
    return re.sub(r"\(\d+\)$", "", cleaned)


def validate_rung_instructions(instructions: list[str], profile: HardwareProfile | str = "CP1E") -> list[str]:
    """Validate rung IL mnemonic instructions against hardware model rules."""
    if isinstance(profile, str):
        prof = detect_hardware_profile(f"DEV:{profile.upper()}")
    else:
        prof = profile

    errors = []
    cnt_count = 0

    for line in instructions:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("'") or line_clean.startswith("//"):
            continue

        parts = line_clean.split()
        raw_cmd = parts[0]
        cmd = strip_function_code(raw_cmd)

        if not prof.supports_binary_timers:
            if cmd in {"TIMX", "TIMHX", "TMHHX", "TTIMX", "MTIMX"}:
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
