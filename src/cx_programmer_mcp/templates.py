from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from .cxt import CxtError, CxtProject


@dataclass(frozen=True)
class ProjectTemplate:
    template_id: str
    plc_model: str
    cx_programmer_version: str
    default_project_name: str
    default_plc_name: str
    default_program_name: str
    default_section_name: str
    resource_name: str
    note: str = ""


_BUILTINS: dict[str, ProjectTemplate] = {
    "CJ2M_CPU11": ProjectTemplate(
        template_id="CJ2M_CPU11",
        plc_model="CJ2M CPU11",
        cx_programmer_version="9.73",
        default_project_name="NewProject",
        default_plc_name="NewPLC1",
        default_program_name="NewProgram1",
        default_section_name="Section1",
        resource_name="templates/CJ2M_CPU11.cxt",
        note=(
            "Blank program template derived from a native CX-Programmer 9.73 CJ2M CPU11 CXT structure. "
            "Non-program PLC configuration is preserved from the template; Program/Section/Symbol surfaces are blank."
        ),
    ),
}


def list_templates() -> list[dict[str, Any]]:
    return [asdict(x) for x in _BUILTINS.values()]


def _load_builtin(template_id: str) -> CxtProject:
    try:
        meta = _BUILTINS[template_id]
    except KeyError as exc:
        raise CxtError(f"Unknown template_id: {template_id}. Available: {', '.join(sorted(_BUILTINS))}") from exc
    resource = files("cx_programmer_mcp").joinpath(meta.resource_name)
    text = resource.read_text(encoding="utf-8")
    return CxtProject(text, source_path=None)


def _timestamp_now() -> str:
    now = datetime.now().astimezone()
    return f"{now.day} {now.month} {now.year} {now.hour} {now.minute} {now.second}"


def create_project(
    *,
    template_id: str = "CJ2M_CPU11",
    template_path: str | Path | None = None,
    project_name: str = "NewProject",
    plc_name: str = "NewPLC1",
    program_name: str = "NewProgram1",
    section_name: str = "Section1",
    blank_program: bool = True,
) -> tuple[CxtProject, dict[str, Any]]:
    """Clone a native CXT/CXP template and normalize only the new-project/program surfaces.

    With template_path, the caller can supply a blank project exported by the exact CX-Programmer
    version/CPU combination they use. This is the highest-fidelity mode because all opaque PLC setup,
    I/O table, UnitSetup and CPU-specific fields are copied verbatim from that native template.
    """
    if template_path is not None:
        base = CxtProject.from_path(template_path)
        source = str(Path(template_path).expanduser().resolve())
        mode = "custom_native_template"
        template_meta: dict[str, Any] = {
            "template_id": None,
            "source_path": source,
            "plc_model": base.project_summary().get("plc_model"),
            "cx_programmer_version": base.project_summary().get("written_by_cx_programmer"),
        }
    else:
        base = _load_builtin(template_id)
        mode = "builtin_template"
        template_meta = asdict(_BUILTINS[template_id])

    programs = base.list_programs()
    if not programs:
        raise CxtError("Template contains no Programs block/program")
    old_program = programs[0]["name"]

    # New-project identity only; device type/network/unit setup remains exactly as the template.
    base.set_project_identity(project_name, plc_name)
    if old_program != program_name:
        base.rename_program(old_program, program_name)

    sections = base.list_sections(program_name)
    normal_sections = [s["name"] for s in sections if s["name"].upper() != "END"]
    if not normal_sections:
        base.create_section(program_name, section_name, before_section="END")
        normal_sections = [section_name]
    elif normal_sections[0] != section_name:
        base.rename_section(program_name, normal_sections[0], section_name)
        normal_sections[0] = section_name

    if blank_program:
        # Keep the first normal section and END. Additional sections are not part of the default new-project surface.
        for extra in list(normal_sections[1:]):
            base.delete_section(program_name, extra)
        base.reset_section_to_blank(program_name, section_name, trailing_empty_rungs=1)
        base.clear_symbols("global")
        try:
            base.clear_symbols("local", program_name)
        except CxtError:
            pass

    base.touch_timestamps(_timestamp_now())
    # The generated object is a new source: its clean baseline is itself and it has no source file yet.
    base.source_path = None
    base.original_text = base.text()

    validation = base.validate()
    if not validation["ok"]:
        raise CxtError(f"Generated project failed structural validation: {validation['errors']}")

    info = {
        "mode": mode,
        "template": template_meta,
        "summary": base.project_summary(),
        "blank_program": blank_program,
        "validation": validation,
        "fidelity_note": (
            "Built-in templates preserve the native CXT structure of the bundled baseline. For exact compatibility "
            "with another CPU or CX-Programmer release, pass template_path pointing to a blank CXT/CXP created by that installation."
        ),
    }
    return base, info
