"""Multi-panel figures: layout, lettering, persistence and the UI wiring."""
import os

from matplotlib.figure import Figure


from PyQt6.QtWidgets import QApplication

app = QApplication.instance()

from plotea.core import demo  # noqa: E402
from plotea.core.panel import Panel, letter_for, render_panel  # noqa: E402
from plotea.core.plotspec import PlotSpec  # noqa: E402
from plotea.core.project import Project  # noqa: E402
from plotea.ui.main_window import MainWindow  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)


viab = demo.viability()
dose = demo.dose_response()
expr = demo.expression()
growth = demo.growth()

specs = {
    "Barres": PlotSpec(name="Barres", plot_type="bar", dataset=viab.name,
                       group="Traitement", y=["Viabilité"], theme="Nature",
                       ylabel="Viabilite (%)", stats_enabled=True),
    "Dose": PlotSpec(name="Dose", plot_type="scatter", dataset=dose.name,
                     x="log[C] (M)", y=["Réponse (%)"], group="Composé",
                     theme="Nature", fit_model="Dose-reponse log",
                     xlabel="log [C] (M)", ylabel="Réponse (%)"),
    "Violons": PlotSpec(name="Violons", plot_type="violin", dataset=expr.name,
                        y=["Sain", "Tumeur", "Métastase"], theme="Nature",
                        ylabel="Expression (UA)", show_points=False),
    "Croissance": PlotSpec(name="Croissance", plot_type="line",
                           dataset=growth.name, x="Temps (h)",
                           y=["WT", "KO"], theme="Nature",
                           xlabel="Temps (h)", ylabel="DO 600"),
}
frames = {viab.name: viab.df, dose.name: dose.df, expr.name: expr.df,
          growth.name: growth.df}


def test_four_panels():
    panel = Panel(name="Figure 1", plots=list(specs), cols=2, span="double",
                  height_mm=120.0)
    fig = Figure(figsize=(7.2, 4.7))
    info = render_panel(fig, panel, specs, frames)
    assert info.drawn == 4, info.drawn
    assert not info.missing, info.missing
    assert len(fig.axes) == 4, len(fig.axes)
    fig.savefig(os.path.join(OUT, "panel_2x2.png"), dpi=200,
                bbox_inches="tight")


def test_letters_follow_order():
    panel = Panel(plots=["Dose", "Barres", "Violons"], cols=3)
    fig = Figure(figsize=(7.2, 2.6))
    render_panel(fig, panel, specs, frames)
    titles = [ax.get_title(loc="left") for ax in fig.axes]
    assert titles == ["A", "B", "C"], titles

    panel.letters = "(a), (b), (c)"
    fig = Figure(figsize=(7.2, 2.6))
    render_panel(fig, panel, specs, frames)
    assert [ax.get_title(loc="left") for ax in fig.axes] == ["(a)", "(b)",
                                                             "(c)"]

    panel.letters = "Aucune"
    fig = Figure(figsize=(7.2, 2.6))
    render_panel(fig, panel, specs, frames)
    assert [ax.get_title(loc="left") for ax in fig.axes] == ["", "", ""]


def test_letter_helper():
    assert letter_for(0, "A, B, C") == "A"
    assert letter_for(2, "a, b, c") == "c"
    assert letter_for(1, "(a), (b), (c)") == "(b)"


def test_grid_is_deduced():
    panel = Panel(plots=list(specs), cols=3, rows=0)
    assert panel.grid(4) == (2, 3), panel.grid(4)
    panel.rows = 4
    assert panel.grid(4) == (4, 3)


def test_sub_plots_keep_their_own_theme():
    mixed = dict(specs)
    mixed["Dose"] = PlotSpec.from_dict(specs["Dose"].to_dict())
    mixed["Dose"].theme = "Science"
    panel = Panel(plots=["Barres", "Dose"], cols=2)
    fig = Figure(figsize=(7.2, 2.8))
    info = render_panel(fig, panel, mixed, frames)
    assert info.drawn == 2
    sizes = [ax.xaxis.label.get_fontsize() for ax in fig.axes]
    assert sizes[0] != sizes[1], sizes   # Nature 7 pt vs Science 8 pt


def test_missing_plot_is_reported():
    panel = Panel(plots=["Barres", "Disparu"], cols=2)
    fig = Figure(figsize=(7.2, 2.8))
    info = render_panel(fig, panel, specs, frames)
    assert info.drawn == 1
    assert info.missing == ["Disparu"], info.missing
    assert any("introuvable" in w for w in info.warnings)


def test_empty_panel_is_explicit():
    fig = Figure(figsize=(4, 3))
    info = render_panel(fig, Panel(plots=[]), specs, frames)
    assert info.drawn == 0
    assert len(fig.axes) == 1


def test_panels_survive_save_and_load():
    project = Project("Composite", [viab, dose], list(specs.values()))
    project.add_panel(Panel(name="Figure 1", plots=["Barres", "Dose"],
                            cols=2, letters="a, b, c", letter_size=11.0))
    path = project.save(os.path.join(OUT, "panels.plotea"))
    back = Project.load(path)
    assert len(back.panels) == 1, back.panels
    panel = back.panels[0]
    assert panel.plots == ["Barres", "Dose"]
    assert panel.letters == "lower" and panel.letter_size == 11.0


def test_deleting_a_plot_cleans_panels():
    project = Project("X", [viab], list(specs.values()))
    project.add_panel(Panel(plots=["Barres", "Dose"]))
    project.remove_plot(0)          # removes "Barres"
    assert project.panels[0].plots == ["Dose"], project.panels[0].plots


win = MainWindow()
win.show()
app.processEvents()
win._render_now()


def test_panel_tab_workflow():
    win.new_plot()
    plots_before = len(win.project.plots)
    win.new_panel()
    assert len(win.project.panels) == 1
    assert win.tabbar.count() == plots_before + 1
    assert win.current_panel() is not None
    assert win.current_spec() is None
    assert win.right_stack.currentWidget() is win.panel_editor
    win._render_now()
    assert win.canvas.last_info.drawn >= 1, win.canvas.last_info.warnings

    win.tabbar.setCurrentIndex(0)
    assert win.current_panel() is None
    assert win.right_stack.currentWidget() is win.inspector


def test_editor_changes_the_panel():
    win.tabbar.setCurrentIndex(len(win.project.plots))
    panel = win.current_panel()
    win.panel_editor.spn_cols.setValue(1)
    assert panel.cols == 1, panel.cols
    win.panel_editor.cmb_letters.setCurrentText("a, b, c")
    assert panel.letters == "lower", panel.letters
    before = len(panel.plots)
    win.panel_editor.cmb_available.setCurrentIndex(0)
    win.panel_editor._add_plot()
    assert len(panel.plots) == before + 1
    win.panel_editor._move(-1)
    win.panel_editor._remove_plot()
    assert len(panel.plots) == before
    win._render_now()


def test_panel_creation_is_undoable():
    win.history.clear()
    count = len(win.project.panels)
    win.new_panel()
    assert len(win.project.panels) == count + 1
    win.undo()
    assert len(win.project.panels) == count, len(win.project.panels)
    win.redo()
    assert len(win.project.panels) == count + 1


def test_panel_deletion_works():
    win.tabbar.setCurrentIndex(win.tabbar.count() - 1)
    count = len(win.project.panels)
    win.delete_plot()
    assert len(win.project.panels) == count - 1
    assert len(win.project.plots) >= 1
