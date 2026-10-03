"""GraphPad Prism import: real Prism files, checked against a reference reader.

The files in tests/data/prism were written by Prism and come with the tables
the R package "pzfx" extracts from them (.tab). The values must agree with
those; the layout is Plotea's own - one row per replicate, long format for
grouped and survival tables - so each check rebuilds the reference view
from it. Every plot the import proposes must also render without a warning:
a plot that opens onto an error would be worse than no plot.
"""
import os

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea import i18n
from plotea.core import plotting
from plotea.core.plotspec import PlotSpec
from plotea.core.pzfx import PzfxError, read_pzfx

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "prism")


def prism(name):
    return read_pzfx(os.path.join(DATA, name))


def only(name):
    result = prism(name)
    assert len(result.tables) == 1, result.tables
    return result.tables[0]


def reference(name):
    return pd.read_csv(os.path.join(DATA, name), sep="\t",
                       na_values=["NA"], keep_default_na=False)


def same(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    assert a.shape == b.shape, (a, b)
    assert np.allclose(a, b, equal_nan=True), (a, b)


def renders(table):
    figure = Figure()
    spec = PlotSpec(dataset=table.dataset.name, **table.plot)
    info = plotting.render(figure, spec, table.dataset.df)
    assert not info.warnings, info.warnings
    axes = figure.axes[0]
    assert axes.lines or axes.patches or axes.collections
    return info


# --------------------------------------------------------------------------
# Values, against the reference reader
# --------------------------------------------------------------------------
def test_xy_replicates_become_rows():
    """Plotea averages rows sharing an X: replicate k is block k."""
    table = only("x_y_rep.pzfx")
    df, ref = table.dataset.df, reference("x_y_rep.tab")
    n = len(ref)
    for title in ("Ya", "Yb", "Yc"):
        same(df[title][:n], ref[f"{title}_1"])
        same(df[title][n:2 * n], ref[f"{title}_2"])
    same(df["XX"][:n], ref["XX"])
    assert table.plot == {"plot_type": "line", "x": "XX", "xlabel": "XX",
                          "y": ["Ya", "Yb", "Yc"]}


def test_values_excluded_in_prism_are_left_out_and_counted():
    result = prism("x_y_with_strike.pzfx")
    df = result.tables[0].dataset.df
    ref = reference("x_y_with_strike_excluded.tab")
    n = len(ref)
    for title in ("Ya", "Yb", "Yc"):
        same(df[title][:n], ref[f"{title}_1"])
        same(df[title][n:2 * n], ref[f"{title}_2"])
    assert any("3 valeur(s) exclue(s)" in note for note in result.notes), \
        result.notes


def test_mean_sd_n_columns():
    table = only("column_sdn.pzfx")
    df, ref = table.dataset.df, reference("column_sdn.tab")
    for title in ("A", "B"):
        same(df[title], ref[f"{title}_MEAN"])
        same(df[f"{title} SD"], ref[f"{title}_SD"])
        same(df[f"{title} N"], ref[f"{title}_N"])


def test_x_error_and_y_summary_make_a_curve_with_error_bars():
    table = only("x_error_y_sdn.pzfx")
    df, ref = table.dataset.df, reference("x_error_y_sdn.tab")
    same(df["XX"], ref["XX_X"])
    same(df["XX erreur"], ref["XX_ERROR"])
    for title in ("Ya", "Yb"):
        same(df[title], ref[f"{title}_MEAN"])
        same(df[f"{title} SD"], ref[f"{title}_SD"])
    assert table.plot["y"] == ["Ya", "Yb"]
    assert table.plot["error_cols"] == ["Ya SD", "Yb SD"]
    renders(table)


def test_survival_becomes_time_group_event():
    table = only("survival.pzfx")
    df, ref = table.dataset.df, reference("survival.tab")
    ref.columns = [c.strip() for c in ref.columns]
    for group in ("Control", "Treatment A", "Treatment B"):
        expected = ref[ref[group].notna()]
        mine = df[df["Groupe"] == group]
        same(mine["Days"], expected["Days"])
        same(mine["Événement"], expected[group])
        assert list(mine["Sujet"]) == list(expected["ROWTITLE"])
    assert table.plot == {"plot_type": "survival", "x": "Days",
                          "group": "Groupe", "event_col": "Événement",
                          "xlabel": "Days", "stats_enabled": True}
    info = renders(table)
    assert info.series == ["Control", "Treatment A", "Treatment B"]
    assert info.omnibus and info.omnibus[0] == "Log-rank"


def test_column_table_is_wide():
    table = only("column.pzfx")
    same(table.dataset.df["Aa"], [1, 2, 3, 4])
    same(table.dataset.df["Bb"], [100, 90, 80, 70])
    assert table.plot["plot_type"] == "bar"
    assert table.plot["y"] == ["Aa", "Bb"]
    renders(table)


def test_columns_of_unequal_length_and_empty_ones():
    df = only("column_unequal_lengths.pzfx").dataset.df
    same(df["A"], [1, 2, np.nan])
    same(df["B"], [10, 20, 30])
    df = only("column_empty.pzfx").dataset.df
    assert df["B"].isna().all()
    same(df["C"], [3, 2, 1])


def test_comma_decimal():
    """Prism on a French system writes "3,5"."""
    same(only("comma_decimal.pzfx").dataset.df["CommaDecimal"], [3.5])


def test_huge_tables_are_read_like_tables():
    table = only("column_hugetable.pzfx")
    df = table.dataset.df
    assert len(df) == 3 * 53
    assert set(df["Ligne"]) == {"Ligne 1", "Ligne 2", "Ligne 3"}
    renders(table)


def test_dates_keep_both_the_elapsed_time_and_the_date():
    table = only("x_date.pzfx")
    df = table.dataset.df
    assert df["Date X (date)"].iloc[0] == "16-Jan-2004"
    assert df["Date X"].iloc[0] == 0
    assert table.plot["x"] == "Date X"         # numbers, so the curve draws
    renders(table)


def test_the_example_shipped_with_prism():
    table = only("exponential_decay.pzfx")
    assert table.dataset.name == "Exponential decay"
    renders(table)


# --------------------------------------------------------------------------
# Tables Plotea cannot plot yet, and files it cannot read
# --------------------------------------------------------------------------
def test_unplotted_tables_are_imported_and_said_so():
    name, kind = "parts_of_whole.pzfx", "parties d'un tout"
    result = prism(name)
    table = result.tables[0]
    assert table.plot == {}
    assert not table.dataset.df.empty
    assert any(kind in note for note in result.notes), result.notes


def test_contingency_counts_with_their_row_titles():
    table = only("contingency.pzfx")
    df = table.dataset.df
    assert list(df["Ligne"]) == ["a", "b"]
    same(df["A"], [10, 20])
    same(df["B"], [30, 40])
    # Prism tests every contingency table; so does the plot made from it
    assert table.plot == {"plot_type": "contingency", "group": "Ligne",
                          "y": ["A", "B"], "xlabel": "",
                          "stats_enabled": True}
    info = renders(table)
    assert info.omnibus[0] == "Test exact de Fisher"


def test_summaries_outside_curves_are_imported_without_a_plot():
    result = prism("column_sdn.pzfx")
    assert result.tables[0].plot == {}
    assert any("moyennes et des écarts" in n for n in result.notes)


def test_an_empty_file_says_so():
    result = prism("empty.pzfx")
    assert result.tables == []
    assert any("vide" in note for note in result.notes)


def test_a_prism_10_file_explains_what_to_do(tmp_path):
    path = tmp_path / "manip.prism"
    path.write_bytes(b"PK\x03\x04")
    with pytest.raises(PzfxError, match=r"\.pzfx"):
        read_pzfx(str(path))


@pytest.mark.parametrize("content", [
    b"Traitement;Viabilite\nA;1\n",                       # a CSV, renamed
    b"<?xml version='1.0'?><other/>",                      # some other XML
    b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'b'>]>"
    b"<GraphPadPrismFile/>",                               # entity tricks
])
def test_what_is_not_a_prism_file_is_refused_clearly(tmp_path, content):
    path = tmp_path / "faux.pzfx"
    path.write_bytes(content)
    with pytest.raises(PzfxError):
        read_pzfx(str(path))


