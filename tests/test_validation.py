"""What the other test files took for granted, checked against definitions.

The descriptive table, the classical one-way ANOVA with Tukey's HSD, and
the corrections for multiple comparisons were only checked for their
labels and their shape. Here each is computed again from its textbook
definition, and the corrections on the published example of Benjamini and
Hochberg (1995). The interval of a mean is also checked by simulation:
built on Student's t it covers 95 times in 100 even with five values,
where 1.96 standard errors would cover about 88.
"""
import numpy as np
import pandas as pd
import pytest
import scipy.stats as sps

from plotea.core import stats as st
from plotea.core.dataset import aggregate

RNG = np.random.default_rng(1995)
GROUPS = {"A": RNG.normal(10, 2, 8), "B": RNG.normal(12, 2, 11),
          "C": RNG.normal(15, 3, 9)}


# --------------------------------------------------------------------------
# Descriptive statistics
# --------------------------------------------------------------------------
def test_descriptives_follow_their_definitions():
    for row, (name, values) in zip(st.describe(GROUPS), GROUPS.items()):
        n = values.size
        mean = values.sum() / n
        sd = np.sqrt(((values - mean) ** 2).sum() / (n - 1))
        sem = sd / np.sqrt(n)
        half = sps.t.ppf(0.975, n - 1) * sem
        assert row["Groupe"] == name and row["n"] == n
        assert row["Moyenne"] == pytest.approx(mean, rel=1e-12)
        assert row["SD"] == pytest.approx(sd, rel=1e-12)
        assert row["SEM"] == pytest.approx(sem, rel=1e-12)
        assert row["IC95 bas"] == pytest.approx(mean - half, rel=1e-12)
        assert row["IC95 haut"] == pytest.approx(mean + half, rel=1e-12)
        ordered = np.sort(values)
        assert row["Médiane"] == pytest.approx(np.median(ordered))
        assert (row["Min"], row["Max"]) == (ordered[0], ordered[-1])


def test_the_interval_of_a_mean_covers_95_times_in_100():
    rng = np.random.default_rng(3)
    draws, covered = 20000, 0
    samples = rng.normal(50, 7, (draws, 5))
    for sample in samples:
        row = st.describe({"x": sample})[0]
        covered += row["IC95 bas"] <= 50 <= row["IC95 haut"]
    assert 0.94 < covered / draws < 0.96, covered / draws


def test_error_bars_and_summary_tables_give_the_same_interval():
    values = GROUPS["A"]
    row = st.describe({"A": values})[0]
    low, high = st.error_value(values, "ci95")
    assert row["Moyenne"] - low == pytest.approx(row["IC95 bas"])
    assert row["Moyenne"] + high == pytest.approx(row["IC95 haut"])
    table = aggregate(pd.DataFrame({"g": "A", "v": values}), "g", "v")
    assert table["IC95"].iloc[0] == pytest.approx(high)


# --------------------------------------------------------------------------
# One-way ANOVA and Tukey's HSD
# --------------------------------------------------------------------------
def anova_by_hand(groups):
    data = list(groups.values())
    everything = np.concatenate(data)
    k, total = len(data), everything.size
    between = sum(g.size * (g.mean() - everything.mean()) ** 2 for g in data)
    within = sum(((g - g.mean()) ** 2).sum() for g in data)
    return between / (k - 1), within / (total - k), k, total


def test_the_one_way_anova_is_the_textbook_one():
    msb, msw, k, total = anova_by_hand(GROUPS)
    name, F, p = st.omnibus(GROUPS, "anova_tukey")
    assert name == "ANOVA à un facteur"
    assert F == pytest.approx(msb / msw, rel=1e-10)
    assert p == pytest.approx(sps.f.sf(msb / msw, k - 1, total - k),
                              rel=1e-8)


def test_tukeys_hsd_is_the_studentized_range_of_each_difference():
    """Tukey-Kramer: |mean difference| over sqrt(MSE / 2 (1/na + 1/nb)),
    referred to the studentized range of k means on N - k df."""
    _msb, mse, k, total = anova_by_hand(GROUPS)
    comps = st.pairwise(GROUPS, "anova_tukey", "none")
    assert len(comps) == 3
    for comp in comps:
        a, b = GROUPS[comp.a], GROUPS[comp.b]
        q = abs(a.mean() - b.mean()) / np.sqrt(
            mse / 2 * (1 / a.size + 1 / b.size))
        expected = sps.studentized_range.sf(q, k, total - k)
        assert comp.p == pytest.approx(expected, rel=1e-6, abs=1e-12)
        assert comp.p_adj == comp.p          # it corrects itself


# --------------------------------------------------------------------------
# Corrections for multiple comparisons
# --------------------------------------------------------------------------
#: Benjamini & Hochberg (1995), section 4: fifteen p-values from a trial of
#: thrombolysis. At 5 %, Bonferroni and Holm reject three hypotheses, the
#: false discovery rate procedure four.
PUBLISHED = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
             0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.000]


@pytest.mark.parametrize("method, rejected", [
    ("bonferroni", 3), ("holm", 3), ("fdr_bh", 4), ("none", 9)])
def test_the_published_example_rejects_what_the_paper_says(method, rejected):
    adjusted = st.adjust(PUBLISHED, method)
    assert sum(p <= 0.05 for p in adjusted) == rejected


def test_each_correction_follows_its_definition():
    p = [0.04, 0.01, 0.03, 0.002, 0.2]
    m = len(p)
    assert st.adjust(p, "bonferroni") == pytest.approx(
        [min(1.0, x * m) for x in p])
    # Holm, by hand: sorted 0.002 0.01 0.03 0.04 0.2, times 5 4 3 2 1,
    # then never smaller than the one before
    assert st.adjust(p, "holm") == pytest.approx(
        [0.09, 0.04, 0.09, 0.01, 0.2])
    # Benjamini-Hochberg, by hand: p * m / rank, then never larger than
    # the one after
    assert st.adjust(p, "fdr_bh") == pytest.approx(
        [0.05, 0.025, 0.05, 0.01, 0.2])
    assert st.adjust(p, "none") == pytest.approx(p)
