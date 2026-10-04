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

from ..i18n import tr
from .enums import CORRECTION, ERROR_TYPE, STATS_FORMAT, STATS_MODE, STATS_TEST

TESTS = STATS_TEST.keys()
CORRECTIONS = CORRECTION.keys()

#: Tests that compare the same subjects twice; they need a pairing key.
PAIRED_TESTS = {"paired_t", "wilcoxon", "rm_anova"}

#: Tests that only mean something against a designated control group.
CONTROL_TESTS = {"dunnett"}


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
def omnibus(groups: dict[str, np.ndarray], test: str = "auto"
            ) -> tuple[str, float, float]:
    """Global test across >2 groups. Returns (name, statistic, p).

    A test chosen by name brings its own global test - "ANOVA + Tukey" an
    ANOVA, "Kruskal-Wallis + Dunn" a Kruskal-Wallis - whatever normality
    says; only the other choices let the assumptions decide.
    """
    data = [np.asarray(v, float)[~np.isnan(np.asarray(v, float))]
            for v in groups.values()]
    data = [d for d in data if d.size > 1]
    if not HAVE_SCIPY or len(data) < 2:
        return ("", float("nan"), float("nan"))
    if test == "anova_tukey":
        parametric = True
    elif test == "kruskal_dunn":
        parametric = False
    else:
        parametric = all(is_normal(d) for d in data) and equal_variance(data)
    try:
        if parametric:
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


def pick_paired_test(paired: dict, labels: list[str]) -> str:
    """The paired test "auto" means on a before-after plot.

    More than two conditions: a repeated-measures ANOVA. Two: a paired t
    test if the differences look normal - their normality is what the t
    test assumes, not that of each condition - and Wilcoxon's signed-rank
    test otherwise.
    """
    if len(labels) > 2:
        return "rm_anova"
    a, b = matched(paired, labels[0], labels[1])
    if a.size < 3:
        return "paired_t"
    return "paired_t" if is_normal(b - a) else "wilcoxon"


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

    # Dunnett compares every group with one control and controls the
    # family-wise error rate itself, which is why it beats "all pairs then
    # Bonferroni" when the control is the only comparison of interest.
    if test == "dunnett":
        if control not in clean:
            return []
        others = [k for k in keys if k != control]
        if not others:
            return []
        try:
            # SciPy integrates the multivariate t by Monte Carlo, so the
            # p-values wobble from one call to the next. A fixed seed keeps
            # the same data giving the same stars on every render.
            res = sps.dunnett(*[clean[k] for k in others],
                              control=clean[control],
                              random_state=np.random.default_rng(12345))
        except Exception:
            return []
        out = []
        for name, stat, p in zip(others, np.atleast_1d(res.statistic),
                                 np.atleast_1d(res.pvalue)):
            out.append(Comparison(control, name, float(stat), float(p),
                                  float(p), "Dunnett", clean[control].size,
                                  clean[name].size,
                                  cohens_d(clean[control], clean[name])))
        return out

    if test == "kruskal_dunn":
        out = dunn(clean, pairs)
        for comp, adjusted in zip(out, adjust([c.p for c in out],
                                              correction)):
            comp.p_adj = adjusted
        return out

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

    if test == "rm_anova":
        test = "paired_t"        # the omnibus is elsewhere; pairs are paired t

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


