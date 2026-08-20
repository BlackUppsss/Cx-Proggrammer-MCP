from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from cx_programmer_mcp.cxt import CxtProject

SAMPLE = Path(__file__).parents[1] / "examples" / "cerdas_cermat.cxt"


def test_load_program():
    p = CxtProject.from_path(SAMPLE)
    summary = p.project_summary()
    assert summary["plc_model"] == "CJ2M CPU11"
    assert p.list_programs()[0]["name"] == "NewProgram1"
    rungs = p.get_rungs("NewProgram1", "Section1", include_empty=False)
    assert rungs[0]["instructions"][0] == "LD 0.00"


def test_replace_insert_delete_and_validate(tmp_path):
    p = CxtProject.from_path(SAMPLE)
    p.replace_rung("NewProgram1", "Section1", 0, ["LD 0.03", "OUT W0.00"], "test")
    p.insert_rung("NewProgram1", "Section1", 1, ["LD W0.00", "OUT 100.00"])
    p.delete_rung("NewProgram1", "Section1", 4)
    result = p.validate()
    assert result["ok"], result
    out = tmp_path / "edited.cxt"
    p.save_cxt(out)
    reloaded = CxtProject.from_path(out)
    assert reloaded.validate()["ok"]
    assert reloaded.get_rungs("NewProgram1", "Section1")[0]["comment"] == "test"


def test_symbol_update():
    p = CxtProject.from_path(SAMPLE)
    p.upsert_symbol("0.03", comment="RESET ROUND")
    symbols = p.list_symbols()
    found = [s for s in symbols if s["address"] == "0.03"][0]
    assert found["comment"] == "RESET ROUND"