# --------------------------------------------------------------------------
# What the samples do not show, built the way Prism writes it
# --------------------------------------------------------------------------
GROUPED = """<?xml version="1.0" encoding="UTF-8"?>
<GraphPadPrismFile xmlns="http://graphpad.com/prism/Prism.htm"
                   PrismXMLVersion="5.00">
<TableSequence><Ref ID="Table0"/></TableSequence>
<Table ID="Table0" XFormat="none" YFormat="replicates" Replicates="2"
       TableType="TwoWay">
<Title><B>Activité</B> enzymatique</Title>
<RowTitlesColumn><Subcolumn><d>0 h</d><d>6 h</d></Subcolumn></RowTitlesColumn>
<YColumn Subcolumns="2"><Title>WT</Title>
<Subcolumn><d>1</d><d>3</d></Subcolumn>
<Subcolumn><d>2</d><d Excluded="1">40</d></Subcolumn></YColumn>
<YColumn Subcolumns="2"><Title>KO</Title>
<Subcolumn><d>5</d><d>7</d></Subcolumn>
<Subcolumn><d>6</d><d>8</d></Subcolumn></YColumn>
</Table>
</GraphPadPrismFile>
"""


def test_a_grouped_table_with_row_titles(tmp_path):
    """Rows x columns -> long format, drawn as grouped bars."""
    path = tmp_path / "groupes.pzfx"
    path.write_text(GROUPED, encoding="utf-8")
    result = read_pzfx(str(path))
    table = result.tables[0]
    # a namespace, and a title wrapped in formatting tags
    assert table.dataset.name == "Activité enzymatique"
    df = table.dataset.df
    assert list(df.columns) == ["Ligne", "Groupe", "Valeur"]
    wt_6h = df[(df["Ligne"] == "6 h") & (df["Groupe"] == "WT")]["Valeur"]
    same(wt_6h, [3])                       # 40 was excluded in Prism
    assert table.plot["group"] == "Ligne"
    assert table.plot["subgroup"] == "Groupe"
    assert any("1 valeur(s) exclue(s)" in n for n in result.notes)
    renders(table)


