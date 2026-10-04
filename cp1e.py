# cp1e.py
"""
CP1E-NA Memory & Instruction Specification Helper.
Helps validate operands and ensures no collisions occur in internal PLC memory.
"""

import re

# Memory map allocation for Omron CP1E-NA (CPU: NA20DR-A / NA20DT-D etc.)
MEMORY_AREAS = {
    "CIO_IN": (0, 1),        # Built-in physical inputs on CP1E-NA20 (CIO 0.00 - 0.11)
    "CIO_OUT": (100, 101),   # Built-in physical outputs on CP1E-NA20 (CIO 100.00 - 100.07)
    "CIO": (0, 199),         # General CIO Area (I/O 0-1, 100-101 & Internal 2-99, 102-199)
    "W": (0, 99),            # Work Area (W0.00 - W99.15)
    "H": (0, 49),            # Holding Area / Retentive (H0.00 - H49.15)
    "D": (0, 7999),          # Data Memory Non-volatile (D0 - D7999)
    "T": (0, 255),           # Timers (T000 - T255)
    "C": (0, 255),           # Counters (C000 - C255)
    "A": (0, 699),           # Auxiliary Area / System Flags (A0.00 - A699.15)
}

# Frequently used CP1E-NA specific system flags
SYSTEM_FLAGS = {
    "P_On": "CF113.00",           # Always ON Flag (Use P_On or CF113.00, not A200.08!)
    "P_Off": "CF113.01",          # Always OFF Flag
    "P_First_Cycle": "A200.11",   # First Scan ON Pulse
    "P_EQ": "A200.10",            # CMP Equal Flag (=)
    "P_LT": "A200.12",            # CMP Less Than Flag (<)
    "P_GT": "A200.14",            # CMP Greater Than Flag (>)
    "RTC_CLOCK": "A351",          # High-byte: Hours (BCD), Low-byte: Minutes (BCD)
    "RTC_DATE": "A352",           # High-byte: Day (BCD), Low-byte: Month (BCD)
}

# Regex patterns for basic memory addresses
PATTERN_BIT = re.compile(r"^(W|H|A|CIO)?(\d+)\.(\d{1,2})$", re.I)
PATTERN_WORD = re.compile(r"^(D|H|A|W)(\d+)$", re.I)
PATTERN_TIMER = re.compile(r"^T(\d{1,3})$", re.I)
PATTERN_COUNTER = re.compile(r"^C(\d{1,3})$", re.I)

def parse_address_info(address: str):
    address = address.strip()
    # Timer / Counter
    m = PATTERN_TIMER.match(address)
    if m:
        return {"area": "T", "index": int(m.group(1)), "is_bit": True}
    m = PATTERN_COUNTER.match(address)
    if m:
        return {"area": "C", "index": int(m.group(1)), "is_bit": True}
    # Bit (W20.00, H2.03, A641.00, CIO 0.00 / 100.01)
    m = PATTERN_BIT.match(address)
    if m:
        area = m.group(1).upper() if m.group(1) else "CIO"
        return {"area": area, "word": int(m.group(2)), "bit": int(m.group(3)), "is_bit": True}
    # Word (Dxxx, Hxxx, Axxx, Wxxx)
    m = PATTERN_WORD.match(address)
    if m:
        return {"area": m.group(1).upper(), "index": int(m.group(2)), "is_bit": False}
    return {"area": "UNKNOWN", "raw": address}



def validate_address(address: str) -> bool:
    info = parse_address_info(address)
    area = info.get("area")
    if area not in MEMORY_AREAS:
        return False
    min_val, max_val = MEMORY_AREAS[area]
    if "index" in info:
        return min_val <= info["index"] <= max_val
    if "word" in info:
        word_ok = min_val <= info["word"] <= max_val
        bit_ok = 0 <= info["bit"] <= 15
        return word_ok and bit_ok
    return False

def allocate_free_bit(used_bits: set[str], area: str = "W", start_word: int = 20, max_word: int = 50) -> str:
    """Find the first unused free bit in a given area."""
    area = area.upper()
    for w in range(start_word, max_word + 1):
        for b in range(16):
            addr = f"{area}{w}.{b:02d}" if area != "CIO" else f"{w}.{b:02d}"
            if addr not in used_bits and addr.lower() not in [x.lower() for x in used_bits]:
                return addr
    raise ValueError(f"No free bits found in area {area}{start_word}..{max_word}")

def allocate_free_word(used_words: set[str], area: str = "D", start_index: int = 100, max_index: int = 1000) -> str:
    """Find the first unused free word in a given area."""
    area = area.upper()
    for i in range(start_index, max_index + 1):
        addr = f"{area}{i}"
        if addr not in used_words and addr.lower() not in [x.lower() for x in used_words]:
            return addr
    raise ValueError(f"No free words found in area {area}{start_index}..{max_index}")

# Output/Block instructions for CP1E-NA
OUTPUT_INSTRUCTIONS = {"OUT", "OUTNOT", "SET", "RSET", "TIM", "CNT", "TIMH", "KEEP(011)"}
UNSUPPORTED_INLINE_CMP = {"=", "<>", "<", "<=", ">", ">="}

def validate_rung_cp1e(instructions: list[str]) -> list[str]:
    """
    Validate Omron CP1E-NA specific compilation rules on a group of IL mnemonic instructions in a rung:
    1. Detect usage of TIMX (Binary Timer) or CNTX (Binary Counter) unsupported by CP1E.
    2. Detect CNT format errors (requires 2 operands and cannot be duplicated within 1 rung).
    3. Detect space in contacts such as 'AND NOT', 'LD NOT' (must be ANDNOT, LDNOT).
    """
    errors = []
    cnt_count = 0

    for line in instructions:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("'"):
            continue
            
        parts = line_clean.split()
        cmd = parts[0].upper()

        if cmd == "TIMX":
            errors.append("CP1E-NA does not support TIMX (Binary Timer). Use TIM (BCD Timer) instead!")
        elif cmd == "CNTX":
            errors.append("CP1E-NA does not support CNTX (Binary Counter). Use CNT (BCD Counter) instead!")
        elif cmd == "CNT":
            cnt_count += 1
            if len(parts) < 3:
                errors.append(f"Instruction CNT requires 2 operands (Counter Number & Set Value, e.g.: 'CNT 001 #10'): {line_clean}")
        elif cmd in {"AND", "LD", "OR"} and len(parts) > 1 and parts[1].upper() == "NOT":
            errors.append(f"NC contacts must not contain spaces ('{parts[0]} NOT'). Use '{parts[0]}NOT' instead!")

    if cnt_count > 1:
        errors.append("CNT instruction cannot be called multiple times in a single rung. Split into separate rungs/branches with correct Reset (R) inputs.")

    return errors



