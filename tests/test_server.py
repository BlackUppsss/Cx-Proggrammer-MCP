import pytest
import asyncio
from server import create_server

@pytest.mark.asyncio
async def test_server_tools_list():
    server = create_server("project/Traffic_Light.cxt", allow_write=True)
    res = await server._request_handlers["tools/list"].handler(None)
    tool_names = [t.name for t in res.tools]
    assert "project_summary" in tool_names
    assert "simulate_scan" in tool_names
    assert "get_hardware_profile" in tool_names
    assert "delete_symbol" in tool_names
    assert "commit_project" in tool_names

@pytest.mark.asyncio
async def test_server_hardware_and_simulation():
    server = create_server("project/Traffic_Light.cxt", allow_write=True)

    # Test get_hardware_profile
    req_hw = type("Req", (), {"params": type("Params", (), {"name": "get_hardware_profile", "arguments": {}})()})()
    res_hw = await server._request_handlers["tools/call"].handler(None, req_hw.params)
    assert "CP1E" in res_hw.content[0].text

    # Test simulate_scan
    req_sim = type("Req", (), {"params": type("Params", (), {"name": "simulate_scan", "arguments": {"section": "TrafficLight", "inputs": {"PB_START": True}, "scans": 2}})()})()
    res_sim = await server._request_handlers["tools/call"].handler(None, req_sim.params)
    assert "scan" in res_sim.content[0].text
