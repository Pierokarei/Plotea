"""GraphPad Prism .pzfx files: their data tables, ready to plot.

A .pzfx is XML. Each data table is a <Table> (<HugeTable> for big ones)
whose TableType says how its columns are meant: an XY table holds an X
column and Y series with replicates, a Column table one column per group, a
Grouped table a row factor crossed with a column factor, a Survival table one
event column per group. Each kind is reshaped into the layout Plotea plots
from, with the plot Prism would have drawn when Plotea can draw it too.

Graphs, analyses and layouts are stored after the tables as a compressed
binary that only Prism reads: they are not imported, and the import says so.
Values excluded in Prism (shown in blue italics there) are left out, as
Prism's own analyses leave them out, and counted so the user knows.
"""
from __future__ import annotations

import os
import string
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..i18n import tr
from .dataset import Dataset

#: What the subcolumns of a Y column hold when Prism stores a summary
#: instead of replicates. The first is always the mean.
SUMMARY = {
    "SDN": ("", "SD", "N"),
    "SEN": ("", "SEM", "N"),
    "CVN": ("", "CV", "N"),
    "SD": ("", "SD"),
    "SE": ("", "SEM"),
    "CV": ("", "CV"),
    "low-high": ("", "erreur haute", "erreur basse"),
    "upper-lower-limits": ("", "limite haute", "limite basse"),
}

#: Summaries whose second subcolumn is a symmetric error Plotea can draw.
SYMMETRIC_ERROR = {"SDN", "SEN", "SD", "SE"}

#: Prism table types Plotea has no plot for yet, as the user calls them.
UNPLOTTED = {
    "PartsOfWhole": "parties d'un tout",
    "MultipleVariables": "variables multiples",
    "Nested": "imbriqué",
}


class PzfxError(ValueError):
    """The file cannot be read as a Prism file; the message says why."""


@dataclass
class PrismTable:
    """One Prism data table, reshaped, with the plot that suits it."""

    dataset: Dataset
    kind: str                                   # Prism's TableType
    plot: dict = field(default_factory=dict)    # PlotSpec fields, or {}


@dataclass
class PrismFile:
    tables: list[PrismTable]
    notes: list[str]              # what the user should know about the import


# --------------------------------------------------------------------------
# XML
# --------------------------------------------------------------------------
@dataclass
class _Column:
    tag: str
    title: str
    cells: list[list[tuple[str, bool]]]         # subcolumns of (text, excluded)


def _text(element) -> str:
    """All the text of an element: Prism wraps titles in formatting tags."""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _strip_namespaces(root):
    for element in root.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]


def _parse(path: str):
    if os.path.splitext(path)[1].lower() == ".prism":
        raise PzfxError(tr(
            "Les fichiers .prism de Prism 10 ne sont pas lisibles en dehors "
            "de Prism. Dans Prism, enregistrez le projet au format .pzfx, "
            "puis importez ce fichier."))
    with open(path, "rb") as handle:
        head = handle.read(4096)
    # Prism never writes a DTD; refusing one keeps entity tricks out
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise PzfxError(tr("Ce fichier n'est pas un fichier Prism .pzfx."))
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise PzfxError(tr(
            "Ce fichier n'est pas un fichier Prism .pzfx lisible ({error})."
        ).format(error=exc)) from exc
    _strip_namespaces(root)
    if root.tag != "GraphPadPrismFile":
        raise PzfxError(tr("Ce fichier n'est pas un fichier Prism .pzfx."))
    return root


def _columns(table) -> list[_Column]:
    columns = []
    for child in table:
        if child.tag not in ("XColumn", "XAdvancedColumn", "YColumn",
                             "RowTitlesColumn"):
            continue
        cells = []
        for sub in child.findall("Subcolumn"):
            cells.append([(_text(d), d.get("Excluded") == "1")
                          for d in sub.findall("d")])
        columns.append(_Column(child.tag, _text(child.find("Title")), cells))
    return columns


# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------
class _Counter:
    """Values left out of a table, reported once per table."""

    def __init__(self):
        self.excluded = 0
        self.unreadable = 0


def _number(text: str) -> float | None:
    if not text:
        return np.nan
    try:
        return float(text)
    except ValueError:
        pass
    # a comma decimal ("3,5"), as Prism writes it on a French system
    if "," in text and "." not in text:
        try:
            return float(text.replace(",", "."))
        except ValueError:
            pass
    return None


def _numbers(cells, rows: int, counter: _Counter) -> np.ndarray:
    out = np.full(rows, np.nan)
    for i, (text, excluded) in enumerate(cells[:rows]):
        value = _number(text)
        if value is None:
            counter.unreadable += 1
        elif excluded and np.isfinite(value):
            counter.excluded += 1
        else:
            out[i] = value
    return out


def _labels(column: _Column | None, rows: int) -> list[str]:
    cells = column.cells[0] if column and column.cells else []
    labels = [text for text, _excluded in cells[:rows]]
    return labels + [""] * (rows - len(labels))


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for name in names:
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        out.append(name)
    return out


# --------------------------------------------------------------------------
# One table
# --------------------------------------------------------------------------
class _Table:
    """The columns of one Prism table, named the way Prism shows them."""

    def __init__(self, element, number: int):
        self.kind = element.get("TableType", "")
        self.x_format = element.get("XFormat", "")
        self.y_format = element.get("YFormat", "replicates") or "replicates"
        self.title = _text(element.find("Title")) or \
            tr("Tableau {number}").format(number=number)
        columns = _columns(element)
        self.rows = max((len(sub) for c in columns for sub in c.cells),
                        default=0)
        self.row_titles = next(
            (c for c in columns if c.tag == "RowTitlesColumn"), None)
        self.x = next((c for c in columns if c.tag == "XColumn"), None)
        self.x_text = next(
            (c for c in columns if c.tag == "XAdvancedColumn"), None)
        self.ys = [c for c in columns if c.tag == "YColumn"]
        # an untitled Y column is shown by its letter in Prism: A, B, C...
        letters = string.ascii_uppercase
        titles = [c.title or tr("Colonne {letter}").format(
                      letter=letters[i] if i < 26 else str(i + 1))
                  for i, c in enumerate(self.ys)]
        for column, title in zip(self.ys, _unique(titles)):
            column.title = title
        self.counter = _Counter()

    def labels(self) -> list[str]:
        return _labels(self.row_titles, self.rows)

    def has_row_titles(self) -> bool:
        return any(self.labels())

    def x_name(self) -> str:
        return (self.x.title if self.x and self.x.title else "") or \
            (self.kind == "Survival" and tr("Temps")) or "X"

    def values(self, column: _Column, sub: int = 0) -> np.ndarray:
        cells = column.cells[sub] if sub < len(column.cells) else []
        return _numbers(cells, self.rows, self.counter)

    def summary_columns(self, column: _Column) -> dict[str, np.ndarray]:
        """Mean, then SD / SEM / N... as Prism names its subcolumns."""
        parts = SUMMARY[self.y_format]
        out = {}
        for i, part in enumerate(parts):
            name = column.title if not part else \
                f"{column.title} {tr(part) if ' ' in part else part}"
            out[name] = self.values(column, i)
        return out


