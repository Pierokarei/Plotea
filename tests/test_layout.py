"""What lands on the page: names that fit, the journal's font, editable text.

A figure is laid out inside its theme and drawn later, by the preview or the
export, once the theme's settings have closed. Everything here checks the
figure as it is finally drawn, not as it was built: that difference is what
let group names run into each other, ticks spill over the edge, every
figure come out in DejaVu Sans and SVG text turn into outlines.
"""
import math
import os
import re

import matplotlib as mpl
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea.core import demo, export, plotting
from plotea.core.panel import Panel, render_panel
from plotea.core.plotspec import PlotSpec
from plotea.core.themes import get_theme, installed_fonts

WORDS = ["Contrôle non traité", "Inhibiteur de kinase",
         "Inhibiteur + anticorps", "Véhicule DMSO 0,1 %"]
ONE_LONG_WORD = ["Hydroxychloroquine", "Dexaméthasone", "Contrôle",
                 "Tocilizumab"]


def long_format(names, seed=3):
    rng = np.random.default_rng(seed)
    return pd.DataFrame([{"Groupe": n, "Valeur": float(v)}
                         for n in names for v in rng.normal(10, 2, 6)])


def drawn(names, **fields):
    """A Nature single-column figure, rendered then saved like an export."""
    fields.setdefault("plot_type", "bar")
    spec = PlotSpec(theme="Nature", group="Groupe", y=["Valeur"], **fields)
    figure = Figure(figsize=get_theme("Nature").figsize("single"), dpi=150)
    plotting.render(figure, spec, long_format(names))
    figure.savefig(os.devnull, format="png")       # outside the theme
    return figure, figure.axes[0]


def labels_of(ax):
    return [t for t in ax.get_xticklabels() if t.get_text()]


def collide(ax) -> bool:
    """Whether two neighbouring names touch, slanted or not."""
    renderer = plotting._renderer(ax.figure)
    labels = labels_of(ax)
    angle = labels[0].get_rotation()
    if angle:
        # parallel slanted names: compare their spacing across the slant
        # with the height of one line
        xs = sorted(ax.transData.transform([(t, 0) for t in ax.get_xticks()])
                    [:, 0])
        gap = min(b - a for a, b in zip(xs, xs[1:]))
        line = max(t.get_fontsize() for t in labels) * ax.figure.dpi / 72
        return gap * math.sin(math.radians(angle)) < line * 1.1
    boxes = sorted((t.get_window_extent(renderer) for t in labels),
                   key=lambda b: b.x0)
    return any(a.x1 > b.x0 for a, b in zip(boxes, boxes[1:]))


def overflow(figure) -> float:
    """How far, in inches, anything sticks out of the page."""
    tight = figure.get_tightbbox(plotting._renderer(figure))
    width, height = figure.get_size_inches()
    return max(0.0, -tight.x0, -tight.y0, tight.x1 - width,
               tight.y1 - height)


# --------------------------------------------------------------------------
# Names under the axis
# --------------------------------------------------------------------------
def test_names_of_several_words_are_broken_between_words():
    figure, ax = drawn(WORDS)
    texts = [t.get_text() for t in labels_of(ax)]
    assert any("\n" in text for text in texts) or \
        labels_of(ax)[0].get_rotation(), texts
    # not one word lost or cut in the middle
    assert [t.replace("\n", " ") for t in texts] == WORDS
    assert not collide(ax)
    assert overflow(figure) < 0.01


def test_a_word_too_long_to_break_slants_every_name():
    figure, ax = drawn(ONE_LONG_WORD, plot_type="box")
    assert {t.get_rotation() for t in labels_of(ax)} == {45.0}
    assert [t.get_text() for t in labels_of(ax)] == ONE_LONG_WORD
    assert not collide(ax)
    assert overflow(figure) < 0.01


def test_many_categories_on_a_violin_plot():
    names = [f"Lignée cellulaire {i}" for i in range(1, 9)]
    figure, ax = drawn(names, plot_type="violin")
    assert not collide(ax)
    assert overflow(figure) < 0.01


def test_short_names_are_left_alone():
    _, ax = drawn(["A", "B", "C"])
    assert [t.get_text() for t in labels_of(ax)] == ["A", "B", "C"]
    assert labels_of(ax)[0].get_rotation() == 0


def test_a_rotation_chosen_by_the_user_wins():
    _, ax = drawn(WORDS, tick_rotation=30)
    assert [t.get_text() for t in labels_of(ax)] == WORDS
    assert {t.get_rotation() for t in labels_of(ax)} == {30.0}


def test_horizontal_bars_keep_their_names_whole():
    _, ax = drawn(WORDS, horizontal=True)
    names = [t.get_text() for t in ax.get_yticklabels() if t.get_text()]
    assert all("\n" not in name for name in names)


