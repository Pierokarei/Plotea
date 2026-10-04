"""Moving a plot between tables, and editing the table on screen.

Two ways a figure went wrong without a word. Coming back to a table after
showing another one chose its columns again - the cell viability bars came
back as bars of replicate numbers, all equal, p = 1. And adding or removing
rows and columns changed the table on screen but not the dataset behind it:
a deleted column was still plotted, still saved, still counted; a cell edit
could not be undone. Each test fails on the old behaviour.
"""
import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu

from plotea.core.dataset import Dataset
from plotea.core.project import Project

VIABILITY = "Viabilité cellulaire (barres, stats)"
CONTINGENCY = "Réponse au traitement (contingence)"


def choose(text):
    def pick(menu, *args):
        return next(a for a in menu.actions() if a.text() == text)
    return pick


def select_table(window, name):
    names = window.project.dataset_names()
    window.data_panel.list.setCurrentRow(names.index(name))
    QApplication.processEvents()
    window._render_now()


def set_type(window, plot_type):
    window.current_spec().plot_type = plot_type
    window._on_plot_type_changed(plot_type)
    window._render_now()


def p_values(window):
    return [round(c.p, 12) for c in window.canvas.last_info.comparisons]


@pytest.fixture
def two_tables(window):
    """The demo bar chart, then a contingency table shown as contingency."""
    window.files.start_new(with_example=True)
    QApplication.processEvents()
    window._render_now()
    bars = window.current_spec().dataset
    window.load_example(CONTINGENCY)
    counts = window.current_spec().dataset
    set_type(window, "contingency")
    return window, bars, counts


# --------------------------------------------------------------------------
# Each table comes back as it was shown
# --------------------------------------------------------------------------
def test_coming_back_gives_the_same_bars(window):
    window.files.start_new(with_example=True)
    QApplication.processEvents()
    window._render_now()
    spec = window.current_spec()
    bars = spec.dataset
    before = (spec.plot_type, spec.y, spec.ylabel, spec.title,
              p_values(window))
    assert before[-1] and min(before[-1]) < 1e-6        # a real effect

    window.load_example(CONTINGENCY)
    set_type(window, "contingency")
    select_table(window, bars)

    after = (spec.plot_type, spec.y, spec.ylabel, spec.title,
             p_values(window))
    assert after == before


def test_each_table_keeps_its_own_plot_type(two_tables):
    window, bars, counts = two_tables
    spec = window.current_spec()
    for _ in range(2):
        select_table(window, bars)
        assert spec.plot_type == "bar"
        select_table(window, counts)
        assert spec.plot_type == "contingency"
        assert spec.y == ["Répondeurs", "Non-répondeurs"]
        assert window.canvas.last_info.contingency is not None
    # chosen from the inspector's table list, the same
    window._on_inspector_dataset(bars)
    assert spec.plot_type == "bar" and spec.y == ["Viabilité"]


def test_the_style_stays_with_the_plot(two_tables):
    """Theme and grid are the figure's: they follow it to every table."""
    window, bars, _counts = two_tables
    spec = window.current_spec()
    spec.theme, spec.grid_y = "Science", True
    select_table(window, bars)
    assert (spec.theme, spec.grid_y) == ("Science", True)


def test_settings_that_no_longer_fit_are_chosen_again(two_tables):
    """A column deleted while the plot was elsewhere is not looked for."""
    window, bars, _counts = two_tables
    table = window.project.get_dataset(bars)
    table.df = table.df.drop(columns=["Viabilité"])
    select_table(window, bars)
    spec = window.current_spec()
    assert spec.y and set(spec.y) <= set(table.df.columns)
    assert window.canvas.last_info.groups                   # it draws


def test_renaming_a_table_keeps_its_settings(two_tables, monkeypatch):
    window, bars, counts = two_tables
    select_table(window, bars)
    spec = window.current_spec()
    spec.ylabel = "Viabilité (% du contrôle)"
    monkeypatch.setattr(QMenu, "exec", choose("Renommer la table..."))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Manip 3", True)))
    window.data_panel._list_menu(QPoint(5, 5))
    QApplication.processEvents()

    assert spec.dataset == "Manip 3"
    assert spec.ylabel == "Viabilité (% du contrôle)"
    assert spec.y == ["Viabilité"]
    select_table(window, counts)
    select_table(window, "Manip 3")
    assert spec.plot_type == "bar"
    assert spec.ylabel == "Viabilité (% du contrôle)"


def test_what_each_table_was_shown_as_is_saved(two_tables, tmp_path):
    window, bars, counts = two_tables
    project = Project.load(window.project.save(str(tmp_path / "t.plotea")))
    spec = project.plots[0]
    assert spec.dataset == counts
    assert spec.per_table[bars]["plot_type"] == "bar"
    assert spec.switch_table(bars) and spec.plot_type == "bar"
    assert spec.y == ["Viabilité"]


