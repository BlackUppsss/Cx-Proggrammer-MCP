"""
MCP PLC Toolkit for Omron CP1E-NA & CX-Programmer
Self-contained, robust, AST-safe CXT/CXP manipulation engine and CLI.
"""

from .codec import decode_cxp, encode_cxp
from .engine import CxtEngine, CxtBlockError
from .api import SafePlcProject
from .cp1e import parse_address_info, validate_address, allocate_free_bit, allocate_free_word

__all__ = [
    "decode_cxp",
    "encode_cxp",
    "CxtEngine",
    "CxtBlockError",
    "SafePlcProject",
    "parse_address_info",
    "validate_address",
    "allocate_free_bit",
    "allocate_free_word",
]

