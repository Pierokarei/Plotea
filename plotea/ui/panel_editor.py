"""Right-hand editor for a multi-panel figure."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QLabel,
                             QLineEdit, QListWidget, QPushButton, QScrollArea,
                             QSpinBox, QVBoxLayout, QWidget)

from ..core import enums
from ..core.panel import Panel
from ..core.themes import THEMES
from .widgets import CollapsibleSection, hint, row


class PanelEditor(QWidget):
    """Compose a figure from existing plots, in a chosen grid."""

    changed = pyqtSignal()
    renamed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel: Panel | None = None
        self._loading = True

        inner = QWidget()
        self.vbox = QVBoxLayout(inner)
        self.vbox.setContentsMargins(10, 6, 10, 14)
        self.vbox.setSpacing(2)

        self._build_content()
        self._build_layout_section()
        self._build_style()
        self.vbox.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)
        self._loading = False

    # ------------------------------------------------------------------
    def _build_content(self):
        sec = CollapsibleSection("Contenu de la figure", True)
        self.vbox.addWidget(sec)

        self.txt_name = QLineEdit()
        self.txt_name.textEdited.connect(self._on_rename)
        sec.add_row("Nom", self.txt_name)

        self.lst_plots = QListWidget()
        self.lst_plots.setMaximumHeight(150)
        sec.add_widget(QLabel("Panneaux, dans l'ordre"))
        sec.add_widget(self.lst_plots)

        self.cmb_available = QComboBox()
        add = QPushButton("Ajouter")
        add.clicked.connect(self._add_plot)
        sec.add_widget(row(self.cmb_available, add, stretch_last=True))

        up = QPushButton("Monter")
        down = QPushButton("Descendre")
        remove = QPushButton("Retirer")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        remove.clicked.connect(self._remove_plot)
        sec.add_widget(row(up, down, remove))
        sec.add_widget(hint("Les lettres A, B, C suivent cet ordre."))

    def _build_layout_section(self):
        sec = CollapsibleSection("Disposition", True)
        self.vbox.addWidget(sec)
        self.spn_cols = QSpinBox()
        self.spn_cols.setRange(1, 8)
        self.spn_rows = QSpinBox()
        self.spn_rows.setRange(0, 8)
        self.spn_rows.setSpecialValueText("auto")
        sec.add_row("Colonnes", self.spn_cols)
        sec.add_row("Lignes", self.spn_rows)

        self.cmb_span = QComboBox()
        self._fill(self.cmb_span, enums.SPAN)
        sec.add_row("Largeur", self.cmb_span)
        self.spn_w = self._spin(40, 500, 1)
        self.spn_h = self._spin(30, 500, 1)
        sec.add_row("Taille (mm)", row(self.spn_w, QLabel("x"), self.spn_h))

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(list(THEMES))
        sec.add_row("Largeur de référence", self.cmb_theme)

        self.spn_wspace = self._spin(0.0, 1.5, 0.02)
        self.spn_hspace = self._spin(0.0, 1.5, 0.02)
        sec.add_row("Écart H / V", row(self.spn_wspace, self.spn_hspace))
        self.chk_sharex = QCheckBox("Meme axe X")
        self.chk_sharey = QCheckBox("Meme axe Y")
        sec.add_widget(row(self.chk_sharex, self.chk_sharey))

        for widget in (self.spn_cols, self.spn_rows, self.spn_w, self.spn_h,
                       self.spn_wspace, self.spn_hspace):
            widget.valueChanged.connect(self._push)
        for widget in (self.cmb_span, self.cmb_theme):
            widget.currentIndexChanged.connect(self._push)
        for widget in (self.chk_sharex, self.chk_sharey):
            widget.toggled.connect(self._push)

    def _build_style(self):
        sec = CollapsibleSection("Lettres de panneau", True)
        self.vbox.addWidget(sec)
        self.cmb_letters = QComboBox()
        self._fill(self.cmb_letters, enums.PANEL_LETTERS)
        sec.add_row("Style", self.cmb_letters)
        self.spn_letter = self._spin(5, 24, 0.5)
        sec.add_row("Taille (pt)", self.spn_letter)
        self.cmb_letters.currentIndexChanged.connect(self._push)
        self.spn_letter.valueChanged.connect(self._push)

    @staticmethod
    def _fill(combo: QComboBox, enum) -> QComboBox:
        combo.clear()
        for choice in enum:
            combo.addItem(choice.label, choice.key)
        return combo

    @staticmethod
    def _spin(minimum, maximum, step) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(minimum, maximum)
        s.setSingleStep(step)
        s.setDecimals(2 if step < 1 else 1)
        s.setFixedWidth(80)
        return s

    # ------------------------------------------------------------------
    def set_panel(self, panel: Panel, available: list[str]):
        self._loading = True
        self.panel = panel
        self.txt_name.setText(panel.name)
        self.lst_plots.clear()
        self.lst_plots.addItems(panel.plots)
        self.cmb_available.clear()
        self.cmb_available.addItems(available)
        self.spn_cols.setValue(panel.cols)
        self.spn_rows.setValue(panel.rows)
        self.cmb_span.setCurrentIndex(max(self.cmb_span.findData(panel.span), 0))
        self.spn_w.setValue(panel.width_mm)
        self.spn_h.setValue(panel.height_mm)
        self.cmb_theme.setCurrentText(panel.theme)
        self.spn_wspace.setValue(panel.wspace)
        self.spn_hspace.setValue(panel.hspace)
        self.chk_sharex.setChecked(panel.share_x)
        self.chk_sharey.setChecked(panel.share_y)
        self.cmb_letters.setCurrentIndex(max(self.cmb_letters.findData(panel.letters), 0))
        self.spn_letter.setValue(panel.letter_size)
        self._loading = False
        self._sync_enabled()

    def _push(self, *_):
        if self._loading or self.panel is None:
            return
        p = self.panel
        p.plots = [self.lst_plots.item(i).text()
                   for i in range(self.lst_plots.count())]
        p.cols = int(self.spn_cols.value())
        p.rows = int(self.spn_rows.value())
        p.span = self.cmb_span.currentData()
        p.width_mm = self.spn_w.value()
        p.height_mm = self.spn_h.value()
        p.theme = self.cmb_theme.currentText()
        p.wspace = self.spn_wspace.value()
        p.hspace = self.spn_hspace.value()
        p.share_x = self.chk_sharex.isChecked()
        p.share_y = self.chk_sharey.isChecked()
        p.letters = self.cmb_letters.currentData()
        p.letter_size = self.spn_letter.value()
        self._sync_enabled()
        self.changed.emit()

    def _sync_enabled(self):
        custom = self.cmb_span.currentData() == "custom"
        self.spn_w.setEnabled(custom)
        self.cmb_theme.setEnabled(not custom)

    def _on_rename(self, text: str):
        if self._loading or self.panel is None:
            return
        self.panel.name = text.strip() or self.panel.name
        self.renamed.emit()

    # ------------------------------------------------------------------
    def _add_plot(self):
        name = self.cmb_available.currentText()
        if not name or self.panel is None:
            return
        self.lst_plots.addItem(name)
        self.lst_plots.setCurrentRow(self.lst_plots.count() - 1)
        self._push()

    def _remove_plot(self):
        index = self.lst_plots.currentRow()
        if index >= 0:
            self.lst_plots.takeItem(index)
            self._push()

    def _move(self, delta: int):
        index = self.lst_plots.currentRow()
        target = index + delta
        if index < 0 or not (0 <= target < self.lst_plots.count()):
            return
        item = self.lst_plots.takeItem(index)
        self.lst_plots.insertItem(target, item)
        self.lst_plots.setCurrentRow(target)
        self._push()
