from pathlib import Path

from cx_programmer_mcp.cxt import CxtProject
from cx_programmer_mcp.templates import create_project, list_templates

ROOT = Path(__file__).parents[1]
SAMPLE_CXT = ROOT / "examples" / "cerdas_cermat.cxt"


def test_builtin_template_list_and_create_blank_project(tmp_path):
    templates = list_templates()
    assert any(t["template_id"] == "CJ2M_CPU11" for t in templates)

    p, info = create_project(
        template_id="CJ2M_CPU11",
        project_name="ConveyorProject",
        plc_name="PLC_CONVEYOR",
        program_name="Main",
        section_name="MainLogic",
    )
    summary = p.project_summary()
    assert summary["project_name"] == "ConveyorProject"
    assert summary["plc_name"] == "PLC_CONVEYOR"
    assert summary["plc_model"] == "CJ2M CPU11"
    assert p.list_programs()[0]["name"] == "Main"
    assert [s["name"] for s in p.list_sections("Main")] == ["MainLogic", "END"]
    assert p.get_rungs("Main", "MainLogic") == [{"index": 0, "comment": "", "instructions": [], "empty": True}]
    assert p.get_rungs("Main", "END", include_empty=False)[0]["instructions"] == ["END(001)"]
    assert p.list_symbols("global") == []
    assert p.validate()["ok"]
    assert info["mode"] == "builtin_template"

    out = tmp_path / "new_project.cxt"
    p.save_cxt(out, backup=False)
    q = CxtProject.from_path(out)
    assert q.project_summary()["plc_model"] == "CJ2M CPU11"
    assert q.validate()["ok"]


def test_custom_native_template_clones_cpu_setup_and_blanks_program():
    original = CxtProject.from_path(SAMPLE_CXT)
    p, info = create_project(
        template_path=SAMPLE_CXT,
        project_name="CloneProject",
        plc_name="NewPLC1",
        program_name="NewProgram1",
        section_name="Section1",
    )
    assert info["mode"] == "custom_native_template"
    assert p.project_summary()["plc_model"] == original.project_summary()["plc_model"]
    assert p.get_rungs("NewProgram1", "Section1")[0]["empty"]
    assert len(p.get_rungs("NewProgram1", "Section1")) == 1
    assert p.list_symbols("global") == []
    assert p.validate()["ok"]
