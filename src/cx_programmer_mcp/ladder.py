from __future__ import annotations

import re
import shlex
from typing import Any, Iterable


# Common CS/CJ/CP mnemonic families. Unknown instructions are preserved and reported,
# not rejected, because CX-Programmer supports a much larger CPU-specific instruction set.
CONTACTS = {"LD", "LDNOT", "AND", "ANDNOT", "OR", "ORNOT"}
BLOCK_OPS = {"AND LD", "OR LD"}
COILS = {"OUT", "OUTNOT"}
STATE_WRITES = {"SET", "RSET"}
STATEFUL = {"SET", "RSET", "KEEP"}
TERMINATORS = {"END"}
TIMERS = {"TIM", "TIMH", "TIMX", "TIMHX"}
COUNTERS = {"CNT", "CNTR", "CNTX", "CNTRX"}
MOVE_FAMILY = {
    "MOV", "MOVL", "MVN", "MVNL", "XFER", "BSET", "XCHG", "DIST", "COLL",
}
MATH_DEST_LAST = {
    "ADD", "ADDL", "SUB", "SUBL", "MUL", "MULL", "DIV", "DIVL", "INC", "INCL",
    "DEC", "DECL", "NEG", "NEGL", "ANDW", "ORW", "XORW", "COM", "ASL", "ASR",
    "ROL", "ROR", "SLD", "SRD",
}
CONTROL_FLOW = {"JMP", "JME", "CJP", "CALL", "SBS", "RET", "IL", "ILC"}

# Deliberately permissive: Omron supports many memory areas and indirect/indexed forms.
# The validator's goal is catching obvious malformed operands, not replacing CX-Programmer compile.
_ADDRESS_PATTERNS = [
    re.compile(r"^(?:CIO)?\d{1,4}\.\d{1,2}$", re.I),
    re.compile(r"^[WHA]\d{1,4}\.\d{1,2}$", re.I),
    re.compile(r"^[DTCE]\d+(?:\.\d+)?$", re.I),
    re.compile(r"^E\d+_\d+(?:\.\d+)?$", re.I),
    re.compile(r"^(?:IR|DR)\d+$", re.I),
    re.compile(r"^(?:TK|TR)\d+$", re.I),
]
_IMMEDIATE = re.compile(r"^(?:[#&][0-9A-F]+|[-+]?\d+(?:\.\d+)?)$", re.I)


def normalize_mnemonic(value: str) -> str:
    v = re.sub(r"\s+", " ", value.strip().upper())
    # CX mnemonic text appears in both compact and spaced forms in the wild.
    aliases = {
        "LD NOT": "LDNOT",
        "AND NOT": "ANDNOT",
        "OR NOT": "ORNOT",
        "OUT NOT": "OUTNOT",
        "ANDLD": "AND LD",
        "ORLD": "OR LD",
    }
    return aliases.get(v, v)


def split_operands(text: str) -> list[str]:
    if not text.strip():
        return []
    try:
        return shlex.split(text, posix=False)
    except ValueError:
        return text.split()


def parse_instruction(line: str) -> dict[str, Any]:
    raw = line.rstrip("\r\n")
    text = raw.strip()
    if not text:
        return {"raw": raw, "mnemonic": "", "function_code": None, "operands": [], "known_family": "empty"}

    # Match compound network operators before generic one-word mnemonic parsing.
    m = re.match(r"^(AND\s+LD|OR\s+LD)(?:\((\d+)\))?(?:\s+(.*))?$", text, re.I)
    if not m:
        m = re.match(r"^([A-Za-z@][A-Za-z0-9_@]*)(?:\((\d+)\))?(?:\s+(.*))?$", text)
    if not m:
        return {
            "raw": raw,
            "mnemonic": "",
            "function_code": None,
            "operands": [],
            "known_family": "invalid",
            "parse_error": "Unrecognized mnemonic line",
        }

    mnemonic = normalize_mnemonic(m.group(1))
    operands = split_operands(m.group(3) or "")
    return {
        "raw": raw,
        "mnemonic": mnemonic,
        "function_code": int(m.group(2)) if m.group(2) else None,
        "operands": operands,
        "known_family": instruction_family(mnemonic),
    }


def instruction_family(mnemonic: str) -> str:
    m = normalize_mnemonic(mnemonic)
    if m in CONTACTS:
        return "contact"
    if m in BLOCK_OPS:
        return "logic_block"
    if m in COILS:
        return "coil"
    if m in STATE_WRITES:
        return "state_write"
    if m == "KEEP":
        return "stateful"
    if m in TIMERS:
        return "timer"
    if m in COUNTERS:
        return "counter"
    if m in TERMINATORS:
        return "terminator"
    if m in CONTROL_FLOW:
        return "control_flow"
    if m in MOVE_FAMILY:
        return "move"
    if m in MATH_DEST_LAST:
        return "math"
    return "other"


