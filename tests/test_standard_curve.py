"""Standard curves: reading the concentration of unknowns off a fitted curve.

What a lab does with an ELISA, a Bradford or a qPCR standard curve, laid
out as Prism does: standards and samples in one XY table, the samples' X
left empty. The values are checked against what can be computed another
way - the 4PL solved for X, the textbook calibration interval of a straight
line - and the report against what a plate gives: replicates, dilutions,
samples beyond the standards.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

from plotea.core import demo, fitting, plotting
from plotea.core.methods import methods_text
from plotea.core.plotspec import PlotSpec

RNG = np.random.default_rng(4)
STANDARDS = np.repeat([7.8, 15.6, 31.25, 62.5, 125, 250, 500, 1000.0], 2)


def four_pl(x, bottom=0.05, top=2.4, ec50=180.0, hill=1.1):
    return bottom + (top - bottom) / (1 + (ec50 / x) ** hill)


def fitted(x, y, model):
    result = fitting.fit(x, y, model)
    assert result.ok, result.message
    return result


# --------------------------------------------------------------------------
# Reading the curve backwards
# --------------------------------------------------------------------------
def test_a_straight_line_gives_the_textbook_calibration_interval():
    """The 95 % interval where y0 meets the confidence band of the line:
    (y0 - a X - b)^2 = t^2 s^2 (1/n + (X - mean x)^2 / Sxx), solved for X
    (Draper & Smith, inverse prediction from the regression line)."""
    x = np.repeat([0, 2, 4, 6, 8, 10.0], 3)
    y = 0.12 * x + 0.05 + RNG.normal(0, 0.02, x.size)
    result = fitted(x, y, "linear")
    a, b = result.params["a"], result.params["b"]
    y0 = 0.7
    found = fitting.inverse(result, y0)

    n = x.size
    s2 = np.sum((y - (a * x + b)) ** 2) / (n - 2)
    sxx = np.sum((x - x.mean()) ** 2)
    t = stats.t.ppf(0.975, n - 2)
    roots = sorted(np.roots([
        a * a - t * t * s2 / sxx,
        -2 * a * (y0 - b) + 2 * t * t * s2 * x.mean() / sxx,
        (y0 - b) ** 2 - t * t * s2 * (1 / n + x.mean() ** 2 / sxx)]).real)
    assert found.status == "ok"
    assert found.x == pytest.approx((y0 - b) / a, rel=1e-9)
    assert (found.low, found.high) == pytest.approx(roots, rel=1e-7)


@pytest.mark.parametrize("y0", [0.3, 1.0, 2.0])
def test_the_4pl_is_solved_for_x(y0):
    y = four_pl(STANDARDS) + RNG.normal(0, 0.02, STANDARDS.size)
    result = fitted(STANDARDS, y, "hill4")
    p = result.params
    exact = p["EC50"] / ((p["Haut"] - p["Bas"]) / (y0 - p["Bas"]) - 1) \
        ** (1 / p["Hill"])
    found = fitting.inverse(result, y0)
    assert found.x == pytest.approx(exact, rel=1e-8)
    assert found.low < found.x < found.high


def test_a_decreasing_curve_is_read_the_same_way():
    """Competitive ELISA: more analyte, less signal."""
    y = 2.45 - four_pl(STANDARDS) + RNG.normal(0, 0.02, STANDARDS.size)
    result = fitted(STANDARDS, y, "hill4")
    found = fitting.inverse(result, 1.2)
    assert found.status == "ok"
    reached = fitting.MODELS["hill4"].func(found.x, *result.popt)
    assert float(reached) == pytest.approx(1.2, abs=1e-9)
    assert found.low < found.x < found.high
    # high signal: less analyte than the lowest standard
    assert fitting.inverse(result, 2.6).status == "below"
    assert fitting.inverse(result, 0.0).status == "above"


def test_nothing_is_extrapolated_beyond_the_standards():
    y = four_pl(STANDARDS) + RNG.normal(0, 0.02, STANDARDS.size)
    result = fitted(STANDARDS, y, "hill4")
    assert fitting.inverse(result, 0.01).status == "below"
    assert fitting.inverse(result, 3.0).status == "above"
    assert np.isnan(fitting.inverse(result, 3.0).x)


def test_a_curve_reaching_a_value_twice_gives_no_answer():
    x = np.linspace(-3, 3, 13)
    result = fitted(x, x ** 2, "poly2")
    assert fitting.inverse(result, 4.0).status == "ambiguous"
    assert fitting.inverse(None, 1.0).status == "none"
    assert fitting.inverse(result, float("nan")).status == "none"


def test_near_the_end_of_the_standards_the_interval_stays_open():
    y = four_pl(STANDARDS) + RNG.normal(0, 0.02, STANDARDS.size)
    result = fitted(STANDARDS, y, "hill4")
    found = fitting.inverse(result, float(four_pl(8.5)))
    assert found.status == "ok" and np.isnan(found.low)
    assert found.high > found.x


# --------------------------------------------------------------------------
# A plate: standards, samples, replicates, dilutions
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def plate():
    ds = demo.standard_curve()
    spec = PlotSpec(**ds.meta["plot"])
    figure = Figure(figsize=(4, 3))
    info = plotting.render(figure, spec, ds.df)
    return ds, spec, info, figure


def rows_by_name(info):
    return {row["Échantillon"]: row for row in info.interpolations}


def test_the_samples_are_the_rows_without_x(plate):
    ds, spec, info, _ = plate
    rows = rows_by_name(info)
    assert list(rows) == [f"Sérum {i}" for i in range(1, 8)]
    assert all(row["n"] == 2 for row in rows.values())
    first = ds.df[ds.df["Échantillon"] == "Sérum 1"]["DO 450 nm"]
    assert rows["Sérum 1"]["Y moyen"] == pytest.approx(first.mean())
    assert rows["Sérum 1"]["CV (%)"] == pytest.approx(
        first.std(ddof=1) / first.mean() * 100)


def test_the_concentrations_come_back(plate):
    """The demo plate was made from known concentrations."""
    _, spec, info, _ = plate
    rows = rows_by_name(info)
    truth = {"Sérum 1": 45, "Sérum 2": 210, "Sérum 3": 640,
             "Sérum 4": 380, "Sérum 5": 95}
    for name, value in truth.items():
        assert rows[name]["Concentration"] == pytest.approx(value, rel=0.12)
        assert rows[name]["Remarque"] == ""


def test_the_dilution_multiplies_value_and_interval(plate):
    _, spec, info, _ = plate
    row = rows_by_name(info)["Sérum 4"]
    assert row["Dilution"] == 10
    assert row["Concentration"] == pytest.approx(10 * row[spec.x])
    assert row["IC 95 % bas"] < row["Concentration"] < row["IC 95 % haut"]
    assert row[spec.x] < 125                 # read low on the curve


def test_samples_beyond_the_standards_say_so(plate):
    _, _, info, _ = plate
    rows = rows_by_name(info)
    assert np.isnan(rows["Sérum 6"]["Concentration"])
    assert rows["Sérum 6"]["Remarque"] == "Au-dessus de la gamme (> 1000)"
    assert rows["Sérum 7"]["Remarque"] == "Sous la gamme (< 7.8)"


def test_the_samples_do_not_change_the_curve(plate):
    ds, spec, info, _ = plate
    standards = ds.df[ds.df[spec.x].notna()]
    alone = plotting.render(Figure(), spec, standards)
    assert alone.fits["DO 450 nm"].params == pytest.approx(
        info.fits["DO 450 nm"].params)
    assert alone.interpolations == []
    assert any("Aucune inconnue" in w for w in alone.warnings)


def test_the_samples_are_marked_on_the_curve(plate):
    ds, spec, info, figure = plate
    from matplotlib.collections import PathCollection

    drawn = [c for c in figure.axes[0].collections
             if isinstance(c, PathCollection)
             and c.get_offsets().shape == (1, 2)]
    ok = [r for r in info.interpolations if not r["Remarque"]]
    assert len(drawn) == len(ok)
    centres = sorted(tuple(c.get_offsets()[0]) for c in drawn)
    expected = sorted((r[spec.x], r["Y moyen"]) for r in ok)
    assert np.allclose(centres, expected)


def test_without_names_each_row_is_its_own_sample():
    frame = pd.DataFrame({"X": [1, 2, 3, 4, 5, None, None],
                          "Y": [2.1, 3.9, 6.2, 7.8, 10.1, 5.0, 9.0]})
    info = plotting.render(Figure(), PlotSpec(
        plot_type="scatter", x="X", y=["Y"], fit_model="linear",
        interpolate=True), frame)
    assert [r["Échantillon"] for r in info.interpolations] == \
        ["Ligne 6", "Ligne 7"]
    assert "Dilution" not in info.interpolations[0]
    assert "Concentration" not in info.interpolations[0]


def test_each_series_is_read_on_its_own_curve():
    """Two plates in one table: a sample is read on its plate's curve."""
    x = [10, 50, 100, 200, None] * 2
    y = [1.0, 5.0, 10.0, 20.0, 8.0, 2.0, 10.0, 20.0, 40.0, 8.0]
    frame = pd.DataFrame({"Plaque": ["P1"] * 5 + ["P2"] * 5, "X": x,
                          "Y": y})
    info = plotting.render(Figure(), PlotSpec(
        plot_type="scatter", x="X", y=["Y"], group="Plaque",
        fit_model="linear", interpolate=True), frame)
    found = {r["Série"]: r["X"] for r in info.interpolations}
    assert found["P1"] == pytest.approx(80.0, rel=1e-6)
    assert found["P2"] == pytest.approx(40.0, rel=1e-6)


