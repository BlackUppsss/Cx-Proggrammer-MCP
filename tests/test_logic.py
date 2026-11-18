import pytest
from logic import validate_rung_stack

def test_balanced_simple_rung():
    insts = ["LD 0.00", "OUT 100.00"]
    assert validate_rung_stack(insts) == []

def test_balanced_parallel_rung():
    insts = ["LD 0.00", "LD 0.01", "ORLD", "OUT 100.00"]
    assert validate_rung_stack(insts) == []

def test_balanced_two_input_counter_and_keep():
    cnt_insts = ["LD 0.02", "LD 0.03", "CNT 001 #10"]
    assert validate_rung_stack(cnt_insts) == []

    keep_insts = ["LD 0.00", "LD 0.01", "KEEP(011) W0.00"]
    assert validate_rung_stack(keep_insts) == []

def test_counter_missing_reset_input():
    insts = ["LD 0.02", "CNT 001 #10"]
    errs = validate_rung_stack(insts)
    assert any("2-input instruction" in e for e in errs)

def test_stack_underflow():
    insts = ["LD 0.00", "ORLD", "OUT 100.00"]
    errs = validate_rung_stack(insts)
    assert any("Stack underflow" in e for e in errs)

def test_uncombined_branches():
    insts = ["LD 0.00", "LD 0.01", "OUT 100.00"]
    errs = validate_rung_stack(insts)
    assert any("uncombined branches" in e for e in errs)

def test_coil_without_condition():
    insts = ["OUT 100.00"]
    errs = validate_rung_stack(insts)
    assert any("without preceding LD" in e for e in errs)