def _xy(table: _Table) -> tuple[pd.DataFrame, dict]:
    x_name = table.x_name()
    frame = {}
    if table.has_row_titles():
        frame[tr("Ligne")] = table.labels()
    x = table.values(table.x) if table.x else \
        np.arange(1, table.rows + 1, dtype=float)
    frame[x_name] = x
    if table.x_format == "error" and table.x and len(table.x.cells) > 1:
        frame[f"{x_name} {tr('erreur')}"] = table.values(table.x, 1)
    if table.x_format == "date" and table.x_text is not None:
        frame[f"{x_name} {tr('(date)')}"] = _labels(table.x_text, table.rows)

    plot = {"plot_type": "line", "x": x_name, "xlabel": x_name}
    if table.y_format in SUMMARY:
        means, errors = [], []
        for column in table.ys:
            parts = table.summary_columns(column)
            frame.update(parts)
            names = list(parts)
            means.append(names[0])
            if table.y_format in SYMMETRIC_ERROR:
                errors.append(names[1])
        plot.update(y=means, error_cols=errors)
        df = pd.DataFrame(frame)
    else:
        # one row per replicate: Plotea averages the rows sharing an X
        replicates = max((len(c.cells) for c in table.ys), default=1)
        blocks = []
        for k in range(replicates):
            block = dict(frame)
            for column in table.ys:
                block[column.title] = table.values(column, k) \
                    if k < len(column.cells) else np.full(table.rows, np.nan)
            blocks.append(pd.DataFrame(block))
        df = pd.concat(blocks, ignore_index=True)
        names = [c.title for c in table.ys]
        df = df[df[names].notna().any(axis=1)]       # rows with nothing to plot
        plot.update(y=names)
    if len(plot["y"]) == 1:
        plot["ylabel"] = plot["y"][0]
    return df.reset_index(drop=True), plot


def _column(table: _Table) -> tuple[pd.DataFrame, dict]:
    """Column table: one column per group, the wide layout Plotea knows."""
    frame = {}
    if table.has_row_titles():
        frame[tr("Ligne")] = table.labels()
    names = []
    for column in table.ys:
        # several subcolumns (rare: pasted replicates) are one group still
        values = np.concatenate([table.values(column, k)
                                 for k in range(max(len(column.cells), 1))])
        frame[column.title] = values
        names.append(column.title)
    length = max(len(v) for v in frame.values())
    frame = {k: _pad(v, length) for k, v in frame.items()}
    df = pd.DataFrame(frame).dropna(how="all", subset=names)
    return df.reset_index(drop=True), {
        "plot_type": "bar", "y": names, "ylabel": table.title}


def _grouped(table: _Table) -> tuple[pd.DataFrame, dict]:
    """Grouped table: row factor x column factor, in long format."""
    row, group, value = tr("Ligne"), tr("Groupe"), tr("Valeur")
    labels = table.labels()
    labels = [label or tr("Ligne {number}").format(number=i + 1)
              for i, label in enumerate(labels)]
    # each subcolumn read once: reading counts what it leaves out
    values = [(column.title, table.values(column, k))
              for column in table.ys for k in range(len(column.cells))]
    records = [(label, title, v[i])
               for i, label in enumerate(labels)
               for title, v in values if np.isfinite(v[i])]
    df = pd.DataFrame(records, columns=[row, group, value])
    plot = {"plot_type": "bar", "y": [value], "ylabel": table.title}
    rows_used = df[row].nunique()
    groups_used = df[group].nunique()
    if rows_used > 1 and groups_used > 1:
        plot.update(group=row, subgroup=group, xlabel="")
    elif groups_used > 1:
        plot.update(group=group, xlabel="")
    else:
        plot.update(group=row, xlabel="")
    return df, plot


def _survival(table: _Table) -> tuple[pd.DataFrame, dict]:
    """One event column per group -> time, group, event, one row a subject."""
    time, group, event = table.x_name(), tr("Groupe"), tr("Événement")
    subject = tr("Sujet")
    times = table.values(table.x) if table.x else \
        np.full(table.rows, np.nan)
    labels = table.labels()
    records = []
    for column in table.ys:
        codes = table.values(column)
        for i in range(table.rows):
            if np.isfinite(codes[i]) and np.isfinite(times[i]):
                records.append((labels[i], times[i], column.title,
                                int(codes[i] != 0)))
    df = pd.DataFrame(records, columns=[subject, time, group, event])
    if not any(labels):
        df = df.drop(columns=[subject])
    # Prism runs the log-rank test on every survival table; so does Plotea
    return df, {"plot_type": "survival", "x": time, "group": group,
                "event_col": event, "xlabel": time, "stats_enabled": True}


