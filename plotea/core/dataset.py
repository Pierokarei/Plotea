"""Data import and the in-memory table model used across the app."""
from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CSV_EXT = {".csv", ".txt", ".tsv", ".tab", ".dat"}
EXCEL_EXT = {".xlsx", ".xlsm", ".xls"}


def sniff_separator(path: str, encoding: str = "utf-8") -> str:
    """Guess the field separator of a delimited text file."""
    try:
        with open(path, "r", encoding=encoding, errors="replace") as fh:
            sample = fh.read(8192)
    except OSError:
        return ","
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {sep: sample.count(sep) for sep in (",", ";", "\t", "|")}
        best = max(counts, key=counts.get)
        return best if counts[best] else ","


@dataclass
class Dataset:
    """A named table plus the provenance needed to reload it."""

    name: str
    df: pd.DataFrame
    source: str = ""
    sheet: str = ""
    notes: str = ""
    meta: dict = field(default_factory=dict)

    # -- column helpers ----------------------------------------------------
    @property
    def columns(self) -> list[str]:
        return [str(c) for c in self.df.columns]

    def numeric_columns(self) -> list[str]:
        return [str(c) for c in self.df.columns
                if pd.api.types.is_numeric_dtype(self.df[c])]

    def categorical_columns(self) -> list[str]:
        return [str(c) for c in self.df.columns
                if not pd.api.types.is_numeric_dtype(self.df[c])]

    def series(self, column: str) -> pd.Series:
        return self.df[column]

    def values(self, column: str) -> np.ndarray:
        """Numeric values of a column, NaNs dropped."""
        s = pd.to_numeric(self.df[column], errors="coerce")
        return s.dropna().to_numpy(dtype=float)

    def summary(self) -> pd.DataFrame:
        """Per-column descriptive statistics, used by the Stats panel."""
        rows = []
        for col in self.df.columns:
            s = pd.to_numeric(self.df[col], errors="coerce").dropna()
            if s.empty:
                rows.append({
                    "Colonne": str(col), "n": int(self.df[col].notna().sum()),
                    "Moyenne": np.nan, "SD": np.nan, "SEM": np.nan,
                    "Médiane": np.nan, "Min": np.nan, "Max": np.nan,
                    "IC95 bas": np.nan, "IC95 haut": np.nan,
                })
                continue
            n = int(s.size)
            mean = float(s.mean())
            sd = float(s.std(ddof=1)) if n > 1 else 0.0
            sem = sd / np.sqrt(n) if n > 1 else 0.0
            ci = 1.96 * sem
            rows.append({
                "Colonne": str(col), "n": n, "Moyenne": mean, "SD": sd,
                "SEM": sem, "Médiane": float(s.median()),
                "Min": float(s.min()), "Max": float(s.max()),
                "IC95 bas": mean - ci, "IC95 haut": mean + ci,
            })
        return pd.DataFrame(rows)

    def copy(self, new_name: str | None = None) -> "Dataset":
        return Dataset(new_name or f"{self.name} (copie)", self.df.copy(),
                       self.source, self.sheet, self.notes, dict(self.meta))


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names, drop fully empty rows/columns, coerce numbers."""
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    cols, seen = [], {}
    for i, c in enumerate(df.columns):
        name = str(c).strip()
        if not name or name.lower().startswith("unnamed"):
            name = f"Col{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}.{seen[name]}"
        else:
            seen[name] = 0
        cols.append(name)
    df.columns = cols
    for c in df.columns:
        # pandas >= 3 gives text columns a StringDtype, so test the opposite
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        raw = df[c].astype("string").str.strip()
        non_null = int(raw.notna().sum())
        if not non_null:
            continue
        # only adopt the numeric view when it loses (almost) nothing
        direct = pd.to_numeric(raw, errors="coerce")
        if direct.notna().sum() >= 0.95 * non_null:
            df[c] = direct
            continue
        # comma decimals ("12,5"), but only when no dot could mean thousands
        if raw.str.contains(".", regex=False).any():
            continue
        swapped = pd.to_numeric(raw.str.replace(",", ".", regex=False),
                                errors="coerce")
        if swapped.notna().sum() >= 0.95 * non_null:
            df[c] = swapped
    return df.reset_index(drop=True)


def load_file(path: str, sheet: str | int | None = None,
              separator: str | None = None, decimal: str = ".",
              header_row: int = 0, encoding: str = "utf-8") -> list[Dataset]:
    """Load a CSV/TSV/Excel file into one Dataset per sheet."""
    ext = os.path.splitext(path)[1].lower()
    base = os.path.splitext(os.path.basename(path))[0]

    if ext in EXCEL_EXT:
        book = pd.read_excel(path, sheet_name=sheet, header=header_row)
        if isinstance(book, dict):
            return [Dataset(f"{base}:{k}", _clean(v), path, str(k))
                    for k, v in book.items() if not v.dropna(how="all").empty]
        return [Dataset(base, _clean(book), path, str(sheet or ""))]

    sep = separator or sniff_separator(path, encoding)
    df = pd.read_csv(path, sep=sep, decimal=decimal, header=header_row,
                     encoding=encoding, engine="python", skip_blank_lines=True)
    return [Dataset(base, _clean(df), path)]


def list_sheets(path: str) -> list[str]:
    if os.path.splitext(path)[1].lower() in EXCEL_EXT:
        return pd.ExcelFile(path).sheet_names
    return []


def from_clipboard_text(text: str, name: str = "Collage") -> Dataset:
    """Build a Dataset from tab/semicolon separated text (Excel paste)."""
    sep = "\t" if "\t" in text.splitlines()[0] else sniff_text(text)
    df = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
    return Dataset(name, _clean(df))


def sniff_text(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def empty_dataset(name: str = "Table 1", rows: int = 12,
                  cols: int = 4) -> Dataset:
    """A blank spreadsheet the user can type into."""
    data = {f"Col{i + 1}": [np.nan] * rows for i in range(cols)}
    return Dataset(name, pd.DataFrame(data))


# --------------------------------------------------------------------------
# Reshaping helpers
# --------------------------------------------------------------------------
def to_long(df: pd.DataFrame, value_cols: list[str], id_cols: list[str] | None =
            None, var_name: str = "Groupe",
            value_name: str = "Valeur") -> pd.DataFrame:
    """Wide -> long (tidy) conversion."""
    return df.melt(id_vars=id_cols or [], value_vars=value_cols,
                   var_name=var_name, value_name=value_name).dropna(
                       subset=[value_name])


def to_wide(df: pd.DataFrame, index: str, columns: str,
            values: str) -> pd.DataFrame:
    out = df.pivot_table(index=index, columns=columns, values=values,
                         aggfunc="mean")
    out.columns = [str(c) for c in out.columns]
    return out.reset_index()


def aggregate(df: pd.DataFrame, group: str, value: str,
              error: str = "SEM") -> pd.DataFrame:
    """Mean and dispersion per group, ready to feed a bar chart."""
    g = df.groupby(group, sort=False)[value]
    out = g.agg(["count", "mean", "std", "median"]).reset_index()
    out = out.rename(columns={"count": "n", "mean": "Moyenne",
                              "std": "SD", "median": "Médiane"})
    out["SD"] = out["SD"].fillna(0.0)
    out["SEM"] = out["SD"] / np.sqrt(out["n"].clip(lower=1))
    out["IC95"] = 1.96 * out["SEM"]
    out["Erreur"] = out[error if error in out.columns else "SEM"]
    return out
