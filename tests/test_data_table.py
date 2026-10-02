"""The table people actually type in: editing, clipboard and context menus."""
import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox

from plotea.core.dataset import Dataset
from plotea.ui.data_view import DataFrameModel

app = QApplication.instance()


@pytest.fixture
def model():
    frame = pd.DataFrame({"Mesure": [1.0, 2.0, 3.0],
                          "Groupe": ["a", "b", "c"]})
    return DataFrameModel(frame)


def cell(model, row, column, role=Qt.ItemDataRole.DisplayRole):
    return model.data(model.index(row, column), role)


def type_in(model, row, column, text) -> bool:
    return model.setData(model.index(row, column), text,
                         Qt.ItemDataRole.EditRole)


def choose(text: str):
    """Answer the next context menu by picking the entry named `text`."""
    def fake_exec(menu, *args, **kwargs):
        for action in menu.actions():
            if action.text().replace("&", "") == text:
                return action
        raise AssertionError(f"entrée absente : {text} "
                             f"({[a.text() for a in menu.actions()]})")
    return fake_exec


# --------------------------------------------------------------------------
# Typing into a cell
# --------------------------------------------------------------------------
def test_a_french_decimal_is_a_number(model):
    """People type 3,5 - and a column of text would silently follow."""
    assert type_in(model, 0, 0, "3,5")
    assert model.dataframe().iat[0, 0] == 3.5
    assert pd.api.types.is_numeric_dtype(model.dataframe()["Mesure"])


def test_text_in_a_numeric_column_keeps_the_other_values(model):
    assert type_in(model, 1, 0, "ND")
    frame = model.dataframe()
    assert frame.iat[1, 0] == "ND"
    assert frame.iat[0, 0] == 1.0, "les autres valeurs ont été perdues"
    assert frame.iat[2, 0] == 3.0


def test_an_empty_cell_becomes_missing_not_zero(model):
    """Zero and "not measured" are different things on a figure."""
    assert type_in(model, 0, 0, "")
    value = model.dataframe().iat[0, 0]
    assert isinstance(value, float) and np.isnan(value)
    assert cell(model, 0, 0) == "", "une case vide ne doit rien afficher"
    assert cell(model, 0, 0, Qt.ItemDataRole.ForegroundRole) is not None


def test_numbers_are_aligned_right_and_text_left(model):
    right = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    left = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    assert cell(model, 0, 0, Qt.ItemDataRole.TextAlignmentRole) == right
    assert cell(model, 0, 1, Qt.ItemDataRole.TextAlignmentRole) == left


def test_an_edit_is_announced(model):
    seen = []
    model.dataChangedExternally.connect(lambda: seen.append(True))
    type_in(model, 0, 0, "9")
    assert seen, "rien n'a prévenu que la table avait changé"


def test_nothing_happens_outside_the_table(model):
    from PyQt6.QtCore import QModelIndex

    assert model.setData(QModelIndex(), "4") is False
    assert model.data(QModelIndex()) is None
    assert model.rowCount(model.index(0, 0)) == 0, "pas d'enfants"


def test_a_cell_can_be_edited(model):
    flags = model.flags(model.index(0, 0))
    assert flags & Qt.ItemFlag.ItemIsEditable
    assert flags & Qt.ItemFlag.ItemIsSelectable


# --------------------------------------------------------------------------
# Columns and rows
# --------------------------------------------------------------------------
def test_the_header_says_what_the_column_holds(model):
    tip = model.headerData(0, Qt.Orientation.Horizontal,
                           Qt.ItemDataRole.ToolTipRole)
    assert "numérique" in tip and "3 valeurs" in tip
    text_tip = model.headerData(1, Qt.Orientation.Horizontal,
                                Qt.ItemDataRole.ToolTipRole)
    assert "texte" in text_tip
    assert model.headerData(0, Qt.Orientation.Vertical) == "1", "lignes en 1..n"


def test_renaming_a_column(model):
    assert model.setHeaderData(0, Qt.Orientation.Horizontal, "Viabilité")
    assert list(model.dataframe().columns) == ["Viabilité", "Groupe"]
    assert model.setHeaderData(0, Qt.Orientation.Vertical, "x") is False


def test_added_columns_never_collide(model):
    model.add_column()
    model.add_column("Groupe")        # a name already taken
    names = list(model.dataframe().columns)
    assert len(names) == len(set(names)), names
    assert len(names) == 4


def test_rows_are_renumbered_after_a_deletion(model):
    model.remove_rows([0])
    frame = model.dataframe()
    assert len(frame) == 2
    assert list(frame.index) == [0, 1], "index laissé à trous"
    assert frame.iat[0, 0] == 2.0


