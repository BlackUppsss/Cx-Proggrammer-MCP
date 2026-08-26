# cx-programmer-mcp

An MCP (Model Context Protocol) server for editing OMRON CX-Programmer ladder logic programs programmatically - without opening the GUI.

> **v0.2** - Adds `list_cpu_instructions` tool, CP1E-NA instruction table, and fixes comparison mnemonic parsing (`LD>=`, `AND<>`, `OR<=`, etc.).

Works with `.CXP` / `.CXT` files for **OMRON CJ/CP/CS series PLCs**.

> **Scope**: Programs, Sections, Ladder Mnemonics, rung comments, and symbol table only.
> Does **not** touch PLC Setup, I/O Table, network configuration, passwords, or transfer to PLC.

---

## How it works

OMRON documents `.CXP` as a compressed version of `.CXT`. `.CXT` is a text-based format that CX-Programmer can import/export. This server reads `.CXP` or `.CXT`, edits the program in memory, then saves the result as `.CXT` / `.CXP` for review in CX-Programmer before deploying to a real PLC.

Uses Python MCP SDK v2 (`MCPServer`) with `stdio` transport.

---

## Requirements

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) package manager
- CX-Programmer installed (to open `.cxp` output and download to PLC)

---

## Installation

```powershell
cd cx-programmer-mcp
uv sync
uv run cx-programmer-mcp
```

---

## MCP Client Setup

