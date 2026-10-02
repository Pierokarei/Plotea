"""The window's own actions: plots, tabs, export, styles, closing.

Several of these paths were never run by a test, and four of them were
wrong: renaming broke composite figures, exporting everything crashed on a
composite figure, "Appliquer à tous" changed plots without the project
knowing, and closing after a cancelled save lost the work.
"""
import os

import pandas as pd
import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
)

from plotea.core import project as project_mod
from plotea.core.dataset import Dataset
from plotea.core.panel import Panel
from plotea.core.project import Project
from plotea.ui.dialogs import ExportDialog, ImportDialog, TransformDialog

app = QApplication.instance()


def answer(text: str):
    """Press the button named `text` in the next message box."""
    def fake(box):
        for button in box.buttons():
            if button.text().replace("&", "") == text:
                button.click()
                return 0
        raise AssertionError(f"bouton absent : {text}")
    return fake


def rename_to(name: str):
    return staticmethod(lambda *a, **k: (name, True))


# --------------------------------------------------------------------------
# Renaming
# --------------------------------------------------------------------------
def test_renaming_a_plot_keeps_it_in_its_composite_figures(window,
                                                           monkeypatch):
    first = window.project.plots[0].name
    window.project.add_panel(Panel(name="Figure A", plots=[first]))
    window._sync_tabs(0)

    monkeypatch.setattr(QInputDialog, "getText", rename_to("Viabilité J3"))
    window.rename_plot()

    assert window.project.plots[0].name == "Viabilité J3"
    assert window.project.panels[0].plots == ["Viabilité J3"], (
        "le graphique a disparu de la figure composite")
    assert window.tabbar.tabText(0) == "Viabilité J3"
    assert window.history.can_undo()


def test_a_name_already_taken_is_made_unique(window, monkeypatch):
    window.new_plot()                       # Graphique 2
    taken = window.project.plots[0].name
    window.tabbar.setCurrentIndex(1)

    monkeypatch.setattr(QInputDialog, "getText", rename_to(taken))
    window.rename_plot()

    names = window.project.plot_names()
    assert len(names) == len(set(names)), names
    assert "déjà pris" in window.statusBar().currentMessage()


def test_renaming_a_composite_figure(window, monkeypatch):
    window.new_panel()
    window.tabbar.setCurrentIndex(len(window.project.plots))
    monkeypatch.setattr(QInputDialog, "getText", rename_to("Figure 2 - final"))
    window.rename_plot()
    assert window.project.panels[0].name == "Figure 2 - final"


def test_cancelling_a_rename_changes_nothing(window, monkeypatch):
    name = window.project.plots[0].name
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("", False)))
    window.rename_plot()
    assert window.project.plots[0].name == name


def test_renaming_in_the_project_itself():
    """The rule lives in the model, so a script gets it too."""
    project = Project()
    for name in ("A", "B"):
        project.add_plot(__import__("plotea.core.plotspec",
                                    fromlist=["PlotSpec"]).PlotSpec(name=name))
    project.add_panel(Panel(name="F", plots=["A", "B"]))

    assert project.rename_plot(0, "B") == "B (2)"
    assert project.panels[0].plots == ["B (2)", "B"]
    assert project.rename_plot(9, "x") == "", "index hors limites"
    assert project.rename_plot(1, "B") == "B", "même nom : rien à faire"


# --------------------------------------------------------------------------
# Plots and tabs
# --------------------------------------------------------------------------
def test_duplicating_a_plot(window):
    before = len(window.project.plots)
    window.duplicate_plot()
    assert len(window.project.plots) == before + 1
    assert window.tabbar.currentIndex() == before
    copy = window.project.plots[-1]
    assert copy.name != window.project.plots[0].name
    assert copy.plot_type == window.project.plots[0].plot_type


def test_the_last_plot_cannot_be_deleted(window, monkeypatch):
    said = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: said.append(a)))
    window.delete_plot()
    assert len(window.project.plots) == 1
    assert said


def test_deleting_a_plot_and_undoing_it(window):
    window.new_plot()
    window.tabbar.setCurrentIndex(1)
    window.delete_plot()
    assert len(window.project.plots) == 1
    window.undo()
    assert len(window.project.plots) == 2, "la suppression ne s'annule pas"


def test_deleting_a_composite_figure(window):
    window.new_panel()
    window.tabbar.setCurrentIndex(len(window.project.plots))
    window.delete_plot()
    assert window.project.panels == []
    assert len(window.project.plots) == 1, "un graphique a été emporté"


def test_moving_tabs_reorders_the_plots(window):
    window.new_plot()
    names = window.project.plot_names()
    window._on_tab_moved(1, 0)
    assert window.project.plot_names() == list(reversed(names))


