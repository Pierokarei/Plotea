"""What must not change the results, for every example Plotea ships.

The order of the rows, a column nobody uses, the name of a column nobody
uses, the look of the plot, a trip to the disk and back: none of these is
data, so none may move a p-value. Each example is analysed as it opens,
then again after each of these, and the statistical results compared -
exactly, but for the order of the rows, which changes the order of sums
and so the last digits.
"""
import math

import numpy as np
import pytest
from driver import fingerprint
from matplotlib.figure import Figure

from plotea.core import demo, plotting
from plotea.core.dataset import Dataset
from plotea.core.plotspec import COLUMN_FIELDS, COLUMN_LISTS, PlotSpec
from plotea.core.project import Project

EXAMPLES = sorted(demo.EXAMPLES)


def analyse(spec: PlotSpec, frame) -> dict:
    return canonical(fingerprint(plotting.render(Figure(), spec, frame)))


def canonical(results: dict) -> dict:
    """Rows in a fixed order: which group comes first is the table's order,
    not a result."""
    out = dict(results)
    for key in ("descriptives", "outliers", "effects", "assay", "areas",
                "roc", "anova"):
        out[key] = sorted(results[key], key=repr)
    out["groups"] = sorted(results["groups"])
    # "A against B" or "B against A": the same test, its statistic of the
    # other sign
    pairs = []
    for a, b, test, stat, p, p_adj, n_a, n_b in results["comparisons"]:
        if a > b:
            a, b, n_a, n_b = b, a, n_b, n_a
        pairs.append([a, b, test, abs(stat) if isinstance(stat, float)
                      else stat, p, p_adj, n_a, n_b])
    out["comparisons"] = sorted(pairs, key=repr)
    # where an outlier sits in the table is its address, not a result
    out["outliers"] = sorted(
        ({k: v for k, v in row.items() if k != "Rang dans le groupe"}
         for row in results["outliers"]), key=repr)
    return out


def close(a, b, rel=1e-9) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], rel) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=rel, abs_tol=1e-12)
    return a == b


def example(label):
    table = demo.EXAMPLES[label]()
    return table, PlotSpec(**table.meta["plot"])


def used_columns(spec: PlotSpec) -> set:
    names = {getattr(spec, f) for f in COLUMN_FIELDS}
    for f in COLUMN_LISTS:
        names |= set(getattr(spec, f))
    return {n for n in names if n}


@pytest.mark.parametrize("label", EXAMPLES)
def test_the_order_of_the_rows(label):
    table, spec = example(label)
    shuffled = table.df.sample(frac=1.0, random_state=7)
    assert close(analyse(spec, shuffled), analyse(spec, table.df), rel=1e-12)


@pytest.mark.parametrize("label", EXAMPLES)
def test_a_column_nobody_uses(label):
    table, spec = example(label)
    extra = table.df.assign(Commentaire="à revoir",
                            Lot=np.arange(len(table.df)) % 3)
    assert analyse(spec, extra) == analyse(spec, table.df)


@pytest.mark.parametrize("label", EXAMPLES)
def test_renaming_the_columns_nobody_uses(label):
    table, spec = example(label)
    unused = [c for c in table.df.columns if c not in used_columns(spec)]
    renamed = table.df.rename(columns={c: f"{c} (bis)" for c in unused})
    assert analyse(spec, renamed) == analyse(spec, table.df)


@pytest.mark.parametrize("label", EXAMPLES)
def test_the_look_of_the_plot(label):
    table, spec = example(label)
    styled = PlotSpec.from_dict(spec.to_dict())
    styled.theme, styled.palette = "Cell", "Okabe-Ito (CB-safe)"
    styled.width_mm, styled.height_mm = 120.0, 90.0
    styled.custom_colors = {str(g): "#123456" for g in
                            analyse(spec, table.df)["groups"]}
    styled.grid_y, styled.despine, styled.show_points = True, False, False
    styled.title, styled.ylabel = "Autre titre", "Autre axe"
    assert analyse(styled, table.df) == analyse(spec, table.df)


@pytest.mark.parametrize("label", EXAMPLES)
def test_a_trip_to_the_disk(label, tmp_path):
    table, spec = example(label)
    project = Project()
    project.add_dataset(Dataset(table.name, table.df.copy()))
    project.add_plot(PlotSpec.from_dict({**spec.to_dict(),
                                         "dataset": table.name}))
    back = Project.load(project.save(str(tmp_path / "x.plotea")))
    again = back.plots[-1]
    assert analyse(again, back.datasets[0].df) == analyse(spec, table.df)
