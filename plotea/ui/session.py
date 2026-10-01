"""What Plotea remembers between two runs.

A thin layer over QSettings, so the main window never has to know a key
name, and so what survives a restart can be read - and tested - in one
place instead of being scattered through a thousand-line window.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QSettings


class SessionMemory:
    """Window layout, recent projects and the folder of the last file."""

    #: How many projects the Fichier menu offers.
    RECENT_MAX = 8

    def __init__(self, settings: QSettings | None = None):
        self.settings = settings or QSettings("Plotea", "Plotea")

    # -- window layout --------------------------------------------------
    def layout(self) -> tuple:
        """(geometry, state) as Qt wrote them, either possibly None."""
        return (self.settings.value("geometry"),
                self.settings.value("windowState"))

    def remember_layout(self, geometry, state):
        self.settings.setValue("geometry", geometry)
        self.settings.setValue("windowState", state)

    def forget_layout(self):
        """Used when a stored layout cannot be read, and by Réinitialiser."""
        self.settings.remove("geometry")
        self.settings.remove("windowState")

    # -- appearance -----------------------------------------------------
    def dark(self) -> bool:
        return self.settings.value("dark", False, type=bool)

    def remember_dark(self, dark: bool):
        self.settings.setValue("dark", bool(dark))

    # -- recent projects ------------------------------------------------
    def recent_projects(self) -> list:
        """Most recently opened or saved first; whatever is stored is data."""
        stored = self.settings.value("recentProjects", [], type=list) or []
        return [p for p in stored if isinstance(p, str)]

    def remember_project(self, path: str):
        if not path:
            return
        path = os.path.abspath(path)
        recent = [p for p in self.recent_projects()
                  if os.path.normcase(p) != os.path.normcase(path)]
        recent.insert(0, path)
        self.settings.setValue("recentProjects", recent[:self.RECENT_MAX])

    def forget_project(self, path: str):
        """Drop a project the menu offered but that no longer opens."""
        target = os.path.normcase(os.path.abspath(path))
        self.settings.setValue(
            "recentProjects",
            [p for p in self.recent_projects()
             if os.path.normcase(p) != target])

    def clear_projects(self):
        self.settings.setValue("recentProjects", [])

    def existing_projects(self) -> list:
        """Only those still on disk: files come and go behind our back."""
        return [p for p in self.recent_projects() if os.path.exists(p)]

    # -- last folder ----------------------------------------------------
    def last_dir(self) -> str:
        """Folder of the last file opened or written, for the next dialog."""
        path = self.settings.value("lastDir", "", type=str)
        return path if path and os.path.isdir(path) else os.path.expanduser("~")

    def remember_dir(self, path: str):
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if folder:
            self.settings.setValue("lastDir", folder)