def dunn(groups: dict[str, np.ndarray], pairs: list) -> list[Comparison]:
    """Dunn's test: pairs compared on the mean ranks of the pooled data.

    The follow-up of a Kruskal-Wallis test. Every value is ranked once,
    across all the groups - not pair by pair as Mann-Whitney would - and
    the difference of two mean ranks is a z with a correction for ties.
    Raw p-values: the caller corrects them for multiplicity.
    """
    keys = list(groups)
    values = np.concatenate([groups[k] for k in keys])
    ranks = sps.rankdata(values)
    n_total = values.size
    _, ties = np.unique(values, return_counts=True)
    tie_term = float(np.sum(ties ** 3 - ties)) / (12.0 * (n_total - 1))
    spread = n_total * (n_total + 1) / 12.0 - tie_term
    mean_rank, size, start = {}, {}, 0
    for k in keys:
        size[k] = groups[k].size
        mean_rank[k] = float(ranks[start:start + size[k]].mean())
        start += size[k]
    out = []
    for a, b in pairs:
        se = np.sqrt(spread * (1.0 / size[a] + 1.0 / size[b]))
        z = (mean_rank[a] - mean_rank[b]) / se if se > 0 else 0.0
        p = float(2 * sps.norm.sf(abs(z)))
        out.append(Comparison(a, b, float(z), p, p, "Dunn", size[a], size[b],
                              cohens_d(groups[a], groups[b])))
    return out


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
        return [], tr("SciPy est requis.")
    levels_a, levels_b = [], []
    for key in cells:
        a, b = str(key[0]), str(key[1])
        if a not in levels_a:
            levels_a.append(a)
        if b not in levels_b:
            levels_b.append(b)
    if len(levels_a) < 2 or len(levels_b) < 2:
        return [], tr("Deux niveaux au minimum sont nécessaires par facteur.")

    y, obs_a, obs_b = [], [], []
    for key, values in cells.items():
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        for v in arr:
            y.append(v)
            obs_a.append(str(key[0]))
            obs_b.append(str(key[1]))
    if len(cells) < len(levels_a) * len(levels_b):
        return [], tr("Certaines combinaisons n'ont aucune donnée.")
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
        return [], tr("Pas assez d'observations pour estimer le modèle.")

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
    rows.append({"Source": "Résidus", "SS": rss_full, "ddl": df_error,
                 "MS": mse, "F": float("nan"), "p": float("nan"),
                 "eta2 partiel": float("nan")})
    return rows, ""


def complete_cases(paired: dict) -> tuple[list[str], list[str], np.ndarray]:
    """Subjects measured in every condition, as a subjects x conditions grid.

    A within-subject design has nothing to say about a subject seen in only
    half the conditions, and averaging over the ones it did attend would
    silently turn it into a between-subject comparison.
    """
    conditions = list(paired)
    if len(conditions) < 2:
        return conditions, [], np.zeros((0, 0))
    subjects = [s for s in paired[conditions[0]]
                if all(s in paired[c] for c in conditions)]
    kept, rows = [], []
    for subject in subjects:
        values = [float(paired[c][subject]) for c in conditions]
        if all(np.isfinite(v) for v in values):
            kept.append(str(subject))
            rows.append(values)
    grid = np.asarray(rows, dtype=float) if rows else np.zeros((0,
                                                                len(conditions)))
    return conditions, kept, grid


def greenhouse_geisser(grid: np.ndarray) -> float:
    """Sphericity correction factor, in [1/(k-1), 1].

    A repeated-measures ANOVA assumes every pair of conditions differs with
    the same variance. When that fails, the F test is too generous; epsilon
    shrinks the degrees of freedom by how far the data depart from it.
    """
    n, k = grid.shape
    if k < 3 or n < 2:
        return 1.0                      # with two conditions there is nothing
    cov = np.cov(grid, rowvar=False)     # k x k
    mean_all = float(cov.mean())
    mean_diag = float(np.mean(np.diag(cov)))
    row_means = cov.mean(axis=1)
    numerator = (k ** 2) * (mean_diag - mean_all) ** 2
    denominator = (k - 1) * (float(np.sum(cov ** 2))
                             - 2 * k * float(np.sum(row_means ** 2))
                             + (k ** 2) * mean_all ** 2)
    if denominator <= 0:
        return 1.0
    return float(min(1.0, max(1.0 / (k - 1), numerator / denominator)))


