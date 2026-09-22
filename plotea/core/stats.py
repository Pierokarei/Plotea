"""Statistical tests, multiplicity correction and p-value formatting.

Kept independent from matplotlib and Qt so it can be unit-tested or reused in
a script. Only numpy/scipy are required.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

try:
    from scipy import stats as sps
    HAVE_SCIPY = True
except Exception:                                     # pragma: no cover
    HAVE_SCIPY = False

from .enums import CORRECTION, ERROR_TYPE, STATS_FORMAT, STATS_MODE, STATS_TEST

TESTS = STATS_TEST.keys()
CORRECTIONS = CORRECTION.keys()

#: Tests that compare the same subjects twice; they need a pairing key.
PAIRED_TESTS = {"paired_t", "wilcoxon"}


@dataclass
class Comparison:
    """Result of one pairwise comparison."""
    a: str
    b: str
    stat: float
    p: float
    p_adj: float
    test: str
    n_a: int = 0
    n_b: int = 0
    effect: float = float("nan")      # Cohen's d or rank-biserial r

    @property
    def stars(self) -> str:
        return p_to_stars(self.p_adj)


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def p_to_stars(p: float) -> str:
    if p is None or np.isnan(p):
        return "n.d."
    if p < 1e-4:
        return "****"
    if p < 1e-3:
        return "***"
    if p < 1e-2:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def p_to_text(p: float, decimals: int = 3) -> str:
    if p is None or np.isnan(p):
        return "n.d."
    if p < 1e-4:
        return "p < 0.0001"
    if p < 10 ** (-decimals):
        return f"p < {10 ** (-decimals):g}"
    return f"p = {p:.{decimals}f}"


def format_p(p: float, style: str) -> str:
    style = STATS_FORMAT.normalise(style)
    if style == "stars":
        return p_to_stars(p)
    if style == "pvalue":
        return p_to_text(p)
    stars = p_to_stars(p)
    return f"{stars} ({p_to_text(p)})" if stars != "ns" else p_to_text(p)


# --------------------------------------------------------------------------
# Assumptions
# --------------------------------------------------------------------------
#: Shapiro-Wilk is only trustworthy up to a few thousand observations, and
#: scipy says so; beyond that a fixed sample answers the same question.
SHAPIRO_MAX = 5000


def normality_p(x: np.ndarray) -> float:
    """Shapiro-Wilk p-value, computed on a sample when the group is large."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if not HAVE_SCIPY or x.size < 3:
        return float("nan")
    if x.size > SHAPIRO_MAX:
        x = np.random.default_rng(0).choice(x, SHAPIRO_MAX, replace=False)
    try:
        return float(sps.shapiro(x).pvalue)
    except Exception:
        return float("nan")


def is_normal(x: np.ndarray, alpha: float = 0.05) -> bool:
    p = normality_p(x)
    return True if np.isnan(p) else p > alpha


def equal_variance(groups: list[np.ndarray], alpha: float = 0.05) -> bool:
    clean = [np.asarray(g, float)[~np.isnan(np.asarray(g, float))]
             for g in groups]
    clean = [g for g in clean if g.size > 1]
    if not HAVE_SCIPY or len(clean) < 2:
        return True
    try:
        return float(sps.levene(*clean, center="median").pvalue) > alpha
    except Exception:
        return True


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    s = np.sqrt(((a.size - 1) * a.var(ddof=1) +
                 (b.size - 1) * b.var(ddof=1)) / (a.size + b.size - 2))
    return float((a.mean() - b.mean()) / s) if s else float("nan")


