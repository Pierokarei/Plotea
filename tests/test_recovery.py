"""Losing work: the backup copy, the guarded discards, the recent list."""
import os

from plotea.core import project as project_mod
from plotea.core.dataset import Dataset
from plotea.core.project import Project


def a_project(tmp_path) -> Project:
    import pandas as pd

    project = Project(name="Essai")
    project.add_dataset(Dataset("Table", pd.DataFrame({"x": [1, 2, 3],
                                                       "y": [4.0, 5.0, 6.0]})))
    project.path = str(tmp_path / "essai.plotea")
    project.dirty = True
    return project


# --------------------------------------------------------------------------
# The copy itself
# --------------------------------------------------------------------------
def test_backup_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PLOTEA_CONFIG_DIR", str(tmp_path / "config"))
    project = a_project(tmp_path)

    assert project_mod.recovery_info() is None, "rien ne doit exister au depart"
    project_mod.write_recovery(project)

    info = project_mod.recovery_info()
    assert info is not None
    assert info["name"] == "Essai"
    assert info["origin"] == project.path
    assert info["saved"]
    assert os.path.exists(info["path"])

    reopened = Project.load(info["path"])
    assert reopened.dataset_names() == ["Table"]
    assert list(reopened.datasets[0].df["y"]) == [4.0, 5.0, 6.0]

    project_mod.clear_recovery()
    assert project_mod.recovery_info() is None


def test_backup_is_not_a_save(tmp_path, monkeypatch):
    """The project must not believe it now lives beside the configuration."""
    monkeypatch.setenv("PLOTEA_CONFIG_DIR", str(tmp_path / "config"))
    project = a_project(tmp_path)
    before = project.path

    project_mod.write_recovery(project)

    assert project.path == before, "le projet a change de fichier"
    assert project.dirty is True, "le projet se croit enregistre"
    assert not os.path.exists(before), "aucun fichier reel ne doit apparaitre"


def test_backup_leaves_no_partial_file(tmp_path, monkeypatch):
    """Written aside and moved into place, so an interruption costs nothing."""
    monkeypatch.setenv("PLOTEA_CONFIG_DIR", str(tmp_path / "config"))
    project = a_project(tmp_path)
    project_mod.write_recovery(project)
    project_mod.write_recovery(project)      # twice: the move must overwrite

    left = os.listdir(project_mod.config_dir())
    assert not [n for n in left if n.endswith(".part")], left


def test_a_config_folder_of_our_own(tmp_path, monkeypatch):
    """Tests and portable installs must not write into the real folder."""
    monkeypatch.setenv("PLOTEA_CONFIG_DIR", str(tmp_path / "ailleurs"))
    assert project_mod.config_dir() == str(tmp_path / "ailleurs")
    assert os.path.isdir(project_mod.config_dir())


# --------------------------------------------------------------------------
# The window around it
# --------------------------------------------------------------------------
def test_autosave_only_writes_when_something_changed(window):
    project_mod.clear_recovery()
    window.project.dirty = False
    assert window.autosave() is False
    assert project_mod.recovery_info() is None

    window.project.dirty = True
    assert window.autosave() is True
    assert project_mod.recovery_info() is not None
    project_mod.clear_recovery()


def test_autosave_survives_a_broken_folder(window, monkeypatch):
    """A full disk must not take the application down with it."""
    def refuse(_project):
        raise OSError("disque plein")

    monkeypatch.setattr(project_mod, "write_recovery", refuse)
    window.project.dirty = True
    assert window.autosave() is False          # reported, not raised
    assert window._autosave_warned is True


def test_the_timer_runs(window):
    from plotea.ui.main_window import AUTOSAVE_MS

    assert window._autosave_timer.isActive()
    assert window._autosave_timer.interval() == AUTOSAVE_MS


def test_recovered_work_is_still_unsaved(window, tmp_path):
    """Recovering is not saving: the copy came from a session that crashed."""
    project = a_project(tmp_path)
    project.name = "Manip du jeudi"
    project_mod.write_recovery(project)
    info = project_mod.recovery_info()

    assert window.restore_recovery(info) is True
    assert window.project.name == "Manip du jeudi"
    assert window.project.dataset_names() == ["Table"]
    # it belongs to the file it came from, not to the copy
    assert window.project.path == project.path
    assert window.project.dirty is True, "l'utilisateur doit encore enregistrer"
    assert "*" in window.windowTitle()
    project_mod.clear_recovery()


def test_an_unreadable_copy_is_reported_not_raised(window, tmp_path):
    broken = tmp_path / "casse.plotea"
    broken.write_text("ceci n'est pas une archive", encoding="utf-8")
    assert window.restore_recovery({"path": str(broken)}) is False


def test_saving_drops_the_copy(window, tmp_path):
    window.project.dirty = True
    window.autosave()
    assert project_mod.recovery_info() is not None

    window.project.path = str(tmp_path / "vrai.plotea")
    window.save_project()

    assert os.path.exists(window.project.path)
    assert project_mod.recovery_info() is None, "la copie survit a un vrai save"


