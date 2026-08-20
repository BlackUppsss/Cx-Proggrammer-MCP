from __future__ import annotations

from typing import Any

from .cxt import CxtProject, CxtError


def exclusive_latch_plan(participants: list[dict[str, str]], reset_address: str) -> list[dict[str, Any]]:
    if len(participants) < 2:
        raise CxtError("At least two participants are required")
    required = {"input", "latch", "output"}
    for i, p in enumerate(participants):
        missing = required - set(p)
        if missing:
            raise CxtError(f"Participant {i} missing fields: {', '.join(sorted(missing))}")
    latches = [p["latch"] for p in participants]
    if len({x.lower() for x in latches}) != len(latches):
        raise CxtError("Latch addresses must be unique")

    rungs: list[dict[str, Any]] = []
    for p in participants:
        instructions = [f"LD {p['input']}"]
        instructions.extend(f"ANDNOT {other}" for other in latches if other.lower() != p["latch"].lower())
        instructions.append(f"SET {p['latch']}")
        rungs.append({"comment": f"Latch winner {p.get('name') or p['latch']}", "instructions": instructions})
    for p in participants:
        rungs.append({
            "comment": f"Winner output {p.get('name') or p['output']}",
            "instructions": [f"LD {p['latch']}", f"OUT {p['output']}"],
        })
    reset = [f"LD {reset_address}"] + [f"RSET {p['latch']}" for p in participants]
    rungs.append({"comment": "Reset winner latches", "instructions": reset})
    return rungs


def apply_section_rungs(project: CxtProject, program_name: str, section_name: str, rungs: list[dict[str, Any]], preserve_trailing_empty: bool = True) -> None:
    existing = project.get_rungs(program_name, section_name, include_empty=True)
    if section_name.upper() == "END":
        raise CxtError("Refusing to replace the END section")
    # Reuse existing rung shells first to preserve as much native metadata as possible.
    for index, spec in enumerate(rungs):
        if index < len(existing):
            project.replace_rung(program_name, section_name, index, spec["instructions"], spec.get("comment", ""))
        else:
            project.insert_rung(program_name, section_name, index, spec["instructions"], spec.get("comment", ""))

    refreshed = project.get_rungs(program_name, section_name, include_empty=True)
    target_count = len(rungs)
    if preserve_trailing_empty:
        target_count += 1
    while len(refreshed) > target_count:
        project.delete_rung(program_name, section_name, len(refreshed) - 1)
        refreshed = project.get_rungs(program_name, section_name, include_empty=True)
    if preserve_trailing_empty:
        refreshed = project.get_rungs(program_name, section_name, include_empty=True)
        if len(refreshed) == len(rungs):
            project.insert_rung(program_name, section_name, len(rungs), [], "")
        elif refreshed[len(rungs)]["instructions"]:
            project.replace_rung(program_name, section_name, len(rungs), [], "")


def apply_exclusive_latch(project: CxtProject, program_name: str, section_name: str, participants: list[dict[str, str]], reset_address: str) -> list[dict[str, Any]]:
    plan = exclusive_latch_plan(participants, reset_address)
    apply_section_rungs(project, program_name, section_name, plan)
    return plan
