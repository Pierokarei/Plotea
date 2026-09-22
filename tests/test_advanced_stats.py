"""Dunnett, repeated measures and outlier flagging, checked against
independent computations rather than against themselves."""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats as sps

from plotea.core import stats as st
from plotea.core.plotspec import PlotSpec
from plotea.core.plotting import render


def draw(spec: PlotSpec, df: pd.DataFrame):
    return render(Figure(figsize=(4, 3)), spec, df)


@pytest.fixture
def within_subject():
    """Ten subjects measured in three conditions, with a real effect."""
    rng = np.random.default_rng(3)
    rows = []
    for subject in range(10):
        base = rng.normal(100, 12)          # large between-subject spread
        for condition, shift in (("Avant", 0), ("Traitement", 9),
                                 ("Après", 4)):
            rows.append({"Sujet": f"S{subject + 1}", "Condition": condition,
                         "Mesure": base + shift + rng.normal(0, 3)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Repeated measures
# --------------------------------------------------------------------------
def test_rm_anova_matches_a_least_squares_fit():
    """Same F as a dummy-coded regression, by a completely different route.

    The module computes sums of squares from condition and subject means;
    this recomputes the effect as the residual variance a full model removes
    compared with one that knows only the subjects.
    """
    rng = np.random.default_rng(7)
    n, k = 12, 4
    grid = (rng.normal(0, 5, size=(n, 1))          # subject
            + np.array([0.0, 1.5, 3.0, 2.0])       # condition
            + rng.normal(0, 1.2, size=(n, k)))
    paired = {f"C{j + 1}": {f"S{i + 1}": grid[i, j] for i in range(n)}
              for j in range(k)}

    rows, message = st.repeated_measures_anova(paired)
    mine = {r["Source"]: r for r in rows}

    y = grid.reshape(-1)
    conditions = np.zeros((y.size, k))
    conditions[np.arange(y.size), np.tile(np.arange(k), n)] = 1
    subjects = np.zeros((y.size, n))
    subjects[np.arange(y.size), np.repeat(np.arange(n), k)] = 1

    def rss(matrix):
        beta, *_ = np.linalg.lstsq(matrix, y, rcond=None)
        residual = y - matrix @ beta
        return float(residual @ residual)

    full = np.column_stack([conditions, subjects[:, 1:]])
    without = np.column_stack([np.ones(y.size), subjects[:, 1:]])
    df_error = y.size - np.linalg.matrix_rank(full)
    f_ols = ((rss(without) - rss(full)) / (k - 1)) / (rss(full) / df_error)

    assert mine["Conditions"]["F"] == pytest.approx(f_ols, rel=1e-9)
    assert mine["Conditions"]["ddl"] == k - 1
    assert mine["Résidus"]["ddl"] == (k - 1) * (n - 1)
    assert "epsilon" in message


def test_rm_anova_needs_subjects_seen_everywhere():
    """A subject missing from a condition cannot be half-counted."""
    paired = {"A": {"s1": 1.0, "s2": 2.0, "s3": 3.0},
              "B": {"s1": 2.0, "s2": 3.0},              # s3 absent
              "C": {"s1": 4.0, "s2": 4.5, "s3": 5.0}}
    conditions, subjects, grid = st.complete_cases(paired)
    assert subjects == ["s1", "s2"], subjects
    assert grid.shape == (2, 3)


def test_rm_anova_says_why_it_cannot_run():
    rows, message = st.repeated_measures_anova(
        {"A": {"s1": 1.0}, "B": {"s2": 2.0}})      # no subject in common
    assert rows == []
    assert "aucun sujet" in message.lower()


@pytest.mark.parametrize("size", [3, 4, 6])
def test_sphericity_holds_under_compound_symmetry(size):
    """Equal variances and equal covariances is the textbook spherical case."""
    rng = np.random.default_rng(11)
    cov = np.full((size, size), 4.0) + np.eye(size) * 6.0
    sample = rng.multivariate_normal(np.zeros(size), cov, size=4000)
    assert st.greenhouse_geisser(sample) == pytest.approx(1.0, abs=0.02)


def test_sphericity_stays_inside_its_bounds():
    """Epsilon lives in [1/(k-1), 1], and two conditions are always spherical."""
    rng = np.random.default_rng(5)
    skewed = rng.multivariate_normal(np.zeros(4),
                                     np.diag([1.0, 1.0, 1.0, 40.0]), size=400)
    epsilon = st.greenhouse_geisser(skewed)
    assert 1 / 3 <= epsilon < 1
    _, _, grid = st.complete_cases({"A": {"s1": 1.0, "s2": 2.0, "s3": 4.0},
                                    "B": {"s1": 2.0, "s2": 2.5, "s3": 5.5}})
    assert st.greenhouse_geisser(grid) == 1.0


def test_repeated_measures_reaches_the_figure(within_subject):
    spec = PlotSpec(plot_type="bar", group="Condition", y=["Mesure"],
                    stats_enabled=True, stats_test="rm_anova",
                    stats_pair_by="Sujet")
    info = draw(spec, within_subject)

    assert not info.warnings, info.warnings
    assert info.anova_title == "ANOVA à mesures répétées"
    assert [r["Source"] for r in info.anova] == ["Conditions", "Sujets",
                                                 "Résidus"]
    assert info.omnibus[0] == "ANOVA à mesures répétées"
    # the follow-up comparisons stay within subject
    assert {c.test for c in info.comparisons} == {"t apparié"}


def test_repeated_measures_demands_the_pairing_column(within_subject):
    spec = PlotSpec(plot_type="bar", group="Condition", y=["Mesure"],
                    stats_enabled=True, stats_test="rm_anova")
    info = draw(spec, within_subject)
    assert info.comparisons == []
    assert any("appariement" in w for w in info.warnings), info.warnings


def test_the_subject_variance_leaves_the_error_term(within_subject):
    """The point of the design: what a between-subject ANOVA cannot see.

    The same numbers analysed as independent groups keep the subject spread
    inside the residual, so the effect is swamped.
    """
    paired = {}
    for condition, sub in within_subject.groupby("Condition"):
        paired[condition] = dict(zip(sub["Sujet"], sub["Mesure"]))
    rows, _ = st.repeated_measures_anova(paired)
    within_p = rows[0]["p"]

    groups = {c: sub["Mesure"].to_numpy()
              for c, sub in within_subject.groupby("Condition")}
    between_p = float(sps.f_oneway(*groups.values()).pvalue)

    assert within_p < 0.01
    assert between_p > 0.2
    assert within_p < between_p


# --------------------------------------------------------------------------
# Dunnett
# --------------------------------------------------------------------------
def test_dunnett_matches_scipy_and_compares_only_with_the_control():
    rng = np.random.default_rng(7)
    groups = {"Contrôle": rng.normal(10, 2, 9), "Dose 1": rng.normal(12, 2, 9),
              "Dose 2": rng.normal(14, 2, 9), "Dose 3": rng.normal(10.5, 2, 9)}

    comps = st.pairwise(groups, test="dunnett", mode="vs_control",
                        control="Contrôle")
    expected = sps.dunnett(*[groups[k] for k in ("Dose 1", "Dose 2", "Dose 3")],
                           control=groups["Contrôle"],
                           random_state=np.random.default_rng(12345))

    assert [c.b for c in comps] == ["Dose 1", "Dose 2", "Dose 3"]
    assert {c.a for c in comps} == {"Contrôle"}
    for comp, p in zip(comps, expected.pvalue):
        assert comp.p == pytest.approx(float(p), abs=1e-12)
        assert comp.p_adj == comp.p, "Dunnett corrige déjà la multiplicité"
        assert comp.test == "Dunnett"


def test_dunnett_gives_the_same_answer_twice():
    """SciPy integrates by Monte Carlo; a figure must not change on redraw."""
    rng = np.random.default_rng(1)
    groups = {"T": rng.normal(0, 1, 12), "A": rng.normal(1, 1, 12),
              "B": rng.normal(2, 1, 12)}
    first = st.pairwise(groups, test="dunnett", mode="vs_control", control="T")
    second = st.pairwise(groups, test="dunnett", mode="vs_control", control="T")
    assert [c.p for c in first] == [c.p for c in second]


def test_dunnett_without_a_control_explains_itself(within_subject):
    spec = PlotSpec(plot_type="bar", group="Condition", y=["Mesure"],
                    stats_enabled=True, stats_test="dunnett")
    info = draw(spec, within_subject)
    assert info.comparisons == []
    assert any("contrôle" in w for w in info.warnings), info.warnings


def test_dunnett_beats_all_pairs_for_the_same_question():
    """Fewer comparisons and a sharper correction when only the control matters.

    Six pairs corrected by Holm cost more than three Dunnett contrasts on the
    same data, which is the whole reason the test exists.
    """
    rng = np.random.default_rng(4)
    groups = {"Contrôle": rng.normal(10, 1.5, 10),
              "A": rng.normal(11.4, 1.5, 10),
              "B": rng.normal(11.6, 1.5, 10),
              "C": rng.normal(11.5, 1.5, 10)}
    dunnett = {c.b: c.p_adj for c in st.pairwise(
        groups, test="dunnett", mode="vs_control", control="Contrôle")}
    holm = {c.b: c.p_adj for c in st.pairwise(
        groups, test="student", correction="holm", mode="all_pairs")
        if c.a == "Contrôle"}
    assert set(dunnett) == set(holm)
    assert all(dunnett[k] < holm[k] for k in dunnett), (dunnett, holm)


# --------------------------------------------------------------------------
# Outliers
# --------------------------------------------------------------------------
def test_grubbs_on_the_published_example():
    """The eight-value set from the NIST handbook: G = 2.4687."""
    sample = [199.31, 199.53, 200.19, 200.82, 201.92, 201.95, 202.18, 245.57]
    flagged = st.grubbs(sample)
    assert len(flagged) == 1
    assert flagged[0]["value"] == 245.57
    assert flagged[0]["G"] == pytest.approx(2.4687, abs=5e-4)
    assert flagged[0]["p"] < 0.001


def test_grubbs_leaves_clean_data_alone():
    rng = np.random.default_rng(12)
    for _ in range(20):
        assert st.grubbs(rng.normal(0, 1, 40)) == []


def test_grubbs_does_not_eat_the_sample():
    """Each removal narrows the spread, so the next point looks extreme.

    Without a budget the test walks through the whole sample; a tenth is as
    far as it is allowed to go.
    """
    rng = np.random.default_rng(2)
    values = list(rng.normal(0, 1, 40)) + [12.0, -11.0, 13.5]
    flagged = st.grubbs(values)
    assert 3 <= len(flagged) <= max(1, int(0.1 * len(values)))


def test_outliers_are_listed_without_being_removed():
    rng = np.random.default_rng(3)
    frame = pd.DataFrame({
        "Groupe": ["A"] * 12 + ["B"] * 12,
        "Valeur": list(rng.normal(100, 8, 12)) + list(rng.normal(100, 8, 12)),
    })
    frame.loc[0, "Valeur"] = 400.0

    info = draw(PlotSpec(plot_type="bar", group="Groupe", y=["Valeur"]), frame)

    assert [r["Groupe"] for r in info.outliers] == ["A"]
    assert info.outliers[0]["Valeur"] == 400.0
    # and the descriptive table still counts it: flagging is not excluding
    counts = {r["Groupe"]: r["n"] for r in info.descriptives}
    assert counts == {"A": 12, "B": 12}


def test_outliers_do_not_wait_for_the_comparisons():
    """Descriptive, so it shows up without switching the statistics on."""
    frame = pd.DataFrame({"Groupe": ["A"] * 10,
                          "Valeur": [1, 1.1, 0.9, 1.05, 0.95, 1.02, 0.98,
                                     1.01, 0.99, 9.0]})
    info = draw(PlotSpec(plot_type="bar", group="Groupe", y=["Valeur"]), frame)
    assert info.outliers and info.outliers[0]["Valeur"] == 9.0
