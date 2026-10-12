"""Renaming columns, renaming, copying and deleting tables, opening examples.

Each was a way for a plot to go wrong without a word: a renamed column
left the plot drawing nothing it was asked for; a deleted table sent its
plots to another table and could not be undone; two tables could share a
name; an example opened as whatever the plot was before - survival times as
bars. Each test fails on the old behaviour.
"""
import pandas as pd
import pytest
from matplotlib.figure import Figure
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox

from plotea.core import demo, plotting
from plotea.core.dataset import Dataset
from plotea.core.plotspec import PlotSpec


def choose(text):
    def pick(menu, *args):
        return next(a for a in menu.actions() if a.text() == text)
    return pick


def answer(monkeypatch, text):
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (text, True)))


@pytest.fixture
def demo_window(window):
    """The first screen: cell viability bars with their statistics."""
    window.files.start_new(with_example=True)
    QApplication.processEvents()
    window._render_now()
    window.history.clear()
    return window


def column_of(window, name):
    return list(window.data_panel.model.dataframe().columns).index(name)


def rename_column(window, old, new, monkeypatch):
    header = window.data_panel.table.horizontalHeader()
    monkeypatch.setattr(header, "logicalIndexAt",
                        lambda pos: column_of(window, old))
    monkeypatch.setattr(QMenu, "exec", choose("Renommer la colonne..."))
    answer(monkeypatch, new)
    window.data_panel._header_menu(QPoint(5, 5))
    window._commit_burst()
    window._render_now()


def comparisons(window):
    return [(c.a, c.b, round(c.p, 12))
            for c in window.canvas.last_info.comparisons]


# --------------------------------------------------------------------------
# A renamed column
# --------------------------------------------------------------------------
def test_a_renamed_column_is_followed(demo_window, monkeypatch):
    window = demo_window
    spec = window.current_spec()
    before = comparisons(window)
    assert len(before) == 6
    rename_column(window, "Viabilité", "Viabilité (% du témoin)",
                  monkeypatch)
    assert spec.y == ["Viabilité (% du témoin)"]
    assert comparisons(window) == before
    assert spec.ylabel == "Viabilité (%)"           # typed by hand: kept


def test_a_title_reading_the_column_name_follows_it(demo_window,
                                                    monkeypatch):
    window = demo_window
    spec = window.current_spec()
    spec.ylabel = "Viabilité"
    rename_column(window, "Viabilité", "Survie cellulaire", monkeypatch)
    assert spec.ylabel == "Survie cellulaire"
    rename_column(window, "Traitement", "Condition", monkeypatch)
    assert spec.group == "Condition"


def test_a_plot_on_another_table_follows_it_too(demo_window, monkeypatch):
    """A plot that showed the table before remembers it by the new name."""
    window = demo_window
    spec = window.current_spec()
    viability = spec.dataset
    window.new_plot()                       # a second plot, on viability
    other = window.current_spec()
    # ...moved to another table: it remembers viability
    window.load_example("Réponse au traitement (contingence)")
    assert other.dataset != viability and viability in other.per_table
    window.tabbar.setCurrentIndex(0)        # the first plot, on viability
    QApplication.processEvents()
    assert window.current_spec() is spec
    assert window.data_panel.current_dataset().name == viability
    rename_column(window, "Viabilité", "Viabilité (%)", monkeypatch)
    assert other.per_table[viability]["y"] == ["Viabilité (%)"]
    assert other.switch_table(viability) and other.y == ["Viabilité (%)"]


def test_a_name_already_taken_is_refused(demo_window, monkeypatch):
    window = demo_window
    said = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: said.append(a[-1])))
    rename_column(window, "Viabilité", "Traitement", monkeypatch)
    columns = list(window.data_panel.current_dataset().df.columns)
    assert columns.count("Traitement") == 1 and "Viabilité" in columns
    assert said and "Traitement" in said[0]
    model = window.data_panel.model
    assert not model.setHeaderData(0, Qt.Orientation.Horizontal, "   ")
    # refused by the table itself, whoever asks
    assert not model.setHeaderData(column_of(window, "Viabilité"),
                                   Qt.Orientation.Horizontal, "Traitement")
    assert list(model.dataframe().columns).count("Traitement") == 1


