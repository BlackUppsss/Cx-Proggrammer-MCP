"""
CPU-specific instruction tables for Omron PLC families.

Each entry: mnemonic -> {"arity": (min, max), "family": str, "desc": str}
arity is the number of operands (excluding the mnemonic itself).
max=None means variadic.

Sources: Omron CP1E Programming Manual (W480), CS/CJ Programming Manual (W394).
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# CP1E instruction set (CP1E-N/NA/S/SA series)
# ---------------------------------------------------------------------------
_CP1E: dict[str, dict[str, Any]] = {
    # --- Boolean contacts ---
    "LD":       {"arity": (1, 1), "family": "contact",     "desc": "Load contact (NO)"},
    "LDNOT":    {"arity": (1, 1), "family": "contact",     "desc": "Load contact (NC)"},
    "AND":      {"arity": (1, 1), "family": "contact",     "desc": "AND contact (NO)"},
    "ANDNOT":   {"arity": (1, 1), "family": "contact",     "desc": "AND contact (NC)"},
    "OR":       {"arity": (1, 1), "family": "contact",     "desc": "OR contact (NO)"},
    "ORNOT":    {"arity": (1, 1), "family": "contact",     "desc": "OR contact (NC)"},
    "AND LD":   {"arity": (0, 0), "family": "logic_block", "desc": "AND load (series blocks)"},
    "OR LD":    {"arity": (0, 0), "family": "logic_block", "desc": "OR load (parallel blocks)"},
    # --- Coils ---
    "OUT":      {"arity": (1, 1), "family": "coil",        "desc": "Output coil"},
    "OUTNOT":   {"arity": (1, 1), "family": "coil",        "desc": "Output coil (inverted)"},
    "SET":      {"arity": (1, 1), "family": "state_write", "desc": "Set bit (latch ON)"},
    "RSET":     {"arity": (1, 1), "family": "state_write", "desc": "Reset bit (latch OFF)"},
    "KEEP":     {"arity": (1, 1), "family": "stateful",    "desc": "Keep relay (S/R coil)"},
    # --- Timers ---
    "TIM":      {"arity": (2, 2), "family": "timer",       "desc": "100ms decrement timer"},
    "TIMH":     {"arity": (2, 2), "family": "timer",       "desc": "10ms high-speed timer"},
    "TIMX":     {"arity": (2, 2), "family": "timer",       "desc": "1ms timer (CP1E-N/NA)"},
    "TIMHX":    {"arity": (2, 2), "family": "timer",       "desc": "0.1ms timer (CP1E-N/NA)"},
    # --- Counters ---
    "CNT":      {"arity": (2, 2), "family": "counter",     "desc": "Decrement counter"},
    "CNTR":     {"arity": (3, 3), "family": "counter",     "desc": "Reversible counter"},
    # --- Data move ---
    "MOV":      {"arity": (2, 2), "family": "move",        "desc": "Move word"},
    "MOVL":     {"arity": (2, 2), "family": "move",        "desc": "Move double-word"},
    "MVN":      {"arity": (2, 2), "family": "move",        "desc": "Move NOT (invert)"},
    "MOVB":     {"arity": (3, 3), "family": "byte_move",   "desc": "Move byte: MOVB src, bit-pos, dest"},
    "MOVD":     {"arity": (3, 3), "family": "byte_move",   "desc": "Move digit: MOVD src, digit-pos, dest"},
    "MOVW":     {"arity": (3, 3), "family": "byte_move",   "desc": "Move word with mask"},
    "XFER":     {"arity": (3, 3), "family": "move",        "desc": "Block transfer: XFER count, src, dest"},
    "BSET":     {"arity": (3, 3), "family": "move",        "desc": "Block set"},
    "XCHG":     {"arity": (2, 2), "family": "move",        "desc": "Exchange words"},
    # --- Arithmetic ---
    "ADD":      {"arity": (3, 3), "family": "math",        "desc": "BCD add: ADD Au, Ad, R"},
    "ADDL":     {"arity": (3, 3), "family": "math",        "desc": "BCD double add"},
    "SUB":      {"arity": (3, 3), "family": "math",        "desc": "BCD subtract"},
    "SUBL":     {"arity": (3, 3), "family": "math",        "desc": "BCD double subtract"},
    "MUL":      {"arity": (3, 3), "family": "math",        "desc": "BCD multiply"},
    "MULL":     {"arity": (3, 3), "family": "math",        "desc": "BCD double multiply"},
    "DIV":      {"arity": (3, 3), "family": "math",        "desc": "BCD divide"},
    "DIVL":     {"arity": (3, 3), "family": "math",        "desc": "BCD double divide"},
    "INC":      {"arity": (1, 1), "family": "math",        "desc": "Increment word"},
    "DEC":      {"arity": (1, 1), "family": "math",        "desc": "Decrement word"},
    # --- Logic ---
    "ANDW":     {"arity": (3, 3), "family": "math",        "desc": "Logical AND words"},
    "ORW":      {"arity": (3, 3), "family": "math",        "desc": "Logical OR words"},
    "XORW":     {"arity": (3, 3), "family": "math",        "desc": "Logical XOR words"},
    "COM":      {"arity": (1, 1), "family": "math",        "desc": "Complement (invert all bits)"},
    # --- Comparison ---
    "CMP":      {"arity": (2, 2), "family": "compare",     "desc": "Compare: CMP op1, op2 → flags"},
    "CMPL":     {"arity": (2, 2), "family": "compare",     "desc": "Compare double-word"},
    "LD=":      {"arity": (2, 2), "family": "compare",     "desc": "Load if equal"},
    "LD<>":     {"arity": (2, 2), "family": "compare",     "desc": "Load if not equal"},
    "LD<":      {"arity": (2, 2), "family": "compare",     "desc": "Load if less than"},
    "LD<=":     {"arity": (2, 2), "family": "compare",     "desc": "Load if less or equal"},
    "LD>":      {"arity": (2, 2), "family": "compare",     "desc": "Load if greater than"},
    "LD>=":     {"arity": (2, 2), "family": "compare",     "desc": "Load if greater or equal"},
    "AND=":     {"arity": (2, 2), "family": "compare",     "desc": "AND if equal"},
    "AND<>":    {"arity": (2, 2), "family": "compare",     "desc": "AND if not equal"},
    "AND<":     {"arity": (2, 2), "family": "compare",     "desc": "AND if less than"},
    "AND<=":    {"arity": (2, 2), "family": "compare",     "desc": "AND if less or equal"},
    "AND>":     {"arity": (2, 2), "family": "compare",     "desc": "AND if greater than"},
    "AND>=":    {"arity": (2, 2), "family": "compare",     "desc": "AND if greater or equal"},
    "OR=":      {"arity": (2, 2), "family": "compare",     "desc": "OR if equal"},
    "OR<>":     {"arity": (2, 2), "family": "compare",     "desc": "OR if not equal"},
    "OR<":      {"arity": (2, 2), "family": "compare",     "desc": "OR if less than"},
    "OR<=":     {"arity": (2, 2), "family": "compare",     "desc": "OR if less or equal"},
    "OR>":      {"arity": (2, 2), "family": "compare",     "desc": "OR if greater than"},
    "OR>=":     {"arity": (2, 2), "family": "compare",     "desc": "OR if greater or equal"},
    # --- Conversion ---
    "BIN":      {"arity": (2, 2), "family": "conversion",  "desc": "BCD → BIN"},
    "BCD":      {"arity": (2, 2), "family": "conversion",  "desc": "BIN → BCD"},
    "BINS":     {"arity": (2, 2), "family": "conversion",  "desc": "Signed BCD → BIN"},
    "BCDS":     {"arity": (2, 2), "family": "conversion",  "desc": "Signed BIN → BCD"},
    "BINL":     {"arity": (2, 2), "family": "conversion",  "desc": "BCD double → BIN double"},
    "BCDL":     {"arity": (2, 2), "family": "conversion",  "desc": "BIN double → BCD double"},
    # --- Shift ---
    "ASL":      {"arity": (1, 1), "family": "math",        "desc": "Arithmetic shift left"},
    "ASR":      {"arity": (1, 1), "family": "math",        "desc": "Arithmetic shift right"},
    "ROL":      {"arity": (1, 1), "family": "math",        "desc": "Rotate left"},
    "ROR":      {"arity": (1, 1), "family": "math",        "desc": "Rotate right"},
    "SLD":      {"arity": (2, 2), "family": "math",        "desc": "1-digit shift left"},
    "SRD":      {"arity": (2, 2), "family": "math",        "desc": "1-digit shift right"},
    # --- Control flow ---
    "JMP":      {"arity": (1, 1), "family": "control_flow","desc": "Jump to label"},
    "JME":      {"arity": (1, 1), "family": "control_flow","desc": "Jump end (label)"},
    "CJP":      {"arity": (1, 1), "family": "control_flow","desc": "Conditional jump"},
    "IL":       {"arity": (0, 0), "family": "control_flow","desc": "Interlock start"},
    "ILC":      {"arity": (0, 0), "family": "control_flow","desc": "Interlock clear"},
    # --- Program control ---
    "END":      {"arity": (0, 0), "family": "terminator",  "desc": "End of program (required)"},
    "NOP":      {"arity": (0, 0), "family": "other",       "desc": "No operation"},
    # --- Serial (CP1E-NA only) ---
    "STUP":     {"arity": (3, 3), "family": "other",       "desc": "Serial port setup (CP1E-NA)"},
    "TXD":      {"arity": (3, 3), "family": "other",       "desc": "Serial transmit (CP1E-NA)"},
    "RXD":      {"arity": (3, 3), "family": "other",       "desc": "Serial receive (CP1E-NA)"},
}

# ---------------------------------------------------------------------------
# Registry: map CPU model name → instruction table
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {
    "CP1E":       _CP1E,
    "CP1E-N":     _CP1E,
    "CP1E-NA":    _CP1E,
    "CP1E-S":     _CP1E,
    "CP1E-SA":    _CP1E,
    "CJ2M":       _CP1E,
    "CJ2M-CPU11": _CP1E,
    "CS1":        _CP1E,
    "CJ1":        _CP1E,
}


def list_cpu_models() -> list[str]:
    """Return all known CPU model strings."""
    return sorted(_REGISTRY.keys())


def get_instructions(cpu_model: str) -> dict[str, dict[str, Any]] | None:
    """Return the instruction table for a given CPU model, or None if unknown.
    Case-insensitive; tries prefix match if no exact match found.
    """
    key = cpu_model.strip().upper()
    if key in _REGISTRY:
        return _REGISTRY[key]
    # Sort by key length descending so the most specific match wins.
    # e.g. "CP1E-NA" beats "CP1E" when querying "CP1E-NA30".
    for k, v in sorted(_REGISTRY.items(), key=lambda x: len(x[0]), reverse=True):
        if key.startswith(k) or k.startswith(key):
            return v
    return None


def list_instructions_by_family(cpu_model: str) -> dict[str, list[dict[str, Any]]]:
    """Return instructions grouped by family for the given CPU model.

    Each list item: {"mnemonic": str, "arity_min": int, "arity_max": int, "desc": str}
    Returns empty dict if CPU model is unknown.
    """
    table = get_instructions(cpu_model)
    if table is None:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for mnemonic, info in sorted(table.items()):
        fam = info["family"]
        grouped.setdefault(fam, []).append({
            "mnemonic": mnemonic,
            "arity_min": info["arity"][0],
            "arity_max": info["arity"][1],
            "desc": info["desc"],
        })
    return grouped
