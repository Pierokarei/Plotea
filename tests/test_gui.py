"""Offscreen GUI smoke test: build the window and drive the main workflows."""
import os


from PyQt6.QtWidgets import QApplication

app = QApplication.instance()

from plotea.core import demo  # noqa: E402
from plotea.ui.main_window import MainWindow  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)


win = MainWindow()
win.resize(1520, 940)
win.show()
app.processEvents()
win._render_now()


def test_window_is_built():
    assert win.current_spec() is not None
    assert win.project.datasets
    assert win.project.plots


def test_switch_types():
    for t in ("line", "scatter", "histogram", "box", "violin", "bar"):
        spec = win.current_spec()
        spec.plot_type = t
        ds = win.project.get_dataset(spec.dataset)
        win._auto_map(spec, ds)
        win._sync_inspector()
        win._render_now()
        app.processEvents()
        assert win.canvas.last_info is not None, t


def test_load_examples():
    for label in demo.EXAMPLES:
        win.load_example(label)
        win._render_now()
        app.processEvents()
        assert not win.canvas.last_info.warnings, \
            f"{label}: {win.canvas.last_info.warnings}"


def test_plot_management():
    before = len(win.project.plots)
    win.new_plot()
    win.duplicate_plot()
    assert len(win.project.plots) == before + 2
    win.delete_plot()
    assert len(win.project.plots) == before + 1


def test_themes():
    for name in ("Nature", "Science", "Cell", "PNAS", "Minimal", "Grayscale"):
        win.set_theme(name)
        win._render_now()
        app.processEvents()
        assert win.current_spec().theme == name


def test_inspector_roundtrip():
    """Every inspector widget must survive a push/pull cycle unchanged."""
    spec = win.current_spec()
    spec.title = "Titre test"
    spec.ylabel = "Y test"
    spec.alpha = 0.55
    spec.bins = 33
    spec.ymax = 250.0
    spec.legend_loc = "outside right"
    win._sync_inspector()
    win.inspector._push()
    assert spec.title == "Titre test", spec.title
    assert spec.ylabel == "Y test", spec.ylabel
    assert abs(spec.alpha - 0.55) < 1e-6, spec.alpha
    assert spec.bins == 33, spec.bins
    assert spec.ymax == 250.0, spec.ymax
    assert spec.legend_loc == "outside right", spec.legend_loc
    assert spec.palette == "", repr(spec.palette)


def test_stats_and_fit():
    win.load_example("Viabilité cellulaire (barres, stats)")
    spec = win.current_spec()
    spec.plot_type = "bar"
    spec.group = "Traitement"
    spec.y = ["Viabilité"]
    spec.stats_enabled = True
    win._render_now()
    assert len(win.canvas.last_info.comparisons) == 6
    assert win.stats_panel.tests.rowCount() == 6

    win.load_example("Dose-réponse (fit 4PL)")
    spec = win.current_spec()
    spec.plot_type = "scatter"
    spec.x = "log[C] (M)"
    spec.y = ["Réponse (%)"]
    spec.group = "Composé"
    spec.fit_model = "Dose-reponse log"
    win._render_now()
    assert len(win.canvas.last_info.fits) == 2
    assert all(r.r2 > 0.9 for r in win.canvas.last_info.fits.values())


def test_export_roundtrip():
    from plotea.core import export as ex
    for label in ex.FORMATS:
        ex.save_figure(win.canvas.figure,
                       ex.ExportOptions(os.path.join(OUT, "gui_export"),
                                        label, dpi=600))


def test_project_roundtrip():
    path = win.project.save(os.path.join(OUT, "gui_project.plotea"))
    from plotea.core.project import Project
    reloaded = Project.load(path)
    assert len(reloaded.plots) == len(win.project.plots)
    assert len(reloaded.datasets) == len(win.project.datasets)