def test_log_concentration_curves_report_the_concentration():
    """With X = log10(C), the curve gives log10(C): the report gives C."""
    logc = np.log10(STANDARDS)
    y = four_pl(STANDARDS) + RNG.normal(0, 0.02, STANDARDS.size)
    frame = pd.DataFrame({"logC": list(logc) + [np.nan],
                          "Y": list(y) + [1.0]})
    info = plotting.render(Figure(), PlotSpec(
        plot_type="scatter", x="logC", y=["Y"], fit_model="hill4_log",
        interpolate=True), frame)
    row = info.interpolations[0]
    assert row["Concentration"] == pytest.approx(10 ** row["logC"])
    assert row["IC 95 % bas"] < row["Concentration"] < row["IC 95 % haut"]


def test_the_methods_paragraph_says_how(plate):
    _, spec, info, _ = plate
    assert "dosés sur la gamme étalon" in methods_text(spec, info, "fr")
    english = methods_text(spec, info, "en")
    assert "multiplied by the dilution factor" in english
    assert "without extrapolation" in english


def test_the_settings_survive_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="E", interpolate=True,
                              interp_label="Puits", interp_factor="Dil"))
    spec = Project.load(project.save(str(tmp_path / "e.plotea"))).plots[-1]
    assert (spec.interpolate, spec.interp_label, spec.interp_factor) == (
        True, "Puits", "Dil")


