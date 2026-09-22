"""Import and export dialogs."""
from __future__ import annotations

import os

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import dataset as ds_mod
from ..core import transforms
from ..core import export as export_mod
from ..core.themes import MM
from .widgets import CheckList

SEPARATORS = {"Automatique": None, "Virgule ,": ",", "Point-virgule ;": ";",
              "Tabulation": "\t", "Barre |": "|", "Espaces": r"\s+"}
ENCODINGS = ["utf-8", "latin-1", "cp1252", "utf-16"]


class ImportDialog(QDialog):
    """Preview a CSV/Excel file and tune the parsing before loading."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.setWindowTitle("Importer des données")
        self.resize(760, 540)
        self.datasets: list = []

        self.is_excel = os.path.splitext(path)[1].lower() in ds_mod.EXCEL_EXT

        self.cmb_sheet = QComboBox()
        self.cmb_sep = QComboBox()
        self.cmb_sep.addItems(list(SEPARATORS))
        self.cmb_dec = QComboBox()
        self.cmb_dec.addItems([". (point)", ", (virgule)"])
        self.cmb_enc = QComboBox()
        self.cmb_enc.addItems(ENCODINGS)
        self.spn_header = QSpinBox()
        self.spn_header.setRange(0, 50)
        self.chk_all_sheets = QCheckBox("Importer toutes les feuilles")

        if self.is_excel:
            try:
                self.cmb_sheet.addItems(ds_mod.list_sheets(path))
            except Exception as exc:
                QMessageBox.warning(self, "Plotea",
                                    f"Lecture impossible : {exc}")
        for w in (self.cmb_sep, self.cmb_dec, self.cmb_enc):
            w.setEnabled(not self.is_excel)
        self.cmb_sheet.setEnabled(self.is_excel)
        self.chk_all_sheets.setEnabled(self.is_excel)

        form = QFormLayout()
        form.addRow("Fichier", QLabel(os.path.basename(path)))
        if self.is_excel:
            form.addRow("Feuille", self.cmb_sheet)
            form.addRow("", self.chk_all_sheets)
        else:
            form.addRow("Séparateur", self.cmb_sep)
            form.addRow("Décimale", self.cmb_dec)
            form.addRow("Encodage", self.cmb_enc)
        form.addRow("Ligne d'en-tête", self.spn_header)

        self.preview = QTableWidget()
        self.preview.setAlternatingRowColors(True)
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.info = QLabel()
        self.info.setProperty("hint", True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Importer")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Aperçu"))
        lay.addWidget(self.preview, 1)
        lay.addWidget(self.info)
        lay.addWidget(buttons)

        for w in (self.cmb_sheet, self.cmb_sep, self.cmb_dec, self.cmb_enc):
            w.currentIndexChanged.connect(self.refresh)
        self.spn_header.valueChanged.connect(self.refresh)
        self.chk_all_sheets.toggled.connect(self.refresh)
        self.refresh()

    def _load(self) -> list:
        sheet = None
        if self.is_excel:
            sheet = (None if self.chk_all_sheets.isChecked()
                     else self.cmb_sheet.currentText())
        return ds_mod.load_file(
            self.path, sheet=sheet,
            separator=SEPARATORS[self.cmb_sep.currentText()],
            decimal="." if self.cmb_dec.currentIndex() == 0 else ",",
            header_row=self.spn_header.value(),
            encoding=self.cmb_enc.currentText())

    def refresh(self):
        try:
            self.datasets = self._load()
        except Exception as exc:
            self.datasets = []
            self.info.setText(f"Erreur : {exc}")
            self.preview.setRowCount(0)
            self.preview.setColumnCount(0)
            return
        if not self.datasets:
            self.info.setText("Aucune donnée trouvée.")
            return
        df = self.datasets[0].df
        head = df.head(60)
        self.preview.setRowCount(len(head))
        self.preview.setColumnCount(len(head.columns))
        self.preview.setHorizontalHeaderLabels([str(c) for c in head.columns])
        for r in range(len(head)):
            for c in range(len(head.columns)):
                v = head.iat[r, c]
                self.preview.setItem(
                    r, c, QTableWidgetItem("" if pd.isna(v) else str(v)))
        numeric = len([c for c in df.columns
                       if pd.api.types.is_numeric_dtype(df[c])])
        self.info.setText(
            f"{len(self.datasets)} table(s) - {len(df)} lignes x "
            f"{len(df.columns)} colonnes ({numeric} numériques)")


class ExportDialog(QDialog):
    """Pick format, resolution and physical size before writing the file."""

    def __init__(self, suggested_name: str, width_mm: float, height_mm: float,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exporter la figure")
        self.setMinimumWidth(460)

        self.cmb_format = QComboBox()
        self.cmb_format.addItems(list(export_mod.FORMATS))
        self.cmb_format.setCurrentText("PNG (raster)")
        self.cmb_dpi = QComboBox()
        self.cmb_dpi.setEditable(True)
        self.cmb_dpi.addItems([str(d) for d in export_mod.DPI_PRESETS])
        self.cmb_dpi.setCurrentText(str(export_mod.DEFAULT_DPI))
        self.chk_transparent = QCheckBox("Fond transparent")
        self.chk_tight = QCheckBox("Recadrer au contenu")
        self.chk_tight.setChecked(True)

        self.spn_w = QDoubleSpinBox()
        self.spn_w.setRange(20, 500)
        self.spn_w.setDecimals(1)
        self.spn_w.setValue(width_mm)
        self.spn_h = QDoubleSpinBox()
        self.spn_h.setRange(20, 500)
        self.spn_h.setDecimals(1)
        self.spn_h.setValue(height_mm)
        self.chk_override = QCheckBox("Redimensionner a l'export")

        self.txt_path = QLineEdit(suggested_name)
        browse = QPushButton("Parcourir...")
        browse.clicked.connect(self._browse)
        path_row = QWidget()
        pl = QHBoxLayout(path_row)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(self.txt_path, 1)
        pl.addWidget(browse)

        self.lbl_result = QLabel()
        self.lbl_result.setProperty("hint", True)

        form = QFormLayout()
        form.addRow("Format", self.cmb_format)
        form.addRow("Résolution (dpi)", self.cmb_dpi)
        form.addRow("Taille (mm)", self._row(self.spn_w, self.spn_h))
        form.addRow("", self.chk_override)
        form.addRow("", self.chk_transparent)
        form.addRow("", self.chk_tight)
        form.addRow("Fichier", path_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Exporter")
        buttons.button(QDialogButtonBox.StandardButton.Save).setProperty(
            "accent", True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Annuler")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.lbl_result)
        lay.addWidget(buttons)

        self.cmb_format.currentTextChanged.connect(self._sync)
        self.cmb_dpi.currentTextChanged.connect(self._sync)
        self.spn_w.valueChanged.connect(self._sync)
        self.spn_h.valueChanged.connect(self._sync)
        self.chk_override.toggled.connect(self._sync)
        self._sync()

    @staticmethod
    def _row(*widgets) -> QWidget:
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            lay.addWidget(w)
        lay.addStretch(1)
        return holder

    def _dpi(self) -> int:
        try:
            return max(int(float(self.cmb_dpi.currentText())), 36)
        except ValueError:
            return export_mod.DEFAULT_DPI

    def _sync(self, *_):
        fmt = self.cmb_format.currentText()
        vector = export_mod.is_vector(fmt)
        self.cmb_dpi.setEnabled(not vector)
        self.spn_w.setEnabled(self.chk_override.isChecked())
        self.spn_h.setEnabled(self.chk_override.isChecked())
        ext = export_mod.FORMATS[fmt][0]
        base = os.path.splitext(self.txt_path.text())[0]
        if base:
            self.txt_path.setText(base + ext)
        if vector:
            self.lbl_result.setText(
                "Vectoriel : texte éditable (Illustrator / Inkscape), "
                "redimensionnable sans perte.")
        else:
            dpi = self._dpi()
            px_w = int(self.spn_w.value() * MM * dpi)
            px_h = int(self.spn_h.value() * MM * dpi)
            note = "" if dpi >= 300 else "  (300 dpi minimum recommandé)"
            self.lbl_result.setText(f"Image finale : {px_w} x {px_h} px"
                                    f" a {dpi} dpi{note}")

    def _browse(self):
        fmt = self.cmb_format.currentText()
        ext = export_mod.FORMATS[fmt][0]
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la figure", self.txt_path.text(),
            f"{fmt} (*{ext})")
        if path:
            self.txt_path.setText(path)
            self._sync()

    def _validate(self):
        if not self.txt_path.text().strip():
            QMessageBox.warning(self, "Plotea", "Choisissez un fichier.")
            return
        self.accept()

    def options(self) -> export_mod.ExportOptions:
        return export_mod.ExportOptions(
            path=self.txt_path.text().strip(),
            fmt=self.cmb_format.currentText(),
            dpi=self._dpi(),
            transparent=self.chk_transparent.isChecked(),
            tight=self.chk_tight.isChecked(),
            width_mm=self.spn_w.value() if self.chk_override.isChecked()
            else None,
            height_mm=self.spn_h.value() if self.chk_override.isChecked()
            else None,
        )


class AboutDialog(QDialog):
    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        from ..resources import logo_pixmap
        self.setWindowTitle("A propos de Plotea")
        self.setFixedWidth(430)
        badge = QLabel()
        badge.setPixmap(logo_pixmap(64))
        title = QLabel("Plotea")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        body = QLabel(
            f"Version {version}\n\n"
            "Figures de qualité publication, libres et gratuites.\n"
            "Alternative ouverte a GraphPad Prism.\n\n"
            "Thématiques Nature, Science, Cell, PNAS.\n"
            "Export SVG / PDF / EPS vectoriels et PNG / TIFF jusqu'a "
            "1200 dpi.\n"
            "Tests statistiques intégrés et ajustements non linéaires.\n\n"
            "Construit avec PyQt6, matplotlib, pandas, SciPy.\n"
            "Licence MIT.")
        body.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fermer")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(badge)
        lay.addWidget(title)
        lay.addWidget(body)
        lay.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)


class TransformDialog(QDialog):
    """Derive a new table from an existing one, with a live preview."""

    def __init__(self, dataset, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.setWindowTitle("Transformer les données")
        self.resize(780, 600)
        self.result_df = None
        self.result_name = ""

        self.cmb_transform = QComboBox()
        for transform in transforms.TRANSFORMS.values():
            self.cmb_transform.addItem(transform.label, transform.key)
        self.lbl_about = QLabel()
        self.lbl_about.setWordWrap(True)
        self.lbl_about.setProperty("hint", True)

        self.lst_cols = CheckList()
        self.lst_cols.set_items(dataset.numeric_columns(),
                                dataset.numeric_columns()[:1])

        self.cmb_group = QComboBox()
        self.cmb_group.addItem("")
        self.cmb_group.addItems(dataset.columns)
        self.cmb_control = QComboBox()
        self.cmb_reference = QComboBox()
        self.cmb_reference.addItem("")
        self.cmb_reference.addItems(dataset.numeric_columns())
        self.txt_name = QLineEdit()

        form = QFormLayout()
        form.addRow("Transformation", self.cmb_transform)
        form.addRow("", self.lbl_about)
        form.addRow("Colonnes", self.lst_cols)
        self.row_group = form.addRow("Grouper par", self.cmb_group)
        form.addRow("Contrôle", self.cmb_control)
        form.addRow("Colonne de référence", self.cmb_reference)
        form.addRow("Nom de la table", self.txt_name)

        self.preview = QTableWidget()
        self.preview.setAlternatingRowColors(True)
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setProperty("hint", True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Créer la table")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Aperçu"))
        lay.addWidget(self.preview, 1)
        lay.addWidget(self.info)
        lay.addWidget(buttons)

        self.cmb_transform.currentTextChanged.connect(self._on_transform)
        self.cmb_group.currentTextChanged.connect(self._fill_controls)
        for widget in (self.cmb_control, self.cmb_reference):
            widget.currentIndexChanged.connect(self.refresh)
        self.lst_cols.changed.connect(self.refresh)
        self._on_transform(self.cmb_transform.currentText())

    # ------------------------------------------------------------------
    def current_key(self) -> str:
        return self.cmb_transform.currentData() or ""

    def _on_transform(self, label: str):
        transform = transforms.by_label(self.current_key())
        if transform is None:
            return
        self.lbl_about.setText(transform.description)
        needs = transform.needs
        self._set_visible(self.cmb_group, transforms.NEEDS_GROUP in needs)
        self._set_visible(self.cmb_control, transforms.NEEDS_CONTROL in needs)
        self._set_visible(self.cmb_reference,
                          transforms.NEEDS_REFERENCE in needs)
        base = self.dataset.name.split(" [")[0]
        self.txt_name.setText(f"{base} [{transform.suffix or transform.key}]")
        self._fill_controls()

    def _set_visible(self, widget, visible: bool):
        widget.setVisible(visible)
        label = self.layout().itemAt(0).labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _fill_controls(self, *_):
        group = self.cmb_group.currentText()
        self.cmb_control.blockSignals(True)
        self.cmb_control.clear()
        if group and group in self.dataset.df.columns:
            values = [str(v) for v in
                      self.dataset.df[group].dropna().unique()]
            self.cmb_control.addItems(values)
        self.cmb_control.blockSignals(False)
        self.refresh()

    def params(self) -> transforms.Params:
        """Only feed a transform the arguments it declares needing.

        Driven by the transform itself, never by widget visibility: a dialog
        that has not been shown yet reports everything as hidden.
        """
        transform = transforms.by_label(self.current_key())
        needs = transform.needs if transform else set()

        def take(widget, key):
            return widget.currentText() if key in needs else ""

        return transforms.Params(
            columns=self.lst_cols.checked_items(),
            group=take(self.cmb_group, transforms.NEEDS_GROUP),
            control=take(self.cmb_control, transforms.NEEDS_CONTROL),
            reference=take(self.cmb_reference, transforms.NEEDS_REFERENCE))

    def refresh(self, *_):
        frame, message = transforms.apply(self.current_key(),
                                          self.dataset.df, self.params())
        self.result_df = frame
        head = frame.head(40)
        self.preview.setRowCount(len(head))
        self.preview.setColumnCount(len(head.columns))
        self.preview.setHorizontalHeaderLabels([str(c) for c in head.columns])
        for r in range(len(head)):
            for c in range(len(head.columns)):
                value = head.iat[r, c]
                text = "" if pd.isna(value) else (
                    f"{value:g}" if isinstance(value, float) else str(value))
                self.preview.setItem(r, c, QTableWidgetItem(text))
        self.info.setText(message or
                          f"{len(frame)} lignes x {len(frame.columns)} colonnes")

    def accept(self):
        self.refresh()
        if self.result_df is None or self.result_df.empty:
            QMessageBox.warning(self, "Plotea", "La transformation ne produit "
                                                "aucune donnée.")
            return
        self.result_name = self.txt_name.text().strip() or "Table transformee"
        super().accept()


class LogDialog(QDialog):
    """Show what the renderer swallowed, with its traceback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ..core import diagnostics
        self.diagnostics = diagnostics
        self.setWindowTitle("Journal des erreurs")
        self.resize(760, 520)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setStyleSheet("font-family: Consolas, monospace;")

        self.info = QLabel()
        self.info.setProperty("hint", True)
        self.info.setWordWrap(True)

        copy = QPushButton("Copier")
        copy.clicked.connect(self._copy)
        clear = QPushButton("Vider")
        clear.clicked.connect(self._clear)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fermer")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(clear, QDialogButtonBox.ButtonRole.ResetRole)

        lay = QVBoxLayout(self)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.info)
        lay.addWidget(buttons)
        self.refresh()

    def refresh(self):
        log = self.diagnostics.LOG
        self.view.setPlainText(log.text())
        where = f" - fichier : {log.path}" if log.path else ""
        self.info.setText(f"{len(log)} événement(s){where}")

    def _copy(self):
        QApplication.clipboard().setText(self.diagnostics.LOG.text())

    def _clear(self):
        self.diagnostics.LOG.clear()
        self.refresh()
