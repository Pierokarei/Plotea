"""Saving never costs the previous file, and earlier versions come back.

A save is all or nothing: written beside the target, forced to the disk,
read back, and only then put in place - so a full disk, a crash, a program
holding the file or a write that went wrong leave the previous file whole.
The hardest case is checked for real: a process saving over and over is
killed at random moments, and the file must always open, as one save or
the other, never half of one.

Each save sets the file it replaces aside: an earlier state can be found
again after it was saved over, even once the file no longer opens.
"""
import json
import os
import subprocess
import sys
import textwrap
import time
import zipfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from plotea.core import project as project_mod
from plotea.core import safefile, versions
from plotea.core.dataset import Dataset
from plotea.core.project import Project


@pytest.fixture(autouse=True)
def own_config(tmp_path, monkeypatch):
    """Each test with its own history, away from the others'."""
    monkeypatch.setenv("PLOTEA_CONFIG_DIR", str(tmp_path / "config"))


def a_project(value=1.0, rows=5) -> Project:
    project = Project(name="Essai")
    project.add_dataset(Dataset("Mesures", pd.DataFrame(
        {"Groupe": ["A", "B"] * rows, "Valeur": [value] * (2 * rows)})))
    return project


def value_in(path) -> float:
    return float(Project.load(path).datasets[0].df["Valeur"].iloc[0])


def leftovers(folder) -> list:
    return [n for n in os.listdir(folder) if n.endswith(".part")]


# --------------------------------------------------------------------------
# All or nothing
# --------------------------------------------------------------------------
def test_a_write_that_fails_leaves_the_previous_file(tmp_path, monkeypatch):
    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)
    project = a_project(2.0)

    def broken(target):
        with open(target, "wb") as handle:
            handle.write(b"PK\x03\x04 half")
        raise OSError("disque plein")
    monkeypatch.setattr(project, "write_to", broken)
    with pytest.raises(OSError, match="disque plein"):
        project.save(path)
    assert value_in(path) == 1.0
    assert not leftovers(tmp_path)


def test_a_file_that_does_not_read_back_is_not_put_in_place(tmp_path,
                                                            monkeypatch):
    """The write went through without an error, yet the archive is not
    the project: the check catches it before the old file is replaced."""
    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)
    project = a_project(2.0)
    real = project.write_to

    def drops_a_table(target):
        real(target)
        with zipfile.ZipFile(target) as archive:
            members = {n: archive.read(n) for n in archive.namelist()}
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("project.json", members["project.json"])
    monkeypatch.setattr(project, "write_to", drops_a_table)
    with pytest.raises(OSError):
        project.save(path)
    assert value_in(path) == 1.0
    assert not leftovers(tmp_path)


def test_a_damaged_archive_is_caught_by_its_checksums(tmp_path, monkeypatch):
    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)
    project = a_project(2.0, rows=500)
    real = project.write_to

    def flips_a_byte(target):
        real(target)
        with open(target, "r+b") as handle:
            data = bytearray(handle.read())
            middle = len(data) // 3
            data[middle] ^= 0xFF
            handle.seek(0)
            handle.write(data)
    monkeypatch.setattr(project, "write_to", flips_a_byte)
    with pytest.raises(Exception):
        project.save(path)
    assert value_in(path) == 1.0


def test_the_content_is_forced_to_the_disk_before_it_replaces(tmp_path,
                                                              monkeypatch):
    synced, replaced = [], []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd),
                                                 real_fsync(fd)))
    monkeypatch.setattr(os, "replace", lambda a, b: (
        replaced.append(len(synced)), real_replace(a, b)))
    a_project().save(str(tmp_path / "p.plotea"))
    assert replaced and replaced[-1] >= 1      # synced before the move


def test_a_file_held_by_another_program_is_waited_for(tmp_path, monkeypatch):
    """An antivirus or OneDrive holding the file for a moment."""
    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)
    real_replace, refusals, waits = os.replace, [2], []

    def busy(src, dst):
        if dst == path and refusals[0]:
            refusals[0] -= 1
            raise PermissionError("fichier utilisé par un autre processus")
        real_replace(src, dst)
    monkeypatch.setattr(os, "replace", busy)
    monkeypatch.setattr(safefile.time, "sleep", waits.append)
    a_project(2.0).save(path)
    assert value_in(path) == 2.0 and len(waits) == 2


