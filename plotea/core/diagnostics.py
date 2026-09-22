"""A consultable error log.

The renderer deliberately swallows exceptions so a bad option never takes the
window down, but a one-line status message is useless when something really
breaks. Everything caught lands here with its traceback, in memory for the
Help menu and on disk for a bug report.
"""
from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime

MAX_ENTRIES = 200
LOG_NAME = "plotea-erreurs.log"


@dataclass
class Entry:
    when: str
    context: str
    summary: str
    detail: str = ""

    def short(self) -> str:
        return f"[{self.when}] {self.context} : {self.summary}"

    def full(self) -> str:
        head = self.short()
        return f"{head}\n{self.detail}" if self.detail else head


@dataclass
class Log:
    entries: list = field(default_factory=list)
    path: str = ""

    def record(self, context: str, summary: str, detail: str = "") -> Entry:
        entry = Entry(datetime.now().strftime("%H:%M:%S"), context, summary,
                      detail)
        self.entries.append(entry)
        del self.entries[:-MAX_ENTRIES]
        self._append_to_file(entry)
        return entry

    def exception(self, context: str, exc: BaseException) -> Entry:
        detail = "".join(traceback.format_exception(type(exc), exc,
                                                    exc.__traceback__))
        return self.record(context, f"{type(exc).__name__}: {exc}", detail)

    def clear(self):
        self.entries.clear()

    def text(self) -> str:
        if not self.entries:
            return "Aucune erreur enregistrée."
        return "\n\n".join(entry.full() for entry in reversed(self.entries))

    def __len__(self) -> int:
        return len(self.entries)

    # -- file ---------------------------------------------------------------
    def _append_to_file(self, entry: Entry):
        if not self.path:
            return
        try:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(f"{datetime.now().isoformat()} {entry.context} :"
                             f" {entry.summary}\n")
                if entry.detail:
                    handle.write(entry.detail)
                    handle.write("\n")
        except OSError:
            self.path = ""          # read-only install: stay in memory only


#: The log the whole application writes to.
LOG = Log()


def use_file(folder: str) -> str:
    """Send the log to `folder`, and return the file path."""
    try:
        os.makedirs(folder, exist_ok=True)
        LOG.path = os.path.join(folder, LOG_NAME)
    except OSError:
        LOG.path = ""
    return LOG.path


def record(context: str, summary: str, detail: str = "") -> Entry:
    return LOG.record(context, summary, detail)


def exception(context: str, exc: BaseException) -> Entry:
    return LOG.exception(context, exc)
