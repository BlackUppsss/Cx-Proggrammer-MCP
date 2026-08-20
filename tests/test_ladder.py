from cx_programmer_mcp.ladder import analyze_rung, compile_rung, parse_instruction, simulate_boolean_rung


def test_parse_instruction_with_function_code():
    x = parse_instruction("END(001)")
    assert x["mnemonic"] == "END"
    assert x["function_code"] == 1


def test_analyze_simple_rung():
    a = analyze_rung(["LD 0.00", "ANDNOT W0.01", "OUT 100.00", "OUT W0.00"])
    assert a["reads"] == ["0.00", "W0.01"]
    assert a["output_writes"] == ["100.00", "W0.00"]
    assert a["boolean_expression"]["op"] == "and"


def test_compile_structured_branch_and_simulate():
    expr = {
        "op": "or",
        "items": [
            {"op": "and", "items": [{"address": "0.00"}, {"address": "0.01"}]},
            {"address": "0.02", "normally_closed": True},
        ],
    }
    lines = compile_rung(expr, [{"kind": "OUT", "address": "100.00"}])
    assert "AND LD" in lines
    assert "OR LD" in lines
    result = simulate_boolean_rung(lines, {"0.00": True, "0.01": True, "0.02": True})
    assert result["supported"]
    assert result["outputs"]["100.00"] is True


def test_set_reset_simulation_state():
    state = {"W0.00": False}
    set_result = simulate_boolean_rung(["LD 0.00", "SET W0.00"], {"0.00": True}, state)
    assert set_result["state"]["W0.00"] is True
    reset_result = simulate_boolean_rung(["LD 0.03", "RSET W0.00"], {"0.03": True}, set_result["state"])
    assert reset_result["state"]["W0.00"] is False
