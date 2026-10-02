"""Starting the application: what happens before the event loop."""
import os

import pandas as pd
import pytest
from conftest import dispose
from PyQt6.QtWidgets import QApplication, QMessageBox

from plotea import app as app_mod
from plotea.core import diagnostics
from plotea.core.dataset import Dataset
from plotea.core.project import Project

app = QApplication.instance()


@pytest.fixture
def started():
    """A real startup, torn down like any other window."""
    application, window = app_mod.build([])
    yield application, window
    dispose(window)


def test_a_startup_produces_a_usable_window(started):
    application, window = started
    assert window.isVisible()
    assert window.project.plots, "aucun graphique de départ"
    assert window.current_spec() is not None
    assert application.applicationName() == "Plotea"
    assert application.applicationVersion() == app_mod.VERSION


def test_the_interface_starts_in_french(started):
    application, _ = started
    box = QMessageBox()
    box.setStandardButtons(QMessageBox.StandardButton.Save)
    assert box.buttons()[0].text().replace("&", "") == "Enregistrer"
    del application


def test_startup_does_not_claim_a_second_application(started):
    """Qt allows one per process; an embedding host already has one."""
    application, _ = started
    assert application is QApplication.instance()


def test_the_error_hook_reports_instead_of_aborting(qapp, monkeypatch):
    """A slot that raises must leave the application standing."""
    shown = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: shown.append(a)))
    before = len(diagnostics.LOG.entries)

    try:
        raise ValueError("essai de panne")
    except ValueError as exc:
        app_mod._excepthook(type(exc), exc, exc.__traceback__)

    assert len(diagnostics.LOG.entries) == before + 1
    last = diagnostics.LOG.entries[-1]
    assert "ValueError" in last.summary
    assert "essai de panne" in last.summary
    assert "Traceback" in last.detail, "la trace doit être conservée"
    assert shown, "l'utilisateur n'a rien vu"
    assert "Journal" in shown[0][2], shown[0][2]


def test_the_error_hook_survives_a_broken_interface(qapp, monkeypatch):
    """Reporting must not raise in turn, or the report is lost."""
    def refuse(*_args, **_kwargs):
        raise RuntimeError("plus d'interface")

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(refuse))
    try:
        raise ValueError("deuxieme essai")
    except ValueError as exc:
        app_mod._excepthook(type(exc), exc, exc.__traceback__)   # must not raise


# --------------------------------------------------------------------------
# A project given on the command line
# --------------------------------------------------------------------------
def test_a_project_passed_as_an_argument_is_opened(started, tmp_path):
    _, window = started
    project = Project(name="Depuis la ligne de commande")
    project.add_dataset(Dataset("Table", pd.DataFrame({"x": [1.0, 2.0]})))
    path = str(tmp_path / "manip.plotea")
    project.save(path)

    assert app_mod.open_arguments(window, ["plotea", path]) is True
    # the name travels inside the archive, the file name does not overrule it
    assert window.project.name == "Depuis la ligne de commande"
    assert window.project.dataset_names() == ["Table"]
    assert window.project.path == path
    assert "manip" in window.windowTitle(), window.windowTitle()


def test_a_damaged_project_says_so_instead_of_opening_nothing(started,
                                                              tmp_path):
    """It used to be swallowed: an empty window and no explanation."""
    _, window = started
    path = tmp_path / "casse.plotea"
    path.write_text("ceci n'est pas une archive", encoding="utf-8")
    before = len(diagnostics.LOG.entries)

    assert app_mod.open_arguments(window, ["plotea", str(path)]) is False

    assert len(diagnostics.LOG.entries) == before + 1
    assert "casse.plotea" in window.statusBar().currentMessage()
    assert window.project.plots, "la fenêtre doit rester utilisable"


def test_other_arguments_are_left_alone(started):
    _, window = started
    name = window.project.name
    assert app_mod.open_arguments(window, ["plotea", "--debug",
                                           "notes.txt"]) is False
    assert window.project.name == name


# --------------------------------------------------------------------------
# The smoke test the packaged build runs
# --------------------------------------------------------------------------
def test_the_self_test_reports_and_returns(monkeypatch, capsys):
    monkeypatch.setenv("PLOTEA_SELFTEST", "1")
    assert app_mod.main(["plotea"]) == 0
    printed = capsys.readouterr().out
    assert "démarré correctement" in printed
    assert "filtre d'en-tête : actif" in printed
    assert "PERDU" not in printed

    for widget in QApplication.topLevelWidgets():
        if widget.objectName() == "" and widget.isWindow():
            widget.hide()


def test_the_config_folder_can_be_moved(tmp_path, monkeypatch):
    """A portable install, and the reason a test run touches nothing real."""
    from plotea.core.project import config_dir

    monkeypatch.setenv("PLOTEA_CONFIG_DIR", str(tmp_path / "portable"))
    assert config_dir() == str(tmp_path / "portable")
    assert os.path.isdir(config_dir())
