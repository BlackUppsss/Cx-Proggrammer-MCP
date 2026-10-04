"""
AST-safe CXT Program Engine for Omron CX-Programmer.
Preserves overall project structure while maintaining exact SC, RC, VariableCount,
Sec[i] indexing, and CRLF line endings to prevent CX-Programmer open failures.
"""

from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .codec import decode_cxp, encode_cxp
except ImportError:  # Supports direct CLI execution from this directory.
    from codec import decode_cxp, encode_cxp


@dataclass(frozen=True)
class Block:
    header: int
    begin: int
    end: int


class CxtBlockError(ValueError):
    pass


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n")


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


class CxtEngine:
    """Bulletproof CXT/CXP Parser and Editor Engine."""

    def __init__(self, text: str, source_path: str | None = None):
        self.lines = text.splitlines()
        self.trailing_newline = text.endswith("\n")
        self.original_text = text
        self.source_path = source_path

    @classmethod
    def from_path(cls, path: str | Path) -> "CxtEngine":
        path = Path(path).expanduser().resolve()
        raw = path.read_bytes()
        if path.suffix.lower() == ".cxp":
            raw = decode_cxp(raw)
        elif path.suffix.lower() != ".cxt":
            raise CxtBlockError("Only .cxp and .cxt files are supported")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
        return cls(text, str(path))

    def text(self) -> str:
        result = "\n".join(self.lines)
        if self.trailing_newline:
            result += "\n"
        return result

    def _find_block(self, header_pattern: str, start: int = 0, end: int | None = None) -> Block:
        end = len(self.lines) if end is None else end
        regex = re.compile(header_pattern)
        header = -1
        for i in range(start, end):
            if regex.match(self.lines[i]):
                header = i
                break
        if header < 0:
            raise CxtBlockError(f"Block header pattern not found: {header_pattern}")

        begin = header + 1
        while begin < end and self.lines[begin].strip() != "BEGIN":
            begin += 1
        if begin >= end:
            raise CxtBlockError(f"BEGIN not found for block at line {header + 1}")

        depth = 0
        for i in range(begin, end):
            token = self.lines[i].strip()
            if token == "BEGIN":
                depth += 1
            elif token == "END;":
                depth -= 1
                if depth == 0:
                    return Block(header, begin, i)
        raise CxtBlockError(f"END not found for block at line {header + 1}")

    def _programs_block(self) -> Block:
        return self._find_block(r"^\s*Programs:=\s*$")

    def _program_blocks(self) -> list[Block]:
        outer = self._programs_block()
        blocks: list[Block] = []
        i = outer.begin + 1
        pattern = re.compile(r"^\s*Program\[(\d+)\]:=\s*$")
        while i < outer.end:
            if pattern.match(self.lines[i]):
                block = self._find_block(r"^\s*Program\[\d+\]:=\s*$", i, outer.end)
                blocks.append(block)
                i = block.end + 1
            else:
                i += 1
        return blocks

    def _direct_value(self, block: Block, key: str) -> str | None:
        regex = re.compile(rf'^\s*{re.escape(key)}:="(.*)";\s*$')
        for i in range(block.begin + 1, block.end):
            m = regex.match(self.lines[i])
            if m:
                return _unescape(m.group(1))
        return None

    def _set_direct_quoted_value(self, block: Block, key: str, value: str) -> None:
        regex = re.compile(rf'^\s*{re.escape(key)}:="(.*)";\s*$')
        for i in range(block.begin + 1, block.end):
            m = regex.match(self.lines[i])
            if m:
                indent = self.lines[i][: len(self.lines[i]) - len(self.lines[i].lstrip())]
                self.lines[i] = f'{indent}{key}:="{_escape(value)}";'
                return
        raise CxtBlockError(f"Field not found in block: {key}")
    def list_programs(self) -> list[dict[str, Any]]:
        result = []
        for index, block in enumerate(self._program_blocks()):
            name = self._direct_value(block, "Name") or f"Program_{index}"
            result.append({"index": index, "name": name})
        return result

    def _program_block(self, name: str) -> Block:
        for block in self._program_blocks():
            if (self._direct_value(block, "Name") or "").lower() == name.lower():
                return block
        raise CxtBlockError(f"Program not found: {name}")

    def _sections_block(self, program_name: str) -> Block:
        pb = self._program_block(program_name)
        return self._find_block(r"^\s*Sections:=\s*$", pb.begin, pb.end)

    def _section_blocks(self, program_name: str) -> list[Block]:
        sb = self._sections_block(program_name)
        blocks: list[Block] = []
        i = sb.begin + 1
        pattern = re.compile(r"^\s*Sec\[(\d+)\]:=\s*$")
        while i < sb.end:
            if pattern.match(self.lines[i]):
                block = self._find_block(r"^\s*Sec\[\d+\]:=\s*$", i, sb.end)
                blocks.append(block)
                i = block.end + 1
            else:
                i += 1
        return blocks

    def list_sections(self, program_name: str = "NewProgram1") -> list[dict[str, Any]]:
        result = []
        for index, block in enumerate(self._section_blocks(program_name)):
            name = self._direct_value(block, "SecName") or f"Section_{index}"
            pdata = self._program_data_block(program_name, name)
            rc = 0
            for i in range(pdata.begin + 1, pdata.end):
                m = re.match(r"^\s*RC:=(\d+);", self.lines[i])
                if m:
                    rc = int(m.group(1))
                    break
            result.append({"index": index, "name": name, "rung_count": rc})
        return result

    def _section_block(self, program_name: str, section_name: str) -> Block:
        for block in self._section_blocks(program_name):
            if (self._direct_value(block, "SecName") or "").lower() == section_name.lower():
                return block
        raise CxtBlockError(f"Section not found: {program_name}/{section_name}")

    def _program_data_block(self, program_name: str, section_name: str) -> Block:
        sb = self._section_block(program_name, section_name)
        return self._find_block(r"^\s*ProgramData:=\s*$", sb.begin, sb.end)

    def _rung_blocks(self, program_name: str, section_name: str) -> list[Block]:
        pdata = self._program_data_block(program_name, section_name)
        blocks: list[Block] = []
        i = pdata.begin + 1
        pattern = re.compile(r"^\s*R\[(\d+)\]:=\s*$")
        while i < pdata.end:
            if pattern.match(self.lines[i]):
                block = self._find_block(r"^\s*R\[\d+\]:=\s*$", i, pdata.end)
                blocks.append(block)
                i = block.end + 1
            else:
                i += 1
        return blocks

    def _sl(self, rung: Block) -> list[str]:
        # SL in CXT can be on the same line SL:="..." or multi-line block starting with SL:=
        sl_header = -1
        for i in range(rung.begin + 1, rung.end):
            line = self.lines[i]
            if re.match(r'^\s*SL:=".*";\s*$', line):
                # Single-line escaped SL
                raw = self._direct_value(rung, "SL") or ""
                return [p.strip() for p in raw.split("\n") if p.strip()]
            if re.match(r'^\s*SL:=\s*$', line):
                sl_header = i
                break

        if sl_header < 0:
            return []

        # Find where SL block ends (usually at AtchCmts:= or next tag)
        sl_lines = []
        for i in range(sl_header + 1, rung.end):
            line = self.lines[i]
            if re.match(r'^\s*AtchCmts:=\s*$', line) or re.match(r'^\s*Flags:=', line) or re.match(r'^\s*Com:=', line):
                break
            stripped = line.strip()
            if stripped:
                sl_lines.append(stripped)
        return sl_lines

    @staticmethod
    def _is_internal_sl_line(line: str) -> bool:
        """Return True for CX-Programmer SL framing lines, not PLC mnemonics."""
        stripped = line.strip()
        return bool(
            re.fullmatch(r"\$\?St\$Bk\?_#\[\d+\]", stripped)
            or re.fullmatch(r"'\s*R\d+", stripped)
            or stripped in {"BEGIN", "END;", "BEGIN_LIST_$#[2]", "END_LIST_$#[2]"}
        )


    def get_rungs(self, program_name: str, section_name: str) -> list[dict[str, Any]]:
        result = []
        for index, rung in enumerate(self._rung_blocks(program_name, section_name)):
            comment = self._direct_value(rung, "Com") or ""
            sl_lines = self._sl(rung)
            instructions = [line for line in sl_lines if not self._is_internal_sl_line(line)]
            result.append({
                "index": index,
                "comment": comment,
                "instructions": instructions,
                "sl_raw": sl_lines
            })
        return result

    def _update_rc(self, program_name: str, section_name: str) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        pdata = self._program_data_block(program_name, section_name)
        for i in range(pdata.begin + 1, pdata.end):
            m = re.match(r"^\s*RC:=(\d+);", self.lines[i])
            if m:
                indent = self.lines[i][: len(self.lines[i]) - len(self.lines[i].lstrip())]
                self.lines[i] = f"{indent}RC:={len(rungs)};"
                return
        raise CxtBlockError(f"RC field not found in {program_name}/{section_name}")

    def _renumber_rungs(self, program_name: str, section_name: str) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        for idx, rung in enumerate(rungs):
            indent = self.lines[rung.header][: len(self.lines[rung.header]) - len(self.lines[rung.header].lstrip())]
            self.lines[rung.header] = f"{indent}R[{idx}]:="

    def _max_block_id(self) -> int:
        max_id = 0
        pattern = re.compile(r"\$\?St\$Bk\?_#\[(\d+)\]")
        for line in self.lines:
            for match in pattern.finditer(line):
                max_id = max(max_id, int(match.group(1)))
        return max_id

    @staticmethod
    def _normalize_instruction(inst: str) -> str:
        s = inst.strip()
        # Omron CX-Programmer strictly requires LDNOT, ANDNOT, ORNOT (no space between mnemonic and NOT)
        s = re.sub(r'^(LD|AND|OR)\s+NOT\b', r'\1NOT', s, flags=re.IGNORECASE)
        return s

    def _build_sl_lines(self, instructions: list[str]) -> list[str]:
        if not instructions:
            return ['       SL:="";']
        bid = self._max_block_id() + 1
        lines = [
            "       SL:=",
            f"$?St$Bk?_#[{bid}]",
            "'  R0",
        ]
        for inst in instructions:
            lines.append(self._normalize_instruction(inst))
        lines.append(f"$?St$Bk?_#[{bid}]")
        return lines

    def replace_rung(
        self, program_name: str, section_name: str, rung_index: int, instructions: list[str], comment: str = ""
    ) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        if not 0 <= rung_index < len(rungs):
            raise CxtBlockError(f"Rung index out of range: {rung_index}")
        target = rungs[rung_index]
        self._set_direct_quoted_value(target, "Com", comment)
        
        sl_start = None
        for i in range(target.begin, target.end):
            line_str = self.lines[i].strip()
            if line_str.startswith("SL:=") or line_str.startswith("SL:"):
                sl_start = i
                break
        if sl_start is None:
            raise CxtBlockError("SL field not found in rung block")
        
        sl_end = None
        for i in range(sl_start, target.end):
            if self.lines[i].strip().startswith("AtchCmts:="):
                sl_end = i
                break
        if sl_end is None:
            sl_end = target.end
            
        sl_lines = self._build_sl_lines(instructions)
        self.lines[sl_start:sl_end] = sl_lines

    def insert_rung(
        self, program_name: str, section_name: str, rung_index: int, instructions: list[str], comment: str = ""
    ) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        pdata = self._program_data_block(program_name, section_name)
        if rung_index < 0 or rung_index > len(rungs):
            raise CxtBlockError(f"Insert rung index out of range: {rung_index}")

        insert_at = pdata.end if rung_index == len(rungs) else rungs[rung_index].header
        sl_lines = self._build_sl_lines(instructions)
        lines = [
            f"      R[{rung_index}]:=",
            "      BEGIN",
            f'       Com:="{_escape(comment)}";',
            '       Flags:="1,0";',
            '       FBversion:="";',
        ]
        lines.extend(sl_lines)
        lines.extend([
            "       AtchCmts:=",
            "       BEGIN",
            "        CC:=0;",
            "       END;",
            "      END;",
        ])
        self.lines[insert_at:insert_at] = lines
        self._renumber_rungs(program_name, section_name)
        self._update_rc(program_name, section_name)

    def delete_rung(self, program_name: str, section_name: str, rung_index: int) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        if not 0 <= rung_index < len(rungs):
            raise CxtBlockError(f"Delete rung index out of range: {rung_index}")
        target = rungs[rung_index]
        del self.lines[target.header:target.end + 1]
        self._renumber_rungs(program_name, section_name)
        self._update_rc(program_name, section_name)

    def _update_sc(self, program_name: str) -> None:
        sb = self._sections_block(program_name)
        count = len(self._section_blocks(program_name))
        for i in range(sb.begin + 1, sb.end):
            m = re.match(r"^(\s*SC:=)\d+(;\s*)$", self.lines[i])
            if m:
                self.lines[i] = f"{m.group(1)}{count}{m.group(2)}"
                return

    def _renumber_sections(self, program_name: str) -> None:
        sb = self._sections_block(program_name)
        pattern = re.compile(r"^(\s*Sec\[)\d+(\]:=\s*)$")
        idx = 0
        for i in range(sb.begin + 1, sb.end):
            m = pattern.match(self.lines[i])
            if m:
                self.lines[i] = f"{m.group(1)}{idx}{m.group(2)}"
                idx += 1

    def add_section(self, program_name: str, section_name: str, before_section: str = "END") -> None:
        """Add a new section before a specific section (default before END)."""
        sections = self.list_sections(program_name)
        for sec in sections:
            if sec["name"].lower() == section_name.lower():
                raise CxtBlockError(f"Section already exists: {section_name}")
        
        insert_at = None
        for sec_block in self._section_blocks(program_name):
            if (self._direct_value(sec_block, "SecName") or "").lower() == before_section.lower():
                insert_at = sec_block.header
                break
        
        if insert_at is None:
            sb = self._sections_block(program_name)
            insert_at = sb.end

        lines = [
            f'    Sec[{len(sections)}]:=',
            '    BEGIN',
            '     IEC1131Type:=11;',
            '     CompileInline:=0;',
            '     SecType:=0;',
            f'     SecName:="{section_name}";',
            '     ProgramData:=',
            '     BEGIN',
            '      RC:=0;',
            '     END;',
            '    END;',
        ]
        self.lines[insert_at:insert_at] = lines
        self._renumber_sections(program_name)
        self._update_sc(program_name)

    def rename_section(self, program_name: str, old_name: str, new_name: str) -> None:
        """Ubah nama section pada program aktif."""
        sec_block = self._section_block(program_name, old_name)
        existing = [s["name"].lower() for s in self.list_sections(program_name)]
        if new_name.lower() in existing and new_name.lower() != old_name.lower():
            raise CxtBlockError(f"Section name already exists: {new_name}")
        self._set_direct_quoted_value(sec_block, "SecName", new_name)

    def _variable_list_range(self, scope: str, program_name: str | None = None) -> tuple[int, int, int | None]:
        if scope == "global":
            outer = self._find_block(r"^\s*GlobalVariables:=\s*$")
        elif scope == "local":
            if not program_name:
                raise CxtBlockError("program_name is required for local scope")
            pb = self._program_block(program_name)
            outer = self._find_block(r"^\s*LocalVariables:=\s*$", pb.begin, pb.end)
        else:
            raise CxtBlockError(f"Invalid variable scope: {scope}")

        assignment = None
        for i in range(outer.begin + 1, outer.end):
            if self.lines[i].strip() == "VariableList:=":
                assignment = i
                break
        if assignment is None:
            raise CxtBlockError("VariableList not found")

        start_marker = assignment + 1
        marker = self.lines[start_marker].strip()
        if not marker.startswith("BEGIN_LIST_"):
            raise CxtBlockError("Unexpected VariableList encoding")

        end_marker = start_marker + 1
        while end_marker < outer.end and not self.lines[end_marker].strip().startswith("END_LIST_"):
            end_marker += 1
        if end_marker >= outer.end:
            raise CxtBlockError("VariableList end marker not found")

        count_line = None
        for i in range(end_marker + 1, outer.end):
            if re.match(r"^\s*VariableCount:=\d+;\s*$", self.lines[i]):
                count_line = i
                break
        return start_marker + 1, end_marker, count_line

    def list_symbols(self, scope: str = "global", program_name: str | None = None) -> list[dict[str, str]]:
        start, end, _ = self._variable_list_range(scope, program_name)
        results = []
        for i in range(start, end):
            line = self.lines[i].strip()
            if not line:
                continue
            if line.endswith(";"):
                line = line[:-1]
            r = io.StringIO(line)
            reader = csv.reader(r, delimiter=",", quotechar='"')
            fields = next(reader, [])
            if len(fields) >= 3:
                name, addr, dtype = fields[0], fields[1], fields[2]
                cmt = fields[4] if len(fields) >= 5 else ""
                results.append({
                    "name": name,
                    "address": addr,
                    "type": dtype,
                    "comment": cmt,
                    "raw": line
                })
        return results

    def upsert_symbol(
        self, address: str, name: str, data_type: str = "BOOL", comment: str = "", scope: str = "global", program_name: str | None = None
    ) -> dict[str, str]:
        # Auto-correct swapped arguments if name is a valid address and address is a symbol name
        try:
            from .cp1e import validate_address
        except ImportError:
            from cp1e import validate_address
        if not validate_address(address) and validate_address(name):
            address, name = name, address
        if not validate_address(address):
            raise CxtBlockError(f"Invalid PLC memory address: {address}")
        if not name.strip():
            raise CxtBlockError("Symbol name cannot be empty")

        # Omron CX-Programmer CP1E-NA expects 5 CSV fields: [name, address, type, "", comment]
        # Timer and Counter bit contacts must use BOOL data type in VariableList
        normalized_dtype = "BOOL" if data_type.upper() in ("TIMER", "COUNTER") else data_type
        
        start, end, count_line = self._variable_list_range(scope, program_name)
        fields_out = [name, address, normalized_dtype, "", comment]
        w = io.StringIO()
        writer = csv.writer(w, delimiter=",", quotechar='"', lineterminator="")
        writer.writerow(fields_out)
        new_row = "   " + w.getvalue() + ";"

        for i in range(start, end):
            raw_line = self.lines[i].strip()
            if raw_line.endswith(";"):
                raw_line = raw_line[:-1]
            r = io.StringIO(raw_line)
            fields = next(csv.reader(r, delimiter=",", quotechar='"'), [])
            if len(fields) >= 2 and fields[1].lower() == address.lower():
                final_name = name if name else fields[0]
                final_comment = comment if comment else (fields[4] if len(fields) >= 5 else "")
                fields_out = [final_name, address, normalized_dtype, "", final_comment]
                w = io.StringIO()
                writer = csv.writer(w, delimiter=",", quotechar='"', lineterminator="")
                writer.writerow(fields_out)
                self.lines[i] = "   " + w.getvalue() + ";"
                return {"name": final_name, "address": address, "type": normalized_dtype, "comment": final_comment}

        # Insert before END_LIST (which is at index `end`)
        self.lines.insert(end, new_row)
        if count_line is not None:
            # Note: after insert, count_line index may shift by +1
            actual_count_line = count_line + 1 if count_line >= end else count_line
            curr_count = len(self.list_symbols(scope, program_name))
            indent = self.lines[actual_count_line][: len(self.lines[actual_count_line]) - len(self.lines[actual_count_line].lstrip())]
            self.lines[actual_count_line] = f"{indent}VariableCount:={curr_count};"

        return {"name": name, "address": address, "type": normalized_dtype, "comment": comment}

    def delete_symbol(self, address_or_name: str, scope: str = "global", program_name: str | None = None) -> bool:
        start, end, count_line = self._variable_list_range(scope, program_name)
        for i in range(start, end):
            raw_line = self.lines[i].strip()
            if raw_line.endswith(";"):
                raw_line = raw_line[:-1]
            r = io.StringIO(raw_line)
            fields = next(csv.reader(r, delimiter=",", quotechar='"'), [])
            if len(fields) >= 2 and (fields[1].lower() == address_or_name.lower() or fields[0].lower() == address_or_name.lower()):
                del self.lines[i]
                _, _, count_line2 = self._variable_list_range(scope, program_name)
                if count_line2 is not None:
                    curr_count = len(self.list_symbols(scope, program_name))
                    indent = self.lines[count_line2][: len(self.lines[count_line2]) - len(self.lines[count_line2].lstrip())]
                    self.lines[count_line2] = f"{indent}VariableCount:={curr_count};"
                return True
        return False


    def search(self, query: str, section: str | None = None, result_type: str = "all") -> list[dict[str, Any]]:
        if result_type not in {"all", "rung", "symbol"}:
            raise ValueError("result_type harus 'all', 'rung', atau 'symbol'")
        q = query.lower()
        matches = []
        for p in self.list_programs():
            pname = p["name"]
            for sec in self.list_sections(pname):
                sname = sec["name"]
                if section and sname.lower() != section.lower():
                    continue
                for rung in self.get_rungs(pname, sname):
                    text_hay = " ".join(rung["instructions"]) + " " + rung["comment"]
                    if result_type in {"all", "rung"} and q in text_hay.lower():
                        matches.append({
                            "type": "rung",
                            "program": pname,
                            "section": sname,
                            "index": rung["index"],
                            "comment": rung["comment"],
                            "instructions": rung["instructions"]
                        })
        for sym in self.list_symbols("global"):
            if result_type in {"all", "symbol"} and q in sym["name"].lower() or result_type in {"all", "symbol"} and (q in sym["address"].lower() or q in sym["comment"].lower()):
                matches.append({"type": "symbol", "scope": "global", **sym})
        return matches

    def analyze(self, program_name: str, section: str | None = None) -> dict[str, Any]:
        address_re = re.compile(r"\b(?:CIO|W|H|D|T|C|A)\d+(?:\.\d+)?\b", re.I)
        writer_re = re.compile(r"^\s*(OUT|SET|RSET|RST|KEEP|SFT|MOV|MOVL|XFER)\b", re.I)
        sections = [s["name"] for s in self.list_sections(program_name)]
        if section and section.lower() not in {s.lower() for s in sections}:
            raise CxtBlockError(f"Section not found: {program_name}/{section}")
        refs: dict[str, list[dict[str, Any]]] = {}
        warnings: list[dict[str, Any]] = []
        writers: dict[str, list[dict[str, Any]]] = {}
        for sname in sections:
            if section and sname.lower() != section.lower():
                continue
            for rung in self.get_rungs(program_name, sname):
                instructions = rung["instructions"]
                evidence = {"section": sname, "index": rung["index"], "display_number": rung["index"] + 1}
                inst_text = " ".join(instructions)
                for address in sorted(set(a.upper() for a in address_re.findall(inst_text))):
                    refs.setdefault(address, []).append(evidence.copy())
                for pos, instruction in enumerate(instructions):
                    match = writer_re.match(instruction)
                    if match:
                        addresses = [a.upper() for a in address_re.findall(instruction)]
                        for address in addresses:
                            writers.setdefault(address, []).append({**evidence, "instruction": instruction, "position": pos, "operation": match.group(1).upper()})
                comment = rung.get("comment", "")
                if comment:
                    mentioned = sorted(set(a.upper() for a in address_re.findall(comment)))
                    missing = [a for a in mentioned if a not in {x.upper() for x in address_re.findall(inst_text)}]
                    if missing:
                        warnings.append({**evidence, "kind": "comment_address_not_in_logic", "comment": comment, "mentioned": missing, "instructions": instructions})
        conflicts = {a: entries for a, entries in writers.items() if len(entries) > 1}
        set_ops = {a for a, entries in writers.items() if any(e["operation"] in {"SET", "KEEP"} for e in entries)}
        reset_ops = {a for a, entries in writers.items() if any(e["operation"] in {"RSET", "RST"} for e in entries)}
        return {"program": program_name, "section": section, "comment_warnings": warnings,
                "references": refs, "writers": writers, "writer_conflicts": conflicts,
                "write_without_reset": sorted(set_ops - reset_ops),
                "notes": ["Analysis is text/mnemonic-based; does not replace compiler, simulator, or live PLC online verification."]}

    def validate(self) -> dict[str, Any]:
        errors = []
        warnings = []
        try:
            progs = self.list_programs()
        except Exception as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}

        for prog in progs:
            pname = prog["name"]
            sections = self.list_sections(pname)
            for sec in sections:
                sname = sec["name"]
                rb = self._rung_blocks(pname, sname)
                pdata = self._program_data_block(pname, sname)
                rc = None
                for i in range(pdata.begin + 1, pdata.end):
                    m = re.match(r"^\s*RC:=(\d+);", self.lines[i])
                    if m:
                        rc = int(m.group(1))
                        break
                if rc is not None and rc != len(rb):
                    errors.append(f"Header RC mismatch in {pname}/{sname}: Header RC={rc}, actual rungs={len(rb)}")

                # Validasi kepatuhan instruksi CP1E-NA pada setiap rung
                try:
                    from .cp1e import validate_rung_cp1e
                except ImportError:
                    from cp1e import validate_rung_cp1e
                for rung in self.get_rungs(pname, sname):
                    rung_errs = validate_rung_cp1e(rung["instructions"])
                    for err in rung_errs:
                        errors.append(f"CP1E constraint error di {pname}/{sname} Rung {rung['index']}: {err}")

        for sym in self.list_symbols("global"):
            # Check if address is valid PLC memory address
            try:
                from .cp1e import validate_address
            except ImportError:
                from cp1e import validate_address
            if not validate_address(sym["address"]):
                errors.append(f"Invalid symbol memory address '{sym['address']}' for symbol '{sym['name']}'")

        return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


    def _create_versioned_backup(self, path: Path) -> Path | None:
        """Create versioned backup with filename_YYYYMMDD_HHMMSS_mmm.ext format in 'backup' folder."""
        if not path.exists():
            return None
        from datetime import datetime
        backup_dir = path.parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        backup_path = backup_dir / f"{path.stem}_{timestamp}{path.suffix}"
        backup_path.write_bytes(path.read_bytes())
        return backup_path

    def save_cxt(self, path: str | Path, backup: bool = True) -> str:
        path = Path(path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            self._create_versioned_backup(path)
            # Also save single .bak for compatibility
            bak = path.with_suffix(path.suffix + ".bak")
            bak.write_bytes(path.read_bytes())
        # Omron CX-Programmer Windows CXT parser strictly requires Windows CRLF line endings (\r\n)
        path.write_text(self.text(), encoding="utf-8", newline="\r\n")
        return str(path)

    def save_cxp(self, path: str | Path, backup: bool = True) -> str:
        path = Path(path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            self._create_versioned_backup(path)
            # Also save single .cxp.bak for compatibility
            bak = path.with_suffix(".cxp.bak")
            bak.write_bytes(path.read_bytes())
        cxt_bytes = self.text().replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")
        path.write_bytes(encode_cxp(cxt_bytes))
        return str(path)

    def _render_cxt_bytes(self) -> bytes:
        text = self.text().replace("\r\n", "\n").replace("\r", "\n")
        return text.replace("\n", "\r\n").encode("utf-8")

    def _render_cxp_bytes(self) -> bytes:
        text = self.text().replace("\r\n", "\n").replace("\r", "\n")
        return encode_cxp(text.replace("\n", "\r\n").encode("utf-8-sig"))

    def save_pair(self, cxt_path: str | Path, cxp_path: str | Path, backup: bool = True) -> dict[str, str]:
        """Validate and replace the CXT/CXP pair using same-directory temporary files."""
        cxt = Path(cxt_path).expanduser().resolve()
        cxp = Path(cxp_path).expanduser().resolve()
        if cxt.parent != cxp.parent:
            raise CxtBlockError("CXT and CXP must be in the same directory for an atomic commit")
        validation = self.validate()
        if not validation["ok"]:
            raise CxtBlockError(f"Validation failed: {validation['errors']}")
        cxt_bytes = self._render_cxt_bytes()
        cxp_bytes = self._render_cxp_bytes()
        cxt.parent.mkdir(parents=True, exist_ok=True)
        old_cxt = cxt.read_bytes() if cxt.exists() else None
        old_cxp = cxp.read_bytes() if cxp.exists() else None
        if backup:
            if cxt.exists(): self._create_versioned_backup(cxt)
            if cxp.exists(): self._create_versioned_backup(cxp)
            if cxt.exists(): cxt.with_suffix(cxt.suffix + ".bak").write_bytes(old_cxt)
            if cxp.exists(): cxp.with_suffix(cxp.suffix + ".bak").write_bytes(old_cxp)
        tmp_cxt = tmp_cxp = None
        try:
            with tempfile.NamedTemporaryFile(dir=cxt.parent, prefix=cxt.name + ".", suffix=".tmp", delete=False) as f:
                tmp_cxt = Path(f.name); f.write(cxt_bytes); f.flush(); os.fsync(f.fileno())
            with tempfile.NamedTemporaryFile(dir=cxp.parent, prefix=cxp.name + ".", suffix=".tmp", delete=False) as f:
                tmp_cxp = Path(f.name); f.write(cxp_bytes); f.flush(); os.fsync(f.fileno())
            check_cxt = CxtEngine(cxt_bytes.decode("utf-8"), str(tmp_cxt)).validate()
            if not check_cxt["ok"]:
                raise CxtBlockError(f"Rendered CXT failed validation: {check_cxt['errors']}")
            # Decode the generated CXP before replacing the real files.
            decoded = decode_cxp(cxp_bytes).decode("utf-8-sig")
            check_cxp = CxtEngine(decoded, str(tmp_cxp)).validate()
            if not check_cxp["ok"]:
                raise CxtBlockError(f"Rendered CXP failed validation: {check_cxp['errors']}")
            os.replace(tmp_cxt, cxt); tmp_cxt = None
            os.replace(tmp_cxp, cxp); tmp_cxp = None
        except Exception:
            if old_cxt is None: cxt.unlink(missing_ok=True)
            else: cxt.write_bytes(old_cxt)
            if old_cxp is None: cxp.unlink(missing_ok=True)
            else: cxp.write_bytes(old_cxp)
            raise
        finally:
            if tmp_cxt: tmp_cxt.unlink(missing_ok=True)
            if tmp_cxp: tmp_cxp.unlink(missing_ok=True)
        return {"cxt": str(cxt), "cxp": str(cxp)}

