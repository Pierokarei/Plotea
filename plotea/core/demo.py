"""Synthetic datasets used by the Help > Exemples menu and the test suite."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..i18n import tr
from .dataset import Dataset


def viability(seed: int = 7) -> Dataset:
    """Long format: 4 treatments x 12 replicates, classic bar/box material."""
    rng = np.random.default_rng(seed)
    groups = {tr("Contrôle"): (100, 9), tr("Drogue A"): (82, 11),
              tr("Drogue B"): (61, 10), tr("Drogue A+B"): (38, 8)}
    rows = []
    for name, (mu, sd) in groups.items():
        for rep, val in enumerate(rng.normal(mu, sd, 12), start=1):
            rows.append({tr("Traitement"): name, tr("Réplicat"): rep,
                         tr("Viabilité"): round(float(val), 2),
                         tr("Lignée"): "HeLa" if rep % 2 else "U2OS"})
    return Dataset(tr("Viabilité cellulaire"), pd.DataFrame(rows))


def growth(seed: int = 3) -> Dataset:
    """Wide format time course with replicate columns: curves with error."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, 49, 4, dtype=float)
    out = {tr("Temps (h)"): t}
    for name, (k, top) in {"WT": (0.10, 1.8), "KO": (0.06, 1.2),
                           "KO + rescue": (0.09, 1.65)}.items():
        base = top / (1 + np.exp(-k * (t - 24)))
        out[name] = np.round(base + rng.normal(0, 0.04, t.size), 4)
        out[f"{name} SD"] = np.round(np.abs(rng.normal(0.06, 0.02, t.size)), 4)
    return Dataset(tr("Courbe de croissance"), pd.DataFrame(out))


def dose_response(seed: int = 11) -> Dataset:
    """Log-concentration dose response, for the 4PL fit."""
    rng = np.random.default_rng(seed)
    logc = np.repeat(np.linspace(-9, -4, 11), 3)
    rows = []
    for compound, (logec50, hill, top) in {
            tr("Inhibiteur 1"): (-7.2, 1.0, 100.0),
            tr("Inhibiteur 2"): (-6.1, 1.4, 96.0)}.items():
        resp = 5 + (top - 5) / (1 + 10 ** ((logc - logec50) * hill))
        resp = resp + rng.normal(0, 3.5, logc.size)
        for lc, r in zip(logc, resp):
            rows.append({"log[C] (M)": round(float(lc), 3),
                         tr("Réponse (%)"): round(float(r), 2),
                         tr("Composé"): compound})
    return Dataset(tr("Dose-réponse"), pd.DataFrame(rows))


def expression(seed: int = 21) -> Dataset:
    """Wide format, heavy-tailed: violin / histogram material."""
    rng = np.random.default_rng(seed)
    n = 220
    return Dataset(tr("Expression génique"), pd.DataFrame({
        tr("Sain"): np.round(rng.lognormal(1.8, 0.45, n), 3),
        tr("Tumeur"): np.round(rng.lognormal(2.4, 0.55, n), 3),
        tr("Métastase"): np.round(rng.lognormal(2.75, 0.62, n), 3),
    }))


def correlation(seed: int = 5) -> Dataset:
    """Scatter with a real linear relationship plus a categorical factor."""
    rng = np.random.default_rng(seed)
    rows = []
    for cohort, (slope, noise) in {tr("Cohorte A"): (1.9, 6.0),
                                   tr("Cohorte B"): (1.1, 5.0)}.items():
        x = rng.uniform(5, 60, 60)
        y = slope * x + 12 + rng.normal(0, noise, x.size)
        for xi, yi in zip(x, y):
            rows.append({tr("Biomarqueur (ng/mL)"): round(float(xi), 2),
                         tr("Score clinique"): round(float(yi), 2),
                         tr("Cohorte"): cohort})
    return Dataset(tr("Corrélation biomarqueur"), pd.DataFrame(rows))


def two_factor(seed: int = 15) -> Dataset:
    """Two-factor design -> grouped bars with error."""
    rng = np.random.default_rng(seed)
    rows = []
    for genotype, base in {"WT": 100.0, tr("Mutant"): 72.0}.items():
        for time, factor in {"0 h": 1.0, "6 h": 0.82, "24 h": 0.55}.items():
            for _ in range(8):
                rows.append({tr("Génotype"): genotype, tr("Temps"): time,
                             tr("Activité"): round(float(
                                 rng.normal(base * factor, 7.5)), 2)})
    return Dataset(tr("Plan à deux facteurs"), pd.DataFrame(rows))


def survival(seed: int = 21) -> Dataset:
    """A two-arm trial with censoring: the shape Kaplan-Meier is made for.

    A third of the subjects leave the study before the event, at a time that
    says nothing about their outcome - which is what censoring means.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for arm, median in {tr("Traitement"): 30.0, tr("Placebo"): 10.0}.items():
        for _ in range(40):
            event_time = float(rng.exponential(median / np.log(2)))
            leaves = float(rng.uniform(14, 40))     # end of follow-up
            observed = min(event_time, leaves)
            rows.append({tr("Bras"): arm,
                         tr("Temps (mois)"): round(min(observed, 36.0), 2),
                         tr("Événement"): int(event_time <= min(leaves, 36.0))})
    return Dataset(tr("Essai de survie"), pd.DataFrame(rows))


def contingency() -> Dataset:
    """Responders per arm, already counted - the way Prism enters them.

    Three arms, so the chi-square tests the whole table and each pair of
    arms gets its own Fisher test.
    """
    arms = {tr("Médicament A"): (28, 12), tr("Médicament B"): (21, 19),
            tr("Placebo"): (14, 26)}
    rows = [{tr("Traitement"): arm, tr("Répondeurs"): yes,
             tr("Non-répondeurs"): no} for arm, (yes, no) in arms.items()]
    return Dataset(tr("Réponse au traitement"), pd.DataFrame(rows))


EXAMPLES = {
    "Viabilité cellulaire (barres, stats)": viability,
    "Courbe de croissance (courbes + SD)": growth,
    "Dose-réponse (fit 4PL)": dose_response,
    "Expression génique (violin/histogramme)": expression,
    "Corrélation (nuage + régression)": correlation,
    "Plan à deux facteurs (barres groupées)": two_factor,
    "Essai de survie (Kaplan-Meier)": survival,
    "Réponse au traitement (contingence)": contingency,
}


def load_example(label: str) -> Dataset:
    return EXAMPLES[label]()


def all_examples() -> list[Dataset]:
    return [fn() for fn in EXAMPLES.values()]
