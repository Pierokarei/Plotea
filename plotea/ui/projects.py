"""Opening, saving and recovering a project.

Everything that decides where the work lives and what happens to it when the
user starts something else - including the backup copy that stands between a
power cut and an afternoon of work.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ..core import demo, diagnostics, versions
from ..core import project as project_mod
from ..core.dataset import empty_dataset
from ..core.plotspec import PlotSpec
from ..core.project import Project
from ..i18n import tr

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
                name=tr("Graphique {number}").format(number=1),
                plot_type="bar",
                dataset=window.project.datasets[0].name,
                group=tr("Traitement"), y=[tr("Viabilité")],
                ylabel=tr("Viabilité (%)"), stats_enabled=True,
                design="independent",
                title=tr("Effet des traitements")))
        else:
            window.project.add_dataset(empty_dataset())
            window.project.add_plot(PlotSpec(
                name=tr("Graphique {number}").format(number=1),
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
                    tr("Copie de secours impossible - voir Aide > Journal"), 6000)
            return False
        self._autosave_warned = False
        window.statusBar().showMessage(tr("Copie de secours enregistrée"), 2500)
        return True

    def ask_to_keep_changes(self, discard: str = "Continuer sans enregistrer",
                            question: str = "Voulez-vous l'enregistrer avant "
                                            "de continuer ?") -> bool:
        """Offer to save before something replaces the current project.

        Returns False when the user calls the whole thing off - including
        when they chose Enregistrer and then backed out of the file dialog,
        which is the case closing the window used to get wrong.
        """
        window = self.window
        if not window.project.dirty:
            return True
        box = QMessageBox(window)
        box.setWindowTitle(self.app_name)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(tr("Le projet a été modifié."))
        box.setInformativeText(tr(question))
        save = box.addButton(tr("Enregistrer"), QMessageBox.ButtonRole.AcceptRole)
        drop = box.addButton(tr(discard), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr("Annuler"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            self.save()
            return not window.project.dirty   # the save dialog called off
        # Work is thrown away only when "continue without saving" was
        # clicked. A box closed without a button - by the system, or by
        # code - gives no button at all, and used to go on as if it had.
        return clicked is drop

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
            tr("Travail récupéré - enregistrez-le pour le conserver"), 8000)
        return True

    # ------------------------------------------------------------------
    # opening and saving
    # ------------------------------------------------------------------
    def open_dialog(self):
        if not self.ask_to_keep_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window, tr("Ouvrir un projet"), self.window.last_dir(), FILTER)
        if path:
            self.load(path)

    def load(self, path: str) -> bool:
        window = self.window
        window.memory.remember_dir(path)
        try:
            window.project = Project.load(path)
        except Exception as exc:
            earlier = versions.versions_of_file(path)
            if earlier and self._offer_version(path, exc, earlier[0]):
                return True
            if not earlier:
                QMessageBox.critical(window, self.app_name, tr(
                    "Ouverture impossible :\n{error}").format(error=exc))
            window.memory.forget_project(path)
            return False
        if not window.project.plots:
            window.project.add_plot(PlotSpec())
        window._reload_all(0)
        self.update_title()
        window.memory.remember_project(path)
        project_mod.clear_recovery()
        if window.project.load_warnings:
            for warning in window.project.load_warnings:
                diagnostics.LOG.record("Projet incomplet", warning, path)
            window.statusBar().showMessage(
                tr("Projet ouvert, mais incomplet : {details}").format(
                    details="; ".join(tr(w) for w in
                                      window.project.load_warnings)), 12000)
        else:
            window.statusBar().showMessage(tr("Projet ouvert : {path}").format(path=path), 4000)
        return True

    def _offer_version(self, path: str, error, latest: dict) -> bool:
        """A file that no longer opens: offer the last version kept of it."""
        box = QMessageBox(self.window)
        box.setWindowTitle(self.app_name)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(tr("Ouverture impossible :\n{error}").format(error=error))
        box.setInformativeText(tr(
            "Plotea a conservé une version antérieure de ce fichier, "
            "enregistrée le {date}. L'ouvrir ?").format(
                date=latest["saved"].strftime(tr("%d/%m/%Y à %H:%M"))))
        reopen = box.addButton(tr("Ouvrir cette version"),
                               QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Fermer"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(reopen)
        box.exec()
        if box.clickedButton() is not reopen:
            return False
        return self.open_version(latest, path, ask=False)

    def show_versions(self):
        """Fichier > Versions précédentes: the project's earlier states."""
        from .dialogs import VersionsDialog

        window = self.window
        dialog = VersionsDialog(versions.versions(window.project.uid), window)
        try:
            if dialog.exec() and dialog.chosen is not None:
                self.open_version(dialog.chosen, window.project.path)
        finally:
            dialog.deleteLater()

    def open_version(self, entry: dict, belongs_to: str = "",
                     ask: bool = True) -> bool:
        """Put an earlier version on screen, still belonging to its file.

        Nothing is written: saving it is what puts it back, and the state
        it then replaces is kept in turn.
        """
        window = self.window
        if ask and not self.ask_to_keep_changes():
            return False
        try:
            project = Project.load(entry["path"])
        except Exception as exc:
            QMessageBox.critical(window, self.app_name, tr(
                "Ouverture impossible :\n{error}").format(error=exc))
            return False
        project.path = belongs_to or entry.get("origin", "")
        if project.path:
            project.name = os.path.splitext(os.path.basename(project.path))[0]
        project.dirty = True
        window.project = project
        if not window.project.plots:
            window.project.add_plot(PlotSpec())
        window._reload_all(0)
        self.update_title()
        window.statusBar().showMessage(tr(
            "Version du {date} ouverte - enregistrez pour la rétablir ; "
            "l'état actuel du fichier sera conservé").format(
                date=entry["saved"].strftime(tr("%d/%m/%Y à %H:%M"))), 12000)
        return True

    def save(self) -> bool:
        window = self.window
        if not window.project.path:
            return self.save_as()
        try:
            window.project.save(window.project.path)
        except Exception as exc:
            QMessageBox.critical(
                window, self.app_name,
                tr("Échec de l'enregistrement :\n{error}\n\n"
                   "Le fichier précédent est intact.").format(error=exc))
            return False
        self.update_title()
        window.memory.remember_project(window.project.path)
        project_mod.clear_recovery()      # the real file is now up to date
        window.statusBar().showMessage(tr("Projet enregistré"), 3000)
        return True

    def save_as(self):
        window = self.window
        path, _ = QFileDialog.getSaveFileName(
            window, tr("Enregistrer le projet"),
            os.path.join(window.last_dir(),
                         window.project.name + project_mod.EXTENSION),
            FILTER)
        if not path:
            return False
        window.memory.remember_dir(path)
        before = (window.project.name, window.project.path)
        window.project.name = os.path.splitext(os.path.basename(path))[0]
        window.project.path = path
        if not self.save():
            # nothing was written there: the project still belongs where it
            # was, not to a file that does not exist
            window.project.name, window.project.path = before
            self.update_title()
            return False
        return True

    # ------------------------------------------------------------------
    def update_title(self):
        window = self.window
        mark = "*" if window.project.dirty else ""
        # the default name is Plotea's; a name the user typed is theirs
        name = window.project.path or tr(window.project.name)
        window.setWindowTitle(
            f"{self.app_name} - {os.path.basename(name)}{mark}")
