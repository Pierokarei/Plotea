"""Kaplan-Meier and log-rank, checked against a published trial."""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea.core import demo
from plotea.core import stats as st
from plotea.core.plotspec import PlotSpec
from plotea.core.plotting import render

# Freireich 1963: 6-mercaptopurine against placebo in leukaemia remission.
# The textbook example of censoring, with published curves and log-rank.
MP_TIMES = [6, 6, 6, 6, 7, 9, 10, 10, 11, 13, 16, 17, 19, 20, 22, 23, 25,
            32, 32, 34, 35]
MP_EVENTS = [1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0]
PLACEBO_TIMES = [1, 1, 2, 2, 3, 4, 4, 5, 5, 8, 8, 8, 8, 11, 11, 12, 12, 15,
                 17, 22, 23]
PLACEBO_EVENTS = [1] * 21


def draw(spec: PlotSpec, df: pd.DataFrame):
    return render(Figure(figsize=(4, 3)), spec, df)


# --------------------------------------------------------------------------
# The estimator
# --------------------------------------------------------------------------
def test_kaplan_meier_matches_the_published_curve():
    km = st.kaplan_meier(MP_TIMES, MP_EVENTS)
    assert km["n"] == 21
    assert km["events"] == 9
    assert km["censored"] == 12

    published = {6: 0.857, 7: 0.807, 10: 0.753, 13: 0.690,
                 16: 0.627, 22: 0.538, 23: 0.448}
    steps = dict(zip(km["time"], km["survival"]))
    for moment, expected in published.items():
        assert steps[moment] == pytest.approx(expected, abs=5e-4), moment
    assert km["median"] == 23
    assert st.kaplan_meier(PLACEBO_TIMES, PLACEBO_EVENTS)["median"] == 8


def test_censoring_is_neither_death_nor_survival():
    """Dropping the censored subjects or counting them as survivors both lie.

    Same follow-up times, three readings: the estimator must sit between the
    two naive answers.
    """
    times = [1, 2, 3, 4, 5, 6]
    events = [1, 0, 1, 0, 1, 0]           # every other one lost to follow-up
    km = st.kaplan_meier(times, events)

    as_if_all_died = 0.0                  # 6 events out of 6
    as_if_censored_survived = 1 - 3 / 6   # 0.5
    final = km["survival"][-1]
    assert as_if_all_died < final < 1.0
    assert final != pytest.approx(as_if_censored_survived, abs=1e-9)
    assert km["censored"] == 3


def test_the_curve_only_goes_down_and_stays_in_range():
    rng = np.random.default_rng(9)
    km = st.kaplan_meier(rng.exponential(10, 60),
                         rng.integers(0, 2, 60))
    survival = np.asarray(km["survival"])
    assert np.all(np.diff(survival) <= 1e-12), "la survie remonte"
    assert survival[0] == 1.0
    assert np.all((survival >= 0) & (survival <= 1))
    lower, upper = np.asarray(km["lower"]), np.asarray(km["upper"])
    assert np.all(lower <= survival + 1e-12)
    assert np.all(upper >= survival - 1e-12)
    assert np.all((lower >= 0) & (upper <= 1)), "la bande sort de [0, 1]"


def test_the_curve_reaches_the_end_of_follow_up():
    """After the last event it is flat, not absent: the censoring marks that
    come later must have a line to sit on."""
    km = st.kaplan_meier(MP_TIMES, MP_EVENTS)
    assert km["time"][-1] == max(MP_TIMES)
    assert km["survival"][-1] == km["survival"][-2]
    assert max(km["censored_time"]) <= km["time"][-1]


def test_without_an_event_column_everyone_has_the_event():
    km = st.kaplan_meier([1, 2, 3, 4])
    assert km["events"] == 4
    assert km["censored"] == 0
    assert km["survival"][-1] == 0.0


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------
def test_logrank_matches_the_published_value():
    chi2, p, df = st.logrank({"6-MP": (MP_TIMES, MP_EVENTS),
                              "Placebo": (PLACEBO_TIMES, PLACEBO_EVENTS)})
    assert chi2 == pytest.approx(16.79, abs=0.01)     # published 16.79
    assert p == pytest.approx(4.2e-5, rel=0.05)       # published 4.2e-05
    assert df == 1


