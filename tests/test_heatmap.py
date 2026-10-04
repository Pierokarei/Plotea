"""Heat maps: the matrix shown is the matrix asked for.

Each transformation is checked against its definition, computed apart: a
z-scored row has mean 0 and SD 1, the correlation matrix is pandas' own,
and clustering puts genes that answer the treatment the same way side by
side - which is the reason anyone clusters a heat map.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea.core import demo, plotting
from plotea.core.methods import methods_text
from plotea.core.plotspec import PlotSpec

EXPR = demo.heatmap().df
SAMPLES = [c for c in EXPR.columns if c != "Gène"]
UP = {"IL6", "CXCL8", "TNF", "CCL2"}
DOWN = {"PPARG", "ADIPOQ", "LPL", "FABP4"}


def spec(**fields):
    fields = {"plot_type": "heatmap", "group": "Gène", "y": SAMPLES,
              **fields}
    return PlotSpec(**fields)


def matrix(df=EXPR, **fields):
    return plotting.heat_matrix(df, spec(**fields))


def render(df=EXPR, **fields):
    figure = Figure()
    the_spec = spec(**fields)
    info = plotting.render(figure, the_spec, df)
    return figure, info, the_spec


# --------------------------------------------------------------------------
# The matrix
# --------------------------------------------------------------------------
def test_the_raw_matrix_is_the_table():
    values, rows, cols, problem = matrix()
    assert not problem
    assert rows == list(EXPR["Gène"]) and cols == SAMPLES
    assert np.allclose(values, EXPR[SAMPLES].to_numpy())


def test_each_row_scaled_to_mean_0_and_sd_1():
    values, _rows, _cols, _ = matrix(heat_values="z_rows")
    assert np.allclose(values.mean(axis=1), 0)
    assert np.allclose(values.std(axis=1, ddof=1), 1)


def test_each_column_scaled_to_mean_0_and_sd_1():
    values, _rows, _cols, _ = matrix(heat_values="z_columns")
    assert np.allclose(values.mean(axis=0), 0)
    assert np.allclose(values.std(axis=0, ddof=1), 1)


def test_a_row_that_never_varies_stays_at_zero():
    flat = pd.DataFrame({"Gène": ["A", "B"], "x": [5.0, 1.0],
                         "y": [5.0, 2.0], "z": [5.0, 3.0]})
    values, *_ = matrix(flat, y=["x", "y", "z"], heat_values="z_rows")
    assert np.allclose(values[0], 0)


def test_the_correlation_matrix_is_pearsons():
    values, rows, cols, _ = matrix(heat_values="correlation")
    assert rows == cols == SAMPLES
    assert np.allclose(values, EXPR[SAMPLES].corr().to_numpy())


def test_long_format_is_pivoted_with_the_mean_of_duplicates():
    long = pd.DataFrame({"Gène": ["A", "A", "A", "B"],
                         "Échantillon": ["s1", "s1", "s2", "s1"],
                         "Valeur": [1.0, 3.0, 5.0, 7.0]})
    values, rows, cols, _ = plotting.heat_matrix(long, PlotSpec(
        plot_type="heatmap", group="Gène", subgroup="Échantillon",
        y=["Valeur"]))
    assert rows == ["A", "B"] and cols == ["s1", "s2"]
    assert values[0].tolist() == [2.0, 5.0]          # (1 + 3) / 2
    assert values[1, 0] == 7.0 and np.isnan(values[1, 1])


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------
def test_clustering_puts_genes_that_answer_alike_together():
    _values, rows, _cols, _ = matrix(heat_values="z_rows",
                                     heat_cluster="rows")
    positions = {gene: i for i, gene in enumerate(rows)}
    for block in (UP, DOWN):
        places = sorted(positions[g] for g in block)
        assert places[-1] - places[0] == len(block) - 1, rows   # contiguous


def test_clustering_columns_separates_controls_from_treated():
    # interleaved, so that only the clustering can sort them out
    mixed = [SAMPLES[i] for i in (0, 3, 1, 4, 2, 5)]
    _values, _rows, cols, _ = matrix(y=mixed, heat_values="z_rows",
                                     heat_cluster="columns")
    halves = [{c.split()[0] for c in cols[:3]}, {c.split()[0]
                                                  for c in cols[3:]}]
    assert sorted(map(sorted, halves)) == [["Contrôle"], ["Traité"]]


def test_a_correlation_matrix_keeps_one_order_for_both_axes():
    values, rows, cols, _ = matrix(heat_values="correlation",
                                   heat_cluster="rows")
    assert rows == cols
    assert np.allclose(values, values.T)
    assert np.allclose(np.diag(values), 1)


# --------------------------------------------------------------------------
# The drawing
# --------------------------------------------------------------------------
def test_centred_values_get_a_diverging_scale_centred_on_zero():
    figure, _info, _ = render(heat_values="z_rows")
    image = figure.axes[0].images[0]
    assert image.get_cmap().name.startswith("RdBu")
    assert image.norm.vmin == pytest.approx(-image.norm.vmax)
    figure, _info, _ = render()
    assert figure.axes[0].images[0].get_cmap().name.startswith("viridis")


def test_the_colour_bar_names_what_it_measures():
    labels = {mode: render(heat_values=mode)[0].axes[1].get_ylabel()
              for mode in ("values", "z_rows", "correlation")}
    assert labels == {"values": "Valeur", "z_rows": "Score z",
                      "correlation": "r de Pearson"}


def test_values_written_in_the_cells_stay_readable():
    figure, _info, _ = render(heat_values="correlation", heat_annotate=True)
    texts = figure.axes[0].texts
    assert len(texts) == len(SAMPLES) ** 2
    assert {t.get_text() for t in texts} >= {"1.00"}
    # white on the darkest cells, black on the lightest
    colours = {t.get_color() for t in texts}
    assert colours == {"white", "black"}


def test_missing_cells_are_grey_not_a_colour_of_the_scale():
    holed = EXPR.copy()
    holed.loc[0, SAMPLES[0]] = np.nan
    figure, _info, _ = render(holed)
    image = figure.axes[0].images[0]
    assert image.get_array().mask[0, 0]
    assert image.get_cmap().get_bad()[:3] == pytest.approx(
        (0xD9 / 255,) * 3)


def test_nothing_to_show_says_what_to_choose():
    _figure, info, _ = render(y=[])
    assert any("Valeurs Y" in w for w in info.warnings)
    _figure, info, _ = render(y=SAMPLES[:1], heat_values="correlation")
    assert any("deux colonnes" in w for w in info.warnings)


def test_the_methods_paragraph():
    _figure, info, the_spec = render(heat_values="z_rows",
                                     heat_cluster="both")
    text = methods_text(the_spec, info, "en")
    assert "12 rows by 6 columns, each row standardised" in text
    assert "Rows and columns were ordered by hierarchical clustering" in text
    assert "centrée et réduite" in methods_text(the_spec, info, "fr")


def test_the_settings_survive_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(spec(name="Chaleur", heat_values="correlation",
                          heat_cmap="magma", heat_cluster="both",
                          heat_annotate=True))
    saved = Project.load(project.save(str(tmp_path / "h.plotea"))).plots[-1]
    assert (saved.plot_type, saved.heat_values, saved.heat_cmap,
            saved.heat_cluster, saved.heat_annotate) == \
        ("heatmap", "correlation", "magma", "both", True)


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_window_maps_the_expression_table(window):
    window.load_example("Expression de gènes (carte de chaleur)")
    for button in window.inspector.type_buttons.buttons():
        if button.property("plot_type") == "heatmap":
            button.click()
    the_spec = window.current_spec()
    assert the_spec.group == "Gène" and the_spec.y == SAMPLES
    inspector = window.inspector
    assert not inspector.cmb_heat_values.isHidden()
    assert not inspector.sec_stats.isVisible()
    window._render_now()
    assert window.canvas.last_info.heatmap["rows"] == 12
