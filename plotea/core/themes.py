"""Journal themes: rcParams presets + qualitative palettes.

Each theme mirrors the typography and figure geometry expected by the
corresponding journal family. Widths are stored in millimetres because that is
how instructions-to-authors specify them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MM = 1.0 / 25.4  # mm -> inch


# --------------------------------------------------------------------------
# Qualitative palettes (colour-blind aware, journal-flavoured)
# --------------------------------------------------------------------------
PALETTES: dict[str, list[str]] = {
    "Nature (NPG)": [
        "#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F",
        "#8491B4", "#91D1C2", "#DC0000", "#7E6148", "#B09C85",
    ],
    "Science (AAAS)": [
        "#3B4992", "#EE0000", "#008B45", "#631879", "#008280",
        "#BB0021", "#5F559B", "#A20056", "#808180", "#1B1919",
    ],
    "Cell Press": [
        "#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F",
        "#FDAF91", "#AD002A", "#ADB6B6", "#1B1919", "#00A087",
    ],
    "PNAS (NEJM)": [
        "#BC3C29", "#0072B5", "#E18727", "#20854E", "#7876B1",
        "#6F99AD", "#EE4C97", "#FFDC91", "#4A6990", "#8C564B",
    ],
    "Okabe-Ito (CB-safe)": [
        "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
        "#56B4E9", "#F0E442", "#000000", "#999999", "#7570B3",
    ],
    "Viridis discrete": [
        "#440154", "#472D7B", "#3B528B", "#2C728E", "#21908C",
        "#27AD81", "#5DC863", "#AADC32", "#FDE725", "#B8DE29",
    ],
    "Grayscale": [
        "#1A1A1A", "#4D4D4D", "#808080", "#B3B3B3", "#D9D9D9",
        "#333333", "#666666", "#999999", "#CCCCCC", "#E6E6E6",
    ],
    "Warm": [
        "#B2182B", "#D6604D", "#F4A582", "#FDDBC7", "#E08214",
        "#B35806", "#8C510A", "#DFC27D", "#A6611A", "#543005",
    ],
    "Cool": [
        "#053061", "#2166AC", "#4393C3", "#92C5DE", "#D1E5F0",
        "#01665E", "#35978F", "#80CDC1", "#5AAE61", "#1B7837",
    ],
}

#: Colormaps offered for continuous colour mapping.
COLORMAPS = [
    "viridis", "magma", "cividis", "plasma", "inferno",
    "RdBu_r", "coolwarm", "Blues", "Reds", "Greys",
]


@dataclass
class Theme:
    """A publication style: typography, geometry and default palette."""

    name: str
    description: str
    font_family: list[str]
    base_size: float               # pt, used for tick labels
    palette: str
    col1_mm: float                 # single-column width
    col2_mm: float                 # double-column width
    default_height_ratio: float = 0.78
    linewidth: float = 0.8
    spine_width: float = 0.8
    tick_direction: str = "out"
    tick_size: float = 3.0
    top_right_spines: bool = False
    grid: bool = False
    marker_size: float = 4.0
    capsize: float = 2.0
    extra: dict = field(default_factory=dict)

    # -- derived -----------------------------------------------------------
    def figsize(self, span: str = "single", height_mm: float | None = None):
        width_mm = self.col1_mm if span == "single" else self.col2_mm
        h = height_mm if height_mm else width_mm * self.default_height_ratio
        return (width_mm * MM, h * MM)

    def rc(self) -> dict:
        """Return the matplotlib rcParams dict for this theme."""
        s = self.base_size
        rc = {
            "font.family": "sans-serif",
            "font.sans-serif": self.font_family,
            "font.size": s,
            "axes.labelsize": s + 1,
            "axes.titlesize": s + 1,
            "axes.titleweight": "bold",
            "axes.labelweight": "normal",
            "xtick.labelsize": s,
            "ytick.labelsize": s,
            "legend.fontsize": s,
            "legend.title_fontsize": s,
            "figure.titlesize": s + 2,

            "axes.linewidth": self.spine_width,
            "axes.spines.top": self.top_right_spines,
            "axes.spines.right": self.top_right_spines,
            "axes.axisbelow": True,
            "axes.grid": self.grid,
            "grid.linewidth": self.spine_width * 0.6,
            "grid.color": "#D9D9D9",
            "grid.alpha": 0.9,

            "lines.linewidth": self.linewidth,
            "lines.markersize": self.marker_size,
            "lines.markeredgewidth": self.linewidth * 0.8,
            "patch.linewidth": self.spine_width,

            "xtick.direction": self.tick_direction,
            "ytick.direction": self.tick_direction,
            "xtick.major.width": self.spine_width,
            "ytick.major.width": self.spine_width,
            "xtick.minor.width": self.spine_width * 0.7,
            "ytick.minor.width": self.spine_width * 0.7,
            "xtick.major.size": self.tick_size,
            "ytick.major.size": self.tick_size,
            "xtick.minor.size": self.tick_size * 0.6,
            "ytick.minor.size": self.tick_size * 0.6,

            "legend.frameon": False,
            "legend.handlelength": 1.4,
            "legend.handletextpad": 0.5,
            "legend.columnspacing": 1.0,
            "legend.labelspacing": 0.35,

            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.pad_inches": 0.02,
            "svg.fonttype": "none",       # keep text editable in Illustrator
            "pdf.fonttype": 42,           # TrueType, editable text
            "ps.fonttype": 42,
            "errorbar.capsize": self.capsize,
        }
        rc.update(self.extra)
        return rc


THEMES: dict[str, Theme] = {
    "Nature": Theme(
        name="Nature",
        description="Helvetica 7 pt - colonne 89 mm - traits fins, ticks sortants",
        font_family=["Helvetica", "Arial", "Nimbus Sans", "DejaVu Sans"],
        base_size=7.0,
        palette="Nature (NPG)",
        col1_mm=89.0,
        col2_mm=183.0,
        linewidth=0.75,
        spine_width=0.6,
        tick_direction="out",
        tick_size=2.5,
        marker_size=3.5,
        capsize=1.8,
    ),
    "Science": Theme(
        name="Science",
        description="Helvetica 8 pt - colonne 55 mm - ticks rentrants",
        font_family=["Helvetica", "Arial", "Nimbus Sans", "DejaVu Sans"],
        base_size=8.0,
        palette="Science (AAAS)",
        col1_mm=55.0,
        col2_mm=120.0,
        default_height_ratio=0.85,
        linewidth=0.9,
        spine_width=0.75,
        tick_direction="in",
        tick_size=3.0,
        marker_size=4.0,
    ),
    "Cell": Theme(
        name="Cell",
        description="Arial 8 pt - colonne 85 mm - traits moyens, style Cell Press",
        font_family=["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
        base_size=8.0,
        palette="Cell Press",
        col1_mm=85.0,
        col2_mm=174.0,
        linewidth=1.0,
        spine_width=0.8,
        tick_direction="out",
        tick_size=3.0,
        marker_size=4.5,
        capsize=2.2,
    ),
    "PNAS": Theme(
        name="PNAS",
        description="Helvetica 8 pt - colonne 87 mm - axes sobres",
        font_family=["Helvetica", "Arial", "Nimbus Sans", "DejaVu Sans"],
        base_size=8.0,
        palette="PNAS (NEJM)",
        col1_mm=87.0,
        col2_mm=178.0,
        linewidth=0.9,
        spine_width=0.7,
        tick_direction="out",
        tick_size=2.8,
        marker_size=4.0,
    ),
    "Minimal": Theme(
        name="Minimal",
        description="Sans-serif 9 pt - axes epures, grille horizontale legere",
        font_family=["Inter", "Helvetica", "Arial", "DejaVu Sans"],
        base_size=9.0,
        palette="Okabe-Ito (CB-safe)",
        col1_mm=100.0,
        col2_mm=190.0,
        linewidth=1.2,
        spine_width=0.8,
        tick_direction="out",
        grid=True,
        marker_size=5.0,
        extra={"grid.linestyle": "-"},
    ),
    "Grayscale": Theme(
        name="Grayscale",
        description="Noir & blanc - impression monochrome / daltonisme",
        font_family=["Helvetica", "Arial", "DejaVu Sans"],
        base_size=8.0,
        palette="Grayscale",
        col1_mm=89.0,
        col2_mm=183.0,
        linewidth=0.9,
        spine_width=0.8,
        tick_direction="out",
    ),
}

DEFAULT_THEME = "Nature"

#: Hatch patterns proposed for monochrome-safe bar charts.
HATCHES = ["", "///", "\\\\\\", "xxx", "...", "+++", "ooo", "***"]

#: Marker cycle used when a series needs a distinct symbol.
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "<", ">", "*"]

#: Line style cycle.
LINESTYLES = ["-", "--", "-.", ":", (0, (3, 1, 1, 1))]


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def get_palette(name: str) -> list[str]:
    return PALETTES.get(name, PALETTES["Nature (NPG)"])


def color_cycle(palette: str, n: int) -> list[str]:
    cols = get_palette(palette)
    return [cols[i % len(cols)] for i in range(max(n, 0))]