# --------------------------------------------------------------------------
# The two paths that used to discard without asking
# --------------------------------------------------------------------------
def test_new_project_asks_first(window, monkeypatch):
    asked = []
    monkeypatch.setattr(type(window), "_ask_to_keep_changes",
                        lambda self: asked.append(True) or False)
    window.project.name = "A garder"
    window.new_project()
    assert asked, "Ctrl+N n'a pas demande"
    assert window.project.name == "A garder", "le projet a ete remplace"


def test_open_asks_first(window, monkeypatch):
    monkeypatch.setattr(type(window), "_ask_to_keep_changes",
                        lambda self: False)
    called = []
    monkeypatch.setattr(type(window), "load_project",
                        lambda self, path: called.append(path))
    window.open_project()
    assert not called, "un projet a ete ouvert malgre le refus"


def test_a_clean_project_asks_nothing(window):
    """No dialog when there is nothing to lose."""
    window.project.dirty = False
    assert window._ask_to_keep_changes() is True


# --------------------------------------------------------------------------
# Recent projects
# --------------------------------------------------------------------------
def test_recent_projects_are_ordered_and_capped(window, tmp_path):
    window.settings.setValue("recentProjects", [])
    paths = []
    for i in range(window.RECENT_MAX + 3):
        path = tmp_path / f"projet{i}.plotea"
        path.write_text("x", encoding="utf-8")
        paths.append(str(path))
        window._remember_project(str(path))

    recent = window.recent_projects()
    assert len(recent) == window.RECENT_MAX
    assert recent[0] == os.path.abspath(paths[-1]), "le dernier doit etre 1er"

    # opening one again moves it back to the top instead of duplicating it
    window._remember_project(paths[-3])
    recent = window.recent_projects()
    assert recent[0] == os.path.abspath(paths[-3])
    assert len(recent) == len(set(os.path.normcase(p) for p in recent))


def test_the_menu_skips_what_has_been_deleted(window, tmp_path):
    alive = tmp_path / "vivant.plotea"
    alive.write_text("x", encoding="utf-8")
    window.settings.setValue(
        "recentProjects", [str(alive), str(tmp_path / "efface.plotea")])

    window._fill_recent()
    labels = [a.text() for a in window.m_recent.actions() if a.isEnabled()]
    assert "vivant.plotea" in labels
    assert "efface.plotea" not in labels


def test_an_empty_list_says_so(window):
    window.settings.setValue("recentProjects", [])
    window._fill_recent()
    actions = window.m_recent.actions()
    assert len(actions) == 1
    assert not actions[0].isEnabled()


def test_a_project_that_no_longer_opens_is_forgotten(window, tmp_path):
    broken = tmp_path / "casse.plotea"
    broken.write_text("pas une archive", encoding="utf-8")
    window.settings.setValue("recentProjects", [str(broken)])

    import pytest
    from PyQt6.QtWidgets import QMessageBox

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(QMessageBox, "critical",
                      staticmethod(lambda *a, **k: None))
        assert window.load_project(str(broken)) is False

    assert window.recent_projects() == []


# --------------------------------------------------------------------------
# The offer made at startup
# --------------------------------------------------------------------------
def click_button(text: str):
    """Answer the next message box by pressing the button named `text`."""
    def fake_exec(box):
        for button in box.buttons():
            if button.text().replace("&", "") == text:
                button.click()
                return 0
        raise AssertionError(f"bouton absent : {text} "
                             f"({[b.text() for b in box.buttons()]})")
    return fake_exec


def test_startup_offers_the_copy(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from plotea.app import offer_recovery

    project = a_project(tmp_path)
    project.name = "Manip interrompue"
    project_mod.write_recovery(project)

    monkeypatch.setattr(QMessageBox, "exec", click_button("Récupérer"))
    assert offer_recovery(window) is True
    assert window.project.name == "Manip interrompue"
    project_mod.clear_recovery()


def test_startup_says_nothing_without_a_copy(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from plotea.app import offer_recovery

    project_mod.clear_recovery()
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box: (_ for _ in ()).throw(
                            AssertionError("dialogue affiche sans copie")))
    assert offer_recovery(window) is False


def test_declining_removes_the_copy(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from plotea.app import offer_recovery

    project_mod.write_recovery(a_project(tmp_path))
    monkeypatch.setattr(QMessageBox, "exec",
                        click_button("Supprimer la copie"))
    assert offer_recovery(window) is False
    assert project_mod.recovery_info() is None


def test_the_timer_actually_writes(window):
    """Not just connected in principle: let it fire and check the file.

    The interval is lowered for the test only; what matters is that the
    timeout reaches autosave and that autosave reaches the disk.
    """
    from PyQt6.QtCore import QEventLoop, QTimer

    project_mod.clear_recovery()
    window.project.dirty = True
    window._autosave_timer.setInterval(120)

    loop = QEventLoop()
    QTimer.singleShot(1200, loop.quit)
    loop.exec()

    window._autosave_timer.setInterval(120_000)
    assert project_mod.recovery_info() is not None, "le minuteur n'a rien ecrit"
    project_mod.clear_recovery()
