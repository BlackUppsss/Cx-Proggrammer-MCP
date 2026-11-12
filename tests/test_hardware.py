import pytest
from hardware import (
    PROFILES,
    detect_hardware_profile,
    validate_address,
    validate_rung_instructions,
    strip_function_code,
)

def test_detect_hardware_profile():
    cp1e_text = 'Config:="[DEV]DEV:CP1E;CLOCK:TRUE;CPU:NA;"'
    assert detect_hardware_profile(cp1e_text).name == "CP1E"

    cp1h_text = 'Config:="[DEV]DEV:CP1H;CLOCK:TRUE;CPU:X;"'
    assert detect_hardware_profile(cp1h_text).name == "CP1H"

    cp2e_text = 'Config:="[DEV]DEV:CP2E;CPU:N;"'
    assert detect_hardware_profile(cp2e_text).name == "CP2E"

    cj2m_text = 'Config:="[DEV]DEV:CJ2M;CPU:CPU31;EM:E,0,32768;"'
    assert detect_hardware_profile(cj2m_text).name == "CJ2M"

def test_validate_address_limits():
    # D address limit on CP1E vs CP1H
    assert validate_address("D7000", "CP1E") is True
    assert validate_address("D8000", "CP1E") is False
    assert validate_address("D8000", "CP1H") is True
    assert validate_address("D32000", "CP1H") is True
    assert validate_address("D35000", "CP1H") is False

    # Holding Area on CP1E vs CP2E
    assert validate_address("H45.00", "CP1E") is True
    assert validate_address("H100.00", "CP1E") is False
    assert validate_address("H100.00", "CP2E") is True

    # Extended Memory on CJ2M
    assert validate_address("E0_100", "CJ2M") is True
    assert validate_address("E0_100", "CP1E") is False

def test_strip_function_code():
    assert strip_function_code("TIMX(550)") == "TIMX"
    assert strip_function_code("DIFU(013)") == "DIFU"
    assert strip_function_code("MOV(021)") == "MOV"
    assert strip_function_code("LD") == "LD"

def test_validate_rung_instructions():
    # TIMX forbidden on CP1E
    errs_cp1e = validate_rung_instructions(["LD 0.00", "TIMX(550) 000 &10"], "CP1E")
    assert any("does not support binary timer" in e for e in errs_cp1e)

    # TIMX allowed on CP1H
    errs_cp1h = validate_rung_instructions(["LD 0.00", "TIMX(550) 000 &10"], "CP1H")
    assert len(errs_cp1h) == 0

    # Spaced contacts rejected
    errs_space = validate_rung_instructions(["LD NOT 0.00", "OUT 100.00"], "CP1E")
    assert any("must not contain spaces" in e for e in errs_space)
