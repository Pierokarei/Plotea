"""Area under the curve: trapezoids, baselines, Bailer's standard error.

Checked against what can be computed another way - numpy's trapezoids,
areas worked out by hand where the curve crosses its baseline, the
standard error written out from Bailer's formula - and, for the interval,
by simulation: a 95 % interval must cover the true area about 95 times in
100. Then what a glucose tolerance test needs: one area per mouse, and the
groups compared on those.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea.core import auc, demo, plotting
from plotea.core.methods import methods_text
from plotea.core.plotspec import PlotSpec

TIMES = np.array([0, 15, 30, 60, 90, 120.0])
CURVE = np.array([100, 250, 230, 170, 130, 115.0])


def replicates(n=4, sd=20.0, seed=1):
    rng = np.random.default_rng(seed)
    return (np.repeat(TIMES, n),
            np.repeat(CURVE, n) + rng.normal(0, sd, TIMES.size * n))


# --------------------------------------------------------------------------
# The area
# --------------------------------------------------------------------------
def test_the_area_is_the_trapezoids_of_the_means():
    x, y = replicates()
    xs, means, _, _ = auc.means_by_x(x, y)
    found = auc.area(x, y)
    assert found.net == pytest.approx(np.trapezoid(means, xs))
    assert found.points == 6
    assert (found.peak_x, found.peak_y) == (15.0, pytest.approx(means[1]))


def test_crossing_the_baseline_is_cut_where_it_crosses():
    # (0, 1) to (1, -1): two triangles of a quarter each
    found = auc.area([0, 1], [1, -1])
    assert (found.above, found.below, found.net) == pytest.approx(
        (0.25, 0.25, 0.0))
    # from Y = 2 the line 0..4 over 0..4 is below for half, above for half
    found = auc.area([0, 4], [0, 4], "value", 2.0)
    assert (found.above, found.below) == pytest.approx((2.0, 2.0))


def test_the_first_value_as_baseline_is_the_incremental_area():
    x, y = replicates()
    xs, means, _, _ = auc.means_by_x(x, y)
    found = auc.area(x, y, "first")
    assert found.baseline == pytest.approx(means[0])
    assert found.net == pytest.approx(np.trapezoid(means - means[0], xs))


@pytest.mark.parametrize("baseline", ["zero", "first"])
def test_the_standard_error_is_bailers(baseline):
    """Var(sum c_i mean_i) = sum c_i^2 SEM_i^2, the c_i written out."""
    x, y = replicates()
    xs, _, sems, _ = auc.means_by_x(x, y)
    gaps = np.diff(xs)
    c = np.array([gaps[0] / 2] + [(gaps[i] + gaps[i + 1]) / 2
                                  for i in range(len(gaps) - 1)]
                 + [gaps[-1] / 2])
    if baseline == "first":
        c[0] -= xs[-1] - xs[0]          # the baseline, over the whole width
    found = auc.area(x, y, baseline)
    assert found.se == pytest.approx(np.sqrt(np.sum(c ** 2 * sems ** 2)))
    assert found.low < found.net < found.high


@pytest.mark.parametrize("baseline", ["zero", "first"])
def test_the_interval_covers_the_true_area_95_times_in_100(baseline):
    rng = np.random.default_rng(7)
    true = np.trapezoid(CURVE - (CURVE[0] if baseline == "first" else 0),
                        TIMES)
    runs, covered = 1500, 0
    for _ in range(runs):
        y = np.repeat(CURVE, 4) + rng.normal(0, 20, TIMES.size * 4)
        found = auc.area(np.repeat(TIMES, 4), y, baseline)
        covered += found.low <= true <= found.high
    # 1500 runs: 95 % +/- 1.1 % (one SD); sum(n - 1) degrees of freedom
    # gave 91 % with the first value as baseline
    assert 0.93 <= covered / runs <= 0.97


def test_without_replicates_there_is_an_area_but_no_error():
    found = auc.area(TIMES, CURVE)
    assert found.net == pytest.approx(np.trapezoid(CURVE, TIMES))
    assert np.isnan(found.se) and np.isnan(found.low)
    assert not auc.area([1, 1, 1], [2, 3, 4]).ok      # one X: no curve


# --------------------------------------------------------------------------
# On the plot
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tolerance():
    return demo.glucose_tolerance()


def render(table, **fields):
    spec = PlotSpec(**{**table.meta["plot"], **fields})
    figure = Figure(figsize=(4, 3))
    return spec, plotting.render(figure, spec, table.df), figure


def test_one_area_per_mouse(tolerance):
    spec, info, _ = render(tolerance)
    assert len(info.aucs) == 12
    row = info.aucs[0]
    assert (row["Régime"], row["Souris"]) == ("Standard", "S1")
    mouse = tolerance.df[tolerance.df["Souris"] == "S1"]
    assert row["Aire nette"] == pytest.approx(np.trapezoid(
        mouse["Glycémie (mg/dL)"], mouse["Temps (min)"]))
    assert "ES" not in row                # one mouse, no replicates


def test_one_area_per_curve_with_its_error(tolerance):
    _, info, _ = render(tolerance, auc_subject="")
    assert [r["Régime"] for r in info.aucs] == ["Standard",
                                                "Riche en graisses"]
    assert all(r["ES"] > 0 for r in info.aucs)
    assert info.aucs[1]["Aire nette"] > info.aucs[0]["Aire nette"]


def test_wide_tables_give_one_area_per_column():
    frame = pd.DataFrame({"t": TIMES, "A": CURVE, "B": CURVE * 2})
    info = plotting.render(Figure(), PlotSpec(
        plot_type="line", x="t", y=["A", "B"], auc=True), frame)
    assert [r["Série"] for r in info.aucs] == ["A", "B"]
    assert info.aucs[1]["Aire nette"] == pytest.approx(
        2 * info.aucs[0]["Aire nette"])


def test_the_area_can_be_shaded(tolerance):
    from matplotlib.collections import PolyCollection

    def shaded(figure):
        return [c for c in figure.axes[0].collections
                if type(c).__name__ == "FillBetweenPolyCollection"
                or isinstance(c, PolyCollection)]
    assert not shaded(render(tolerance)[2])
    assert len(shaded(render(tolerance, auc_shade=True)[2])) == 2


def test_the_methods_paragraph_says_how(tolerance):
    spec, info, _ = render(tolerance)
    text = methods_text(spec, info, "fr")
    assert "méthode des trapèzes à partir de Y = 0, une aire par Souris" \
        in text
    spec, info, _ = render(tolerance, auc_subject="",
                           auc_baseline="first")
    english = methods_text(spec, info, "en")
    assert "incremental area" in english and "Bailer" in english
    assert "Satterthwaite" in english


def test_the_settings_survive_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="G", auc=True, auc_baseline="value",
                              auc_baseline_value=90.0, auc_subject="Souris",
                              auc_shade=True))
    spec = Project.load(project.save(str(tmp_path / "g.plotea"))).plots[-1]
    assert (spec.auc, spec.auc_baseline, spec.auc_baseline_value,
            spec.auc_subject, spec.auc_shade) == (True, "value", 90.0,
                                                  "Souris", True)
    spec.dataset = "T"
    spec.rename_column("T", "Souris", "Animal")
    assert spec.auc_subject == "Animal"


# --------------------------------------------------------------------------
# In the window: from the curves to the comparison
# --------------------------------------------------------------------------
@pytest.fixture
def gtt(window):
    window.files.start_new()
    window.load_example("Tolérance au glucose (aire sous la courbe)")
    window._render_now()
    return window


def test_the_example_opens_with_its_areas(gtt):
    panel = gtt.stats_panel
    assert panel.tabs.isTabVisible(panel.tabs.indexOf(panel.areas))
    assert panel.areas.rowCount() == 12
    assert "Aire sous la courbe : 12 sujet(s)" in panel.header.text()


def test_the_groups_are_compared_on_the_areas(gtt):
    curves = gtt.current_spec()
    plots, tables = len(gtt.project.plots), len(gtt.project.datasets)
    assert gtt.inspector.btn_auc_table.isEnabled()
    gtt.inspector.btn_auc_table.click()
    gtt._render_now()

    bars = gtt.current_spec()
    assert bars is not curves and bars.plot_type == "bar"
    table = gtt.project.get_dataset(bars.dataset)
    assert list(table.df.columns[:3]) == ["Régime", "Souris", "Aire nette"]
    assert len(table.df) == 12
    info = gtt.canvas.last_info
    assert [str(g) for g in info.groups] == ["Standard", "Riche en graisses"]
    assert len(info.comparisons) == 1 and info.comparisons[0].p < 0.001
    # the curves stayed on their own table
    assert curves.dataset == "Tolérance au glucose"

    gtt.undo()
    assert (len(gtt.project.plots), len(gtt.project.datasets)) == (
        plots, tables)


def test_the_button_waits_for_a_subject_column(gtt):
    inspector = gtt.inspector
    inspector.cmb_auc_subject.setCurrentIndex(0)          # none
    assert gtt.current_spec().auc_subject == ""
    assert not inspector.btn_auc_table.isEnabled()
    gtt.compare_aucs()                                    # and says why
    assert "sujets" in gtt.statusBar().currentMessage()
