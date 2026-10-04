"""
CLI interface for Omron CP1E-NA CX-Programmer tools.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    from .api import SafePlcProject
    from .cp1e import allocate_free_bit, allocate_free_word, validate_address
except ImportError:  # Supports direct CLI execution from this directory.
    from api import SafePlcProject
    from cp1e import allocate_free_bit, allocate_free_word, validate_address

def main():
    parser = argparse.ArgumentParser(description="Omron CP1E-NA / CX-Programmer Project CLI")
    parser.add_argument("--project", "-p", default="project/Traffic_Light.cxt", help="Path to .cxt or .cxp file")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # summary
    subparsers.add_parser("summary", help="Display summary of section, rung count, and symbol count")

    # list-rungs
    rungs_parser = subparsers.add_parser("rungs", help="Display list of rungs in section")
    rungs_parser.add_argument("section", help="Section name (e.g.: TrafficLight)")
    rungs_parser.add_argument("--start", "-s", type=int, default=0, help="Start index")
    rungs_parser.add_argument("--count", "-c", type=int, default=10, help="Rung count")

    # search
    search_parser = subparsers.add_parser("search", help="Search instructions / addresses / text")
    search_parser.add_argument("query", help="Search query")

    # validate
    subparsers.add_parser("validate", help="Validate project AST structure and RC/SC")

    # symbols
    sym_parser = subparsers.add_parser("symbols", help="Display memory symbol list")
    sym_parser.add_argument("--scope", default="global", choices=["global", "local"])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        prj = SafePlcProject(args.project)
        if args.command == "summary":
            s = prj.summary()
            print(f"\n[Project: {s['file']}] (Program: {s['program']})")
            print(f"Total Symbols: {s['total_symbols']}\nSections:")
            for sec in s["sections"]:
                print(f"  [{sec['index']}] {sec['name']:<15} : {sec['rung_count']} rungs")
            print()

        elif args.command == "rungs":
            rungs = prj.list_rungs(args.section, start=args.start, count=args.count)
            print(f"\n[Section: {args.section}] (Showing {len(rungs)} rungs starting at #{args.start}):\n")
            for r in rungs:
                cmt = f" // {r['comment']}" if r["comment"] else ""
                print(f"--- Rung {r['index']}{cmt} ---")
                for inst in r["instructions"]:
                    print(f"    {inst}")
                print()

        elif args.command == "search":
            results = prj.search(args.query)
            print(f"\nFound {len(results)} matches for query '{args.query}':\n")
            for m in results:
                if m["type"] == "rung":
                    print(f"[Rung] {m['program']}/{m['section']} Rung #{m['index']} (Comment: {m['comment']})")
                    for inst in m["instructions"]:
                        if args.query.lower() in inst.lower():
                            print(f"    -> {inst}")
                elif m["type"] == "symbol":
                    print(f"[Symbol] {m['name']} @ {m['address']} ({m['type']}) - {m['comment']}")
            print()

        elif args.command == "validate":
            v = prj.validate()
            if v["ok"]:
                print("\n[OK] Project AST, SC, RC, and VariableCount are 100% VALID.\n")
            else:
                print(f"\n[ERROR] Project Validation FAILED:\n{v['errors']}\n")

        elif args.command == "symbols":
            symbols = prj.engine.list_symbols(args.scope)
            print(f"\n[Symbols ({args.scope})] Total: {len(symbols)}")
            for s in symbols:
                print(f"  {s['address']:<10} {s['name']:<25} {s['type']:<8} {s['comment']}")
            print()

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
