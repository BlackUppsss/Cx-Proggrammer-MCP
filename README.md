# Omron Multi-Model MCP Server & Automation Toolkit

A Model Context Protocol (MCP) server and Python automation library designed for AI agents (Claude Desktop, Cursor, Cline, Roo Code, etc.) and engineers to inspect, analyze, simulate, validate, and safely edit Omron CX-Programmer project files (`.cxt` and `.cxp`).

> [!NOTE]
> Forked, enhanced, and maintained by **Rico Allif Lazzami** ([@ricolazzami](https://github.com/ricolazzami)).  
> Based on the open-source foundation from [BlackUppsss/Cx-Proggrammer-MCP](https://github.com/BlackUppsss/Cx-Proggrammer-MCP).

---

## 1. Supported PLC Models & Hardware Profiles

The engine automatically detects the target PLC architecture from the project's internal `Config:=` header and dynamically enforces hardware memory maps, valid timer types, and opcode boundaries:

| Family | Models | Data Memory (D) | Work Area (W) | Holding (H) | Timers / Counters | Binary Timers (TIMX/CNTX) | Extended Memory (EM) |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **CP1E** | `E20`, `N30`, `NA20` | D0 - D7999 | W0.00 - W99.15 | H0.00 - H49.15 | 256 (T0-255) | ❌ (BCD `TIM` only) | ❌ |
| **CP1L** | `L10`, `L20`, `M30`, `M40` | D0 - D32767 | W0.00 - W511.15 | H0.00 - H511.15 | 4096 (T0-4095) | ✅ Supported | ❌ |
| **CP1H** | `X40`, `XA40` (Analog) | D0 - D32767 | W0.00 - W511.15 | H0.00 - H511.15 | 4096 (T0-4095) | ✅ Supported | ❌ |
| **CP2E** | `E`, `S`, `N30` (Ethernet) | D0 - D32767 | W0.00 - W511.15 | H0.00 - H1535.15 | 4096 (T0-4095) | ✅ Supported | ❌ |
| **CJ2M** | `CPU1x`, `CPU31` | D0 - D32767 | W0.00 - W511.15 | H0.00 - H511.15 | 4096 (T0-4095) | ✅ Supported | ✅ (E0_0 - E3_32767) |

---

## 2. Base Templates for Multiple Omron Series

Clean, compiler-validated base templates are included in `templates/`:
- `templates/CP1E/`: `CP1E-NA.cxt` / `.cxp`, `CP1E-E20.cxt` / `.cxp`
- `templates/CP1H/`: `CP1H-X.cxt` / `.cxp` (High-speed & Analog)
- `templates/CP2E/`: `CP2E-N.cxt` / `.cxp` (Dual Ethernet IoT)
- `templates/CJ2M/`: `CJ2M-CPU31.cxt` / `.cxp` (Modular PLC)

Each template contains a clean `Section1` workspace and mandatory `END` section with `END(001)` instruction (0 Errors, 0 Warnings when opened in CX-Programmer).

### Automatic Project Creation:
- Call `create_project` tool at runtime specifying `target_path` and `template` (e.g. `CP1H-X.cxt`, `CP2E-N.cxt`, or `CP1E-NA.cxt`).

---

## 3. How AI Agents Connect to this MCP Server

The server communicates via **stdio** following the Model Context Protocol specification.

### A. Claude Desktop Configuration
Add the server definition to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omron-plc": {
      "command": "python",
      "args": [
        "C:/path/to/Cx-Proggrammer-MCP/server.py",
        "--project",
        "C:/path/to/Cx-Proggrammer-MCP/project/my_controller.cxt",
        "--allow-write",
        "--auto-reload-cxp"
      ]
    }
  }
}
```

### B. VS Code (Cline / Roo Code / Cursor)
```json
{
  "mcpServers": {
    "omron-plc": {
      "command": "python",
      "args": [
        "C:/path/to/Cx-Proggrammer-MCP/server.py",
        "--project",
        "C:/path/to/Cx-Proggrammer-MCP/project/my_controller.cxt",
        "--allow-write",
        "--auto-reload-cxp"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

---

## 4. Available MCP Tools Reference

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `project_summary` | `{}` | Overview of PLC model, total rungs, sections, and symbols count. |
| `get_hardware_profile` | `{}` | Returns detected Omron PLC model, CPU type, memory boundaries, and timer capabilities. |
| `simulate_scan` | `section` (req), `inputs` (opt), `scans` (opt, int) | Offline simulation of N scan cycles for discrete logic, timers, and arithmetic without hardware. |
| `list_sections` | `{}` | Lists all sections and rung counts. |
| `list_rungs` | `section` (req), `start` (int), `count` (int), `mode` ("summary" \| "full") | Reads paginated rungs within a section. |
| `get_rung` | `section` (req), `index` (int, req), `mode` ("summary" \| "full") | Reads a single rung by index with comments and instructions. |
| `list_symbols` | `scope` ("global" \| "local") | Lists all symbols with addresses, types, and comments. |
| `search_project` | `query` (req), `section` (opt), `result_type` ("all" \| "rung" \| "symbol") | Fast regex search across instructions and symbols. |
| `analyze_project` | `section` (opt) | Detects logic anomalies, unreset SET coils, and double outputs. |
| `validate_project`| `{}` | Validates ladder structure, hardware memory limits, and branch balance. |
| `replace_rung` | `section` (req), `index` (req), `instructions` (list), `comment` (str) | Replaces a rung in memory (requires `--allow-write`). |
| `insert_rung` | `section` (req), `index` (req), `instructions` (list), `comment` (str) | Inserts a new rung in memory (requires `--allow-write`). |
| `delete_rung` | `section` (req), `index` (req) | Deletes a rung in memory (requires `--allow-write`). |
| `set_symbol` | `address` (req), `name` (req), `data_type` (str), `comment` (str) | Creates or updates a symbol in memory. |
| `delete_symbol` | `address_or_name` (req) | Deletes a symbol by address or name and updates VariableCount in memory (requires `--allow-write`). |
| `commit_project` | `backup` (bool, default `true`), `reload_cxp` (bool, opt) | Validates staged changes, writes twin `.cxt`/`.cxp`, and reloads CX-Programmer GUI if configured. |
| `add_section` | `section_name` (req), `before_section` (opt, default `"END"`) | Adds a new ladder section (requires `--allow-write`). |
| `rename_section` | `old_name` (req), `new_name` (req) | Renames an existing ladder section (requires `--allow-write`). |
| `create_project` | `target_path` (req), `template` (opt, default `CP1E-NA.cxt`) | Creates a brand-new project pair from base template. |
| `open_in_cxp` | `{}` | Launches the active project in CX-Programmer GUI on Windows. |

---

## 5. Offline Logic Scan Cycle Simulator

Engineers and AI agents can verify ladder logic behavior before writing to disk or downloading to hardware:

```python
from api import SafePlcProject

project = SafePlcProject("project/Traffic_Light.cxt")

# Simulate 3 scan cycles with Push Button Start pressed on scan 1
traces = project.simulate_scan(
    section="TrafficLight",
    inputs={"PB_START": True, "PB_STOP": False},
    scans=3
)

for trace in traces:
    print(f"Scan #{trace['scan']}: Changes = {trace['changes']}")
```

---

## 6. CLI Tools & Binary Codec Conversion

Convert between binary `.cxp` and text `.cxt` effortlessly:

```bash
# Decompress binary .cxp into editable text .cxt
python cli.py decode project/my_controller.cxp -o project/my_controller.cxt

# Compress text .cxt into binary .cxp
python cli.py encode project/my_controller.cxt -o project/my_controller.cxp

# Offline simulation directly from terminal
python cli.py simulate TrafficLight --inputs '{"PB_START": true}' --scans 3
```

---

## 7. Automated Test Suite

Full automated test suite with `pytest`:
```bash
pytest -v
```
All 20 test cases pass covering PKWARE DCL roundtrip, hardware boundaries, Boolean stack balance, logic simulation, and AST manipulation.
