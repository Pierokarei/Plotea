"""PlotSpec: the serialisable description of one figure.

Everything the renderer needs lives here, so a project file is just a list of
PlotSpecs plus the datasets. Nothing in this module imports matplotlib.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .enums import PLOT_TYPE, SPEC_FIELDS

#: Kept for convenience: plot type key -> label shown in the interface.
PLOT_TYPES = {choice.key: choice.label for choice in PLOT_TYPE}


@dataclass
class Annotation:
    """A free text label placed in axes-fraction coordinates."""
    text: str = ""
    x: float = 0.5
    y: float = 0.95
    size: float = 8.0
    color: str = "#000000"
    ha: str = "center"
    bold: bool = False
    italic: bool = False


@dataclass
class PlotSpec:
    # -- identity ----------------------------------------------------------
    name: str = "Graphique 1"
    plot_type: str = "bar"
    dataset: str = ""

    # -- data mapping ------------------------------------------------------
    x: str = ""                       # X column (line/scatter) or category
    y: list[str] = field(default_factory=list)   # one or more value columns
    group: str = ""                   # long format: grouping column
    subgroup: str = ""                # second factor -> grouped bars/boxes
    error_cols: list[str] = field(default_factory=list)  # explicit error cols

    # -- style -------------------------------------------------------------
    theme: str = "Nature"
    palette: str = ""                 # empty -> theme default
    custom_colors: dict = field(default_factory=dict)   # series -> hex
    span: str = "single"
    width_mm: float = 89.0
    height_mm: float = 69.0
    transparent_bg: bool = False
    monochrome_hatch: bool = False

    # -- labels ------------------------------------------------------------
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    legend_title: str = ""
    show_legend: bool = True
    legend_loc: str = "best"
    legend_ncol: int = 1
    annotations: list = field(default_factory=list)

    # -- axes --------------------------------------------------------------
    xmin: float | None = None
    xmax: float | None = None
    ymin: float | None = None
    ymax: float | None = None
    log_x: bool = False
    log_y: bool = False
    grid_x: bool = False
    grid_y: bool = False
    minor_ticks: bool = False
    despine: bool = True
    tick_rotation: float = 0.0
    y_from_zero: bool = True          # bar charts anchored at zero

    # -- series appearance -------------------------------------------------
    line_width: float = 0.0           # 0 -> theme default
    marker: str = "o"
    marker_size: float = 0.0          # 0 -> theme default
    line_style: str = "-"
    show_markers: bool = True
    show_line: bool = True
    alpha: float = 1.0
    fill_alpha: float = 0.18
    error_band: bool = False          # shaded band instead of error bars
    connect_means: bool = False       # line joining group means (bar/box)

    # -- error -------------------------------------------------------------
    error_type: str = "sem"
    error_capsize: float = 0.0        # 0 -> theme default
    error_direction: str = "both"

    # -- distribution options ---------------------------------------------
    bins: int = 20
    bins_auto: bool = True
    hist_stat: str = "count"
    hist_cumulative: bool = False
    hist_kde: bool = False
    hist_step: bool = False

    box_width: float = 0.6
    notch: bool = False
    show_outliers: bool = True
    violin_inner: str = "box"
    violin_bw: float = 0.0            # 0 -> scott
    violin_side: str = "both"

    bar_width: float = 0.7
    bar_edge: bool = True
    horizontal: bool = False

    # -- individual points overlay ----------------------------------------
    show_points: bool = True
    point_style: str = "jitter"
    point_size: float = 0.0
    point_alpha: float = 0.85
    jitter_width: float = 0.12
    point_edge: bool = True

    # -- fitting -----------------------------------------------------------
    fit_model: str = "none"
    fit_ci: bool = False
    fit_show_equation: bool = True
    fit_extrapolate: bool = False
    fit_equation_loc: str = "top left"

    # -- statistics --------------------------------------------------------
    stats_enabled: bool = False
    stats_test: str = "auto"
    stats_mode: str = "all_pairs"
    stats_control: str = ""
    stats_pair_by: str = ""          # subject column for paired tests
    stats_format: str = "stars"
    stats_correction: str = "holm"
    stats_hide_ns: bool = True
    stats_bracket_gap: float = 0.045

    # -- misc --------------------------------------------------------------
    dpi_preview: int = 110
    notes: str = ""

    # ---------------------------------------------------------------------
    def __setattr__(self, name, value):
        """Accept a key, a current label or a legacy one; store the key.

        On assignment rather than at construction, so a value set later by a
        script or by an old project file is converted just the same.
        """
        enum = SPEC_FIELDS.get(name)
        if enum is not None and isinstance(value, str):
            value = enum.normalise(value)
        object.__setattr__(self, name, value)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlotSpec":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def clone(self, name: str | None = None) -> "PlotSpec":
        spec = PlotSpec.from_dict(self.to_dict())
        spec.name = name or f"{self.name} (copie)"
        return spec

    # -- convenience -------------------------------------------------------
    @property
    def is_categorical(self) -> bool:
        return self.plot_type in ("bar", "box", "violin")

    @property
    def is_xy(self) -> bool:
        return self.plot_type in ("line", "scatter")

    def series_names(self) -> list[str]:
        return list(self.y)