def test_a_plot_cannot_be_moved_among_the_figures(window):
    """Plots come first, composite figures after: no interleaving."""
    window.new_plot()
    window.new_panel()
    plots = window.project.plot_names()
    window._on_tab_moved(0, 2)              # a plot dropped past a figure
    assert window.project.plot_names() == plots
    assert window.tabbar.count() == 3


def test_composite_figures_can_be_reordered(window):
    window.new_panel()
    window.new_panel()
    names = window.project.panel_names()
    count = len(window.project.plots)
    window._on_tab_moved(count + 1, count)
    assert window.project.panel_names() == list(reversed(names))


def test_switching_to_a_composite_shows_its_editor(window):
    window.new_panel()
    window.tabbar.setCurrentIndex(len(window.project.plots))
    app.processEvents()
    assert window.right_stack.currentWidget() is window.panel_editor
    assert window.dock_inspector.windowTitle() == "Figure composite"


def test_the_tab_menu_offers_the_plot_actions(window, monkeypatch):
    offered = []

    def fake_exec(menu, *args, **kwargs):
        offered.extend(a.text() for a in menu.actions() if a.text())
        return None

    monkeypatch.setattr(QMenu, "exec", fake_exec)
    point = window.tabbar.tabRect(0).center()
    window._tab_menu(point)
    assert any("Renommer" in t for t in offered), offered
    assert any("Supprimer" in t for t in offered), offered


def test_the_tab_menu_ignores_empty_space(window, monkeypatch):
    monkeypatch.setattr(QMenu, "exec", lambda *a, **k: pytest.fail("menu"))
    window._tab_menu(QPoint(5000, 5))


def test_the_quick_theme_changes_only_the_current_plot(window):
    window.new_plot()
    window.tabbar.setCurrentIndex(1)
    window.set_theme("Cell")
    assert window.project.plots[1].theme == "Cell"
    assert window.project.plots[0].theme != "Cell"
    window.set_theme("pas un thème")
    assert window.project.plots[1].theme == "Cell"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "manip.csv"
    path.write_text("Groupe;Valeur\nA;1,5\nA;2\nB;3\nB;3,5\n",
                    encoding="utf-8")
    return str(path)


def test_importing_a_file_maps_it_onto_the_plot(window, csv_file,
                                                monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (csv_file, "")))
    monkeypatch.setattr(ImportDialog, "exec",
                        lambda self: ImportDialog.DialogCode.Accepted)

    window.import_data()

    assert "manip" in window.project.dataset_names()
    spec = window.current_spec()
    assert spec.dataset == "manip"
    assert spec.y, "aucune colonne de valeurs choisie"
    assert window.history.undo_label() == "Import de données"


def test_an_abandoned_import_changes_nothing(window, csv_file, monkeypatch):
    before = window.project.dataset_names()
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (csv_file, "")))
    monkeypatch.setattr(ImportDialog, "exec",
                        lambda self: ImportDialog.DialogCode.Rejected)
    window.import_data()
    assert window.project.dataset_names() == before


def test_a_new_blank_table(window):
    before = len(window.project.datasets)
    window.add_table()
    assert len(window.project.datasets) == before + 1
    assert window.history.undo_label() == "Nouvelle table"


def test_a_transform_creates_a_new_table(window, monkeypatch):
    def accept(self):
        self.result_df = pd.DataFrame({"x": [1.0, 2.0]})
        self.result_name = "Transformée"
        return TransformDialog.DialogCode.Accepted

    monkeypatch.setattr(TransformDialog, "exec", accept)
    before = window.project.dataset_names()
    window.transform_data()
    added = set(window.project.dataset_names()) - set(before)
    assert added == {"Transformée"}
    assert window.project.get_dataset("Transformée").notes.startswith(
        "Dérivée de")


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
def test_exporting_every_figure_including_a_composite(window, tmp_path,
                                                      monkeypatch):
    """It crashed as soon as the project held a composite figure."""
    window.new_panel()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: ("PNG (raster)", True)))

    window.export_all()

    written = sorted(os.listdir(tmp_path))
    assert len(written) == 2, written
    assert "exportée" in window.statusBar().currentMessage()


def test_two_figures_never_share_a_file(window, tmp_path, monkeypatch):
    """Names that sanitise alike used to overwrite each other."""
    window.project.plots[0].name = "Figure 1/2"
    window.new_plot()
    window.project.plots[1].name = "Figure 1_2"
    window._sync_tabs(0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: ("PNG (raster)", True)))

    window.export_all()

    assert len(os.listdir(tmp_path)) == 2, os.listdir(tmp_path)


