"""Undo / redo built on project snapshots.

A snapshot holds the plot specifications as plain dicts plus a reference to
each table. Tables are only copied when an edit actually touches the data, so
restyling a figure costs almost nothing while a cell edit stays reversible.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Snapshot:
    """Restorable state of a project."""
    plots: list = field(default_factory=list)          # list[dict]
    panels: list = field(default_factory=list)         # list[dict]
    datasets: list = field(default_factory=list)       # list[(name, df, notes)]
    current_plot: int = 0
    current_dataset: int = 0


@dataclass
class Entry:
    label: str
    before: Snapshot
    after: Snapshot


class History:
    """A bounded undo stack of before/after snapshots."""

    def __init__(self, limit: int = 60):
        self.limit = limit
        self._done: list[Entry] = []
        self._undone: list[Entry] = []

    def clear(self):
        self._done.clear()
        self._undone.clear()

    def push(self, label: str, before: Snapshot, after: Snapshot):
        self._done.append(Entry(label, before, after))
        if len(self._done) > self.limit:
            self._done.pop(0)
        self._undone.clear()

    # -- state -------------------------------------------------------------
    def can_undo(self) -> bool:
        return bool(self._done)

    def can_redo(self) -> bool:
        return bool(self._undone)

    def undo_label(self) -> str:
        return self._done[-1].label if self._done else ""

    def redo_label(self) -> str:
        return self._undone[-1].label if self._undone else ""

    # -- moves -------------------------------------------------------------
    def undo(self) -> Snapshot | None:
        if not self._done:
            return None
        entry = self._done.pop()
        self._undone.append(entry)
        return entry.before

    def redo(self) -> Snapshot | None:
        if not self._undone:
            return None
        entry = self._undone.pop()
        self._done.append(entry)
        return entry.after

    def __len__(self) -> int:
        return len(self._done)
