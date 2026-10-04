"""Bland-Altman agreement, checked against the paper that defined it.

Bland & Altman (Lancet 1986) compared two peak flow meters on 17 subjects
and published a bias of -2.1 l/min with an SD of 38.8, and limits of
agreement of -79.7 to 75.5 (they used 2 SD, not 1.96). The same data are
the example shipped with Plotea; the tests ask for those numbers back, and
for the bias's interval and p-value to equal those of the paired t test
SciPy computes on its own.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats as sps

from plotea.core import demo, plotting
from plotea.core import stats as st
from plotea.core.methods import methods_text
from plotea.core.plotspec import PlotSpec

WRIGHT = np.array(demo.PEAK_FLOW["Wright"], dtype=float)
MINI = np.array(demo.PEAK_FLOW["Mini-Wright"], dtype=float)


# --------------------------------------------------------------------------
# The 1986 paper
# --------------------------------------------------------------------------
def test_the_published_bias_and_standard_deviation():
    result = st.bland_altman(WRIGHT, MINI)
    assert result["n"] == 17
    assert result["bias"] == pytest.approx(-2.1, abs=0.05)
    assert result["sd"] == pytest.approx(38.8, abs=0.05)


def test_the_published_limits_with_their_two_standard_deviations():
    result = st.bland_altman(WRIGHT, MINI, z=2.0)
    # the paper rounded the bias and SD before computing the limits
    assert result["low"] == pytest.approx(-79.7, abs=0.15)
    assert result["high"] == pytest.approx(75.5, abs=0.15)


def test_the_bias_interval_and_p_are_those_of_the_paired_t_test():
    result = st.bland_altman(WRIGHT, MINI)
    paired = sps.ttest_rel(WRIGHT, MINI)
    interval = paired.confidence_interval(0.95)
    assert result["bias_ci"] == pytest.approx((interval.low, interval.high))
    assert result["p"] == pytest.approx(paired.pvalue)


def test_each_limit_is_known_sqrt3_times_less_precisely_than_the_bias():
    result = st.bland_altman(WRIGHT, MINI)
    bias_half = (result["bias_ci"][1] - result["bias_ci"][0]) / 2
    for key in ("low_ci", "high_ci"):
        half = (result[key][1] - result[key][0]) / 2
        assert half == pytest.approx(np.sqrt(3) * bias_half)


def test_the_difference_as_a_percentage_of_the_mean():
    result = st.bland_altman(WRIGHT, MINI, percent=True)
    expected = 100 * (WRIGHT - MINI) / ((WRIGHT + MINI) / 2)
    assert result["diff"] == pytest.approx(expected)
    assert result["bias"] == pytest.approx(expected.mean())


def test_fewer_than_three_subjects_give_no_limits():
    result = st.bland_altman([1.0, 2.0], [1.5, 2.5])
    assert np.isnan(result["bias"])


# --------------------------------------------------------------------------
# The plot
# --------------------------------------------------------------------------
def render(df=None, **fields):
    figure = Figure()
    spec = PlotSpec(plot_type="bland_altman", **fields)
    info = plotting.render(figure, spec,
                           demo.agreement().df if df is None else df)
    return figure.axes[0], info


def test_lines_at_the_bias_and_the_limits_with_their_labels():
    ax, info = render(y=["Wright", "Mini-Wright"])
    result = info.bland_altman
    levels = {round(line.get_ydata()[0], 6) for line in ax.lines}
    for key in ("bias", "low", "high"):
        assert round(result[key], 6) in levels
    labels = [t.get_text() for t in ax.texts]
    assert f"Biais {result['bias']:.3g}" in labels
    assert f"-1.96 SD {result['low']:.3g}" in labels
    assert f"+1.96 SD {result['high']:.3g}" in labels
    points = ax.collections[0].get_offsets()
    assert len(points) == 17
    assert np.allclose(points[:, 0], (WRIGHT + MINI) / 2)
    assert np.allclose(points[:, 1], WRIGHT - MINI)
    assert ax.get_xlabel() == "Moyenne de Wright et Mini-Wright"
    assert ax.get_ylabel() == "Wright - Mini-Wright"


def test_confidence_bands_are_drawn_whole():
    ax, info = render(y=["Wright", "Mini-Wright"], ba_ci=True)
    low, high = ax.get_ylim()
    assert low <= info.bland_altman["low_ci"][0]
    assert high >= info.bland_altman["high_ci"][1]
    assert len(ax.patches) == 3                    # bias + two limits


def test_long_format_gives_the_same_answer():
    df = demo.agreement().df.melt(id_vars="Sujet", var_name="Méthode",
                                  value_name="DEP")
    _ax, info = render(df, group="Méthode", y=["DEP"],
                       stats_pair_by="Sujet")
    _ax, wide = render(y=["Wright", "Mini-Wright"])
    assert info.bland_altman["bias"] == pytest.approx(
        wide.bland_altman["bias"])


@pytest.mark.parametrize("df, fields, says", [
    (None, dict(y=["Wright"]), "exactement deux"),
    (demo.agreement().df.assign(Autre=WRIGHT + 1),
     dict(y=["Wright", "Mini-Wright", "Autre"]), "exactement deux"),
    ("long", dict(group="Méthode", y=["DEP"]), "Appariement"),
    (pd.DataFrame({"A": [1.0, 2.0], "B": [1.1, 2.1]}), dict(y=["A", "B"]),
     "trois sujets"),
])
def test_what_cannot_be_drawn_says_why(df, fields, says):
    if isinstance(df, str):
        df = demo.agreement().df.melt(id_vars="Sujet", var_name="Méthode",
                                      value_name="DEP")
    _ax, info = render(df, **fields)
    assert any(says in w for w in info.warnings), info.warnings


def test_the_effects_rows_and_the_methods_paragraph():
    _ax, info = render(y=["Wright", "Mini-Wright"], ba_ci=True)
    measures = [row["Mesure"] for row in info.agreement]
    assert measures[:4] == ["Biais (moyenne des différences)",
                            "Écart-type des différences",
                            "Limite d'agrément basse",
                            "Limite d'agrément haute"]
    spec = PlotSpec(plot_type="bland_altman", y=["Wright", "Mini-Wright"],
                    ba_ci=True)
    text = methods_text(spec, info, "en")
    assert "Agreement between Wright and Mini-Wright" in text
    assert "(n = 17)" in text and "Bland and Altman (1999)" in text
    assert "La concordance entre Wright et Mini-Wright" in methods_text(
        spec, info, "fr")


def test_the_settings_survive_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="BA", plot_type="bland_altman",
                              ba_view="percent", ba_ci=True))
    spec = Project.load(project.save(str(tmp_path / "b.plotea"))).plots[-1]
    assert (spec.plot_type, spec.ba_view, spec.ba_ci) == \
        ("bland_altman", "percent", True)


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_window_maps_two_methods_and_shows_the_agreement(window):
    window.load_example("Deux débitmètres (Bland-Altman)")
    for button in window.inspector.type_buttons.buttons():
        if button.property("plot_type") == "bland_altman":
            button.click()
    spec = window.current_spec()
    assert (spec.group, spec.y, spec.stats_pair_by) == \
        ("", ["Wright", "Mini-Wright"], "Sujet")
    inspector = window.inspector
    assert inspector.cmb_test.isHidden() and inspector.chk_stats.isHidden()
    assert not inspector.cmb_ba_view.isHidden()
    window._render_now()
    panel = window.stats_panel
    assert "Biais -2.12" in panel.header.text()
    assert panel.tabs.isTabVisible(panel.tabs.indexOf(panel.effects))
