"""PlotSpec: the serialisable description of one figure.

Everything the renderer needs lives here, so a project file is just a list of
PlotSpecs plus the datasets. Nothing in this module imports matplotlib.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field

from .enums import PLOT_TYPE, SPEC_FIELDS

#: Kept for convenience: plot type key -> label shown in the interface.
PLOT_TYPES = {choice.key: choice.label for choice in PLOT_TYPE}

#: How a figure looks whatever table it shows: "Apply style" and the presets
#: carry these, and they stay put when a plot moves to another table.
STYLE_FIELDS = [
    "theme", "palette", "span", "width_mm", "height_mm", "line_width",
    "marker", "marker_size", "line_style", "alpha", "fill_alpha",
    "error_type", "error_capsize", "show_points", "point_style",
    "point_alpha", "jitter_width", "bar_width", "bar_edge", "box_width",
    "notch", "violin_inner", "despine", "grid_x", "grid_y", "minor_ticks",
    "show_legend", "legend_loc", "monochrome_hatch", "transparent_bg",
]

#: The plot itself, not the way one of its tables is shown.
_OWN_FIELDS = {"name", "dataset", "per_table", "dpi_preview", "notes"}


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
    event_col: str = ""               # survival: 1 = event, 0 = censored

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
    # broken Y axis: the values between y_break_from and y_break_to are cut
    # out, the upper part taking y_break_top of the height
    y_break: bool = False
    y_break_from: float | None = None
    y_break_to: float | None = None
    y_break_top: float = 0.35
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

    survival_ci: bool = False         # 95 % band around the curve
    show_censors: bool = True         # ticks where follow-up stopped

    contingency_view: str = "percent"   # percent / stacked / grouped
    ba_view: str = "difference"         # Bland-Altman: difference / percent
    ba_ci: bool = False                 # CIs of the bias and of the limits
    heat_values: str = "values"         # values / z_rows / z_columns / corr.
    heat_cmap: str = "auto"
    heat_cluster: str = "none"          # none / rows / columns / both
    heat_annotate: bool = False         # write each value in its cell
    contingency_test: str = "auto"      # Fisher on 2 x 2, chi-square beyond

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
    # "" no comparison, "all" one curve for every series, or the name of a
    # parameter of the model whose value may differ between the series
    fit_compare: str = ""

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

    # -- how each table was last shown -------------------------------------
    # table name -> its plot type, columns, titles, statistics..., so that
    # coming back to a table gives back the plot it had
    per_table: dict = field(default_factory=dict)

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

    # -- moving between tables ---------------------------------------------
    def table_settings(self) -> dict:
        """Everything that describes how the current table is shown."""
        return {k: v for k, v in asdict(self).items()
                if k not in _OWN_FIELDS and k not in STYLE_FIELDS}

    def switch_table(self, name: str) -> bool:
        """Leave the current table for `name`, remembering how it was shown.

        True when `name` was shown before and its settings are back; False
        when it is new to this plot, whose columns are then to be chosen.
        The style stays: a plot keeps its look from one table to the next.
        """
        if self.dataset:
            self.per_table[self.dataset] = self.table_settings()
        self.dataset = name
        saved = self.per_table.get(name)
        if saved is None:
            return False
        for key, value in saved.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, copy.deepcopy(value))
        return True

    def rename_table(self, old: str, new: str):
        if self.dataset == old:
            self.dataset = new
        if old in self.per_table:
            self.per_table[new] = self.per_table.pop(old)

    # -- convenience -------------------------------------------------------
    @property
    def is_categorical(self) -> bool:
        return self.plot_type in ("bar", "box", "violin", "paired")

    @property
    def is_xy(self) -> bool:
        return self.plot_type in ("line", "scatter")

    @property
    def is_survival(self) -> bool:
        return self.plot_type == "survival"

    @property
    def is_contingency(self) -> bool:
        return self.plot_type == "contingency"

    def series_names(self) -> list[str]:
        return list(self.y)