def repeated_measures_anova(paired: dict) -> tuple[list[dict], str]:
    """One-way ANOVA for a within-subject design.

    Each subject is its own control, so the variability between subjects is
    taken out of the error term instead of hiding the effect. Returns
    (table, message); the table is empty when the design cannot support it.
    """
    if not HAVE_SCIPY:
        return [], tr("SciPy est requis.")
    conditions, subjects, grid = complete_cases(paired)
    if len(conditions) < 2:
        return [], tr("Deux conditions au minimum sont nécessaires.")
    n, k = grid.shape
    if n < 2:
        return [], (tr("Aucun sujet mesuré dans toutes les conditions : "
                    "une ANOVA à mesures répétées est impossible."))

    grand = float(grid.mean())
    ss_cond = n * float(np.sum((grid.mean(axis=0) - grand) ** 2))
    ss_subj = k * float(np.sum((grid.mean(axis=1) - grand) ** 2))
    ss_total = float(np.sum((grid - grand) ** 2))
    ss_error = max(ss_total - ss_cond - ss_subj, 0.0)
    df_cond, df_subj = k - 1, n - 1
    df_error = df_cond * df_subj
    if df_error < 1 or ss_error <= 0:
        return [], tr("Pas assez de sujets pour estimer l'erreur.")

    ms_cond, ms_error = ss_cond / df_cond, ss_error / df_error
    f = ms_cond / ms_error
    p = float(sps.f.sf(f, df_cond, df_error))
    epsilon = greenhouse_geisser(grid)
    p_gg = float(sps.f.sf(f, df_cond * epsilon, df_error * epsilon))

    rows = [
        {"Source": "Conditions", "SS": ss_cond, "ddl": df_cond, "MS": ms_cond,
         "F": f, "p": p, "eta2 partiel": ss_cond / (ss_cond + ss_error)},
        {"Source": "Sujets", "SS": ss_subj, "ddl": df_subj,
         "MS": ss_subj / df_subj, "F": float("nan"), "p": float("nan"),
         "eta2 partiel": float("nan")},
        {"Source": "Résidus", "SS": ss_error, "ddl": df_error, "MS": ms_error,
         "F": float("nan"), "p": float("nan"), "eta2 partiel": float("nan")},
    ]
    message = tr("{subjects} sujets complets sur {conditions} conditions - "
                 "Greenhouse-Geisser epsilon = {epsilon:.3f}, "
                 "p corrigé = {p}").format(subjects=n, conditions=k,
                                           epsilon=epsilon, p=p_to_text(p_gg))
    return rows, message


# --------------------------------------------------------------------------
# Survival
# --------------------------------------------------------------------------
def _survival_input(times, events):
    """Clean (time, event) pairs, sorted by time. event: 1 seen, 0 censored."""
    t = np.asarray(times, dtype=float)
    if events is None:
        e = np.ones_like(t)
    else:
        e = np.asarray(events, dtype=float)
        if e.size != t.size:
            e = np.ones_like(t)
    ok = np.isfinite(t) & np.isfinite(e) & (t >= 0)
    t, e = t[ok], e[ok]
    order = np.argsort(t, kind="stable")
    return t[order], (e[order] > 0).astype(int)


def kaplan_meier(times, events=None, alpha: float = 0.05) -> dict:
    """Survival curve for right-censored data.

    A censored subject - lost to follow-up, or still alive when the study
    ended - is not a survivor and not a death: it leaves the population at
    risk without an event, which is exactly what this estimator does with it
    and what a simple proportion cannot.

    The confidence band uses Greenwood's variance on the log(-log) scale, so
    it never escapes [0, 1] near the ends of the curve.
    """
    t, e = _survival_input(times, events)
    out = {"time": [0.0], "survival": [1.0], "lower": [1.0], "upper": [1.0],
           "censored_time": [], "censored_survival": [],
           "n": int(t.size), "events": int(e.sum()),
           "censored": int(t.size - e.sum()), "median": float("nan")}
    if t.size == 0:
        return out

    at_risk = t.size
    surv = 1.0
    cumulative = 0.0           # sum of d / (n (n - d)) for Greenwood
    z = float(sps.norm.ppf(1 - alpha / 2)) if HAVE_SCIPY else 1.959964
    for moment in np.unique(t):
        here = t == moment
        deaths = int(e[here].sum())
        censored_here = int(here.sum() - deaths)
        if deaths:
            surv *= 1.0 - deaths / at_risk
            if at_risk > deaths:
                cumulative += deaths / (at_risk * (at_risk - deaths))
            out["time"].append(float(moment))
            out["survival"].append(float(surv))
            if 0.0 < surv < 1.0 and cumulative > 0:
                spread = z * np.sqrt(cumulative) / abs(np.log(surv))
                out["lower"].append(float(surv ** np.exp(spread)))
                out["upper"].append(float(surv ** np.exp(-spread)))
            else:
                out["lower"].append(float(surv))
                out["upper"].append(float(surv))
        if censored_here:
            out["censored_time"].append(float(moment))
            out["censored_survival"].append(float(surv))
        at_risk -= int(here.sum())
        if at_risk <= 0:
            break

    # Carry the curve to the end of follow-up: after the last event it is
    # flat, and stopping earlier leaves the censoring marks hanging in the
    # air beyond the line they belong to.
    last = float(t[-1])
    if last > out["time"][-1]:
        out["time"].append(last)
        for key in ("survival", "lower", "upper"):
            out[key].append(out[key][-1])

    survival = np.asarray(out["survival"])
    reached = np.nonzero(survival <= 0.5)[0]
    if reached.size:
        out["median"] = float(out["time"][int(reached[0])])
    return out