def test_renaming_a_column_is_undone_with_the_plot(demo_window,
                                                   monkeypatch):
    window = demo_window
    rename_column(window, "Viabilité", "V", monkeypatch)
    window.undo()
    assert "Viabilité" in window.data_panel.current_dataset().df.columns
    assert window.current_spec().y == ["Viabilité"]
    window.redo()
    assert window.current_spec().y == ["V"]


# --------------------------------------------------------------------------
# A column that is not there is said, on the plot itself
# --------------------------------------------------------------------------
def draw(spec, frame):
    figure = Figure(figsize=(3, 2.5))
    info = plotting.render(figure, spec, frame)
    return figure, info


FRAME = pd.DataFrame({"G": list("AABB"), "V": [1.0, 2.0, 3.0, 4.0],
                      "E": [0.1, 0.1, 0.2, 0.2]})


def test_a_missing_column_is_written_on_the_plot():
    figure, info = draw(PlotSpec(group="G", y=["Ancienne"]), FRAME)
    ax = figure.axes[0]
    assert not ax.axison and not ax.patches            # nothing half drawn
    assert any("Ancienne" in t.get_text() for t in ax.texts)
    assert any("Colonne introuvable" in w and "Ancienne" in w
               for w in info.warnings)


def test_a_missing_error_column_is_said_and_the_plot_drawn():
    figure, info = draw(PlotSpec(plot_type="line", x="V", y=["V"],
                                 error_cols=["SD"]), FRAME)
    assert figure.axes[0].lines
    assert any("SD" in w for w in info.warnings)


@pytest.mark.parametrize("spec, lost, unused", [
    (PlotSpec(group="G", y=["V"]), [], []),
    (PlotSpec(group="X", y=["V", "W"]), ["W", "X"], []),
    # survival draws no Y: a stale one is not looked for
    (PlotSpec(plot_type="survival", x="V", y=["Old"], event_col="Ev"),
     [], ["Ev"]),
    # a subject column matters only to a paired test
    (PlotSpec(group="G", y=["V"], stats_pair_by="Patient"), [], []),
    (PlotSpec(group="G", y=["V"], stats_pair_by="Patient",
              stats_enabled=True), [], ["Patient"]),
    (PlotSpec(group="G", subgroup="S", y=["V"]), ["S"], []),
    (PlotSpec(plot_type="line", x="T", y=["V"]), ["T"], []),
])
def test_which_missing_columns_matter(spec, lost, unused):
    found = plotting.missing_columns(spec, FRAME)
    assert sorted(found[0]) == sorted(lost) and found[1] == unused


# --------------------------------------------------------------------------
# Tables: renamed, copied, deleted - and undone
# --------------------------------------------------------------------------
def list_action(window, text, monkeypatch, row=None):
    if row is not None:
        window.data_panel.list.setCurrentRow(row)
        QApplication.processEvents()
    monkeypatch.setattr(QMenu, "exec", choose(text))
    window.data_panel._list_menu(QPoint(5, 5))
    QApplication.processEvents()
    window._render_now()


def test_two_tables_cannot_share_a_name(demo_window, monkeypatch):
    window = demo_window
    window.load_example("Réponse au traitement (contingence)")
    said = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: said.append(a[-1])))
    answer(monkeypatch, "Viabilité cellulaire")
    list_action(window, "Renommer la table...", monkeypatch, row=1)
    assert window.project.dataset_names() == ["Viabilité cellulaire",
                                              "Réponse au traitement"]
    assert said


def test_renaming_a_table_is_undone(demo_window, monkeypatch):
    window = demo_window
    spec = window.current_spec()
    answer(monkeypatch, "Manip 3")
    list_action(window, "Renommer la table...", monkeypatch)
    assert spec.dataset == "Manip 3"
    window.undo()
    assert window.project.dataset_names() == ["Viabilité cellulaire"]
    assert window.current_spec().dataset == "Viabilité cellulaire"
    assert "Viabilité cellulaire" in window.data_panel.list.item(0).text()