def test_annotations_and_error_columns():
    win.load_example("Courbe de croissance (courbes + SD)")
    spec = win.current_spec()
    spec.plot_type = "line"
    spec.x = "Temps (h)"
    spec.y = ["WT", "KO", "KO + rescue"]
    spec.error_cols = ["WT SD", "KO SD", "KO + rescue SD"]
    spec.error_band = True
    win._sync_inspector()
    win._render_now()
    assert win.inspector.lst_err.checked_items() == spec.error_cols

    win.inspector._add_annotation()
    win.inspector.ann_text.setText("n = 3 experiences")
    win.inspector._store_annotation()
    win._render_now()
    assert spec.annotations[0]["text"] == "n = 3 experiences"
    win.inspector._remove_annotation()
    assert not spec.annotations


def test_paired_control_visibility():
    """The pairing combo appears only for a paired test, and feeds the spec."""
    win.load_example("Viabilité cellulaire (barres, stats)")
    spec = win.current_spec()
    spec.plot_type = "bar"
    spec.group = "Traitement"
    spec.y = ["Viabilité"]
    spec.stats_enabled = True
    spec.stats_test = "t de Welch"
    win._sync_inspector()
    assert not win.inspector.r_pair.isVisible()

    spec.stats_test = "t apparié"
    win._sync_inspector()
    assert win.inspector.r_pair.isVisible()
    assert win.inspector.cmb_pair.findText("Réplicat") > 0

    win.inspector.cmb_pair.setCurrentText("Réplicat")
    win.inspector._push()
    assert spec.stats_pair_by == "Réplicat", spec.stats_pair_by
    win._render_now()
    assert len(win.canvas.last_info.comparisons) == 6,         win.canvas.last_info.warnings


def test_grouped_bar_stats_through_ui():
    win.load_example("Plan à deux facteurs (barres groupées)")
    spec = win.current_spec()
    spec.plot_type = "bar"
    spec.group = "Temps"
    spec.subgroup = "Génotype"
    spec.y = ["Activité"]
    spec.stats_enabled = True
    spec.stats_test = "Auto"
    win._sync_inspector()
    win._render_now()
    info = win.canvas.last_info
    assert len(info.comparisons) == 3, info.comparisons

    # a paired test has no meaning here: refuse it rather than invent a number
    spec.stats_test = "t apparié"
    win._render_now()
    assert win.canvas.last_info.comparisons == []
    assert any("groupees" in w for w in win.canvas.last_info.warnings), \
        win.canvas.last_info.warnings
    spec.stats_test = "Auto"
    win._render_now()
    info = win.canvas.last_info
    assert win.stats_panel.tests.rowCount() == 3
    assert win.stats_panel.desc.rowCount() == 6
    # colour swatches follow the subgroups, not the categories
    assert set(win.inspector._color_buttons) == {"WT", "Mutant"},         list(win.inspector._color_buttons)


def test_data_editing():
    panel = win.data_panel
    n = panel.model.rowCount()
    panel.model.add_rows(3)
    assert panel.model.rowCount() == n + 3
    c = panel.model.columnCount()
    panel.model.add_column("Nouvelle")
    assert panel.model.columnCount() == c + 1
    panel.model.remove_columns([c])
    assert panel.model.columnCount() == c


def test_dark_mode():
    win.apply_theme(True)
    app.processEvents()
    win.apply_theme(False)
    app.processEvents()


def test_screenshots():
    win.load_example("Viabilité cellulaire (barres, stats)")
    spec = win.current_spec()
    spec.plot_type = "bar"
    spec.group = "Traitement"
    spec.y = ["Viabilité"]
    spec.ylabel = "Viabilite (%)"
    spec.title = "Effet des traitements"
    spec.stats_enabled = True
    win._sync_inspector()
    win._render_now()
    app.processEvents()
    win.grab().save(os.path.join(OUT, "ui_light.png"))
    win.apply_theme(True)
    app.processEvents()
    win._render_now()
    win.grab().save(os.path.join(OUT, "ui_dark.png"))
    win.apply_theme(False)