def logrank(curves: dict) -> tuple[float, float, int]:
    """Mantel-Cox test across k groups: (chi2, p, degrees of freedom).

    At every time where something happens, each group is credited with the
    deaths it would have had if survival were the same everywhere; the test
    asks whether the gap between observed and expected is more than chance.
    """
    if not HAVE_SCIPY:
        return (float("nan"), float("nan"), 0)
    groups = {}
    for name, (times, events) in curves.items():
        t, e = _survival_input(times, events)
        if t.size:
            groups[name] = (t, e)
    k = len(groups)
    if k < 2:
        return (float("nan"), float("nan"), 0)

    moments = np.unique(np.concatenate([t for t, _ in groups.values()]))
    names = list(groups)
    observed = np.zeros(k)
    expected = np.zeros(k)
    variance = np.zeros((k, k))
    for moment in moments:
        at_risk = np.array([float(np.sum(t >= moment))
                            for t, _ in groups.values()])
        deaths = np.array([float(np.sum((t == moment) & (e == 1)))
                           for t, e in groups.values()])
        total_risk = at_risk.sum()
        total_deaths = deaths.sum()
        if total_deaths == 0 or total_risk <= 1:
            continue
        share = at_risk / total_risk
        observed += deaths
        expected += total_deaths * share
        factor = (total_deaths * (total_risk - total_deaths)
                  / (total_risk - 1))
        variance += factor * (np.diag(share) - np.outer(share, share))

    difference = (observed - expected)[:-1]        # one group is redundant
    reduced = variance[:-1, :-1]
    try:
        chi2 = float(difference @ np.linalg.pinv(reduced) @ difference)
    except Exception:
        return (float("nan"), float("nan"), 0)
    df = k - 1
    p = float(sps.chi2.sf(chi2, df)) if np.isfinite(chi2) else float("nan")
    del names
    return (chi2, p, df)


def logrank_pairs(curves: dict, correction: str = "holm") -> list[Comparison]:
    """Log-rank on every pair of groups, corrected for multiplicity."""
    names = list(curves)
    raw = []
    for a, b in itertools.combinations(names, 2):
        chi2, p, _ = logrank({a: curves[a], b: curves[b]})
        if not np.isfinite(p):
            continue
        n_a = len(_survival_input(*curves[a])[0])
        n_b = len(_survival_input(*curves[b])[0])
        raw.append(Comparison(a, b, chi2, p, p, "Log-rank", n_a, n_b))
    for comp, adjusted in zip(raw, adjust([c.p for c in raw], correction)):
        comp.p_adj = adjusted
    return raw


def describe_survival(curves: dict) -> list[dict]:
    """One row per group: numbers at risk, events, censored, median survival."""
    rows = []
    for name, (times, events) in curves.items():
        km = kaplan_meier(times, events)
        rows.append({"Groupe": name, "n": km["n"], "Événements": km["events"],
                     "Censurés": km["censored"],
                     "Survie médiane": km["median"],
                     "Survie finale": km["survival"][-1] if km["survival"]
                     else float("nan")})
    return rows


# --------------------------------------------------------------------------
# Contingency tables
# --------------------------------------------------------------------------
CONTINGENCY_LABELS = {
    "fisher": "Test exact de Fisher",
    "chi2": "Khi² de Pearson",
    "chi2_yates": "Khi² avec correction de Yates",
}


def _trimmed(table) -> np.ndarray:
    """Counts as floats, without the rows and columns that hold nothing.

    An empty row or column has no expected count and would make the
    chi-square divide by zero; it carries no information either.
    """
    table = np.asarray(table, dtype=float)
    table = np.where(np.isfinite(table), table, 0.0)
    return table[table.sum(axis=1) > 0][:, table.sum(axis=0) > 0]