def _contingency(table: _Table) -> tuple[pd.DataFrame, dict]:
    """Counts, one row per group: Plotea's own contingency layout."""
    df, _plot = _as_is(table)
    groups = tr("Ligne") if tr("Ligne") in df.columns else ""
    outcomes = [c for c in df.columns if c != groups]
    return df, {"plot_type": "contingency", "group": groups, "y": outcomes,
                "xlabel": "", "stats_enabled": True}


def _as_is(table: _Table) -> tuple[pd.DataFrame, dict]:
    """Any other table, column by column, without a plot."""
    frame = {}
    if table.has_row_titles():
        frame[tr("Ligne")] = table.labels()
    if table.x is not None:
        frame[table.x_name()] = table.values(table.x)
    for column in table.ys:
        if table.y_format in SUMMARY:
            frame.update(table.summary_columns(column))
        elif len(column.cells) > 1:
            for k in range(len(column.cells)):
                frame[f"{column.title} ({k + 1})"] = table.values(column, k)
        else:
            frame[column.title] = table.values(column)
    return pd.DataFrame(frame), {}


def _pad(values, length: int):
    values = list(values)
    filler = "" if values and isinstance(values[0], str) else np.nan
    return values + [filler] * (length - len(values))


def _convert(table: _Table) -> tuple[pd.DataFrame, dict, list[str]]:
    notes = []
    summary = table.y_format in SUMMARY
    if not table.ys or not table.rows:
        return pd.DataFrame(), {}, notes
    if table.kind == "XY":
        df, plot = _xy(table)
    elif table.kind == "Survival":
        df, plot = _survival(table)
    elif table.kind == "Contingency" and not summary:
        df, plot = _contingency(table)
    elif table.kind == "OneWay" and not summary:
        df, plot = _column(table)
    elif table.kind == "TwoWay" and not summary:
        df, plot = _grouped(table)
    else:
        df, plot = _as_is(table)
        if summary and table.kind in ("OneWay", "TwoWay"):
            notes.append(tr(
                "« {table} » : Prism y stocke des moyennes et des écarts déjà "
                "calculés. Ils sont importés, mais Plotea ne trace des barres "
                "d'erreur à partir de résumés que sur les courbes.").format(
                    table=table.title))
        else:
            kind = UNPLOTTED.get(table.kind, table.kind or "?")
            notes.append(tr(
                "« {table} » : Plotea ne trace pas encore les tableaux de type "
                "{kind} ; les données sont importées telles quelles.").format(
                    table=table.title, kind=tr(kind)))
    if table.counter.excluded:
        notes.append(tr(
            "« {table} » : {count} valeur(s) exclue(s) dans Prism, laissée(s) "
            "de côté comme Prism le fait.").format(
                table=table.title, count=table.counter.excluded))
    if table.counter.unreadable:
        notes.append(tr(
            "« {table} » : {count} cellule(s) non numérique(s) ignorée(s)."
        ).format(table=table.title, count=table.counter.unreadable))
    return df, plot, notes


# --------------------------------------------------------------------------
# The file
# --------------------------------------------------------------------------
def read_pzfx(path: str) -> PrismFile:
    """Every data table of a .pzfx, in the order Prism lists them."""
    root = _parse(path)
    elements = [e for e in root if e.tag in ("Table", "HugeTable")]
    tables, notes = [], []
    for number, element in enumerate(elements, start=1):
        table = _Table(element, number)
        df, plot, table_notes = _convert(table)
        notes.extend(table_notes)
        if df.empty or df.shape[1] == 0:
            notes.append(tr("« {table} » est vide : ignoré.").format(
                table=table.title))
            continue
        dataset = Dataset(table.title, df, source=path, sheet=table.title,
                          notes=tr("Importé de GraphPad Prism"),
                          meta={"prism_type": table.kind})
        tables.append(PrismTable(dataset, table.kind, plot))
    return PrismFile(tables, notes)
