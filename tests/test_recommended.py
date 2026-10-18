"""The recommended test: chosen from the declared design, never from the data.

A normality test on a few values proves nothing when it finds no departure,
and a test chosen on the data it then tests is not the test it says it is.
So "Test recommandé" reads the design the user declared - independent
groups, the same subjects - and where that does not settle it (not said,
several factors, several times) runs nothing and asks.

The new tests (Welch's ANOVA, Games-Howell, Dunnett's T3) are checked
against the identities that pin them down and against simulation: under
unequal variances they hold their 5 % where the classical ANOVA drifts.
"""
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
import scipy.stats as sps
from matplotlib.figure import Figure

from plotea.core import demo, methods, plotting
from plotea.core import stats as st
from plotea.core.plotspec import PlotSpec

RNG = np.random.default_rng(2024)
A, B, C = RNG.normal(10, 1, 9), RNG.normal(11, 3, 14), RNG.normal(12, 2, 6)


def welch_t(a, b):
    r = sps.ttest_ind(a, b, equal_var=False)
    return float(r.statistic), float(r.pvalue)


# --------------------------------------------------------------------------
# The tests themselves
# --------------------------------------------------------------------------
def test_welch_anova_of_two_groups_is_welchs_t_squared():
    F, df1, _df2, p = st.welch_anova([A, B])
    t, p_t = welch_t(A, B)
    assert df1 == 1
    assert F == pytest.approx(t ** 2, rel=1e-12)
    assert p == pytest.approx(p_t, rel=1e-10)


def test_welch_anova_follows_welchs_formula():
    """Written out again from Welch (1951), as a textbook gives it."""
    groups = [A, B, C]
    n = np.array([g.size for g in groups], float)
    m = np.array([g.mean() for g in groups])
    w = n / np.array([g.var(ddof=1) for g in groups])
    k, W = len(groups), w.sum()
    grand = (w * m).sum() / W
    lam = ((1 - w / W) ** 2 / (n - 1)).sum()
    F = ((w * (m - grand) ** 2).sum() / (k - 1)) / (
        1 + 2 * (k - 2) / (k ** 2 - 1) * lam)
    df2 = (k ** 2 - 1) / (3 * lam)
    got = st.welch_anova(groups)
    assert got[0] == pytest.approx(F, rel=1e-12)
    assert got[1] == k - 1 and got[2] == pytest.approx(df2, rel=1e-12)
    assert got[3] == pytest.approx(sps.f.sf(F, k - 1, df2), rel=1e-10)


def test_games_howell_of_two_groups_is_welchs_t():
    (comp,) = st.games_howell({"A": A, "B": B}, [("A", "B")])
    assert comp.p == pytest.approx(welch_t(A, B)[1], rel=1e-8)


def test_dunnett_t3_of_one_comparison_is_welchs_t():
    (comp,) = st.dunnett_t3({"A": A, "B": B}, [("A", "B")])
    assert comp.p == pytest.approx(welch_t(A, B)[1], rel=1e-8)


@pytest.mark.parametrize("t, c, df", [(2.0, 3, 8.0), (2.8, 6, 20.0),
                                      (1.2, 2, 4.5)])
def test_the_studentized_maximum_modulus_matches_its_definition(t, c, df):
    """The largest of c independent |Z|, over sqrt(chi2_df / df)."""
    rng = np.random.default_rng(7)
    draws = 400_000
    z = np.abs(rng.standard_normal((draws, c))).max(axis=1)
    s = np.sqrt(rng.chisquare(df, draws) / df)
    simulated = (z / s > t).mean()
    se = np.sqrt(simulated * (1 - simulated) / draws)
    assert abs(st.max_modulus_sf(t, c, df) - simulated) < 4 * se


def test_a_small_p_keeps_its_digits():
    """Integrated as a tail, not as 1 - a probability."""
    p = st.max_modulus_sf(12.0, 1, 30.0)
    assert p == pytest.approx(2 * sps.t.sf(12.0, 30.0), rel=1e-6)
    assert 0 < p < 1e-11