def contingency(table, test: str = "auto") -> dict:
    """Test of independence between the rows and the columns of a table.

    "auto" follows Prism: Fisher's exact test on a 2 x 2 table, Pearson's
    chi-square on anything larger. Fisher is offered on 2 x 2 tables only;
    asked of a larger one, the chi-square is run and the result says so.
    Returns the test's name, its statistic (NaN for Fisher, which has none),
    degrees of freedom, p, the total and a warning to show, if any.
    """
    counts = _trimmed(table)
    result = {"test": "", "stat": float("nan"), "df": float("nan"),
              "p": float("nan"), "n": int(counts.sum()), "warning": ""}
    if counts.ndim != 2 or min(counts.shape) < 2:
        result["warning"] = tr(
            "Contingence : il faut au moins deux groupes et deux issues "
            "non vides.")
        return result
    if np.any(counts < 0) or np.any(counts != np.round(counts)):
        result["warning"] = tr(
            "Contingence : les effectifs doivent être des nombres entiers "
            "positifs.")
        return result
    two_by_two = counts.shape == (2, 2)
    if test == "auto":
        test = "fisher" if two_by_two else "chi2"
    if test == "fisher" and not two_by_two:
        result["warning"] = tr(
            "Le test exact de Fisher ne s'applique ici qu'à un tableau "
            "2 x 2 : khi² de Pearson utilisé.")
        test = "chi2"
    if test == "chi2_yates" and not two_by_two:
        test = "chi2"                 # Yates only exists for one ddl

    if test == "fisher":
        _odds, p = sps.fisher_exact(counts.astype(int))
        result.update(test=CONTINGENCY_LABELS["fisher"], p=float(p))
        return result

    stat, p, dof, expected = sps.chi2_contingency(
        counts, correction=(test == "chi2_yates"))
    result.update(test=CONTINGENCY_LABELS[test], stat=float(stat),
                  df=int(dof), p=float(p))
    # Cochran's rule: the chi-square is an approximation that fails on
    # small expected counts, which is exactly when Fisher is needed
    if (expected < 1).any() or (expected < 5).mean() > 0.2:
        result["warning"] = result["warning"] or tr(
            "Effectifs attendus faibles : le khi² n'est qu'approximatif ici"
            "{advice}.").format(advice=tr(" ; préférez le test exact de "
                                          "Fisher") if two_by_two else "")
    return result


def contingency_effects(table) -> list[dict]:
    """Effect sizes: odds ratio and relative risk on 2 x 2, Cramér's V always.

    On a 2 x 2 table, the first row is compared with the second for the
    outcome in the first column: an odds ratio of 2 means the odds of that
    outcome are twice as high in the first group. The intervals are Woolf's
    (log odds ratio) and Katz's (log relative risk), the textbook ones; a
    table with an empty cell gets 0.5 added to every cell (Haldane), without
    which neither ratio exists.
    """
    counts = _trimmed(table)
    rows = []
    if counts.ndim != 2 or min(counts.shape) < 2:
        return rows
    if counts.shape == (2, 2):
        a, b, c, d = counts.ravel()
        # the difference of proportions needs no correction: from raw counts
        difference = a / (a + b) - c / (c + d)
        note = ""
        if 0 in (a, b, c, d):
            a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
            note = "Haldane"
        z = sps.norm.ppf(0.975)
        odds = (a * d) / (b * c)
        se = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        rows.append({"Mesure": "Odds ratio", "Valeur": float(odds),
                     "IC95 bas": float(odds * np.exp(-z * se)),
                     "IC95 haut": float(odds * np.exp(z * se)),
                     "Correction": note})
        risk_1, risk_2 = a / (a + b), c / (c + d)
        ratio = risk_1 / risk_2
        se = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
        rows.append({"Mesure": "Risque relatif", "Valeur": float(ratio),
                     "IC95 bas": float(ratio * np.exp(-z * se)),
                     "IC95 haut": float(ratio * np.exp(z * se)),
                     "Correction": note})
        rows.append({"Mesure": "Différence de proportions",
                     "Valeur": float(difference),
                     "IC95 bas": float("nan"), "IC95 haut": float("nan"),
                     "Correction": ""})
    chi2 = sps.chi2_contingency(counts, correction=False)[0]
    v = np.sqrt(chi2 / (counts.sum() * (min(counts.shape) - 1)))
    rows.append({"Mesure": "V de Cramér", "Valeur": float(v),
                 "IC95 bas": float("nan"), "IC95 haut": float("nan"),
                 "Correction": ""})
    return rows


