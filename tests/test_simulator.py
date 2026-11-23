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
    assert sim.get_bit("T1") is False

    # Scan 2: hits zero -> timer flag ON (both T001 and T1 normalized)
    sim.run_scan([{"instructions": rung}])
    assert sim.get_bit("T001") is True
    assert sim.get_bit("T1") is True

def test_counter_two_input_and_reset():
    sim = LadderSimulator()
    rungs = [
        {"instructions": ["LD 0.02", "LD 0.03", "CNT 001 #2"]},
        {"instructions": ["LD C001", "OUT 100.02"]},
    ]

    # Pulse 1 (rising edge on 0.02, reset 0.03=False) -> PV=1
    sim.run_scan(rungs, inputs={"0.02": True, "0.03": False})
    assert sim.get_bit("C001") is False
    assert sim.get_bit("100.02") is False

    # Release 0.02
    sim.run_scan(rungs, inputs={"0.02": False, "0.03": False})

    # Pulse 2 (rising edge on 0.02) -> PV=0 -> C001 done & 100.02 ON
    sim.run_scan(rungs, inputs={"0.02": True, "0.03": False})
    assert sim.get_bit("C001") is True
    assert sim.get_bit("C1") is True
    assert sim.get_bit("100.02") is True

    # Trigger Reset (0.03=True) -> PV resets to 2, C001 & 100.02 turn OFF
    sim.run_scan(rungs, inputs={"0.02": False, "0.03": True})
    assert sim.get_bit("C001") is False
    assert sim.get_bit("100.02") is False
