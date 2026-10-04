"""
MCP PLC Toolkit CLI
Concise & fast helper tools for inspection, search, rung/symbol editing, and validation of CX-Programmer projects (.cxt / .cxp).
"""

import argparse
from pathlib import Path

try:
    from .api import SafePlcProject
except ImportError:  # Supports direct CLI execution from this directory.
    from api import SafePlcProject

DEFAULT_PROJECT = Path("project/Traffic_Light.cxt")

def get_project(path_str=None):
    target = Path(path_str) if path_str else DEFAULT_PROJECT
    if not target.exists():
        cxp = target.with_suffix(".cxp")
        if cxp.exists():
            target = cxp
    return SafePlcProject(target), target

def cmd_summary(args):
    p, path = get_project(args.file)
    print(f"Project File: {path}")
    summary = p.summary()
    print(f"Program     : {summary['program']}")
    print(f"Symbols     : {summary['total_symbols']}")
    for s in summary["sections"]:
        print(f"  - {s['name']:<16}: {s['rung_count']} rungs")

def cmd_rungs(args):
    p, _ = get_project(args.file)
    prog = args.program or "NewProgram1"
    if prog != p.program_name:
        raise ValueError(f"Program not found: {prog}")
    page = p.list_rungs(args.section, mode="full")
    rungs = page["items"]
    start = args.start or 0
    end = args.end if args.end is not None else len(rungs)
    
    print(f"=== Section: {prog}/{args.section} (Rung {start} to {min(end, len(rungs)-1)}) ===")
    for idx in range(start, min(end, len(rungs))):
        r = rungs[idx]
        com = f" // {r.get('comment')}" if r.get('comment') else ""
        print(f"[{idx:02d}]{com}")
        for inst in r['instructions']:
            print(f"     {inst}")

def cmd_search(args):
    p, _ = get_project(args.file)
    results = p.search(args.query)
    print(f"Search results for '{args.query}' ({len(results)} matches):")
    for r in results:
        kind = r.get("type")
        if kind == "rung":
            print(f" [RUNG] {r['program']}/{r['section']}: Rung {r['index']} | Com: {r.get('comment')}")
            for inst in r.get("instructions", []):
                if args.query.lower() in inst.lower():
                    print(f"        -> {inst}")
        elif kind == "symbol":
            print(f" [SYMBOL] {r.get('address'):8s} | Name: {r.get('name'):20s} | {r.get('raw')}")

def cmd_symbols(args):
    p, _ = get_project(args.file)
    symbols = p.engine.list_symbols(args.scope or "global", p.program_name)
    print(f"Total symbols ({args.scope or 'global'}): {len(symbols)}")
    filter_q = args.filter.lower() if args.filter else ""
    for s in symbols:
        if not filter_q or filter_q in s['name'].lower() or filter_q in s['address'].lower():
            print(f"{s['address']:8s} | {s['name']:24s} | {s['type']:8s} | {s['raw']}")

def cmd_validate(args):
    p, path = get_project(args.file)
    val = p.validate()
    print(f"Validation for {path}: {'OK (PASS)' if val['ok'] else 'FAIL'}")
    if val['errors']:
        print("ERRORS:")
        for e in val['errors']:
            print(f"  [ERROR] {e}")
    if val['warnings']:
        print(f"WARNINGS ({len(val['warnings'])}):")
        for w in val['warnings'][:10]:
            print(f"  [WARN] {w}")
        if len(val['warnings']) > 10:
            print(f"  ... and {len(val['warnings'])-10} more warnings.")

def main():
    parser = argparse.ArgumentParser(description="MCP PLC Toolkit for CX-Programmer")
    parser.add_argument("-f", "--file", help="Path to .cxt or .cxp file", default=None)
    sub = parser.add_subparsers(dest="command")

    # Summary
    p_sum = sub.add_parser("summary", help="Show project summary")
    p_sum.set_defaults(func=cmd_summary)

    # Rungs
    p_rng = sub.add_parser("rungs", help="View section rungs")
    p_rng.add_argument("section", help="Section name (e.g. TrafficLight)")
    p_rng.add_argument("-p", "--program", help="Program name", default="NewProgram1")
    p_rng.add_argument("-s", "--start", type=int, help="Start rung index", default=0)
    p_rng.add_argument("-e", "--end", type=int, help="End rung index (exclusive)", default=None)
    p_rng.set_defaults(func=cmd_rungs)

    # Search
    p_srch = sub.add_parser("search", help="Search mnemonic instructions or symbols")
    p_srch.add_argument("query", help="Keyword/address/mnemonic to find")
    p_srch.set_defaults(func=cmd_search)

    # Symbols
    p_sym = sub.add_parser("symbols", help="List symbols")
    p_sym.add_argument("--scope", default="global", help="Scope: global or local")
    p_sym.add_argument("--filter", help="Filter by name or address", default=None)
    p_sym.set_defaults(func=cmd_symbols)

    # Validate
    p_val = sub.add_parser("validate", help="Validate project integrity")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
    else:
        args.func(args)

if __name__ == "__main__":
    main()
