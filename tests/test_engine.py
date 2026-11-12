import pytest
import tempfile
import shutil
from pathlib import Path
from engine import CxtEngine
from api import SafePlcProject

def test_rung_crud_and_renumber():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path("project/Traffic_Light.cxt")
        dst = Path(tmpdir) / "test.cxt"
        shutil.copy(src, dst)

        p = SafePlcProject(dst)
        init_count = p.list_rungs("TrafficLight")["total"]

        # Insert
        p.insert_rung("TrafficLight", 1, ["LD 0.05", "OUT 100.05"], "Inserted")
        assert p.list_rungs("TrafficLight")["total"] == init_count + 1
        assert p.get_rung("TrafficLight", 1)["comment"] == "Inserted"

        # Replace
        p.replace_rung("TrafficLight", 1, ["LD 0.06", "OUT 100.06"], "Replaced")
        assert p.get_rung("TrafficLight", 1)["comment"] == "Replaced"

        # Delete
        p.delete_rung("TrafficLight", 1)
        assert p.list_rungs("TrafficLight")["total"] == init_count

def test_symbol_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path("project/Traffic_Light.cxt")
        dst = Path(tmpdir) / "test.cxt"
        shutil.copy(src, dst)

        p = SafePlcProject(dst)
        p.set_symbol("W50.00", "MY_TEST_FLAG", "BOOL", "Unit test flag")
        syms = [s["name"] for s in p.engine.list_symbols("global")]
        assert "MY_TEST_FLAG" in syms

        ok = p.delete_symbol("MY_TEST_FLAG")
        assert ok is True
        syms_after = [s["name"] for s in p.engine.list_symbols("global")]
        assert "MY_TEST_FLAG" not in syms_after

def test_section_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path("project/Traffic_Light.cxt")
        dst = Path(tmpdir) / "test.cxt"
        shutil.copy(src, dst)

        p = SafePlcProject(dst)
        p.add_section("AlarmHandling", before_section="END")
        secs = [s["name"] for s in p.list_sections()]
        assert "AlarmHandling" in secs

        p.rename_section("AlarmHandling", "FaultManagement")
        secs_after = [s["name"] for s in p.list_sections()]
        assert "FaultManagement" in secs_after
        assert "AlarmHandling" not in secs_after

def test_atomic_commit():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path("project/Traffic_Light.cxt")
        dst = Path(tmpdir) / "test.cxt"
        shutil.copy(src, dst)

        p = SafePlcProject(dst)
        res = p.commit(backup=True, reload_cxp=False)
        assert res["ok"] is True
        assert Path(res["cxp"]).exists()

        # Reopen committed cxp
        p2 = SafePlcProject(res["cxp"])
        assert p2.validate()["ok"] is True
