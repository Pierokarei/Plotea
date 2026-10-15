"""ROC curves: the area, its interval, the cut-off, two markers compared.

Checked against published data - the CT ratings of Hanley and McNeil
(Radiology 1982;143:29-36), whose area under the curve is 0.893 - against
the Mann-Whitney statistic the area is, against DeLong's placement values
computed pair by pair, and by simulation: the 95 % interval must cover the
true area about 95 times in 100, and the paired test must not find a
difference between equal markers more than about 5 times in 100.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

from plotea.core import demo, plotting, roc
from plotea.core.methods import methods_text
from plotea.core.plotspec import PlotSpec

#: Hanley & McNeil 1982, table 1: CT ratings 1 (definitely normal) to 5
#: (definitely abnormal) of 58 normal and 51 abnormal patients.
NORMAL = np.repeat([1, 2, 3, 4, 5.0], [33, 6, 6, 11, 2])
ABNORMAL = np.repeat([1, 2, 3, 4, 5.0], [3, 2, 2, 11, 33])


# --------------------------------------------------------------------------
# One marker
# --------------------------------------------------------------------------
def test_the_published_area_comes_back():
    found = roc.analyse(NORMAL, ABNORMAL)
    assert round(found.auc, 3) == 0.893
    # their standard error formula gives the 0.032 they report; DeLong's,
    # which makes no assumption on the shape, is close to it
    a, m, n = found.auc, ABNORMAL.size, NORMAL.size
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    hanley = np.sqrt((a * (1 - a) + (m - 1) * (q1 - a * a)
                      + (n - 1) * (q2 - a * a)) / (m * n))
    assert round(hanley, 3) == 0.032
    assert found.se == pytest.approx(hanley, abs=0.003)
    assert found.low < found.auc < found.high and found.p < 1e-10


def test_the_cut_off_and_what_it_gives():
    """Above 3.5 - "probably" or "definitely abnormal" - is positive."""
    found = roc.analyse(NORMAL, ABNORMAL)
    assert found.cutoff == 3.5
    assert found.sensitivity == pytest.approx(44 / 51)
    assert found.specificity == pytest.approx(45 / 58)
    assert found.sens_ci[0] < found.sensitivity < found.sens_ci[1]


def test_the_area_is_the_mann_whitney_statistic():
    rng = np.random.default_rng(2)
    neg = rng.integers(0, 8, 40).astype(float)        # ties on purpose
    pos = rng.integers(2, 10, 30).astype(float)
    u = stats.mannwhitneyu(pos, neg).statistic
    assert roc.analyse(neg, pos).auc == pytest.approx(u / (40 * 30))


def test_placement_values_from_ranks_are_delongs():
    """Midranks (Sun & Xu) give what comparing every pair gives."""
    rng = np.random.default_rng(3)
    neg = rng.integers(0, 6, 25).astype(float)
    pos = rng.integers(1, 8, 20).astype(float)
    psi = (pos[:, None] > neg[None, :]) + 0.5 * (pos[:, None] == neg[None, :])
    auc, v10, v01 = roc.placements(neg, pos)
    assert auc == pytest.approx(psi.mean())
    assert np.allclose(v10, psi.mean(axis=1))
    assert np.allclose(v01, psi.mean(axis=0))


def test_a_marker_lower_in_the_disease_is_read_in_reverse():
    found = roc.analyse(-NORMAL, -ABNORMAL)
    assert found.lower_is_positive
    assert found.auc == pytest.approx(0.8932, abs=1e-4)
    assert found.cutoff == -3.5


def test_the_curve_goes_from_corner_to_corner():
    found = roc.analyse(NORMAL, ABNORMAL)
    assert (found.fpr[0], found.tpr[0]) == (0, 0)
    assert (found.fpr[-1], found.tpr[-1]) == (1, 1)
    assert np.all(np.diff(found.fpr) >= 0) and np.all(np.diff(found.tpr) >= 0)
    # trapezoids under the empirical curve: the same area
    assert np.trapezoid(found.tpr, found.fpr) == pytest.approx(found.auc)


def test_wilson_intervals():
    """8 of 10: the textbook Wilson interval, 0.490 to 0.943."""
    low, high = roc.wilson(8, 10)
    assert (round(low, 3), round(high, 3)) == (0.490, 0.943)
    assert roc.wilson(10, 10)[1] == pytest.approx(1.0)


def test_too_few_subjects_give_nothing():
    assert not roc.analyse([1.0], [2.0, 3.0]).ok
    assert np.isnan(roc.analyse([1.0], [2.0, 3.0]).auc)


# --------------------------------------------------------------------------
# By simulation
# --------------------------------------------------------------------------
def test_the_interval_covers_and_the_paired_test_holds_its_level():
    rng = np.random.default_rng(11)
    true = stats.norm.cdf(1 / np.sqrt(2))        # N(0,1) against N(1,1)
    runs, covered, false_alarms = 800, 0, 0
    for _ in range(runs):
        x0, x1 = rng.normal(0, 1, 50), rng.normal(1, 1, 40)
        first = roc.analyse(x0, x1)
        covered += first.low <= true <= first.high
        # a second marker, correlated, with the same true area
        y0 = 0.6 * x0 + 0.8 * rng.normal(0, 1, 50)
        y1 = 0.6 * (x1 - 1) + 0.8 * rng.normal(0, 1, 40) + 1
        _, p = roc.compare(first, roc.analyse(y0, y1))
        false_alarms += p < 0.05
    assert 0.93 <= covered / runs <= 0.97
    assert 0.025 <= false_alarms / runs <= 0.075


def test_the_paired_test_sees_a_real_difference():
    rng = np.random.default_rng(5)
    x0, x1 = rng.normal(0, 1, 80), rng.normal(1.6, 1, 80)
    y0 = 0.5 * x0 + rng.normal(0, 1, 80)
    y1 = 0.5 * (x1 - 1.6) + rng.normal(0, 1, 80) + 0.6
    z, p = roc.compare(roc.analyse(x0, x1), roc.analyse(y0, y1))
    assert z > 0 and p < 0.01


# --------------------------------------------------------------------------
# On the plot
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def markers():
    table = demo.diagnostic()
    spec = PlotSpec(**table.meta["plot"])
    figure = Figure(figsize=(4, 3.4))
    return table, spec, plotting.render(figure, spec, table.df), figure


def test_three_markers_and_their_table(markers):
    _, _, info, figure = markers
    assert [r["Marqueur"] for r in info.rocs] == [
        "Troponine (ng/L)", "CRP (mg/L)", "Albumine (g/L)"]
    assert info.roc_classes == ["Sain", "Malade"]
    trop, crp, albumin = info.rocs
    assert trop["AUC"] > albumin["AUC"] > crp["AUC"] > 0.5
    assert trop["Seuil optimal"].startswith(">")
    assert albumin["Seuil optimal"].startswith("<")     # falls with disease
    assert (trop["n positifs"], trop["n négatifs"]) == (60, 70)
    legend = [t.get_text() for t in figure.axes[0].get_legend().get_texts()]
    assert legend[0] == f"Troponine (ng/L) (AUC = {trop['AUC']:.3f})"


def test_markers_on_the_same_patients_are_compared(markers):
    _, spec, info, _ = markers
    pairs = {(c.a, c.b): c for c in info.comparisons}
    assert len(pairs) == 3
    best = pairs[("Troponine (ng/L)", "CRP (mg/L)")]
    assert best.test == "DeLong (apparié)" and best.p_adj < 0.001
    # three pairs: corrected, by the method the plot names (Holm)
    from plotea.core import stats as st

    raw = [c.p for c in info.comparisons]
    assert [c.p_adj for c in info.comparisons] == pytest.approx(
        st.adjust(raw, spec.stats_correction))
    assert any(c.p_adj > c.p for c in info.comparisons)


def test_prisms_two_columns_give_the_same_area(markers):
    table, _, info, _ = markers
    df = table.df
    healthy = df[df["Diagnostic"] == "Sain"]["Troponine (ng/L)"]
    sick = df[df["Diagnostic"] == "Malade"]["Troponine (ng/L)"]
    wide = pd.DataFrame({"Sains": healthy.reset_index(drop=True),
                         "Malades": sick.reset_index(drop=True)})
    found = plotting.render(Figure(), PlotSpec(
        plot_type="roc", y=["Sains", "Malades"]), wide)
    assert found.rocs[0]["AUC"] == pytest.approx(info.rocs[0]["AUC"])
    assert found.rocs[0]["n positifs"] == 60       # empty cells dropped


def test_the_other_class_as_positive_reads_the_same_area(markers):
    table, spec, info, _ = markers
    other = plotting.render(Figure(), PlotSpec(
        **{**table.meta["plot"], "roc_positive": "Sain"}), table.df)
    assert other.rocs[0]["AUC"] == pytest.approx(info.rocs[0]["AUC"])
    assert other.rocs[0]["Seuil optimal"].startswith("<")
    assert other.roc_classes == ["Malade", "Sain"]


def test_three_classes_are_refused_on_the_plot():
    frame = pd.DataFrame({"Statut": list("ABCABC"),
                          "M": [1.0, 2, 3, 4, 5, 6]})
    figure = Figure()
    info = plotting.render(figure, PlotSpec(plot_type="roc", group="Statut",
                                            y=["M"]), frame)
    assert not info.rocs
    assert any("deux classes" in w for w in info.warnings)
    assert any("deux classes" in t.get_text()
               for t in figure.axes[0].texts)


def test_missing_values_are_left_out_marker_by_marker(markers):
    table, spec, _, _ = markers
    df = table.df.copy()
    df.loc[df.index[:10], "CRP (mg/L)"] = np.nan
    info = plotting.render(Figure(), spec, df)
    rows = {r["Marqueur"]: r for r in info.rocs}
    assert rows["Troponine (ng/L)"]["n négatifs"] == 70
    assert rows["CRP (mg/L)"]["n négatifs"] == 60
    assert len(info.comparisons) == 3          # on the complete subjects


def test_the_methods_paragraph_says_how(markers):
    _, spec, info, _ = markers
    french = methods_text(spec, info, "fr")
    assert "méthode de DeLong" in french and "indice de Youden" in french
    assert "Pour Albumine (g/L), plus faibles" in french
    english = methods_text(spec, info, "en")
    assert "correlated ROC curves" in english and "Holm" in english


def test_the_settings_survive_saving_and_renaming(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="R", plot_type="roc", y=["A", "B"],
                              roc_positive="B", roc_youden=False))
    spec = Project.load(project.save(str(tmp_path / "r.plotea"))).plots[-1]
    assert (spec.plot_type, spec.roc_positive, spec.roc_youden) == (
        "roc", "B", False)
    spec.dataset = "T"
    spec.rename_column("T", "B", "Patients")
    assert spec.roc_positive == "Patients" and spec.y == ["A", "Patients"]


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_example_opens_with_its_table(window):
    window.files.start_new()
    window.load_example("Biomarqueurs diagnostiques (courbes ROC)")
    window._render_now()
    panel = window.stats_panel
    assert panel.tabs.isTabVisible(panel.tabs.indexOf(panel.roc))
    assert panel.roc.rowCount() == 3
    assert "3 marqueurs" in panel.header.text()
    assert "positif : Malade" in panel.header.text()
    picker = window.inspector.cmb_roc_positive
    assert [picker.itemText(i) for i in range(picker.count())] == [
        "", "Sain", "Malade"]
    picker.setCurrentText("Sain")
    window._render_now()
    assert window.current_spec().roc_positive == "Sain"
    assert "positif : Sain" in panel.header.text()


def test_choosing_roc_finds_the_status_column(window):
    window.files.start_new()
    window.load_example("Biomarqueurs diagnostiques (courbes ROC)")
    spec = window.current_spec()
    spec.plot_type = "bar"
    window._on_plot_type_changed("bar")
    for button in window.inspector.type_buttons.buttons():
        if button.property("plot_type") == "roc":
            button.click()
    assert spec.plot_type == "roc"
    assert spec.group == "Diagnostic"
    assert spec.y[0] == "Troponine (ng/L)"
