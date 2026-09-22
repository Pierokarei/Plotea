"""Bottom dock: descriptive statistics, pairwise tests and fit reports."""
from __future__ import annotations

import math

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def _table() -> QTableWidget:
    t = QTableWidget()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(24)
    t.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(False)
    return t


def _fill(table: QTableWidget, rows: list[dict], highlight: str = ""):
    table.clear()
    if not rows:
        table.setRowCount(0)
        table.setColumnCount(0)
        return
    cols = list(rows[0])
    table.setColumnCount(len(cols))
    table.setRowCount(len(rows))
    table.setHorizontalHeaderLabels(cols)
    for r, data in enumerate(rows):
        for c, key in enumerate(cols):
            value = data.get(key)
            if isinstance(value, float):
                text = ("-" if math.isnan(value) else
                        (f"{value:.3g}" if abs(value) < 1e-3 or
                         abs(value) >= 1e5 else f"{value:.4g}"))
            else:
                text = str(value)
            item = QTableWidgetItem(text)
            if isinstance(value, (int, float)):
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter))
            if highlight and key == highlight and isinstance(value, float):
                if value < 0.05:
                    item.setForeground(QColor("#17885C"))
                    f = QFont()
                    f.setBold(True)
                    item.setFont(f)
                else:
                    item.setForeground(QColor("#8A929C"))
            table.setItem(r, c, item)


class StatsPanel(QWidget):
    """Three tabs: descriptive stats, tests, fits."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = QTabWidget()
        self.desc = _table()
        self.tests = _table()
        self.fits = QPlainTextEdit()
        self.fits.setReadOnly(True)
        self.fits.setFont(QFont("Consolas" if hasattr(QFont, "Monospace")
                                else "monospace", 10))
        self.anova = _table()
        self.outliers = _table()
        self.tabs.addTab(self.desc, "Descriptives")
        self.tabs.addTab(self.tests, "Comparaisons")
        self.tabs.addTab(self.anova, "ANOVA 2 facteurs")
        self.tabs.addTab(self.fits, "Ajustements")
        self.tabs.addTab(self.outliers, "Aberrantes")

        self.header = QLabel("Aucune analyse")
        self.header.setProperty("hint", True)
        # The summary is long and the buttons are not: let the text give way
        # first, instead of cutting "Exporter CSV" in half.
        self.header.setSizePolicy(QSizePolicy.Policy.Ignored,
                                  QSizePolicy.Policy.Preferred)
        btn_copy = QPushButton("Copier")
        btn_copy.setProperty("flat", True)
        btn_copy.clicked.connect(self.copy_current)
        btn_csv = QPushButton("Exporter CSV")
        btn_csv.setProperty("flat", True)
        btn_csv.clicked.connect(self.export_csv)
        for button in (btn_copy, btn_csv):
            button.setSizePolicy(QSizePolicy.Policy.Fixed,
                                 QSizePolicy.Policy.Fixed)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 0)
        bar.addWidget(self.header, 1)
        bar.addWidget(btn_copy)
        bar.addWidget(btn_csv)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(bar)
        lay.addWidget(self.tabs)
        self._desc_rows: list[dict] = []
        self._test_rows: list[dict] = []
        self._anova_rows: list[dict] = []
        self._outlier_rows: list[dict] = []
        self.tabs.setTabVisible(2, False)

    # ------------------------------------------------------------------
    def update_from(self, info):
        """Refresh every tab from a RenderInfo."""
        self._desc_rows = list(info.descriptives)
        _fill(self.desc, self._desc_rows)

        rows = []
        for c in info.comparisons:
            rows.append({
                "Groupe A": c.a, "Groupe B": c.b, "Test": c.test,
                "n A": c.n_a, "n B": c.n_b, "Statistique": c.stat,
                "p brut": c.p, "p ajuste": c.p_adj, "Signif.": c.stars,
                "Cohen d": c.effect,
            })
        self._test_rows = rows
        _fill(self.tests, rows, highlight="p ajuste")

        _fill(self.anova, info.anova, highlight="p")
        self._anova_rows = list(info.anova)
        anova_tab = self.tabs.indexOf(self.anova)
        self.tabs.setTabVisible(anova_tab, bool(info.anova))
        self.tabs.setTabText(anova_tab, info.anova_title or "ANOVA")
        _fill(self.outliers, info.outliers, highlight="p")
        self._outlier_rows = list(info.outliers)
        self.tabs.setTabVisible(self.tabs.indexOf(self.outliers),
                                bool(info.outliers))

        head = []
        if info.anova:
            effects = [f"{r['Source']} p = {r['p']:.4g}" for r in info.anova
                       if r["Source"] != "Residus"]
            head.append("ANOVA 2 facteurs : " + " ; ".join(effects))
        if info.omnibus and info.omnibus[0]:
            name, stat, p = info.omnibus
            head.append(f"{name}: stat = {stat:.4g}, p = {p:.4g}")
        if info.comparisons:
            head.append(f"{len(info.comparisons)} comparaison(s)")
        if info.groups:
            head.append(f"groupes: {', '.join(map(str, info.groups[:8]))}")
        self.header.setText("   |   ".join(head) if head
                            else "Aucune analyse a afficher")

        if info.fits:
            blocks = []
            for label, res in info.fits.items():
                lines = [f"=== {label} - {res.model} ==="]
                lines += res.summary_lines()
                lines.append(f"R2 ajuste = {res.r2_adj:.4f}    "
                             f"RMSE = {res.rmse:.4g}")
                for k, v in res.extra.items():
                    lines.append(f"{k} = {v:.4g}")
                blocks.append("\n".join(lines))
            self.fits.setPlainText("\n\n".join(blocks))
        else:
            self.fits.setPlainText("Aucun ajustement actif.")

        if info.warnings:
            self.header.setText(self.header.text() + "   |   "
                                + " ; ".join(info.warnings))

    # ------------------------------------------------------------------
    def _current_rows(self) -> list[dict]:
        """Rows of the tab on screen, found by widget: tabs get inserted."""
        return {id(self.desc): self._desc_rows,
                id(self.tests): self._test_rows,
                id(self.anova): self._anova_rows,
                id(self.outliers): self._outlier_rows}.get(
                    id(self.tabs.currentWidget()), [])

    def copy_current(self):
        if self.tabs.currentWidget() is self.fits:
            QApplication.clipboard().setText(self.fits.toPlainText())
            return
        rows = self._current_rows()
        if rows:
            QApplication.clipboard().setText(
                pd.DataFrame(rows).to_csv(sep="\t", index=False))

    def export_csv(self):
        rows = self._current_rows()
        if not rows:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les statistiques", "statistiques.csv",
            "CSV (*.csv)")
        if path:
            pd.DataFrame(rows).to_csv(path, index=False)
