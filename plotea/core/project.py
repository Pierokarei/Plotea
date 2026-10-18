"""Project container and .plotea file format.

A .plotea file is a zip archive:
    project.json        metadata + every PlotSpec
    data/<slug>.csv     one CSV per dataset
"""
from __future__ import annotations

import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from ..i18n import tr
from . import diagnostics, safefile, versions
from .dataset import Dataset
from .panel import Panel
from .plotspec import STYLE_FIELDS, PlotSpec

FORMAT_VERSION = 1
EXTENSION = ".plotea"
#: Up to this many values, a save reads every table back before it
#: replaces the previous file.
CHECK_CELLS = 250_000


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return s or "table"


def _kinds(df: pd.DataFrame) -> dict:
    """Which columns hold numbers and which hold text, as written."""
    return {str(c): ("number" if pd.api.types.is_numeric_dtype(df[c])
                     else "text") for c in df.columns}


def _read_table(handle, kinds: dict | None) -> pd.DataFrame:
    """A table as it was saved, not as pandas would guess it.

    Read with pandas' defaults, "NA", "None", "null" or "N/A" became
    missing values - a group of that name vanished from the analysis on
    reopening -, "001" became the number 1 - two subjects "01" and "001"
    one and the same -, and a number could come back a last digit off.
    Texts stay texts, numbers come back exactly, and only an empty cell is
    missing - as it was in the table, where an empty group is no group.
    Files saved before the kinds were recorded are read the same way, the
    kinds guessed.
    """
    text = [name for name, kind in (kinds or {}).items() if kind == "text"]
    try:
        return pd.read_csv(handle, keep_default_na=False, na_values=[""],
                           float_precision="round_trip",
                           dtype={name: str for name in text} or None)
    except pd.errors.EmptyDataError:
        # a table whose every column was deleted is written as an empty
        # file; it used to make the whole project impossible to reopen
        return pd.DataFrame()


