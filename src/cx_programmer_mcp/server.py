from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .cxt import CxtError, CxtProject
from .diagnostics import cross_reference, program_diagnostics, semantic_program
from .ladder import analyze_rung as analyze_mnemonic_rung
from .ladder import compile_rung, simulate_boolean_rung
from .recipes import apply_exclusive_latch, exclusive_latch_plan
from .session import ProjectSession
from .templates import create_project as create_project_from_native_template, list_templates

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)
mcp = MCPServer("cx-programmer-program-editor")

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
SESSION_MUTATION = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False)
SESSION_ADDITIVE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
LOCAL_FILE_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False)
LOCAL_APP_LAUNCH = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)

_PROJECTS: dict[str, ProjectSession] = {}


def _allowed_path(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    raw_roots = os.environ.get("CX_MCP_ALLOWED_ROOTS", "").strip()
    if not raw_roots:
        return p
    roots = [Path(x).expanduser().resolve() for x in raw_roots.split(os.pathsep) if x.strip()]
    if not any(p == root or p.is_relative_to(root) for root in roots):
        raise CxtError(f"Path is outside CX_MCP_ALLOWED_ROOTS: {p}")
    return p


def _session(project_id: str) -> ProjectSession:
    try:
        return _PROJECTS[project_id]
    except KeyError as exc:
        raise CxtError(f"Unknown project_id: {project_id}") from exc


def _project(project_id: str) -> CxtProject:
    return _session(project_id).project


def _with_revision(session: ProjectSession, payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {**payload, "revision": session.revision}
    return {"result": payload, "revision": session.revision}


def _symbol_map(project: CxtProject) -> dict[str, str]:
    return {s["address"]: (s["name"] or s["comment"]) for s in project.list_symbols("global") if s["address"]}


def _rung(project: CxtProject, program_name: str, section_name: str, rung_index: int) -> dict[str, Any]:
    rungs = project.get_rungs(program_name, section_name, include_empty=True)
    if not 0 <= rung_index < len(rungs):
        raise CxtError(f"Rung index out of range: {rung_index}")
    return rungs[rung_index]


def _apply_patch_op(project: CxtProject, op: dict[str, Any]) -> Any:
    kind = str(op.get("op", "")).strip().lower()
    if kind == "replace_rung":
        return project.replace_rung(op["program"], op["section"], int(op["index"]), list(op["instructions"]), op.get("comment"))
    if kind == "insert_rung":
        return project.insert_rung(op["program"], op["section"], int(op["index"]), list(op["instructions"]), op.get("comment", ""))
    if kind == "delete_rung":
        project.delete_rung(op["program"], op["section"], int(op["index"])); return {"deleted": True}
    if kind == "set_rung_comment":
        project.set_rung_comment(op["program"], op["section"], int(op["index"]), str(op.get("comment", ""))); return {"updated": True}
    if kind == "create_section":
        project.create_section(op["program"], op["section"], op.get("before_section", "END")); return {"created": True}
    if kind == "rename_section":
        project.rename_section(op["program"], op["section"], op["new_name"]); return {"renamed": True}
    if kind == "delete_section":
        project.delete_section(op["program"], op["section"]); return {"deleted": True}
    if kind == "upsert_symbol":
        return project.upsert_symbol(
            op["address"], op.get("name", ""), op.get("data_type", "BOOL"), op.get("comment", ""),
            op.get("scope", "global"), op.get("program_name"),
        )
    if kind == "delete_symbol":
        return {"deleted": project.delete_symbol(op["address"], op.get("scope", "global"), op.get("program_name"))}
    raise CxtError(f"Unsupported patch operation: {kind}")


@mcp.tool(annotations=READ_ONLY)
def list_project_templates() -> dict[str, Any]:
    """List bundled blank CX-Programmer project templates available for native-structure project creation."""
    return {"templates": list_templates()}


@mcp.tool(annotations=LOCAL_FILE_WRITE)
def create_project_from_template(
    template_id: str = "CJ2M_CPU11",
    project_name: str = "NewProject",
    plc_name: str = "NewPLC1",
    program_name: str = "NewProgram1",
    section_name: str = "Section1",
    template_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create a new offline CX-Programmer project session from a native CXT/CXP template.

    Use a bundled template_id for supported CPUs. For maximum fidelity with another CPU or CX-Programmer
    release, create one blank project in CX-Programmer and pass its .CXT/.CXP as template_path. The MCP
    clones the opaque PLC setup/I/O/unit configuration from that native template and blanks only the program
    surfaces. Optionally saves the new project as .CXT immediately.
    """
    safe_template = _allowed_path(template_path) if template_path else None
    project, info = create_project_from_native_template(
        template_id=template_id,
        template_path=safe_template,
        project_name=project_name,
        plc_name=plc_name,
        program_name=program_name,
        section_name=section_name,
        blank_program=True,
    )
    project_id = uuid.uuid4().hex[:12]
    session = ProjectSession(project)
    _PROJECTS[project_id] = session

    saved_path = None
    if output_path:
        output = _allowed_path(output_path)
        if output.suffix.lower() != ".cxt":
            output = output.with_suffix(".cxt")
        if output.exists() and not overwrite:
            _PROJECTS.pop(project_id, None)
            raise CxtError(f"Output already exists: {output}. Set overwrite=true to replace it.")
        saved_path = project.save_cxt(output, backup=bool(overwrite and output.exists()))

    return {
        "project_id": project_id,
        "revision": 0,
        "saved_path": saved_path,
        "summary": project.project_summary(),
        "creation": info,
        "session": session.status(),
    }


@mcp.tool(annotations=SESSION_ADDITIVE)
def load_project(path: str) -> dict[str, Any]:
    """Load a CX-Programmer .CXP or .CXT into an offline, in-memory editing session.

    The input file is never modified. Set CX_MCP_ALLOWED_ROOTS to restrict filesystem access.
    """
    safe = _allowed_path(path)
    project = CxtProject.from_path(safe)
    project_id = uuid.uuid4().hex[:12]
    session = ProjectSession(project)
    _PROJECTS[project_id] = session
    return {"project_id": project_id, "revision": 0, "summary": project.project_summary(), "session": session.status()}


@mcp.tool(annotations=SESSION_MUTATION)
def close_project(project_id: str) -> dict[str, bool]:
    """Discard an in-memory project session without writing changes."""
    return {"closed": _PROJECTS.pop(project_id, None) is not None}


@mcp.tool(annotations=READ_ONLY)
def session_status(project_id: str) -> dict[str, Any]:
    """Return revision, dirty state, undo/redo depth, and program-scope integrity."""
    return _session(project_id).status()


@mcp.tool(annotations=READ_ONLY)
def project_summary(project_id: str) -> dict[str, Any]:
    """Return PLC identity and the program/section tree without PLC setup payloads."""
    s = _session(project_id)
    return _with_revision(s, s.project.project_summary())


@mcp.tool(annotations=READ_ONLY)
def list_programs(project_id: str) -> dict[str, Any]:
    """List programs and their section names."""
    s = _session(project_id)
    return {"revision": s.revision, "programs": s.project.list_programs()}


@mcp.tool(annotations=READ_ONLY)
def get_program_context(project_id: str, program_name: str, include_empty_rungs: bool = False, structured: bool = True) -> dict[str, Any]:
    """Return AI-friendly program context: ladder, comments, symbols and optional rung analysis."""
    s = _session(project_id)
    base = s.project.get_program_context(program_name, include_empty_rungs)
    if structured:
        symbols = _symbol_map(s.project)
        for section in base["sections"]:
            for rung in section["rungs"]:
                rung["analysis"] = analyze_mnemonic_rung(rung["instructions"], symbols)
    return {"revision": s.revision, **base}


@mcp.tool(annotations=READ_ONLY)
def list_sections(project_id: str, program_name: str) -> dict[str, Any]:
    """List sections and rung counts for one program."""
    s = _session(project_id)
    return {"revision": s.revision, "sections": s.project.list_sections(program_name)}


@mcp.tool(annotations=READ_ONLY)
def get_rungs(project_id: str, program_name: str, section_name: str, include_empty: bool = True, structured: bool = True) -> dict[str, Any]:
    """Read rungs from one section. structured=true adds read/write and boolean-expression analysis."""
    s = _session(project_id)
    rungs = s.project.get_rungs(program_name, section_name, include_empty)
    if structured:
        symbols = _symbol_map(s.project)
        for rung in rungs:
            rung["analysis"] = analyze_mnemonic_rung(rung["instructions"], symbols)
    return {"revision": s.revision, "rungs": rungs}


@mcp.tool(annotations=READ_ONLY)
def analyze_rung(project_id: str, program_name: str, section_name: str, rung_index: int) -> dict[str, Any]:
    """Parse one rung into structured mnemonic, boolean AST, reads/writes, stateful writes, timers and counters."""
    s = _session(project_id)
    rung = _rung(s.project, program_name, section_name, rung_index)
    return {"revision": s.revision, "rung": rung, "analysis": analyze_mnemonic_rung(rung["instructions"], _symbol_map(s.project))}


@mcp.tool(annotations=READ_ONLY)
def simulate_rung(project_id: str, program_name: str, section_name: str, rung_index: int, bits: dict[str, bool], state: dict[str, bool] | None = None) -> dict[str, Any]:
    """Evaluate the supported boolean mnemonic subset for reasoning/testing only, not PLC-cycle simulation."""
    s = _session(project_id)
    rung = _rung(s.project, program_name, section_name, rung_index)
    return {"revision": s.revision, **simulate_boolean_rung(rung["instructions"], bits, state)}


@mcp.tool(annotations=READ_ONLY)
def search_program(project_id: str, query: str) -> dict[str, Any]:
    """Search mnemonic text, addresses, comments, and global/local symbols."""
    s = _session(project_id)
    return {"revision": s.revision, "hits": s.project.search(query)}


@mcp.tool(annotations=READ_ONLY)
def cross_reference_address(project_id: str, address: str) -> dict[str, Any]:
    """Find every program reference to an address and classify it as read/write/coil/set/reset."""
    s = _session(project_id)
    return {"revision": s.revision, "address": address, "references": cross_reference(s.project, address)}


@mcp.tool(annotations=READ_ONLY)
def program_diagnostics_tool(project_id: str) -> dict[str, Any]:
    """Report duplicate coils, mixed writes, SET/RSET imbalance, unused symbols, and unclassified instructions."""
    s = _session(project_id)
    return {"revision": s.revision, **program_diagnostics(s.project)}


@mcp.tool(annotations=READ_ONLY)
def compile_structured_rung(expression: dict[str, Any], outputs: list[dict[str, str]]) -> dict[str, Any]:
    """Compile a boolean AST into CX mnemonic using LD/AND LD/OR LD plus OUT/SET/RSET outputs.

    This is a preview and does not edit a project.
    """
    lines = compile_rung(expression, outputs)
    return {"instructions": lines, "analysis": analyze_mnemonic_rung(lines)}


@mcp.tool(annotations=SESSION_MUTATION)
def replace_rung(project_id: str, program_name: str, section_name: str, rung_index: int, instructions: list[str], comment: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    """Replace one rung using CX-Programmer mnemonic lines. Revision guard prevents stale edits."""
    s = _session(project_id)
    result = s.edit(lambda p: p.replace_rung(program_name, section_name, rung_index, instructions, comment), expected_revision)
    return _with_revision(s, result)


@mcp.tool(annotations=SESSION_MUTATION)
def replace_rung_structured(project_id: str, program_name: str, section_name: str, rung_index: int, expression: dict[str, Any], outputs: list[dict[str, str]], comment: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    """Replace a rung from a structured boolean expression instead of raw mnemonic text."""
    instructions = compile_rung(expression, outputs)
    return replace_rung(project_id, program_name, section_name, rung_index, instructions, comment, expected_revision)


@mcp.tool(annotations=SESSION_MUTATION)
def insert_rung(project_id: str, program_name: str, section_name: str, rung_index: int, instructions: list[str], comment: str = "", expected_revision: int | None = None) -> dict[str, Any]:
    """Insert a mnemonic rung at a zero-based rung index."""
    s = _session(project_id)
    result = s.edit(lambda p: p.insert_rung(program_name, section_name, rung_index, instructions, comment), expected_revision)
    return _with_revision(s, result)


@mcp.tool(annotations=SESSION_MUTATION)
def insert_rung_structured(project_id: str, program_name: str, section_name: str, rung_index: int, expression: dict[str, Any], outputs: list[dict[str, str]], comment: str = "", expected_revision: int | None = None) -> dict[str, Any]:
    """Insert a rung compiled from a structured boolean expression."""
    instructions = compile_rung(expression, outputs)
    return insert_rung(project_id, program_name, section_name, rung_index, instructions, comment, expected_revision)


@mcp.tool(annotations=SESSION_MUTATION)
def delete_rung(project_id: str, program_name: str, section_name: str, rung_index: int, expected_revision: int | None = None) -> dict[str, Any]:
    """Delete one rung and repair CX-Programmer rung indexes/counts."""
    s = _session(project_id)
    s.edit(lambda p: p.delete_rung(program_name, section_name, rung_index), expected_revision)
    return {"deleted": True, "revision": s.revision}


@mcp.tool(annotations=SESSION_MUTATION)
def set_rung_comment(project_id: str, program_name: str, section_name: str, rung_index: int, comment: str, expected_revision: int | None = None) -> dict[str, Any]:
    """Set the comment attached to one rung."""
    s = _session(project_id)
    s.edit(lambda p: p.set_rung_comment(program_name, section_name, rung_index, comment), expected_revision)
    return {"updated": True, "revision": s.revision}


@mcp.tool(annotations=SESSION_MUTATION)
def create_section(project_id: str, program_name: str, section_name: str, before_section: str | None = "END", expected_revision: int | None = None) -> dict[str, Any]:
    """Create a program section, normally immediately before END."""
    s = _session(project_id)
    s.edit(lambda p: p.create_section(program_name, section_name, before_section), expected_revision)
    return {"created": True, "revision": s.revision}


@mcp.tool(annotations=SESSION_MUTATION)
def rename_section(project_id: str, program_name: str, section_name: str, new_name: str, expected_revision: int | None = None) -> dict[str, Any]:
    """Rename one program section."""
    s = _session(project_id)
    s.edit(lambda p: p.rename_section(program_name, section_name, new_name), expected_revision)
    return {"renamed": True, "revision": s.revision}


@mcp.tool(annotations=SESSION_MUTATION)
def delete_section(project_id: str, program_name: str, section_name: str, expected_revision: int | None = None) -> dict[str, Any]:
    """Delete a section. END is protected."""
    s = _session(project_id)
    s.edit(lambda p: p.delete_section(program_name, section_name), expected_revision)
    return {"deleted": True, "revision": s.revision}


@mcp.tool(annotations=READ_ONLY)
def list_symbols(project_id: str, scope: str = "global", program_name: str | None = None) -> dict[str, Any]:
    """List global or local CX-Programmer symbols/address comments."""
    s = _session(project_id)
    return {"revision": s.revision, "symbols": s.project.list_symbols(scope, program_name)}


@mcp.tool(annotations=SESSION_MUTATION)
def upsert_symbol(project_id: str, address: str, name: str = "", data_type: str = "BOOL", comment: str = "", scope: str = "global", program_name: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    """Create or update a global/local program symbol without touching PLC setup or I/O tables."""
    s = _session(project_id)
    result = s.edit(lambda p: p.upsert_symbol(address, name, data_type, comment, scope, program_name), expected_revision)
    return _with_revision(s, result)


@mcp.tool(annotations=SESSION_MUTATION)
def delete_symbol(project_id: str, address: str, scope: str = "global", program_name: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    """Delete a symbol-table entry by address."""
    s = _session(project_id)
    deleted = s.edit(lambda p: p.delete_symbol(address, scope, program_name), expected_revision)
    return {"deleted": deleted, "revision": s.revision}


@mcp.tool(annotations=SESSION_MUTATION)
def apply_program_patch(project_id: str, operations: list[dict[str, Any]], expected_revision: int | None = None) -> dict[str, Any]:
    """Apply multiple program-only edits atomically; any failing operation rolls the entire patch back."""
    if not operations:
        raise CxtError("operations cannot be empty")
    s = _session(project_id)
    results: list[Any] = []

    def run(project: CxtProject) -> None:
        for op in operations:
            results.append(_apply_patch_op(project, op))

    s.atomic(run, expected_revision)
    return {"applied": len(results), "results": results, "revision": s.revision}


@mcp.tool(annotations=READ_ONLY)
def plan_exclusive_latch(participants: list[dict[str, str]], reset_address: str) -> dict[str, Any]:
    """Preview a first-press-wins latch recipe using SET/RSET; does not edit a project."""
    rungs = exclusive_latch_plan(participants, reset_address)
    return {"rungs": rungs, "note": "Review in CX-Programmer Program Check before PLC transfer."}


@mcp.tool(annotations=SESSION_MUTATION)
def apply_exclusive_latch_group(project_id: str, program_name: str, section_name: str, participants: list[dict[str, str]], reset_address: str, expected_revision: int | None = None) -> dict[str, Any]:
    """Replace a non-END section with a first-press-wins SET/RSET latch program plus one trailing empty rung."""
    s = _session(project_id)
    plan = s.atomic(lambda p: apply_exclusive_latch(p, program_name, section_name, participants, reset_address), expected_revision)
    return {"applied": True, "revision": s.revision, "rungs": plan, "diagnostics": program_diagnostics(s.project)}


@mcp.tool(annotations=SESSION_MUTATION)
def undo_last_edit(project_id: str, expected_revision: int | None = None) -> dict[str, Any]:
    """Undo the last in-memory edit without touching disk."""
    return _session(project_id).undo(expected_revision)


@mcp.tool(annotations=SESSION_MUTATION)
def redo_last_edit(project_id: str, expected_revision: int | None = None) -> dict[str, Any]:
    """Redo the last undone in-memory edit."""
    return _session(project_id).redo(expected_revision)


@mcp.tool(annotations=READ_ONLY)
def validate_program(project_id: str) -> dict[str, Any]:
    """Run CXT structural checks, protected-scope integrity checks, and ladder diagnostics."""
    s = _session(project_id)
    structural = s.project.validate()
    integrity = s.integrity()
    diagnostics = program_diagnostics(s.project)
    return {
        "ok": bool(structural["ok"] and integrity["ok"]),
        "revision": s.revision,
        "structural": structural,
        "scope_integrity": integrity,
        "diagnostics": diagnostics,
    }


@mcp.tool(annotations=READ_ONLY)
def project_diff(project_id: str, context_lines: int = 3) -> dict[str, Any]:
    """Show a unified CXT diff of pending edits versus the loaded project."""
    s = _session(project_id)
    return {"revision": s.revision, "diff": s.project.diff(context_lines)}


@mcp.tool(annotations=READ_ONLY)
def semantic_snapshot(project_id: str) -> dict[str, Any]:
    """Return program-only semantic JSON suitable for AI review or external versioning."""
    s = _session(project_id)
    return {"revision": s.revision, **semantic_program(s.project)}


@mcp.tool(annotations=LOCAL_FILE_WRITE)
def save_cxt(project_id: str, output_path: str, backup: bool = True, expected_revision: int | None = None, allow_source_overwrite: bool = False) -> dict[str, Any]:
    """Validate and save edited source as CXT. Source overwrite is refused unless explicitly allowed."""
    s = _session(project_id)
    s.assert_revision(expected_revision)
    output = _allowed_path(output_path)
    if output.suffix.lower() != ".cxt":
        output = output.with_suffix(".cxt")
    if s.source_path and output == Path(s.source_path).resolve() and not allow_source_overwrite:
        return {"saved": False, "reason": "Refusing to overwrite the loaded source; choose another CXT path or set allow_source_overwrite=true", "revision": s.revision}
    validation = validate_program(project_id)
    if not validation["ok"]:
        return {"saved": False, "validation": validation, "revision": s.revision}
    saved = s.project.save_cxt(output, backup=backup)
    return {"saved": True, "path": saved, "revision": s.revision, "validation": validation}


@mcp.tool(annotations=LOCAL_APP_LAUNCH)
def launch_in_cx_programmer(project_id: str, output_path: str, cx_programmer_exe: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    """Save a CXT and open it in locally installed CX-Programmer on Windows.

    This never performs GUI automation, online edit, PLC download, force-set/reset, or mode changes.
    """
    if os.name != "nt":
        return {"launched": False, "reason": "CX-Programmer launch helper is Windows-only"}
    exe = cx_programmer_exe or os.environ.get("CX_PROGRAMMER_EXE")
    if not exe:
        return {"launched": False, "reason": "Set CX_PROGRAMMER_EXE or pass cx_programmer_exe"}
    exe_path = Path(exe).expanduser().resolve()
    if not exe_path.exists():
        return {"launched": False, "reason": f"Executable not found: {exe_path}"}
    saved = save_cxt(project_id, output_path, backup=True, expected_revision=expected_revision)
    if not saved.get("saved"):
        return {"launched": False, **saved}
    subprocess.Popen([str(exe_path), saved["path"]])
    return {"launched": True, "path": saved["path"], "revision": saved["revision"], "validation": saved["validation"]}


# Resources let an MCP host fetch stable context without choosing a mutation tool.
@mcp.resource("cxprog://project/{project_id}/summary")
def summary_resource(project_id: str) -> str:
    return json.dumps(project_summary(project_id), ensure_ascii=False, indent=2)


@mcp.resource("cxprog://project/{project_id}/semantic")
def semantic_resource(project_id: str) -> str:
    return json.dumps(semantic_snapshot(project_id), ensure_ascii=False, indent=2)


@mcp.resource("cxprog://project/{project_id}/program/{program_name}")
def program_resource(project_id: str, program_name: str) -> str:
    return json.dumps(get_program_context(project_id, program_name, include_empty_rungs=False, structured=True), ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