def test_column_names_follow_the_interface_language(tmp_path):
    path = tmp_path / "groupes.pzfx"
    path.write_text(GROUPED, encoding="utf-8")
    i18n.set_language("en")
    try:
        table = read_pzfx(str(path)).tables[0]
        survival = only("survival.pzfx")
    finally:
        i18n.set_language("fr")
    assert list(table.dataset.df.columns) == ["Row", "Group", "Value"]
    assert table.plot["subgroup"] == "Group"
    assert survival.plot["event_col"] == "Event"
    renders(survival)


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
@pytest.fixture
def quiet(monkeypatch):
    """Record the message boxes instead of showing them."""
    from PyQt6.QtWidgets import QMessageBox

    said = []
    for kind in ("information", "warning"):
        monkeypatch.setattr(
            QMessageBox, kind,
            staticmethod(lambda parent, title, text, *a, **k:
                         said.append(text)))
    return said


def test_the_window_imports_every_table_with_its_plot(window, quiet):
    plots_before = len(window.project.plots)
    tables_before = len(window.project.datasets)
    assert window.import_prism(os.path.join(DATA, "survival.pzfx"))
    assert len(window.project.datasets) == tables_before + 1
    assert len(window.project.plots) == plots_before + 1
    spec = window.current_spec()
    assert spec.name == "Three groups" and spec.plot_type == "survival"
    window._render_now()
    assert not window.canvas.last_info.warnings
    assert "1 tableau(x) importé(s)" in quiet[-1]
    assert "Les graphiques et analyses de Prism" in quiet[-1]

    window.undo()
    assert len(window.project.plots) == plots_before
    assert len(window.project.datasets) == tables_before


def test_a_table_without_a_plot_adds_data_only(window, quiet):
    plots_before = len(window.project.plots)
    assert window.import_prism(os.path.join(DATA, "parts_of_whole.pzfx"))
    assert len(window.project.plots) == plots_before
    assert "0 graphique(s) créé(s)" in quiet[-1]


def test_an_unreadable_file_changes_nothing(window, quiet, tmp_path):
    path = tmp_path / "faux.pzfx"
    path.write_text("pas du XML", encoding="utf-8")
    before = (len(window.project.datasets), len(window.project.plots))
    assert not window.import_prism(str(path))
    assert (len(window.project.datasets), len(window.project.plots)) == before
    assert "pas un fichier Prism" in quiet[-1]


def test_the_import_menu_sends_prism_files_here(window, monkeypatch, quiet):
    from PyQt6.QtWidgets import QFileDialog

    path = os.path.join(DATA, "column.pzfx")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (path, "")))
    called = []
    monkeypatch.setattr(type(window), "import_prism",
                        lambda self, p: called.append(p))
    window.import_data()
    assert called == [path]
