from __future__ import annotations

import csv
import difflib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cxp_decode import decode_cxp


@dataclass(frozen=True)
class Block:
    header: int
    begin: int
    end: int


class CxtError(ValueError):
    pass


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n")


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


class CxtProject:
    """Program-focused editor that preserves non-program CXT content."""

    def __init__(self, text: str, source_path: str | None = None):
        self.lines = text.splitlines()
        self.trailing_newline = text.endswith("\n")
        self.original_text = text
        self.source_path = source_path

    @classmethod
    def from_path(cls, path: str | Path) -> "CxtProject":
        path = Path(path).expanduser().resolve()
        raw = path.read_bytes()
        if path.suffix.lower() == ".cxp":
            raw = decode_cxp(raw)
        elif path.suffix.lower() != ".cxt":
            raise CxtError("Only .cxp and .cxt inputs are supported")
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
            raise CxtError(f"Block not found: {header_pattern}")

        begin = header + 1
        while begin < end and self.lines[begin].strip() != "BEGIN":
            begin += 1
        if begin >= end:
            raise CxtError(f"BEGIN not found for block at line {header + 1}")

        depth = 0
        for i in range(begin, end):
            token = self.lines[i].strip()
            if token == "BEGIN":
                depth += 1
            elif token == "END;":
                depth -= 1
                if depth == 0:
                    return Block(header, begin, i)
        raise CxtError(f"END not found for block at line {header + 1}")

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

    def _program_block(self, program_name: str) -> Block:
        for block in self._program_blocks():
            if self._direct_value(block, "Name") == program_name:
                return block
        raise CxtError(f"Program not found: {program_name}")

    def _sections_block(self, program_name: str) -> Block:
        p = self._program_block(program_name)
        return self._find_block(r"^\s*Sections:=\s*$", p.begin + 1, p.end)

    def _section_blocks(self, program_name: str) -> list[Block]:
        outer = self._sections_block(program_name)
        blocks: list[Block] = []
        i = outer.begin + 1
        pattern = re.compile(r"^\s*Sec\[(\d+)\]:=\s*$")
        while i < outer.end:
            if pattern.match(self.lines[i]):
                block = self._find_block(r"^\s*Sec\[\d+\]:=\s*$", i, outer.end)
                blocks.append(block)
                i = block.end + 1
            else:
                i += 1
        return blocks

    def _section_block(self, program_name: str, section_name: str) -> Block:
        for block in self._section_blocks(program_name):
            if self._direct_value(block, "SecName") == section_name:
                return block
        raise CxtError(f"Section not found: {program_name}/{section_name}")

    def _program_data_block(self, program_name: str, section_name: str) -> Block:
        s = self._section_block(program_name, section_name)
        return self._find_block(r"^\s*ProgramData:=\s*$", s.begin + 1, s.end)

    def _rung_blocks(self, program_name: str, section_name: str) -> list[Block]:
        outer = self._program_data_block(program_name, section_name)
        blocks: list[Block] = []
        i = outer.begin + 1
        pattern = re.compile(r"^\s*R\[(\d+)\]:=\s*$")
        while i < outer.end:
            if pattern.match(self.lines[i]):
                block = self._find_block(r"^\s*R\[\d+\]:=\s*$", i, outer.end)
                blocks.append(block)
                i = block.end + 1
            else:
                i += 1
        return blocks

    def _sl(self, rung: Block) -> list[str]:
        for i in range(rung.begin + 1, rung.end):
            stripped = self.lines[i].strip()
            if stripped == 'SL:="";':
                return []
            if stripped == "SL:=":
                if i + 1 >= rung.end:
                    return []
                marker = self.lines[i + 1].strip()
                if not marker.startswith("$?St$Bk?_"):
                    raise CxtError("Unexpected SL block encoding")
                result: list[str] = []
                j = i + 2
                while j < rung.end and self.lines[j].strip() != marker:
                    result.append(self.lines[j])
                    j += 1
                return result
        return []

    def _rung_comment(self, rung: Block) -> str:
        regex = re.compile(r'^\s*Com:="(.*)";\s*$')
        for i in range(rung.begin + 1, rung.end):
            m = regex.match(self.lines[i])
            if m:
                return _unescape(m.group(1))
        return ""

    def _replace_sl(self, rung: Block, instructions: list[str]) -> None:
        start = end = None
        indent = "       "
        for i in range(rung.begin + 1, rung.end):
            stripped = self.lines[i].strip()
            if stripped.startswith("SL:="):
                start = i
                indent = self.lines[i][: len(self.lines[i]) - len(self.lines[i].lstrip())]
                if stripped == 'SL:="";':
                    end = i
                else:
                    marker = self.lines[i + 1].strip()
                    j = i + 2
                    while j < rung.end and self.lines[j].strip() != marker:
                        j += 1
                    if j >= rung.end:
                        raise CxtError("Unterminated SL block")
                    end = j
                break
        if start is None or end is None:
            raise CxtError("Rung SL field not found")

        clean = [line.rstrip() for line in instructions if line.strip()]
        if not clean:
            replacement = [f'{indent}SL:="";']
        else:
            marker_id = self._next_marker_id()
            marker = f"$?St$Bk?_#[{marker_id}]"
            replacement = [f"{indent}SL:=", marker, *clean, marker]
        self.lines[start : end + 1] = replacement

    def _next_marker_id(self) -> int:
        ids = [int(x) for line in self.lines for x in re.findall(r"#\[(\d+)\]", line)]
        return max(ids, default=0) + 1

    def _set_direct_quoted_value(self, block: Block, key: str, value: str) -> None:
        regex = re.compile(rf"^(\s*){re.escape(key)}:=\".*\";\s*$")
        for i in range(block.begin + 1, block.end):
            m = regex.match(self.lines[i])
            if m:
                self.lines[i] = f'{m.group(1)}{key}:="{_escape(value)}";'
                return
        raise CxtError(f"Field not found: {key}")

    def project_summary(self) -> dict[str, Any]:
        def top(pattern: str) -> str | None:
            r = re.compile(pattern)
            for line in self.lines[:80]:
                m = r.match(line)
                if m:
                    return m.group(1)
            return None

        plc_name = None
        plc_model = None
        for i, line in enumerate(self.lines):
            if re.match(r"^\s*PLC:=\s*$", line):
                block = self._find_block(r"^\s*PLC:=\s*$", i)
                plc_name = self._direct_value(block, "Name")
                config = self._direct_value(block, "Config") or ""
                dev = re.search(r"DEV:([^;]+)", config)
                cpu = re.search(r"CPU:([^;]+)", config)
                if dev:
                    plc_model = dev.group(1) + (f" {cpu.group(1)}" if cpu else "")
                break
        return {
            "project_name": top(r'^Name:="(.*)";$'),
            "written_by_cx_programmer": top(r'^WrittenByCXPVersion:="(.*)";$'),
            "plc_name": plc_name,
            "plc_model": plc_model,
            "source_path": self.source_path,
            "programs": self.list_programs(),
        }

    def _set_top_quoted_value(self, key: str, value: str, search_limit: int = 120) -> None:
        regex = re.compile(rf"^(\s*){re.escape(key)}:=\".*\";\s*$")
        for i in range(min(search_limit, len(self.lines))):
            m = regex.match(self.lines[i])
            if m:
                self.lines[i] = f'{m.group(1)}{key}:="{_escape(value)}";'
                return
        raise CxtError(f"Top-level field not found: {key}")

    def set_project_identity(self, project_name: str, plc_name: str | None = None) -> None:
        """Rename project and optionally PLC identity without changing PLC type/setup."""
        self._set_top_quoted_value("Name", project_name)
        if plc_name is not None:
            for i, line in enumerate(self.lines):
                if re.match(r"^\s*PLC:=\s*$", line):
                    block = self._find_block(r"^\s*PLC:=\s*$", i)
                    self._set_direct_quoted_value(block, "Name", plc_name)
                    try:
                        block = self._find_block(r"^\s*PLC:=\s*$", i)
                        self._set_direct_quoted_value(block, "ConnectedtoPLCName", plc_name)
                    except CxtError:
                        pass
                    return
            raise CxtError("PLC block not found")

    def rename_program(self, program_name: str, new_name: str) -> None:
        if any(p["name"].lower() == new_name.lower() and p["name"].lower() != program_name.lower() for p in self.list_programs()):
            raise CxtError(f"Program already exists: {new_name}")
        block = self._program_block(program_name)
        self._set_direct_quoted_value(block, "Name", new_name)

    def touch_timestamps(self, timestamp: str) -> None:
        """Set project/program Created/Modified strings using CX-Programmer's textual timestamp shape."""
        for key in ("Created", "Modified"):
            self._set_top_quoted_value(key, timestamp)
        # Re-resolve each program as line offsets change minimally but names do not.
        for program in self.list_programs():
            block = self._program_block(program["name"])
            for key in ("Created", "Modified"):
                try:
                    self._set_direct_quoted_value(block, key, timestamp)
                    block = self._program_block(program["name"])
                except CxtError:
                    pass

    def clear_symbols(self, scope: str = "global", program_name: str | None = None) -> int:
        """Remove all symbol rows while preserving the native CXT symbol-list container."""
        start, end, _ = self._variable_list_range(scope, program_name)
        count = sum(1 for i in range(start, end) if self.lines[i].strip())
        del self.lines[start:end]
        _, _, count_line = self._variable_list_range(scope, program_name)
        if count_line is not None:
            lead = self.lines[count_line][: len(self.lines[count_line]) - len(self.lines[count_line].lstrip())]
            self.lines[count_line] = f"{lead}VariableCount:=0;"
        return count

    def reset_section_to_blank(self, program_name: str, section_name: str, trailing_empty_rungs: int = 1) -> None:
        """Reset a normal ladder section to CX-style empty rungs, keeping section metadata."""
        if section_name.upper() == "END":
            raise CxtError("Use END section as generated by the template; refusing to blank it")
        rungs = self._rung_blocks(program_name, section_name)
        # CX projects need at least one rung object. Keep one and remove the rest.
        while len(rungs) > 1:
            rung = rungs[-1]
            del self.lines[rung.header : rung.end + 1]
            rungs = self._rung_blocks(program_name, section_name)
        self._renumber_rungs_and_rc(program_name, section_name)
        self.replace_rung(program_name, section_name, 0, [], "")
        # Create additional empty rows only when explicitly requested.
        while len(self._rung_blocks(program_name, section_name)) < max(1, trailing_empty_rungs):
            self.insert_rung(program_name, section_name, len(self._rung_blocks(program_name, section_name)), [], "")

    def list_programs(self) -> list[dict[str, Any]]:
        result = []
        for block in self._program_blocks():
            name = self._direct_value(block, "Name") or ""
            sections = [self._direct_value(s, "SecName") or "" for s in self._section_blocks(name)]
            result.append({"name": name, "sections": sections})
        return result

    def list_sections(self, program_name: str) -> list[dict[str, Any]]:
        result = []
        for index, block in enumerate(self._section_blocks(program_name)):
            name = self._direct_value(block, "SecName") or f"Section{index}"
            rungs = self._rung_blocks(program_name, name)
            non_empty = sum(bool(self._sl(r)) for r in rungs)
            result.append({"index": index, "name": name, "rung_count": len(rungs), "non_empty_rungs": non_empty})
        return result

    def get_rungs(self, program_name: str, section_name: str, include_empty: bool = True) -> list[dict[str, Any]]:
        result = []
        for index, rung in enumerate(self._rung_blocks(program_name, section_name)):
            instructions = self._sl(rung)
            if not include_empty and not instructions:
                continue
            result.append({
                "index": index,
                "comment": self._rung_comment(rung),
                "instructions": instructions,
                "empty": not instructions,
            })
        return result

    def get_program_context(self, program_name: str, include_empty: bool = False) -> dict[str, Any]:
        return {
            "program": program_name,
            "sections": [
                {
                    "name": section["name"],
                    "rungs": self.get_rungs(program_name, section["name"], include_empty=include_empty),
                }
                for section in self.list_sections(program_name)
            ],
            "symbols": self.list_symbols("global"),
        }

    def replace_rung(self, program_name: str, section_name: str, rung_index: int, instructions: list[str], comment: str | None = None) -> dict[str, Any]:
        rungs = self._rung_blocks(program_name, section_name)
        if not 0 <= rung_index < len(rungs):
            raise CxtError(f"Rung index out of range: {rung_index}")
        rung = rungs[rung_index]
        self._replace_sl(rung, instructions)
        if comment is not None:
            # Re-resolve because SL replacement can shift indices.
            rung = self._rung_blocks(program_name, section_name)[rung_index]
            self._set_direct_quoted_value(rung, "Com", comment)
        return self.get_rungs(program_name, section_name)[rung_index]

    def _new_rung_lines(self, index: int, instructions: list[str], comment: str = "") -> list[str]:
        marker_id = self._next_marker_id()
        clean = [line.rstrip() for line in instructions if line.strip()]
        sl = ['       SL:="";'] if not clean else [
            "       SL:=",
            f"$?St$Bk?_#[{marker_id}]",
            *clean,
            f"$?St$Bk?_#[{marker_id}]",
        ]
        return [
            f"      R[{index}]:=",
            "      BEGIN",
            f'       Com:="{_escape(comment)}";',
            '       Flags:="1,0";',
            '       FBversion:="";',
            *sl,
            "       AtchCmts:=",
            "       BEGIN",
            "        CC:=0;",
            "       END;",
            "      END;",
        ]

    def _renumber_rungs_and_rc(self, program_name: str, section_name: str) -> None:
        blocks = self._rung_blocks(program_name, section_name)
        for index, block in enumerate(blocks):
            indent = self.lines[block.header][: len(self.lines[block.header]) - len(self.lines[block.header].lstrip())]
            self.lines[block.header] = f"{indent}R[{index}]:="
        pdata = self._program_data_block(program_name, section_name)
        for i in range(pdata.begin + 1, pdata.end):
            if re.match(r"^\s*RC:=\d+;\s*$", self.lines[i]):
                indent = self.lines[i][: len(self.lines[i]) - len(self.lines[i].lstrip())]
                self.lines[i] = f"{indent}RC:={len(blocks)};"
                return
        raise CxtError("ProgramData RC field not found")

    def insert_rung(self, program_name: str, section_name: str, rung_index: int, instructions: list[str], comment: str = "") -> dict[str, Any]:
        rungs = self._rung_blocks(program_name, section_name)
        if not 0 <= rung_index <= len(rungs):
            raise CxtError(f"Rung insert index out of range: {rung_index}")
        pdata = self._program_data_block(program_name, section_name)
        insert_at = rungs[rung_index].header if rung_index < len(rungs) else pdata.end
        self.lines[insert_at:insert_at] = self._new_rung_lines(rung_index, instructions, comment)
        self._renumber_rungs_and_rc(program_name, section_name)
        return self.get_rungs(program_name, section_name)[rung_index]

    def delete_rung(self, program_name: str, section_name: str, rung_index: int) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        if len(rungs) <= 1:
            raise CxtError("Refusing to delete the last rung in a section")
        if not 0 <= rung_index < len(rungs):
            raise CxtError(f"Rung index out of range: {rung_index}")
        rung = rungs[rung_index]
        del self.lines[rung.header : rung.end + 1]
        self._renumber_rungs_and_rc(program_name, section_name)

    def set_rung_comment(self, program_name: str, section_name: str, rung_index: int, comment: str) -> None:
        rungs = self._rung_blocks(program_name, section_name)
        if not 0 <= rung_index < len(rungs):
            raise CxtError(f"Rung index out of range: {rung_index}")
        self._set_direct_quoted_value(rungs[rung_index], "Com", comment)

    def rename_section(self, program_name: str, section_name: str, new_name: str) -> None:
        if any(s["name"].lower() == new_name.lower() for s in self.list_sections(program_name)):
            raise CxtError(f"Section already exists: {new_name}")
        block = self._section_block(program_name, section_name)
        self._set_direct_quoted_value(block, "SecName", new_name)

    def _renumber_sections_and_sc(self, program_name: str) -> None:
        blocks = self._section_blocks(program_name)
        for index, block in enumerate(blocks):
            indent = self.lines[block.header][: len(self.lines[block.header]) - len(self.lines[block.header].lstrip())]
            self.lines[block.header] = f"{indent}Sec[{index}]:="
        sections = self._sections_block(program_name)
        for i in range(sections.begin + 1, sections.end):
            if re.match(r"^\s*SC:=\d+;\s*$", self.lines[i]):
                indent = self.lines[i][: len(self.lines[i]) - len(self.lines[i].lstrip())]
                self.lines[i] = f"{indent}SC:={len(blocks)};"
                return
        raise CxtError("Sections SC field not found")

    def create_section(self, program_name: str, section_name: str, before_section: str | None = "END") -> None:
        if any(s["name"].lower() == section_name.lower() for s in self.list_sections(program_name)):
            raise CxtError(f"Section already exists: {section_name}")
        blocks = self._section_blocks(program_name)
        sections = self._sections_block(program_name)
        index = len(blocks)
        insert_at = sections.end
        if before_section is not None:
            target = self._section_block(program_name, before_section)
            index = [b.header for b in blocks].index(target.header)
            insert_at = target.header
        marker = self._next_marker_id()
        lines = [
            f"    Sec[{index}]:=",
            "    BEGIN",
            "     IEC1131Type:=11;",
            "     CompileInline:=0;",
            "     SecType:=0;",
            f'     SecName:="{_escape(section_name)}";',
            "     ProgramData:=",
            "     BEGIN",
            "      RC:=1;",
            "      R[0]:=",
            "      BEGIN",
            '       Com:="";',
            '       Flags:="1,0";',
            '       FBversion:="";',
            '       SL:="";',
            "       AtchCmts:=",
            "       BEGIN",
            "        CC:=0;",
            "       END;",
            "      END;",
            "     END;",
            "    END;",
        ]
        self.lines[insert_at:insert_at] = lines
        self._renumber_sections_and_sc(program_name)

    def delete_section(self, program_name: str, section_name: str) -> None:
        if section_name.upper() == "END":
            raise CxtError("Refusing to delete the END section")
        block = self._section_block(program_name, section_name)
        del self.lines[block.header : block.end + 1]
        self._renumber_sections_and_sc(program_name)

    def _variable_list_range(self, scope: str, program_name: str | None = None) -> tuple[int, int, int | None]:
        if scope == "global":
            outer = self._find_block(r"^\s*GlobalVariables:=\s*$")
        elif scope == "local":
            if not program_name:
                raise CxtError("program_name is required for local symbols")
            p = self._program_block(program_name)
            outer = self._find_block(r"^\s*LocalVariables:=\s*$", p.begin + 1, p.end)
        else:
            raise CxtError("scope must be 'global' or 'local'")

        assignment = None
        for i in range(outer.begin + 1, outer.end):
            if self.lines[i].strip() == "VariableList:=":
                assignment = i
                break
        if assignment is None:
            raise CxtError("VariableList not found")
        start_marker = assignment + 1
        marker = self.lines[start_marker].strip()
        if not marker.startswith("BEGIN_LIST_"):
            raise CxtError("Unexpected VariableList encoding")
        end_marker = start_marker + 1
        while end_marker < outer.end and not self.lines[end_marker].strip().startswith("END_LIST_"):
            end_marker += 1
        if end_marker >= outer.end:
            raise CxtError("VariableList end marker not found")

        count_line = None
        for i in range(end_marker + 1, outer.end):
            if re.match(r"^\s*VariableCount:=\d+;\s*$", self.lines[i]):
                count_line = i
                break
        return start_marker + 1, end_marker, count_line

    @staticmethod
    def _parse_var_line(line: str) -> list[str]:
        stripped = line.strip()
        if stripped.endswith(";"):
            stripped = stripped[:-1]
        return next(csv.reader([stripped], delimiter=",", quotechar='"'))

    @staticmethod
    def _format_var_fields(fields: list[str]) -> str:
        # CXT VariableList is CSV-like. Quote only when required so simple files stay
        # visually close to CX-Programmer's native output.
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=",", quotechar='"', lineterminator="", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(fields)
        return buf.getvalue() + ";"

    def list_symbols(self, scope: str = "global", program_name: str | None = None) -> list[dict[str, str]]:
        start, end, _ = self._variable_list_range(scope, program_name)
        result = []
        for i in range(start, end):
            if not self.lines[i].strip():
                continue
            fields = self._parse_var_line(self.lines[i])
            fields += [""] * (7 - len(fields))
            result.append({
                "name": fields[0],
                "address": fields[1],
                "type": fields[2],
                "comment": fields[-1],
                "raw": self.lines[i].strip(),
            })
        return result

    def upsert_symbol(self, address: str, name: str = "", data_type: str = "BOOL", comment: str = "", scope: str = "global", program_name: str | None = None) -> dict[str, str]:
        start, end, count_line = self._variable_list_range(scope, program_name)
        for i in range(start, end):
            fields = self._parse_var_line(self.lines[i])
            fields += [""] * (7 - len(fields))
            if fields[1].lower() == address.lower():
                fields[0] = name
                fields[2] = data_type
                fields[-1] = comment
                indent = self.lines[i][: len(self.lines[i]) - len(self.lines[i].lstrip())]
                self.lines[i] = indent + self._format_var_fields(fields)
                return {"name": name, "address": address, "type": data_type, "comment": comment}

        indent = "   "
        fields = [name, address, data_type, "", "", "", comment]
        self.lines[end:end] = [indent + self._format_var_fields(fields)]
        if count_line is not None:
            # count_line shifted by insertion if it was after end marker
            _, _, count_line2 = self._variable_list_range(scope, program_name)
            if count_line2 is not None:
                current = len(self.list_symbols(scope, program_name))
                lead = self.lines[count_line2][: len(self.lines[count_line2]) - len(self.lines[count_line2].lstrip())]
                self.lines[count_line2] = f"{lead}VariableCount:={current};"
        return {"name": name, "address": address, "type": data_type, "comment": comment}


    def delete_symbol(self, address: str, scope: str = "global", program_name: str | None = None) -> bool:
        start, end, _ = self._variable_list_range(scope, program_name)
        for i in range(start, end):
            fields = self._parse_var_line(self.lines[i])
            fields += [""] * (7 - len(fields))
            if fields[1].lower() == address.lower():
                del self.lines[i]
                _, _, count_line = self._variable_list_range(scope, program_name)
                if count_line is not None:
                    current = len(self.list_symbols(scope, program_name))
                    lead = self.lines[count_line][: len(self.lines[count_line]) - len(self.lines[count_line].lstrip())]
                    self.lines[count_line] = f"{lead}VariableCount:={current};"
                return True
        return False

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        hits: list[dict[str, Any]] = []
        for program in self.list_programs():
            for section in self.list_sections(program["name"]):
                for rung in self.get_rungs(program["name"], section["name"], include_empty=False):
                    hay = "\n".join(rung["instructions"]) + "\n" + rung["comment"]
                    if q in hay.lower():
                        hits.append({
                            "kind": "rung",
                            "program": program["name"],
                            "section": section["name"],
                            **rung,
                        })
        for symbol in self.list_symbols("global"):
            if q in " ".join(symbol.values()).lower():
                hits.append({"kind": "global_symbol", **symbol})
        for program in self.list_programs():
            try:
                local_symbols = self.list_symbols("local", program["name"])
            except CxtError:
                local_symbols = []
            for symbol in local_symbols:
                if q in " ".join(symbol.values()).lower():
                    hits.append({"kind": "local_symbol", "program": program["name"], **symbol})
        return hits

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        outputs: dict[str, list[str]] = {}

        try:
            programs = self.list_programs()
        except Exception as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}

        for program in programs:
            name = program["name"]
            sections = self.list_sections(name)
            # Check SC.
            sb = self._sections_block(name)
            sc = None
            for i in range(sb.begin + 1, sb.end):
                m = re.match(r"^\s*SC:=(\d+);", self.lines[i])
                if m:
                    sc = int(m.group(1)); break
            if sc is not None and sc != len(sections):
                errors.append(f"{name}: SC={sc}, actual sections={len(sections)}")

            for section in sections:
                sname = section["name"]
                rb = self._rung_blocks(name, sname)
                pdata = self._program_data_block(name, sname)
                rc = None
                for i in range(pdata.begin + 1, pdata.end):
                    m = re.match(r"^\s*RC:=(\d+);", self.lines[i])
                    if m:
                        rc = int(m.group(1)); break
                if rc is not None and rc != len(rb):
                    errors.append(f"{name}/{sname}: RC={rc}, actual rungs={len(rb)}")

                for idx, rung in enumerate(rb):
                    instructions = self._sl(rung)
                    for line in instructions:
                        if not re.match(r"^[A-Za-z@][A-Za-z0-9@]*(?:\(\d+\))?(?:\s+.*)?$", line.strip()):
                            warnings.append(f"{name}/{sname} rung {idx}: unusual mnemonic syntax: {line}")
                        m = re.match(r"^OUT(?:\(\d+\))?\s+([^\s]+)", line.strip(), re.I)
                        if m:
                            outputs.setdefault(m.group(1), []).append(f"{name}/{sname}:{idx}")

        for address, refs in outputs.items():
            if len(refs) > 1:
                warnings.append(f"Duplicate OUT destination {address}: {', '.join(refs)}")

        return {"ok": not errors, "errors": errors, "warnings": warnings}

    def diff(self, context: int = 3) -> str:
        return "\n".join(difflib.unified_diff(
            self.original_text.splitlines(),
            self.text().splitlines(),
            fromfile="original.cxt",
            tofile="edited.cxt",
            lineterm="",
            n=context,
        ))

    def save_cxt(self, path: str | Path, backup: bool = True) -> str:
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() != ".cxt":
            path = path.with_suffix(".cxt")
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            backup_path.write_bytes(path.read_bytes())
        path.write_text(self.text(), encoding="utf-8", newline="\n")
        return str(path)

    def save_cxp(self, path: str | Path, backup: bool = True) -> str:
        """Encode project ke format .cxp (PKWARE DCL Implode) untuk dibuka CX-Programmer."""
        from .cxp_decode import encode_cxp
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() != ".cxp":
            path = path.with_suffix(".cxp")
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            backup_path = path.with_suffix(".cxp.bak")
            backup_path.write_bytes(path.read_bytes())
        raw = self.text().replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")
        path.write_bytes(encode_cxp(raw))
        return str(path)
