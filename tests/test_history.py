"""Undo / redo through the real window."""


from PyQt6.QtWidgets import QApplication

app = QApplication.instance()

from plotea.ui.main_window import MainWindow  # noqa: E402


win = MainWindow()
win.show()
app.processEvents()
win._render_now()


def test_starts_empty():
    assert not win.history.can_undo(), len(win.history)
    assert not win.a_undo.isEnabled()


def test_plot_creation_is_reversible():
    before = len(win.project.plots)
    win.new_plot()
    assert len(win.project.plots) == before + 1
    assert win.a_undo.isEnabled()
    win.undo()
    assert len(win.project.plots) == before, len(win.project.plots)
    win.redo()
    assert len(win.project.plots) == before + 1
    win.undo()


def test_styling_is_reversible():
    spec = win.current_spec()
    original = spec.theme
    win._begin_edit("Mise en forme")
    spec.theme = "Science"
    spec.title = "Essai"
    win._commit_burst()
    assert win.history.undo_label() == "Mise en forme"

    win.undo()
    assert win.current_spec().theme == original, win.current_spec().theme
    assert win.current_spec().title != "Essai"
    win.redo()
    assert win.current_spec().theme == "Science"
    win.undo()


def test_data_edits_are_reversible():
    model = win.data_panel.model
    original = model.dataframe().iat[0, 1]

    win._begin_edit("Modification des donnees", deep=True)
    model.dataframe().iat[0, 1] = 999.0
    win._commit_burst()

    win.undo()
    restored = win.data_panel.model.dataframe().iat[0, 1]
    assert restored == original, (restored, original)
    win.redo()
    assert win.data_panel.model.dataframe().iat[0, 1] == 999.0
    win.undo()


def test_burst_collapses_into_one_step():
    """A run of quick edits is one undo step, not twenty."""
    win.history.clear()
    spec = win.current_spec()
    for size in range(1, 12):
        win._begin_edit("Mise en forme")
        spec.marker_size = float(size)
    win._commit_burst()
    assert len(win.history) == 1, len(win.history)
    win.undo()
    assert win.current_spec().marker_size != 11.0


def test_transform_is_reversible():
    win.history.clear()
    before = len(win.project.datasets)
    from plotea.core import transforms
    from plotea.core.dataset import Dataset
    ds = win.data_panel.current_dataset()
    frame, _ = transforms.apply("Normaliser de 0 a 100", ds.df,
                                transforms.Params(
                                    columns=ds.numeric_columns()[:1]))
    snapshot = win._capture()
    win.project.add_dataset(Dataset("Normalisee", frame))
    win.data_panel.set_datasets(win.project.datasets,
                                len(win.project.datasets) - 1)
    win._record("Transformation des donnees", snapshot)

    assert len(win.project.datasets) == before + 1
    win.undo()
    assert len(win.project.datasets) == before, len(win.project.datasets)
    win.redo()
    assert len(win.project.datasets) == before + 1


def test_redo_dropped_after_new_edit():
    win.history.clear()
    win.new_plot()
    win.undo()
    assert win.history.can_redo()
    win.new_plot()
    assert not win.history.can_redo(), "une nouvelle action efface le retablir"


def test_bounded_memory():
    win.history.clear()
    win.history.limit = 5
    spec = win.current_spec()
    for i in range(12):
        snapshot = win._capture()
        spec.alpha = 0.5 + i / 100
        win._record("Mise en forme", snapshot)
    assert len(win.history) == 5, len(win.history)


def test_opening_a_project_clears_history():
    win.history.limit = 60
    win.new_plot()
    assert win.history.can_undo()
    win._reload_all(0)
    assert not win.history.can_undo()
    assert not win.a_undo.isEnabled()
