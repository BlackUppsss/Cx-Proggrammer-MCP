# Omron CP1E MCP Server & Automation Toolkit

A Model Context Protocol (MCP) server and Python automation library designed for AI agents (Claude Desktop, Cursor, Cline, Roo Code, etc.) and engineers to inspect, analyze, validate, and safely edit Omron CX-Programmer project files (`.cxt` and `.cxp`).

---

## 1. Important Warning & PLC Compatibility

> TARGET HARDWARE WARNING:  
> This toolkit is currently configured, tested, and validated specifically for the **Omron CP1E Series** (such as `CP1E-NA20DR-A`, `CP1E-NA20DT-D`, `CP1E-E20`, `CP1E-E/N` series).
>
> Key CP1E Constraints & Memory Boundaries Enforced:
> - Timers: Standard BCD timers (`TIM xxx #SV`). CP1E does not support `TIMX` (Binary Timers).
> - Counters: `CNT xxx #SV` (0 to 255).
> - Data Memory: `D0` - `D7999` (Non-volatile).
> - Work Area: `W0.00` - `W99.15`.
> - Holding Area: `H0.00` - `H49.15` (Retentive).
> - CIO Area: Physical Inputs `CIO 0.00 - 0.11`, Outputs `CIO 100.00 - 100.07`, Internal `CIO 2 - 199`.
> - Auxiliary / System Flags: `P_On` (`CF113.00`), `P_First_Cycle` (`A200.11`), `P_1s` (`CF002`), `P_1m` (`CF001`), etc.

---

## 2. Base Templates for CP1E Series

Clean, validated base templates are included in `templates/CP1E/`:
- `CP1E-NA.cxt` / `CP1E-NA.cxp`: For CP1E-NA models (Built-in Analog I/O).
- `CP1E-E20.cxt` / `CP1E-E20.cxp`: For CP1E-E20 models (Standard Basic I/O).

Each template contains:
- `Section1`: A clean workspace section ready for user/AI ladder logic.
- `END`: A dedicated termination section containing the mandatory `END(001)` instruction.
- Zero leftover variables and valid `AtchCmts` headers (0 Errors, 0 Warnings when opened in CX-Programmer).