def test_removing_several_columns_at_once(model):
    model.add_column("Extra")
    model.remove_columns([0, 2])
    assert list(model.dataframe().columns) == ["Groupe"]


def test_clearing_cells_empties_without_shifting(model):
    model.clear_cells([(0, 0), (2, 1)])
    frame = model.dataframe()
    assert np.isnan(frame.iat[0, 0])
    assert pd.isna(frame.iat[2, 1])
    assert frame.iat[1, 0] == 2.0, "les voisines ont bougé"


def test_adding_rows_fills_them_with_nothing(model):
    model.add_rows(2)
    frame = model.dataframe()
    assert len(frame) == 5
    assert frame.iloc[3].isna().all()


# --------------------------------------------------------------------------
# Clipboard
# --------------------------------------------------------------------------
@pytest.fixture
def panel(window):
    """The data panel of a real window, on a small table of our own."""
    frame = pd.DataFrame({"Temps": [0.0, 1.0, 2.0],
                          "Signal": [10.0, np.nan, 30.0]})
    window.project.datasets = [Dataset("Table", frame)]
    window.data_panel.set_datasets(window.project.datasets, 0)
    app.processEvents()
    return window.data_panel


def select(panel, cells):
    from PyQt6.QtCore import QItemSelection, QItemSelectionModel

    selection = QItemSelection()
    for row, column in cells:
        index = panel.model.index(row, column)
        selection.select(index, index)
    panel.table.selectionModel().select(
        selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def test_copying_sends_values_and_leaves_gaps_empty(panel):
    """Values only: a header line would land in a cell when pasted back."""
    select(panel, [(0, 0), (0, 1), (1, 0), (1, 1)])
    panel.copy_selection()
    lines = QApplication.clipboard().text().splitlines()
    assert lines[0] == "0.0\t10.0"
    assert lines[1] == "1.0\t", "une valeur manquante doit rester vide"
    assert len(lines) == 2


def test_copying_nothing_leaves_the_clipboard_alone(panel):
    QApplication.clipboard().setText("témoin")
    panel.table.clearSelection()
    panel.copy_selection()
    assert QApplication.clipboard().text() == "témoin"


def test_pasting_grows_the_table_when_it_has_to(panel):
    QApplication.clipboard().setText("4,5\n5,5\n6,5\n7,5")
    select(panel, [(1, 1)])
    panel.paste_clipboard()
    frame = panel.model.dataframe()
    assert len(frame) == 5, "le collage a été tronqué"
    assert frame.iat[1, 1] == 4.5, "la virgule décimale doit être comprise"
    assert frame.iat[4, 1] == 7.5


def test_pasting_text_into_a_number_column_does_not_lose_the_numbers(panel):
    QApplication.clipboard().setText("n.d.")
    select(panel, [(0, 1)])
    panel.paste_clipboard()
    frame = panel.model.dataframe()
    assert frame.iat[0, 1] == "n.d."
    assert frame.iat[2, 1] == 30.0


def test_pasting_past_the_last_column_is_ignored(panel):
    QApplication.clipboard().setText("1\t2\t3\t4")
    select(panel, [(0, 0)])
    panel.paste_clipboard()
    assert len(panel.model.dataframe().columns) == 2, "des colonnes inventées"


def test_pasting_nothing_changes_nothing(panel):
    QApplication.clipboard().setText("   ")
    before = panel.model.dataframe().copy()
    panel.paste_clipboard()
    pd.testing.assert_frame_equal(panel.model.dataframe(), before)


# --------------------------------------------------------------------------
# Context menus
# --------------------------------------------------------------------------
def test_renaming_a_column_from_the_header_menu(panel, monkeypatch):
    monkeypatch.setattr(QMenu, "exec", choose("Renommer la colonne..."))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Durée", True)))
    from PyQt6.QtCore import QPoint

    panel._header_menu(QPoint(5, 5))
    assert list(panel.model.dataframe().columns)[0] == "Durée"


def test_converting_a_column_to_numbers(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    frame = panel.model.dataframe()
    frame["Temps"] = frame["Temps"].astype(str).str.replace(".", ",")
    panel.model.set_dataframe(frame)
    assert not pd.api.types.is_numeric_dtype(panel.model.dataframe()["Temps"])

    monkeypatch.setattr(QMenu, "exec", choose("Convertir en numérique"))
    panel._header_menu(QPoint(5, 5))

    converted = panel.model.dataframe()["Temps"]
    assert pd.api.types.is_numeric_dtype(converted)
    assert list(converted) == [0.0, 1.0, 2.0], "les virgules ont été perdues"


def test_deleting_a_column_from_the_header_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    monkeypatch.setattr(QMenu, "exec", choose("Supprimer la colonne"))
    panel._header_menu(QPoint(5, 5))
    assert list(panel.model.dataframe().columns) == ["Signal"]


def test_deleting_rows_from_the_cell_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    select(panel, [(0, 0), (0, 1)])
    monkeypatch.setattr(QMenu, "exec",
                        choose("Supprimer les lignes sélectionnées"))
    panel._cell_menu(QPoint(5, 5))
    frame = panel.model.dataframe()
    assert len(frame) == 2
    assert frame.iat[0, 0] == 1.0


def test_clearing_cells_from_the_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    select(panel, [(0, 1)])
    monkeypatch.setattr(QMenu, "exec", choose("Effacer"))
    panel._cell_menu(QPoint(5, 5))
    assert pd.isna(panel.model.dataframe().iat[0, 1])


def test_duplicating_a_table_from_the_list_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    monkeypatch.setattr(QMenu, "exec", choose("Dupliquer"))
    panel._list_menu(QPoint(5, 5))
    assert len(panel.datasets) == 2
    assert panel.datasets[1].df is not panel.datasets[0].df, "copie partagée"


def test_the_last_table_cannot_be_deleted(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    said = []
    monkeypatch.setattr(QMenu, "exec", choose("Supprimer"))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: said.append(a[-1])))
    panel._list_menu(QPoint(5, 5))
    assert len(panel.datasets) == 1, "la dernière table a disparu"
    assert said, "aucune explication donnée"


def test_renaming_a_table_from_the_list_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    monkeypatch.setattr(QMenu, "exec", choose("Renommer la table..."))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Manip 3", True)))
    panel._list_menu(QPoint(5, 5))
    assert panel.datasets[0].name == "Manip 3"
    assert "Manip 3" in panel.list.item(0).text()


def test_an_empty_project_says_so(panel):
    panel.set_datasets([], 0)
    assert panel.model.rowCount() == 0
    assert "Aucune donnée" in panel.info.text()


def test_transposing_a_table(panel, monkeypatch):
    """Rows become columns: the shape people paste from a plate reader."""
    from PyQt6.QtCore import QPoint

    frame = pd.DataFrame({"Condition": ["Contrôle", "Traité"],
                          "J1": [10.0, 20.0], "J2": [11.0, 22.0]})
    panel.datasets[0].df = frame
    panel.model.set_dataframe(frame)

    monkeypatch.setattr(QMenu, "exec", choose("Transposer"))
    panel._list_menu(QPoint(5, 5))

    turned = panel.model.dataframe()
    assert list(turned.columns) == ["Condition", "Contrôle", "Traité"]
    assert list(turned.iloc[:, 0]) == ["J1", "J2"]
    # Contrôle was measured at 10 on J1 and at 11 on J2
    assert turned["Contrôle"].tolist() == [10.0, 11.0]


def test_transposing_twice_comes_back(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    frame = pd.DataFrame({"Condition": ["Contrôle", "Traité"],
                          "J1": [10.0, 20.0], "J2": [11.0, 22.0]})
    panel.datasets[0].df = frame
    panel.model.set_dataframe(frame)

    monkeypatch.setattr(QMenu, "exec", choose("Transposer"))
    panel._list_menu(QPoint(5, 5))
    panel._list_menu(QPoint(5, 5))

    back = panel.model.dataframe()
    assert list(back.columns) == ["Condition", "J1", "J2"], (
        "le nom de la première colonne doit survivre à l'aller-retour")
    assert back.iloc[:, 0].tolist() == ["Contrôle", "Traité"]
    assert back["J1"].tolist() == [10.0, 20.0]


def test_inserting_a_column_from_the_header_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    monkeypatch.setattr(QMenu, "exec", choose("Insérer une colonne"))
    panel._header_menu(QPoint(5, 5))
    assert len(panel.model.dataframe().columns) == 3


def test_copy_and_paste_from_the_cell_menu(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    select(panel, [(2, 1)])
    monkeypatch.setattr(QMenu, "exec", choose("Copier"))
    panel._cell_menu(QPoint(5, 5))
    assert "30.0" in QApplication.clipboard().text()

    select(panel, [(1, 1)])
    monkeypatch.setattr(QMenu, "exec", choose("Coller"))
    panel._cell_menu(QPoint(5, 5))
    assert panel.model.dataframe().iat[1, 1] == 30.0


def test_deleting_a_table_when_another_remains(panel, monkeypatch):
    from PyQt6.QtCore import QPoint

    panel.datasets.append(Dataset("Seconde", pd.DataFrame({"x": [1.0]})))
    panel.set_datasets(panel.datasets, 0)

    monkeypatch.setattr(QMenu, "exec", choose("Supprimer"))
    panel._list_menu(QPoint(5, 5))
    assert [d.name for d in panel.datasets] == ["Seconde"]
