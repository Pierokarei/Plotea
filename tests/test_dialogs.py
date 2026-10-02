"""The three dialogs that stand between a file and a figure."""
import os

import pandas as pd
import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from plotea.core import export as export_mod
from plotea.core.dataset import Dataset
from plotea.ui.dialogs import (
    AboutDialog,
    ExportDialog,
    ImportDialog,
    LogDialog,
    TransformDialog,
)

app = QApplication.instance()


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------
@pytest.fixture
def french_csv(tmp_path):
    """A CSV as a French instrument writes one: semicolons and commas."""
    path = tmp_path / "mesures.csv"
    path.write_text("Temps;Signal;Groupe\n"
                    "0;10,5;A\n"
                    "1;11,25;A\n"
                    "2;;B\n", encoding="utf-8")
    return str(path)


def test_the_preview_shows_what_will_be_imported(french_csv, qapp):
    dialog = ImportDialog(french_csv)
    try:
        assert dialog.datasets, "aucune table lue"
        frame = dialog.datasets[0].df
        assert list(frame.columns) == ["Temps", "Signal", "Groupe"]
        assert frame["Signal"].iloc[0] == 10.5, "la virgule décimale"
        assert dialog.preview.rowCount() == 3
        assert dialog.preview.columnCount() == 3
        assert dialog.preview.item(0, 1).text() == "10.5"
        assert dialog.preview.item(2, 1).text() == "", "le trou doit rester vide"
        assert "3 lignes" in dialog.info.text()
        assert "2 numériques" in dialog.info.text()
    finally:
        dialog.deleteLater()


def test_changing_the_separator_changes_the_reading(french_csv, qapp):
    """The whole point of the dialog: see the mistake before importing."""
    dialog = ImportDialog(french_csv)
    try:
        dialog.cmb_sep.setCurrentText("Virgule ,")
        dialog.refresh()
        # read with the wrong separator, everything lands in one column
        assert dialog.preview.columnCount() <= 2
    finally:
        dialog.deleteLater()


def test_a_header_further_down_the_file(tmp_path, qapp):
    path = tmp_path / "entete.csv"
    path.write_text("Export instrument v2\nsérie 42\n"
                    "Temps;Signal\n0;1\n1;2\n", encoding="utf-8")
    dialog = ImportDialog(str(path))
    try:
        dialog.spn_header.setValue(2)       # third line
        dialog.refresh()
        assert list(dialog.datasets[0].df.columns) == ["Temps", "Signal"]
    finally:
        dialog.deleteLater()


def test_an_unreadable_file_is_explained_not_raised(tmp_path, qapp):
    path = tmp_path / "vide.csv"
    path.write_text("", encoding="utf-8")
    dialog = ImportDialog(str(path))
    try:
        assert dialog.datasets == []
        assert dialog.info.text(), "aucune explication affichée"
        assert dialog.preview.rowCount() == 0
    finally:
        dialog.deleteLater()


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
@pytest.fixture
def export(tmp_path, qapp):
    """As the window opens it: a suggested path inside the last folder."""
    dialog = ExportDialog(os.path.join(str(tmp_path), "figure.png"),
                          89.0, 69.0)
    yield dialog
    dialog.deleteLater()


def test_the_extension_follows_the_format(export):
    export.cmb_format.setCurrentText("PDF (vectoriel, publication)")
    assert export.txt_path.text().endswith(".pdf")
    export.cmb_format.setCurrentText("PNG (raster)")
    assert export.txt_path.text().endswith(".png")


def test_resolution_is_meaningless_for_a_vector_file(export):
    export.cmb_format.setCurrentText("SVG (vectoriel, éditable)")
    assert not export.cmb_dpi.isEnabled()
    assert "ectoriel" in export.lbl_result.text()

    export.cmb_format.setCurrentText("TIFF (raster, LZW)")
    assert export.cmb_dpi.isEnabled()


def test_the_dialog_says_how_many_pixels_come_out(export):
    export.cmb_format.setCurrentText("PNG (raster)")
    export.cmb_dpi.setCurrentText("600")
    export._sync()
    # 89 mm at 600 dpi is 2102 px, and the reader should not have to work
    # that out from millimetres and a resolution
    assert "2102" in export.lbl_result.text(), export.lbl_result.text()


def test_a_low_resolution_is_flagged(export):
    export.cmb_format.setCurrentText("PNG (raster)")
    export.cmb_dpi.setCurrentText("72")
    export._sync()
    assert "300 dpi" in export.lbl_result.text(), "aucune mise en garde"


def test_a_nonsense_resolution_falls_back(export):
    export.cmb_dpi.setCurrentText("beaucoup")
    assert export._dpi() == export_mod.DEFAULT_DPI
    export.cmb_dpi.setCurrentText("4")
    assert export._dpi() >= 36, "une résolution inutilisable"


def test_the_size_is_the_figure_size_unless_overridden(export):
    options = export.options()
    assert options.width_mm is None and options.height_mm is None

    export.chk_override.setChecked(True)
    export.spn_w.setValue(120.0)
    export.spn_h.setValue(90.0)
    options = export.options()
    assert (options.width_mm, options.height_mm) == (120.0, 90.0)


