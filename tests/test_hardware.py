import pytest
from hardware import (
    PROFILES,
    detect_hardware_profile,
    validate_address,
    validate_rung_instructions,
    strip_function_code,
)

def test_detect_all_omron_families():
    samples = [
        ('Config:="[DEV]DEV:CP1E;CLOCK:TRUE;CPU:NA;"', "CP1E", "NA"),
        ('Config:="[DEV]DEV:CP1E;CLOCK:FALSE;CPU:E20;"', "CP1E", "E20"),
        ('Config:="[DEV]DEV:CP1L;CLOCK:TRUE;CPU:M;"', "CP1L", "M"),
        ('Config:="[DEV]DEV:CP1L-E;CPU:EM;"', "CP1L", "EM"),
        ('Config:="[DEV]DEV:CP1H;CLOCK:TRUE;CPU:X;"', "CP1H", "X"),
        ('Config:="[DEV]DEV:CP1H-E;CPU:EX;"', "CP1H", "EX"),
        ('Config:="[DEV]DEV:CP2E-N;CPU:N;"', "CP2E", "N"),
        ('Config:="[DEV]DEV:CP2E-ENT;CPU:N;"', "CP2E", "N"),
        ('Config:="[DEV]DEV:CJ1M;CPU:CPU13;"', "CJ1M", "CPU13"),
        ('Config:="[DEV]DEV:CJ1G-H;CPU:CPU45;"', "CJ1G", "CPU45"),
        ('Config:="[DEV]DEV:CJ1H-H;CPU:CPU67;"', "CJ1H", "CPU67"),
        ('Config:="[DEV]DEV:CJ2M;CPU:CPU31;EM:E,0,32768;"', "CJ2M", "CPU31"),
        ('Config:="[DEV]DEV:CJ2H;CPU:CPU64-EIP;"', "CJ2H", "CPU64-EIP"),
        ('Config:="[DEV]DEV:CS1G-H;CPU:CPU44;"', "CS1G", "CPU44"),
        ('Config:="[DEV]DEV:CS1H;CPU:CPU67;"', "CS1H", "CPU67"),
        ('Config:="[DEV]DEV:CS1D-H;CPU:CPU67;"', "CS1D", "CPU67"),
        ('Config:="[DEV]DEV:CPM1A;CPU:CPU;"', "CPM1A", "CPU"),
        ('Config:="[DEV]DEV:CPM2A;CPU:CPU;"', "CPM2A", "CPU"),
        ('Config:="[DEV]DEV:CQM1H;CPU:CPU51;"', "CQM1H", "CPU51"),
        ('Config:="[DEV]DEV:C200HS;CPU:CPU01;"', "C200H", "CPU01"),
        ('Config:="[DEV]DEV:NSJ;CPU:G5D;"', "NSJ", "G5D"),
        ('Config:="[DEV]DEV:CVM1-V2;CPU:CPU21;"', "CVM1", "CPU21"),
        ('Config:="[DEV]DEV:FQM1-MMP;CPU:MMP;"', "FQM1", "MMP"),
    ]
    for cfg, expected_name, expected_cpu in samples:
        prof = detect_hardware_profile(cfg)
        assert prof.name == expected_name, f"Expected {expected_name} for {cfg}, got {prof.name}"
        assert prof.cpu == expected_cpu, f"Expected CPU {expected_cpu} for {cfg}, got {prof.cpu}"

def test_validate_address_limits():
    # D address limit on CP1E vs CP1L/CP1H/CJ1M/CS1H
    assert validate_address("D7000", "CP1E") is True
    assert validate_address("D8000", "CP1E") is False
    assert validate_address("D8000", "CP1L") is True
    assert validate_address("D32000", "CP1L") is True
    assert validate_address("D32000", "CP1H") is True
    assert validate_address("D35000", "CP1H") is False

    # CIO and W Area on CP1L vs CP1E
    assert validate_address("1500.00", "CP1L") is True
    assert validate_address("1500.00", "CP1E") is False
    assert validate_address("W300.05", "CP1L") is True
    assert validate_address("W300.05", "CP1E") is False

    # Holding Area on CP1E vs CP2E vs CP1L vs CJ2M
    assert validate_address("H45.00", "CP1E") is True
    assert validate_address("H100.00", "CP1E") is False
    assert validate_address("H100.00", "CP1L") is True
    assert validate_address("H1200.00", "CP2E") is True
    assert validate_address("H1200.00", "CJ2M") is True

    # Timers and Counters on CP1L/CJ1M/CS1H vs CP1E vs CPM1A
    assert validate_address("T3500", "CP1L") is True
    assert validate_address("T3500", "CP1E") is False
    assert validate_address("C3500", "CP1L") is True
    assert validate_address("C3500", "CP1E") is False
    assert validate_address("T100", "CPM1A") is True
    assert validate_address("T200", "CPM1A") is False

    # Extended Memory on CJ1M, CJ2M, CS1H vs CP1E/CP1L
    assert validate_address("E0_100", "CJ1M") is True
    assert validate_address("E1_100", "CJ1M") is False  # CJ1M has 1 bank (E0)
    assert validate_address("E3_100", "CJ2M") is True
    assert validate_address("E0_100", "CS1H") is True
    assert validate_address("E0_100", "CP1E") is False
    assert validate_address("E0_100", "CP1L") is False

    # Legacy C-series prefixes
    assert validate_address("DM100", "CPM1A") is True
    assert validate_address("HR10.05", "CPM1A") is True
    assert validate_address("LR5.00", "CQM1H") is True

def test_strip_function_code():
    assert strip_function_code("TIMX(550)") == "TIMX"
    assert strip_function_code("@MOV(021)") == "MOV"
    assert strip_function_code("DIFU(013)") == "DIFU"
    assert strip_function_code("LD") == "LD"

def test_validate_rung_instructions():
    # TIMX forbidden on CP1E & CPM1A
    errs_cp1e = validate_rung_instructions(["LD 0.00", "TIMX(550) 000 &10"], "CP1E")
    assert any("does not support binary timer" in e for e in errs_cp1e)
    errs_cpm1a = validate_rung_instructions(["LD 0.00", "TIMX(550) 000 &10"], "CPM1A")
    assert any("does not support binary timer" in e for e in errs_cpm1a)

    # TIMX allowed on CP1L, CP1H, CP2E, CJ1M, CJ2M, CS1H
    for model in ["CP1L", "CP1H", "CP2E", "CJ1M", "CJ2M", "CS1H"]:
        errs = validate_rung_instructions(["LD 0.00", "TIMX(550) 000 &10"], model)
        assert len(errs) == 0, f"TIMX should be allowed on {model}"

    # Spaced contacts rejected
    errs_space = validate_rung_instructions(["LD NOT 0.00", "OUT 100.00"], "CP1E")
    assert any("must not contain spaces" in e for e in errs_space)
