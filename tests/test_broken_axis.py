"""Broken Y axis: two parts that read as one plot, cut where asked.

What would betray the cut is checked: each part shows its own range and no
more; what must appear once - comparisons, brackets, legend, title, the Y
title - appears once; the two parts sit a hair apart with the share of
height asked for; a cut that cannot be made says why and leaves the plot
whole.
"""
import io

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea.core import demo, plotting
from plotea.core.panel import Panel, render_panel
from plotea.core.plotspec import PlotSpec

RNG = np.random.default_rng(2)
DATA = pd.DataFrame([{"Groupe": g, "Valeur": float(v)}
                     for g, m in (("Témoin", 12), ("Faible", 15),
                                  ("Moyen", 18), ("Fort", 240))
                     for v in RNG.normal(m, m * 0.12, 6)])


def render(**fields):
    fields = {"plot_type": "bar", "group": "Groupe", "y": ["Valeur"],
              "ylabel": "Concentration", "y_break": True,
              "y_break_from": 30.0, "y_break_to": 180.0, **fields}
    figure = Figure(figsize=(3.5, 2.8))
    info = plotting.render(figure, PlotSpec(**fields), DATA)
    return figure, info


def parts(figure):
    top, bottom = figure.axes
    return top, bottom


# --------------------------------------------------------------------------
# The two parts
# --------------------------------------------------------------------------
def test_each_part_shows_its_own_range():
    figure, info = render()
    assert info.broken and len(figure.axes) == 2
    top, bottom = parts(figure)
    assert bottom.get_ylim()[1] == pytest.approx(30.0)
    assert top.get_ylim()[0] == pytest.approx(180.0)
    assert bottom.get_ylim()[0] <= 0.0
    assert top.get_ylim()[1] >= DATA["Valeur"].max()


def test_the_seam_is_hidden_and_marked():
    figure, _ = render()
    top, bottom = parts(figure)
    assert not top.spines["bottom"].get_visible()
    assert not bottom.spines["top"].get_visible()
    assert not any(t.get_text() for t in top.get_xticklabels())
    assert [t.get_text() for t in bottom.get_xticklabels()] == \
        ["Témoin", "Faible", "Moyen", "Fort"]

    def slants(ax):
        return [line for line in ax.lines if not line.get_clip_on()]
    # one slant per spine shown: the left only, then both sides
    assert [len(slants(ax)[0].get_xdata()) for ax in (top, bottom)] == [1, 1]
    figure, _ = render(despine=False)
    top, bottom = parts(figure)
    assert [len(slants(ax)[0].get_xdata()) for ax in (top, bottom)] == [2, 2]


def test_the_parts_sit_a_hair_apart_with_their_share():
    figure, _ = render(y_break_top=0.4)
    top, bottom = (ax.get_position() for ax in parts(figure))
    height = top.y1 - bottom.y0
    assert top.y0 > bottom.y1                              # above it
    assert (top.y0 - bottom.y1) == pytest.approx(
        plotting.BREAK_GAP * height, rel=1e-6)
    assert top.height / (top.height + bottom.height) == pytest.approx(0.4)
    assert top.x0 == pytest.approx(bottom.x0)
    assert top.width == pytest.approx(bottom.width)


def test_what_appears_once_appears_once():
    figure, info = render(stats_enabled=True, title="Dosage")
    top, bottom = parts(figure)
    assert len(info.comparisons) == 6                       # computed once
    assert any(t.get_text() == "****" for t in top.texts)   # brackets above
    assert not any(t.get_text().strip("*") == "" and t.get_text()
                   for t in bottom.texts)
    assert top.get_title() == "Dosage" and bottom.get_title() == ""
    assert top.get_ylabel() == "" and bottom.get_ylabel() == "Concentration"


def test_the_y_title_is_centred_on_the_whole_axis():
    figure, _ = render()
    top, bottom = parts(figure)
    figure.savefig(io.BytesIO(), format="png")
    renderer = plotting._renderer(figure)
    label = bottom.yaxis.label.get_window_extent(renderer)
    whole = (top.get_window_extent(renderer).y1
             + bottom.get_window_extent(renderer).y0) / 2
    assert (label.y0 + label.y1) / 2 == pytest.approx(whole, abs=2)


