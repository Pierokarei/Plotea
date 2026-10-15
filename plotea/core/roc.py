"""ROC curves: how well a measurement tells the diseased from the healthy.

The area under the ROC curve is the probability that a diseased subject
scores higher than a healthy one, ties counting half - the Mann-Whitney
statistic divided by n_pos x n_neg. Its standard error is DeLong's
(DeLong ER, DeLong DM, Clarke-Pearson DL. Biometrics 1988;44:837-845),
computed from midranks (Sun X, Xu W. IEEE Signal Process Lett
2014;21:1389-1393), the way pROC does; the same placement values give the
test comparing two markers measured on the same subjects.

Which way the marker points is found from the medians, as pROC does with
direction = "auto", and said: a marker that is lower in the diseased is
read with its values reversed, and its cut-off becomes "< c".

The optimal cut-off maximises Youden's index (sensitivity + specificity -
1); cut-offs lie midway between consecutive observed values. Sensitivity
and specificity come with Wilson score intervals.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats as sps

Z95 = float(sps.norm.ppf(0.975))


@dataclass
class Roc:
    auc: float = float("nan")
    se: float = float("nan")
    low: float = float("nan")
    high: float = float("nan")
    p: float = float("nan")             # against AUC = 0.5
    n_pos: int = 0
    n_neg: int = 0
    lower_is_positive: bool = False
    cutoff: float = float("nan")
    sensitivity: float = float("nan")
    specificity: float = float("nan")
    sens_ci: tuple = (float("nan"), float("nan"))
    spec_ci: tuple = (float("nan"), float("nan"))
    fpr: np.ndarray = field(default_factory=lambda: np.array([]))
    tpr: np.ndarray = field(default_factory=lambda: np.array([]))
    # DeLong placement values, kept for comparing two markers
    v10: np.ndarray = field(default_factory=lambda: np.array([]))
    v01: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def ok(self) -> bool:
        return self.n_pos >= 2 and self.n_neg >= 2


def _clean(values) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return values[np.isfinite(values)]


def placements(neg, pos):
    """DeLong's placement values from midranks: (auc, V10, V01)."""
    m, n = pos.size, neg.size
    ranks = sps.rankdata(np.concatenate([pos, neg]))
    v10 = (ranks[:m] - sps.rankdata(pos)) / n
    v01 = 1.0 - (ranks[m:] - sps.rankdata(neg)) / m
    return float(v10.mean()), v10, v01


def curve(neg, pos):
    """(FPR, TPR) at every cut-off, from (0, 0) to (1, 1)."""
    cuts = np.unique(np.concatenate([neg, pos]))[::-1]
    fpr = 1.0 - np.searchsorted(np.sort(neg), cuts, "left") / neg.size
    tpr = 1.0 - np.searchsorted(np.sort(pos), cuts, "left") / pos.size
    return np.concatenate([[0.0], fpr]), np.concatenate([[0.0], tpr])


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson score 95 % interval of a proportion k / n."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    z2 = Z95 ** 2
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z95 * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return float(max(centre - half, 0.0)), float(min(centre + half, 1.0))


def youden(neg, pos):
    """Cut-off maximising sensitivity + specificity - 1: (cut, sens, spec).

    Positive means above the cut-off. Ties on the index go to the higher
    sensitivity - in screening, the miss is the costlier error.
    """
    values = np.unique(np.concatenate([neg, pos]))
    cuts = (values[:-1] + values[1:]) / 2 if values.size > 1 else values
    sens = 1.0 - np.searchsorted(np.sort(pos), cuts, "right") / pos.size
    spec = np.searchsorted(np.sort(neg), cuts, "right") / neg.size
    index = np.round(sens + spec - 1, 12)
    best = np.flatnonzero(index == index.max())
    pick = best[np.argmax(sens[best])]
    return float(cuts[pick]), float(sens[pick]), float(spec[pick])


def analyse(neg, pos, direction: str = "auto") -> Roc:
    """Everything the ROC tab shows for one marker."""
    neg, pos = _clean(neg), _clean(pos)
    found = Roc(n_pos=int(pos.size), n_neg=int(neg.size))
    if not found.ok:
        return found
    lower = (np.median(pos) < np.median(neg) if direction == "auto"
             else direction == "lower")
    found.lower_is_positive = bool(lower)
    if lower:
        neg, pos = -neg, -pos
    found.auc, found.v10, found.v01 = placements(neg, pos)
    var = (found.v10.var(ddof=1) / pos.size
           + found.v01.var(ddof=1) / neg.size)
    found.se = float(np.sqrt(var))
    found.low = max(found.auc - Z95 * found.se, 0.0)
    found.high = min(found.auc + Z95 * found.se, 1.0)
    if found.se > 0:
        z = (found.auc - 0.5) / found.se
        found.p = float(2 * sps.norm.sf(abs(z)))
    elif found.auc != 0.5:
        found.p = 0.0
    found.fpr, found.tpr = curve(neg, pos)
    cut, sens, spec = youden(neg, pos)
    found.cutoff = -cut if lower else cut
    found.sensitivity, found.specificity = sens, spec
    found.sens_ci = wilson(round(sens * pos.size), pos.size)
    found.spec_ci = wilson(round(spec * neg.size), neg.size)
    return found


def compare(a: Roc, b: Roc) -> tuple[float, float]:
    """DeLong's test for two ROC curves on the same subjects: (z, p).

    `a` and `b` must come from the same subjects in the same order - the
    placement values are paired subject by subject.
    """
    if not (a.ok and b.ok) or a.v10.size != b.v10.size \
            or a.v01.size != b.v01.size:
        return float("nan"), float("nan")
    m, n = a.v10.size, a.v01.size
    s10 = np.cov(np.vstack([a.v10, b.v10]))
    s01 = np.cov(np.vstack([a.v01, b.v01]))
    var = ((s10[0, 0] + s10[1, 1] - 2 * s10[0, 1]) / m
           + (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / n)
    if var <= 0:
        return float("nan"), float("nan")
    z = (a.auc - b.auc) / np.sqrt(var)
    return float(z), float(2 * sps.norm.sf(abs(z)))