def test_curves_have_numbers_on_x_and_are_not_touched():
    figure = Figure(figsize=get_theme("Nature").figsize("single"))
    spec = PlotSpec(theme="Nature", plot_type="line", x="Temps (h)",
                    y=["Contrôle"])
    plotting.render(figure, spec, demo.growth().df)
    assert plotting.fit_category_labels(figure.axes[0], spec) == ""


def test_contingency_bars_with_long_arm_names():
    figure = Figure(figsize=get_theme("Nature").figsize("single"), dpi=150)
    plotting.render(figure, PlotSpec(
        theme="Nature", plot_type="contingency", group="Traitement",
        y=["Répondeurs", "Non-répondeurs"], stats_enabled=True),
        demo.contingency().df)
    figure.savefig(os.devnull, format="png")
    assert not collide(figure.axes[0])
    assert overflow(figure) < 0.01          # legend beside the plot included


def test_each_panel_of_a_composite_figure_fits_its_own_tile():
    frames = {"T": long_format(WORDS)}
    specs = {name: PlotSpec(name=name, plot_type=kind, dataset="T",
                            group="Groupe", y=["Valeur"], theme="Nature")
             for name, kind in (("P1", "bar"), ("P2", "box"), ("P3", "bar"))}
    figure = Figure(figsize=(7.0, 2.7), dpi=150)
    render_panel(figure, Panel(name="F", plots=list(specs)), specs, frames)
    figure.savefig(os.devnull, format="png")
    for ax in figure.axes:
        assert not collide(ax)


# --------------------------------------------------------------------------
# The theme survives until the figure is drawn
# --------------------------------------------------------------------------
def test_the_journal_font_reaches_the_drawn_figure():
    expected = installed_fonts(tuple(get_theme("Nature").font_family))[0]
    figure, ax = drawn(["A", "B"])
    for text in (ax.get_yticklabels()[1], labels_of(ax)[0], ax.yaxis.label):
        assert text.get_fontname() == expected, text.get_text()


def test_the_ticks_drawn_are_the_ticks_laid_out():
    """The number of ticks follows the label size: it must not change."""
    spec = PlotSpec(theme="Nature", plot_type="bar", group="Groupe",
                    y=["Valeur"])
    theme = get_theme("Nature")
    figure = Figure(figsize=theme.figsize("single"), dpi=150)
    plotting.render(figure, spec, long_format(["Contrôle", "Inhibiteur"]))
    with mpl.rc_context(theme.rc()):            # as the layout saw them
        laid_out = list(figure.axes[0].get_yticks())
    figure.savefig(os.devnull, format="png")    # as the export draws them
    assert list(figure.axes[0].get_yticks()) == laid_out
    tick = figure.axes[0].yaxis.get_major_ticks()[0]
    assert tick.label1.get_fontsize() == get_theme("Nature").base_size


def test_only_installed_fonts_are_asked_for():
    fonts = installed_fonts(("Police imaginaire", "DejaVu Sans"))
    assert fonts == ["DejaVu Sans"]
    assert installed_fonts(("Police imaginaire",)) == ["DejaVu Sans"]


# --------------------------------------------------------------------------
# Exported files
# --------------------------------------------------------------------------
@pytest.fixture
def figure():
    figure = Figure(figsize=get_theme("Nature").figsize("single"))
    plotting.render(figure, PlotSpec(
        theme="Nature", plot_type="bar", group="Traitement",
        y=["Viabilité"], ylabel="Viabilité (%)", stats_enabled=True),
        demo.viability().df)
    return figure


def test_svg_text_stays_text(figure, tmp_path):
    path = export.save_figure(figure, export.ExportOptions(
        str(tmp_path / "f"), "SVG (vectoriel, éditable)"))
    svg = open(path, encoding="utf-8").read()
    assert svg.count("<text") > 10, "le texte a été converti en contours"
    assert "Viabilité (%)" in svg


def test_pdf_embeds_truetype_not_type3(figure, tmp_path):
    path = export.save_figure(figure, export.ExportOptions(
        str(tmp_path / "f"), "PDF (vectoriel, publication)"))
    pdf = open(path, "rb").read()
    assert b"/Type3" not in pdf
    expected = installed_fonts(tuple(get_theme("Nature").font_family))[0]
    fonts = re.findall(rb"/BaseFont /[A-Z]{6}\+([A-Za-z-]+)", pdf)
    assert fonts and all(expected.replace(" ", "").encode() in f
                         for f in fonts), fonts


def test_the_clipboard_copies_keep_editable_text(figure):
    assert export.figure_to_svg_text(figure).count("<text") > 10