def test_a_file_held_just_after_its_save_still_opens(tmp_path, monkeypatch):
    """An antivirus scanning the file it just saw written: Windows refuses
    to open it for a moment. Opening waits, as saving does."""
    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)
    real_open, refusals, waits = safefile._open, [3], []

    def held(name, mode="r", *args, **kwargs):
        if name == path and refusals[0]:
            refusals[0] -= 1
            raise PermissionError("utilisé par un autre processus")
        return real_open(name, mode, *args, **kwargs)
    monkeypatch.setattr(safefile, "_open", held)
    monkeypatch.setattr(safefile.time, "sleep", waits.append)
    assert value_in(path) == 1.0 and len(waits) == 3
    # and a version is still set aside when the file is held
    refusals[0] = 2
    project = Project.load(path)
    project.datasets[0].df["Valeur"] = 2.0
    project.save(path)
    kept = versions.versions(project.uid)
    assert [value_in(v["path"]) for v in kept] == [1.0]


def test_a_read_only_file_is_refused_at_once(tmp_path, monkeypatch):
    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)
    os.chmod(path, 0o444)
    waits = []
    monkeypatch.setattr(safefile.time, "sleep", waits.append)
    try:
        with pytest.raises(PermissionError, match="lecture seule"):
            a_project(2.0).save(path)
        assert not waits
    finally:
        os.chmod(path, 0o666)
    assert value_in(path) == 1.0


def test_temporary_files_left_by_a_crash_are_cleared(tmp_path):
    path = str(tmp_path / "p.plotea")
    old = tmp_path / ".p.plotea.abc123.part"
    old.write_bytes(b"x")
    past = time.time() - 3600
    os.utime(old, (past, past))
    fresh = tmp_path / ".p.plotea.def456.part"     # another save, running
    fresh.write_bytes(b"x")
    a_project().save(path)
    assert not old.exists() and fresh.exists()


@pytest.mark.skipif(os.name == "nt", reason="droits POSIX")
def test_the_file_keeps_its_permissions(tmp_path):
    path = str(tmp_path / "p.plotea")
    a_project().save(path)
    os.chmod(path, 0o640)
    a_project(2.0).save(path)
    assert os.stat(path).st_mode & 0o777 == 0o640


CHILD = textwrap.dedent("""
    import sys
    import pandas as pd
    from plotea.core.dataset import Dataset
    from plotea.core.project import Project
    path = sys.argv[1]
    value = 0
    while True:
        value = 1 - value
        project = Project(name="Boucle")
        project.add_dataset(Dataset("T", pd.DataFrame(
            {"Valeur": [float(value)] * 20000})))
        project.save(path)
        print(value, flush=True)
""")


def test_killed_in_the_middle_of_a_save_the_file_still_opens(tmp_path):
    """A process saving over and over, killed at random moments: the file
    is always one save or the other, never half of one."""
    path = str(tmp_path / "boucle.plotea")
    script = tmp_path / "child.py"
    script.write_text(CHILD, encoding="utf-8")
    env = dict(os.environ, PLOTEA_CONFIG_DIR=str(tmp_path / "config"))
    rng = np.random.default_rng(4)
    for _ in range(8):
        child = subprocess.Popen([sys.executable, str(script), path],
                                 stdout=subprocess.PIPE, env=env,
                                 cwd=os.path.dirname(os.path.dirname(
                                     os.path.abspath(__file__))))
        child.stdout.readline()                 # one save done at least
        time.sleep(float(rng.uniform(0.0, 0.4)))
        child.kill()
        child.wait()
        child.stdout.close()
        reopened = Project.load(path)
        values = set(reopened.datasets[0].df["Valeur"])
        assert values in ({0.0}, {1.0}), values
        assert len(reopened.datasets[0].df) == 20000