Add this to your MCP client config (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cx-programmer": {
      "command": "uv",
      "args": ["run", "cx-programmer-mcp"],
      "cwd": "ABSOLUTE_PATH_TO_THIS_FOLDER"
    }
  }
}
```

**Windows example:**
```json
"cwd": "C:\\Users\\yourname\\cx-programmer-mcp"
```

Optional - restrict file access to specific folders:
```
CX_MCP_ALLOWED_ROOTS=C:\PLC_Projects
```

---

## Project Template Setup

### Built-in template (CJ2M CPU11)

A native CJ2M CPU11 template is included. Generate a blank project:

```powershell
uv run python make_template.py
```

### Other PLC models

Each PLC model has a different binary configuration. For models other than CJ2M CPU11:

1. Open CX-Programmer on your machine
2. Create a **new empty project** for your PLC model (CP1L, CS1G, CP1E-NA, etc.)
3. Save it as `.CXP` or `.CXT`
4. **Place the file in the `project/` folder**
5. Update `make_template.py` to point to your file:

```python
SRC = Path(__file__).parent / "project" / "your_blank_template.cxp"
```

6. Run `make_template.py` once

---

## Example Program

An example ladder program is included: `project/example_basic_io.cxp`

It demonstrates a simple conveyor/IO controller with:
- Manual output control (hold-to-run)
- Scheduled auto run via RTC (configurable via DM)
- Timer-based duration
- SET/RSET latch
- Emergency reset

To rebuild it from source:

```powershell
uv run python make_template.py
uv run python build_program.py
```

Output: `project/example_basic_io.cxp` - open in CX-Programmer to review and download.

---

## Run Tests

```powershell
uv run pytest -q
```

---

## Available MCP Tools

### Read-only

| Tool | Description |
|---|---|
| `list_project_templates` | List available built-in project templates |
| `session_status` | Current revision, dirty flag, undo depth |
| `project_summary` | PLC model, I/O config, and program tree |
| `list_programs` | List all programs in the loaded project |
| `list_sections` | List sections and rung counts in a program |
| `get_program_context` | Full ladder content with rung analysis (reads/writes/AST) |
| `get_rungs` | Get rungs from one section with optional analysis |
| `analyze_rung` | Parse one rung into mnemonic, boolean AST, reads/writes, timers, counters |
| `simulate_rung` | Boolean simulation of a rung (supported subset only) |
| `search_program` | Search mnemonic text, addresses, comments, and symbols |
| `cross_reference_address` | Find every reference to an address (read/write/coil/set/reset) |
| `program_diagnostics_tool` | Report duplicate coils, SET/RSET imbalance, unclassified instructions |
| `compile_structured_rung` | Convert JSON boolean expression to mnemonic lines (dry-run) |
| `validate_program` | Validate program XML structure |
| `project_diff` | Diff two loaded projects |
| `semantic_snapshot` | Semantic JSON snapshot of the full project for AI review |
| `list_cpu_instructions` | List all known instructions for a CPU model, grouped by family |

### Session edits (in-memory, undoable)

| Tool | Description |
|---|---|
| `replace_rung` | Replace a rung's mnemonic instructions |
| `replace_rung_structured` | Replace a rung using a JSON boolean expression |
| `insert_rung` | Insert a new rung at a given index |
| `delete_rung` | Delete a rung |
| `patch_program` | Batch multiple rung edits atomically |
| `close_project` | Discard the session without saving |

### File and app

| Tool | Description |
|---|---|
| `load_project` | Load a `.cxp` or `.cxt` file into a session |
| `create_project_from_template` | Create a new blank project from a built-in template |
| `save_cxt` | Write the current session to disk as `.cxt` |
| `launch_in_cx_programmer` | Save and open the project in CX-Programmer (Windows) |

---

## CP1E-NA Instruction Support

`list_cpu_instructions` returns 60+ instructions for the CP1E-NA, grouped by family:

- **contact** - LD, LDNOT, AND, ANDNOT, OR, ORNOT
- **compare** - CMP, CMPL, LD=/LD<>/LD</LD<=/LD>/LD>=, AND=/OR= variants
- **move** - MOV, MOVL, MVN, XFER, BSET, XCHG, DIST, COLL
- **byte_move** - MOVB, MOVD, MOVW
- **math** - ADD, SUB, MUL, DIV, INC, DEC, ANDW, ORW, XORW, COM, shift/rotate
- **conversion** - BIN, BCD, BINS, BCDS, BINL, BCDL
- **timer** - TIM, TIMH, TIMX, TIMHX
- **counter** - CNT, CNTR, CNTX, CNTRX
- **control_flow** - JMP, JME, CJP, IL, ILC
- **other** - NOP, STUP, TXD, RXD (serial, CP1E-NA only)

Pass `cpu_model="CP1E-NA"` to the tool. Unknown models return `known: false` and a list of registered models.

---

## Project Structure

```
cx-programmer-mcp/
|-- src/cx_programmer_mcp/
|   |-- server.py              # MCP tool definitions
|   |-- cxt.py                 # CXT/CXP parser and editor
|   |-- ladder.py              # Mnemonic parser, analyzer, compiler, simulator
|   |-- cpu_instructions.py    # CPU-specific instruction tables (CP1E-NA, CJ2M, ...)
|   |-- diagnostics.py         # Program diagnostics and cross-reference
|   |-- recipes.py             # Reusable ladder patterns
|   |-- session.py             # In-memory session with undo/redo
|   |-- templates.py           # Built-in template registry
|   |-- templates/
|       |-- CJ2M_CPU11.cxt     # Native CJ2M CPU11 blank template
|-- tests/                     # Test suite
|-- project/                   # Output folder
|   |-- example_basic_io.cxp   # Example ladder program
|-- build_program.py           # Builds the example ladder program
|-- make_template.py           # Generates blank template from base .cxp
|-- pyproject.toml
```

---

## Notes

- Always run **Program Check in CX-Programmer** before downloading to a real PLC.
- This tool edits program logic only - I/O table, unit setup, and PLC configuration are preserved as-is from the template.
- `.CXP` output is binary-compatible with CX-Programmer 9.73 on CJ2M CPU11.
- For other PLC models, provide your own blank `.CXP` template (see Project Template Setup above).
- Comparison instructions (`LD>=`, `AND<>`, `OR<=`, etc.) are fully parsed and classified as family `compare` - no false warnings in diagnostics.