def test_exporting_the_current_figure(window, tmp_path, monkeypatch):
    target = str(tmp_path / "figure.png")

    def accept(self):
        self.txt_path.setText(target)
        return ExportDialog.DialogCode.Accepted

    monkeypatch.setattr(ExportDialog, "exec", accept)
    window.export_figure()
    assert os.path.exists(target)
    assert target in window.statusBar().currentMessage()


def test_a_failed_export_is_reported(window, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(ExportDialog, "exec",
                        lambda self: ExportDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        "plotea.core.export.save_figure",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disque plein")))
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: shown.append(a)))
    window.export_figure()
    assert shown and "disque plein" in shown[0][2]


def test_copying_the_figure(window):
    QApplication.clipboard().clear()
    window._copy(False)
    assert not QApplication.clipboard().image().isNull()
    window._copy(True)
    assert "<svg" in QApplication.clipboard().text()


# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------
def test_applying_a_style_to_every_plot_is_saved_and_undoable(window):
    """It used to leave the project unmodified: closing asked nothing."""
    window.new_plot()
    window.tabbar.setCurrentIndex(0)
    window.project.dirty = False
    window.current_spec().theme = "Science"

    window.apply_style_to_all()

    assert window.project.plots[1].theme == "Science"
    assert window.project.dirty is True, "le changement n'est pas signalé"
    assert window.history.undo_label() == "Style appliqué à tous"
    window.undo()
    assert window.project.plots[1].theme != "Science"


def test_a_single_plot_has_nobody_to_share_its_style_with(window):
    window.apply_style_to_all()
    assert "Aucun autre" in window.statusBar().currentMessage()


def test_saving_and_reapplying_a_style(window, monkeypatch):
    window.current_spec().theme = "PNAS"
    monkeypatch.setattr(QInputDialog, "getText", rename_to("Mon style"))
    window.save_preset()
    assert "Mon style" in project_mod.load_presets()

    window.current_spec().theme = "Nature"
    window.apply_preset(project_mod.load_presets()["Mon style"])
    assert window.current_spec().theme == "PNAS"
    assert window.history.undo_label() == "Style enregistré"

    window._fill_presets()
    labels = [a.text() for a in window.m_presets.actions()]
    assert "Mon style" in labels


# --------------------------------------------------------------------------
# Closing
# --------------------------------------------------------------------------
def test_a_cancelled_save_keeps_the_window_open(window, monkeypatch):
    """Enregistrer, then backing out of the file dialog, used to close
    the window and throw the work away."""
    window.project.dirty = True
    window.project.path = ""
    monkeypatch.setattr(QMessageBox, "exec", answer("Enregistrer"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))

    event = QCloseEvent()
    window.closeEvent(event)

    assert not event.isAccepted(), "la fenêtre s'est fermée sans enregistrer"
    assert window.project.dirty is True


def test_quitting_without_saving_is_a_choice(window, monkeypatch):
    window.project.dirty = True
    window.autosave()
    monkeypatch.setattr(QMessageBox, "exec",
                        answer("Quitter sans enregistrer"))
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()
    assert project_mod.recovery_info() is None, (
        "une sortie voulue ne doit pas laisser croire à un incident")


def test_cancelling_the_close(window, monkeypatch):
    window.project.dirty = True
    monkeypatch.setattr(QMessageBox, "exec", answer("Annuler"))
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()


def test_saving_on_the_way_out(window, tmp_path, monkeypatch):
    window.project.dirty = True
    window.project.path = str(tmp_path / "sortie.plotea")
    monkeypatch.setattr(QMessageBox, "exec", answer("Enregistrer"))
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()
    assert os.path.exists(window.project.path)


# --------------------------------------------------------------------------
# Small windows
# --------------------------------------------------------------------------
def test_the_shortcuts_are_listed(window, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.append(a)))
    window.show_shortcuts()
    assert "Ctrl+S" in shown[0][2]


def test_the_log_and_about_windows_do_not_linger(window, monkeypatch):
    from plotea.ui.dialogs import AboutDialog, LogDialog

    monkeypatch.setattr(LogDialog, "exec", lambda self: 0)
    monkeypatch.setattr(AboutDialog, "exec", lambda self: 0)
    before = len(window.findChildren(LogDialog))
    window.show_log()
    window.show_about()
    app.sendPostedEvents(None, __import__(
        "PyQt6.QtCore", fromlist=["QEvent"]).QEvent.Type.DeferredDelete)
    assert len(window.findChildren(LogDialog)) == before
    assert not window.findChildren(AboutDialog)


def test_a_dataset_switch_from_the_inspector(window):
    window.project.add_dataset(Dataset("Autre", pd.DataFrame({"v": [1.0]})))
    window.data_panel.set_datasets(window.project.datasets, 0)
    window._on_inspector_dataset("Autre")
    assert window.current_spec().dataset == "Autre"
