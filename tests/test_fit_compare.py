"""Comparing fitted curves: does a parameter differ between the series?

The extra sum-of-squares F test is checked against an algebra that shares
nothing with it: on straight lines, a common slope, a common intercept or a
single line for all series is an analysis of covariance that ordinary least
squares solves exactly. The nonlinear optimiser must land on the same F.
On dose-response curves, it must find the EC50 that differs, leave alone
the slope that does not, and - over many datasets where nothing differs -
cry wolf about as often as its 5 % promises.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

from plotea.core import demo, plotting
from plotea.core import fitting as ft
from plotea.core.plotspec import PlotSpec

X = np.repeat(np.arange(1, 9, dtype=float), 3)


def lines(seed=4, slopes=(1.0, 1.4), intercepts=(2.0, 3.0)):
    rng = np.random.default_rng(seed)
    return {name: (X, b + a * X + rng.normal(0, 0.8, X.size))
            for name, a, b in zip("ABC", slopes, intercepts)}


def ols_f(series, reduced):
    """F of a nested comparison of linear models, by plain least squares."""
    labels = list(series)
    x = np.concatenate([series[k][0] for k in labels])
    y = np.concatenate([series[k][1] for k in labels])
    group = np.concatenate([[i] * series[k][0].size
                            for i, k in enumerate(labels)])
    dummies = np.column_stack([(group == i).astype(float)
                               for i in range(len(labels))])
    full = np.column_stack([dummies, dummies * x[:, None]])
    small = {"a": np.column_stack([dummies, x]),            # common slope
             "b": np.column_stack([np.ones_like(x), dummies * x[:, None]]),
             ft.ONE_CURVE: np.column_stack([np.ones_like(x), x])}[reduced]

    def rss(design):
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        return float(np.sum((y - design @ beta) ** 2))

    df_num = full.shape[1] - small.shape[1]
    df_den = y.size - full.shape[1]
    F = ((rss(small) - rss(full)) / df_num) / (rss(full) / df_den)
    return F, df_num, df_den, stats.f.sf(F, df_num, df_den)


# --------------------------------------------------------------------------
# Against ordinary least squares
# --------------------------------------------------------------------------
@pytest.mark.parametrize("shared", ["a", "b", ft.ONE_CURVE])
def test_lines_agree_with_the_analysis_of_covariance(shared):
    series = lines()
    result = ft.compare_fits(series, "linear", shared)
    F, df_num, df_den, p = ols_f(series, shared)
    assert result.ok, result.message
    assert (result.df_num, result.df_den) == (df_num, df_den)
    assert result.F == pytest.approx(F, rel=1e-8)
    assert result.p == pytest.approx(p, rel=1e-6)


def test_three_series_agree_too():
    series = lines(slopes=(1.0, 1.4, 1.1), intercepts=(2.0, 3.0, 2.5))
    result = ft.compare_fits(series, "linear", "a")
    F, df_num, df_den, _p = ols_f(series, "a")
    assert (result.df_num, result.df_den) == (2, df_den) == (df_num, df_den)
    assert result.F == pytest.approx(F, rel=1e-8)


def test_the_order_of_the_series_does_not_matter():
    series = lines()
    reverse = dict(reversed(list(series.items())))
    assert ft.compare_fits(series, "linear", "a").F == pytest.approx(
        ft.compare_fits(reverse, "linear", "a").F, rel=1e-9)


# --------------------------------------------------------------------------
# Dose-response
# --------------------------------------------------------------------------
LOG_DOSE = np.repeat(np.linspace(-9, -5, 9), 3)


def hill(log_ec50, slope=1.0):
    return 5 + 95 / (1 + 10 ** ((log_ec50 - LOG_DOSE) * slope))


def dose_response(rng, ec50s, noise=4.0):
    return {name: (LOG_DOSE, hill(e) + rng.normal(0, noise, LOG_DOSE.size))
            for name, e in zip(("A", "B"), ec50s)}


def test_a_different_ec50_is_found_and_a_shared_slope_is_not_flagged():
    series = dose_response(np.random.default_rng(4), (-7.0, -6.5))
    ec50 = ft.compare_fits(series, "hill4_log", "logEC50")
    slope = ft.compare_fits(series, "hill4_log", "Hill")
    assert ec50.differs and ec50.p < 1e-6
    assert not slope.differs and slope.p > 0.05
    assert set(ec50.free) == {"A", "B"}
    assert ec50.free["A"]["logEC50"] == pytest.approx(-7.0, abs=0.1)
    assert ec50.free["B"]["logEC50"] == pytest.approx(-6.5, abs=0.1)


def test_when_nothing_differs_it_cries_wolf_about_five_percent_of_the_time():
    rng = np.random.default_rng(2026)
    runs = 120
    false_alarms = sum(
        ft.compare_fits(dose_response(rng, (-7.0, -7.0)), "hill4_log",
                        "logEC50").differs
        for _ in range(runs))
    assert 1 <= false_alarms <= 12, f"{false_alarms}/{runs}"


def test_far_apart_curves_take_the_best_of_several_starts():
    """The constrained error has a hollow near each series: the deepest
    one is kept, whichever the optimiser met first."""
    df = demo.dose_response().df
    series = {g: (sub["log[C] (M)"].to_numpy(float),
                  sub["Réponse (%)"].to_numpy(float))
              for g, sub in df.groupby("Composé")}
    result = ft.compare_fits(series, "hill4_log", "logEC50")
    model = ft.MODELS["hill4_log"]
    worse = []
    for common in (-7.2, -6.6):
        total = 0.0
        for label, (x, y) in series.items():
            own = result.free[label]
            popt, _ = ft.curve_fit(
                lambda xs, b, t, h: model.func(xs, b, t, common, h), x, y,
                p0=[own["Bas"], own["Haut"], own["Hill"]], maxfev=20000)
            total += float(np.sum(
                (y - model.func(x, popt[0], popt[1], common, popt[2])) ** 2))
        worse.append(total)
    assert result.ss_shared <= min(worse) + 1e-6


# --------------------------------------------------------------------------
# What cannot be compared
# --------------------------------------------------------------------------
@pytest.mark.parametrize("series, model, shared, says", [
    ({"A": (X, X)}, "linear", "a", "au moins deux"),
    ({"A": ([1, 2], [1, 2]), "B": ([1, 2, 3], [1, 2, 3])}, "linear", "a",
     "Pas assez de points"),
    (lines(), "linear", "logEC50", "inconnu"),
    (lines(), "none", "a", "modèle"),
])
def test_what_cannot_be_compared_says_why(series, model, shared, says):
    result = ft.compare_fits(series, model, shared)
    assert not result.ok and says in result.message


# --------------------------------------------------------------------------
# On the plot
# --------------------------------------------------------------------------
def dose_spec(**fields):
    return PlotSpec(plot_type="line", x="log[C] (M)", y=["Réponse (%)"],
                    group="Composé", fit_model="hill4_log", **fields)


def test_every_replicate_is_compared_not_the_means():
    df = demo.dose_response().df
    info = plotting.render(Figure(), dose_spec(fit_compare="logEC50"), df)
    comparison = info.fit_comparison
    assert comparison.ok
    per_series = df.groupby("Composé").size().to_dict()
    assert comparison.n == per_series            # 33 each, not 11 means
    # and the curves drawn are fitted to the same points: same values
    for label, res in info.fits.items():
        assert res.n == per_series[label]
        assert res.params["logEC50"] == pytest.approx(
            comparison.free[label]["logEC50"], rel=1e-6)


def test_drawn_curves_follow_the_replicates_not_the_means():
    """Unequal replicates: fitting the means would weigh a dose measured
    once like one measured five times. The curve must follow the points."""
    x = np.array([1, 1, 1, 1, 1, 2, 3, 3, 3, 4, 5, 5], dtype=float)
    y = np.array([1.0, 1.4, 0.6, 1.2, 0.8, 3.1, 2.4, 3.0, 2.7, 4.2, 4.6,
                  5.4])
    df = pd.DataFrame({"x": x, "y": y})
    spec = PlotSpec(plot_type="line", x="x", y=["y"], fit_model="linear",
                    error_type="sem")
    drawn = plotting.render(Figure(), spec, df).fits["y"]
    on_points = ft.fit(x, y, "linear")
    means = df.groupby("x")["y"].mean()
    on_means = ft.fit(means.index.to_numpy(), means.to_numpy(), "linear")
    assert drawn.n == x.size
    assert drawn.params["a"] == pytest.approx(on_points.params["a"])
    assert drawn.params["a"] != pytest.approx(on_means.params["a"], rel=1e-3)
    # the points on the plot are still the means with their error bars
    assert plotting.extract_xy(df, spec)[0].x.size == means.size


def test_the_verdict_is_written_on_the_figure():
    figure = Figure()
    info = plotting.render(figure, dose_spec(fit_compare="logEC50"),
                           demo.dose_response().df)
    texts = " ".join(t.get_text() for t in figure.axes[0].texts)
    assert "logEC50 : F(1, 58)" in texts
    assert plotting.comparison_line(info.fit_comparison) in texts


def test_no_comparison_unless_asked():
    info = plotting.render(Figure(), dose_spec(), demo.dose_response().df)
    assert info.fit_comparison is None


def test_the_choice_survives_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(dose_spec(name="EC50", fit_compare="logEC50"))
    spec = Project.load(project.save(str(tmp_path / "f.plotea"))).plots[-1]
    assert spec.fit_compare == "logEC50"


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_choices_follow_the_model(window):
    inspector = window.inspector
    window.load_example("Dose-réponse (fit 4PL)")
    for button in inspector.type_buttons.buttons():
        if button.property("plot_type") == "line":
            button.click()
    inspector.cmb_fit.setCurrentIndex(inspector.cmb_fit.findData("hill4_log"))
    keys = [inspector.cmb_fit_compare.itemData(i)
            for i in range(inspector.cmb_fit_compare.count())]
    assert keys == ["", ft.ONE_CURVE, "Bas", "Haut", "logEC50", "Hill"]

    inspector.cmb_fit_compare.setCurrentIndex(
        inspector.cmb_fit_compare.findData("logEC50"))
    assert window.current_spec().fit_compare == "logEC50"
    window._render_now()
    panel = window.stats_panel
    assert "logEC50 : F(1, 58)" in panel.header.text()
    assert "Comparaison des courbes" in panel.fits.toPlainText()
    assert "Conclusion : différent" in panel.fits.toPlainText()

    # a model without that parameter: the choice cannot survive
    inspector.cmb_fit.setCurrentIndex(inspector.cmb_fit.findData("linear"))
    assert window.current_spec().fit_compare == ""
    assert not window.canvas.last_info.warnings or all(
        "inconnu" not in w for w in window.canvas.last_info.warnings)


def test_two_y_columns_are_two_series_too():
    """Wide format: no group column, one Y column per series."""
    wide = pd.DataFrame({"x": X, "A": lines()["A"][1], "B": lines()["B"][1]})
    info = plotting.render(Figure(), PlotSpec(
        plot_type="scatter", x="x", y=["A", "B"], fit_model="linear",
        fit_compare="a"), wide)
    assert info.fit_comparison.ok and set(info.fit_comparison.n) == {"A", "B"}
