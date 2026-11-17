"""
Standalone Omron PLC Ladder Scan Cycle Simulator.
Simulates execution of contacts, coils, timers, counters, and arithmetic
without physical hardware or CX-Programmer.
"""

from __future__ import annotations

import re
from typing import Any
from hardware import parse_address_info, strip_function_code


class LadderSimulator:
    """Cycle-by-cycle logic execution simulator for Omron ladder instructions."""

    def __init__(self):
        self.bits: dict[str, bool] = {}
        self.words: dict[str, int] = {}
        self.prev_bits: dict[str, bool] = {}
        self.timers: dict[str, dict[str, Any]] = {}
        self.counters: dict[str, dict[str, Any]] = {}
        self.scan_count: int = 0

    def _norm_addr(self, address: str) -> str:
        addr = address.strip().upper()
        # Normalize Timer T0 / T00 / T000 / T0000 -> T000 (or T1000 for >=1000)
        m_tim = re.match(r"^(?:TIM|T)(\d{1,4})$", addr)
        if m_tim:
            return f"T{int(m_tim.group(1)):03d}"
        # Normalize Counter C0 / C001 / C0001 -> C001
        m_cnt = re.match(r"^(?:CNT|C)(\d{1,4})$", addr)
        if m_cnt:
            return f"C{int(m_cnt.group(1)):03d}"
        # Normalise 0.00 -> CIO0.00 or 100.01 -> CIO100.01
        m = re.match(r"^(\d+)\.(\d{1,2})$", addr)
        if m:
            return f"CIO{m.group(1)}.{int(m.group(2)):02d}"
        m_area_bit = re.match(r"^([A-Z]+)(\d+)\.(\d{1,2})$", addr)
        if m_area_bit:
            return f"{m_area_bit.group(1)}{int(m_area_bit.group(2))}.{int(m_area_bit.group(3)):02d}"
        m_word = re.match(r"^\d+$", addr)
        if m_word:
            return f"CIO{addr}"
        return addr

    def set_bit(self, address: str, value: bool) -> None:
        self.bits[self._norm_addr(address)] = bool(value)

    def get_bit(self, address: str) -> bool:
        addr = self._norm_addr(address)
        if addr in {"P_ON", "CF113.00"}:
            return True
        if addr in {"P_OFF", "CF113.01"}:
            return False
        if addr in {"P_FIRST_CYCLE", "A200.11"}:
            return self.scan_count == 1
        # Check timer/counter completion contacts (e.g. T000 or C001)
        if addr.startswith("T") and addr[1:].isdigit():
            t = self.timers.get(addr)
            return t["done"] if t else False
        if addr.startswith("C") and addr[1:].isdigit():
            c = self.counters.get(addr)
            return c["done"] if c else False
        return self.bits.get(addr, False)

    def set_word(self, address: str, value: int) -> None:
        self.words[self._norm_addr(address)] = int(value) & 0xFFFF

    def get_word(self, address: str) -> int:
        addr = address.strip()
        if addr.startswith("#"):
            return int(addr[1:], 16) & 0xFFFF
        if addr.startswith("&"):
            return int(addr[1:]) & 0xFFFF
        return self.words.get(self._norm_addr(addr), 0)

    def step_rung(self, instructions: list[str]) -> dict[str, Any]:
        """Execute a single ladder rung given its list of IL instructions."""
        stack: list[bool] = []
        rung_changes: dict[str, Any] = {}

        for line in instructions:
            line_clean = line.strip()
            if not line_clean or line_clean.startswith("'") or line_clean.startswith("//"):
                continue

            tokens = line_clean.split()
            cmd = strip_function_code(tokens[0])
            operands = tokens[1:] if len(tokens) > 1 else []

            # Contacts
            if cmd == "LD":
                stack.append(self.get_bit(operands[0]))
            elif cmd == "LDNOT":
                stack.append(not self.get_bit(operands[0]))
            elif cmd == "AND":
                val = self.get_bit(operands[0])
                if stack:
                    stack[-1] = stack[-1] and val
                else:
                    stack.append(val)
            elif cmd == "ANDNOT":
                val = not self.get_bit(operands[0])
                if stack:
                    stack[-1] = stack[-1] and val
                else:
                    stack.append(val)
            elif cmd == "OR":
                val = self.get_bit(operands[0])
                if stack:
                    stack[-1] = stack[-1] or val
                else:
                    stack.append(val)
            elif cmd == "ORNOT":
                val = not self.get_bit(operands[0])
                if stack:
                    stack[-1] = stack[-1] or val
                else:
                    stack.append(val)
            elif cmd == "ANDLD":
                if len(stack) >= 2:
                    b = stack.pop()
                    stack[-1] = stack[-1] and b
            elif cmd == "ORLD":
                if len(stack) >= 2:
                    b = stack.pop()
                    stack[-1] = stack[-1] or b

            # Coils & Outputs
            elif cmd == "OUT":
                power = stack[-1] if stack else False
                target = operands[0]
                old = self.get_bit(target)
                self.set_bit(target, power)
                if old != power:
                    rung_changes[target] = power
            elif cmd == "OUTNOT":
                power = not (stack[-1] if stack else False)
                target = operands[0]
                old = self.get_bit(target)
                self.set_bit(target, power)
                if old != power:
                    rung_changes[target] = power
            elif cmd == "SET":
                power = stack[-1] if stack else False
                if power:
                    target = operands[0]
                    self.set_bit(target, True)
                    rung_changes[target] = True
            elif cmd in {"RSET", "RST"}:
                power = stack[-1] if stack else False
                if power:
                    target = operands[0]
                    self.set_bit(target, False)
                    rung_changes[target] = False
            elif cmd == "KEEP":
                target = operands[0]
                if len(stack) >= 2:
                    rst_cond = stack.pop()
                    set_cond = stack[-1]
                else:
                    rst_cond = False
                    set_cond = stack[-1] if stack else False
                if rst_cond:
                    self.set_bit(target, False)
                    rung_changes[target] = False
                elif set_cond:
                    self.set_bit(target, True)
                    rung_changes[target] = True

            # Differential Edges
            elif cmd == "DIFU":
                power = stack[-1] if stack else False
                target = operands[0]
                prev = self.prev_bits.get(target, False)
                pulse = power and not prev
                self.set_bit(target, pulse)
                self.prev_bits[target] = power
                if pulse:
                    rung_changes[target] = True
            elif cmd == "DIFD":
                power = stack[-1] if stack else False
                target = operands[0]
                prev = self.prev_bits.get(target, False)
                pulse = not power and prev
                self.set_bit(target, pulse)
                self.prev_bits[target] = power
                if pulse:
                    rung_changes[target] = True

            # Timers
            elif cmd in {"TIM", "TIMX", "TIMH", "TIMHX"}:
                t_num = self._norm_addr(f"T{operands[0]}" if operands[0].isdigit() else operands[0])
                pv = self.get_word(operands[1]) if len(operands) > 1 else 10
                power = stack[-1] if stack else False
                t_state = self.timers.setdefault(t_num, {"pv": pv, "sv": pv, "done": False})
                if power:
                    if t_state["pv"] > 0:
                        t_state["pv"] -= 1
                    t_state["done"] = t_state["pv"] == 0
                else:
                    t_state["pv"] = pv
                    t_state["done"] = False
                rung_changes[t_num] = {"pv": t_state["pv"], "done": t_state["done"]}

            # Counters (2-input: LD pulse, LD reset, CNT num sv)
            elif cmd in {"CNT", "CNTX"}:
                c_num = self._norm_addr(f"C{operands[0]}" if operands[0].isdigit() else operands[0])
                sv = self.get_word(operands[1]) if len(operands) > 1 else 10
                c_state = self.counters.setdefault(c_num, {"pv": sv, "sv": sv, "done": False, "prev_in": False})
                if len(stack) >= 2:
                    reset_in = stack.pop()
                    pulse_in = stack[-1]
                else:
                    reset_in = False
                    pulse_in = stack[-1] if stack else False

                if reset_in:
                    c_state["pv"] = sv
                    c_state["done"] = False
                else:
                    if pulse_in and not c_state["prev_in"] and c_state["pv"] > 0:
                        c_state["pv"] -= 1
                    c_state["done"] = c_state["pv"] == 0
                c_state["prev_in"] = pulse_in
                rung_changes[c_num] = {"pv": c_state["pv"], "done": c_state["done"]}

            # Math & Data Transfer
            elif cmd == "MOV":
                power = stack[-1] if stack else True
                if power and len(operands) >= 2:
                    val = self.get_word(operands[0])
                    dest = operands[1]
                    self.set_word(dest, val)
                    rung_changes[dest] = val
            elif cmd == "INC":
                power = stack[-1] if stack else True
                if power and len(operands) >= 1:
                    dest = operands[0]
                    new_val = (self.get_word(dest) + 1) & 0xFFFF
                    self.set_word(dest, new_val)
                    rung_changes[dest] = new_val
            elif cmd == "DEC":
                power = stack[-1] if stack else True
                if power and len(operands) >= 1:
                    dest = operands[0]
                    new_val = (self.get_word(dest) - 1) & 0xFFFF
                    self.set_word(dest, new_val)
                    rung_changes[dest] = new_val

        return rung_changes

    def run_scan(self, rungs: list[dict[str, Any]], inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute one complete scan cycle over a list of rungs."""
        self.scan_count += 1
        if inputs:
            for k, v in inputs.items():
                if isinstance(v, bool):
                    self.set_bit(k, v)
                else:
                    self.set_word(k, int(v))

        scan_changes: dict[str, Any] = {}
        for r in rungs:
            insts = r.get("instructions", [])
            changes = self.step_rung(insts)
            scan_changes.update(changes)

        return {
            "scan": self.scan_count,
            "inputs_applied": inputs or {},
            "changes": scan_changes,
            "bits": {k: v for k, v in self.bits.items() if v},
            "timers": {k: v for k, v in self.timers.items()},
            "counters": {k: v for k, v in self.counters.items()},
        }
