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

def test_multi_model_create_and_high_range_symbols():
    with tempfile.TemporaryDirectory() as tmpdir:
        models = [
            ("CP1E-NA.cxt", "CP1E", "W50.00", ["LD 0.00", "TIM 000 #10"]),
            ("CP1L-M.cxt", "CP1L", "D15000", ["LD 0.00", "TIMX(550) 000 &50"]),
            ("CP1H-X.cxt", "CP1H", "W250.05", ["LD 0.00", "TIMX(550) 000 &50"]),
            ("CP2E-N.cxt", "CP2E", "H500.00", ["LD 0.00", "TIMX(550) 000 &50"]),
            ("CJ1M-CPU13.cxt", "CJ1M", "E0_100", ["LD 0.00", "TIMX(550) 000 &50"]),
            ("CJ2M-CPU31.cxt", "CJ2M", "E2_100", ["LD 0.00", "TIMX(550) 000 &50"]),
            ("CS1H-CPU67.cxt", "CS1H", "E5_500", ["LD 0.00", "TIMX(550) 000 &50"]),
        ]
        for tmpl, expected_hw, test_addr, test_rung in models:
            target = Path(tmpdir) / f"proj_{expected_hw}.cxt"
            p = SafePlcProject.create_new_project(target, template_name=tmpl)
            assert p.get_hardware_profile()["name"] == expected_hw
            dtype = "CHANNEL" if test_addr.startswith(("D", "E")) else "BOOL"
            p.set_symbol(test_addr, f"SYM_{expected_hw}", dtype, f"Test on {expected_hw}")
            p.replace_rung("Section1", 0, test_rung, f"Rung on {expected_hw}")
            val = p.validate()
            assert val["ok"] is True, f"Validation failed on {expected_hw}: {val}"
            assert val["warnings"] == [], f"Unexpected warnings on {expected_hw}: {val['warnings']}"
            res = p.commit(backup=False)
            assert res["ok"] is True

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
