"""Project container and .plotea file format.

A .plotea file is a zip archive:
    project.json        metadata + every PlotSpec
    data/<slug>.csv     one CSV per dataset
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from .dataset import Dataset
from .panel import Panel
from .plotspec import PlotSpec

FORMAT_VERSION = 1
EXTENSION = ".plotea"


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return s or "table"


@dataclass
class Project:
    name: str = "Projet sans titre"
    datasets: list = field(default_factory=list)      # list[Dataset]
    plots: list = field(default_factory=list)         # list[PlotSpec]
    panels: list = field(default_factory=list)        # list[Panel]
    path: str = ""
    dirty: bool = False
    created: str = field(default_factory=lambda: datetime.now().isoformat())

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
            "created": self.created,
            "saved": datetime.now().isoformat(),
            "datasets": [
                {"name": d.name, "file": f"data/{_slug(d.name)}.csv",
                 "source": d.source, "sheet": d.sheet, "notes": d.notes}
                for d in self.datasets
            ],
            "plots": [p.to_dict() for p in self.plots],
            "panels": [p.to_dict() for p in self.panels],
        }

    def save(self, path: str) -> str:
        if not path.lower().endswith(EXTENSION):
            path += EXTENSION
        meta = self.to_json()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", json.dumps(meta, indent=2,
                                                   ensure_ascii=False))
            for entry, ds in zip(meta["datasets"], self.datasets):
                zf.writestr(entry["file"],
                            ds.df.to_csv(index=False, encoding="utf-8"))
        self.path = path
        self.dirty = False
        return path

    @classmethod
    def load(cls, path: str) -> "Project":
        with zipfile.ZipFile(path) as zf:
            meta = json.loads(zf.read("project.json").decode("utf-8"))
            datasets = []
            for entry in meta.get("datasets", []):
                try:
                    with zf.open(entry["file"]) as fh:
                        df = pd.read_csv(fh)
                except KeyError:
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
        proj.dirty = False
        return proj


# --------------------------------------------------------------------------
# Style presets: reusable appearance snapshots, stored next to the config
# --------------------------------------------------------------------------
STYLE_FIELDS = [
    "theme", "palette", "span", "width_mm", "height_mm", "line_width",
    "marker", "marker_size", "line_style", "alpha", "fill_alpha",
    "error_type", "error_capsize", "show_points", "point_style",
    "point_alpha", "jitter_width", "bar_width", "bar_edge", "box_width",
    "notch", "violin_inner", "despine", "grid_x", "grid_y", "minor_ticks",
    "show_legend", "legend_loc", "monochrome_hatch", "transparent_bg",
]


def extract_style(spec: PlotSpec) -> dict:
    data = spec.to_dict()
    return {k: data[k] for k in STYLE_FIELDS if k in data}


def apply_style(spec: PlotSpec, style: dict) -> PlotSpec:
    for k, v in style.items():
        if k in STYLE_FIELDS and hasattr(spec, k):
            setattr(spec, k, v)
    return spec


def config_dir() -> str:
    base = (os.environ.get("APPDATA")
            or os.path.expanduser("~/.config"))
    path = os.path.join(base, "Plotea")
    os.makedirs(path, exist_ok=True)
    return path


def save_preset(name: str, style: dict):
    path = os.path.join(config_dir(), "presets.json")
    presets = load_presets()
    presets[name] = style
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(presets, fh, indent=2, ensure_ascii=False)


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