def test_a_copy_has_a_name_of_its_own_and_the_same_plot(demo_window,
                                                        monkeypatch):
    window = demo_window
    before = comparisons(window)
    for _ in range(2):
        list_action(window, "Dupliquer", monkeypatch, row=0)
    names = window.project.dataset_names()
    assert len(set(names)) == len(names) == 3
    spec = window.current_spec()
    assert spec.dataset == names[-1]
    assert (spec.plot_type, spec.y, spec.ylabel) == (
        "bar", ["Viabilité"], "Viabilité (%)")
    assert comparisons(window) == before
    window.undo()
    assert len(window.project.datasets) == 2


def test_deleting_a_table_moves_its_plots_and_says_so(demo_window,
                                                      monkeypatch):
    window = demo_window
    spec = window.current_spec()
    window.load_example("Réponse au traitement (contingence)")
    counts = spec.dataset
    list_action(window, "Supprimer", monkeypatch, row=1)

    assert window.project.dataset_names() == ["Viabilité cellulaire"]
    assert spec.dataset == "Viabilité cellulaire"
    assert counts not in spec.per_table
    # it comes back the way it was shown, not chosen again
    assert (spec.plot_type, spec.y) == ("bar", ["Viabilité"])
    message = window.statusBar().currentMessage()
    assert counts in message and spec.name in message

    window.undo()
    assert window.project.dataset_names() == ["Viabilité cellulaire",
                                              counts]
    spec = window.current_spec()
    assert spec.dataset == counts and spec.plot_type == "contingency"


def test_deleting_another_table_leaves_the_plot_alone(demo_window):
    window = demo_window
    window.project.add_dataset(Dataset("Brouillon", FRAME.copy()))
    window.data_panel.set_datasets(window.project.datasets, 0)
    spec = window.current_spec()
    window.delete_table("Brouillon")
    assert window.project.dataset_names() == ["Viabilité cellulaire"]
    assert window.data_panel.current_dataset().name == spec.dataset
    assert spec.dataset == "Viabilité cellulaire"
    assert spec.y == ["Viabilité"]


# --------------------------------------------------------------------------
# Examples open as the plot they were made for
# --------------------------------------------------------------------------
@pytest.mark.parametrize("label", list(demo.EXAMPLES))
def test_each_example_opens_as_its_plot(window, label):
    window.files.start_new()
    spec = window.current_spec()
    spec.plot_type, spec.fit_model, spec.subgroup = "box", "linear", "X"
    window.load_example(label)
    window._render_now()
    made = window.project.datasets[-1].meta["plot"]
    assert spec.plot_type == made["plot_type"]
    if "fit_model" not in made:
        assert spec.fit_model == "none"        # nothing of the plot before
    info = window.canvas.last_info
    assert not any("introuvable" in w for w in info.warnings), info.warnings
    assert not any("Erreur" in w for w in info.warnings), info.warnings


def test_the_survival_example_has_its_events(window):
    window.files.start_new()
    window.load_example("Essai de survie (Kaplan-Meier)")
    window._render_now()
    spec = window.current_spec()
    assert (spec.x, spec.group, spec.event_col) == (
        "Temps (mois)", "Bras", "Événement")
    info = window.canvas.last_info
    assert info.omnibus[0] == "Log-rank" and info.omnibus[2] < 0.05


def test_survival_columns_are_chosen_on_a_table_of_ones_own(window):
    frame = pd.DataFrame({"Bras": ["A"] * 4 + ["B"] * 4,
                          "Suivi (j)": [5.0, 8, 12, 20, 3, 4, 9, 11],
                          "Décès": [1, 0, 1, 1, 1, 1, 0, 1]})
    spec = PlotSpec(plot_type="survival")
    window._auto_map(spec, Dataset("Cohorte", frame))
    assert (spec.x, spec.event_col, spec.group) == ("Suivi (j)", "Décès",
                                                    "Bras")
    assert window._mapping_fits(spec, Dataset("Cohorte", frame), "survival")
