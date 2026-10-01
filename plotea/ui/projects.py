"""Opening, saving and recovering a project.

Everything that decides where the work lives and what happens to it when the
user starts something else - including the backup copy that stands between a
power cut and an afternoon of work.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ..core import demo, diagnostics
from ..core import project as project_mod
from ..core.dataset import empty_dataset
from ..core.plotspec import PlotSpec
from ..core.project import Project

FILTER = "Projet Plotea (*.plotea)"


class ProjectFiles(QObject):
    """The project of one window, and its comings and goings on disk."""

    def __init__(self, window, app_name: str = "Plotea"):
        super().__init__(window)
        self.window = window
        self.app_name = app_name
        self._autosave_warned = False

    # ------------------------------------------------------------------
    # creation
    # ------------------------------------------------------------------
    def start_new(self, with_example: bool = False):
        """Replace the project with an empty one, or with the demo figure."""
        window = self.window
        window.project = Project()
        if with_example:
            window.project.add_dataset(demo.viability())
            window.project.add_plot(PlotSpec(
                name="Graphique 1", plot_type="bar",
                dataset=window.project.datasets[0].name,
                group="Traitement", y=["Viabilité"],
                ylabel="Viabilité (%)", stats_enabled=True,
                title="Effet des traitements"))
        else:
            window.project.add_dataset(empty_dataset())
            window.project.add_plot(PlotSpec(
                name="Graphique 1",
                dataset=window.project.datasets[0].name))
        window._reload_all(select_plot=0)
        self.update_title()

    def new_project(self):
        if not self.ask_to_keep_changes():
            return
        self.start_new()
        project_mod.clear_recovery()

    # ------------------------------------------------------------------
    # protection against losing work
    # ------------------------------------------------------------------
    def autosave(self) -> bool:
        """Copy the work in progress beside the configuration.

        Only when something has changed, and without touching the project's
        own file or its modified flag: this is a net, not a save.
        """
        window = self.window
        if not window.project.dirty:
            return False
        try:
            project_mod.write_recovery(window.project)
        except Exception as exc:                 # disk full, folder gone...
            if not self._autosave_warned:        # once, not every two minutes
                self._autosave_warned = True
                diagnostics.LOG.record(
                    "Copie de secours impossible",
                    f"{type(exc).__name__}: {exc}")
                window.statusBar().showMessage(
                    "Copie de secours impossible - voir Aide > Journal", 6000)
            return False
        self._autosave_warned = False
        window.statusBar().showMessage("Copie de secours enregistrée", 2500)
        return True

    def ask_to_keep_changes(self) -> bool:
        """Offer to save before something replaces the current project.

        Returns False when the user calls the whole thing off. Ctrl+N and
        Ouvrir used to discard the work in progress without a word.
        """
        window = self.window
        if not window.project.dirty:
            return True
        box = QMessageBox(window)
        box.setWindowTitle(self.app_name)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Le projet a été modifié.")
        box.setInformativeText(
            "Voulez-vous l'enregistrer avant de continuer ?")
        save = box.addButton("Enregistrer", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Continuer sans enregistrer",
                      QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is save:
            self.save()
            if window.project.dirty:      # the save dialog was called off
                return False
        return True

    def restore_recovery(self, info: dict) -> bool:
        """Reopen the copy left behind by a session that ended badly."""
        window = self.window
        try:
            project = Project.load(info["path"])
        except Exception as exc:
            diagnostics.LOG.record("Récupération impossible",
                                   f"{type(exc).__name__}: {exc}")
            return False
        # The copy lives beside the configuration; the project still belongs
        # to the file it came from, and was never saved there.
        project.path = info.get("origin", "")
        project.name = info.get("name") or project.name
        project.dirty = True
        window.project = project
        if not window.project.plots:
            window.project.add_plot(PlotSpec())
        window._reload_all(0)
        self.update_title()
        window.statusBar().showMessage(
            "Travail récupéré - enregistrez-le pour le conserver", 8000)
        return True

    # ------------------------------------------------------------------
    # opening and saving
    # ------------------------------------------------------------------
    def open_dialog(self):
        if not self.ask_to_keep_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Ouvrir un projet", self.window.last_dir(), FILTER)
        if path:
            self.load(path)

    def load(self, path: str) -> bool:
        window = self.window
        window.memory.remember_dir(path)
        try:
            window.project = Project.load(path)
        except Exception as exc:
            QMessageBox.critical(window, self.app_name,
                                 f"Ouverture impossible :\n{exc}")
            window.memory.forget_project(path)
            return False
        if not window.project.plots:
            window.project.add_plot(PlotSpec())
        window._reload_all(0)
        self.update_title()
        window.memory.remember_project(path)
        project_mod.clear_recovery()
        window.statusBar().showMessage(f"Projet ouvert : {path}", 4000)
        return True

    def save(self):
        window = self.window
        if not window.project.path:
            return self.save_as()
        try:
            window.project.save(window.project.path)
        except Exception as exc:
            QMessageBox.critical(window, self.app_name, f"Échec :\n{exc}")
            return
        self.update_title()
        window.memory.remember_project(window.project.path)
        project_mod.clear_recovery()      # the real file is now up to date
        window.statusBar().showMessage("Projet enregistré", 3000)

    def save_as(self):
        window = self.window
        path, _ = QFileDialog.getSaveFileName(
            window, "Enregistrer le projet",
            os.path.join(window.last_dir(),
                         window.project.name + project_mod.EXTENSION),
            FILTER)
        if not path:
            return
        window.memory.remember_dir(path)
        window.project.name = os.path.splitext(os.path.basename(path))[0]
        window.project.path = path
        self.save()

    # ------------------------------------------------------------------
    def update_title(self):
        window = self.window
        mark = "*" if window.project.dirty else ""
        name = window.project.path or window.project.name
        window.setWindowTitle(
            f"{self.app_name} - {os.path.basename(name)}{mark}")