def operand_kind(operand: str) -> str:
    op = operand.strip().rstrip(",")
    deref = op.lstrip("@*")
    # Check address syntax before numeric immediates because bare CIO bits such as
    # 0.00 are syntactically decimal-looking.
    if any(p.match(deref) for p in _ADDRESS_PATTERNS):
        return "address"
    if _IMMEDIATE.match(deref):
        return "immediate"
    # Symbolic names are valid operands in CX-Programmer mnemonic view.
    if re.match(r"^[A-Za-z_][A-Za-z0-9_.$]*$", deref):
        return "symbol"
    return "expression"


def _add_ref(target: list[str], value: str) -> None:
    if value and operand_kind(value) in {"address", "symbol", "expression"} and value not in target:
        target.append(value)


def analyze_rung(instructions: Iterable[str], symbols: dict[str, str] | None = None) -> dict[str, Any]:
    parsed = [parse_instruction(line) for line in instructions]
    reads: list[str] = []
    writes: list[str] = []
    output_writes: list[str] = []
    set_writes: list[str] = []
    reset_writes: list[str] = []
    timers: list[str] = []
    counters: list[str] = []
    unknown: list[str] = []
    errors: list[str] = []

    for inst in parsed:
        m = inst["mnemonic"]
        ops = inst["operands"]
        fam = inst["known_family"]
        if fam == "invalid":
            errors.append(inst.get("parse_error", "Invalid instruction"))
            continue
        if fam == "other":
            unknown.append(m)
        if m in CONTACTS and ops:
            _add_ref(reads, ops[0])
        elif m in COILS and ops:
            _add_ref(writes, ops[0]); _add_ref(output_writes, ops[0])
        elif m == "SET" and ops:
            _add_ref(writes, ops[0]); _add_ref(set_writes, ops[0])
        elif m == "RSET" and ops:
            _add_ref(writes, ops[0]); _add_ref(reset_writes, ops[0])
        elif m == "KEEP" and ops:
            _add_ref(writes, ops[-1]); _add_ref(set_writes, ops[-1]); _add_ref(reset_writes, ops[-1])
        elif m in TIMERS and ops:
            _add_ref(writes, ops[0]); _add_ref(timers, ops[0])
            for op in ops[1:]:
                if operand_kind(op) != "immediate": _add_ref(reads, op)
        elif m in COUNTERS and ops:
            _add_ref(writes, ops[0]); _add_ref(counters, ops[0])
            for op in ops[1:]:
                if operand_kind(op) != "immediate": _add_ref(reads, op)
        elif m in MOVE_FAMILY and ops:
            for op in ops[:-1]:
                if operand_kind(op) != "immediate": _add_ref(reads, op)
            _add_ref(writes, ops[-1])
        elif m in MATH_DEST_LAST and ops:
            for op in ops[:-1]:
                if operand_kind(op) != "immediate": _add_ref(reads, op)
            _add_ref(writes, ops[-1])
        elif fam not in {"logic_block", "terminator", "control_flow"}:
            # Conservative for unknown CPU-specific instructions: operands are references,
            # but we do not guess write direction.
            for op in ops:
                if operand_kind(op) != "immediate": _add_ref(reads, op)

    expression = boolean_expression(parsed)
    symbol_names = symbols or {}
    return {
        "instructions": parsed,
        "reads": reads,
        "writes": writes,
        "output_writes": output_writes,
        "set_writes": set_writes,
        "reset_writes": reset_writes,
        "timers": timers,
        "counters": counters,
        "stateful": bool(set_writes or reset_writes or any(x["mnemonic"] == "KEEP" for x in parsed)),
        "has_control_flow": any(x["mnemonic"] in CONTROL_FLOW for x in parsed),
        "unknown_mnemonics": sorted(set(filter(None, unknown))),
        "parse_errors": errors,
        "boolean_expression": expression,
        "resolved": {
            ref: symbol_names.get(ref, "") for ref in sorted(set(reads + writes))
        },
    }


def _leaf(address: str, nc: bool = False) -> dict[str, Any]:
    return {"type": "contact", "address": address, "normally_closed": nc}


def _combine(op: str, left: dict[str, Any] | None, right: dict[str, Any]) -> dict[str, Any]:
    if left is None:
        return right
    if left.get("op") == op:
        return {"op": op, "items": [*left["items"], right]}
    return {"op": op, "items": [left, right]}


