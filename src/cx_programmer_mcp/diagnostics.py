from __future__ import annotations

from collections import defaultdict
from typing import Any

from .cxt import CxtProject
from .ladder import analyze_rung


def _symbol_map(project: CxtProject) -> dict[str, str]:
    result: dict[str, str] = {}
    for s in project.list_symbols("global"):
        if s["address"]:
            result[s["address"]] = s["name"] or s["comment"]
    return result


def cross_reference(project: CxtProject, address: str | None = None) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    symbols = _symbol_map(project)
    target = address.lower() if address else None
    for program in project.list_programs():
        pname = program["name"]
        for section in project.list_sections(pname):
            sname = section["name"]
            for rung in project.get_rungs(pname, sname, include_empty=False):
                analysis = analyze_rung(rung["instructions"], symbols)
                roles: dict[str, set[str]] = defaultdict(set)
                for ref in analysis["reads"]: roles[ref].add("read")
                for ref in analysis["writes"]: roles[ref].add("write")
                for ref in analysis["output_writes"]: roles[ref].add("coil")
                for ref in analysis["set_writes"]: roles[ref].add("set")
                for ref in analysis["reset_writes"]: roles[ref].add("reset")
                for ref, rroles in roles.items():
                    if target is not None and ref.lower() != target:
                        continue
                    refs.append({
                        "address": ref,
                        "symbol": symbols.get(ref, ""),
                        "roles": sorted(rroles),
                        "program": pname,
                        "section": sname,
                        "rung_index": rung["index"],
                        "comment": rung["comment"],
                    })
    return refs


def semantic_program(project: CxtProject) -> dict[str, Any]:
    symbols = _symbol_map(project)
    programs = []
    for p in project.list_programs():
        sections = []
        for s in project.list_sections(p["name"]):
            rungs = []
            for r in project.get_rungs(p["name"], s["name"], include_empty=False):
                rungs.append({**r, "analysis": analyze_rung(r["instructions"], symbols)})
            sections.append({"name": s["name"], "rungs": rungs})
        programs.append({"name": p["name"], "sections": sections})
    return {"programs": programs, "symbols": project.list_symbols("global")}


def program_diagnostics(project: CxtProject) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    info: list[dict[str, Any]] = []
    refs = cross_reference(project)
    by_addr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ref in refs:
        by_addr[ref["address"]].append(ref)

    for addr, occurrences in sorted(by_addr.items()):
        coil_writers = [x for x in occurrences if "coil" in x["roles"]]
        set_writers = [x for x in occurrences if "set" in x["roles"]]
        reset_writers = [x for x in occurrences if "reset" in x["roles"]]
        if len(coil_writers) > 1:
            warnings.append({"code": "duplicate_coil", "address": addr, "severity": "warning", "references": coil_writers})
        if coil_writers and (set_writers or reset_writers):
            warnings.append({"code": "mixed_direct_and_latched_write", "address": addr, "severity": "warning", "references": occurrences})
        if set_writers and not reset_writers:
            warnings.append({"code": "set_without_reset", "address": addr, "severity": "warning", "references": set_writers})
        if reset_writers and not set_writers:
            warnings.append({"code": "reset_without_set", "address": addr, "severity": "info", "references": reset_writers})

    all_refs = {x["address"].lower() for x in refs}
    for symbol in project.list_symbols("global"):
        addr = symbol["address"]
        if addr and addr.lower() not in all_refs:
            info.append({"code": "unused_symbol", "address": addr, "name": symbol["name"], "comment": symbol["comment"]})

    unknowns: list[dict[str, Any]] = []
    for p in project.list_programs():
        for s in project.list_sections(p["name"]):
            for r in project.get_rungs(p["name"], s["name"], include_empty=False):
                a = analyze_rung(r["instructions"])
                if a["unknown_mnemonics"]:
                    unknowns.append({"program": p["name"], "section": s["name"], "rung_index": r["index"], "mnemonics": a["unknown_mnemonics"]})
    if unknowns:
        info.append({"code": "cpu_specific_or_unclassified_mnemonics", "references": unknowns})

    return {"warning_count": len(warnings), "warnings": warnings, "info": info}
