"""Spreadsheet panel: dataset list + editable table backed by a DataFrame."""
from __future__ import annotations

import numpy as np
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout,
                             QHeaderView, QInputDialog, QLabel, QListWidget,
                             QMenu, QMessageBox, QSplitter, QTableView,
                             QToolButton, QVBoxLayout, QWidget)

from ..core.dataset import Dataset
from .widgets import follow_sections, tag_icon


class DataFrameModel(QAbstractTableModel):
    """Editable Qt model over a pandas DataFrame."""

    dataChangedExternally = pyqtSignal()

    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    # -- required -----------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008 (Qt API)
        return 0 if parent.isValid() else len(self._df.index)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._df.iat[index.row(), index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return ""
            if isinstance(value, float):
                return f"{value:g}"
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if pd.api.types.is_numeric_dtype(self._df.dtypes.iloc[index.column()]):
                return int(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft
                       | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and (
                value is None
                or (isinstance(value, float) and np.isnan(value))):
            return QColor("#B0B7C0")
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        col = self._df.columns[index.column()]
        text = str(value).strip().replace(",", ".")
        if text == "":
            new = np.nan
        else:
            try:
                new = float(text)
                if pd.api.types.is_numeric_dtype(self._df[col]) is False:
                    new = text if not _column_is_numeric(self._df[col]) else new
            except ValueError:
                new = str(value)
                if pd.api.types.is_numeric_dtype(self._df[col]):
                    self._df[col] = self._df[col].astype(object)
        self._df.iat[index.row(), index.column()] = new
        self.dataChanged.emit(index, index)
        self.dataChangedExternally.emit()
        return True

    def flags(self, index):
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable)

    def headerData(self, section, orientation,
                   role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._df.columns[section])
            return str(section + 1)
        if role == Qt.ItemDataRole.FontRole \
                and orientation == Qt.Orientation.Horizontal:
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ItemDataRole.ToolTipRole \
                and orientation == Qt.Orientation.Horizontal:
            col = self._df.columns[section]
            kind = ("numérique" if pd.api.types.is_numeric_dtype(self._df[col])
                    else "texte")
            return f"{col} - {kind} - {self._df[col].notna().sum()} valeurs"
        return None

    def setHeaderData(self, section, orientation, value,
                      role=Qt.ItemDataRole.EditRole) -> bool:
        if orientation != Qt.Orientation.Horizontal:
            return False
        cols = list(self._df.columns)
        cols[section] = str(value)
        self._df.columns = cols
        self.headerDataChanged.emit(orientation, section, section)
        self.dataChangedExternally.emit()
        return True

    # -- structural edits ---------------------------------------------------
    def dataframe(self) -> pd.DataFrame:
        return self._df

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def add_rows(self, count: int = 1):
        self.beginInsertRows(QModelIndex(), len(self._df),
                             len(self._df) + count - 1)
        extra = pd.DataFrame({c: [np.nan] * count for c in self._df.columns})
        self._df = pd.concat([self._df, extra], ignore_index=True)
        self.endInsertRows()
        self.dataChangedExternally.emit()

    def add_column(self, name: str | None = None):
        n = len(self._df.columns)
        name = name or f"Col{n + 1}"
        while name in self._df.columns:
            n += 1
            name = f"Col{n + 1}"
        self.beginInsertColumns(QModelIndex(), n, n)
        self._df[name] = np.nan
        self.endInsertColumns()
        self.dataChangedExternally.emit()

    def remove_columns(self, indexes: list[int]):
        for idx in sorted(set(indexes), reverse=True):
            if 0 <= idx < len(self._df.columns):
                self.beginRemoveColumns(QModelIndex(), idx, idx)
                self._df = self._df.drop(columns=[self._df.columns[idx]])
                self.endRemoveColumns()
        self.dataChangedExternally.emit()

    def remove_rows(self, indexes: list[int]):
        keep = [i for i in range(len(self._df)) if i not in set(indexes)]
        self.beginResetModel()
        self._df = self._df.iloc[keep].reset_index(drop=True)
        self.endResetModel()
        self.dataChangedExternally.emit()

    def clear_cells(self, cells: list[tuple[int, int]]):
        for r, c in cells:
            self._df.iat[r, c] = np.nan
        self.beginResetModel()
        self.endResetModel()
        self.dataChangedExternally.emit()


def _column_is_numeric(s: pd.Series) -> bool:
    return pd.to_numeric(s, errors="coerce").notna().mean() > 0.8


class DataPanel(QWidget):
    """Left dock: the dataset list on top, the editable table below."""

    datasetChanged = pyqtSignal()        # active dataset switched
    dataEdited = pyqtSignal()            # cells changed -> re-render
    importRequested = pyqtSignal()
    addTableRequested = pyqtSignal()
    transformRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.datasets: list[Dataset] = []
        self.model = DataFrameModel()
        self.model.dataChangedExternally.connect(self.dataEdited)

        self.list = QListWidget()
        self.list.setMaximumHeight(122)
        self.list.currentRowChanged.connect(self._on_select)
        self.list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._list_menu)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(96)
        self.table.horizontalHeader().setSectionsMovable(True)
        # the column tooltips change from one section to the next: tie each
        # one to its section so the bubble follows the pointer
        self._header_tips = follow_sections(self.table.horizontalHeader())
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(
            self._header_menu)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._cell_menu)

        self.info = QLabel("Aucune donnée")
        self.info.setProperty("hint", True)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        for name, icon, tip, slot in (
                ("Importer", "import", "Importer CSV / Excel (Ctrl+O)",
                 self.importRequested.emit),
                ("Nouvelle", "table", "Nouvelle table vierge",
                 self.addTableRequested.emit),
                ("+ Ligne", "plus", "Ajouter 10 lignes",
                 lambda: self.model.add_rows(10)),
                ("+ Colonne", "plus", "Ajouter une colonne",
                 lambda: self.model.add_column()),
                ("Transformer", "fit",
                 "Normaliser, % du contrôle, log, score z...",
                 self.transformRequested.emit)):
            btn = QToolButton()
            btn.setText(name)
            tag_icon(btn, icon)
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
        bar.addStretch(1)

        split = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(4)
        tl.addWidget(self.list)
        split.addWidget(top)
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)
        bl.addWidget(self.table)
        bl.addWidget(self.info)
        split.addWidget(bottom)
        split.setStretchFactor(1, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        lay.addLayout(bar)
        lay.addWidget(split)

        copy = QAction(self)
        copy.setShortcut(QKeySequence.StandardKey.Copy)
        copy.triggered.connect(self.copy_selection)
        self.addAction(copy)
        paste = QAction(self)
        paste.setShortcut(QKeySequence.StandardKey.Paste)
        paste.triggered.connect(self.paste_clipboard)
        self.addAction(paste)
        delete = QAction(self)
        delete.setShortcut(QKeySequence.StandardKey.Delete)
        delete.triggered.connect(self._clear_selection)
        self.addAction(delete)

    # -- dataset plumbing ---------------------------------------------------
    def set_datasets(self, datasets: list[Dataset], select: int = 0):
        self.datasets = datasets
        self.list.blockSignals(True)
        self.list.clear()
        for ds in datasets:
            self.list.addItem(f"{ds.name}   ({len(ds.df)}x{len(ds.df.columns)})")
        self.list.blockSignals(False)
        if datasets:
            self.list.setCurrentRow(min(select, len(datasets) - 1))
        else:
            self.model.set_dataframe(pd.DataFrame())
            self.info.setText("Aucune donnée")

    def current_dataset(self) -> Dataset | None:
        i = self.list.currentRow()
        if 0 <= i < len(self.datasets):
            return self.datasets[i]
        return None

    def _on_select(self, index: int):
        ds = self.current_dataset()
        if ds is None:
            return
        self.model.set_dataframe(ds.df)
        num = len(ds.numeric_columns())
        self.info.setText(f"{len(ds.df)} lignes - {len(ds.df.columns)} colonnes"
                          f" ({num} numériques)"
                          + (f" - {ds.source}" if ds.source else ""))
        self.datasetChanged.emit()

    def refresh_current_label(self):
        i = self.list.currentRow()
        ds = self.current_dataset()
        if ds and 0 <= i < self.list.count():
            self.list.item(i).setText(
                f"{ds.name}   ({len(ds.df)}x{len(ds.df.columns)})")

    # -- clipboard ----------------------------------------------------------
    def copy_selection(self):
        sel = self.table.selectedIndexes()
        if not sel:
            return
        rows = sorted({i.row() for i in sel})
        cols = sorted({i.column() for i in sel})
        df = self.model.dataframe()
        lines = ["\t".join(str(df.columns[c]) for c in cols)]
        for r in rows:
            lines.append("\t".join(
                "" if pd.isna(df.iat[r, c]) else str(df.iat[r, c])
                for c in cols))
        QApplication.clipboard().setText("\n".join(lines))

    def paste_clipboard(self):
        text = QApplication.clipboard().text()
        if not text.strip():
            return
        sel = self.table.selectedIndexes()
        r0 = sel[0].row() if sel else 0
        c0 = sel[0].column() if sel else 0
        df = self.model.dataframe()
        rows = [line.split("\t") for line in text.replace("\r", "").split("\n")
                if line.strip()]
        needed_rows = r0 + len(rows) - len(df)
        if needed_rows > 0:
            self.model.add_rows(needed_rows)
            df = self.model.dataframe()
        for dr, cells in enumerate(rows):
            for dc, cell in enumerate(cells):
                r, c = r0 + dr, c0 + dc
                if c >= len(df.columns):
                    continue
                try:
                    df.iat[r, c] = float(cell.replace(",", "."))
                except ValueError:
                    if cell.strip() == "":
                        df.iat[r, c] = np.nan
                    else:
                        df[df.columns[c]] = df[df.columns[c]].astype(object)
                        df.iat[r, c] = cell
        self.model.set_dataframe(df)
        self.dataEdited.emit()

    def _clear_selection(self):
        cells = [(i.row(), i.column()) for i in self.table.selectedIndexes()]
        if cells:
            self.model.clear_cells(cells)

    # -- context menus ------------------------------------------------------
    def _header_menu(self, pos):
        header = self.table.horizontalHeader()
        col = header.logicalIndexAt(pos)
        if col < 0:
            return
        menu = QMenu(self)
        rename = menu.addAction("Renommer la colonne...")
        to_num = menu.addAction("Convertir en numérique")
        menu.addSeparator()
        insert = menu.addAction("Insérer une colonne")
        delete = menu.addAction("Supprimer la colonne")
        act = menu.exec(header.mapToGlobal(pos))
        df = self.model.dataframe()
        if act is rename:
            new, ok = QInputDialog.getText(self, "Renommer",
                                           "Nouveau nom :",
                                           text=str(df.columns[col]))
            if ok and new.strip():
                self.model.setHeaderData(col, Qt.Orientation.Horizontal,
                                         new.strip())
        elif act is to_num:
            name = df.columns[col]
            df[name] = pd.to_numeric(
                df[name].astype(str).str.replace(",", ".", regex=False),
                errors="coerce")
            self.model.set_dataframe(df)
            self.dataEdited.emit()
        elif act is insert:
            self.model.add_column()
        elif act is delete:
            self.model.remove_columns([col])

    def _cell_menu(self, pos):
        menu = QMenu(self)
        a_copy = menu.addAction("Copier")
        a_paste = menu.addAction("Coller")
        a_clear = menu.addAction("Effacer")
        menu.addSeparator()
        a_delrow = menu.addAction("Supprimer les lignes sélectionnées")
        act = menu.exec(self.table.viewport().mapToGlobal(pos))
        if act is a_copy:
            self.copy_selection()
        elif act is a_paste:
            self.paste_clipboard()
        elif act is a_clear:
            self._clear_selection()
        elif act is a_delrow:
            rows = sorted({i.row() for i in self.table.selectedIndexes()})
            if rows:
                self.model.remove_rows(rows)

    def _list_menu(self, pos):
        if self.list.currentRow() < 0:
            return
        menu = QMenu(self)
        a_rename = menu.addAction("Renommer la table...")
        a_dup = menu.addAction("Dupliquer")
        a_transpose = menu.addAction("Transposer")
        menu.addSeparator()
        a_del = menu.addAction("Supprimer")
        act = menu.exec(self.list.mapToGlobal(pos))
        ds = self.current_dataset()
        if ds is None:
            return
        if act is a_rename:
            new, ok = QInputDialog.getText(self, "Renommer la table",
                                           "Nom :", text=ds.name)
            if ok and new.strip():
                ds.name = new.strip()
                self.refresh_current_label()
                self.datasetChanged.emit()
        elif act is a_dup:
            self.datasets.append(ds.copy())
            self.set_datasets(self.datasets, len(self.datasets) - 1)
        elif act is a_transpose:
            ds.df = ds.df.set_index(ds.df.columns[0]).T.reset_index()
            ds.df.columns = [str(c) for c in ds.df.columns]
            self.model.set_dataframe(ds.df)
            self.dataEdited.emit()
        elif act is a_del:
            if len(self.datasets) == 1:
                QMessageBox.information(self, "Plotea",
                                        "Au moins une table est nécessaire.")
                return
            self.datasets.remove(ds)
            self.set_datasets(self.datasets, 0)