@dataclass
class Project:
    name: str = "Projet sans titre"
    datasets: list = field(default_factory=list)      # list[Dataset]
    plots: list = field(default_factory=list)         # list[PlotSpec]
    panels: list = field(default_factory=list)        # list[Panel]
    path: str = ""
    dirty: bool = False
    #: what load() could not read back, for the window to say out loud
    load_warnings: list = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    #: carried by the file, so that its earlier versions follow it when it
    #: is renamed or moved
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)

    # -- dataset helpers ---------------------------------------------------
    def dataset_names(self) -> list[str]:
        return [d.name for d in self.datasets]

    def get_dataset(self, name: str) -> Dataset | None:
        for d in self.datasets:
            if d.name == name:
                return d
        return self.datasets[0] if self.datasets else None

    def add_dataset(self, ds: Dataset) -> Dataset:
        existing = set(self.dataset_names())
        if ds.name in existing:
            i = 2
            while f"{ds.name} ({i})" in existing:
                i += 1
            ds.name = f"{ds.name} ({i})"
        self.datasets.append(ds)
        self.dirty = True
        return ds

    def remove_dataset(self, name: str):
        self.datasets = [d for d in self.datasets if d.name != name]
        self.dirty = True

    # -- plot helpers ------------------------------------------------------
    def plot_names(self) -> list[str]:
        return [p.name for p in self.plots]

    def add_plot(self, spec: PlotSpec) -> PlotSpec:
        existing = set(self.plot_names())
        base = spec.name
        i = 2
        while spec.name in existing:
            spec.name = f"{base} ({i})"
            i += 1
        self.plots.append(spec)
        self.dirty = True
        return spec

    def rename_plot(self, index: int, name: str) -> str:
        """Rename a plot everywhere it is referred to; returns the name kept.

        Composite figures list their plots by name, so renaming only the
        plot made it drop out of every figure it belonged to. A name already
        taken by another plot is made unique, as add_plot does, or two plots
        would answer to it and a figure would show the wrong one.
        """
        if not 0 <= index < len(self.plots):
            return ""
        spec = self.plots[index]
        old = spec.name
        taken = {p.name for i, p in enumerate(self.plots) if i != index}
        new, i = name, 2
        while new in taken:
            new = f"{name} ({i})"
            i += 1
        if new == old:
            return old
        spec.name = new
        for panel in self.panels:
            panel.plots = [new if n == old else n for n in panel.plots]
        self.dirty = True
        return new

    def remove_plot(self, index: int):
        if 0 <= index < len(self.plots):
            removed = self.plots.pop(index)
            for panel in self.panels:
                panel.plots = [n for n in panel.plots if n != removed.name]
            self.dirty = True

    # -- panel helpers -----------------------------------------------------
    def panel_names(self) -> list[str]:
        return [p.name for p in self.panels]

    def add_panel(self, panel: Panel) -> Panel:
        existing = set(self.panel_names())
        base = panel.name
        i = 2
        while panel.name in existing:
            panel.name = f"{base} ({i})"
            i += 1
        self.panels.append(panel)
        self.dirty = True
        return panel

    def remove_panel(self, index: int):
        if 0 <= index < len(self.panels):
            self.panels.pop(index)
            self.dirty = True

    def specs_by_name(self) -> dict:
        return {spec.name: spec for spec in self.plots}

    def frames_by_name(self) -> dict:
        return {ds.name: ds.df for ds in self.datasets}

    # -- persistence -------------------------------------------------------
    def to_json(self) -> dict:
        return {
            "format": FORMAT_VERSION,
            "app": "Plotea",
            "name": self.name,
            "id": self.uid,
            "created": self.created,
            "saved": datetime.now().isoformat(),
            # numbered: two names with the same slug ("Essai 1",
            # "Essai_1") would otherwise write one file over the other
            "datasets": [
                {"name": d.name, "file": f"data/{i:03d}_{_slug(d.name)}.csv",
                 "source": d.source, "sheet": d.sheet, "notes": d.notes,
                 "columns": _kinds(d.df)}
                for i, d in enumerate(self.datasets, start=1)
            ],
            "plots": [p.to_dict() for p in self.plots],
            "panels": [p.to_dict() for p in self.panels],
        }

    def write_to(self, path: str) -> str:
        """Write the archive at `path` without claiming it as our own file.

        Separate from save() because a backup copy must not make the project
        believe it has been saved, nor move it to another file.
        """
        meta = self.to_json()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", json.dumps(meta, indent=2,
                                                   ensure_ascii=False))
            for entry, ds in zip(meta["datasets"], self.datasets):
                zf.writestr(entry["file"],
                            ds.df.to_csv(index=False, encoding="utf-8"))
        return path

    def save(self, path: str) -> str:
        """Write the project, never at the expense of the previous file.

        All or nothing (safefile): written beside the target, forced to
        the disk, read back and checked, and only then moved into place, so
        a full disk, a crash or a power cut leaves the previous file whole.
        The file being replaced is first set aside among the project's
        earlier versions.
        """
        if not path.lower().endswith(EXTENSION):
            path += EXTENSION

        def keep_previous():
            try:
                versions.archive(path, self.uid)
            except Exception as exc:
                # the save is what was asked for: a version that could not
                # be kept is reported, not allowed to stop it
                diagnostics.exception("Version précédente non conservée",
                                      exc)

        safefile.write_atomic(path, self.write_to,
                              verify=lambda partial: self.check(partial),
                              before_replace=keep_previous)
        self.path = path
        self.dirty = False
        return path

    def check(self, path: str):
        """Read an archive back and make sure it holds this project.

        Every member's checksum, the description and every table present;
        then, up to CHECK_CELLS values - nearly every project -, each table
        read back with its number of rows and columns: a file that would
        not reopen as it was saved must not replace one that does. Beyond,
        reading everything again would add half the time of the save.
        """
        with zipfile.ZipFile(path) as archive:
            broken = archive.testzip()
            if broken is not None:
                raise OSError(tr("Archive endommagée à l'écriture : {name}"
                                 ).format(name=broken))
            meta = json.loads(archive.read("project.json").decode("utf-8"))
            members = set(archive.namelist())
        absent = [entry["name"] for entry in meta.get("datasets", [])
                  if entry.get("file") not in members]
        if absent or len(meta.get("datasets", [])) != len(self.datasets):
            raise OSError(tr("Table absente du fichier : {name}").format(
                name=", ".join(absent) or "?"))
        if sum(d.df.size for d in self.datasets) > CHECK_CELLS:
            return
        reopened = Project.load(path)

        def shape(df):
            # a table without columns keeps no rows either
            return df.shape if df.shape[1] else (0, 0)
        wrote = [(d.name, shape(d.df)) for d in reopened.datasets]
        meant = [(d.name, shape(d.df)) for d in self.datasets]
        if wrote != meant or len(reopened.plots) != len(self.plots)                 or len(reopened.panels) != len(self.panels):
            raise OSError(tr("Le fichier écrit ne relit pas le projet tel "
                             "qu'il est : enregistrement annulé."))

    @classmethod
    def load(cls, path: str) -> "Project":
        with safefile.open_read(path) as handle, \
                zipfile.ZipFile(handle) as zf:
            meta = json.loads(zf.read("project.json").decode("utf-8"))
            datasets = []
            missing = []
            for entry in meta.get("datasets", []):
                try:
                    with zf.open(entry["file"]) as fh:
                        df = _read_table(fh, entry.get("columns"))
                except KeyError:
                    # listed but absent: say so rather than open a project
                    # that silently lacks a table
                    missing.append(entry.get("name") or entry.get("file", "?"))
                    continue
                datasets.append(Dataset(entry["name"], df,
                                        entry.get("source", ""),
                                        entry.get("sheet", ""),
                                        entry.get("notes", "")))
        proj = cls(name=meta.get("name", "Projet"), datasets=datasets,
                   plots=[PlotSpec.from_dict(p) for p in meta.get("plots", [])],
                   panels=[Panel.from_dict(p)
                           for p in meta.get("panels", [])],
                   path=path, created=meta.get("created", ""))
        if meta.get("id"):
            proj.uid = str(meta["id"])
        proj.dirty = False
        proj.load_warnings = [
            tr("Table absente du fichier : {name}").format(name=name)
            for name in missing]
        return proj


