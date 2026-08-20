from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from .cxt import CxtProject
from .integrity import scope_integrity

T = TypeVar("T")


@dataclass
class ProjectSession:
    project: CxtProject
    revision: int = 0
    _undo: list[str] = field(default_factory=list)
    _redo: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.initial_text = self.project.original_text
        self.source_path = self.project.source_path

    def _restore(self, text: str) -> None:
        p = CxtProject(text, self.source_path)
        p.original_text = self.initial_text
        self.project = p

    def assert_revision(self, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != self.revision:
            raise ValueError(f"Stale edit: expected revision {expected_revision}, current revision {self.revision}")

    def edit(self, operation: Callable[[CxtProject], T], expected_revision: int | None = None) -> T:
        self.assert_revision(expected_revision)
        before = self.project.text()
        try:
            result = operation(self.project)
        except Exception:
            self._restore(before)
            raise
        after = self.project.text()
        if after != before:
            self._undo.append(before)
            self._redo.clear()
            self.revision += 1
        return result

    def atomic(self, operation: Callable[[CxtProject], T], expected_revision: int | None = None) -> T:
        return self.edit(operation, expected_revision)

    def undo(self, expected_revision: int | None = None) -> dict[str, Any]:
        self.assert_revision(expected_revision)
        if not self._undo:
            return {"undone": False, "revision": self.revision, "reason": "No edit to undo"}
        current = self.project.text()
        previous = self._undo.pop()
        self._redo.append(current)
        self._restore(previous)
        self.revision += 1
        return {"undone": True, "revision": self.revision}

    def redo(self, expected_revision: int | None = None) -> dict[str, Any]:
        self.assert_revision(expected_revision)
        if not self._redo:
            return {"redone": False, "revision": self.revision, "reason": "No edit to redo"}
        current = self.project.text()
        nxt = self._redo.pop()
        self._undo.append(current)
        self._restore(nxt)
        self.revision += 1
        return {"redone": True, "revision": self.revision}

    def integrity(self) -> dict[str, Any]:
        return scope_integrity(self.initial_text, self.project.text())

    def status(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "dirty": self.project.text() != self.initial_text,
            "undo_depth": len(self._undo),
            "redo_depth": len(self._redo),
            "scope_integrity": self.integrity(),
        }