# --------------------------------------------------------------------------
# Multiplicity correction
# --------------------------------------------------------------------------
def adjust(pvals: list[float], method: str) -> list[float]:
    method = CORRECTION.normalise(method)
    p = np.asarray(pvals, dtype=float)
    n = p.size
    if n == 0 or method == "none":
        return list(p)
    if method == "bonferroni":
        return list(np.minimum(p * n, 1.0))
    order = np.argsort(p)
    out = np.empty(n, dtype=float)
    if method == "holm":
        running = 0.0
        for rank, idx in enumerate(order):
            val = (n - rank) * p[idx]
            running = max(running, val)
            out[idx] = min(running, 1.0)
        return list(out)
    # Benjamini-Hochberg
    ranked = p[order]
    adj = ranked * n / (np.arange(n) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out[order] = np.minimum(adj, 1.0)
    return list(out)


# --------------------------------------------------------------------------
# Omnibus + pairwise
# --------------------------------------------------------------------------
def omnibus(groups: dict[str, np.ndarray]) -> tuple[str, float, float]:
    """Global test across >2 groups. Returns (name, statistic, p)."""
    data = [np.asarray(v, float)[~np.isnan(np.asarray(v, float))]
            for v in groups.values()]
    data = [d for d in data if d.size > 1]
    if not HAVE_SCIPY or len(data) < 2:
        return ("", float("nan"), float("nan"))
    normal = all(is_normal(d) for d in data)
    try:
        if normal and equal_variance(data):
            res = sps.f_oneway(*data)
            return ("ANOVA à un facteur", float(res.statistic),
                    float(res.pvalue))
        res = sps.kruskal(*data)
        return ("Kruskal-Wallis", float(res.statistic), float(res.pvalue))
    except Exception:
        return ("", float("nan"), float("nan"))


def _pick_test(a: np.ndarray, b: np.ndarray) -> str:
    if is_normal(a) and is_normal(b):
        return "welch" if not equal_variance([a, b]) else "student"
    return "mannwhitney"


def pick_family_test(groups: dict[str, np.ndarray]) -> str:
    """Choose one test for the whole figure, not one per pair.

    Reporting a mix of Student and Mann-Whitney across the same set of bars is
    hard to justify in a legend, so the assumptions are checked once on every
    group involved and the verdict applies to all comparisons.
    """
    data = [np.asarray(v, float) for v in groups.values()]
    data = [d[~np.isnan(d)] for d in data]
    data = [d for d in data if d.size >= 2]
    if len(data) < 2:
        return "welch"
    if not all(is_normal(d) for d in data):
        return "mannwhitney"
    return "student" if equal_variance(data) else "welch"


def _run_pair(a: np.ndarray, b: np.ndarray, test: str):
    """Run one test. Paired tests receive arrays already matched element-wise."""
    if test == "auto":
        test = _pick_test(a, b)
    if test == "student":
        r = sps.ttest_ind(a, b, equal_var=True)
    elif test == "welch":
        r = sps.ttest_ind(a, b, equal_var=False)
    elif test == "paired_t":
        r = sps.ttest_rel(a, b)
    elif test == "wilcoxon":
        r = sps.wilcoxon(a, b)
    elif test in ("mannwhitney", "kruskal_dunn"):
        r = sps.mannwhitneyu(a, b, alternative="two-sided")
        test = "mannwhitney"
    elif test == "anova_tukey":
        r = sps.ttest_ind(a, b, equal_var=True)
        test = "tukey"
    else:
        r = sps.ttest_ind(a, b, equal_var=False)
        test = "welch"
    return TEST_LABELS.get(test, test), float(r.statistic), float(r.pvalue)


def matched(paired: dict, a: str, b: str) -> tuple[np.ndarray, np.ndarray]:
    """Values of two groups aligned on their subject key.

    Only subjects present in both groups with a finite value on both sides are
    kept, so a missing measurement never shifts the pairing.
    """
    left, right = paired.get(a, {}), paired.get(b, {})
    va, vb = [], []
    for subject, value in left.items():
        if subject not in right:
            continue
        x, y = float(value), float(right[subject])
        if np.isfinite(x) and np.isfinite(y):
            va.append(x)
            vb.append(y)
    return np.asarray(va, dtype=float), np.asarray(vb, dtype=float)


def pairwise(groups: dict[str, np.ndarray], test: str = "auto",
             correction: str = "holm", mode: str = "all_pairs",
             control: str = "", pairs: list | None = None,
             paired: dict | None = None) -> list[Comparison]:
    """Every requested pairwise comparison, corrected for multiplicity.

    `pairs` restricts which comparisons are made (used by two-factor plots).
    `paired` maps each group to {subject: value} and is required by the paired
    tests: without it they would compare unrelated observations.
    """
    if not HAVE_SCIPY:
        return []
    test = STATS_TEST.normalise(test)
    mode = STATS_MODE.normalise(mode)
    if test in PAIRED_TESTS and not paired:
        return []
    clean = {}
    for k, v in groups.items():
        arr = np.asarray(v, dtype=float)
        arr = arr[~np.isnan(arr)]
        if arr.size >= 2:
            clean[k] = arr
    keys = list(clean)
    if len(keys) < 2:
        return []

    if test == "auto":
        test = pick_family_test(clean)

    if pairs is not None:
        pairs = [(a, b) for a, b in pairs if a in clean and b in clean]
    elif mode == "vs_control" and control in clean:
        pairs = [(control, k) for k in keys if k != control]
    else:
        pairs = list(itertools.combinations(keys, 2))

    # Tukey HSD handles its own family-wise error rate
    if test == "anova_tukey" and len(keys) > 2:
        try:
            res = sps.tukey_hsd(*[clean[k] for k in keys])
            out = []
            for a, b in pairs:
                i, j = keys.index(a), keys.index(b)
                p = float(res.pvalue[i, j])
                out.append(Comparison(a, b, float(res.statistic[i, j]), p, p,
                                      "Tukey HSD", clean[a].size, clean[b].size,
                                      cohens_d(clean[a], clean[b])))
            return out
        except Exception:
            pass

    raw = []
    for a, b in pairs:
        if test in PAIRED_TESTS:
            va, vb = matched(paired, a, b)
            if va.size < 2:          # no usable subject measured on both sides
                continue
        else:
            va, vb = clean[a], clean[b]
        try:
            name, stat, p = _run_pair(va, vb, test)
        except Exception:
            continue
        raw.append(Comparison(a, b, stat, p, p, name, va.size, vb.size,
                              cohens_d(va, vb)))
    adjusted = adjust([c.p for c in raw], correction)
    for c, pa in zip(raw, adjusted):
        c.p_adj = pa
    return raw


def _effect_coding(levels: list[str], observed: list[str]) -> np.ndarray:
    """Sum-to-zero contrasts: k-1 columns for k levels."""
    last = levels[-1]
    cols = []
    for lev in levels[:-1]:
        cols.append([1.0 if o == lev else (-1.0 if o == last else 0.0)
                     for o in observed])
    return np.asarray(cols, dtype=float).T if cols else np.zeros((len(observed),
                                                                  0))


def two_way_anova(cells: dict, factor_a: str = "Facteur A",
                  factor_b: str = "Facteur B") -> tuple[list[dict], str]:
    """Two-way ANOVA with interaction on cells keyed by (level_a, level_b).

    Sums of squares are type III: each effect is measured by how much residual
    variance it removes from the full model, which is what an unbalanced design
    needs. Returns (table, message); the table is empty when it cannot be run.
    """
    if not HAVE_SCIPY:
        return [], "SciPy est requis."
    levels_a, levels_b = [], []
    for key in cells:
        a, b = str(key[0]), str(key[1])
        if a not in levels_a:
            levels_a.append(a)
        if b not in levels_b:
            levels_b.append(b)
    if len(levels_a) < 2 or len(levels_b) < 2:
        return [], "Deux niveaux au minimum sont nécessaires par facteur."

    y, obs_a, obs_b = [], [], []
    for key, values in cells.items():
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        for v in arr:
            y.append(v)
            obs_a.append(str(key[0]))
            obs_b.append(str(key[1]))
    if len(cells) < len(levels_a) * len(levels_b):
        return [], "Certaines combinaisons n'ont aucune donnée."
    y = np.asarray(y, dtype=float)

    ca = _effect_coding(levels_a, obs_a)
    cb = _effect_coding(levels_b, obs_b)
    cab = np.column_stack([ca[:, i] * cb[:, j]
                           for i in range(ca.shape[1])
                           for j in range(cb.shape[1])]) if ca.size and cb.size \
        else np.zeros((y.size, 0))
    ones = np.ones((y.size, 1))

    blocks = {factor_a: ca, factor_b: cb,
              f"{factor_a} x {factor_b}": cab}
    full = np.column_stack([ones, ca, cb, cab])
    df_error = y.size - np.linalg.matrix_rank(full)
    if df_error < 1:
        return [], "Pas assez d'observations pour estimer le modèle."

    def rss(matrix: np.ndarray) -> float:
        beta, *_ = np.linalg.lstsq(matrix, y, rcond=None)
        resid = y - matrix @ beta
        return float(resid @ resid)

    rss_full = rss(full)
    mse = rss_full / df_error
    rows = []
    for name, block in blocks.items():
        if block.shape[1] == 0:
            continue
        others = [ones] + [b for key, b in blocks.items()
                           if key != name and b.shape[1]]
        ss = rss(np.column_stack(others)) - rss_full
        ss = max(ss, 0.0)
        df = block.shape[1]
        f = (ss / df) / mse if mse > 0 else float("nan")
        p = float(sps.f.sf(f, df, df_error)) if np.isfinite(f) else float("nan")
        rows.append({"Source": name, "SS": ss, "ddl": df, "MS": ss / df,
                     "F": f, "p": p,
                     "eta2 partiel": ss / (ss + rss_full) if ss + rss_full
                     else float("nan")})
    rows.append({"Source": "Residus", "SS": rss_full, "ddl": df_error,
                 "MS": mse, "F": float("nan"), "p": float("nan"),
                 "eta2 partiel": float("nan")})
    return rows, ""


def describe(groups: dict[str, np.ndarray]) -> list[dict]:
    """Descriptive table used by the Stats panel."""
    rows = []
    for name, v in groups.items():
        arr = np.asarray(v, dtype=float)
        arr = arr[~np.isnan(arr)]
        if arr.size == 0:
            continue
        sd = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        sem = sd / np.sqrt(arr.size) if arr.size > 1 else 0.0
        rows.append({
            "Groupe": name, "n": int(arr.size), "Moyenne": float(arr.mean()),
            "SD": sd, "SEM": sem, "Médiane": float(np.median(arr)),
            "Q1": float(np.percentile(arr, 25)),
            "Q3": float(np.percentile(arr, 75)),
            "Min": float(arr.min()), "Max": float(arr.max()),
            "IC95 bas": float(arr.mean() - 1.96 * sem),
            "IC95 haut": float(arr.mean() + 1.96 * sem),
            "Normalité (p)": normality_p(arr),
        })
    return rows


#: Test key -> the wording that belongs in a figure legend or a table.
TEST_LABELS = {
    "student": "t de Student", "welch": "t de Welch",
    "paired_t": "t apparié", "mannwhitney": "Mann-Whitney",
    "wilcoxon": "Wilcoxon apparié", "tukey": "Tukey HSD",
}


def error_value(arr: np.ndarray, kind: str) -> tuple[float, float]:
    """Lower/upper error magnitudes for a group, given the error type."""
    arr = np.asarray(arr, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return (0.0, 0.0)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    sem = sd / np.sqrt(arr.size) if arr.size > 1 else 0.0
    kind = ERROR_TYPE.normalise(kind)
    if kind == "sd":
        return (sd, sd)
    if kind == "sem":
        return (sem, sem)
    if kind == "ci95":
        if HAVE_SCIPY and arr.size > 1:
            t = float(sps.t.ppf(0.975, arr.size - 1))
        else:
            t = 1.96
        return (t * sem, t * sem)
    if kind == "minmax":
        return (mean - float(arr.min()), float(arr.max()) - mean)
    return (0.0, 0.0)
