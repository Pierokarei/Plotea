"""Curve fitting: linear, polynomial and the usual non-linear biology models.

Each model exposes a callable, parameter names, an initial-guess heuristic and
a pretty equation. Fits return R2, parameter standard errors and an optional
95 % confidence band computed by the delta method.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .enums import FIT_MODEL

try:
    from scipy import stats as sps
    from scipy.optimize import curve_fit
    HAVE_SCIPY = True
except Exception:                                     # pragma: no cover
    HAVE_SCIPY = False


# --------------------------------------------------------------------------
# Model definitions
# --------------------------------------------------------------------------
def _lin(x, a, b):
    return a * x + b


def _poly2(x, a, b, c):
    return a * x ** 2 + b * x + c


def _poly3(x, a, b, c, d):
    return a * x ** 3 + b * x ** 2 + c * x + d


def _exp_growth(x, a, k, c):
    return a * np.exp(np.clip(k * x, -700, 700)) + c


def _exp_decay(x, a, k, plateau):
    return (a - plateau) * np.exp(-np.clip(k * x, -700, 700)) + plateau


def _log(x, a, b):
    return a * np.log(np.clip(x, 1e-12, None)) + b


def _power(x, a, b):
    return a * np.power(np.clip(x, 1e-12, None), b)


def _mm(x, vmax, km):
    return vmax * x / (km + x)


def _hill4(x, bottom, top, ec50, hill):
    """4-parameter logistic on a linear X (concentration)."""
    ec50 = np.clip(ec50, 1e-12, None)
    return bottom + (top - bottom) / (1.0 + (ec50 / np.clip(x, 1e-12, None))
                                      ** hill)


def _hill4_log(x, bottom, top, logec50, hill):
    """4PL on log10(concentration) X, the dose-response classic."""
    exponent = np.clip((logec50 - x) * hill, -300, 300)
    return bottom + (top - bottom) / (1.0 + 10 ** exponent)


def _gauss(x, amp, mu, sigma, offset):
    sigma = np.clip(np.abs(sigma), 1e-12, None)
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + offset


def _sigmoid(x, top, x0, k):
    return top / (1.0 + np.exp(-np.clip(k * (x - x0), -700, 700)))


@dataclass
class Model:
    key: str
    label: str
    func: object
    params: list[str]
    guess: object
    equation: str
    bounds: tuple = field(default=(-np.inf, np.inf))


def _g_lin(x, y):
    a = (y[-1] - y[0]) / (x[-1] - x[0]) if x[-1] != x[0] else 1.0
    return [a, float(np.mean(y) - a * np.mean(x))]


MODELS: dict[str, Model] = {
    "none": Model("none", "Aucun", None, [], None, ""),
    "linear": Model(
        "linear", "Linéaire (y = ax + b)", _lin, ["a", "b"], _g_lin,
        "y = {a:.4g}x + {b:.4g}"),
    "poly2": Model(
        "poly2", "Polynôme degré 2", _poly2, ["a", "b", "c"],
        lambda x, y: [1.0, 1.0, float(np.mean(y))],
        "y = {a:.4g}x2 + {b:.4g}x + {c:.4g}"),
    "poly3": Model(
        "poly3", "Polynôme degré 3", _poly3, ["a", "b", "c", "d"],
        lambda x, y: [1.0, 1.0, 1.0, float(np.mean(y))],
        "y = {a:.4g}x3 + {b:.4g}x2 + {c:.4g}x + {d:.4g}"),
    "exp_growth": Model(
        "exp_growth", "Croissance exponentielle", _exp_growth,
        ["a", "k", "c"],
        lambda x, y: [float(np.ptp(y) or 1.0), 0.1, float(np.min(y))],
        "y = {a:.4g}e^({k:.4g}x) + {c:.4g}"),
    "exp_decay": Model(
        "exp_decay", "Décroissance exponentielle (1 phase)", _exp_decay,
        ["Y0", "k", "Plateau"],
        lambda x, y: [float(np.max(y)), 0.5, float(np.min(y))],
        "y = ({Y0:.4g} - {Plateau:.4g})e^(-{k:.4g}x) + {Plateau:.4g}"),
    "log": Model(
        "log", "Logarithmique (y = a ln x + b)", _log, ["a", "b"],
        lambda x, y: [1.0, float(np.mean(y))],
        "y = {a:.4g} ln(x) + {b:.4g}"),
    "power": Model(
        "power", "Puissance (y = a x^b)", _power, ["a", "b"],
        lambda x, y: [float(np.mean(np.abs(y)) or 1.0), 1.0],
        "y = {a:.4g} x^{b:.4g}"),
    "michaelis": Model(
        "michaelis", "Michaelis-Menten", _mm, ["Vmax", "Km"],
        lambda x, y: [float(np.max(y)), float(np.median(x) or 1.0)],
        "y = {Vmax:.4g}x / ({Km:.4g} + x)",
        bounds=(0, np.inf)),
    "hill4": Model(
        "hill4", "Dose-réponse 4PL (X linéaire)", _hill4,
        ["Bas", "Haut", "EC50", "Hill"],
        lambda x, y: [float(np.min(y)), float(np.max(y)),
                      float(np.median(x[x > 0]) if np.any(x > 0) else 1.0), 1.0],
        "y = {Bas:.4g} + ({Haut:.4g} - {Bas:.4g}) / (1 + (EC50/x)^{Hill:.3g}),"
        " EC50 = {EC50:.4g}"),
    "hill4_log": Model(
        "hill4_log", "Dose-réponse 4PL (X = log concentration)",
        _hill4_log, ["Bas", "Haut", "logEC50", "Hill"],
        lambda x, y: [float(np.min(y)), float(np.max(y)),
                      float(np.median(x)), 1.0],
        "y = {Bas:.4g} + ({Haut:.4g} - {Bas:.4g}) /"
        " (1 + 10^(({logEC50:.4g} - x) x {Hill:.3g}))"),
    "gaussian": Model(
        "gaussian", "Gaussienne", _gauss, ["Amplitude", "Mu", "Sigma",
                                             "Offset"],
        lambda x, y: [float(np.ptp(y) or 1.0), float(x[np.argmax(y)]),
                      float(np.std(x) or 1.0), float(np.min(y))],
        "y = {Amplitude:.4g} exp(-0.5((x-{Mu:.4g})/{Sigma:.4g})^2)"
        " + {Offset:.4g}"),
    "sigmoid": Model(
        "sigmoid", "Sigmoïde logistique", _sigmoid, ["Top", "x0", "k"],
        lambda x, y: [float(np.max(y)), float(np.median(x)), 1.0],
        "y = {Top:.4g} / (1 + e^(-{k:.4g}(x - {x0:.4g})))"),
}

MODEL_NAMES = list(MODELS)
MODEL_LABELS = {key: model.label for key, model in MODELS.items()}


@dataclass
class FitResult:
    model: str
    params: dict
    stderr: dict
    r2: float
    r2_adj: float
    rmse: float
    n: int
    equation: str
    x_fit: np.ndarray
    y_fit: np.ndarray
    ci_low: np.ndarray | None = None
    ci_high: np.ndarray | None = None
    extra: dict = field(default_factory=dict)
    ok: bool = True
    message: str = ""

    def summary_lines(self) -> list[str]:
        lines = [self.equation] if self.equation else []
        lines.append(f"R2 = {self.r2:.4f}   n = {self.n}")
        for k in self.params:
            se = self.stderr.get(k, float("nan"))
            if np.isfinite(se):
                lines.append(f"{k} = {self.params[k]:.4g} +/- {se:.3g}")
            else:
                lines.append(f"{k} = {self.params[k]:.4g}")
        return lines


def _jacobian(func, x, popt, eps=1e-6):
    base = func(x, *popt)
    J = np.zeros((x.size, len(popt)))
    for i, p in enumerate(popt):
        step = eps * max(abs(p), 1.0)
        up = list(popt)
        up[i] = p + step
        J[:, i] = (func(x, *up) - base) / step
    return J


def fit(x, y, model_name: str, n_points: int = 200,
        extrapolate: bool = False) -> FitResult | None:
    """Fit `model_name` to (x, y). Returns None when the model is 'Aucun'."""
    model = MODELS.get(FIT_MODEL.normalise(model_name))
    if model is None or model.func is None:
        return None
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    order = np.argsort(x)
    x, y = x[order], y[order]
    n_par = len(model.params)
    if x.size <= n_par:
        return FitResult(model_name, {}, {}, float("nan"), float("nan"),
                         float("nan"), int(x.size), "", np.array([]),
                         np.array([]), ok=False,
                         message="Pas assez de points pour ce modèle.")
    if not HAVE_SCIPY:
        return FitResult(model_name, {}, {}, float("nan"), float("nan"),
                         float("nan"), int(x.size), "", np.array([]),
                         np.array([]), ok=False, message="scipy requis.")

    try:
        p0 = model.guess(x, y)
        popt, pcov = curve_fit(model.func, x, y, p0=p0, maxfev=20000,
                               bounds=model.bounds)
    except Exception as exc:
        return FitResult(model_name, {}, {}, float("nan"), float("nan"),
                         float("nan"), int(x.size), "", np.array([]),
                         np.array([]), ok=False,
                         message=f"Convergence impossible ({exc}).")

    resid = y - model.func(x, *popt)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    dof = max(x.size - n_par, 1)
    r2_adj = 1.0 - (1.0 - r2) * (x.size - 1) / dof if np.isfinite(r2) else r2
    rmse = float(np.sqrt(ss_res / dof))

    perr = np.sqrt(np.abs(np.diag(pcov))) if pcov is not None else \
        np.full(n_par, np.nan)
    params = {k: float(v) for k, v in zip(model.params, popt)}
    stderr = {k: float(v) for k, v in zip(model.params, perr)}

    span = x.max() - x.min()
    pad = 0.08 * span if extrapolate else 0.0
    xf = np.linspace(x.min() - pad, x.max() + pad, n_points)
    yf = model.func(xf, *popt)

    ci_low = ci_high = None
    try:
        J = _jacobian(model.func, xf, popt)
        var = np.einsum("ij,jk,ik->i", J, pcov, J)
        se = np.sqrt(np.clip(var, 0, None))
        tval = float(sps.t.ppf(0.975, dof))
        ci_low, ci_high = yf - tval * se, yf + tval * se
    except Exception:
        pass

    try:
        equation = model.equation.format(**params)
    except Exception:
        equation = model.equation

    extra = {}
    if model.key == "hill4_log" and "logEC50" in params:
        extra["EC50"] = float(10 ** params["logEC50"])
    if model.key == "exp_decay" and params.get("k"):
        extra["Demi-vie"] = float(np.log(2) / params["k"])
    if model.key == "linear" and HAVE_SCIPY:
        lr = sps.linregress(x, y)
        extra["p (pente)"] = float(lr.pvalue)
        extra["r Pearson"] = float(lr.rvalue)

    return FitResult(model_name, params, stderr, r2, r2_adj, rmse,
                     int(x.size), equation, xf, yf, ci_low, ci_high, extra)


def correlation(x, y, method: str = "pearson") -> dict:
    """Pearson/Spearman correlation, shown next to scatter plots."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if not HAVE_SCIPY or x.size < 3:
        return {}
    if method == "spearman":
        r, p = sps.spearmanr(x, y)
        return {"rho": float(r), "p": float(p), "n": int(x.size)}
    r, p = sps.pearsonr(x, y)
    return {"r": float(r), "p": float(p), "n": int(x.size),
            "r2": float(r) ** 2}