def contingency_pairs(table, labels: list[str], test: str = "auto",
                      correction: str = "holm", mode: str = "all_pairs",
                      control: str = "") -> list[Comparison]:
    """Every pair of groups (rows) tested on its own 2-row sub-table."""
    counts = np.asarray(table, dtype=float)
    if mode == "vs_control" and control in labels:
        pairs = [(control, other) for other in labels if other != control]
    else:
        pairs = list(itertools.combinations(labels, 2))
    raw = []
    for a, b in pairs:
        sub = counts[[labels.index(a), labels.index(b)]]
        result = contingency(sub, test)
        if not np.isfinite(result["p"]):
            continue
        raw.append(Comparison(a, b, result["stat"], result["p"], result["p"],
                              result["test"],
                              int(np.nansum(sub[0])), int(np.nansum(sub[1]))))
    for comp, adjusted in zip(raw, adjust([c.p for c in raw], correction)):
        comp.p_adj = adjusted
    return raw


def describe_contingency(table, labels: list[str],
                         outcomes: list[str]) -> list[dict]:
    """The table itself: counts and shares of each outcome, group by group."""
    counts = np.asarray(table, dtype=float)
    rows = []
    for label, line in zip(labels, counts):
        total = float(np.nansum(line))
        row = {"Groupe": label, "n": int(total)}
        for outcome, count in zip(outcomes, line):
            row[outcome] = int(count) if np.isfinite(count) else count
            row[f"{outcome} (%)"] = (100.0 * count / total if total
                                     else float("nan"))
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Outliers
# --------------------------------------------------------------------------
def grubbs(values, alpha: float = 0.05) -> list[dict]:
    """Points Grubbs' test flags, one at a time until none is left.

    The test assumes the rest of the sample is normal and looks for a single
    outlier, so it is applied again after each removal. Flagging is all it
    does: dropping a measurement is a decision for whoever took it.
    """
    arr = np.asarray(values, dtype=float)
    keep = np.arange(arr.size)[np.isfinite(arr)]
    flagged = []
    if not HAVE_SCIPY:
        return flagged
    # Repeating the test on what is left can run away: each removal shrinks
    # the spread and makes the next point look extreme in turn. A tenth of
    # the sample is as far as it goes.
    budget = max(1, int(0.1 * keep.size))
    while keep.size >= 3 and len(flagged) < budget:
        sample = arr[keep]
        sd = float(sample.std(ddof=1))
        if sd <= 0:
            break
        deviations = np.abs(sample - sample.mean())
        worst = int(np.argmax(deviations))
        n = sample.size
        g = float(deviations[worst] / sd)
        critical = float(sps.t.ppf(1 - alpha / (2 * n), n - 2))
        limit = ((n - 1) / np.sqrt(n)
                 * np.sqrt(critical ** 2 / (n - 2 + critical ** 2)))
        if g <= limit:
            break
        denominator = (n - 1) ** 2 - n * g ** 2
        if denominator <= 0:
            p = 0.0
        else:
            t_obs = np.sqrt(n * (n - 2) * g ** 2 / denominator)
            p = float(min(1.0, n * 2 * sps.t.sf(t_obs, n - 2)))
        flagged.append({"index": int(keep[worst]),
                        "value": float(sample[worst]),
                        "G": g, "seuil": float(limit), "p": p})
        keep = np.delete(keep, worst)
    return flagged


def outliers(groups: dict, alpha: float = 0.05) -> list[dict]:
    """Grubbs applied group by group, as a table for the Analyses panel."""
    rows = []
    for name, values in groups.items():
        for hit in grubbs(values, alpha):
            rows.append({"Groupe": name, "Valeur": hit["value"],
                         "Rang dans le groupe": hit["index"] + 1,
                         "G": hit["G"], "Seuil": hit["seuil"], "p": hit["p"]})
    return rows


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
    "dunnett": "Dunnett", "rm_anova": "ANOVA à mesures répétées",
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
