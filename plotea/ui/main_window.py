"""Main window: assembles the data panel, canvas, inspector and stats dock."""
from __future__ import annotations

import os

from PyQt6.QtCore import QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import demo, plotting
from ..core import export as export_mod
from ..core import project as project_mod
from ..core.dataset import empty_dataset
from ..core.history import History, Snapshot
from ..core.panel import Panel
from ..core.plotspec import PlotSpec
from ..core.project import Project, config_dir
from ..core.themes import THEMES
from ..resources import app_icon, write_dock_icons
from .canvas import PlotCanvas
from .data_view import DataPanel
from .dialogs import (
    AboutDialog,
    ExportDialog,
    ImportDialog,
    LogDialog,
    TransformDialog,
)
from .inspector import Inspector
from .panel_editor import PanelEditor
from .stats_view import StatsPanel
from .style import build_qss, palette_colors
from .widgets import refresh_icons, set_icon_color, tag_icon

APP_NAME = "Plotea"
VERSION = "1.0.0"


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("Plotea", "Plotea")
        self.project = Project()
        self.dark = self.settings.value("dark", False, type=bool)
        self.history = History()
        self._burst_base: Snapshot | None = None
        self._burst_label = ""
        self._restoring = False
        self._burst_timer = QTimer(self)
        self._burst_timer.setSingleShot(True)
        self._burst_timer.setInterval(700)
        self._burst_timer.timeout.connect(self._commit_burst)

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(120)
        self._render_timer.timeout.connect(self._render_now)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1520, 940)
        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks
                            | QMainWindow.DockOption.AllowTabbedDocks
                            | QMainWindow.DockOption.AnimatedDocks)

        self._build_central()
        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._label_dock_buttons()
        for dock in (self.dock_data, self.dock_inspector, self.dock_stats):
            # floating a panel rebuilds its title bar; re-label it there and
            # then rather than leave a button with no tooltip
            dock.topLevelChanged.connect(
                lambda _=False: self._label_dock_buttons())
        self.statusBar().showMessage("Prêt")
        self.apply_theme(self.dark)
        self._restore_layout()

        self._new_project(with_example=True)

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    def _build_central(self):
        self.tabbar = QTabBar()
        self.tabbar.setExpanding(False)
        self.tabbar.setMovable(True)
        self.tabbar.setDrawBase(False)
        self.tabbar.setDocumentMode(True)
        self.tabbar.currentChanged.connect(self._on_tab_changed)
        self.tabbar.tabMoved.connect(self._on_tab_moved)
        self.tabbar.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabbar.customContextMenuRequested.connect(self._tab_menu)

        add = QToolButton()
        tag_icon(add, "plus")
        add.setToolTip("Nouveau graphique (Ctrl+T)")
        add.setAutoRaise(True)
        add.clicked.connect(self.new_plot)

        # The journal theme belongs to the graph on screen, so it sits on the
        # tab row rather than in the toolbar, where it was crowding out the
        # labels of the file actions.
        self.cmb_theme_quick = QComboBox()
        self.cmb_theme_quick.addItems(list(THEMES))
        self.cmb_theme_quick.setFixedWidth(126)
        self.cmb_theme_quick.setToolTip(
            "Thématique de journal du graphique courant")
        self.cmb_theme_quick.currentTextChanged.connect(self.set_theme)
        lbl_theme = QLabel("Thématique")
        lbl_theme.setProperty("hint", True)

        bar = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 6, 8, 0)
        bl.setSpacing(4)
        bl.addWidget(self.tabbar)
        bl.addWidget(add)
        bl.addStretch(1)
        bl.addWidget(lbl_theme)
        bl.addWidget(self.cmb_theme_quick)

        self.canvas = PlotCanvas()
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(bar)
        lay.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

    def _build_docks(self):
        self.data_panel = DataPanel()
        self.data_panel.datasetChanged.connect(self._on_dataset_changed)
        self.data_panel.dataEdited.connect(
            lambda: self._begin_edit("Modification des données", deep=True))
        self.data_panel.dataEdited.connect(self.schedule_render)
        self.data_panel.importRequested.connect(self.import_data)
        self.data_panel.addTableRequested.connect(self.add_table)
        self.data_panel.transformRequested.connect(self.transform_data)

        self.dock_data = QDockWidget("Données", self)
        self.dock_data.setObjectName("dock_data")
        self.dock_data.setWidget(self.data_panel)
        self.dock_data.setMinimumWidth(330)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.dock_data)

        self.inspector = Inspector()
        self.inspector.changed.connect(
            lambda: self._begin_edit("Mise en forme"))
        self.inspector.changed.connect(self.schedule_render)
        self.inspector.datasetSwitched.connect(self._on_inspector_dataset)
        self.inspector.plotTypeChanged.connect(self._on_plot_type_changed)
        self.panel_editor = PanelEditor()
        self.panel_editor.changed.connect(
            lambda: self._begin_edit("Figure composite"))
        self.panel_editor.changed.connect(self.schedule_render)
        self.panel_editor.renamed.connect(self._on_panel_renamed)

        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.inspector)
        self.right_stack.addWidget(self.panel_editor)

        self.dock_inspector = QDockWidget("Mise en forme", self)
        self.dock_inspector.setObjectName("dock_inspector")
        self.dock_inspector.setWidget(self.right_stack)
        self.dock_inspector.setMinimumWidth(340)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,
                           self.dock_inspector)

        self.stats_panel = StatsPanel()
        self.dock_stats = QDockWidget("Analyses", self)
        self.dock_stats.setObjectName("dock_stats")
        self.dock_stats.setWidget(self.stats_panel)
        self.dock_stats.setMinimumHeight(150)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,
                           self.dock_stats)
        self.resizeDocks([self.dock_stats], [210],
                         Qt.Orientation.Vertical)

    def _label_dock_buttons(self):
        """Give the title-bar buttons the tooltip every other button has.

        Qt names them for screen readers but shows nothing on hover, so what
        they do - and that a closed panel comes back from the Affichage menu -
        is left to guesswork.
        """
        tips = {
            "qt_dockwidget_floatbutton":
                "Détacher le panneau dans sa propre fenêtre",
            "qt_dockwidget_closebutton":
                "Fermer le panneau (menu Affichage pour le rouvrir)",
        }
        for dock in (self.dock_data, self.dock_inspector, self.dock_stats):
            for button in dock.findChildren(QAbstractButton):
                tip = tips.get(button.objectName())
                if tip:
                    button.setToolTip(f"{tip} — {dock.windowTitle()}")

    def _act(self, text, slot, shortcut=None, icon=None, tip=""):
        action = QAction(text, self)
        if icon:
            tag_icon(action, icon)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(tip or text)
        action.triggered.connect(slot)
        return action

    def _build_actions(self):
        self.a_new = self._act("Nouveau projet", self._new_project, "Ctrl+N")
        self.a_open = self._act("Ouvrir un projet...", self.open_project,
                                "Ctrl+Shift+O", "open")
        self.a_import = self._act("Importer des données...", self.import_data,
                                  "Ctrl+O", "import",
                                  "Importer un fichier CSV ou Excel")
        self.a_save = self._act("Enregistrer", self.save_project, "Ctrl+S",
                                "save")
        self.a_save_as = self._act("Enregistrer sous...", self.save_project_as,
                                   "Ctrl+Shift+S")
        self.a_export = self._act("Exporter la figure...", self.export_figure,
                                  "Ctrl+E", "export",
                                  "SVG, PDF, PNG 600 dpi...")
        self.a_export_all = self._act("Exporter toutes les figures...",
                                      self.export_all)
        self.a_quit = self._act("Quitter", self.close, "Ctrl+Q")

        self.a_undo = self._act("Annuler", self.undo, "Ctrl+Z")
        self.a_redo = self._act("Rétablir", self.redo, "Ctrl+Y")
        self.a_undo.setEnabled(False)
        self.a_redo.setEnabled(False)

        self.a_copy_png = self._act("Copier la figure (PNG)",
                                    lambda: self._copy(False),
                                    "Ctrl+Shift+C", "copy")
        self.a_copy_svg = self._act("Copier la figure (SVG)",
                                    lambda: self._copy(True))
        self.a_paste = self._act("Coller des données", self._paste_data)

        self.a_new_plot = self._act("Nouveau graphique", self.new_plot,
                                    "Ctrl+T", "plus")
        # "composite", not "table": the data panel already uses the table
        # glyph for its blank-table button and the two must not look alike.
        self.a_new_panel = self._act("Nouvelle figure composite",
                                     self.new_panel, "Ctrl+Shift+T",
                                     "composite",
                                     "Assembler plusieurs graphiques (A, B, C)")
        # its own glyph: side by side with Copier, two sets of overlapping
        # sheets were indistinguishable
        self.a_dup_plot = self._act("Dupliquer le graphique",
                                    self.duplicate_plot, "Ctrl+D", "duplicate")
        self.a_rename_plot = self._act("Renommer le graphique...",
                                       self.rename_plot, "F2")
        self.a_del_plot = self._act("Supprimer le graphique",
                                    self.delete_plot, None, "trash")

        self.a_transform = self._act("Transformer les données...",
                                     self.transform_data, "Ctrl+M", "fit",
                                     "Normaliser, % du contrôle, log...")
        self.a_save_preset = self._act("Enregistrer le style courant...",
                                       self.save_preset)
        self.a_reset_layout = self._act("Réinitialiser la disposition",
                                        self.reset_layout)
        self.a_dark = self._act("Interface sombre",
                                lambda: self.apply_theme(not self.dark))
        self.a_dark.setCheckable(True)
        self.a_dark.setChecked(self.dark)
        self.a_log = self._act("Journal des erreurs...", self.show_log)
        self.a_about = self._act("A propos", self.show_about)
        self.a_shortcuts = self._act("Raccourcis clavier", self.show_shortcuts)

    def _build_menus(self):
        mb = self.menuBar()
        m_file = mb.addMenu("&Fichier")
        m_file.addAction(self.a_new)
        m_file.addAction(self.a_open)
        m_file.addSeparator()
        m_file.addAction(self.a_import)
        m_examples = m_file.addMenu("Jeux de données d'exemple")
        for label in demo.EXAMPLES:
            m_examples.addAction(
                self._act(label,
                          lambda _=False, name=label:
                          self.load_example(name)))
        m_file.addSeparator()
        m_file.addAction(self.a_save)
        m_file.addAction(self.a_save_as)
        m_file.addSeparator()
        m_file.addAction(self.a_export)
        m_file.addAction(self.a_export_all)
        m_file.addSeparator()
        m_file.addAction(self.a_quit)

        m_data = mb.addMenu("&Données")
        m_data.addAction(self.a_import)
        m_data.addAction(self.a_transform)

        m_edit = mb.addMenu("&Édition")
        m_edit.addAction(self.a_undo)
        m_edit.addAction(self.a_redo)
        m_edit.addSeparator()
        m_edit.addAction(self.a_copy_png)
        m_edit.addAction(self.a_copy_svg)
        m_edit.addAction(self.a_paste)

        m_plot = mb.addMenu("&Graphique")
        m_plot.addAction(self.a_new_plot)
        m_plot.addAction(self.a_new_panel)
        m_plot.addAction(self.a_dup_plot)
        m_plot.addAction(self.a_rename_plot)
        m_plot.addSeparator()
        m_plot.addAction(self.a_del_plot)

        m_style = mb.addMenu("&Style")
        m_theme = m_style.addMenu("Thématique de journal")
        for name, theme in THEMES.items():
            act = self._act(f"{name} - {theme.description}",
                            lambda _=False, n=name: self.set_theme(n))
            m_theme.addAction(act)
        m_style.addSeparator()
        m_style.addAction(self.a_save_preset)
        self.m_presets = m_style.addMenu("Appliquer un style enregistré")
        self.m_presets.aboutToShow.connect(self._fill_presets)

        m_view = mb.addMenu("&Affichage")
        m_view.addAction(self.dock_data.toggleViewAction())
        m_view.addAction(self.dock_inspector.toggleViewAction())
        m_view.addAction(self.dock_stats.toggleViewAction())
        m_view.addSeparator()
        m_view.addAction(self.a_reset_layout)
        m_view.addAction(self.a_dark)

        m_help = mb.addMenu("&Aide")
        m_help.addAction(self.a_shortcuts)
        m_help.addAction(self.a_log)
        m_help.addAction(self.a_about)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(17, 17))
        for action in (self.a_import, self.a_open, self.a_save):
            tb.addAction(action)
        tb.addSeparator()
        tb.addAction(self.a_new_plot)
        tb.addAction(self.a_new_panel)
        tb.addAction(self.a_dup_plot)
        tb.addSeparator()
        tb.addAction(self.a_copy_png)
        tb.addAction(self.a_export)
        tb.addSeparator()

        self.a_new_plot.setIconText("Nouveau")
        self.a_new_panel.setIconText("Composite")
        self.a_dup_plot.setIconText("Dupliquer")
        self.a_import.setIconText("Importer")
        self.a_open.setIconText("Ouvrir")
        self.a_save.setIconText("Enregistrer")
        self.a_export.setIconText("Exporter")
        self.a_copy_png.setIconText("Copier")

        self.addToolBar(tb)

    # ------------------------------------------------------------------
    # project lifecycle
    # ------------------------------------------------------------------
    def _new_project(self, with_example: bool = False):
        self.project = Project()
        if with_example:
            self.project.add_dataset(demo.viability())
            spec = PlotSpec(name="Graphique 1", plot_type="bar",
                            dataset=self.project.datasets[0].name,
                            group="Traitement", y=["Viabilité"],
                            ylabel="Viabilité (%)", stats_enabled=True,
                            title="Effet des traitements")
            self.project.add_plot(spec)
        else:
            self.project.add_dataset(empty_dataset())
            self.project.add_plot(PlotSpec(
                name="Graphique 1", dataset=self.project.datasets[0].name))
        self._reload_all(select_plot=0)
        self._update_title()

    def _reload_all(self, select_plot: int = 0):
        self.history.clear()
        self._burst_base = None
        self.data_panel.set_datasets(self.project.datasets, 0)
        self._sync_tabs(select_plot)
        self._sync_inspector()
        self.schedule_render()
        self._update_history_actions()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un projet", self.last_dir(),
            "Projet Plotea (*.plotea)")
        if not path:
            return
        self._remember_dir(path)
        try:
            self.project = Project.load(path)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME,
                                 f"Ouverture impossible :\n{exc}")
            return
        if not self.project.plots:
            self.project.add_plot(PlotSpec())
        self._reload_all(0)
        self._update_title()
        self.statusBar().showMessage(f"Projet ouvert : {path}", 4000)

    def save_project(self):
        if not self.project.path:
            return self.save_project_as()
        try:
            self.project.save(self.project.path)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"Échec :\n{exc}")
            return
        self._update_title()
        self.statusBar().showMessage("Projet enregistré", 3000)

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le projet",
            os.path.join(self.last_dir(), self.project.name + ".plotea"),
            "Projet Plotea (*.plotea)")
        if not path:
            return
        self._remember_dir(path)
        self.project.name = os.path.splitext(os.path.basename(path))[0]
        self.project.path = path
        self.save_project()

    def _update_title(self):
        mark = "*" if self.project.dirty else ""
        name = self.project.path or self.project.name
        self.setWindowTitle(f"{APP_NAME} - {os.path.basename(name)}{mark}")

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def import_data(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer des données", self.last_dir(),
            "Tableaux (*.csv *.txt *.tsv *.xlsx *.xlsm *.xls);;"
            "CSV (*.csv *.txt *.tsv);;Excel (*.xlsx *.xlsm *.xls);;"
            "Tous les fichiers (*)")
        if not path:
            return
        self._remember_dir(path)
        dlg = ImportDialog(path, self)
        if dlg.exec() != ImportDialog.DialogCode.Accepted or not dlg.datasets:
            return
        before = self._capture()
        first = None
        for ds in dlg.datasets:
            added = self.project.add_dataset(ds)
            first = first or added
        self.data_panel.set_datasets(self.project.datasets,
                                     self.project.datasets.index(first))
        spec = self.current_spec()
        if spec and first is not None:
            spec.dataset = first.name
            self._auto_map(spec, first)
        self._sync_inspector()
        self.schedule_render()
        self._record("Import de données", before)
        self.statusBar().showMessage(
            f"{len(dlg.datasets)} table(s) importée(s)", 4000)

    def add_table(self):
        before = self._capture()
        self.project.add_dataset(
            empty_dataset(f"Table {len(self.project.datasets) + 1}"))
        self.data_panel.set_datasets(self.project.datasets,
                                     len(self.project.datasets) - 1)
        self._record("Nouvelle table", before)

    def transform_data(self):
        ds = self.data_panel.current_dataset()
        if ds is None:
            return
        dlg = TransformDialog(ds, self)
        if dlg.exec() != TransformDialog.DialogCode.Accepted:
            return
        from ..core.dataset import Dataset
        before = self._capture()
        created = self.project.add_dataset(
            Dataset(dlg.result_name, dlg.result_df, ds.source, ds.sheet,
                    f"Dérivée de {ds.name}"))
        self.data_panel.set_datasets(self.project.datasets,
                                     self.project.datasets.index(created))
        self._record("Transformation des données", before)
        self.statusBar().showMessage(
            f"Table '{created.name}' créée", 5000)

    def load_example(self, label: str):
        before = self._capture()
        ds = self.project.add_dataset(demo.load_example(label))
        self.data_panel.set_datasets(self.project.datasets,
                                     len(self.project.datasets) - 1)
        spec = self.current_spec()
        if spec:
            spec.dataset = ds.name
            self._auto_map(spec, ds)
            self._sync_inspector()
            self.schedule_render()
        self._record("Jeu de données d'exemple", before)

    def _paste_data(self):
        self.data_panel.paste_clipboard()

    def _auto_map(self, spec: PlotSpec, ds):
        """Pick sensible X/Y/group columns and axis titles for a table."""
        if ds is None:
            return
        numeric = ds.numeric_columns()
        categorical = ds.categorical_columns()
        spec.error_cols = []
        if spec.plot_type in ("line", "scatter"):
            spec.x = numeric[0] if numeric else (ds.columns[0] if ds.columns
                                                 else "")
            rest = [c for c in numeric if c != spec.x]
            if categorical and rest:
                spec.group = categorical[0]
                spec.y = rest[:1]
            else:
                spec.group = ""
                spec.y = rest[:4] or numeric[:1]
            spec.xlabel = spec.x
        else:
            if categorical and numeric:
                spec.group = categorical[0]
                spec.y = numeric[:1]
            else:
                spec.group = ""
                spec.y = numeric[:4]
            spec.xlabel = spec.group if spec.plot_type != "histogram" else (
                spec.y[0] if spec.y else "")
        if spec.plot_type == "histogram":
            spec.ylabel = ""
        elif spec.y:
            spec.ylabel = spec.y[0]
        spec.subgroup = ""

    def _on_plot_type_changed(self, plot_type: str):
        """Re-map columns when the new type cannot use the current mapping."""
        spec = self.current_spec()
        if spec is None:
            return
        ds = self.project.get_dataset(spec.dataset)
        cols = set(ds.columns) if ds else set()
        needs_x = plot_type in ("line", "scatter")
        invalid = (not spec.y or not set(spec.y) <= cols
                   or (needs_x and spec.x not in cols)
                   or (not needs_x and spec.group and spec.group not in cols))
        if invalid:
            self._auto_map(spec, ds)
        self._sync_inspector()
        self.schedule_render()

    def _on_dataset_changed(self):
        ds = self.data_panel.current_dataset()
        spec = self.current_spec()
        if ds and spec and spec.dataset != ds.name:
            spec.dataset = ds.name
            self._auto_map(spec, ds)
        self._sync_inspector()
        self.schedule_render()

    def _on_inspector_dataset(self, name: str):
        spec = self.current_spec()
        if not spec or not name or name == spec.dataset:
            return
        ds = self.project.get_dataset(name)
        if ds is None:
            return
        spec.dataset = name
        self._auto_map(spec, ds)
        idx = self.project.datasets.index(ds)
        self.data_panel.list.setCurrentRow(idx)
        self._sync_inspector()
        self.schedule_render()

    # ------------------------------------------------------------------
    # plots
    # ------------------------------------------------------------------
    def current_spec(self) -> PlotSpec | None:
        i = self.tabbar.currentIndex()
        if 0 <= i < len(self.project.plots):
            return self.project.plots[i]
        return None

    def current_panel(self) -> Panel | None:
        i = self.tabbar.currentIndex() - len(self.project.plots)
        if 0 <= i < len(self.project.panels):
            return self.project.panels[i]
        return None

    def _panel_tab_text(self, panel) -> str:
        return f"\u25a6 {panel.name}"

    def _sync_tabs(self, select: int = 0):
        self.tabbar.blockSignals(True)
        while self.tabbar.count():
            self.tabbar.removeTab(0)
        for spec in self.project.plots:
            self.tabbar.addTab(spec.name)
        for panel in self.project.panels:
            self.tabbar.addTab(self._panel_tab_text(panel))
        self.tabbar.blockSignals(False)
        if self.tabbar.count():
            self.tabbar.setCurrentIndex(
                min(max(select, 0), self.tabbar.count() - 1))

    def _on_tab_changed(self, index: int):
        if self.current_panel() is not None:
            self._sync_panel_editor()
            self.schedule_render()
            return
        spec = self.current_spec()
        if spec is None:
            return
        ds = self.project.get_dataset(spec.dataset)
        if ds is not None:
            idx = self.project.datasets.index(ds)
            if self.data_panel.list.currentRow() != idx:
                self.data_panel.list.blockSignals(True)
                self.data_panel.list.setCurrentRow(idx)
                self.data_panel.list.blockSignals(False)
                self.data_panel.model.set_dataframe(ds.df)
        self._sync_inspector()
        self.schedule_render()

    def _on_tab_moved(self, frm: int, to: int):
        count = len(self.project.plots)
        if frm < count and to < count:
            self.project.plots.insert(to, self.project.plots.pop(frm))
        elif frm >= count and to >= count:
            panels = self.project.panels
            panels.insert(to - count, panels.pop(frm - count))
        else:                    # would interleave plots and panels: put back
            self._sync_tabs(frm)

    def _tab_menu(self, pos):
        index = self.tabbar.tabAt(pos)
        if index < 0:
            return
        self.tabbar.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction(self.a_rename_plot)
        menu.addAction(self.a_dup_plot)
        menu.addSeparator()
        menu.addAction(self.a_del_plot)
        menu.exec(self.tabbar.mapToGlobal(pos))

    def new_plot(self):
        base = self.current_spec()
        ds = self.data_panel.current_dataset() or (
            self.project.datasets[0] if self.project.datasets else None)
        spec = PlotSpec(name=f"Graphique {len(self.project.plots) + 1}",
                        dataset=ds.name if ds else "",
                        theme=base.theme if base else "Nature")
        if ds is not None:
            self._auto_map(spec, ds)
        before = self._capture()
        self.project.add_plot(spec)
        self._sync_tabs(len(self.project.plots) - 1)
        self._record("Nouveau graphique", before)

    def new_panel(self):
        before = self._capture()
        spec = self.current_spec()
        panel = Panel(name=f"Figure {len(self.project.panels) + 1}",
                      plots=[s.name for s in self.project.plots[:4]],
                      theme=spec.theme if spec else "Nature")
        self.project.add_panel(panel)
        self._sync_tabs(len(self.project.plots) + len(self.project.panels) - 1)
        self._record("Nouvelle figure composite", before)

    def _sync_panel_editor(self):
        panel = self.current_panel()
        if panel is None:
            return
        self.right_stack.setCurrentWidget(self.panel_editor)
        self.panel_editor.set_panel(panel, self.project.plot_names())
        self.dock_inspector.setWindowTitle("Figure composite")

    def _on_panel_renamed(self):
        panel = self.current_panel()
        if panel is not None:
            self.tabbar.setTabText(self.tabbar.currentIndex(),
                                   self._panel_tab_text(panel))

    def duplicate_plot(self):
        spec = self.current_spec()
        if spec is None:
            return
        before = self._capture()
        self.project.add_plot(spec.clone())
        self._sync_tabs(len(self.project.plots) - 1)
        self._record("Duplication", before)

    def rename_plot(self):
        panel = self.current_panel()
        if panel is not None:
            name, ok = QInputDialog.getText(self, "Renommer",
                                            "Nom de la figure :",
                                            text=panel.name)
            if ok and name.strip():
                before = self._capture()
                panel.name = name.strip()
                self.tabbar.setTabText(self.tabbar.currentIndex(),
                                       self._panel_tab_text(panel))
                self.panel_editor.set_panel(panel, self.project.plot_names())
                self._record("Renommage", before)
            return
        spec = self.current_spec()
        if spec is None:
            return
        name, ok = QInputDialog.getText(self, "Renommer", "Nom du graphique :",
                                        text=spec.name)
        if ok and name.strip():
            before = self._capture()
            spec.name = name.strip()
            self.tabbar.setTabText(self.tabbar.currentIndex(), spec.name)
            self._record("Renommage", before)
            self.project.dirty = True
            self._update_title()

    def delete_plot(self):
        index = self.tabbar.currentIndex()
        if self.current_panel() is not None:
            before = self._capture()
            self.project.remove_panel(index - len(self.project.plots))
            self._sync_tabs(max(index - 1, 0))
            self._record("Suppression de la figure composite", before)
            return
        if len(self.project.plots) <= 1:
            QMessageBox.information(self, APP_NAME,
                                    "Au moins un graphique est nécessaire.")
            return
        before = self._capture()
        self.project.remove_plot(index)
        self._sync_tabs(max(index - 1, 0))
        self._record("Suppression du graphique", before)

    def set_theme(self, name: str):
        spec = self.current_spec()
        if spec is None or name not in THEMES or spec.theme == name:
            return
        spec.theme = name
        self._sync_inspector()
        self.schedule_render()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def _sync_inspector(self):
        spec = self.current_spec()
        if spec is None:
            self._sync_panel_editor()
            return
        self.right_stack.setCurrentWidget(self.inspector)
        self.dock_inspector.setWindowTitle("Mise en forme")
        ds = self.project.get_dataset(spec.dataset)
        columns = ds.columns if ds else []
        self.inspector.set_spec(spec, columns, self.project.dataset_names())
        self.cmb_theme_quick.blockSignals(True)
        self.cmb_theme_quick.setCurrentText(spec.theme)
        self.cmb_theme_quick.blockSignals(False)

    # ------------------------------------------------------------------
    # remembered session
    # ------------------------------------------------------------------
    def _restore_layout(self):
        """Put the window and its docks back where they were left."""
        geometry = self.settings.value("geometry")
        state = self.settings.value("windowState")
        try:
            if geometry is not None:
                self.restoreGeometry(geometry)
            if state is not None:
                self.restoreState(state)
        except Exception:            # a settings file from another version
            self.settings.remove("geometry")
            self.settings.remove("windowState")

    def _save_layout(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def reset_layout(self):
        """Bring the panels back, for a layout dragged into a corner."""
        self.settings.remove("geometry")
        self.settings.remove("windowState")
        for dock, area in ((self.dock_data,
                            Qt.DockWidgetArea.LeftDockWidgetArea),
                           (self.dock_inspector,
                            Qt.DockWidgetArea.RightDockWidgetArea),
                           (self.dock_stats,
                            Qt.DockWidgetArea.BottomDockWidgetArea)):
            dock.setFloating(False)
            dock.show()
            self.addDockWidget(area, dock)
        self.resize(1520, 940)
        self.resizeDocks([self.dock_data, self.dock_inspector], [340, 360],
                         Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_stats], [210], Qt.Orientation.Vertical)
        self.statusBar().showMessage("Disposition réinitialisée", 3000)

    def last_dir(self) -> str:
        """Folder of the last file opened or written, for the next dialog."""
        path = self.settings.value("lastDir", "", type=str)
        return path if path and os.path.isdir(path) else os.path.expanduser("~")

    def _remember_dir(self, path: str):
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if folder:
            self.settings.setValue("lastDir", folder)

    # ------------------------------------------------------------------
    # undo / redo
    # ------------------------------------------------------------------
    def _capture(self, deep: bool = False) -> Snapshot:
        """Current state. `deep` copies the tables, for data edits."""
        return Snapshot(
            panels=[panel.to_dict() for panel in self.project.panels],
            plots=[spec.to_dict() for spec in self.project.plots],
            datasets=[(ds.name, ds.df.copy() if deep else ds.df, ds.notes)
                      for ds in self.project.datasets],
            current_plot=max(self.tabbar.currentIndex(), 0),
            current_dataset=max(self.data_panel.list.currentRow(), 0))

    def _begin_edit(self, label: str, deep: bool = False):
        """Start (or extend) a burst of edits recorded as one undo step."""
        if self._restoring:
            return
        if self._burst_base is None:
            self._burst_base = self._capture(deep)
            self._burst_label = label
        self._burst_timer.start()

    def _commit_burst(self):
        if self._burst_base is None:
            return
        before, self._burst_base = self._burst_base, None
        deep = any(a is not b.df for (_, a, _), b
                   in zip(before.datasets, self.project.datasets))
        self.history.push(self._burst_label, before, self._capture(deep))
        self._update_history_actions()

    def _record(self, label: str, before: Snapshot, deep: bool = False):
        """Record a single, immediate action."""
        if self._restoring:
            return
        self._commit_burst()
        self.history.push(label, before, self._capture(deep))
        self._update_history_actions()

    def _restore(self, snapshot: Snapshot):
        from ..core.dataset import Dataset
        self._restoring = True
        self._burst_timer.stop()
        self._burst_base = None
        try:
            self.project.plots = [PlotSpec.from_dict(d) for d in snapshot.plots]
            self.project.panels = [Panel.from_dict(d)
                                   for d in snapshot.panels]
            self.project.datasets = [
                Dataset(name, df, notes=notes)
                for name, df, notes in snapshot.datasets]
            self.data_panel.set_datasets(self.project.datasets,
                                         snapshot.current_dataset)
            self._sync_tabs(snapshot.current_plot)
            self._sync_inspector()
            self._render_now()
        finally:
            self._restoring = False
        self._update_history_actions()

    def undo(self):
        self._commit_burst()
        snapshot = self.history.undo()
        if snapshot is None:
            return
        label = self.history.redo_label()
        self._restore(snapshot)
        self.statusBar().showMessage(f"Annulé : {label}", 3000)

    def redo(self):
        snapshot = self.history.redo()
        if snapshot is None:
            return
        self._restore(snapshot)
        self.statusBar().showMessage(f"Rétabli : {self.history.undo_label()}",
                                     3000)

    def _update_history_actions(self):
        self.a_undo.setEnabled(self.history.can_undo())
        self.a_redo.setEnabled(self.history.can_redo())
        self.a_undo.setText(f"Annuler {self.history.undo_label()}".strip()
                            if self.history.can_undo() else "Annuler")
        self.a_redo.setText(f"Rétablir {self.history.redo_label()}".strip()
                            if self.history.can_redo() else "Rétablir")

    def schedule_render(self):
        self.project.dirty = True
        self._render_timer.start()

    def _render_now(self):
        panel = self.current_panel()
        if panel is not None:
            info = self.canvas.render_panel(panel,
                                            self.project.specs_by_name(),
                                            self.project.frames_by_name())
            self.tabbar.setTabText(self.tabbar.currentIndex(),
                                   self._panel_tab_text(panel))
            self._update_title()
            if info.warnings:
                self.statusBar().showMessage(" ; ".join(info.warnings), 6000)
            return
        spec = self.current_spec()
        if spec is None:
            return
        ds = self.project.get_dataset(spec.dataset)
        df = ds.df if ds else None
        info = self.canvas.render_spec(spec, df)
        series = [str(s) for s in info.series]
        self.inspector.update_series(
            series, plotting.series_colors(spec, series))
        self.inspector.set_group_labels([str(g) for g in info.groups])
        self.stats_panel.update_from(info)
        self.tabbar.setTabText(self.tabbar.currentIndex(), spec.name)
        self.data_panel.refresh_current_label()
        self._update_title()
        if info.warnings:
            self.statusBar().showMessage(" ; ".join(info.warnings), 6000)

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------
    def export_figure(self):
        spec = self.current_spec()
        if spec is None:
            return
        safe = "".join(c if c.isalnum() or c in " -_" else "_"
                       for c in spec.name).strip() or "figure"
        folder = (os.path.dirname(self.project.path) if self.project.path
                  else self.last_dir())
        dlg = ExportDialog(os.path.join(folder, safe + ".png"),
                           spec.width_mm, spec.height_mm, self)
        if dlg.exec() != ExportDialog.DialogCode.Accepted:
            return
        options = dlg.options()
        options.transparent = options.transparent or spec.transparent_bg
        try:
            path = export_mod.save_figure(self.canvas.figure, options)
            self._remember_dir(path)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"Export impossible :\n{exc}")
            return
        self.canvas.refresh()
        self.statusBar().showMessage(f"Exporté : {path}", 6000)

    def export_all(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Dossier de destination", self.last_dir())
        if not folder:
            return
        self._remember_dir(folder)
        fmt, ok = QInputDialog.getItem(self, "Format",
                                       "Format d'export :",
                                       list(export_mod.FORMATS), 3, False)
        if not ok:
            return
        current = self.tabbar.currentIndex()
        written = []
        for i, spec in enumerate(list(self.project.plots)
                                 + list(self.project.panels)):
            self.tabbar.setCurrentIndex(i)
            self._render_now()
            safe = "".join(c if c.isalnum() or c in " -_" else "_"
                           for c in spec.name).strip() or f"figure{i + 1}"
            options = export_mod.ExportOptions(
                os.path.join(folder, safe), fmt,
                dpi=export_mod.DEFAULT_DPI,
                transparent=spec.transparent_bg)
            try:
                written.append(export_mod.save_figure(self.canvas.figure,
                                                      options))
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME,
                                    f"{spec.name} : {exc}")
        self.tabbar.setCurrentIndex(current)
        self.statusBar().showMessage(
            f"{len(written)} figure(s) exportée(s) dans {folder}", 6000)

    def _copy(self, as_svg: bool):
        if as_svg:
            self.canvas.copy_svg_to_clipboard()
            self.statusBar().showMessage("SVG copie dans le presse-papiers",
                                         3000)
        else:
            self.canvas.copy_to_clipboard(dpi=300)
            self.statusBar().showMessage("Figure copiee (300 dpi)", 3000)

    # ------------------------------------------------------------------
    # styles & appearance
    # ------------------------------------------------------------------
    def save_preset(self):
        spec = self.current_spec()
        if spec is None:
            return
        name, ok = QInputDialog.getText(self, "Style", "Nom du style :",
                                        text=f"{spec.theme} personnalisé")
        if ok and name.strip():
            project_mod.save_preset(name.strip(),
                                    project_mod.extract_style(spec))
            self.statusBar().showMessage(f"Style '{name}' enregistré", 3000)

    def _fill_presets(self):
        self.m_presets.clear()
        presets = project_mod.load_presets()
        if not presets:
            act = self.m_presets.addAction("(aucun style enregistré)")
            act.setEnabled(False)
            return
        for name, style in presets.items():
            self.m_presets.addAction(
                self._act(name, lambda _=False, s=style: self.apply_preset(s)))
        self.m_presets.addSeparator()
        self.m_presets.addAction(self._act("Appliquer a tous les graphiques",
                                           self.apply_style_to_all))

    def apply_preset(self, style: dict):
        spec = self.current_spec()
        if spec is None:
            return
        project_mod.apply_style(spec, style)
        self._sync_inspector()
        self.schedule_render()

    def apply_style_to_all(self):
        spec = self.current_spec()
        if spec is None:
            return
        style = project_mod.extract_style(spec)
        for other in self.project.plots:
            if other is not spec:
                project_mod.apply_style(other, style)
        self.statusBar().showMessage(
            f"Style appliqué a {len(self.project.plots)} graphiques", 4000)

    def apply_theme(self, dark: bool):
        colors = palette_colors(dark)
        self.dark = dark
        self.a_dark.setChecked(dark)
        self.settings.setValue("dark", dark)
        icons = write_dock_icons(config_dir(), colors["text"],
                                 {"close": colors["danger"],
                                  "float": colors["accent"]})
        self.dock_icons = icons        # kept for the packaged smoke test
        QApplication.instance().setStyleSheet(build_qss(dark, icons))
        set_icon_color(colors["text"])
        refresh_icons(self)
        # Qt rebuilds the title bar when a panel is floated; re-apply the
        # tooltips so they never go missing after a detach.
        self._label_dock_buttons()
        self.canvas.set_desk_color(colors["canvas"])

    # ------------------------------------------------------------------
    def show_log(self):
        LogDialog(self).exec()

    def show_about(self):
        AboutDialog(VERSION, self).exec()

    def show_shortcuts(self):
        QMessageBox.information(
            self, "Raccourcis clavier",
            "Ctrl+O        Importer des données\n"
            "Ctrl+Shift+O  Ouvrir un projet\n"
            "Ctrl+S        Enregistrer le projet\n"
            "Ctrl+E        Exporter la figure\n"
            "Ctrl+T        Nouveau graphique\n"
            "Ctrl+D        Dupliquer le graphique\n"
            "F2            Renommer le graphique\n"
            "Ctrl+C / V    Copier / coller dans le tableau\n"
            "Ctrl+Shift+C  Copier la figure en PNG\n"
            "Suppr         Effacer les cellules sélectionnées")

    def closeEvent(self, event):
        if self.project.dirty:
            # Spelled out rather than left to Qt: the standard buttons read
            # "Save / Discard / Cancel" whenever the translations are missing,
            # which is exactly what a packaged build tends to drop.
            box = QMessageBox(self)
            box.setWindowTitle(APP_NAME)
            box.setIcon(QMessageBox.Icon.Question)
            box.setText("Le projet a été modifié.")
            box.setInformativeText("Voulez-vous l'enregistrer avant de "
                                   "quitter ?")
            save = box.addButton("Enregistrer",
                                 QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Quitter sans enregistrer",
                          QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton("Annuler",
                                   QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(save)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel:
                event.ignore()
                return
            if clicked is save:
                self.save_project()
        self._save_layout()
        event.accept()
