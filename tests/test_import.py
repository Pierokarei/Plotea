"""Import: real files, European CSV, encodings and the import dialog."""
import os

import pandas as pd
import pytest

from plotea.core import dataset as ds_mod
from plotea.ui.dialogs import ImportDialog


def example_files(folder: str) -> list[str]:
    return sorted(os.listdir(folder))


@pytest.fixture(scope="module")
def base(examples_dir):
    return pd.read_csv(os.path.join(examples_dir, "viabilite_cellulaire.csv"))


@pytest.mark.parametrize("name", [
    "correlation_biomarqueur.csv", "courbe_de_croissance.csv",
    "dose_reponse.csv", "exemples_plotea.xlsx", "expression_genique.csv",
    "plan_a_deux_facteurs.csv", "viabilite_cellulaire.csv",
])
def test_example_file_loads(name, examples_dir):
    tables = ds_mod.load_file(os.path.join(examples_dir, name))
    assert tables
    for table in tables:
        assert not table.df.empty
        assert table.numeric_columns(), f"{name}: aucune colonne numerique"


@pytest.mark.parametrize("label,options", [
    ("point-virgule + virgule decimale", {"sep": ";", "decimal": ","}),
    ("tabulation", {"sep": "\t", "decimal": "."}),
    ("barre verticale", {"sep": "|", "decimal": "."}),
])
def test_delimiter_variants(label, options, base, out_dir):
    path = os.path.join(out_dir, f"variant_{abs(hash(label))}.csv")
    base.to_csv(path, index=False, **options)
    table = ds_mod.load_file(path)[0]
    assert list(table.df.columns) == list(base.columns)
    assert "Viabilité" in table.numeric_columns(), table.df.dtypes.to_dict()
    assert len(table.df) == len(base)


@pytest.mark.parametrize("sep", [",", ";", "\t", "|"])
def test_separator_is_sniffed(sep, base, out_dir):
    path = os.path.join(out_dir, "sniff.csv")
    base.to_csv(path, index=False, sep=sep)
    assert ds_mod.sniff_separator(path) == sep


def test_latin1_encoding(base, out_dir):
    path = os.path.join(out_dir, "latin1.csv")
    frame = base.copy()
    frame["Traitement"] = frame["Traitement"].str.replace("Contrôle",
                                                          "Contrôle")
    frame.to_csv(path, index=False, encoding="latin-1")
    table = ds_mod.load_file(path, encoding="latin-1")[0]
    assert "Contrôle" in set(table.df["Traitement"])


def test_messy_file_is_cleaned(out_dir):
    """Blank rows, an empty column and a missing header must not survive."""
    path = os.path.join(out_dir, "messy.csv")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("Groupe,Valeur,,Note\nA,1.5,,ok\n\nB,2.5,,ok\nA,1.8,,\n")
    table = ds_mod.load_file(path)[0]
    assert len(table.df) == 3
    assert "Valeur" in table.numeric_columns()


def test_excel_sheets(examples_dir):
    path = os.path.join(examples_dir, "exemples_plotea.xlsx")
    assert len(ds_mod.list_sheets(path)) == 6
    assert len(ds_mod.load_file(path, sheet=None)) == 6
    one = ds_mod.load_file(path, sheet="dose_reponse")
    assert len(one) == 1 and len(one[0].df) == 66


def test_dialog_previews_csv(examples_dir, qapp):
    dialog = ImportDialog(os.path.join(examples_dir,
                                       "viabilite_cellulaire.csv"))
    assert dialog.datasets
    assert dialog.preview.rowCount() > 0
    assert dialog.preview.columnCount() == 4


def test_dialog_lists_excel_sheets(examples_dir, qapp):
    dialog = ImportDialog(os.path.join(examples_dir, "exemples_plotea.xlsx"))
    assert dialog.is_excel and dialog.cmb_sheet.count() == 6
    dialog.chk_all_sheets.setChecked(True)
    assert len(dialog.datasets) == 6
