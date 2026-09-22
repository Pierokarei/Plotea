"""Two-way ANOVA and family-wide test selection."""

import numpy as np
from matplotlib.figure import Figure

from plotea.core import demo, plotting, stats
from plotea.core.plotspec import PlotSpec


def test_balanced_matches_hand_computation():
    """On a balanced design, type III SS equal the textbook formulas."""
    rng = np.random.default_rng(3)
    cells, means = {}, {("A", "X"): 10.0, ("A", "Y"): 14.0,
                        ("B", "X"): 12.0, ("B", "Y"): 25.0}
    n = 9
    for key, mu in means.items():
        cells[key] = rng.normal(mu, 2.0, n)
    rows, msg = stats.two_way_anova(cells, "Facteur", "Niveau")
    assert not msg, msg
    assert [r["Source"] for r in rows] == [
        "Facteur", "Niveau", "Facteur x Niveau", "Residus"], rows

    y = np.concatenate([cells[k] for k in cells])
    grand = y.mean()
    levels_a = ["A", "B"]
    levels_b = ["X", "Y"]
    cell_means = {k: v.mean() for k, v in cells.items()}
    a_means = {a: np.mean([cell_means[(a, b)] for b in levels_b])
               for a in levels_a}
    b_means = {b: np.mean([cell_means[(a, b)] for a in levels_a])
               for b in levels_b}
    ss_a = n * len(levels_b) * sum((m - grand) ** 2 for m in a_means.values())
    ss_b = n * len(levels_a) * sum((m - grand) ** 2 for m in b_means.values())
    ss_ab = n * sum((cell_means[(a, b)] - a_means[a] - b_means[b] + grand) ** 2
                    for a in levels_a for b in levels_b)
    ss_err = sum(float(((v - v.mean()) ** 2).sum()) for v in cells.values())

    table = {r["Source"]: r for r in rows}
    assert abs(table["Facteur"]["SS"] - ss_a) < 1e-8, (table["Facteur"]["SS"],
                                                       ss_a)
    assert abs(table["Niveau"]["SS"] - ss_b) < 1e-8
    assert abs(table["Facteur x Niveau"]["SS"] - ss_ab) < 1e-8
    assert abs(table["Residus"]["SS"] - ss_err) < 1e-8
    assert table["Residus"]["ddl"] == 4 * (n - 1)


def test_detects_interaction():
    """A crossed design must flag the interaction, a parallel one must not."""
    rng = np.random.default_rng(11)
    crossed = {("A", "X"): rng.normal(10, 1.5, 12),
               ("A", "Y"): rng.normal(20, 1.5, 12),
               ("B", "X"): rng.normal(20, 1.5, 12),
               ("B", "Y"): rng.normal(10, 1.5, 12)}
    rows, _ = stats.two_way_anova(crossed)
    inter = [r for r in rows if "x" in r["Source"]][0]
    assert inter["p"] < 1e-6, inter

    parallel = {("A", "X"): rng.normal(10, 1.5, 12),
                ("A", "Y"): rng.normal(15, 1.5, 12),
                ("B", "X"): rng.normal(14, 1.5, 12),
                ("B", "Y"): rng.normal(19, 1.5, 12)}
    rows, _ = stats.two_way_anova(parallel)
    inter = [r for r in rows if "x" in r["Source"]][0]
    assert inter["p"] > 0.05, inter


def test_unbalanced_runs():
    rng = np.random.default_rng(5)
    cells = {("A", "X"): rng.normal(10, 2, 12), ("A", "Y"): rng.normal(14, 2, 7),
             ("B", "X"): rng.normal(12, 2, 9), ("B", "Y"): rng.normal(25, 2, 15)}
    rows, msg = stats.two_way_anova(cells)
    assert not msg, msg
    assert rows[-1]["ddl"] == 12 + 7 + 9 + 15 - 4
    assert all(r["SS"] >= 0 for r in rows)


def test_refuses_empty_cell():
    rng = np.random.default_rng(1)
    cells = {("A", "X"): rng.normal(10, 2, 6), ("A", "Y"): rng.normal(12, 2, 6),
             ("B", "X"): rng.normal(11, 2, 6)}
    rows, msg = stats.two_way_anova(cells)
    assert rows == [] and msg, (rows, msg)


def test_anova_surfaces_in_render():
    two = demo.two_factor()
    spec = PlotSpec(plot_type="bar", group="Temps", subgroup="Génotype",
                    y=["Activité"], stats_enabled=True)
    fig = Figure()
    info = plotting.render(fig, spec, two.df)
    assert len(info.anova) == 4, info.anova
    sources = [r["Source"] for r in info.anova]
    assert sources[0] == "Temps" and sources[1] == "Génotype", sources
    assert info.anova[0]["p"] < 0.001 and info.anova[1]["p"] < 0.001
    # no artificial one-way omnibus on a two-factor design
    assert info.omnibus == ()


def test_one_test_for_every_pair():
    """A skewed group must switch the whole figure to a rank test."""
    rng = np.random.default_rng(8)
    groups = {"A": rng.normal(10, 1, 40), "B": rng.normal(12, 1, 40),
              "C": rng.lognormal(2.2, 0.9, 40)}   # clearly not normal
    comps = stats.pairwise(groups, "Auto", "Holm")
    used = {c.test for c in comps}
    assert used == {"Mann-Whitney"}, used

    normal = {"A": rng.normal(10, 1, 40), "B": rng.normal(12, 1, 40),
              "C": rng.normal(14, 1, 40)}
    comps = stats.pairwise(normal, "Auto", "Holm")
    assert len({c.test for c in comps}) == 1, {c.test for c in comps}


def test_family_choice_reported():
    groups = {"A": np.array([1.0, 2, 3, 4, 5, 6, 7, 8]),
              "B": np.array([2.0, 3, 4, 5, 6, 7, 8, 9])}
    assert stats.pick_family_test(groups) in {"student", "welch"}
