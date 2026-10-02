"""Opening and saving: the paths where a mistake costs someone's work."""
import os
import zipfile

import pandas as pd
import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from plotea.core import diagnostics
from plotea.core import project as project_mod
from plotea.core.dataset import Dataset
from plotea.core.project import Project


class Exploding(pd.DataFrame):
    """A table whose serialisation fails, the way a full disk would."""

    def to_csv(self, *args, **kwargs):
        raise OSError("plus de place sur le disque")


def two_tables(tmp_path) -> str:
    project = Project(name="Thèse")
    project.add_dataset(Dataset("Manip 1", pd.DataFrame({"x": [1.0, 2.0]})))
    project.add_dataset(Dataset("Manip 2", pd.DataFrame({"y": [7.0, 8.0]})))
    path = str(tmp_path / "these.plotea")
    project.save(path)
    return path


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------
def test_a_failed_save_leaves_the_previous_file_intact(tmp_path):
    """It used to empty the file: two tables before, none after."""
    path = two_tables(tmp_path)
    later = Project.load(path)
    later.datasets[0].df = Exploding(later.datasets[0].df)

    with pytest.raises(OSError):
        later.save(path)

    assert Project.load(path).dataset_names() == ["Manip 1", "Manip 2"]
    assert os.listdir(tmp_path) == ["these.plotea"], "fichier partiel laissé"


def test_a_failed_save_does_not_claim_success(tmp_path):
    path = two_tables(tmp_path)
    later = Project.load(path)
    later.dirty = True
    later.datasets[0].df = Exploding(later.datasets[0].df)
    with pytest.raises(OSError):
        later.save(str(tmp_path / "ailleurs.plotea"))
    assert later.dirty is True
    assert later.path == path, "le projet se croit enregistré ailleurs"


def test_a_table_missing_from_the_file_is_reported(tmp_path):
    """Listed in project.json but absent: say so, do not open it quietly."""
    path = two_tables(tmp_path)
    damaged = str(tmp_path / "abime.plotea")
    with zipfile.ZipFile(path) as source, \
            zipfile.ZipFile(damaged, "w") as target:
        for item in source.infolist():
            if "Manip_2" not in item.filename:
                target.writestr(item, source.read(item.filename))

    project = Project.load(damaged)
    assert project.dataset_names() == ["Manip 1"]
    assert project.load_warnings == ["Table absente du fichier : Manip 2"]


def test_a_sound_file_has_nothing_to_report(tmp_path):
    assert Project.load(two_tables(tmp_path)).load_warnings == []


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
def test_opening_a_project_through_the_dialog(window, tmp_path, monkeypatch):
    path = two_tables(tmp_path)
    window.project.dirty = False
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (path, "")))

    window.open_project()

    assert window.project.dataset_names() == ["Manip 1", "Manip 2"]
    assert window.project.plots, "un projet sans graphique est inutilisable"
    assert window.recent_projects()[0] == os.path.abspath(path)
    assert "Projet ouvert" in window.statusBar().currentMessage()


def test_opening_nothing_changes_nothing(window, monkeypatch):
    name = window.project.name
    window.project.dirty = False
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    window.open_project()
    assert window.project.name == name


def test_an_incomplete_project_opens_and_says_so(window, tmp_path):
    path = two_tables(tmp_path)
    damaged = str(tmp_path / "abime.plotea")
    with zipfile.ZipFile(path) as source, \
            zipfile.ZipFile(damaged, "w") as target:
        for item in source.infolist():
            if "Manip_2" not in item.filename:
                target.writestr(item, source.read(item.filename))
    before = len(diagnostics.LOG.entries)

    assert window.load_project(damaged) is True

    assert "incomplet" in window.statusBar().currentMessage()
    assert "Manip 2" in window.statusBar().currentMessage()
    assert len(diagnostics.LOG.entries) == before + 1


def test_an_unreadable_project_is_reported_and_forgotten(window, tmp_path,
                                                         monkeypatch):
    broken = tmp_path / "casse.plotea"
    broken.write_text("pas une archive", encoding="utf-8")
    window.memory.remember_project(str(broken))
    shown = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: shown.append(a)))

    assert window.load_project(str(broken)) is False
    assert shown
    assert str(broken) not in window.recent_projects()


def test_saving_a_new_project_asks_where(window, tmp_path, monkeypatch):
    target = str(tmp_path / "Manip du jeudi.plotea")
    window.project.path = ""
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (target, "")))

    window.save_project()

    assert os.path.exists(target)
    assert window.project.path == target
    assert window.project.name == "Manip du jeudi"
    assert window.project.dirty is False
    assert "*" not in window.windowTitle()


def test_a_cancelled_save_as_changes_nothing(window, monkeypatch):
    window.project.path = ""
    name = window.project.name
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    assert window.files.save_as() is False
    assert window.project.name == name
    assert window.project.path == ""


def test_a_failed_save_as_keeps_the_project_where_it_was(window, tmp_path,
                                                         monkeypatch):
    """The project used to adopt the new name and path before anything was
    written, and then pointed to a file that did not exist."""
    window.project.path = ""
    name = window.project.name
    window.project.datasets[0].df = Exploding(window.project.datasets[0].df)
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (
                            str(tmp_path / "nouveau.plotea"), "")))
    shown = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: shown.append(a)))

    assert window.files.save_as() is False

    assert window.project.path == ""
    assert window.project.name == name
    assert not os.path.exists(tmp_path / "nouveau.plotea")
    assert shown and "intact" in shown[0][2]


def test_a_failed_save_keeps_the_previous_file(window, tmp_path, monkeypatch):
    path = two_tables(tmp_path)
    window.load_project(path)
    window.project.datasets[0].df = Exploding(window.project.datasets[0].df)
    window.project.dirty = True
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: None))

    assert window.files.save() is False

    assert Project.load(path).dataset_names() == ["Manip 1", "Manip 2"]
    assert window.project.dirty is True, "un échec ne vaut pas enregistrement"


def test_a_new_project_without_the_example(window):
    window.project.dirty = False
    window.new_project()
    assert len(window.project.datasets) == 1
    assert window.project.plots[0].name == "Graphique 1"
    assert window.project.datasets[0].df.empty or \
        window.project.datasets[0].df.isna().all().all()


def test_the_title_shows_unsaved_work(window):
    window.project.dirty = True
    window.files.update_title()
    assert window.windowTitle().endswith("*")
    window.project.dirty = False
    window.files.update_title()
    assert not window.windowTitle().endswith("*")


def test_saving_drops_the_backup_copy(window, tmp_path):
    window.project.dirty = True
    window.autosave()
    assert project_mod.recovery_info() is not None
    window.project.path = str(tmp_path / "vrai.plotea")
    assert window.files.save() is True
    assert project_mod.recovery_info() is None