def test_t3_against_the_control_counts_only_the_comparisons_made():
    groups = {"C": A, "X": B, "Y": C}
    all_pairs = st.pairwise(groups, "welch_anova", "none",
                            posthoc="dunnett_t3")
    control = st.pairwise(groups, "welch_anova", "none", mode="vs_control",
                          control="C")
    assert len(all_pairs) == 3 and len(control) == 2
    p_all = {(c.a, c.b): c.p for c in all_pairs}
    for comp in control:
        # a family of two is a smaller penalty than a family of three
        assert comp.p < p_all[(comp.a, comp.b)]
        t, df = st._welch_pair(groups[comp.a], groups[comp.b])
        assert comp.p == pytest.approx(st.max_modulus_sf(abs(t), 2, df))


def simulate(sizes, sds, draws, seed):
    rng = np.random.default_rng(seed)
    for _ in range(draws):
        yield {f"G{i}": rng.normal(0, sd, n)
               for i, (n, sd) in enumerate(zip(sizes, sds))}


def test_welchs_anova_holds_its_error_rate_where_the_classical_one_drifts():
    """Equal means, unequal variances, the smallest group the most
    scattered: the classical ANOVA rejects far too often."""
    sizes, sds = (6, 12, 24), (4.0, 2.0, 1.0)
    welch = classical = 0
    draws = 3000
    for groups in simulate(sizes, sds, draws, seed=1):
        data = list(groups.values())
        welch += st.welch_anova(data)[3] < 0.05
        classical += sps.f_oneway(*data).pvalue < 0.05
    assert 0.035 < welch / draws < 0.065, welch / draws
    assert classical / draws > 0.10, classical / draws


def critical_range(k, level=0.95):
    """The exact critical studentized range at a grid of degrees of
    freedom, interpolated in 1/df: a stand-in for scipy's sf, some tens of
    milliseconds a call, that gives the same decision at 5 %."""
    from scipy.interpolate import CubicSpline

    grid = np.geomspace(2.5, 80, 14)
    q = [sps.studentized_range.ppf(level, k, df) for df in grid]
    spline = CubicSpline(1 / grid[::-1], np.array(q)[::-1])

    def sf(q, k_, df):
        assert k_ == k and 2.5 <= df <= 80, (k_, df)
        return 0.01 if q > spline(1 / df) else 0.5
    return sf


@pytest.mark.parametrize("posthoc", ["games_howell", "dunnett_t3"])
def test_the_pairs_hold_the_family_error_rate(posthoc, monkeypatch):
    if posthoc == "games_howell":
        monkeypatch.setattr(st, "_range_sf", critical_range(3))
    sizes, sds = (6, 12, 24), (4.0, 2.0, 1.0)
    draws, wrong = 1500, 0
    for groups in simulate(sizes, sds, draws, seed=2):
        comps = st.pairwise(groups, "welch_anova", "none", posthoc=posthoc)
        wrong += any(c.p < 0.05 for c in comps)
    # both are slightly conservative with small groups; never liberal
    assert 0.025 < wrong / draws < 0.065, wrong / draws


def test_unadjusted_welch_tests_would_not_hold_it():
    """What the two above guard against: the same pairs, uncorrected."""
    sizes, sds = (6, 12, 24), (4.0, 2.0, 1.0)
    draws, wrong = 800, 0
    for groups in simulate(sizes, sds, draws, seed=2):
        comps = st.pairwise(groups, "welch", "none")
        wrong += any(c.p < 0.05 for c in comps)
    assert wrong / draws > 0.08, wrong / draws


# --------------------------------------------------------------------------
# What is recommended, from the design
# --------------------------------------------------------------------------
def render(df, **fields):
    spec = PlotSpec(stats_enabled=True, **fields)
    return spec, plotting.render(Figure(), spec, df)


def viability(**fields):
    return render(demo.viability().df, plot_type="bar", group="Traitement",
                  y=["Viabilité"], **fields)


def two_groups():
    df = demo.viability().df
    keep = df["Traitement"].isin(df["Traitement"].unique()[:2])
    return df[keep]


def test_two_independent_groups_get_welch():
    spec, info = render(two_groups(), plot_type="bar", group="Traitement",
                        y=["Viabilité"], design="independent")
    assert info.test_used == "welch"
    assert info.recommendation["title"] == "Test recommandé : Welch"
    (comp,) = info.comparisons
    a, b = (two_groups().groupby("Traitement", sort=False)["Viabilité"]
            .apply(np.asarray))
    assert comp.p == pytest.approx(welch_t(a, b)[1])


