"""Multi-panel figures: several plots laid out on one publication figure.

A Panel references existing plots by name and arranges them on a grid, with
the A/B/C lettering journals expect. Each sub-plot keeps its own theme, so a
composite figure can mix a dose-response curve and a bar chart.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import matplotlib as mpl

from . import plotting
from .enums import PANEL_FIELDS, PANEL_LETTERS, SPAN
from .themes import MM, get_theme

LETTER_STYLES = PANEL_LETTERS.keys()
SPANS = SPAN.keys()


def letter_for(index: int, style: str) -> str:
    style = PANEL_LETTERS.normalise(style)
    base = chr(ord("A") + index % 26)
    if style == "lower":
        return base.lower()
    if style == "paren":
        return f"({base.lower()})"
    return base


@dataclass
class Panel:
    """A grid of plots rendered as a single figure."""

    name: str = "Figure 1"
    plots: list = field(default_factory=list)      # plot names, in order
    rows: int = 0                                  # 0 -> deduced from cols
    cols: int = 2
    span: str = "double"
    width_mm: float = 183.0
    height_mm: float = 120.0
    letters: str = "upper"
    letter_size: float = 9.0
    wspace: float = 0.28
    hspace: float = 0.32
    theme: str = "Nature"                          # geometry reference
    share_x: bool = False
    share_y: bool = False
    notes: str = ""

    def __setattr__(self, name, value):
        enum = PANEL_FIELDS.get(name)
        if enum is not None and isinstance(value, str):
            value = enum.normalise(value)
        object.__setattr__(self, name, value)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Panel":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def grid(self, count: int) -> tuple[int, int]:
        cols = max(int(self.cols), 1)
        rows = int(self.rows) or max(math.ceil(count / cols), 1)
        return rows, cols

    def size_mm(self) -> tuple[float, float]:
        if self.span == "custom":
            return self.width_mm, self.height_mm
        theme = get_theme(self.theme)
        width_in, _ = theme.figsize(self.span)
        width = width_in / MM
        return width, self.height_mm


@dataclass
class PanelInfo:
    warnings: list = field(default_factory=list)
    drawn: int = 0
    missing: list = field(default_factory=list)


def render_panel(fig, panel: Panel, specs: dict, frames: dict) -> PanelInfo:
    """Draw `panel` onto `fig`.

    `specs` maps a plot name to its PlotSpec, `frames` a dataset name to its
    DataFrame. Missing plots are reported rather than silently skipped.
    """
    info = PanelInfo()
    fig.clear()
    chosen = []
    for name in panel.plots:
        if name in specs:
            chosen.append(specs[name])
        else:
            info.missing.append(name)
    if info.missing:
        info.warnings.append(
            "Graphique(s) introuvable(s) : " + ", ".join(info.missing))

    if not chosen:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Ajoutez des graphiques a cette figure",
                ha="center", va="center", transform=ax.transAxes,
                color="#999999")
        ax.set_axis_off()
        return info

    rows, cols = panel.grid(len(chosen))
    try:
        fig.set_layout_engine("constrained", wspace=panel.wspace,
                              hspace=panel.hspace)
    except Exception:
        pass
    gs = fig.add_gridspec(rows, cols)

    first = None
    for index, spec in enumerate(chosen):
        row, col = divmod(index, cols)
        if row >= rows:
            info.warnings.append(
                f"La grille {rows}x{cols} ne peut pas contenir "
                f"{len(chosen)} graphiques.")
            break
        theme = get_theme(spec.theme)
        with mpl.rc_context(theme.rc()):
            shared = {}
            if first is not None:
                if panel.share_x:
                    shared["sharex"] = first
                if panel.share_y:
                    shared["sharey"] = first
            ax = fig.add_subplot(gs[row, col], **shared)
            first = first or ax
            sub = plotting.draw_into(ax, spec, frames.get(spec.dataset))
            info.warnings.extend(sub.warnings)
            if panel.letters != "none":
                ax.set_title(letter_for(index, panel.letters), loc="left",
                             fontweight="bold", fontsize=panel.letter_size)
            info.drawn += 1
    return info
