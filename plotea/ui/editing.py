"""Undo and redo for the main window.

Snapshots rather than inverse operations: a figure has enough coupled state
(specs, panels, tables, selection) that replaying a change backwards would be
a second implementation of everything the editor does. Keeping the history
here leaves the window with one less job, and puts the burst logic - the part
that decides what counts as a single step - in one readable place.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer

from ..core.dataset import Dataset
from ..core.history import History, Snapshot
from ..core.panel import Panel
from ..core.plotspec import PlotSpec
from ..i18n import tr

#: A run of edits closer together than this is recorded as one step, so
#: dragging a slider does not leave fifty entries to undo one by one.
BURST_MS = 700


class EditHistory(QObject):
    """Records what the window did, and puts it back."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.history = History()
        self._burst_base: Snapshot | None = None
        self._burst_label = ""
        self.restoring = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(BURST_MS)
        self._timer.timeout.connect(self.commit_burst)

    # ------------------------------------------------------------------
    def capture(self, deep: bool = False) -> Snapshot:
        """Current state. `deep` copies the tables, for data edits."""
        window = self.window
        return Snapshot(
            panels=[panel.to_dict() for panel in window.project.panels],
            plots=[spec.to_dict() for spec in window.project.plots],
            datasets=[(ds.name, ds.df.copy() if deep else ds.df, ds.notes)
                      for ds in window.project.datasets],
            current_plot=max(window.tabbar.currentIndex(), 0),
            current_dataset=max(window.data_panel.list.currentRow(), 0))

    def begin(self, label: str, deep: bool = False):
        """Start (or extend) a burst of edits recorded as one undo step."""
        if self.restoring:
            return
        if self._burst_base is None:
            self._burst_base = self.capture(deep)
            self._burst_label = label
        self._timer.start()

    def commit_burst(self):
        if self._burst_base is None:
            return
        before, self._burst_base = self._burst_base, None
        deep = any(a is not b.df for (_, a, _), b
                   in zip(before.datasets, self.window.project.datasets))
        self.history.push(self._burst_label, before, self.capture(deep))
        self.update_actions()

    def record(self, label: str, before: Snapshot, deep: bool = False):
        """Record a single, immediate action."""
        if self.restoring:
            return
        self.commit_burst()
        self.history.push(label, before, self.capture(deep))
        self.update_actions()

    # ------------------------------------------------------------------
    def restore(self, snapshot: Snapshot):
        window = self.window
        self.restoring = True
        self._timer.stop()
        self._burst_base = None
        try:
            window.project.plots = [PlotSpec.from_dict(d)
                                    for d in snapshot.plots]
            window.project.panels = [Panel.from_dict(d)
                                     for d in snapshot.panels]
            window.project.datasets = [
                Dataset(name, df, notes=notes)
                for name, df, notes in snapshot.datasets]
            window.data_panel.set_datasets(window.project.datasets,
                                           snapshot.current_dataset)
            window._sync_tabs(snapshot.current_plot)
            window._sync_inspector()
            window._render_now()
        finally:
            self.restoring = False
        self.update_actions()

    def undo(self):
        self.commit_burst()
        snapshot = self.history.undo()
        if snapshot is None:
            return
        label = self.history.redo_label()
        self.restore(snapshot)
        self.window.statusBar().showMessage(
            tr("Annulé : {action}").format(action=tr(label)), 3000)

    def redo(self):
        snapshot = self.history.redo()
        if snapshot is None:
            return
        self.restore(snapshot)
        self.window.statusBar().showMessage(
            tr("Rétabli : {action}").format(
                action=tr(self.history.undo_label())), 3000)

    def clear(self):
        self.history.clear()
        self._burst_base = None

    # ------------------------------------------------------------------
    def update_actions(self):
        """Keep the two menu entries saying what they would actually do."""
        window = self.window
        window.a_undo.setEnabled(self.history.can_undo())
        window.a_redo.setEnabled(self.history.can_redo())
        # the step names are stored in French and translated on display, so
        # the history itself does not depend on the interface language
        window.a_undo.setText(
            tr("Annuler {action}").format(
                action=tr(self.history.undo_label())).strip()
            if self.history.can_undo() else tr("Annuler"))
        window.a_redo.setText(
            tr("Rétablir {action}").format(
                action=tr(self.history.redo_label())).strip()
            if self.history.can_redo() else tr("Rétablir"))