def test_more_groups_get_welchs_anova_then_games_howell():
    _spec, info = viability(design="independent")
    assert info.test_used == "welch_anova"
    assert info.omnibus[0] == "ANOVA de Welch"
    assert {c.test for c in info.comparisons} == {"Games-Howell"}
    assert "Games-Howell" in info.recommendation["title"]


def test_dunnett_t3_on_request_or_against_the_control():
    _spec, info = viability(design="independent", posthoc="dunnett_t3")
    assert {c.test for c in info.comparisons} == {"Dunnett T3"}
    assert len(info.comparisons) == 6
    _spec, info = viability(design="independent", stats_mode="vs_control",
                            stats_control="Contrôle")
    assert {c.test for c in info.comparisons} == {"Dunnett T3"}
    assert len(info.comparisons) == 3
    assert "Dunnett T3" in info.recommendation["title"]


def test_the_same_subjects_get_a_paired_t():
    df = demo.paired().df
    _spec, info = render(df, plot_type="paired", y=["Avant", "Après"])
    assert info.test_used == "paired_t"
    assert info.comparisons[0].p == pytest.approx(
        sps.ttest_rel(df["Avant"], df["Après"]).pvalue)


def test_an_undeclared_design_runs_nothing_and_asks():
    _spec, info = viability()
    assert not info.comparisons and not info.omnibus
    assert info.test_used == ""
    assert info.recommendation["test"] is None
    assert info.recommendation["title"] == "Précisez le plan expérimental"
    assert "Précisez le plan expérimental" in info.warnings
    # the diagnostics are still there to be looked at
    assert set(info.diagnostics["normality"]) == set(info.groups)


def test_two_factors_are_not_settled_automatically():
    ds = demo.two_factor()
    settings = {k: v for k, v in ds.meta["plot"].items()
                if k not in ("stats_test", "stats_enabled")}
    spec = PlotSpec(**settings)
    spec.stats_enabled = True
    spec.stats_test = "auto"
    info = plotting.render(Figure(), spec, ds.df)
    assert info.recommendation["test"] is None
    assert not info.comparisons
    assert "Aucun test recommandé automatiquement" in info.warnings


def test_the_shape_of_the_data_never_changes_the_choice():
    """A heavy-tailed group, then a normal one: the same test both times."""
    rng = np.random.default_rng(5)
    for third in (rng.lognormal(2.2, 1.2, 15), rng.normal(10, 1, 15)):
        df = pd.DataFrame({
            "G": ["a"] * 15 + ["b"] * 15 + ["c"] * 15,
            "V": np.concatenate([rng.normal(10, 1, 15),
                                 rng.normal(11, 1, 15), third])})
        _spec, info = render(df, plot_type="box", group="G", y=["V"],
                             design="independent")
        assert info.test_used == "welch_anova"


def test_a_test_chosen_by_name_is_run_as_chosen():
    for key, ran in (("kruskal_dunn", "Dunn"), ("anova_tukey", "Tukey HSD"),
                     ("mannwhitney", "Mann-Whitney")):
        _spec, info = viability(stats_test=key)
        assert info.test_used == key and not info.recommendation
        assert {c.test for c in info.comparisons} == {ran}


def test_the_explanation_and_methods_name_the_test_that_ran():
    for fields in ({}, {"posthoc": "dunnett_t3"}):
        spec, info = viability(design="independent", **fields)
        ran = info.comparisons[0].test
        assert ran in info.recommendation["title"]
        text = methods.methods_text(spec, info, "en")
        assert methods.TESTS["en"][ran] in text
        assert "chosen a priori from the experimental design" in text
    spec, info = render(two_groups(), plot_type="bar", group="Traitement",
                        y=["Viabilité"], design="independent")
    assert "Welch" in info.recommendation["body"]
    assert methods.TESTS["en"]["t de Welch"] in methods.methods_text(
        spec, info, "en")


def test_every_example_with_statistics_declares_its_design():
    for ds in demo.all_examples():
        plot = ds.meta.get("plot", {})
        if plot.get("plot_type") in ("bar", "box", "violin"):
            assert plot.get("design", "unknown") != "unknown", ds.name


