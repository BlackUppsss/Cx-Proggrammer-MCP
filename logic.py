"""
Omron Ladder Boolean Stack & Branch Balance Validator.
Ensures that LD/ORLD/ANDLD branch expressions are properly balanced
so CX-Programmer can render clean, continuous 2D ladder rungs.
"""

from __future__ import annotations
from hardware import strip_function_code


TWO_INPUT_INSTRUCTIONS = {"CNT", "CNTX", "CNTR", "CNTRX", "KEEP", "SFT"}
SINGLE_INPUT_OUTPUTS = {
    "OUT", "OUTNOT", "SET", "RSET", "RST",
    "TIM", "TIMX", "TIMH", "TIMHX", "TMHH", "TMHHX", "TTIM", "TTIMX",
    "MOV", "MOVL", "MVN", "XFER", "BSET", "INC", "DEC",
    "ADD", "SUB", "MUL", "DIV", "ANDW", "ORW", "XORW",
    "DIFU", "DIFD",
}


def validate_rung_stack(instructions: list[str]) -> list[str]:
    """
    Validate that a rung's Boolean evaluation stack remains balanced:
    - LD / LDNOT pushes a new branch (depth += 1).
    - ANDLD / ORLD combines two parallel branches (depth -= 1).
    - 2-input instructions (CNT, CNTX, KEEP, SFT) require depth >= 2 and consume 1 branch (depth -= 1).
    - Standard coils/outputs require depth >= 1.
    - End of rung should not have leftover dangling branches (depth == 1 or 0 after coils).
    """
    errors = []
    depth = 0
    has_coil = False

    for idx, line in enumerate(instructions):
        clean = line.strip()
        if not clean or clean.startswith("'") or clean.startswith("//"):
            continue

        parts = clean.split()
        cmd = strip_function_code(parts[0])

        if cmd in {"LD", "LDNOT"}:
            depth += 1
        elif cmd in {"ANDLD", "ORLD"}:
            if depth < 2:
                errors.append(
                    f"Line {idx + 1} '{clean}': Stack underflow. '{cmd}' requires at least 2 active branches to combine, found depth={depth}."
                )
            else:
                depth -= 1
        elif cmd in TWO_INPUT_INSTRUCTIONS:
            if depth < 2:
                errors.append(
                    f"Line {idx + 1} '{clean}': '{cmd}' is a 2-input instruction (Pulse/Set + Reset) requiring 2 preceding LD branches, found depth={depth}."
                )
            else:
                depth -= 1
            has_coil = True
        elif cmd in SINGLE_INPUT_OUTPUTS:
            if depth < 1:
                errors.append(f"Line {idx + 1} '{clean}': Output instruction without preceding LD/contact condition.")
            has_coil = True

    if depth > 1 and has_coil:
        errors.append(f"Rung contains {depth} uncombined branches at termination. Use 'ORLD' or 'ANDLD' to combine parallel contacts.")

    return errors