def test_renaming_the_name_column_is_followed():
    spec = PlotSpec(dataset="T", interp_label="Puits", interp_factor="Dil")
    spec.rename_column("T", "Puits", "Échantillon")
    spec.rename_column("T", "Dil", "Dilution")
    assert (spec.interp_label, spec.interp_factor) == ("Échantillon",
                                                       "Dilution")


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_example_opens_with_its_assay(window):
    window.files.start_new()
    window.load_example("Dosage ELISA (gamme étalon)")
    window._render_now()
    panel = window.stats_panel
    tab = panel.tabs.indexOf(panel.assay)
    assert panel.tabs.isTabVisible(tab)
    assert panel.assay.rowCount() == 7
    assert "Dosage : 7 échantillon(s), 2 sans concentration" in \
        panel.header.text()
    panel.tabs.setCurrentIndex(tab)
    assert panel._current_rows()[0]["Échantillon"] == "Sérum 1"


def test_the_controls_wake_with_a_curve(window):
    window.files.start_new(with_example=True)
    spec = window.current_spec()
    spec.plot_type = "scatter"
    window._sync_inspector()
    inspector = window.inspector
    assert not inspector.chk_interp.isEnabled()
    spec.fit_model = "linear"
    window._sync_inspector()
    assert inspector.chk_interp.isEnabled()
    assert not inspector.cmb_interp_label.isEnabled()
    inspector.chk_interp.setChecked(True)
    assert spec.interpolate and inspector.cmb_interp_label.isEnabled()
    labels = [inspector.cmb_interp_label.itemText(i)
              for i in range(inspector.cmb_interp_label.count())]
    assert "Traitement" in labels