### Automatic Project Creation:
- **Auto-Initialization on Startup:** If you run the server targeting a non-existent file (e.g. `--project project/new_plc.cxt --allow-write`), the server will automatically clone the base template and generate its twin `.cxp` binary.
- **Dynamic Creation via MCP Tool:** Call `create_project` tool at runtime to generate a new `.cxt` and `.cxp` pair anywhere on disk.

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
        "C:/path/to/omron-cp1e-mcp/server.py",
        "--project",
        "C:/path/to/omron-cp1e-mcp/project/my_controller.cxt",
        "--allow-write",
        "--auto-reload-cxp"
      ]
    }
  }
}
```

### B. VS Code (Cline / Roo Code / Cursor)
In your MCP settings configuration (`cline_mcp_settings.json` or Cursor MCP settings):

```json
{
  "mcpServers": {
    "omron-plc": {
      "command": "python",
      "args": [
        "C:/path/to/omron-cp1e-mcp/server.py",
        "--project",
        "C:/path/to/omron-cp1e-mcp/project/my_controller.cxt",
        "--allow-write",
        "--auto-reload-cxp"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Server Startup Flags & Configurations:
- `--allow-write`: Enables editing & commit tools (without this flag, server is strictly read-only).
- `--auto-reload-cxp`: Enables automatic closing of CX-Programmer before writing and re-opening after commit.
- `--no-auto-reload-cxp`: Disables automatic closing and re-opening of CX-Programmer GUI on commit.
- Environment Variable `OMRON_AUTO_RELOAD_CXP`: Set to `1` / `true` to enable or `0` / `false` to disable by default.
- `--cxp-path <PATH>` *(optional)*: Specifies custom path to `CX-P.exe` if not installed in default Omron directory. (Can also be configured via environment variable `OMRON_CXP_PATH`).

---

## 4. Available MCP Tools Reference

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `project_summary` | `{}` | Overview of PLC model, total rungs, sections, and symbols count. |
| `list_sections` | `{}` | Lists all sections and rung counts. |
| `list_rungs` | `section` (req), `start` (int), `count` (int), `mode` ("summary" \| "full") | Reads paginated rungs within a section. |
| `get_rung` | `section` (req), `index` (int, req), `mode` ("summary" \| "full") | Reads a single rung by index with comments and instructions. |
| `list_symbols` | `scope` ("global" \| "local") | Lists all symbols with addresses, types, and comments. |
| `search_project` | `query` (req), `section` (opt), `result_type` ("all" \| "rung" \| "symbol") | Fast regex search across instructions and symbols. |
| `analyze_project` | `section` (opt) | Detects logic anomalies, unreset SET coils, and double outputs. |
| `validate_project`| `{}` | Validates ladder structure and CP1E instruction constraints. |
| `replace_rung` | `section` (req), `index` (req), `instructions` (list), `comment` (str) | Replaces a rung in memory (requires `--allow-write`). |
| `insert_rung` | `section` (req), `index` (req), `instructions` (list), `comment` (str) | Inserts a new rung in memory (requires `--allow-write`). |
| `delete_rung` | `section` (req), `index` (req) | Deletes a rung in memory (requires `--allow-write`). |
| `set_symbol` | `address` (req), `name` (req), `data_type` (str), `comment` (str) | Creates or updates a symbol in memory. |
| `commit_project` | `backup` (bool, default `true`), `reload_cxp` (bool, opt) | Validates staged changes, writes twin `.cxt`/`.cxp`, and reloads CX-Programmer GUI if configured. |
| `add_section` | `section_name` (req), `before_section` (opt, default `"END"`) | Adds a new ladder section (requires `--allow-write`). |
| `rename_section` | `old_name` (req), `new_name` (req) | Renames an existing ladder section (requires `--allow-write`). |
| `create_project` | `target_path` (req), `template` (opt, default `CP1E-NA.cxt`) | Creates a brand-new project pair from base template. |
| `open_in_cxp` | `{}` | Launches the active project in CX-Programmer GUI on Windows. |

---

## 5. CX-Programmer Auto-Close & Auto-Reopen Integration

When **CX-Programmer (`CX-P.exe`)** has a `.cxp` file open on Windows, it holds a lock on the binary project file.

### Controlling Auto-Reload Behavior:

1. **Auto-Reload Enabled (`--auto-reload-cxp` or `reload_cxp=true`):**
   - **Auto-Close:** When `commit_project` is executed, MCP safely closes `CX-P.exe` to avoid file locking issues.
   - **Atomic Write & Sync:** MCP updates the formatted `.cxt` file and encodes the binary `.cxp` file.
   - **Auto-Reopen:** MCP immediately re-launches `CX-P.exe` with the updated file, displaying the latest ladder changes instantly.

2. **Auto-Reload Disabled (`--no-auto-reload-cxp` or `reload_cxp=false`):**
   - MCP writes `.cxt` and `.cxp` files directly to disk without touching the running `CX-P.exe` process.
   - **CRITICAL PROCEDURE FOR USERS WHEN AUTO-RELOAD IS DISABLED:**  
     If CX-Programmer is currently open with the target project file when MCP commits changes:
     1. **Close CX-Programmer WITHOUT SAVING (`Don't Save`).** *(Do NOT hit Save inside CX-Programmer, or CX-Programmer will overwrite disk files with its old in-memory state!)*
     2. Re-open the `.cxp` or `.cxt` project file in CX-Programmer to load the new changes committed by MCP.

3. **On-Demand Launch:** Use the `open_in_cxp` tool at any time to open the project in CX-Programmer GUI.

---

## 6. Programmatic Python API (`SafePlcProject`)

```python
from api import SafePlcProject

# 1. Open existing project or create new from template
project = SafePlcProject("project/my_controller.cxt")

# 2. Inspect sections
print("Sections:", project.list_sections())

# 3. Modify logic
project.replace_rung("Section1", 0, ["LD 0.00", "OUT 100.00"], "Toggle Output 100.00")

# 4. Save and auto-reload in CX-Programmer GUI
project.commit(backup=True, reload_cxp=True)
```