# --------------------------------------------------------------------------
# Tables the check must not refuse
# --------------------------------------------------------------------------
@pytest.mark.parametrize("frame", [
    pd.DataFrame(),                                      # every column gone
    pd.DataFrame(index=range(4)),
    pd.DataFrame({"a": pd.Series([], dtype=float)}),     # no row
    pd.DataFrame([[1, 2]], columns=["a", "a"]),          # one name twice
    pd.DataFrame({0: [1.0], 1: ["x"]}),                  # numbers as names
    pd.DataFrame({"t": ["deux\nlignes", 'des "guillemets", et ;']}),
], ids=["vide", "lignes", "sans-ligne", "doublon", "noms-nombres", "texte"])
def test_unusual_tables_save_and_reopen(tmp_path, frame):
    project = Project()
    project.add_dataset(Dataset("Inhabituelle", frame))
    project.add_dataset(Dataset("Suivante", pd.DataFrame({"x": [1.0]})))
    path = project.save(str(tmp_path / "u.plotea"))
    reopened = Project.load(path)
    assert reopened.dataset_names() == ["Inhabituelle", "Suivante"]
    assert len(reopened.datasets[0].df) == (len(frame) if frame.shape[1]
                                            else 0)


def test_presets_and_the_backup_copy_are_written_all_or_nothing(
        tmp_path, monkeypatch):
    project_mod.save_preset("Revue", {"theme": "Nature"})
    project_mod.write_recovery(a_project(1.0))

    def no_disk(path):
        raise OSError("disque plein")
    monkeypatch.setattr(safefile, "sync", no_disk)
    with pytest.raises(OSError):
        project_mod.save_preset("Autre", {"theme": "Cell"})
    with pytest.raises(OSError):
        project_mod.write_recovery(a_project(2.0))
    assert project_mod.load_presets() == {"Revue": {"theme": "Nature"}}
    assert value_in(project_mod.recovery_path()) == 1.0


# --------------------------------------------------------------------------
# Earlier versions
# --------------------------------------------------------------------------
def test_each_save_keeps_the_version_it_replaces(tmp_path):
    path = str(tmp_path / "p.plotea")
    project = a_project(1.0)
    project.save(path)
    assert versions.versions(project.uid) == []     # nothing replaced yet
    project.datasets[0].df["Valeur"] = 2.0
    project.save(path)
    project.datasets[0].df["Valeur"] = 3.0
    project.save(path)
    kept = versions.versions(project.uid)
    assert [value_in(v["path"]) for v in kept] == [2.0, 1.0]
    assert value_in(path) == 3.0
    assert kept[0]["origin"] == os.path.abspath(path)
    assert (kept[0]["tables"], kept[0]["plots"]) == (1, 0)


def test_saving_unchanged_keeps_nothing_twice(tmp_path):
    path = str(tmp_path / "p.plotea")
    project = a_project()
    project.save(path)
    first = open(path, "rb").read()
    for hours in (1, 2, 3):
        project.save(path)
        # the save time inside differs: make the file the same again, as
        # saved at another time
        with open(path, "wb") as handle:
            handle.write(first)
        past = time.time() - hours * 3600
        os.utime(path, (past, past))
    assert len(versions.versions(project.uid)) == 1


def test_the_history_follows_the_project_renamed_or_moved(tmp_path):
    project = a_project(1.0)
    project.save(str(tmp_path / "avant.plotea"))
    moved = tmp_path / "ailleurs"
    moved.mkdir()
    os.replace(tmp_path / "avant.plotea", moved / "apres.plotea")
    reopened = Project.load(str(moved / "apres.plotea"))
    assert reopened.uid == project.uid
    reopened.datasets[0].df["Valeur"] = 2.0
    reopened.save(str(moved / "apres.plotea"))
    (kept,) = versions.versions(project.uid)
    assert value_in(kept["path"]) == 1.0


def test_a_file_from_before_identifiers_is_kept_under_its_project(tmp_path):
    path = str(tmp_path / "ancien.plotea")
    project = a_project(1.0)
    project.save(path)
    with zipfile.ZipFile(path) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    meta = json.loads(members["project.json"])
    del meta["id"]
    members["project.json"] = json.dumps(meta).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    old = Project.load(path)
    assert old.uid != project.uid               # a new one, kept from now on
    old.save(path)
    (kept,) = versions.versions(old.uid)
    assert value_in(kept["path"]) == 1.0
    assert Project.load(path).uid == old.uid


def test_a_version_that_cannot_be_kept_does_not_stop_the_save(tmp_path,
                                                              monkeypatch):
    from plotea.core import diagnostics

    path = str(tmp_path / "p.plotea")
    a_project(1.0).save(path)

    def full(*_args):
        raise OSError("historique plein")
    monkeypatch.setattr(versions, "archive", full)
    before = len(diagnostics.LOG)
    a_project(2.0).save(path)
    assert value_in(path) == 2.0
    assert len(diagnostics.LOG) == before + 1