# --------------------------------------------------------------------------
# Style presets: reusable appearance snapshots, stored next to the config
# --------------------------------------------------------------------------
def extract_style(spec: PlotSpec) -> dict:
    data = spec.to_dict()
    return {k: data[k] for k in STYLE_FIELDS if k in data}


def apply_style(spec: PlotSpec, style: dict) -> PlotSpec:
    for k, v in style.items():
        if k in STYLE_FIELDS and hasattr(spec, k):
            setattr(spec, k, v)
    return spec


def config_dir() -> str:
    """Where preferences, presets and the backup copy live.

    PLOTEA_CONFIG_DIR overrides it, which keeps a test run out of the real
    folder and makes a portable installation possible.
    """
    path = os.environ.get("PLOTEA_CONFIG_DIR") or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~/.config"),
        "Plotea")
    os.makedirs(path, exist_ok=True)
    return path


# --------------------------------------------------------------------------
# Backup copy: what stands between a power cut and an afternoon of work
# --------------------------------------------------------------------------
RECOVERY_NAME = "recuperation" + EXTENSION
RECOVERY_INFO = "recuperation.json"


def recovery_path() -> str:
    return os.path.join(config_dir(), RECOVERY_NAME)


def write_recovery(project: Project) -> str:
    """Snapshot `project` beside the configuration, atomically.

    Written to a temporary name and moved into place, so an interruption
    during the write leaves the previous copy intact rather than half of a
    new one. The project keeps its own path and its modified flag: this is a
    safety net, not a save.
    """
    target = recovery_path()
    safefile.write_atomic(target, project.write_to)
    safefile.write_text(os.path.join(config_dir(), RECOVERY_INFO), json.dumps(
        {"name": project.name, "origin": project.path,
         "saved": datetime.now().isoformat(timespec="seconds")},
        ensure_ascii=False, indent=2))
    return target


def recovery_info() -> dict | None:
    """Describe a backup copy left behind, or None when there is none.

    A copy only survives a session that ended badly: a normal exit, and every
    real save, remove it.
    """
    path = recovery_path()
    if not os.path.exists(path):
        return None
    info = {"name": "Projet", "origin": "", "saved": ""}
    try:
        with open(os.path.join(config_dir(), RECOVERY_INFO),
                  encoding="utf-8") as fh:
            info.update(json.load(fh))
    except (OSError, ValueError):
        pass                       # the archive alone is enough to recover
    info["path"] = path
    return info


def clear_recovery():
    for name in (RECOVERY_NAME, RECOVERY_INFO, RECOVERY_NAME + ".part"):
        try:
            os.remove(os.path.join(config_dir(), name))
        except OSError:
            pass
    safefile.clear_stale(recovery_path(), older_than=0)


def save_preset(name: str, style: dict):
    path = os.path.join(config_dir(), "presets.json")
    presets = load_presets()
    presets[name] = style
    safefile.write_text(path, json.dumps(presets, indent=2,
                                         ensure_ascii=False))


def load_presets() -> dict:
    path = os.path.join(config_dir(), "presets.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def delete_preset(name: str):
    presets = load_presets()
    presets.pop(name, None)
    with open(os.path.join(config_dir(), "presets.json"), "w",
              encoding="utf-8") as fh:
        json.dump(presets, fh, indent=2, ensure_ascii=False)
