"""
MCP PLC Safe Editor Module
High-level API for editing symbols, rungs, and synchronizing .cxt and .cxp simultaneously with automated validation.
"""

from pathlib import Path

try:
    from .api import SafePlcProject
    from .engine import CxtBlockError
except ImportError:  # Supports direct CLI execution from this directory.
    from api import SafePlcProject
    from engine import CxtBlockError

class SafePlcEditor:
    def __init__(self, cxt_path: str | Path = "project/Traffic_Light.cxt"):
        self.cxt_path = Path(cxt_path).resolve()
        self.cxp_path = self.cxt_path.with_suffix(".cxp")
        self.project = SafePlcProject(self.cxt_path)
        self.program_name = self.project.program_name

    def upsert_symbol(self, address: str, name: str, data_type: str = "BOOL", comment: str = ""):
        return self.project.set_symbol(address, name=name, data_type=data_type, comment=comment)

    def replace_rung(self, section: str, rung_index: int, instructions: list[str], comment: str = ""):
        self.project.replace_rung(section, rung_index, instructions, comment=comment)

    def insert_rung(self, section: str, rung_index: int, instructions: list[str], comment: str = ""):
        self.project.insert_rung(section, rung_index, instructions, comment=comment)

    def delete_rung(self, section: str, rung_index: int):
        self.project.delete_rung(section, rung_index)

    def commit(self, backup: bool = True):
        """Validate structural integrity, then save to .cxt and .cxp simultaneously."""
        return self.project.commit(backup=backup)
