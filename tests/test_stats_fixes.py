"""Regression tests for the two silent-failure bugs.

1. Two-factor bar charts produced no statistics at all.
2. Paired tests matched observations by position after dropping NaNs, which
   silently compared unrelated subjects.
"""
import os

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy import stats as sps


from plotea.core import demo, plotting  # noqa: E402
from plotea.core.plotspec import PlotSpec  # noqa: E402
from plotea.core.themes import get_theme  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)


def render(spec, df, name=None):
    fig = Figure(figsize=get_theme(spec.theme).figsize("double"))
    info = plotting.render(fig, spec, df)
    if name:
        fig.savefig(os.path.join(OUT, name), bbox_inches="tight")
    return info


# ==========================================================================
two = demo.two_factor()          # Genotype x Temps, 8 replicats par cellule


def test_grouped_stats():
    spec = PlotSpec(plot_type="bar", group="Temps", subgroup="Génotype",
                    y=["Activité"], theme="Cell", stats_enabled=True,
                    stats_test="t de Welch", ylabel="Activite (%)")
    info = render(spec, two.df, "fix_grouped_stats.png")
    # one comparison per category: WT vs Mutant at 0 h, 6 h and 24 h
    assert len(info.comparisons) == 3, len(info.comparisons)
    assert not info.warnings, info.warnings
    for c in info.comparisons:
        assert c.a.split(" / ")[0] == c.b.split(" / ")[0], (c.a, c.b)
        assert c.n_a == 8 and c.n_b == 8, (c.n_a, c.n_b)
        assert c.p_adj < 0.05, (c.a, c.b, c.p_adj)


def test_grouped_cells_and_series():
    spec = PlotSpec(plot_type="bar", group="Temps", subgroup="Génotype",
                    y=["Activité"], stats_enabled=True)
    info = render(spec, two.df)
    assert info.series == ["WT", "Mutant"], info.series
    assert len(info.stat_groups) == 6, list(info.stat_groups)
    assert "0 h / WT" in info.stat_groups, list(info.stat_groups)
    # the descriptive table must show the six cells, not the three categories
    assert len(info.descriptives) == 6, len(info.descriptives)
    assert info.omnibus == (), "pas d'ANOVA a un facteur sur un plan a deux"


def test_grouped_matches_manual():
    """The reported p must equal a Welch test run by hand on that cell."""
    spec = PlotSpec(plot_type="bar", group="Temps", subgroup="Génotype",
                    y=["Activité"], stats_enabled=True,
                    stats_test="t de Welch", stats_correction="Aucune")
    info = render(spec, two.df)
    for comp in info.comparisons:
        cat, sub_a = comp.a.split(" / ")
        _, sub_b = comp.b.split(" / ")
        def pick(sub):
            rows = two.df[(two.df["Temps"] == cat)
                          & (two.df["Génotype"] == sub)]
            return rows["Activité"].values

        expected = sps.ttest_ind(pick(sub_a), pick(sub_b),
                                 equal_var=False).pvalue
        assert abs(comp.p - float(expected)) < 1e-12, (comp.a, comp.p, expected)


# ==========================================================================

rng = np.random.default_rng(42)
n = 20
before = rng.normal(100, 12, n)
after = before + rng.normal(-8, 4, n)          # every subject drops a little
long_df = pd.DataFrame({
    "Sujet": [f"S{i:02d}" for i in range(n)] * 2,
    "Temps": ["Avant"] * n + ["Apres"] * n,
    "Score": np.concatenate([before, after]),
})


def test_paired_without_column_refuses():
    """No pairing key in long format -> no number at all, and a clear reason."""
    spec = PlotSpec(plot_type="bar", group="Temps", y=["Score"],
                    stats_enabled=True, stats_test="t apparié")
    info = render(spec, long_df)
    assert info.comparisons == [], info.comparisons
    assert any("appariement" in w for w in info.warnings), info.warnings


def test_paired_with_column():
    spec = PlotSpec(plot_type="bar", group="Temps", y=["Score"],
                    stats_enabled=True, stats_test="t apparié",
                    stats_pair_by="Sujet", stats_correction="Aucune")
    info = render(spec, long_df, "fix_paired.png")
    assert len(info.comparisons) == 1, info.comparisons
    comp = info.comparisons[0]
    expected = sps.ttest_rel(before, after).pvalue
    assert abs(comp.p - float(expected)) < 1e-12, (comp.p, expected)
    assert comp.n_a == n and comp.n_b == n, (comp.n_a, comp.n_b)


def test_pairing_survives_missing_values():
    """A hole in one group must drop that subject, not shift the pairing."""
    holed = long_df.copy()
    # remove two subjects from the "Avant" arm only
    drop = (holed["Temps"] == "Avant") & holed["Sujet"].isin(["S03", "S11"])
    holed.loc[drop, "Score"] = np.nan

    spec = PlotSpec(plot_type="bar", group="Temps", y=["Score"],
                    stats_enabled=True, stats_test="t apparié",
                    stats_pair_by="Sujet", stats_correction="Aucune")
    info = render(spec, holed)
    comp = info.comparisons[0]
    assert comp.n_a == n - 2, comp.n_a

    keep = [i for i in range(n) if i not in (3, 11)]
    expected = sps.ttest_rel(before[keep], after[keep]).pvalue
    assert abs(comp.p - float(expected)) < 1e-12, (comp.p, expected)


def test_shuffled_rows_give_same_result():
    """Row order must not change a paired result once subjects are named."""
    spec = PlotSpec(plot_type="bar", group="Temps", y=["Score"],
                    stats_enabled=True, stats_test="t apparié",
                    stats_pair_by="Sujet", stats_correction="Aucune")
    straight = render(spec, long_df).comparisons[0].p
    shuffled = render(spec, long_df.sample(frac=1, random_state=7)
                      ).comparisons[0].p
    assert abs(straight - shuffled) < 1e-12, (straight, shuffled)


def test_wide_format_pairs_on_the_row():
    """In wide format the table row is the subject, so no column is needed."""
    wide = pd.DataFrame({"Avant": before, "Apres": after})
    spec = PlotSpec(plot_type="box", y=["Avant", "Apres"], stats_enabled=True,
                    stats_test="Wilcoxon apparié", stats_correction="Aucune")
    info = render(spec, wide, "fix_paired_wide.png")
    assert len(info.comparisons) == 1, info.warnings
    expected = sps.wilcoxon(before, after).pvalue
    assert abs(info.comparisons[0].p - float(expected)) < 1e-12


def test_unpaired_path_untouched():
    """The ordinary tests must be exactly what they were."""
    viab = demo.viability()
    spec = PlotSpec(plot_type="bar", group="Traitement", y=["Viabilité"],
                    stats_enabled=True, stats_test="Auto")
    info = render(spec, viab.df)
    assert len(info.comparisons) == 6, len(info.comparisons)
    assert info.omnibus[0] == "ANOVA à un facteur", info.omnibus
