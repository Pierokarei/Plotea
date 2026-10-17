"""Someone using Plotea, for tests that go the whole way.

A `User` only acts the way a person does: through the window's menus,
cards, lists, swatches and dialogs - the dialogs answered by monkeypatch,
since nobody is there to click. What it reads back is what the Analyses
panel would show, reduced by `fingerprint` to plain values that compare
exactly. Comparing those with what the same analysis gives when the data
are handed to the computation directly - an oracle that skips the
interface - is what catches an interface passing the wrong data to a
correct engine.
"""
from __future__ import annotations

import math

import numpy as np
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
)


# --------------------------------------------------------------------------
# What the Analyses panel shows, as values that compare exactly
# --------------------------------------------------------------------------
def _plain(value):
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return "nan" if math.isnan(value) else value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def fingerprint(info) -> dict:
    """Every statistical result of a render, and nothing of its look."""
    fits = {}
    for label, res in (info.fits or {}).items():
        fits[str(label)] = {"params": res.params, "stderr": res.stderr,
                            "r2": res.r2, "n": res.n}
    comparison = getattr(info, "fit_comparison", None)
    return _plain({
        "test": info.test_used,
        "omnibus": list(info.omnibus or ()),
        "comparisons": sorted(
            [str(c.a), str(c.b), c.test, c.stat, c.p, c.p_adj, c.n_a, c.n_b]
            for c in info.comparisons),
        "descriptives": info.descriptives,
        "groups": [str(g) for g in info.groups],
        "anova": info.anova,
        "outliers": info.outliers,
        "effects": list(info.contingency) + list(info.agreement),
        "fits": fits,
        "fit_comparison": None if comparison is None or not comparison.ok
        else [comparison.F, comparison.p],
        "assay": info.interpolations,
        "areas": info.aucs,
        "roc": info.rocs,
    })


# --------------------------------------------------------------------------
# Someone at the keyboard
# --------------------------------------------------------------------------
def _choose(text):
    def pick(menu, *args):
        return next(a for a in menu.actions() if a.text() == text)
    return pick


#: Windows opened by `reopen`, closed by the fixture when the test ends.
OPENED: list = []


class User:
    def __init__(self, window, monkeypatch):
        self.window = window
        self.mp = monkeypatch
        self.mp.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))

    # -- the window ------------------------------------------------------
    @property
    def spec(self):
        return self.window.current_spec()

    @property
    def inspector(self):
        return self.window.inspector

    def settle(self):
        QApplication.processEvents()
        self.window._render_now()

    def results(self) -> dict:
        self.settle()
        return fingerprint(self.window.canvas.last_info)

    @property
    def warnings(self) -> list:
        return list(self.window.canvas.last_info.warnings)

    # -- data ------------------------------------------------------------
    def import_file(self, path: str):
        """Fichier > Importer des données, the preview accepted as shown."""
        from plotea.ui.dialogs import ImportDialog

        self.mp.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(path), "")))
        self.mp.setattr(ImportDialog, "exec",
                        lambda self: ImportDialog.DialogCode.Accepted)
        self.window.import_data()
        self.settle()

    def select_table(self, name: str):
        names = self.window.project.dataset_names()
        self.window.data_panel.list.setCurrentRow(names.index(name))
        self.settle()

    def _column(self, name: str) -> int:
        frame = self.window.data_panel.model.dataframe()
        return [str(c) for c in frame.columns].index(name)

    def rename_column(self, old: str, new: str):
        """Right click on the column header, Renommer la colonne..."""
        header = self.window.data_panel.table.horizontalHeader()
        index = self._column(old)
        self.mp.setattr(header, "logicalIndexAt", lambda pos: index)
        self.mp.setattr(QMenu, "exec", _choose("Renommer la colonne..."))
        self.mp.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (new, True)))
        self.window.data_panel._header_menu(QPoint(5, 5))
        self.window._commit_burst()
        self.settle()

    def delete_column(self, name: str):
        header = self.window.data_panel.table.horizontalHeader()
        index = self._column(name)
        self.mp.setattr(header, "logicalIndexAt", lambda pos: index)
        self.mp.setattr(QMenu, "exec", _choose("Supprimer la colonne"))
        self.window.data_panel._header_menu(QPoint(5, 5))
        self.window._commit_burst()
        self.settle()

    def delete_rows(self, rows: list[int]):
        """Select the rows' cells, right click, Supprimer les lignes..."""
        from PyQt6.QtCore import QItemSelection, QItemSelectionModel

        panel = self.window.data_panel
        selection = QItemSelection()
        for row in rows:
            index = panel.model.index(row, 0)
            selection.select(index, index)
        panel.table.selectionModel().select(
            selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.mp.setattr(QMenu, "exec",
                        _choose("Supprimer les lignes sélectionnées"))
        panel._cell_menu(QPoint(5, 5))
        self.window._commit_burst()
        self.settle()

    def type_in(self, row: int, column: str, text: str):
        model = self.window.data_panel.model
        model.setData(model.index(row, self._column(column)), text,
                      Qt.ItemDataRole.EditRole)
        self.window._commit_burst()
        self.settle()

    def undo(self):
        self.window.undo()
        self.settle()

    # -- the plot --------------------------------------------------------
    def plot_type(self, key: str):
        for button in self.inspector.type_buttons.buttons():
            if button.property("plot_type") == key:
                button.click()
        self.settle()

    def pick(self, combo: str, text: str):
        """Choose an entry of one of the inspector's lists, by its text."""
        widget = getattr(self.inspector, combo)
        index = widget.findText(text)
        assert index >= 0, f"« {text} » absent de {combo}"
        widget.setCurrentIndex(index)
        self.settle()

    def pick_data(self, combo: str, key: str):
        """Choose an entry by its key (tests, corrections, models)."""
        widget = getattr(self.inspector, combo)
        index = widget.findData(key)
        assert index >= 0, f"« {key} » absent de {combo}"
        widget.setCurrentIndex(index)
        self.settle()

    def tick_y(self, columns: list[str]):
        listing = self.inspector.lst_y
        for i in range(listing.count()):
            item = listing.item(i)
            item.setCheckState(Qt.CheckState.Checked
                               if item.text() in columns
                               else Qt.CheckState.Unchecked)
        self.settle()

    def tick(self, checkbox: str, state: bool = True):
        getattr(self.inspector, checkbox).setChecked(state)
        self.settle()

    def colour(self, series: str, colour: str):
        """Click a series' swatch and pick a colour."""
        button = self.inspector._color_buttons[series]
        button.setColor(colour)
        button.colorChanged.emit(colour)
        self.settle()

    def theme(self, name: str):
        self.window.set_theme(name)
        self.settle()

    # -- files -----------------------------------------------------------
    def save_as(self, path: str):
        self.mp.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(path), "")))
        assert self.window.files.save_as() is not False
        return path

    def close(self):
        from conftest import dispose
        dispose(self.window)

    @classmethod
    def reopen(cls, path: str, monkeypatch) -> "User":
        """A new Plotea, the project opened from its file."""
        from plotea.ui.main_window import MainWindow

        window = MainWindow()
        window.show()
        QApplication.processEvents()
        OPENED.append(window)
        assert window.files.load(str(path))
        user = cls(window, monkeypatch)
        user.settle()
        return user
