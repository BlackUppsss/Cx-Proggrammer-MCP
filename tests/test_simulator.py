import pytest
from simulator import LadderSimulator

def test_start_stop_latch():
    sim = LadderSimulator()
    rung = [
        "LD PB_START",
        "OR SYS_RUN",
        "ANDNOT PB_STOP",
        "OUT SYS_RUN",
    ]

    # Scan 1: Press start
    r1 = sim.run_scan([{"instructions": rung}], inputs={"PB_START": True, "PB_STOP": False})
    assert sim.get_bit("SYS_RUN") is True

    # Scan 2: Release start, latch holds
    r2 = sim.run_scan([{"instructions": rung}], inputs={"PB_START": False, "PB_STOP": False})
    assert sim.get_bit("SYS_RUN") is True

    # Scan 3: Press stop, latch resets
    r3 = sim.run_scan([{"instructions": rung}], inputs={"PB_START": False, "PB_STOP": True})
    assert sim.get_bit("SYS_RUN") is False

def test_difu_edge_pulse():
    sim = LadderSimulator()
    rung = [
        "LD IN_BUTTON",
        "DIFU OUT_PULSE",
    ]

    # Scan 1: button pressed -> pulse ON
    sim.run_scan([{"instructions": rung}], inputs={"IN_BUTTON": True})
    assert sim.get_bit("OUT_PULSE") is True

    # Scan 2: button still pressed -> pulse turns OFF
    sim.run_scan([{"instructions": rung}], inputs={"IN_BUTTON": True})
    assert sim.get_bit("OUT_PULSE") is False

def test_timer_countdown():
    sim = LadderSimulator()
    rung = [
        "LD P_ON",
        "TIM 001 #2",
    ]

    # Scan 1
    sim.run_scan([{"instructions": rung}])
    assert sim.get_bit("T001") is False

    # Scan 2: hits zero -> timer flag ON
    sim.run_scan([{"instructions": rung}])
    assert sim.get_bit("T001") is True
