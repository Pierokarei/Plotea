"""Every text Plotea may show, as the keys a translation must cover.

Two harvests:

- literal: the strings written inside tr("..."), plus the French names stored
  as data and translated when displayed (undo steps, log entries);
- runtime: labels that live in tables rather than in tr() calls - choices of
  the enumerations, theme descriptions, transforms, examples, test names,
  the headers of the statistics tables - collected by asking the modules.

    python tools/i18n_keys.py            missing English entries
    python tools/i18n_keys.py --update   add them to en.json, empty

The test suite runs the same harvest, so a text added without its
translation fails the build instead of reaching an English user in French.
"""
from __future__ import annotations

import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "plotea")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: Calls whose first argument is a French name stored as data and translated
#: where it is displayed.
STORED_NAMES = {"_record", "_begin_edit", "record", "begin"}


def _python_files():
    for folder, _dirs, files in os.walk(PACKAGE):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(folder, name)


def literal_keys() -> dict[str, str]:
    """Key -> first place it appears, from the source itself."""
    found: dict[str, str] = {}
    for path in _python_files():
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        rel = os.path.relpath(path, ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = getattr(func, "id", getattr(func, "attr", ""))
            first = node.args[0]
            if not (isinstance(first, ast.Constant)
                    and isinstance(first.value, str)):
                continue
            if name == "tr" or (name in STORED_NAMES
                                and any(c.isalpha() for c in first.value)):
                found.setdefault(first.value, f"{rel}:{first.lineno}")
        # the row headers of the comparisons table are dictionary keys
        if rel.endswith(os.path.join("ui", "stats_view.py")):
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    for key in node.keys:
                        if isinstance(key, ast.Constant) and \
                                isinstance(key.value, str):
                            found.setdefault(key.value, f"{rel}:{key.lineno}")
        # extra fit statistics are subscripts of `extra`
        if rel.endswith(os.path.join("core", "fitting.py")):
            for node in ast.walk(tree):
                if (isinstance(node, ast.Subscript)
                        and getattr(node.value, "id", "") == "extra"
                        and isinstance(node.slice, ast.Constant)):
                    found.setdefault(node.slice.value, f"{rel}:{node.lineno}")
    return found


def runtime_keys() -> set[str]:
    """Labels kept in tables, asked of the modules themselves."""
    import inspect

    import numpy as np

    from plotea.core import (
        demo,
        enums,
        export,
        fitting,
        plotting,
        stats,
        transforms,
    )
    from plotea.core.plotspec import PLOT_TYPES
    from plotea.core.project import Project
    from plotea.core.themes import THEMES

    keys: set[str] = set()
    for value in vars(enums).values():
        if isinstance(value, enums.Enum):
            keys.update(choice.label for choice in value)
    keys.update(PLOT_TYPES.values())
    keys.update(theme.description for theme in THEMES.values())
    for transform in transforms.TRANSFORMS.values():
        keys.update({transform.label, transform.description})
        if transform.suffix:
            keys.add(transform.suffix)
    keys.update(demo.EXAMPLES)
    keys.update(stats.TEST_LABELS.values())
    keys.update(export.FORMATS)
    keys.update(plotting.HIST_LABELS.values())
    keys.update({"ANOVA à un facteur", "Kruskal-Wallis", "Log-rank",
                 "ANOVA 2 facteurs", "ANOVA à mesures répétées", "ANOVA"})
    for model in fitting.MODELS.values():
        keys.add(model.label)
        keys.update(model.params)
    keys.add(Project().name)

    # the statistics tables: run them on a little data and read the headers
    rng = np.random.default_rng(0)
    groups = {"A": rng.normal(0, 1, 12), "B": rng.normal(1, 1, 12)}
    groups["A"][0] = 40.0                        # one outlier for the table
    for rows in (stats.describe(groups), stats.outliers(groups),
                 stats.describe_survival({"A": ([1, 2, 3], [1, 0, 1])})):
        for row in rows:
            keys.update(row)
    cells = {(a, b): rng.normal(0, 1, 6) for a in "xy" for b in "uv"}
    anova, _ = stats.two_way_anova(cells)
    paired = {c: {f"s{i}": float(rng.normal()) for i in range(8)}
              for c in ("c1", "c2", "c3")}
    rm, _ = stats.repeated_measures_anova(paired)
    for rows in (anova, rm):
        for row in rows:
            keys.update(row)
            keys.add(row["Source"])
    defaults = inspect.signature(stats.two_way_anova).parameters
    keys.update({defaults["factor_a"].default, defaults["factor_b"].default})

    # interface tables
    from plotea.ui.dialogs import SEPARATORS
    from plotea.ui.inspector import Inspector
    from plotea.ui.main_window import MainWindow
    from plotea.ui.projects import ProjectFiles

    keys.update(SEPARATORS)
    keys.update(Inspector.CARD_LABELS.values())
    keys.add(Inspector.PLACEHOLDER)
    keys.update(MainWindow.DOCK_TIPS.values())
    asking = inspect.signature(ProjectFiles.ask_to_keep_changes).parameters
    keys.update({asking["discard"].default, asking["question"].default})
    return {k for k in keys if isinstance(k, str) and k.strip()}


def all_keys() -> set[str]:
    return set(literal_keys()) | runtime_keys()


def needs_translation(text: str) -> bool:
    """Whether a key holds language at all: "n A", "SEM" or "Tukey HSD" are
    the same in English, but are kept in the catalogue all the same so the
    check stays simple - a missing key is always a mistake."""
    return any(ch.isalpha() for ch in text)


def main() -> int:
    from plotea import i18n

    path = i18n.catalogue_path("en")
    try:
        with open(path, encoding="utf-8") as handle:
            catalogue = json.load(handle)
    except (OSError, ValueError):
        catalogue = {}
    keys = {k for k in all_keys() if needs_translation(k)}
    missing = sorted(k for k in keys if not catalogue.get(k))
    unused = sorted(k for k in catalogue if k not in keys)
    print(f"{len(keys)} clés, {len(missing)} sans traduction, "
          f"{len(unused)} inutilisées")
    if "--update" in sys.argv:
        for key in missing:
            catalogue.setdefault(key, "")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(dict(sorted(catalogue.items())), handle,
                      ensure_ascii=False, indent=1)
            handle.write("\n")
        print("écrit", path)
    else:
        for key in missing:
            print("  manque :", repr(key))
        for key in unused:
            print("  inutile :", repr(key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
