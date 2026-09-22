"""The rendering engine: turn a PlotSpec + DataFrame into a matplotlib figure.

Pure matplotlib (no seaborn) so the output stays fully controllable and the
dependency list stays small. Every drawing routine honours the active Theme.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import matplotlib as mpl
import numpy as np
import pandas as pd

from . import diagnostics, fitting
from . import stats as st
from .plotspec import PlotSpec
from .themes import HATCHES, Theme, color_cycle, get_theme


@dataclass
class RenderInfo:
    """Everything the UI wants to show after a render.

    `series` are the legend/colour entities; `stat_groups` are the units that
    statistics compare. On a two-factor bar chart they differ: the colours
    follow the subgroups, the comparisons run on each category x subgroup cell.
    """
    warnings: list = field(default_factory=list)
    fits: dict = field(default_factory=dict)
    comparisons: list = field(default_factory=list)
    omnibus: tuple = ()
    descriptives: list = field(default_factory=list)
    groups: list = field(default_factory=list)      # labels of stat_groups
    series: list = field(default_factory=list)
    stat_groups: dict = field(default_factory=dict)
    stat_pairs: list | None = None                  # restrict comparisons
    anova: list = field(default_factory=list)       # two-way table
    anova_message: str = ""


# --------------------------------------------------------------------------
# Data shaping
# --------------------------------------------------------------------------
def _num(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)


def extract_groups(df: pd.DataFrame, spec: PlotSpec
                   ) -> dict[str, np.ndarray]:
    """Categorical plots: label -> raw values.

    Two supported layouts: long (a grouping column + one value column) and
    wide (one column per group).
    """
    out: dict[str, np.ndarray] = {}
    if spec.group and spec.group in df.columns and spec.y:
        value_col = spec.y[0]
        if value_col not in df.columns:
            return out
        for key, sub in df.groupby(spec.group, sort=False):
            arr = _num(sub[value_col])
            arr = arr[np.isfinite(arr)]
            if arr.size:
                out[str(key)] = arr
        return out
    for col in spec.y:
        if col in df.columns:
            arr = _num(df[col])
            arr = arr[np.isfinite(arr)]
            if arr.size:
                out[str(col)] = arr
    return out


def extract_nested(df: pd.DataFrame, spec: PlotSpec
                   ) -> tuple[list[str], dict[str, dict[str, np.ndarray]]]:
    """Two-factor layout: categories on X, one series per subgroup."""
    value_col = spec.y[0] if spec.y else ""
    if not (spec.group and spec.subgroup and value_col in df.columns):
        return [], {}
    cats = [str(c) for c in pd.unique(df[spec.group].dropna())]
    subs = [str(s) for s in pd.unique(df[spec.subgroup].dropna())]
    table: dict[str, dict[str, np.ndarray]] = {s: {} for s in subs}
    for (cat, sub), chunk in df.groupby([spec.group, spec.subgroup],
                                        sort=False):
        arr = _num(chunk[value_col])
        arr = arr[np.isfinite(arr)]
        table.setdefault(str(sub), {})[str(cat)] = arr
    return cats, table


#: How a category / subgroup cell is labelled in the stats tables.
CELL_SEP = " / "

#: Above this many points, a series is rasterised inside the vector output:
#: the file stays small and the figure still draws quickly.
RASTER_THRESHOLD = 5000

#: Individual points stop being legible long before this, and drawing every
#: one of them is what makes a large table feel slow.
MAX_OVERLAY_POINTS = 2000

#: A density estimate does not need the whole population.
MAX_KDE_SAMPLES = 20000


def _subsample(values: np.ndarray, limit: int, seed: int = 12345):
    """A fixed random subset, so the preview never jitters between renders."""
    if values.size <= limit:
        return values, False
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(values, limit, replace=False)), True


def extract_paired(df: pd.DataFrame, spec: PlotSpec) -> dict | None:
    """Subject-aligned values: {group: {subject: value}}, or None.

    Long format needs an explicit pairing column, because the row order of one
    group says nothing about the row order of another. Wide format falls back
    to the table row, which is exactly what pairing means there.
    """
    key_col = spec.stats_pair_by
    if spec.group and spec.group in df.columns and spec.y:
        value_col = spec.y[0]
        if (not key_col or key_col not in df.columns
                or value_col not in df.columns):
            return None
        out: dict[str, dict] = {}
        for label, sub in df.groupby(spec.group, sort=False):
            out[str(label)] = {str(subject): value for subject, value
                               in zip(sub[key_col], _num(sub[value_col]))}
        return out

    cols = [c for c in spec.y if c in df.columns]
    if len(cols) < 2:
        return None
    if key_col and key_col in df.columns:
        subjects = [str(s) for s in df[key_col]]
    else:
        subjects = [str(i) for i in range(len(df))]
    return {c: dict(zip(subjects, _num(df[c]))) for c in cols}


@dataclass
class XYSeries:
    label: str
    x: np.ndarray
    y: np.ndarray
    err_low: np.ndarray | None = None
    err_high: np.ndarray | None = None


def extract_xy(df: pd.DataFrame, spec: PlotSpec) -> list[XYSeries]:
    """Line/scatter series, aggregating replicates sharing the same X."""
    series: list[XYSeries] = []
    aggregate = spec.error_type != "none" and spec.plot_type == "line"

    def build(label, xv, yv, err_col=None):
        mask = np.isfinite(xv) & np.isfinite(yv)
        xv, yv = xv[mask], yv[mask]
        if xv.size == 0:
            return None
        if err_col is not None:
            ev = err_col[mask]
            order = np.argsort(xv)
            return XYSeries(label, xv[order], yv[order], ev[order], ev[order])
        if aggregate and np.unique(xv).size < xv.size:
            xs, means, lo, hi = [], [], [], []
            for ux in np.unique(xv):
                vals = yv[xv == ux]
                e = st.error_value(vals, spec.error_type)
                xs.append(ux)
                means.append(float(vals.mean()))
                lo.append(e[0])
                hi.append(e[1])
            return XYSeries(label, np.array(xs), np.array(means),
                            np.array(lo), np.array(hi))
        order = np.argsort(xv)
        return XYSeries(label, xv[order], yv[order])

    if spec.group and spec.group in df.columns and spec.y:
        ycol = spec.y[0]
        if ycol not in df.columns:
            return series
        for key, sub in df.groupby(spec.group, sort=False):
            xv = (_num(sub[spec.x]) if spec.x in sub.columns
                  else np.arange(len(sub), dtype=float))
            s = build(str(key), xv, _num(sub[ycol]))
            if s:
                series.append(s)
        return series

    xv = (_num(df[spec.x]) if spec.x in df.columns
          else np.arange(len(df), dtype=float))
    for i, col in enumerate(spec.y):
        if col not in df.columns:
            continue
        err = None
        if i < len(spec.error_cols):
            ec = spec.error_cols[i]
            if ec and ec in df.columns:
                err = _num(df[ec])
        s = build(str(col), xv.copy(), _num(df[col]), err)
        if s:
            series.append(s)
    return series


# --------------------------------------------------------------------------
# Small drawing helpers
# --------------------------------------------------------------------------
def _beeswarm(values: np.ndarray, center: float, width: float,
              point_size: float) -> np.ndarray:
    """Cheap beeswarm: bin on Y, spread ties symmetrically around center."""
    if values.size == 0:
        return np.array([])
    order = np.argsort(values)
    sorted_v = values[order]
    span = float(np.ptp(sorted_v)) or 1.0
    nbins = max(int(np.sqrt(values.size) * 3), 6)
    bin_h = span / nbins
    offsets = np.zeros(values.size)
    bins: dict[int, int] = {}
    for i, v in enumerate(sorted_v):
        b = int((v - sorted_v[0]) / bin_h) if bin_h else 0
        k = bins.get(b, 0)
        bins[b] = k + 1
        step = width / max(np.sqrt(values.size), 3)
        sign = 1 if k % 2 else -1
        offsets[i] = center + sign * step * ((k + 1) // 2)
    out = np.empty_like(offsets)
    out[order] = offsets
    return out


def _point_positions(values: np.ndarray, center: float, spec: PlotSpec,
                     rng: np.random.Generator) -> np.ndarray:
    style = spec.point_style
    if style == "aligned":
        return np.full(values.size, center)
    if style == "swarm":
        return _beeswarm(values, center, spec.jitter_width * 2, spec.point_size)
    return center + rng.uniform(-spec.jitter_width, spec.jitter_width,
                                values.size)


def _lighten(color: str, amount: float = 0.55) -> tuple:
    rgb = np.array(mpl.colors.to_rgb(color))
    return tuple(rgb + (1.0 - rgb) * amount)


def _no_data(ax, message: str = "Aucune donnée à tracer"):
    """Say so on the figure rather than letting an empty array explode."""
    ax.text(0.5, 0.5, message, ha="center", va="center",
            transform=ax.transAxes, color="#999999")
    ax.set_axis_off()
    return {}, {}


def _orient(spec: PlotSpec) -> str:
    return "horizontal" if spec.horizontal else "vertical"


def _sizes(spec: PlotSpec, theme: Theme) -> dict:
    return {
        "lw": spec.line_width or theme.linewidth,
        "ms": spec.marker_size or theme.marker_size,
        "ps": (spec.point_size or theme.marker_size * 0.8) ** 2,
        "cap": spec.error_capsize or theme.capsize,
    }


def _colors(spec: PlotSpec, theme: Theme, labels: list[str]) -> list[str]:
    palette = spec.palette or theme.palette
    base = color_cycle(palette, len(labels))
    return [spec.custom_colors.get(lab, base[i]) for i, lab in
            enumerate(labels)]


# --------------------------------------------------------------------------
# Significance brackets
# --------------------------------------------------------------------------
def draw_brackets(ax, comparisons, positions: dict[str, float],
                  tops: dict[str, float], spec: PlotSpec, theme: Theme):
    """Stack significance brackets above the data without overlapping."""
    comps = [c for c in comparisons
             if c.a in positions and c.b in positions]
    if spec.stats_hide_ns:
        comps = [c for c in comps if c.p_adj < 0.05]
    if not comps:
        return
    comps.sort(key=lambda c: abs(positions[c.a] - positions[c.b]))

    y0, y1 = ax.get_ylim()
    span = (y1 - y0) or 1.0
    gap = spec.stats_bracket_gap * span
    baseline = max(tops.values()) if tops else y1
    occupied: list[tuple[float, float, float]] = []   # x0, x1, level y

    # Height the stars actually occupy in data units. Measuring it beats
    # guessing: on a short axes the label is a large share of the range, and
    # a fixed allowance lets it collide with the bracket stacked above.
    text_height = gap
    try:
        bbox = ax.get_window_extent()
        if bbox.height > 0:
            pixels = theme.base_size * ax.figure.get_dpi() / 72.0
            text_height = span * pixels / bbox.height
    except Exception:
        pass
    clearance = text_height * 1.25

    for comp in comps:
        xa, xb = sorted((positions[comp.a], positions[comp.b]))
        local = max(baseline, tops.get(comp.a, y0), tops.get(comp.b, y0))
        level = local + gap
        for ox0, ox1, oy in occupied:
            if not (xb < ox0 - 1e-9 or xa > ox1 + 1e-9):
                level = max(level, oy)
        h = gap * 0.28
        ax.plot([xa, xa, xb, xb], [level, level + h, level + h, level],
                lw=theme.spine_width, color="black",
                solid_joinstyle="miter", clip_on=False, zorder=20)
        ax.text((xa + xb) / 2, level + h * 1.05,
                st.format_p(comp.p_adj, spec.stats_format),
                ha="center", va="bottom", fontsize=theme.base_size,
                clip_on=False, zorder=21)
        occupied.append((xa, xb, level + h + clearance))

    top_needed = max(o[2] for o in occupied) + gap * 0.4
    if top_needed > y1:
        ax.set_ylim(y0, top_needed)


# --------------------------------------------------------------------------
# Plot types
# --------------------------------------------------------------------------
def _draw_points_overlay(ax, values, center, color, spec, theme, rng,
                         sizes, horizontal=False, info=None):
    if not spec.show_points or spec.point_style == "none" or values.size == 0:
        return
    values, trimmed = _subsample(values, MAX_OVERLAY_POINTS)
    if trimmed and info is not None:
        message = (f"Nuage limite a {MAX_OVERLAY_POINTS} points par groupe "
                   "pour l'affichage ; les statistiques utilisent tout.")
        if message not in info.warnings:
            info.warnings.append(message)
    pos = _point_positions(values, center, spec, rng)
    edge = "white" if spec.point_edge else "none"
    raster = values.size > RASTER_THRESHOLD
    if horizontal:
        ax.scatter(values, pos, s=sizes["ps"], facecolor=color,
                   edgecolor=edge, linewidth=theme.spine_width * 0.7,
                   alpha=spec.point_alpha, zorder=6, clip_on=False,
                   rasterized=raster)
    else:
        ax.scatter(pos, values, s=sizes["ps"], facecolor=color,
                   edgecolor=edge, linewidth=theme.spine_width * 0.7,
                   alpha=spec.point_alpha, zorder=6, clip_on=False,
                   rasterized=raster)


def draw_bar(ax, df, spec, theme, info):
    cats, table = extract_nested(df, spec)
    rng = np.random.default_rng(12345)
    sizes = _sizes(spec, theme)
    positions: dict[str, float] = {}
    tops: dict[str, float] = {}

    if cats and table:                       # grouped bars, two factors
        subs = list(table)
        colors = _colors(spec, theme, subs)
        n = len(subs)
        width = spec.bar_width / max(n, 1)
        base = np.arange(len(cats), dtype=float)
        cells: dict[str, np.ndarray] = {}
        for si, sub in enumerate(subs):
            offs = base - spec.bar_width / 2 + width * (si + 0.5)
            means, errs = [], []
            for ci, cat in enumerate(cats):
                vals = table[sub].get(cat, np.array([]))
                m = float(vals.mean()) if vals.size else np.nan
                lo, hi = st.error_value(vals, spec.error_type)
                means.append(m)
                errs.append(hi)
                if vals.size:
                    _draw_points_overlay(ax, vals, offs[ci], "#3A3A3A", spec,
                                         theme, rng, sizes, info=info)
                    # each cell is a comparable unit: keep it addressable so
                    # significance brackets can be drawn between two bars
                    key = f"{cat}{CELL_SEP}{sub}"
                    cells[key] = vals
                    positions[key] = float(offs[ci])
                    tops[key] = max(m + hi, float(vals.max())
                                    if spec.show_points else -np.inf)
            ax.bar(offs, means, width * 0.92, label=sub, color=colors[si],
                   edgecolor="black" if spec.bar_edge else "none",
                   linewidth=theme.spine_width if spec.bar_edge else 0,
                   alpha=spec.alpha, zorder=2,
                   hatch=HATCHES[si % len(HATCHES)] if spec.monochrome_hatch
                   else None)
            if spec.error_type != "none":
                yerr = ([np.zeros(len(cats)), errs]
                        if spec.error_direction == "up" else errs)
                ax.errorbar(offs, means, yerr=yerr, fmt="none", ecolor="black",
                            elinewidth=theme.spine_width,
                            capsize=sizes["cap"], zorder=5)
        ax.set_xticks(base)
        ax.set_xticklabels(cats)
        # compare subgroups inside each category: the comparison a two-factor
        # design is drawn for, and the only one whose brackets stay local
        info.stat_pairs = [
            (f"{cat}{CELL_SEP}{a}", f"{cat}{CELL_SEP}{b}")
            for cat in cats for a, b in itertools.combinations(subs, 2)]
        info.series = subs
        info.stat_groups = cells
        info.anova, info.anova_message = st.two_way_anova(
            {(cat, sub): table[sub].get(cat, np.array([]))
             for cat in cats for sub in subs},
            spec.group or "Facteur A", spec.subgroup or "Facteur B")
        return positions, tops

    groups = extract_groups(df, spec)
    info.groups = list(groups)
    info.series = list(groups)
    info.stat_groups = groups
    labels = list(groups)
    if not labels:
        return _no_data(ax)
    colors = _colors(spec, theme, labels)
    pos = np.arange(len(labels), dtype=float)
    means, lows, highs = [], [], []
    for lab in labels:
        vals = groups[lab]
        means.append(float(vals.mean()))
        lo, hi = st.error_value(vals, spec.error_type)
        lows.append(lo)
        highs.append(hi)

    horiz = spec.horizontal
    hatches = [HATCHES[i % len(HATCHES)] for i in range(len(labels))] \
        if spec.monochrome_hatch else [None] * len(labels)
    err = None
    if spec.error_type != "none":
        err = ([np.zeros(len(labels)), highs] if spec.error_direction == "up"
               else [lows, highs])

    if horiz:
        ax.barh(pos, means, spec.bar_width, color=colors,
                edgecolor="black" if spec.bar_edge else "none",
                linewidth=theme.spine_width if spec.bar_edge else 0,
                alpha=spec.alpha, zorder=2, hatch=hatches)
        if err is not None:
            ax.errorbar(means, pos, xerr=err, fmt="none", ecolor="black",
                        elinewidth=theme.spine_width, capsize=sizes["cap"],
                        zorder=5)
        ax.set_yticks(pos)
        ax.set_yticklabels(labels)
    else:
        ax.bar(pos, means, spec.bar_width, color=colors,
               edgecolor="black" if spec.bar_edge else "none",
               linewidth=theme.spine_width if spec.bar_edge else 0,
               alpha=spec.alpha, zorder=2, hatch=hatches)
        if err is not None:
            ax.errorbar(pos, means, yerr=err, fmt="none", ecolor="black",
                        elinewidth=theme.spine_width, capsize=sizes["cap"],
                        zorder=5)
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)

    for i, lab in enumerate(labels):
        _draw_points_overlay(ax, groups[lab], pos[i], "#2B2B2B", spec, theme,
                             rng, sizes, horizontal=horiz, info=info)
        positions[lab] = pos[i]
        peak = max(means[i] + highs[i],
                   float(groups[lab].max()) if spec.show_points else -np.inf)
        tops[lab] = peak

    if spec.connect_means and not horiz:
        ax.plot(pos, means, color="black", lw=theme.linewidth,
                marker="", zorder=7)
    if spec.y_from_zero and not horiz:
        ax.set_ylim(bottom=min(0.0, float(np.nanmin(means)) * 1.1))
    return positions, tops


def _style_box(bp, colors, theme, spec):
    for i, patch in enumerate(bp["boxes"]):
        c = colors[i % len(colors)]
        patch.set_facecolor(_lighten(c, 0.55))
        patch.set_edgecolor(c)
        patch.set_linewidth(theme.spine_width * 1.2)
        patch.set_alpha(spec.alpha)
        if spec.monochrome_hatch:
            patch.set_hatch(HATCHES[i % len(HATCHES)])
    for key in ("whiskers", "caps"):
        for i, item in enumerate(bp[key]):
            item.set_color(colors[(i // 2) % len(colors)])
            item.set_linewidth(theme.spine_width)
    for i, med in enumerate(bp["medians"]):
        med.set_color("black")
        med.set_linewidth(theme.spine_width * 1.6)
    for i, fl in enumerate(bp.get("fliers", [])):
        fl.set_marker("o")
        fl.set_markersize(theme.marker_size * 0.6)
        fl.set_markerfacecolor("none")
        fl.set_markeredgecolor(colors[i % len(colors)])
        fl.set_markeredgewidth(theme.spine_width)


def draw_box(ax, df, spec, theme, info):
    groups = extract_groups(df, spec)
    info.groups = list(groups)
    info.series = list(groups)
    info.stat_groups = groups
    labels = list(groups)
    if not labels:
        return _no_data(ax)
    colors = _colors(spec, theme, labels)
    data = [groups[key] for key in labels]
    pos = np.arange(len(labels), dtype=float)
    rng = np.random.default_rng(12345)
    sizes = _sizes(spec, theme)

    bp = ax.boxplot(data, positions=pos, widths=spec.box_width,
                    patch_artist=True, notch=spec.notch,
                    showfliers=spec.show_outliers and not spec.show_points,
                    orientation=_orient(spec), zorder=3,
                    medianprops={}, manage_ticks=False)
    _style_box(bp, colors, theme, spec)

    positions, tops = {}, {}
    for i, lab in enumerate(labels):
        _draw_points_overlay(ax, groups[lab], pos[i], colors[i], spec, theme,
                             rng, sizes, horizontal=spec.horizontal,
                             info=info)
        positions[lab] = pos[i]
        tops[lab] = float(np.max(groups[lab]))

    if spec.horizontal:
        ax.set_yticks(pos)
        ax.set_yticklabels(labels)
    else:
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)
    if spec.connect_means and not spec.horizontal:
        ax.plot(pos, [float(np.mean(groups[key])) for key in labels],
                color="black", lw=theme.linewidth, zorder=7)
    return positions, tops


def draw_violin(ax, df, spec, theme, info):
    groups = extract_groups(df, spec)
    info.groups = list(groups)
    info.series = list(groups)
    info.stat_groups = groups
    labels = list(groups)
    if not labels:
        return _no_data(ax)
    colors = _colors(spec, theme, labels)
    data = [groups[key] for key in labels]
    pos = np.arange(len(labels), dtype=float)
    rng = np.random.default_rng(12345)
    sizes = _sizes(spec, theme)

    kwargs = dict(positions=pos, widths=spec.box_width, showextrema=False,
                  showmeans=False, showmedians=False,
                  orientation=_orient(spec),
                  side={"left": "low", "right": "high"}.get(
                      spec.violin_side, "both"))
    if spec.violin_bw:
        kwargs["bw_method"] = spec.violin_bw
    parts = ax.violinplot(data, **kwargs)
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(_lighten(colors[i], 0.45))
        body.set_edgecolor(colors[i])
        body.set_linewidth(theme.spine_width)
        body.set_alpha(spec.alpha if spec.alpha < 1 else 0.85)

    inner = spec.violin_inner
    if inner == "box":
        bp = ax.boxplot(data, positions=pos, widths=spec.box_width * 0.18,
                        patch_artist=True, showfliers=False,
                        orientation=_orient(spec), manage_ticks=False,
                        zorder=5)
        for patch in bp["boxes"]:
            patch.set_facecolor("black")
            patch.set_edgecolor("black")
        for key in ("whiskers", "caps"):
            for item in bp[key]:
                item.set_color("black")
                item.set_linewidth(theme.spine_width)
        for med in bp["medians"]:
            med.set_color("white")
            med.set_linewidth(theme.spine_width * 1.4)
    elif inner == "quartiles":
        for i, vals in enumerate(data):
            q1, med, q3 = np.percentile(vals, [25, 50, 75])
            if spec.horizontal:
                ax.plot([q1, q3], [pos[i]] * 2, color="black",
                        lw=theme.spine_width * 2.6, zorder=5)
                ax.scatter([med], [pos[i]], color="white", s=sizes["ps"] * 0.6,
                           zorder=6, edgecolor="black",
                           linewidth=theme.spine_width)
            else:
                ax.plot([pos[i]] * 2, [q1, q3], color="black",
                        lw=theme.spine_width * 2.6, zorder=5)
                ax.scatter([pos[i]], [med], color="white", s=sizes["ps"] * 0.6,
                           zorder=6, edgecolor="black",
                           linewidth=theme.spine_width)

    positions, tops = {}, {}
    for i, lab in enumerate(labels):
        if inner == "points" or spec.show_points:
            _draw_points_overlay(ax, groups[lab], pos[i], colors[i], spec,
                                 theme, rng, sizes,
                                 horizontal=spec.horizontal, info=info)
        positions[lab] = pos[i]
        tops[lab] = float(np.max(groups[lab]))

    if spec.horizontal:
        ax.set_yticks(pos)
        ax.set_yticklabels(labels)
    else:
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)
    return positions, tops


def draw_histogram(ax, df, spec, theme, info):
    groups = extract_groups(df, spec)
    info.groups = list(groups)
    info.series = list(groups)
    info.stat_groups = groups
    labels = list(groups)
    if not labels:
        return _no_data(ax)
    colors = _colors(spec, theme, labels)
    allv = np.concatenate([groups[key] for key in labels])
    bins = ("auto" if spec.bins_auto else
            np.linspace(allv.min(), allv.max(), max(spec.bins, 2) + 1))
    # "Densité" is matplotlib's density; the two relative modes are obtained
    # with per-observation weights so the bin heights stay comparable.
    density = spec.hist_stat == "density"
    histtype = "step" if spec.hist_step else "bar"

    for i, lab in enumerate(labels):
        vals = groups[lab]
        w = None
        if spec.hist_stat == "percent":
            w = np.full(vals.size, 100.0 / vals.size)
        elif spec.hist_stat == "probability":
            w = np.full(vals.size, 1.0 / vals.size)
        ax.hist(vals, bins=bins, density=density, weights=w, label=lab,
                color=colors[i], alpha=spec.alpha if len(labels) == 1
                else min(spec.alpha, 0.6),
                edgecolor="black" if histtype == "bar" else colors[i],
                linewidth=theme.spine_width, histtype=histtype,
                cumulative=spec.hist_cumulative, zorder=2 + i,
                hatch=HATCHES[i % len(HATCHES)] if spec.monochrome_hatch
                else None)
        if spec.hist_kde and vals.size > 2:
            try:
                from scipy.stats import gaussian_kde
                sample, _ = _subsample(vals, MAX_KDE_SAMPLES)
                kde = gaussian_kde(sample)
                xs = np.linspace(vals.min(), vals.max(), 256)
                ys = kde(xs)
                if not density:
                    _, edges = np.histogram(vals, bins=bins)
                    ys = ys * vals.size * float(np.diff(edges).mean())
                ax.plot(xs, ys, color=colors[i], lw=theme.linewidth * 1.4,
                        zorder=10)
            except Exception:
                info.warnings.append("KDE indisponible (scipy requis).")
    if not spec.ylabel:
        ax.set_ylabel({"count": "Effectif", "density": "Densité",
                       "probability": "Probabilité",
                       "percent": "Pourcentage (%)"}[spec.hist_stat])
    return {}, {}


def draw_xy(ax, df, spec, theme, info):
    series = extract_xy(df, spec)
    info.groups = [s.label for s in series]
    info.series = [s.label for s in series]
    if not series:
        return _no_data(ax)
    colors = _colors(spec, theme, [s.label for s in series])
    sizes = _sizes(spec, theme)
    scatter_mode = spec.plot_type == "scatter"

    for i, s in enumerate(series):
        color = colors[i]
        marker = spec.marker if spec.show_markers else "None"
        heavy = s.x.size > RASTER_THRESHOLD
        if scatter_mode:
            ax.scatter(s.x, s.y, s=sizes["ms"] ** 2, facecolor=color,
                       edgecolor=("white" if spec.point_edge and not heavy
                                  else "none"),
                       linewidth=theme.spine_width * 0.8, label=s.label,
                       alpha=spec.alpha, zorder=4, rasterized=heavy)
        else:
            if s.err_low is not None and spec.error_band:
                ax.fill_between(s.x, s.y - s.err_low, s.y + s.err_high,
                                color=color, alpha=spec.fill_alpha,
                                linewidth=0, zorder=2)
                ax.plot(s.x, s.y, color=color, lw=sizes["lw"],
                        ls=spec.line_style if spec.show_line else "None",
                        marker=marker, ms=sizes["ms"], label=s.label,
                        markerfacecolor=color, markeredgecolor="white",
                        alpha=spec.alpha, zorder=4)
            elif s.err_low is not None:
                ax.errorbar(s.x, s.y, yerr=[s.err_low, s.err_high],
                            color=color, lw=sizes["lw"],
                            ls=spec.line_style if spec.show_line else "None",
                            marker=marker, ms=sizes["ms"], label=s.label,
                            capsize=sizes["cap"],
                            elinewidth=theme.spine_width,
                            markerfacecolor=color, markeredgecolor="white",
                            alpha=spec.alpha, zorder=4)
            else:
                ax.plot(s.x, s.y, color=color, lw=sizes["lw"],
                        ls=spec.line_style if spec.show_line else "None",
                        marker="None" if heavy else marker, ms=sizes["ms"],
                        label=s.label, markerfacecolor=color,
                        markeredgecolor="white", alpha=spec.alpha, zorder=4,
                        rasterized=heavy)

        if spec.fit_model != "none":
            res = fitting.fit(s.x, s.y, spec.fit_model,
                              extrapolate=spec.fit_extrapolate)
            if res and res.ok:
                info.fits[s.label] = res
                ax.plot(res.x_fit, res.y_fit, color=color,
                        lw=sizes["lw"] * 1.2, ls="--" if scatter_mode else "-",
                        zorder=5)
                if spec.fit_ci and res.ci_low is not None:
                    ax.fill_between(res.x_fit, res.ci_low, res.ci_high,
                                    color=color, alpha=0.15, linewidth=0,
                                    zorder=1)
            elif res:
                info.warnings.append(f"{s.label}: {res.message}")

    if spec.fit_show_equation and info.fits:
        # One series: the full equation fits. Several: stay compact and let
        # the Analyses panel carry the detail.
        lines = []
        if len(info.fits) == 1:
            res = next(iter(info.fits.values()))
            lines = [res.equation, f"R2 = {res.r2:.4f}"]
        else:
            for lab, res in info.fits.items():
                lines.append(f"{lab}: R2 = {res.r2:.4f}")
        anchors = {
            "top left": (0.02, 0.98, "top", "left"),
            "top right": (0.98, 0.98, "top", "right"),
            "bottom left": (0.02, 0.02, "bottom", "left"),
            "bottom right": (0.98, 0.02, "bottom", "right"),
        }
        px, py, va, ha = anchors.get(spec.fit_equation_loc,
                                     anchors["top left"])
        ax.text(px, py, "\n".join(lines), transform=ax.transAxes,
                va=va, ha=ha, fontsize=theme.base_size * 0.9,
                linespacing=1.35, zorder=30,
                bbox=dict(facecolor="white", alpha=0.75, edgecolor="none",
                          boxstyle="round,pad=0.25"))
    return {}, {}


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------
DRAWERS = {
    "bar": draw_bar,
    "box": draw_box,
    "violin": draw_violin,
    "histogram": draw_histogram,
    "line": draw_xy,
    "scatter": draw_xy,
}


def render(fig, spec: PlotSpec, df: pd.DataFrame) -> RenderInfo:
    """Draw `spec` onto `fig` (which is cleared first)."""
    info = RenderInfo()
    theme = get_theme(spec.theme)
    fig.clear()

    if df is None or df.empty:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Aucune donnée", ha="center", va="center",
                transform=ax.transAxes, color="#999999")
        ax.set_axis_off()
        return info

    with mpl.rc_context(theme.rc()):
        ax = fig.add_subplot(111)
        draw_into(ax, spec, df, info, theme)
        try:
            fig.tight_layout(pad=0.4)
        except Exception:
            pass
    return info


def draw_into(ax, spec: PlotSpec, df: pd.DataFrame,
              info: RenderInfo | None = None, theme: Theme | None = None
              ) -> RenderInfo:
    """Draw one plot onto an existing axes.

    Split out of `render` so a multi-panel figure can place several plots on
    the same figure. The caller owns the rc_context and the layout.
    """
    info = info if info is not None else RenderInfo()
    theme = theme or get_theme(spec.theme)
    if df is None or df.empty:
        ax.text(0.5, 0.5, "Aucune donnée", ha="center", va="center",
                transform=ax.transAxes, color="#999999")
        ax.set_axis_off()
        return info

    drawer = DRAWERS.get(spec.plot_type, draw_bar)
    try:
        positions, tops = drawer(ax, df, spec, theme, info)
    except Exception as exc:       # keep the window alive, but keep the trace
        diagnostics.exception(f"Rendu de '{spec.name}' ({spec.plot_type})",
                              exc)
        info.warnings.append(
            f"Erreur de rendu : {exc} — détails dans Aide > Journal.")
        positions, tops = {}, {}

    _finish_axes(ax, spec, theme, info)

    if spec.is_categorical:
        groups = info.stat_groups or extract_groups(df, spec)
        info.groups = list(groups)
        info.descriptives = st.describe(groups)
        if spec.stats_enabled and positions:
            _run_statistics(ax, groups, positions, tops, spec, theme, df, info)

    _finish_legend(ax, spec, theme)
    for ann in spec.annotations:
        data = ann if isinstance(ann, dict) else ann.__dict__
        if not data.get("text"):
            continue
        ax.text(data.get("x", 0.5), data.get("y", 0.95),
                data["text"], transform=ax.transAxes,
                fontsize=data.get("size", theme.base_size),
                color=data.get("color", "#000000"),
                ha=data.get("ha", "center"),
                fontweight="bold" if data.get("bold") else "normal",
                fontstyle="italic" if data.get("italic") else "normal")
    return info


def _run_statistics(ax, groups, positions, tops, spec: PlotSpec, theme: Theme,
                    df: pd.DataFrame, info: RenderInfo):
    """Compare the groups and draw the brackets, or explain why it cannot."""
    paired = None
    if spec.stats_test in st.PAIRED_TESTS:
        if info.stat_pairs is not None:
            info.warnings.append(
                "Test apparié indisponible sur des barres groupees a deux "
                "facteurs.")
            return
        paired = extract_paired(df, spec)
        if paired is None:
            info.warnings.append(
                "Test apparié : choisissez la colonne d'appariement "
                "(sujet, patient, réplicat) dans la section Statistiques.")
            return

    if len(groups) > 2 and info.stat_pairs is None:
        info.omnibus = st.omnibus(groups)
    comps = st.pairwise(groups, spec.stats_test, spec.stats_correction,
                        spec.stats_mode, spec.stats_control,
                        pairs=info.stat_pairs, paired=paired)
    info.comparisons = comps
    if not comps and paired is not None:
        info.warnings.append(
            "Aucun sujet mesuré dans les deux groupes : appariement "
            "impossible avec cette colonne.")
    draw_brackets(ax, comps, positions, tops, spec, theme)


def series_colors(spec: PlotSpec, labels: list[str]) -> list[str]:
    """Colours the renderer would assign to `labels` (used by the UI)."""
    return _colors(spec, get_theme(spec.theme), labels)


def _finish_axes(ax, spec: PlotSpec, theme: Theme, info: RenderInfo):
    if spec.title:
        ax.set_title(spec.title)
    if spec.xlabel:
        ax.set_xlabel(spec.xlabel)
    if spec.ylabel:
        ax.set_ylabel(spec.ylabel)
    if spec.log_x:
        ax.set_xscale("log")
    if spec.log_y:
        try:
            ax.set_yscale("log")
        except Exception:
            info.warnings.append("Échelle log Y impossible (valeurs <= 0).")
    if spec.xmin is not None or spec.xmax is not None:
        ax.set_xlim(left=spec.xmin, right=spec.xmax)
    if spec.ymin is not None or spec.ymax is not None:
        ax.set_ylim(bottom=spec.ymin, top=spec.ymax)
    if spec.minor_ticks:
        ax.minorticks_on()
    ax.grid(spec.grid_x, axis="x")
    ax.grid(spec.grid_y, axis="y")
    if spec.despine:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    else:
        ax.spines["top"].set_visible(True)
        ax.spines["right"].set_visible(True)
    if spec.tick_rotation:
        for lab in ax.get_xticklabels():
            lab.set_rotation(spec.tick_rotation)
            lab.set_ha("right" if spec.tick_rotation > 0 else "left")


def _finish_legend(ax, spec: PlotSpec, theme: Theme):
    handles, labels = ax.get_legend_handles_labels()
    if not spec.show_legend or not handles:
        return
    kwargs = dict(title=spec.legend_title or None, ncol=max(spec.legend_ncol, 1),
                  fontsize=theme.base_size, markerscale=1.3,
                  borderpad=0.2, borderaxespad=0.4)
    if spec.legend_loc == "outside right":
        ax.legend(handles, labels, loc="center left",
                  bbox_to_anchor=(1.02, 0.5), **kwargs)
    elif spec.legend_loc == "outside top":
        ax.legend(handles, labels, loc="lower center",
                  bbox_to_anchor=(0.5, 1.02), **kwargs)
    else:
        ax.legend(handles, labels, loc=spec.legend_loc, **kwargs)