def boolean_expression(parsed: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Recover a boolean AST for the common LD/AND/OR/AND LD/OR LD subset.

    Output/state instructions are ignored. Any unsupported logic instruction makes the
    expression unknown instead of inventing semantics.
    """
    current: dict[str, Any] | None = None
    stack: list[dict[str, Any]] = []
    saw_logic = False
    for inst in parsed:
        m, ops = inst["mnemonic"], inst["operands"]
        if m in {"OUT", "OUTNOT", "SET", "RSET", "END"}:
            continue
        if m == "LD" and ops:
            if current is not None:
                stack.append(current)
            current = _leaf(ops[0], False); saw_logic = True
        elif m == "LDNOT" and ops:
            if current is not None:
                stack.append(current)
            current = _leaf(ops[0], True); saw_logic = True
        elif m in {"AND", "ANDNOT", "OR", "ORNOT"} and ops and current is not None:
            op = "and" if m.startswith("AND") else "or"
            current = _combine(op, current, _leaf(ops[0], m.endswith("NOT"))); saw_logic = True
        elif m in BLOCK_OPS and current is not None and stack:
            left = stack.pop()
            current = _combine("and" if m == "AND LD" else "or", left, current); saw_logic = True
        elif inst["known_family"] in {"empty", "coil", "state_write", "terminator"}:
            continue
        else:
            return None
    if not saw_logic or stack:
        return None
    return current


def _compile_expr(expr: dict[str, Any]) -> list[str]:
    if expr.get("type") == "contact" or "address" in expr and "op" not in expr:
        address = str(expr["address"]).strip()
        if not address:
            raise ValueError("Contact address cannot be empty")
        return [("LDNOT " if bool(expr.get("normally_closed", False)) else "LD ") + address]
    op = str(expr.get("op", "")).lower()
    items = expr.get("items")
    if op not in {"and", "or"} or not isinstance(items, list) or len(items) < 2:
        raise ValueError("Expression node must be contact or {'op':'and|or','items':[...]} with at least 2 items")
    result = _compile_expr(items[0])
    for child in items[1:]:
        result.extend(_compile_expr(child))
        result.append("AND LD" if op == "and" else "OR LD")
    return result


def compile_rung(expression: dict[str, Any], outputs: list[dict[str, str]]) -> list[str]:
    lines = _compile_expr(expression)
    if not outputs:
        raise ValueError("At least one output is required")
    for output in outputs:
        kind = normalize_mnemonic(output.get("kind", "OUT"))
        address = str(output.get("address", "")).strip()
        if kind not in {"OUT", "OUTNOT", "SET", "RSET"}:
            raise ValueError(f"Structured output kind not supported: {kind}")
        if not address:
            raise ValueError("Output address cannot be empty")
        lines.append(f"{kind} {address}")
    return lines


def simulate_boolean_rung(instructions: Iterable[str], bits: dict[str, bool], state: dict[str, bool] | None = None) -> dict[str, Any]:
    """Simulate only the boolean mnemonic subset; never claims PLC-cycle equivalence."""
    parsed = [parse_instruction(line) for line in instructions]
    current: bool | None = None
    stack: list[bool] = []
    outputs: dict[str, bool] = {}
    next_state = dict(state or {})

    def value(address: str) -> bool:
        return bool(bits.get(address, next_state.get(address, False)))

    for inst in parsed:
        m, ops = inst["mnemonic"], inst["operands"]
        if m == "LD" and ops:
            if current is not None: stack.append(current)
            current = value(ops[0])
        elif m == "LDNOT" and ops:
            if current is not None: stack.append(current)
            current = not value(ops[0])
        elif m in {"AND", "ANDNOT", "OR", "ORNOT"} and ops and current is not None:
            v = value(ops[0]); v = (not v) if m.endswith("NOT") else v
            current = current and v if m.startswith("AND") else current or v
        elif m in BLOCK_OPS and current is not None and stack:
            left = stack.pop()
            current = left and current if m == "AND LD" else left or current
        elif m in COILS and ops and current is not None:
            outputs[ops[0]] = (not current) if m == "OUTNOT" else current
        elif m == "SET" and ops and current is not None:
            if current: next_state[ops[0]] = True
        elif m == "RSET" and ops and current is not None:
            if current: next_state[ops[0]] = False
        elif m == "END":
            continue
        else:
            return {"supported": False, "reason": f"Unsupported for boolean simulator: {inst['raw']}", "outputs": outputs, "state": next_state}
    if stack:
        return {"supported": False, "reason": "Unbalanced LD logic blocks", "outputs": outputs, "state": next_state}
    return {"supported": True, "logic_result": current, "outputs": outputs, "state": next_state}