# --------------------------------------------------------------------------
# Choosing columns for a table shown for the first time
# --------------------------------------------------------------------------
def test_a_replicate_number_is_not_what_gets_plotted(window):
    window.files.start_new()
    window.load_example(VIABILITY)
    spec = window.current_spec()
    assert spec.plot_type == "bar"
    assert spec.group == "Traitement" and spec.y == ["Viabilité"]


@pytest.mark.parametrize("values, numbering", [
    ([1, 2, 3, 1, 2, 3], True),           # replicate within each group
    ([0, 1, 2, 0, 1, 2], True),
    ([3, 1, 2, 2, 3, 1], True),           # in any order
    ([1, 2, 3, 4, 5, 3], False),          # a 1-5 score, not a numbering
    ([2, 3, 4, 2, 3, 4], False),
    ([1.0, 2.0, 2.5, 1.0, 2.0, 3.0], False),
])
def test_what_counts_as_a_numbering(window, values, numbering):
    ds = Dataset("T", pd.DataFrame({"G": list("AAABBB"), "N": values}))
    assert window._numbering(ds, "N", "G") is numbering


# --------------------------------------------------------------------------
# The table on screen is the dataset
# --------------------------------------------------------------------------
@pytest.fixture
def viability(window):
    window.files.start_new(with_example=True)
    QApplication.processEvents()
    window._render_now()
    return window, window.data_panel


def shown(panel):
    return panel.list.item(panel.list.currentRow()).text(), panel.info.text()


def test_a_column_added_then_removed_is_gone(viability):
    window, panel = viability
    ds = panel.current_dataset()
    panel.model.add_column()
    assert ds.df.shape == (48, 5)
    assert "(48x5)" in shown(panel)[0] and "5 colonnes" in shown(panel)[1]
    panel.model.remove_columns([4])
    assert ds.df.shape == (48, 4)
    assert "(48x4)" in shown(panel)[0] and "4 colonnes" in shown(panel)[1]
    window._render_now()
    assert "(48x4)" in shown(panel)[0]


def test_removed_columns_and_rows_leave_the_plot_and_the_file(viability,
                                                              tmp_path):
    window, panel = viability
    panel.model.remove_rows(list(range(12)))       # the whole control group
    window._render_now()
    assert "Contrôle" not in [str(g) for g in window.canvas.last_info.groups]
    project = Project.load(window.project.save(str(tmp_path / "v.plotea")))
    assert len(project.datasets[0].df) == 36


def test_added_rows_reach_the_dataset(viability):
    _window, panel = viability
    panel.model.add_rows(10)
    assert len(panel.current_dataset().df) == 58
    assert "(58x4)" in shown(panel)[0]


def test_a_cell_edit_can_be_undone(viability):
    window, panel = viability
    model = panel.model
    column = list(model.dataframe().columns).index("Viabilité")
    original = model.dataframe().iat[0, column]
    model.setData(model.index(0, column), "999", Qt.ItemDataRole.EditRole)
    window._commit_burst()
    window.undo()
    assert window.data_panel.current_dataset().df.iat[0, column] == original
    window.redo()
    assert window.data_panel.current_dataset().df.iat[0, column] == 999.0


def test_a_column_removal_can_be_undone(viability):
    window, panel = viability
    panel.model.remove_columns([3])
    window._commit_burst()
    assert panel.current_dataset().df.shape == (48, 3)
    window.undo()
    assert window.data_panel.current_dataset().df.shape == (48, 4)
    assert "(48x4)" in shown(window.data_panel)[0]


def test_history_survives_editing_a_restored_table(viability):
    """Undo then redo, edit: the step redone later still holds its value."""
    window, panel = viability
    column = list(panel.model.dataframe().columns).index("Viabilité")

    def edit(text):
        model = window.data_panel.model
        model.setData(model.index(0, column), text, Qt.ItemDataRole.EditRole)
        window._commit_burst()

    def value():
        return window.data_panel.current_dataset().df.iat[0, column]

    original = value()
    edit("999")
    window.undo()
    window.redo()
    edit("555")
    window.undo()
    assert value() == 999.0
    window.undo()
    assert value() == original
    window.redo()
    assert value() == 999.0, "l'édition suivante a réécrit l'historique"


def test_pasting_reaches_the_dataset(viability):
    _window, panel = viability
    panel.model.add_column("Texte")
    ds = panel.current_dataset()
    column = ds.df.shape[1] - 1
    from PyQt6.QtCore import QItemSelectionModel
    panel.table.selectionModel().select(
        panel.model.index(47, column),
        QItemSelectionModel.SelectionFlag.ClearAndSelect)
    QApplication.clipboard().setText("1,5\n2,5\n3,5")
    panel.paste_clipboard()
    assert len(ds.df) == 50 and ds.df.iat[49, column] == 3.5
    assert "(50x5)" in shown(panel)[0]
    assert np.isnan(ds.df.iat[0, column])
