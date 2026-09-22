"""The rendering engine, without Qt: every plot type, theme, fit and format."""
import os

import pytest
from matplotlib.figure import Figure

from plotea.core import demo, export, fitting, plotting, stats
from plotea.core.plotspec import PlotSpec
from plotea.core.project import Project
from plotea.core.themes import THEMES, get_theme

DATA = {
    "viability": demo.viability(),
    "growth": demo.growth(),
    "expression": demo.expression(),
    "correlation": demo.correlation(),
    "dose": demo.dose_response(),
    "two_factor": demo.two_factor(),
}


def render(spec: PlotSpec, table, out_dir: str, filename: str | None = None):
    theme = get_theme(spec.theme)
    fig = Figure(figsize=theme.figsize(spec.span), dpi=150)
    info = plotting.render(fig, spec, table.df)
    if filename:
        fig.savefig(os.path.join(out_dir, filename), bbox_inches="tight",
                    pad_inches=0.02)
    return info


# --------------------------------------------------------------------------
# Plot types
# --------------------------------------------------------------------------
PLOTS = {
    "bar": (PlotSpec(plot_type="bar", group="Traitement", y=["Viabilité"],
                     theme="Nature", ylabel="Viabilite (%)",
                     stats_enabled=True, show_points=True, title="Viabilité"),
            "viability"),
    "box": (PlotSpec(plot_type="box", group="Traitement", y=["Viabilité"],
                     theme="Science", stats_enabled=True), "viability"),
    "violin": (PlotSpec(plot_type="violin",
                        y=["Sain", "Tumeur", "Métastase"], theme="Cell",
                        violin_inner="Boxplot", show_points=False,
                        stats_enabled=True), "expression"),
    "histogram": (PlotSpec(plot_type="histogram", y=["Sain", "Tumeur"],
                           theme="PNAS", hist_kde=True, bins_auto=False,
                           bins=30, alpha=0.6), "expression"),
    "line": (PlotSpec(plot_type="line", x="Temps (h)",
                      y=["WT", "KO", "KO + rescue"],
                      error_cols=["WT SD", "KO SD", "KO + rescue SD"],
                      theme="Nature", error_band=True), "growth"),
    "scatter": (PlotSpec(plot_type="scatter", x="Biomarqueur (ng/mL)",
                         y=["Score clinique"], group="Cohorte",
                         theme="Minimal", fit_model="Lineaire",
                         fit_ci=True), "correlation"),
    "dose_response": (PlotSpec(plot_type="scatter", x="log[C] (M)",
                               y=["Réponse (%)"], group="Composé",
                               theme="Nature", fit_model="Dose-reponse log"),
                      "dose"),
    "grouped_bars": (PlotSpec(plot_type="bar", group="Temps",
                              subgroup="Génotype", y=["Activité"],
                              theme="Cell", error_type="SD",
                              show_points=False), "two_factor"),
    "horizontal_bars": (PlotSpec(plot_type="bar", group="Traitement",
                                 y=["Viabilité"], horizontal=True,
                                 theme="Grayscale", monochrome_hatch=True,
                                 show_points=False), "viability"),
}


@pytest.mark.parametrize("name", list(PLOTS))
def test_plot_type_renders(name, out_dir):
    spec, table = PLOTS[name]
    info = render(spec, DATA[table], out_dir, f"{name}.png")
    assert not info.warnings, info.warnings


@pytest.mark.parametrize("theme", list(THEMES))
def test_every_theme_renders(theme, out_dir):
    spec = PlotSpec(plot_type="bar", group="Traitement", y=["Viabilité"],
                    theme=theme, stats_enabled=True, title=theme)
    info = render(spec, DATA["viability"], out_dir, f"theme_{theme}.png")
    assert not info.warnings, info.warnings
    assert len(info.comparisons) == 6


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def groups():
    return plotting.extract_groups(
        DATA["viability"].df,
        PlotSpec(group="Traitement", y=["Viabilité"]))


def test_pairwise_holm(groups):
    comps = stats.pairwise(groups, "auto", "holm")
    assert len(comps) == 6
    assert all(c.p_adj >= c.p for c in comps)
    assert all(c.p_adj < 0.05 for c in comps)


def test_omnibus(groups):
    name, stat, p = stats.omnibus(groups)
    assert name == "ANOVA à un facteur"
    assert p < 1e-10 and stat > 0


def test_tukey(groups):
    comps = stats.pairwise(groups, "anova_tukey", "none")
    assert len(comps) == 6
    assert all(c.test == "Tukey HSD" for c in comps)


def test_describe(groups):
    rows = stats.describe(groups)
    assert len(rows) == 4
    assert all(row["n"] == 12 for row in rows)
    assert {"Moyenne", "SD", "SEM", "IC95 bas"} <= set(rows[0])


# --------------------------------------------------------------------------
# Fitting
# --------------------------------------------------------------------------
@pytest.mark.parametrize("model", [
    "linear", "poly2", "poly3", "exp_growth", "exp_decay", "log", "power",
    "michaelis", "gaussian", "sigmoid",
])
def test_fit_converges(model):
    table = DATA["correlation"].df
    result = fitting.fit(table["Biomarqueur (ng/mL)"].values,
                         table["Score clinique"].values, model)
    assert result is not None
    if result.ok:
        assert result.n > 0


def test_four_parameter_logistic():
    table = DATA["dose"].df
    result = fitting.fit(table["log[C] (M)"].values,
                         table["Réponse (%)"].values, "hill4_log")
    assert result.ok and result.r2 > 0.85
    assert "EC50" in result.extra


def test_linear_fit_is_exact():
    import numpy as np
    x = np.linspace(0, 10, 25)
    result = fitting.fit(x, 3.0 * x - 7.0, "linear")
    assert abs(result.params["a"] - 3.0) < 1e-9
    assert abs(result.params["b"] + 7.0) < 1e-9
    assert result.r2 > 0.999999


# --------------------------------------------------------------------------
# Export and projects
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def rendered_figure():
    theme = get_theme("Nature")
    fig = Figure(figsize=theme.figsize("single"))
    plotting.render(fig, PlotSpec(plot_type="bar", group="Traitement",
                                  y=["Viabilité"], stats_enabled=True),
                    DATA["viability"].df)
    return fig


@pytest.mark.parametrize("fmt", list(export.FORMATS))
def test_export_format(fmt, rendered_figure, out_dir):
    path = export.save_figure(
        rendered_figure,
        export.ExportOptions(os.path.join(out_dir, "export"), fmt, dpi=600))
    assert os.path.getsize(path) > 1000


def test_project_round_trip(out_dir):
    project = Project("Demo", [DATA["viability"], DATA["growth"]],
                      [PlotSpec(name="G1", plot_type="bar")])
    path = project.save(os.path.join(out_dir, "demo.plotea"))
    back = Project.load(path)
    assert back.name == "Demo"
    assert len(back.datasets) == 2 and len(back.plots) == 1
    assert back.plots[0].name == "G1"
    assert list(back.datasets[0].df.columns) == \
        list(DATA["viability"].df.columns)