def fake_versions(project_id, dates, size=1000):
    where = versions.folder(project_id)
    os.makedirs(where, exist_ok=True)
    for i, when in enumerate(dates):
        stem = f"{when.strftime(versions.STAMP)}-{i:08x}"
        with open(os.path.join(where, stem + ".plotea"), "wb") as handle:
            handle.write(b"x" * size)
        with open(os.path.join(where, stem + ".json"), "w") as handle:
            json.dump({"saved": when.isoformat(), "size": size,
                       "sha256": f"{i}"}, handle)


def test_the_last_twenty_then_one_a_day_for_a_month():
    now = datetime(2026, 10, 18, 18, 0)
    # five saves a day for sixty days
    dates = [now - timedelta(days=d, hours=h) for d in range(60)
             for h in (0, 1, 2, 3, 4)]
    fake_versions("p", dates)
    versions.prune("p", now=now)
    kept = [v["saved"] for v in versions.versions("p")]
    newest = sorted(dates, reverse=True)
    assert kept[:20] == newest[:20]
    older = kept[20:]
    assert len({d.date() for d in older}) == len(older)   # one a day
    assert all(now - d <= timedelta(days=30) for d in older)
    days_covered = {d.date() for d in kept}
    assert days_covered == {(now - timedelta(days=d)).date()
                            for d in range(31)}


def test_the_history_never_outgrows_its_cap(monkeypatch):
    monkeypatch.setattr(versions, "MAX_BYTES", 10_000)
    now = datetime(2026, 10, 18, 18, 0)
    fake_versions("p", [now - timedelta(minutes=m) for m in range(30)],
                  size=1000)
    versions.prune("p", now=now)
    kept = versions.versions("p")
    assert sum(v["size"] for v in kept) <= 10_000
    assert kept[0]["saved"] == now                 # the newest stays


def test_versions_of_a_file_that_no_longer_opens(tmp_path):
    path = str(tmp_path / "p.plotea")
    project = a_project(1.0)
    project.save(path)
    project.datasets[0].df["Valeur"] = 2.0
    project.save(path)
    with open(path, "wb") as handle:
        handle.write(b"rien de lisible")
    with pytest.raises(Exception):
        Project.load(path)
    (found,) = versions.versions_of_file(path)
    assert value_in(found["path"]) == 1.0


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
def saved_twice(window, tmp_path):
    path = str(tmp_path / "fenetre.plotea")
    window.project = a_project(1.0)
    window.project.save(path)
    window.project.datasets[0].df["Valeur"] = 2.0
    window.project.save(path)
    window._reload_all(0)
    window.project.dirty = False      # as saved: nothing to ask about
    return path


def test_an_earlier_version_opens_on_screen_without_touching_the_file(
        window, tmp_path, monkeypatch):
    from plotea.ui import dialogs

    path = saved_twice(window, tmp_path)
    shown = []

    def pick_first(dialog):
        shown.append(dialog.table.rowCount())
        dialog.table.selectRow(0)
        dialog._open()
        return 1
    monkeypatch.setattr(dialogs.VersionsDialog, "exec", pick_first)
    window.a_versions.trigger()
    assert shown == [1]
    assert window.project.datasets[0].df["Valeur"].iloc[0] == 1.0
    assert window.project.path == path and window.project.dirty
    assert value_in(path) == 2.0                    # untouched
    # saving it puts it back, and the state it replaces is kept
    assert window.files.save()
    assert value_in(path) == 1.0
    values = {value_in(v["path"])
              for v in versions.versions(window.project.uid)}
    assert values == {1.0, 2.0}
    window.project.dirty = False


def test_a_file_that_no_longer_opens_offers_its_last_version(
        window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from plotea.i18n import tr

    path = saved_twice(window, tmp_path)
    with open(path, "wb") as handle:
        handle.write(b"abime")
    offered = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: offered.append(
        box.informativeText()) or 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: next(
        b for b in box.buttons() if b.text() == tr("Ouvrir cette version")))
    assert window.files.load(path)
    assert offered and "version antérieure" in offered[0]
    assert window.project.datasets[0].df["Valeur"].iloc[0] == 1.0
    assert window.project.path == path and window.project.dirty
    window.project.dirty = False
