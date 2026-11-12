"""
CLI interface for Omron CX-Programmer tools (.cxt / .cxp).
Supports inspection, validation, simulation, and CXP/CXT conversion.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    from .api import SafePlcProject
    from .codec import decode_cxp, encode_cxp
except ImportError:
    from api import SafePlcProject
    from codec import decode_cxp, encode_cxp


def main():
    parser = argparse.ArgumentParser(description="Omron Multi-Model CX-Programmer Project CLI")
    parser.add_argument("--project", "-p", default="project/Traffic_Light.cxt", help="Path to .cxt or .cxp file")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # summary
    subparsers.add_parser("summary", help="Display summary of hardware model, section, and symbols")

    # list-rungs
    rungs_parser = subparsers.add_parser("rungs", help="Display list of rungs in section")
    rungs_parser.add_argument("section", help="Section name (e.g.: TrafficLight)")
    rungs_parser.add_argument("--start", "-s", type=int, default=0, help="Start index")
    rungs_parser.add_argument("--count", "-c", type=int, default=10, help="Rung count")

    # search
    search_parser = subparsers.add_parser("search", help="Search instructions / addresses / text")
    search_parser.add_argument("query", help="Search query")

    # validate
    subparsers.add_parser("validate", help="Validate project AST structure, hardware constraints, and branch balance")

    # symbols
    sym_parser = subparsers.add_parser("symbols", help="Display memory symbol list")
    sym_parser.add_argument("--scope", default="global", choices=["global", "local"])

    # simulate
    sim_parser = subparsers.add_parser("simulate", help="Simulate scan cycles of a section offline")
    sim_parser.add_argument("section", help="Section name to simulate")
    sim_parser.add_argument("--inputs", "-i", default="{}", help="JSON string of inputs, e.g. '{\"0.00\": true}'")
    sim_parser.add_argument("--scans", "-n", type=int, default=3, help="Number of scan cycles")

    # decode (CXP -> CXT)
    dec_parser = subparsers.add_parser("decode", help="Decompress binary .cxp file into text .cxt")
    dec_parser.add_argument("input_cxp", help="Path to .cxp file")
    dec_parser.add_argument("-o", "--output", help="Output .cxt file path (optional)")

    # encode (CXT -> CXP)
    enc_parser = subparsers.add_parser("encode", help="Compress text .cxt file into binary .cxp")
    enc_parser.add_argument("input_cxt", help="Path to .cxt file")
    enc_parser.add_argument("-o", "--output", help="Output .cxp file path (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "decode":
            src = Path(args.input_cxp)
            out = Path(args.output) if args.output else src.with_suffix(".cxt")
            raw = src.read_bytes()
            cxt_bytes = decode_cxp(raw)
            out.write_bytes(cxt_bytes)
            print(f"[OK] Decoded {src} ({len(raw)} bytes) -> {out} ({len(cxt_bytes)} bytes)")
            return

        if args.command == "encode":
            src = Path(args.input_cxt)
            out = Path(args.output) if args.output else src.with_suffix(".cxp")
            raw = src.read_bytes()
            cxp_bytes = encode_cxp(raw)
            out.write_bytes(cxp_bytes)
            print(f"[OK] Encoded {src} ({len(raw)} bytes) -> {out} ({len(cxp_bytes)} bytes)")
            return

        prj = SafePlcProject(args.project)
        if args.command == "summary":
            s = prj.summary()
            print(f"\n[Project: {s['file']}] (Program: {s['program']})")
            print(f"Hardware: {s.get('hardware', 'Unknown')} | Total Symbols: {s['total_symbols']}")
            print("Sections:")
            for sec in s["sections"]:
                print(f"  [{sec['index']}] {sec['name']:<15} : {sec['rung_count']} rungs")
            print()

        elif args.command == "rungs":
            res = prj.list_rungs(args.section, start=args.start, count=args.count, mode="full")
            items = res.get("items", [])
            print(f"\n[Section: {args.section}] (Showing {len(items)} of {res.get('total', len(items))} rungs starting at #{args.start}):\n")
            for r in items:
                cmt = f" // {r['comment']}" if r["comment"] else ""
                print(f"--- Rung {r['index']}{cmt} ---")
                for inst in r.get("instructions", []):
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
            hw = v.get("hardware", "CP1E")
            if v["ok"]:
                print(f"\n[OK] Project AST, SC, RC, Hardware ({hw}), and Branch Balance are 100% VALID.\n")
            else:
                print(f"\n[ERROR] Project Validation FAILED for {hw}:\n{v['errors']}\n")
            if v.get("warnings"):
                print(f"[WARNINGS] {v['warnings']}\n")

        elif args.command == "symbols":
            symbols = prj.engine.list_symbols(args.scope)
            print(f"\n[Symbols ({args.scope})] Total: {len(symbols)}")
            for s in symbols:
                print(f"  {s['address']:<10} {s['name']:<25} {s['type']:<8} {s['comment']}")
            print()

        elif args.command == "simulate":
            inputs_dict = json.loads(args.inputs)
            steps = prj.simulate_scan(args.section, inputs=inputs_dict, scans=args.scans)
            print(f"\n[Simulation: Section '{args.section}' for {len(steps)} scans]")
            for step in steps:
                print(f"\n--- Scan #{step['scan']} ---")
                if step["changes"]:
                    print("  Changes:", step["changes"])
                print("  Active bits:", list(step["bits"].keys()))
            print()

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