@pytest.mark.parametrize("plot_type", ["box", "violin", "paired"])
def test_other_categorical_plots_can_be_cut(plot_type):
    _figure, info = render(plot_type=plot_type)
    assert info.broken, info.warnings


@pytest.mark.parametrize("plot_type", ["line", "scatter"])
def test_curves_with_one_runaway_point_can_be_cut(plot_type):
    xy = pd.DataFrame({"t": np.arange(1.0, 9.0),
                       "y": [1.0, 1.4, 2.1, 2.6, 3.2, 3.9, 4.4, 95.0]})
    figure = Figure(figsize=(3.5, 2.8))
    info = plotting.render(figure, PlotSpec(
        plot_type=plot_type, x="t", y=["y"], y_break=True,
        y_break_from=6.0, y_break_to=90.0), xy)
    assert info.broken, info.warnings
    top, bottom = parts(figure)
    assert bottom.get_ylim()[1] == pytest.approx(6.0)
    assert top.get_ylim()[0] == pytest.approx(90.0)


def test_the_export_keeps_its_text_editable():
    from plotea.core import export

    figure, _ = render()
    svg = export.figure_to_svg_text(figure)
    assert "Concentration" in svg and svg.count("<text") > 10


# --------------------------------------------------------------------------
# Cuts that cannot be made
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fields, says", [
    (dict(y_break_from=None), "indiquez"),
    (dict(y_break_from=180.0, y_break_to=30.0), "son début avant sa fin"),
    (dict(y_break_to=5000.0), "doit tomber entre"),
    (dict(log_y=True), "log Y"),
    (dict(plot_type="survival"), "type de graphique"),
])
def test_a_cut_that_cannot_be_made_says_why_and_leaves_the_plot(fields,
                                                               says):
    figure, info = render(**fields)
    assert not info.broken and len(figure.axes) == 1
    assert any(says in w for w in info.warnings), info.warnings


# --------------------------------------------------------------------------
# In a composite figure
# --------------------------------------------------------------------------
def composite(cut=None, **panel_fields):
    """A cut bar chart, a whole one, and a heat map with its colour bar."""
    heat = demo.heatmap()
    cut = {"name": "Coupé", "plot_type": "bar", "dataset": "D",
           "group": "Groupe", "y": ["Valeur"], "ylabel": "Concentration",
           "title": "Dosage", "stats_enabled": True, "y_break": True,
           "y_break_from": 30.0, "y_break_to": 180.0, "y_break_top": 0.35,
           **(cut or {})}
    specs = {
        "Coupé": PlotSpec(**cut),
        "Entier": PlotSpec(name="Entier", plot_type="bar", dataset="D",
                           group="Groupe", y=["Valeur"]),
        "Chaleur": PlotSpec(**{**heat.meta["plot"], "name": "Chaleur",
                               "dataset": "H"}),
        "Courbe": PlotSpec(name="Courbe", plot_type="scatter", dataset="D2",
                           x="t", y=["y"])}
    frames = {"D": DATA, "H": heat.df,
              "D2": pd.DataFrame({"t": [1.0, 2, 3], "y": [1.0, 4, 9]})}
    fields = {"name": "F", "plots": ["Coupé", "Entier", "Chaleur"],
              "cols": 2, **panel_fields}
    figure = Figure(figsize=(7, 5))
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        info = render_panel(figure, Panel(**fields), specs, frames)
        figure.savefig(io.BytesIO(), format="png")
    collapsed = [w for w in caught if "collapsed" in str(w.message)]
    return figure, info, collapsed


def test_composite_figures_cut_the_axis_too():
    figure, info, collapsed = composite()
    assert not collapsed, "la mise en page a renoncé"
    assert not any("composites" in w for w in info.warnings), info.warnings
    top, bottom = figure.axes[0], figure.axes[1]
    assert bottom.get_ylim()[1] == pytest.approx(30.0)
    assert top.get_ylim()[0] == pytest.approx(180.0)
    # drawn once, on the upper part: letter, title, brackets
    assert top.get_title(loc="left") == "A" and top.get_title() == "Dosage"
    assert any(t.get_text() == "****" for t in top.texts)
    assert not bottom.get_title(loc="left")