def test_a_group_against_itself_is_a_perfect_match():
    chi2, p, _ = st.logrank({"A": (MP_TIMES, MP_EVENTS),
                             "B": (MP_TIMES, MP_EVENTS)})
    assert chi2 == pytest.approx(0.0, abs=1e-12)
    assert p == pytest.approx(1.0)


def test_logrank_handles_more_than_two_arms():
    rng = np.random.default_rng(6)
    curves = {name: (rng.exponential(median, 50),
                     np.ones(50, dtype=int))
              for name, median in (("A", 6.0), ("B", 12.0), ("C", 24.0))}
    chi2, p, df = st.logrank(curves)
    assert df == 2
    assert p < 1e-4, (chi2, p)

    pairs = st.logrank_pairs(curves, correction="holm")
    assert {(c.a, c.b) for c in pairs} == {("A", "B"), ("A", "C"), ("B", "C")}
    assert all(c.test == "Log-rank" for c in pairs)
    assert all(c.p_adj >= c.p for c in pairs), "la correction doit augmenter p"


# --------------------------------------------------------------------------
# On a figure
# --------------------------------------------------------------------------
@pytest.fixture
def trial():
    return demo.survival().df


def test_a_survival_plot_draws_one_step_curve_per_arm(trial):
    spec = PlotSpec(plot_type="survival", x="Temps (mois)", group="Bras",
                    event_col="Événement", stats_enabled=True)
    figure = Figure(figsize=(4, 3))
    info = render(figure, spec, trial)

    assert not info.warnings, info.warnings
    axes = figure.axes[0]
    drawn = [line for line in axes.lines
             if line.get_linestyle() not in ("None", "none")]
    assert len(drawn) >= 2
    for line in drawn[:2]:
        ys = line.get_ydata()
        assert max(ys) <= 1.0 and min(ys) >= 0.0
    assert axes.get_ylabel() == "Survie"
    assert info.omnibus[0] == "Log-rank"
    assert info.omnibus[2] < 0.05, info.omnibus


def test_the_median_survival_reaches_the_panel(trial):
    spec = PlotSpec(plot_type="survival", x="Temps (mois)", group="Bras",
                    event_col="Événement")
    info = draw(spec, trial)
    rows = {r["Groupe"]: r for r in info.descriptives}
    assert set(rows) == {"Traitement", "Placebo"}
    assert rows["Traitement"]["Survie médiane"] > rows["Placebo"][
        "Survie médiane"]
    for row in rows.values():
        assert row["n"] == row["Événements"] + row["Censurés"]


def test_censoring_marks_can_be_switched_off(trial):
    base = Figure(figsize=(4, 3))
    render(base, PlotSpec(plot_type="survival", x="Temps (mois)", group="Bras",
                          event_col="Événement", show_censors=True), trial)
    ticks = [line for line in base.axes[0].lines
             if line.get_marker() == "|"]
    assert ticks

    bare = Figure(figsize=(4, 3))
    render(bare, PlotSpec(plot_type="survival", x="Temps (mois)", group="Bras",
                          event_col="Événement", show_censors=False), trial)
    assert not [line for line in bare.axes[0].lines
                if line.get_marker() == "|"]


def test_a_missing_event_column_is_said_out_loud(trial):
    info = draw(PlotSpec(plot_type="survival", x="Temps (mois)",
                         group="Bras"), trial)
    assert any("événement" in w.lower() for w in info.warnings), info.warnings


def test_a_missing_time_column_does_not_crash(trial):
    info = draw(PlotSpec(plot_type="survival", group="Bras"), trial)
    assert any("temps" in w.lower() for w in info.warnings), info.warnings


def test_the_survival_example_is_offered(trial):
    assert "Essai de survie (Kaplan-Meier)" in demo.EXAMPLES
    assert {"Bras", "Temps (mois)", "Événement"} <= set(trial.columns)
    assert set(trial["Événement"].unique()) <= {0, 1}