# --------------------------------------------------------------------------
# Old projects
# --------------------------------------------------------------------------
def test_an_old_auto_project_reopens_asking_for_the_design(tmp_path):
    """Saved before the design existed: "Auto", no design. It opens, and
    asks rather than guessing - the release notes say so."""
    from plotea.core.project import Project

    project = Project()
    ds = demo.viability()
    project.add_dataset(ds)
    project.add_plot(PlotSpec(name="Ancien", plot_type="bar",
                              dataset=ds.name, group="Traitement",
                              y=["Viabilité"], stats_enabled=True))
    path = project.save(str(tmp_path / "ancien.plotea"))
    # rewrite it as the earlier version wrote it
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    meta = json.loads(files["project.json"])
    for plot in meta["plots"]:
        plot["stats_test"] = "Auto"
        plot.pop("design", None)
        plot.pop("posthoc", None)
    files["project.json"] = json.dumps(meta).encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    spec = Project.load(path).plots[-1]
    assert (spec.stats_test, spec.design, spec.posthoc) == \
        ("auto", "unknown", "games_howell")
    info = plotting.render(Figure(), spec, ds.df)
    assert not info.comparisons
    assert "Précisez le plan expérimental" in info.warnings
    spec.design = "independent"
    info = plotting.render(Figure(), spec, ds.df)
    assert info.test_used == "welch_anova"


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
def test_the_inspector_offers_the_design_and_the_pairs(window):
    window.load_example("Viabilité cellulaire (barres, stats)")
    inspector = window.inspector
    spec = window.current_spec()
    assert not inspector.cmb_design.isHidden()
    assert inspector.cmb_design.currentData() == spec.design == "independent"
    assert not inspector.cmb_posthoc.isHidden()
    inspector.cmb_posthoc.setCurrentIndex(
        inspector.cmb_posthoc.findData("dunnett_t3"))
    assert spec.posthoc == "dunnett_t3"
    inspector.cmb_design.setCurrentIndex(
        inspector.cmb_design.findData("unknown"))
    assert spec.design == "unknown"
    window._render_now()
    assert not window.canvas.last_info.comparisons
    panel = window.stats_panel
    assert not panel.advice.isHidden()
    assert "Précisez le plan expérimental" in panel.advice.text()


def test_the_comparisons_tab_explains_the_choice(window):
    window.load_example("Viabilité cellulaire (barres, stats)")
    window._render_now()
    panel = window.stats_panel
    text = panel.advice.text()
    assert "ANOVA de Welch" in text and "Games-Howell" in text
    assert "Levene" in text and "Le choix du test peut être modifié" in text
    assert panel.tests.rowCount() == 6
    # a test chosen by name needs no explanation
    spec = window.current_spec()
    spec.stats_test = "kruskal_dunn"
    window._render_now()
    assert panel.advice.isHidden()


def test_a_before_after_plot_declares_the_same_subjects(window):
    window.load_example("Pression artérielle (avant/après)")
    inspector = window.inspector
    for button in inspector.type_buttons.buttons():
        if button.property("plot_type") == "paired":
            button.click()
    assert inspector.cmb_design.currentData() == "paired"
    assert not inspector.cmb_design.isEnabled()


def test_the_explanation_does_not_hold_the_panel_open(window):
    """A word-wrapped label once set the Analyses panel's minimum to its
    height at the narrowest width - over 400 pixels - and the panel could
    no longer be made smaller. Shown or not, it must change nothing."""
    from conftest import app
    from PyQt6.QtCore import Qt

    dock = window.dock_stats
    window.resize(1500, 950)
    window.load_example("Essai de survie (Kaplan-Meier)")
    window._render_now()
    app.processEvents()
    assert window.stats_panel.advice.isHidden()
    without = dock.minimumSizeHint().height()
    window.load_example("Viabilité cellulaire (barres, stats)")
    window._render_now()
    app.processEvents()
    assert not window.stats_panel.advice.isHidden()
    assert dock.minimumSizeHint().height() == without
    for height in (without, 260, 420, 520):
        window.resizeDocks([dock], [height], Qt.Orientation.Vertical)
        app.processEvents()
        assert abs(dock.height() - height) <= 30, (height, dock.height())
