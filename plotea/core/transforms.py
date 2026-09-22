"""Data transforms: the operations people otherwise go back to Excel for.

Every transform returns a brand new DataFrame, so the imported table is never
altered. The caller stores the result as a separate table, the way a Prism
results sheet works.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .enums import TRANSFORM

#: What a transform needs the caller to supply, beyond the value columns.
NEEDS_GROUP = "group"
NEEDS_CONTROL = "control"
NEEDS_REFERENCE = "reference"


@dataclass
class Params:
    columns: list = field(default_factory=list)
    group: str = ""
    control: str = ""
    reference: str = ""


def _numeric(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def _as_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


# --------------------------------------------------------------------------
# Implementations
# --------------------------------------------------------------------------
def percent_of_control(df: pd.DataFrame, p: Params) -> tuple[pd.DataFrame, str]:
    """Express every value as a percentage of the control mean."""
    out = df.copy()
    cols = _numeric(df, p.columns)
    if not cols:
        return out, "Aucune colonne numérique sélectionnée."

    if p.group and p.group in df.columns:
        if not p.control:
            return out, "Choisissez le groupe contrôle."
        mask = df[p.group].astype(str) == str(p.control)
        if not mask.any():
            return out, f"Groupe contrôle '{p.control}' introuvable."
        for col in cols:
            ref = _as_float(df.loc[mask, col]).mean()
            if not np.isfinite(ref) or ref == 0:
                return out, f"Moyenne du contrôle nulle pour '{col}'."
            out[col] = _as_float(df[col]) / ref * 100.0
        return out, ""

    if not p.reference or p.reference not in df.columns:
        return out, "Choisissez la colonne servant de contrôle."
    ref = _as_float(df[p.reference]).mean()
    if not np.isfinite(ref) or ref == 0:
        return out, "Moyenne de la colonne contrôle nulle."
    for col in cols:
        out[col] = _as_float(df[col]) / ref * 100.0
    return out, ""


def normalize_range(df: pd.DataFrame, p: Params) -> tuple[pd.DataFrame, str]:
    """Rescale each column so its minimum is 0 and its maximum 100."""
    out = df.copy()
    for col in _numeric(df, p.columns):
        values = _as_float(df[col])
        low, high = values.min(), values.max()
        if not np.isfinite(low) or high == low:
            continue
        out[col] = (values - low) / (high - low) * 100.0
    return out, ""


def _log(base: float | None):
    def run(df: pd.DataFrame, p: Params) -> tuple[pd.DataFrame, str]:
        out = df.copy()
        dropped = 0
        for col in _numeric(df, p.columns):
            values = _as_float(df[col])
            bad = values <= 0
            dropped += int(bad.sum())
            values = values.mask(bad)
            out[col] = (np.log(values) if base is None
                        else np.log(values) / np.log(base))
        message = (f"{dropped} valeur(s) <= 0 exclue(s) : le logarithme n'y "
                   "est pas défini." if dropped else "")
        return out, message
    return run


def zscore(df: pd.DataFrame, p: Params) -> tuple[pd.DataFrame, str]:
    """Centre and reduce, per group when one is given."""
    out = df.copy()
    cols = _numeric(df, p.columns)
    if p.group and p.group in df.columns:
        for col in cols:
            values = _as_float(df[col])
            out[col] = values.groupby(df[p.group]).transform(
                lambda s: (s - s.mean()) / (s.std(ddof=1) or np.nan))
        return out, ""
    for col in cols:
        values = _as_float(df[col])
        sd = values.std(ddof=1)
        out[col] = (values - values.mean()) / (sd or np.nan)
    return out, ""


def subtract_baseline(df: pd.DataFrame, p: Params) -> tuple[pd.DataFrame, str]:
    """Subtract the first measured value, per group when one is given."""
    out = df.copy()
    cols = _numeric(df, p.columns)
    if p.group and p.group in df.columns:
        for col in cols:
            values = _as_float(df[col])
            out[col] = values.groupby(df[p.group]).transform(
                lambda s: s - (s.dropna().iloc[0] if s.notna().any() else 0.0))
        return out, ""
    for col in cols:
        values = _as_float(df[col])
        base = values.dropna()
        out[col] = values - (base.iloc[0] if not base.empty else 0.0)
    return out, ""


def ratio_to_column(df: pd.DataFrame, p: Params) -> tuple[pd.DataFrame, str]:
    """Divide each selected column by a reference column, row by row."""
    out = df.copy()
    if not p.reference or p.reference not in df.columns:
        return out, "Choisissez la colonne de référence."
    ref = _as_float(df[p.reference]).replace(0.0, np.nan)
    for col in _numeric(df, p.columns):
        if col == p.reference:
            continue
        out[col] = _as_float(df[col]) / ref
    return out, ""


def aggregate_replicates(df: pd.DataFrame,
                         p: Params) -> tuple[pd.DataFrame, str]:
    """Collapse replicates into mean, SD, SEM and n per group."""
    cols = _numeric(df, p.columns)
    if not (p.group and p.group in df.columns):
        return df.copy(), "Choisissez la colonne de regroupement."
    if not cols:
        return df.copy(), "Aucune colonne numérique sélectionnée."
    frames = []
    for col in cols:
        grouped = _as_float(df[col]).groupby(df[p.group], sort=False)
        stats = grouped.agg(["count", "mean", "std"])
        stats.columns = [f"{col} n", f"{col} moyenne", f"{col} SD"]
        stats[f"{col} SD"] = stats[f"{col} SD"].fillna(0.0)
        stats[f"{col} SEM"] = stats[f"{col} SD"] / np.sqrt(
            stats[f"{col} n"].clip(lower=1))
        frames.append(stats)
    out = pd.concat(frames, axis=1).reset_index()
    return out, ""


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
@dataclass
class Transform:
    key: str
    label: str
    description: str
    run: object
    needs: set = field(default_factory=set)
    suffix: str = ""


TRANSFORMS: dict[str, Transform] = {
    "percent": Transform(
        "percent", "Pourcentage du contrôle",
        "Divise chaque valeur par la moyenne du contrôle, en pourcentage.",
        percent_of_control, {NEEDS_GROUP, NEEDS_CONTROL, NEEDS_REFERENCE},
        "% ctrl"),
    "normalize": Transform(
        "normalize", "Normaliser de 0 a 100",
        "Ramène le minimum de chaque colonne a 0 et le maximum a 100.",
        normalize_range, set(), "norm"),
    "log10": Transform(
        "log10", "Logarithme décimal", "log10 de chaque valeur (x > 0).",
        _log(10.0), set(), "log10"),
    "ln": Transform(
        "ln", "Logarithme naturel", "ln de chaque valeur (x > 0).",
        _log(None), set(), "ln"),
    "log2": Transform(
        "log2", "Logarithme base 2",
        "log2, utile pour les rapports d'expression.", _log(2.0), set(),
        "log2"),
    "zscore": Transform(
        "zscore", "Score z", "Centre et réduit, par groupe si demandé.",
        zscore, {NEEDS_GROUP}, "z"),
    "baseline": Transform(
        "baseline", "Soustraire la ligne de base",
        "Retire la première valeur mesuree, par groupe si demandé.",
        subtract_baseline, {NEEDS_GROUP}, "base"),
    "ratio": Transform(
        "ratio", "Rapport a une colonne",
        "Divise chaque colonne choisie par une colonne de référence.",
        ratio_to_column, {NEEDS_REFERENCE}, "ratio"),
    "aggregate": Transform(
        "aggregate", "Moyenne des réplicats",
        "Une ligne par groupe avec moyenne, SD, SEM et n.",
        aggregate_replicates, {NEEDS_GROUP}, "moyennes"),
}

TRANSFORM_LABELS = [t.label for t in TRANSFORMS.values()]


def by_label(name: str) -> Transform | None:
    """Look a transform up by key, by label or by legacy wording."""
    if name in TRANSFORMS:
        return TRANSFORMS[name]
    return TRANSFORMS.get(TRANSFORM.normalise(name))


def apply(name: str, df: pd.DataFrame,
          params: Params) -> tuple[pd.DataFrame, str]:
    transform = by_label(name)
    if transform is None:
        return df.copy(), f"Transformation inconnue : {name}"
    try:
        return transform.run(df, params)
    except Exception as exc:
        return df.copy(), f"Échec de la transformation : {exc}"