def test_exporting_without_a_file_refuses_politely(export, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a)))
    export.txt_path.setText("   ")
    export._validate()
    assert warned, "la boîte a été acceptée sans fichier"
    assert export.result() != ExportDialog.DialogCode.Accepted


def test_browsing_keeps_the_chosen_path(export, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("D:/ailleurs/f.png", "")))
    export._browse()
    assert export.txt_path.text().endswith("f.png")


def test_the_options_describe_what_was_asked(export):
    export.cmb_format.setCurrentText("PNG (raster)")
    export.cmb_dpi.setCurrentText("300")
    export.chk_transparent.setChecked(True)
    options = export.options()
    assert options.dpi == 300
    assert options.transparent is True
    assert options.path.endswith(".png")


# --------------------------------------------------------------------------
# Transform
# --------------------------------------------------------------------------
@pytest.fixture
def transform(qapp):
    frame = pd.DataFrame({
        "Traitement": ["Contrôle", "Contrôle", "Drogue", "Drogue"],
        "Viabilité": [100.0, 96.0, 51.0, 49.0],
        "Réplicat": [1, 2, 1, 2],
    })
    dialog = TransformDialog(Dataset("Viabilité", frame))
    yield dialog
    dialog.deleteLater()


def choose_transform(dialog, key: str):
    index = dialog.cmb_transform.findData(key)
    assert index >= 0, key
    dialog.cmb_transform.setCurrentIndex(index)


def test_the_preview_computes_the_transform(transform):
    """Percent of control: 100 against a control averaging 98 is 102 %."""
    choose_transform(transform, "percent")
    transform.lst_cols.set_checked(["Viabilité"])
    transform.cmb_group.setCurrentText("Traitement")
    transform._fill_controls()
    transform.cmb_control.setCurrentText("Contrôle")
    transform.refresh()

    assert transform.result_df is not None
    values = transform.result_df["Viabilité"]
    assert round(float(values.iloc[0]), 2) == 102.04
    assert round(float(values.iloc[3]), 2) == 50.0
    assert transform.preview.rowCount() == 4
    assert transform.preview.item(0, 1).text().startswith("102")


def test_the_control_list_follows_the_grouping_column(transform):
    choose_transform(transform, "percent")
    transform.cmb_group.setCurrentText("Traitement")
    transform._fill_controls()
    offered = [transform.cmb_control.itemText(i)
               for i in range(transform.cmb_control.count())]
    assert offered == ["Contrôle", "Drogue"]


def test_only_the_arguments_a_transform_asks_for_are_passed(transform):
    """A hidden widget still holds a value; the transform decides, not the UI."""
    choose_transform(transform, "log10")
    transform.lst_cols.set_checked(["Viabilité"])
    transform.cmb_group.setCurrentText("Traitement")
    params = transform.params()
    assert params.group == "", "log10 n'a que faire d'un groupe"
    assert params.columns == ["Viabilité"]

    choose_transform(transform, "percent")
    transform.cmb_group.setCurrentText("Traitement")
    assert transform.params().group == "Traitement"


def test_the_suggested_name_says_what_was_done(transform):
    choose_transform(transform, "zscore")
    assert "Viabilité" in transform.txt_name.text()
    assert transform.txt_name.text() != "Viabilité", "nom inchangé"


def test_a_transform_without_a_column_is_refused(transform, monkeypatch):
    """It used to return the table untouched, under a name claiming a
    calculation that never ran."""
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a)))
    choose_transform(transform, "log10")
    transform.lst_cols.set_checked([])        # no column at all
    transform.accept()
    assert warned, "une transformation vide a été acceptée"
    assert transform.result() != TransformDialog.DialogCode.Accepted
    assert "colonne" in transform.info.text().lower(), transform.info.text()


def test_accepting_keeps_the_table_and_its_name(transform):
    choose_transform(transform, "log10")
    transform.lst_cols.set_checked(["Viabilité"])
    transform.txt_name.setText("Viabilité en log")
    transform.accept()
    assert transform.result_name == "Viabilité en log"
    assert transform.result_df is not None
    assert not transform.result_df.empty


# --------------------------------------------------------------------------
# The two small ones
# --------------------------------------------------------------------------
def test_the_about_box_names_the_version(qapp):
    from PyQt6.QtWidgets import QLabel

    dialog = AboutDialog("1.2.3")
    try:
        said = " ".join(label.text() for label in dialog.findChildren(QLabel))
        assert "1.2.3" in said, said[:200]
        assert "Plotea" in said
    finally:
        dialog.deleteLater()


def test_the_log_dialog_shows_what_was_recorded(qapp, tmp_path):
    from plotea.core import diagnostics

    diagnostics.LOG.record("Essai", "quelque chose a échoué", "trace")
    dialog = LogDialog()
    try:
        dialog.refresh()
        assert "Essai" in dialog.view.toPlainText()
        dialog._copy()
        assert "Essai" in QApplication.clipboard().text()
        dialog._clear()
        dialog.refresh()
        assert "Essai" not in dialog.view.toPlainText()
    finally:
        dialog.deleteLater()


def test_the_suggested_path_is_kept(tmp_path, qapp):
    suggested = os.path.join(str(tmp_path), "ma figure.png")
    dialog = ExportDialog(suggested, 89.0, 69.0)
    try:
        assert dialog.txt_path.text() == suggested
        assert dialog.options().path == suggested
    finally:
        dialog.deleteLater()
