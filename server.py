"""MCP stdio server for inspecting and safely editing Omron CXT/CXP projects."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

try:
    from mcp import types
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server
except ImportError as exc:  # pragma: no cover - gives a useful direct-run error
    raise ImportError("Install the MCP Python package with: pip install mcp") from exc

try:
    from .api import SafePlcProject
    from .engine import CxtBlockError
except ImportError:  # Supports `python server.py` from this directory.
    from api import SafePlcProject
    from engine import CxtBlockError


def create_server(project_path: str | Path, allow_write: bool = False, auto_reload_cxp: bool = False, cxp_path: str | Path | None = None) -> Server:
    project = SafePlcProject(project_path, auto_reload_cxp=auto_reload_cxp, cxp_exe_path=cxp_path)
    def schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
        return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}

    tools = [
        types.Tool(name="project_summary", description="Summary of program, sections, and symbols.", inputSchema=schema({})),
        types.Tool(name="list_sections", description="List sections and rung counts.", inputSchema=schema({})),
        types.Tool(name="list_rungs", description="Read batch of rungs in a section with pagination metadata.", inputSchema=schema({"section": {"type": "string"}, "start": {"type": "integer", "minimum": 0}, "count": {"type": "integer", "minimum": 0}, "mode": {"type": "string", "enum": ["summary", "full"]}}, ["section"])),
        types.Tool(name="get_rung", description="Read a single rung by 0-based index.", inputSchema=schema({"section": {"type": "string"}, "index": {"type": "integer", "minimum": 0}, "mode": {"type": "string", "enum": ["summary", "full"]}}, ["section", "index"])),
        types.Tool(name="list_symbols", description="List global or local symbols.", inputSchema=schema({"scope": {"type": "string", "enum": ["global", "local"]}}, [])),
        types.Tool(name="search_project", description="Search mnemonic, address, symbol, or comment, optionally by section and result type.", inputSchema=schema({"query": {"type": "string", "minLength": 1}, "section": {"type": "string"}, "result_type": {"type": "string", "enum": ["all", "rung", "symbol"]}}, ["query"])),
        types.Tool(name="analyze_project", description="Detect potential comment/logic mismatches, references, conflicting output writers, and unreset SETs.", inputSchema=schema({"section": {"type": "string"}})),
        types.Tool(name="validate_project", description="Validate project structure and available PLC constraints.", inputSchema=schema({})),
        types.Tool(name="get_hardware_profile", description="Get detected Omron PLC model, CPU type, memory boundaries, and capabilities.", inputSchema=schema({})),
        types.Tool(name="simulate_scan", description="Simulate execution of ladder logic for N scan cycles with given inputs.", inputSchema=schema({"section": {"type": "string"}, "inputs": {"type": "object"}, "scans": {"type": "integer", "minimum": 1}}, ["section"])),
        types.Tool(name="replace_rung", description="Replace a rung (requires --allow-write). Unsaved until commit_project.", inputSchema=schema({"section": {"type": "string"}, "index": {"type": "integer", "minimum": 0}, "instructions": {"type": "array", "items": {"type": "string"}}, "comment": {"type": "string"}}, ["section", "index", "instructions"])),
        types.Tool(name="insert_rung", description="Insert a rung (requires --allow-write). Unsaved until commit_project.", inputSchema=schema({"section": {"type": "string"}, "index": {"type": "integer", "minimum": 0}, "instructions": {"type": "array", "items": {"type": "string"}}, "comment": {"type": "string"}}, ["section", "index", "instructions"])),
        types.Tool(name="delete_rung", description="Delete a rung (requires --allow-write). Unsaved until commit_project.", inputSchema=schema({"section": {"type": "string"}, "index": {"type": "integer", "minimum": 0}}, ["section", "index"])),
        types.Tool(name="set_symbol", description="Add or update a symbol (requires --allow-write). Unsaved until commit_project.", inputSchema=schema({"address": {"type": "string"}, "name": {"type": "string"}, "data_type": {"type": "string"}, "comment": {"type": "string"}}, ["address", "name"])),
        types.Tool(name="delete_symbol", description="Delete a symbol by address or name (requires --allow-write). Unsaved until commit_project.", inputSchema=schema({"address_or_name": {"type": "string"}}, ["address_or_name"])),
        types.Tool(name="commit_project", description="Validate and save CXT/CXP pair with backup & optional CX-Programmer GUI reload (requires --allow-write).", inputSchema=schema({"backup": {"type": "boolean"}, "reload_cxp": {"type": "boolean"}})),
        types.Tool(name="open_in_cxp", description="Open active .cxp/.cxt project file in CX-Programmer Windows GUI.", inputSchema=schema({})),
        types.Tool(name="add_section", description="Add a new ladder section before a specific section (requires --allow-write).", inputSchema=schema({"section_name": {"type": "string"}, "before_section": {"type": "string"}}, ["section_name"])),
        types.Tool(name="rename_section", description="Rename a ladder section (requires --allow-write).", inputSchema=schema({"old_name": {"type": "string"}, "new_name": {"type": "string"}}, ["old_name", "new_name"])),
        types.Tool(name="create_project", description="Create new .cxt and .cxp project files from CP1E template (requires --allow-write).", inputSchema=schema({"target_path": {"type": "string"}, "template": {"type": "string"}}, ["target_path"])),
        types.Tool(name="take_screenshot", description="Capture a screenshot of CX-Programmer window for visual verification and ACC before committing.", inputSchema=schema({"output_path": {"type": "string"}, "auto_launch": {"type": "boolean"}})),
        types.Tool(name="live_type_rung", description="Visually type ladder instructions directly into the active CX-Programmer window using shortcuts (C, /, O, I) with visible pacing.", inputSchema=schema({"instructions": {"type": "array", "items": {"type": "string"}}, "insert_new_rung": {"type": "boolean"}, "comment": {"type": "string"}, "typing_speed": {"type": "number"}}, ["instructions"])),
    ]

    async def list_tools(_ctx: Any = None, _params: Any = None) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def call_tool(_ctx: Any, params: Any) -> types.CallToolResult:
        name = params.name
        arguments = params.arguments or {}
        try:
            if name == "project_summary": result = project.summary()
            elif name == "list_sections": result = project.list_sections()
            elif name == "list_rungs": result = project.list_rungs(arguments["section"], arguments.get("start", 0), arguments.get("count"), arguments.get("mode", "summary"))
            elif name == "get_rung": result = project.get_rung(arguments["section"], arguments["index"], arguments.get("mode", "full"))
            elif name == "list_symbols": result = project.engine.list_symbols(arguments.get("scope", "global"), project.program_name)
            elif name == "search_project": result = project.search(arguments["query"], arguments.get("section"), arguments.get("result_type", "all"))
            elif name == "analyze_project": result = project.analyze(arguments.get("section"))
            elif name == "validate_project": result = project.validate()
            elif name == "get_hardware_profile": result = project.get_hardware_profile()
            elif name == "simulate_scan": result = project.simulate_scan(arguments["section"], arguments.get("inputs"), arguments.get("scans", 1))
            elif name == "take_screenshot": result = project.capture_screenshot(output_path=arguments.get("output_path"), auto_launch=arguments.get("auto_launch", True))
            elif name == "live_type_rung":
                from live_typer import live_type_ladder
                result = live_type_ladder(
                    instructions=arguments["instructions"],
                    insert_new_rung=arguments.get("insert_new_rung", True),
                    comment=arguments.get("comment", ""),
                    typing_speed=float(arguments.get("typing_speed", 0.10)),
                )
            elif name in {"replace_rung", "insert_rung", "delete_rung", "set_symbol", "delete_symbol", "commit_project", "create_project", "open_in_cxp", "add_section", "rename_section"}:
                if not allow_write:
                    raise PermissionError("Penulisan dinonaktifkan. Jalankan server dengan --allow-write setelah memastikan backup.")
                if name == "replace_rung":
                    project.replace_rung(arguments["section"], arguments["index"], arguments["instructions"], arguments.get("comment", "")); result = {"ok": True, "saved": False}
                elif name == "insert_rung":
                    project.insert_rung(arguments["section"], arguments["index"], arguments["instructions"], arguments.get("comment", "")); result = {"ok": True, "saved": False}
                elif name == "delete_rung":
                    project.delete_rung(arguments["section"], arguments["index"]); result = {"ok": True, "saved": False}
                elif name == "add_section":
                    project.add_section(arguments["section_name"], before_section=arguments.get("before_section", "END")); result = {"ok": True, "saved": False}
                elif name == "rename_section":
                    project.rename_section(arguments["old_name"], arguments["new_name"]); result = {"ok": True, "saved": False}
                elif name == "set_symbol":
                    result = project.set_symbol(arguments["address"], arguments["name"], arguments.get("data_type", "BOOL"), arguments.get("comment", "")); result["saved"] = False
                elif name == "delete_symbol":
                    ok = project.delete_symbol(arguments["address_or_name"])
                    result = {"ok": ok, "saved": False}
                elif name == "commit_project":
                    result = project.commit(arguments.get("backup", True))
                elif name == "open_in_cxp":
                    from api import open_cx_programmer
                    reopened = open_cx_programmer(project.cxp_path, custom_exe=project.cxp_exe_path)
                    result = {"ok": True, "opened": reopened, "file": str(project.cxp_path)}
                else:
                    new_proj = SafePlcProject.create_new_project(arguments["target_path"], arguments.get("template", "CP1E-NA.cxt"))
                    result = {"ok": True, "created": str(new_proj.cxt_path), "cxp": str(new_proj.cxp_path), "sections": new_proj.list_sections()}
            else:
                raise ValueError(f"Unknown tool: {name}")
            return types.CallToolResult(content=[types.TextContent(text=json.dumps(result, ensure_ascii=False, default=str))])
        except Exception as exc:
            return types.CallToolResult(content=[types.TextContent(text=json.dumps({"error": str(exc)}, ensure_ascii=False))], isError=True)

    return Server("omron-cx-programmer", version="1.0.0", on_list_tools=list_tools, on_call_tool=call_tool)


async def _run(project_path: Path, allow_write: bool, auto_reload_cxp: bool = False, cxp_path: Path | None = None) -> None:
    server = create_server(project_path, allow_write, auto_reload_cxp=auto_reload_cxp, cxp_path=cxp_path)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP server for Omron CX-Programmer CXT/CXP files")
    parser.add_argument("--project", type=Path, default=Path("project/Traffic_Light.cxt"))
    parser.add_argument("--allow-write", action="store_true", help="Enable edit and commit tools")
    parser.add_argument("--auto-reload-cxp", dest="auto_reload_cxp", action="store_true", default=None, help="Enable automatic closing and re-opening of CX-Programmer on commit")
    parser.add_argument("--no-auto-reload-cxp", dest="auto_reload_cxp", action="store_false", help="Disable automatic closing and re-opening of CX-Programmer on commit")
    parser.add_argument("--cxp-path", type=Path, default=None, help="Custom path to CX-P.exe executable")
    args = parser.parse_args()
    
    auto_reload = args.auto_reload_cxp
    if auto_reload is None:
        env_val = os.environ.get("OMRON_AUTO_RELOAD_CXP", "").strip().lower()
        auto_reload = env_val in {"1", "true", "yes", "on"}

    try:
        asyncio.run(_run(args.project, args.allow_write, auto_reload_cxp=auto_reload, cxp_path=args.cxp_path))
    except (OSError, CxtBlockError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()