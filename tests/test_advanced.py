from pathlib import Path

import pytest

from cx_programmer_mcp.cxt import CxtProject
from cx_programmer_mcp.diagnostics import cross_reference, program_diagnostics
from cx_programmer_mcp.integrity import scope_integrity
from cx_programmer_mcp.recipes import apply_exclusive_latch, exclusive_latch_plan
from cx_programmer_mcp.session import ProjectSession

SAMPLE = Path(__file__).parents[1] / "examples" / "cerdas_cermat.cxt"


def test_scope_integrity_allows_program_edit_but_not_plc_edit():
    p = CxtProject.from_path(SAMPLE)
    original = p.text()
    p.replace_rung("NewProgram1", "Section1", 0, ["LD 0.00", "OUT 100.00"])
    assert scope_integrity(original, p.text())["ok"]

    tampered = p.text().replace('Name:="tombol_cerdas_cermat";', 'Name:="tampered";', 1)
    assert not scope_integrity(original, tampered)["ok"]


def test_session_revision_undo_redo():
    s = ProjectSession(CxtProject.from_path(SAMPLE))
    s.edit(lambda p: p.set_rung_comment("NewProgram1", "Section1", 0, "edited"), expected_revision=0)
    assert s.revision == 1
    assert s.project.get_rungs("NewProgram1", "Section1")[0]["comment"] == "edited"
    with pytest.raises(ValueError):
        s.edit(lambda p: p.set_rung_comment("NewProgram1", "Section1", 0, "stale"), expected_revision=0)
    assert s.undo(expected_revision=1)["undone"]
    assert s.project.get_rungs("NewProgram1", "Section1")[0]["comment"] == ""
    assert s.redo(expected_revision=2)["redone"]
    assert s.project.get_rungs("NewProgram1", "Section1")[0]["comment"] == "edited"


def test_cross_reference_and_unused_reset_diagnostic():
    p = CxtProject.from_path(SAMPLE)
    refs = cross_reference(p, "W0.00")
    assert any("coil" in x["roles"] for x in refs)
    d = program_diagnostics(p)
    unused = [x for x in d["info"] if x.get("code") == "unused_symbol"]
    assert any(x["address"] == "0.03" for x in unused)


def test_exclusive_latch_recipe_applies_and_balances_set_reset():
    p = CxtProject.from_path(SAMPLE)
    participants = [
        {"name": "A", "input": "0.00", "latch": "W0.00", "output": "100.00"},
        {"name": "B", "input": "0.01", "latch": "W0.01", "output": "100.01"},
        {"name": "C", "input": "0.02", "latch": "W0.02", "output": "100.02"},
    ]
    assert len(exclusive_latch_plan(participants, "0.03")) == 7
    apply_exclusive_latch(p, "NewProgram1", "Section1", participants, "0.03")
    rungs = p.get_rungs("NewProgram1", "Section1", include_empty=False)
    assert any("SET W0.00" in r["instructions"] for r in rungs)
    assert any("RSET W0.00" in r["instructions"] for r in rungs)
    assert not any(x.get("code") == "set_without_reset" for x in program_diagnostics(p)["warnings"])
    assert p.validate()["ok"]


def test_symbol_csv_roundtrip_with_comma(tmp_path):
    p = CxtProject.from_path(SAMPLE)
    p.upsert_symbol("0.03", name="ResetRound", comment="Reset, next round")
    out = tmp_path / "quoted.cxt"
    p.save_cxt(out)
    q = CxtProject.from_path(out)
    sym = [x for x in q.list_symbols() if x["address"] == "0.03"][0]
    assert sym["name"] == "ResetRound"
    assert sym["comment"] == "Reset, next round"


def test_delete_symbol():
    p = CxtProject.from_path(SAMPLE)
    assert p.delete_symbol("0.03")
    assert not any(x["address"] == "0.03" for x in p.list_symbols())


def test_cxp_decompression_sample():
    cxp = Path(__file__).parents[1] / "examples" / "cerdas_cermat.cxp"
    p = CxtProject.from_path(cxp)
    assert p.project_summary()["plc_model"] == "CJ2M CPU11"
    assert p.get_rungs("NewProgram1", "Section1", include_empty=False)[0]["instructions"][0] == "LD 0.00"