def test_in_its_tile_the_parts_stack_with_their_share():
    figure, _, _ = composite()
    top, bottom = (ax.get_position() for ax in figure.axes[:2])
    assert top.x0 == pytest.approx(bottom.x0)
    assert top.width == pytest.approx(bottom.width)
    whole = top.y1 - bottom.y0
    gap = top.y0 - bottom.y1
    assert 0 < gap < 0.12 * whole                  # a hair apart
    assert top.height / (top.height + bottom.height) == pytest.approx(
        0.35, abs=0.01)


def test_in_a_composite_the_y_title_is_centred_on_both_parts():
    figure, _, _ = composite()
    top, bottom = figure.axes[:2]
    renderer = plotting._renderer(figure)
    label = bottom.yaxis.label.get_window_extent(renderer)
    whole = (top.get_window_extent(renderer).y1
             + bottom.get_window_extent(renderer).y0) / 2
    assert (label.y0 + label.y1) / 2 == pytest.approx(whole, abs=2)
    assert top.get_ylabel() == ""                # written once


def test_each_part_hides_what_belongs_to_the_other():
    """The low groups' points stay out of the upper part - and out of the
    cut between the two."""
    figure, _, _ = composite()
    for part in figure.axes[:2]:
        assert all(c.get_clip_on() for c in part.collections)


def test_the_layout_is_the_same_at_every_drawing():
    figure, _, _ = composite()
    def places():
        return [v for ax in figure.axes for v in ax.get_position().bounds]
    figure.savefig(io.BytesIO(), format="svg")
    before = places()
    figure.savefig(io.BytesIO(), format="svg")
    assert places() == pytest.approx(before, abs=1e-5)   # sub-pixel
    # an export measures text its own way and moves the parts a little:
    # the Y title is centred again on the places of that export
    top, bottom = (ax.get_position() for ax in figure.axes[:2])
    centre = ((top.y1 + bottom.y0) / 2 - bottom.y0) / bottom.height
    assert figure.axes[1].yaxis.label.get_position()[1] == pytest.approx(
        centre)


def test_shared_scales_skip_the_cut_plot():
    figure, _, collapsed = composite(plots=["Coupé", "Entier", "Courbe"],
                                     share_x=False, share_y=True)
    assert not collapsed
    cut_top, cut_bottom, whole, curve = figure.axes[:4]
    assert curve.get_shared_y_axes().joined(whole, curve)
    assert not cut_bottom.get_shared_y_axes().joined(cut_bottom, whole)


def test_a_cut_plot_does_not_stretch_the_scale_it_would_share():
    """Drawn whole first to find where to cut, it must not pull the shared
    scale of the plots before it up to its own brackets."""
    alone, _, _ = composite(plots=["Entier", "Courbe"], share_y=True)
    figure, _, _ = composite(plots=["Entier", "Coupé", "Courbe"],
                             share_y=True)
    whole = figure.axes[0]
    assert whole.get_ylim() == pytest.approx(alone.axes[0].get_ylim())


def test_a_cut_that_cannot_be_made_leaves_the_tile_whole():
    figure, info, _ = composite(cut={"y_break_to": 5000.0})
    assert any("« Coupé »" in w and "doit tomber entre" in w
               for w in info.warnings), info.warnings
    assert len(figure.axes) == 3 + 1         # three tiles + the colour bar


def test_the_settings_survive_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="B", y_break=True, y_break_from=30.0,
                              y_break_to=180.0, y_break_top=0.4))
    spec = Project.load(project.save(str(tmp_path / "b.plotea"))).plots[-1]
    assert (spec.y_break, spec.y_break_from, spec.y_break_to,
            spec.y_break_top) == (True, 30.0, 180.0, 0.4)


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_controls_wake_with_the_checkbox(window):
    inspector = window.inspector
    assert not inspector.f_break_from.isEnabled()
    inspector.chk_ybreak.setChecked(True)
    assert inspector.f_break_from.isEnabled()
    inspector.f_break_from.setText("40")
    inspector.f_break_from.editingFinished.emit()
    inspector.f_break_to.setText("80")
    inspector.f_break_to.editingFinished.emit()
    window._render_now()
    assert window.canvas.last_info.broken
    assert len(window.canvas.figure.axes) == 2
