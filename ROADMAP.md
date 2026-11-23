# 🗺️ Roadmap & Planned Enhancements

This document tracks known limitations and upcoming improvements for **Cx-Proggrammer-MCP**.

## 1. Structured Text (ST) & Function Block (FB) Support
- **Current State:** `engine.py` focuses on Ladder Diagram sections (`IEC1131Type:=11`, `SL:=` mnemonics).
- **Planned:** Add AST parsing, validation, and dedicated MCP tools to read/write **Structured Text (ST)** sections and custom **Function Blocks (`FunctionBlocks:=`)** commonly used in CP1H, CJ2M, and CS1H projects.

## 2. Full Program Compile (`Ctrl + F7`) in `visual_verifier.py`
- **Current State:** `visual_verifier.py` inspects the visible CX-Programmer canvas for red power rails (`RGB: R > 180, G < 70, B < 70`). Rungs scrolled off-screen are not covered by visual-only checks.
- **Planned:** Trigger CX-Programmer's built-in **Compile Program (`Ctrl + F7`)** shortcut and parse/capture the Output/Compile pane to verify 0 Errors and 0 Warnings across all rungs and sections regardless of scroll position.

## 3. Unified PLC ↔ HMI Symbol Synchronization (`Cx-Designer-MCP`)
- **Current State:** PLC symbol editing (`set_symbol`, `list_symbols`) and HMI tag management (`Cx-Designer-MCP`) operate independently.
- **Planned:** Document and streamline end-to-end symbol synchronization between `.cxt`/`.cxp` PLC projects and `.IPP`/`.IPW` CX-Designer HMI screens (mapping `CIO`, `W`, `H`, `D`, `T`, `C` addresses seamlessly).
