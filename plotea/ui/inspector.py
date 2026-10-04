"""The right-hand inspector: every PlotSpec option, grouped and bound."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import enums, fitting
from ..core.plotspec import PLOT_TYPES, PlotSpec
from ..core.stats import PAIRED_TESTS
from ..core.themes import LINESTYLES, MARKERS, PALETTES, THEMES
from ..i18n import tr
from .widgets import (
    PLOT_ICONS,
    CheckList,
    CollapsibleSection,
    ColorButton,
    PaletteCombo,
    hint,
    row,
    tag_icon,
)


class OptionalFloat(QLineEdit):
    """Line edit that yields a float or None when left empty ('auto')."""

    def __init__(self, placeholder: str = "auto", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setValidator(QDoubleValidator())
        self.setFixedWidth(74)

    def value(self):
        text = self.text().strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def setValue(self, value):
        self.setText("" if value is None else f"{value:g}")


def _spin(minimum, maximum, step, decimals=2, width=78) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(minimum, maximum)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    s.setFixedWidth(width)
    return s


def _int_spin(minimum, maximum, width=78) -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimum, maximum)
    s.setFixedWidth(width)
    return s


class Inspector(QWidget):
    """Two-way bound editor for a PlotSpec."""

    changed = pyqtSignal()
    datasetSwitched = pyqtSignal(str)
    plotTypeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spec = PlotSpec()
        self._loading = True          # muted until the UI is fully built
        self._bindings: list[tuple] = []
        self._color_buttons: dict[str, ColorButton] = {}

        inner = QWidget()
        self.vbox = QVBoxLayout(inner)
        self.vbox.setContentsMargins(10, 6, 10, 14)
        self.vbox.setSpacing(2)

        self._build_type()
        self._build_data()
        self._build_theme()
        self._build_labels()
        self._build_annotations()
        self._build_axes()
        self._build_series()
        self._build_error_points()
        self._build_type_specific()
        self._build_fit()
        self._build_stats()
        self.vbox.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)
        self._loading = False

    # ------------------------------------------------------------------
    # binding plumbing
    # ------------------------------------------------------------------
    PLACEHOLDER = "(thématique)"

    @staticmethod
    def fill(combo: QComboBox, enum) -> QComboBox:
        """Show the labels, carry the keys as item data."""
        combo.clear()
        for choice in enum:
            combo.addItem(tr(choice.label), choice.key)
        return combo

    def _bind(self, widget, attr: str):
        """Register a widget <-> spec attribute link and wire its signal."""
        if isinstance(widget, QComboBox):
            def getter(w=widget):
                data = w.currentData()
                if data is not None:
                    return data
                text = w.currentText()
                # compared with what is shown, which follows the language
                return "" if text == tr(self.PLACEHOLDER) else text
            widget.currentIndexChanged.connect(self._push)
        elif isinstance(widget, QCheckBox):
            getter = widget.isChecked
            widget.toggled.connect(self._push)
        elif isinstance(widget, OptionalFloat):
            getter = widget.value
            widget.editingFinished.connect(self._push)
        elif isinstance(widget, QSpinBox):
            getter = widget.value
            widget.valueChanged.connect(self._push)
        elif isinstance(widget, QDoubleSpinBox):
            getter = widget.value
            widget.valueChanged.connect(self._push)
        elif isinstance(widget, QLineEdit):
            getter = widget.text
            widget.textEdited.connect(self._push)
        elif isinstance(widget, CheckList):
            getter = widget.checked_items
            widget.changed.connect(self._push)
        elif isinstance(widget, ColorButton):
            getter = widget.color
            widget.colorChanged.connect(self._push)
        else:
            raise TypeError(f"Widget non supporte: {type(widget)}")
        self._bindings.append((widget, attr, getter))
        return widget

    def _push(self, *_):
        """UI -> spec, then ask for a re-render."""
        if self._loading or self.spec is None:
            return
        for widget, attr, getter in self._bindings:
            setattr(self.spec, attr, getter())
        self.spec.custom_colors = {
            name: btn.color() for name, btn in self._color_buttons.items()}
        self._sync_enabled()
        self.changed.emit()

    def set_spec(self, spec: PlotSpec, columns: list[str],
                 datasets: list[str]):
        """spec -> UI."""
        self._loading = True
        self.spec = spec
        numeric = columns
        self.cmb_dataset.blockSignals(True)
        self.cmb_dataset.clear()
        self.cmb_dataset.addItems(datasets)
        if spec.dataset in datasets:
            self.cmb_dataset.setCurrentText(spec.dataset)
        self.cmb_dataset.blockSignals(False)

        for combo, items, keep_blank in (
                (self.cmb_x, numeric, True),
                (self.cmb_group, numeric, True),
                (self.cmb_subgroup, numeric, True),
                (self.cmb_pair, numeric, True),
                (self.cmb_control, [], True)):
            combo.blockSignals(True)
            combo.clear()
            if keep_blank:
                combo.addItem("")
            combo.addItems(items)
            combo.blockSignals(False)
        self.lst_y.set_items(numeric, spec.y)
        self.lst_err.set_items(numeric, spec.error_cols)

        for widget, attr, _ in self._bindings:
            value = getattr(spec, attr, None)
            if isinstance(widget, QComboBox):
                idx = widget.findData(value) if value else -1
                if idx < 0 and value:
                    idx = widget.findText(str(value))
                widget.setCurrentIndex(idx if idx >= 0 else 0)
            elif isinstance(widget, CheckList):
                widget.set_checked(list(value or []))
            elif isinstance(widget, OptionalFloat):
                widget.setValue(value)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value or 0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value or ""))

        # its choices depend on the model, which the loop above just set
        self._refill_compare(keep=spec.fit_compare)

        for btn in self.type_buttons.buttons():
            if btn.property("plot_type") == spec.plot_type:
                btn.setChecked(True)
        self._refresh_annotations()
        self._loading = False
        self._sync_enabled()

    # ------------------------------------------------------------------
    # sections
    # ------------------------------------------------------------------
    def _add(self, section: CollapsibleSection):
        self.vbox.addWidget(section)
        return section

    #: Short names for the cards, so the six tiles stay the same size. The
    #: full wording lives in the tooltip.
    CARD_LABELS = {
        "line": "Courbe", "scatter": "Nuage", "histogram": "Histogramme",
        "box": "Boxplot", "violin": "Violon", "bar": "Barres",
        "survival": "Survie", "contingency": "Contingence",
        "paired": "Avant/après", "bland_altman": "Bland-Altman",
    }
    CARD_HEIGHT = 62

    def _build_type(self):
        sec = self._add(CollapsibleSection(tr("Type de graphique"), True))
        grid = QWidget()
        gl = QGridLayout(grid)
        gl.setContentsMargins(0, 2, 0, 2)
        gl.setSpacing(6)
        gl.setColumnStretch(0, 1)
        gl.setColumnStretch(1, 1)
        self.type_buttons = QButtonGroup(self)
        self.type_buttons.setExclusive(True)
        for i, (key, label) in enumerate(PLOT_TYPES.items()):
            btn = QToolButton()
            btn.setText(tr(self.CARD_LABELS.get(key, label)))
            btn.setToolTip(tr(label))
            tag_icon(btn, PLOT_ICONS.get(key, "bar"))
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setCheckable(True)
            btn.setProperty("plot_type", key)
            # identical tiles: fixed height, and each column takes half the
            # panel, so no card is wider than its neighbour
            btn.setFixedHeight(self.CARD_HEIGHT)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
            btn.setProperty("plotCard", True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self._on_type_clicked)
            self.type_buttons.addButton(btn)
            gl.addWidget(btn, i // 2, i % 2)
        sec.add_widget(grid)

    def _on_type_clicked(self):
        btn = self.sender()
        if btn and not self._loading:
            self.spec.plot_type = btn.property("plot_type")
            self._apply_smart_defaults()
            self._sync_enabled()
            self.plotTypeChanged.emit(self.spec.plot_type)

    def _apply_smart_defaults(self):
        """Set what the new plot type needs, including what a previous one
        turned off.

        Each type states its own defaults rather than only disabling things:
        a curve after a scatter has to get its line back, otherwise it draws
        markers with no line and still looks like a scatter.
        """
        t = self.spec.plot_type
        if t == "line":
            self.spec.show_line = True
            self.spec.show_markers = True
        elif t == "scatter":
            self.spec.show_line = False
            self.spec.show_markers = True
        elif t == "histogram":
            self.spec.show_points = False
        elif t in ("box", "violin"):
            self.spec.show_points = True

    def _build_data(self):
        sec = self.sec_data = self._add(CollapsibleSection(tr("Données"), True))
        self.cmb_dataset = QComboBox()
        self.cmb_dataset.currentTextChanged.connect(
            lambda t: (not self._loading) and self.datasetSwitched.emit(t))
        sec.add_row(tr("Table"), self.cmb_dataset)

        self.cmb_x = self._bind(QComboBox(), "x")
        self.lbl_x = QLabel(tr("Axe X"))
        sec.form.addRow(self.lbl_x, self.cmb_x)

        self.lst_y = self._bind(CheckList(), "y")
        self.r_y = sec.add_row(tr("Valeurs Y"), self.lst_y)

        self.cmb_event = self._bind(QComboBox(), "event_col")
        self.r_event = sec.add_row(tr("Événement (1/0)"), self.cmb_event)
        self.hint_event = hint(
            tr("Colonne valant 1 quand l'événement est survenu et 0 quand le "
            "suivi s'est arrêté avant (censure). Sans elle, tout le monde "
            "est compté comme ayant eu l'événement."))
        sec.add_widget(self.hint_event)

        self.cmb_group = self._bind(QComboBox(), "group")
        sec.add_row(tr("Grouper par"), self.cmb_group)
        self.cmb_subgroup = self._bind(QComboBox(), "subgroup")
        sec.add_row(tr("Sous-groupe"), self.cmb_subgroup)
        self.hint_counts = hint(
            tr("Effectifs déjà comptés : une ligne par groupe, cochez une "
            "colonne d'effectifs par issue dans « Valeurs Y ». Données "
            "brutes, une ligne par sujet : laissez « Valeurs Y » vide, "
            "choisissez le groupe dans « Grouper par » et l'issue dans "
            "« Sous-groupe »."))
        sec.add_widget(self.hint_counts)

        self.lst_err = self._bind(CheckList(), "error_cols")
        self.lst_err.setMaximumHeight(110)
        self.r_err_cols = sec.add_row(tr("Colonnes d'erreur"), self.lst_err)
        self.hint_err = hint(
            tr("Cochez une colonne d'erreur par série Y, dans le même ordre "
            "(ex. WT puis WT SD)."))
        sec.add_widget(self.hint_err)
        sec.add_widget(hint(
            tr("Format long : choisissez une colonne de groupe et une seule "
            "colonne de valeurs. Format large : cochez plusieurs colonnes Y.")))

    def _build_theme(self):
        sec = self._add(CollapsibleSection(tr("Style et thématique"), True))
        self.cmb_theme = self._bind(QComboBox(), "theme")
        self.cmb_theme.addItems(list(THEMES))
        self.cmb_theme.currentTextChanged.connect(self._on_theme_changed)
        sec.add_row(tr("Thématique"), self.cmb_theme)
        self.lbl_theme = hint(tr(THEMES["Nature"].description))
        sec.add_widget(self.lbl_theme)

        self.cmb_palette = self._bind(PaletteCombo(PALETTES), "palette")
        self.cmb_palette.insertItem(0, tr("(thématique)"))
        sec.add_row(tr("Palette"), self.cmb_palette)

        self.cmb_span = self._bind(QComboBox(), "span")
        self.fill(self.cmb_span, enums.SPAN)
        sec.add_row(tr("Largeur"), self.cmb_span)
        self.spn_w = self._bind(_spin(20, 500, 1, 1), "width_mm")
        self.spn_h = self._bind(_spin(20, 500, 1, 1), "height_mm")
        sec.add_row(tr("Taille (mm)"), row(self.spn_w, QLabel(tr("x")), self.spn_h))

        self.chk_transparent = self._bind(
            QCheckBox(tr("Fond transparent à l'export")), "transparent_bg")
        self.chk_hatch = self._bind(
            QCheckBox(tr("Motifs hachurés (impression N&B)")), "monochrome_hatch")
        sec.add_widget(self.chk_transparent)
        sec.add_widget(self.chk_hatch)

        self.colors_holder = QWidget()
        self.colors_layout = QVBoxLayout(self.colors_holder)
        self.colors_layout.setContentsMargins(0, 4, 0, 0)
        self.colors_layout.setSpacing(4)
        sec.add_widget(QLabel(tr("Couleurs des séries")))
        sec.add_widget(self.colors_holder)
        reset = QPushButton(tr("Réinitialiser les couleurs"))
        reset.setProperty("flat", True)
        reset.clicked.connect(self._reset_colors)
        sec.add_widget(reset)

    def _on_theme_changed(self, name: str):
        if name in THEMES:
            self.lbl_theme.setText(tr(THEMES[name].description))

    def _reset_colors(self):
        self.spec.custom_colors = {}
        self._color_buttons.clear()
        self.update_series([])
        self.changed.emit()

    def update_series(self, names: list[str], colors: list[str] | None = None):
        """Rebuild the per-series colour swatches after a render."""
        while self.colors_layout.count():
            item = self.colors_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._color_buttons.clear()
        colors = colors or []
        for i, name in enumerate(names[:12]):
            btn = ColorButton(self.spec.custom_colors.get(
                name, colors[i] if i < len(colors) else "#4C72B0"))
            btn.colorChanged.connect(self._push)
            self._color_buttons[name] = btn
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            hl.addWidget(btn)
            lab = QLabel(name)
            lab.setToolTip(name)
            hl.addWidget(lab, 1)
            self.colors_layout.addWidget(holder)
        if not names:
            self.colors_layout.addWidget(hint(tr("Aucune série.")))

    def _build_labels(self):
        sec = self._add(CollapsibleSection(tr("Titres et légende"), True))
        self.txt_title = self._bind(QLineEdit(), "title")
        self.txt_xlabel = self._bind(QLineEdit(), "xlabel")
        self.txt_ylabel = self._bind(QLineEdit(), "ylabel")
        sec.add_row(tr("Titre"), self.txt_title)
        sec.add_row(tr("Axe X"), self.txt_xlabel)
        sec.add_row(tr("Axe Y"), self.txt_ylabel)
        self.chk_legend = self._bind(QCheckBox(tr("Afficher la légende")),
                                     "show_legend")
        sec.add_widget(self.chk_legend)
        self.cmb_legend_loc = self._bind(QComboBox(), "legend_loc")
        self.fill(self.cmb_legend_loc, enums.LEGEND_LOC)
        sec.add_row(tr("Position"), self.cmb_legend_loc)
        self.txt_legend_title = self._bind(QLineEdit(), "legend_title")
        sec.add_row(tr("Titre légende"), self.txt_legend_title)
        self.spn_ncol = self._bind(_int_spin(1, 6), "legend_ncol")
        sec.add_row(tr("Colonnes"), self.spn_ncol)

    def _build_annotations(self):
        sec = self._add(CollapsibleSection(tr("Annotations libres"), False))
        self.lst_ann = QListWidget()
        self.lst_ann.setMaximumHeight(96)
        self.lst_ann.currentRowChanged.connect(self._load_annotation)
        sec.add_widget(self.lst_ann)

        self.ann_text = QLineEdit()
        self.ann_text.setPlaceholderText(tr("Texte de l'annotation"))
        self.ann_text.textEdited.connect(self._store_annotation)
        sec.add_row(tr("Texte"), self.ann_text)
        self.ann_x = _spin(-0.2, 1.2, 0.02, 2)
        self.ann_y = _spin(-0.2, 1.2, 0.02, 2)
        for widget in (self.ann_x, self.ann_y):
            widget.valueChanged.connect(self._store_annotation)
        sec.add_row(tr("Position X / Y"), row(self.ann_x, self.ann_y))
        self.ann_size = _spin(4, 36, 0.5, 1)
        self.ann_size.valueChanged.connect(self._store_annotation)
        sec.add_row(tr("Taille (pt)"), self.ann_size)
        self.ann_color = ColorButton("#000000")
        self.ann_color.colorChanged.connect(self._store_annotation)
        self.ann_bold = QCheckBox(tr("Gras"))
        self.ann_italic = QCheckBox(tr("Italique"))
        for widget in (self.ann_bold, self.ann_italic):
            widget.toggled.connect(self._store_annotation)
        sec.add_row(tr("Style"), row(self.ann_color, self.ann_bold,
                                 self.ann_italic))

        add = QPushButton(tr("Ajouter"))
        add.clicked.connect(self._add_annotation)
        remove = QPushButton(tr("Supprimer"))
        remove.clicked.connect(self._remove_annotation)
        sec.add_widget(row(add, remove))
        sec.add_widget(hint(tr("Coordonnées relatives aux axes : 0 = bord "
                            "gauche/bas, 1 = bord droit/haut.")))

    def _refresh_annotations(self, select: int = -1):
        self.lst_ann.blockSignals(True)
        self.lst_ann.clear()
        for ann in self.spec.annotations:
            data = ann if isinstance(ann, dict) else ann.__dict__
            self.lst_ann.addItem(data.get("text") or "(vide)")
        self.lst_ann.blockSignals(False)
        if self.lst_ann.count():
            self.lst_ann.setCurrentRow(
                select if 0 <= select < self.lst_ann.count() else 0)

    def _current_annotation(self) -> dict | None:
        i = self.lst_ann.currentRow()
        if 0 <= i < len(self.spec.annotations):
            ann = self.spec.annotations[i]
            if not isinstance(ann, dict):
                ann = ann.__dict__
                self.spec.annotations[i] = ann
            return ann
        return None

    def _load_annotation(self, *_):
        ann = self._current_annotation()
        if ann is None:
            return
        was, self._loading = self._loading, True
        self.ann_text.setText(ann.get("text", ""))
        self.ann_x.setValue(ann.get("x", 0.5))
        self.ann_y.setValue(ann.get("y", 0.95))
        self.ann_size.setValue(ann.get("size", 8.0))
        self.ann_color.setColor(ann.get("color", "#000000"))
        self.ann_bold.setChecked(bool(ann.get("bold")))
        self.ann_italic.setChecked(bool(ann.get("italic")))
        self._loading = was

    def _store_annotation(self, *_):
        if self._loading:
            return
        ann = self._current_annotation()
        if ann is None:
            return
        ann.update(text=self.ann_text.text(), x=self.ann_x.value(),
                   y=self.ann_y.value(), size=self.ann_size.value(),
                   color=self.ann_color.color(),
                   bold=self.ann_bold.isChecked(),
                   italic=self.ann_italic.isChecked())
        i = self.lst_ann.currentRow()
        if 0 <= i < self.lst_ann.count():
            self.lst_ann.item(i).setText(ann["text"] or "(vide)")
        self.changed.emit()

    def _add_annotation(self):
        self.spec.annotations.append(
            {"text": "Nouvelle annotation", "x": 0.5, "y": 0.95, "size": 8.0,
             "color": "#000000", "ha": "center", "bold": False,
             "italic": False})
        self._refresh_annotations(len(self.spec.annotations) - 1)
        self.changed.emit()

    def _remove_annotation(self):
        i = self.lst_ann.currentRow()
        if 0 <= i < len(self.spec.annotations):
            self.spec.annotations.pop(i)
            self._refresh_annotations(max(i - 1, 0))
            self.changed.emit()

    def _build_axes(self):
        sec = self._add(CollapsibleSection(tr("Axes"), False))
        self.f_xmin = self._bind(OptionalFloat(), "xmin")
        self.f_xmax = self._bind(OptionalFloat(), "xmax")
        self.f_ymin = self._bind(OptionalFloat(), "ymin")
        self.f_ymax = self._bind(OptionalFloat(), "ymax")
        sec.add_row(tr("X min / max"), row(self.f_xmin, self.f_xmax))
        sec.add_row(tr("Y min / max"), row(self.f_ymin, self.f_ymax))
        self.chk_logx = self._bind(QCheckBox(tr("Échelle log X")), "log_x")
        self.chk_logy = self._bind(QCheckBox(tr("Échelle log Y")), "log_y")
        sec.add_widget(row(self.chk_logx, self.chk_logy))
        self.chk_gridx = self._bind(QCheckBox(tr("Grille X")), "grid_x")
        self.chk_gridy = self._bind(QCheckBox(tr("Grille Y")), "grid_y")
        sec.add_widget(row(self.chk_gridx, self.chk_gridy))
        self.chk_minor = self._bind(QCheckBox(tr("Ticks mineurs")), "minor_ticks")
        self.chk_despine = self._bind(QCheckBox(tr("Retirer haut/droite")),
                                      "despine")
        sec.add_widget(row(self.chk_minor, self.chk_despine))
        self.spn_rot = self._bind(_spin(-90, 90, 5, 0), "tick_rotation")
        sec.add_row(tr("Rotation X"), self.spn_rot)
        self.chk_zero = self._bind(QCheckBox(tr("Barres ancrées à zéro")),
                                   "y_from_zero")
        sec.add_widget(self.chk_zero)

    def _build_series(self):
        sec = self._add(CollapsibleSection(tr("Apparence des séries"), False))
        self.spn_lw = self._bind(_spin(0, 8, 0.1, 2), "line_width")
        self.spn_lw.setSpecialValueText(tr("auto"))
        sec.add_row(tr("Épaisseur"), self.spn_lw)
        self.cmb_ls = self._bind(QComboBox(), "line_style")
        self.cmb_ls.addItems([str(s) for s in LINESTYLES if isinstance(s, str)])
        sec.add_row(tr("Style de trait"), self.cmb_ls)
        self.cmb_marker = self._bind(QComboBox(), "marker")
        self.cmb_marker.addItems(MARKERS)
        sec.add_row(tr("Symbole"), self.cmb_marker)
        self.spn_ms = self._bind(_spin(0, 20, 0.5, 1), "marker_size")
        self.spn_ms.setSpecialValueText(tr("auto"))
        sec.add_row(tr("Taille symbole"), self.spn_ms)
        self.chk_line = self._bind(QCheckBox(tr("Relier les points")), "show_line")
        self.chk_markers = self._bind(QCheckBox(tr("Afficher les symboles")),
                                      "show_markers")
        sec.add_widget(row(self.chk_line, self.chk_markers))
        self.spn_alpha = self._bind(_spin(0.05, 1.0, 0.05, 2), "alpha")
        sec.add_row(tr("Opacité"), self.spn_alpha)
        self.chk_connect = self._bind(
            QCheckBox(tr("Relier les moyennes (barres/box)")), "connect_means")
        sec.add_widget(self.chk_connect)

    def _build_error_points(self):
        sec = self._add(CollapsibleSection(tr("Erreurs et points"), True))
        self.cmb_error = self._bind(QComboBox(), "error_type")
        self.fill(self.cmb_error, enums.ERROR_TYPE)
        sec.add_row(tr("Barres d'erreur"), self.cmb_error)
        self.cmb_err_dir = self._bind(QComboBox(), "error_direction")
        self.fill(self.cmb_err_dir, enums.ERROR_DIRECTION)
        sec.add_row(tr("Direction"), self.cmb_err_dir)
        self.spn_cap = self._bind(_spin(0, 10, 0.5, 1), "error_capsize")
        self.spn_cap.setSpecialValueText(tr("auto"))
        sec.add_row(tr("Chapeaux"), self.spn_cap)
        self.chk_band = self._bind(QCheckBox(tr("Bande d'erreur (courbes)")),
                                   "error_band")
        sec.add_widget(self.chk_band)
        self.spn_fill = self._bind(_spin(0.02, 1.0, 0.02, 2), "fill_alpha")
        sec.add_row(tr("Opacité bande"), self.spn_fill)

        sec.add_widget(hint(tr("Points individuels")))
        self.chk_points = self._bind(QCheckBox(tr("Afficher les points")),
                                     "show_points")
        sec.add_widget(self.chk_points)
        self.cmb_pstyle = self._bind(QComboBox(), "point_style")
        self.fill(self.cmb_pstyle, enums.POINT_STYLE)
        sec.add_row(tr("Disposition"), self.cmb_pstyle)
        self.spn_psize = self._bind(_spin(0, 20, 0.5, 1), "point_size")
        self.spn_psize.setSpecialValueText(tr("auto"))
        sec.add_row(tr("Taille"), self.spn_psize)
        self.spn_palpha = self._bind(_spin(0.05, 1.0, 0.05, 2), "point_alpha")
        sec.add_row(tr("Opacité"), self.spn_palpha)
        self.spn_jitter = self._bind(_spin(0.0, 0.5, 0.01, 2), "jitter_width")
        sec.add_row(tr("Dispersion"), self.spn_jitter)
        self.chk_pedge = self._bind(QCheckBox(tr("Contour blanc")), "point_edge")
        sec.add_widget(self.chk_pedge)

    def _build_type_specific(self):
        sec = self._add(CollapsibleSection(tr("Options du type"), True))
        self.sec_specific = sec
        self.chk_bins_auto = self._bind(QCheckBox(tr("Classes automatiques")),
                                        "bins_auto")
        self.spn_bins = self._bind(_int_spin(2, 200), "bins")
        self.cmb_hstat = self._bind(QComboBox(), "hist_stat")
        self.fill(self.cmb_hstat, enums.HIST_STAT)
        self.chk_kde = self._bind(QCheckBox(tr("Courbe de densité (KDE)")),
                                  "hist_kde")
        self.chk_cum = self._bind(QCheckBox(tr("Cumulatif")), "hist_cumulative")
        self.chk_step = self._bind(QCheckBox(tr("Contour seul")), "hist_step")
        self.r_bins_auto = sec.add_row(tr("Classes auto"), self.chk_bins_auto)
        self.r_bins = sec.add_row(tr("Nombre de classes"), self.spn_bins)
        self.r_hstat = sec.add_row(tr("Statistique"), self.cmb_hstat)
        self.r_kde = sec.add_widget(self.chk_kde)
        self.r_cum = sec.add_widget(row(self.chk_cum, self.chk_step))

        self.spn_boxw = self._bind(_spin(0.1, 1.0, 0.05, 2), "box_width")
        self.chk_notch = self._bind(QCheckBox(tr("Encoche (IC médiane)")), "notch")
        self.chk_fliers = self._bind(QCheckBox(tr("Valeurs extrêmes")),
                                     "show_outliers")
        self.r_boxw = sec.add_row(tr("Largeur"), self.spn_boxw)
        self.r_notch = sec.add_widget(row(self.chk_notch, self.chk_fliers))

        self.cmb_vinner = self._bind(QComboBox(), "violin_inner")
        self.fill(self.cmb_vinner, enums.VIOLIN_INNER)
        self.cmb_vside = self._bind(QComboBox(), "violin_side")
        self.fill(self.cmb_vside, enums.VIOLIN_SIDE)
        self.spn_vbw = self._bind(_spin(0.0, 2.0, 0.05, 2), "violin_bw")
        self.spn_vbw.setSpecialValueText(tr("auto"))
        self.r_vinner = sec.add_row(tr("Intérieur"), self.cmb_vinner)
        self.r_vside = sec.add_row(tr("Côté"), self.cmb_vside)
        self.r_vbw = sec.add_row(tr("Lissage"), self.spn_vbw)

        self.spn_barw = self._bind(_spin(0.1, 1.0, 0.05, 2), "bar_width")
        self.chk_baredge = self._bind(QCheckBox(tr("Contour noir")), "bar_edge")
        self.chk_horiz = self._bind(QCheckBox(tr("Barres horizontales")),
                                    "horizontal")
        self.r_barw = sec.add_row(tr("Largeur barres"), self.spn_barw)
        self.r_baredge = sec.add_widget(row(self.chk_baredge, self.chk_horiz))
        self._build_survival_rows(sec)
        self._build_contingency_rows(sec)
        self._build_agreement_rows(sec)

    def _build_agreement_rows(self, sec):
        self.cmb_ba_view = self._bind(QComboBox(), "ba_view")
        self.fill(self.cmb_ba_view, enums.BA_VIEW)
        self.r_ba_view = sec.add_row(tr("Différence"), self.cmb_ba_view)
        self.chk_ba_ci = self._bind(
            QCheckBox(tr("IC 95 % du biais et des limites")), "ba_ci")
        self.r_ba_ci = sec.add_row(tr("Incertitude"), self.chk_ba_ci)

    def _build_contingency_rows(self, sec):
        self.cmb_cview = self._bind(QComboBox(), "contingency_view")
        self.fill(self.cmb_cview, enums.CONTINGENCY_VIEW)
        self.r_cview = sec.add_row(tr("Barres"), self.cmb_cview)

    def _build_survival_rows(self, sec):
        self.chk_surv_ci = self._bind(
            QCheckBox(tr("Bande de confiance 95 %")), "survival_ci")
        self.r_surv_ci = sec.add_row(tr("Incertitude"), self.chk_surv_ci)
        self.chk_censors = self._bind(
            QCheckBox(tr("Marquer les censures")), "show_censors")
        self.r_censors = sec.add_row(tr("Censures"), self.chk_censors)

    def _build_fit(self):
        sec = self._add(CollapsibleSection(tr("Ajustement de courbe"), False))
        self.sec_fit = sec
        self.cmb_fit = QComboBox()
        # connected before the binding: the comparison choices follow the
        # model before the spec is read back from the widgets
        self.cmb_fit.currentIndexChanged.connect(
            lambda *_: self._refill_compare())
        self._bind(self.cmb_fit, "fit_model")
        self.fill(self.cmb_fit, enums.FIT_MODEL)
        sec.add_row(tr("Modèle"), self.cmb_fit)
        self.cmb_fit_compare = self._bind(QComboBox(), "fit_compare")
        sec.add_row(tr("Comparer"), self.cmb_fit_compare)
        self.hint_compare = hint(
            tr("Test F, comme Prism : la même courbe avec ce paramètre commun "
               "à toutes les séries s'ajuste-t-elle nettement moins bien ? "
               "Calculé sur chaque réplicat."))
        sec.add_widget(self.hint_compare)
        self._refill_compare()
        self.chk_fit_ci = self._bind(QCheckBox(tr("Bande de confiance 95 %")),
                                     "fit_ci")
        self.chk_fit_eq = self._bind(QCheckBox(tr("Afficher équation et R2")),
                                     "fit_show_equation")
        self.chk_fit_ext = self._bind(QCheckBox(tr("Extrapoler")),
                                      "fit_extrapolate")
        sec.add_widget(self.chk_fit_ci)
        sec.add_widget(self.chk_fit_eq)
        sec.add_widget(self.chk_fit_ext)
        self.cmb_eqloc = self._bind(QComboBox(), "fit_equation_loc")
        self.fill(self.cmb_eqloc, enums.EQUATION_LOC)
        sec.add_row(tr("Position équation"), self.cmb_eqloc)
        sec.add_widget(hint(tr("L'ajustement est calculé série par série, sur chaque "
                "réplicat comme Prism : les points tracés restent les "
                "moyennes.")))

    def _refill_compare(self, keep: str | None = None):
        """Offer the parameters of the chosen model, keeping the choice."""
        combo = getattr(self, "cmb_fit_compare", None)
        if combo is None:                    # still building the panel
            return
        if keep is None:
            keep = combo.currentData() or ""
        model = fitting.MODELS.get(self.cmb_fit.currentData() or "none")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr("Ne pas comparer"), "")
        if model is not None and model.func is not None:
            combo.addItem(tr("Une seule courbe pour toutes les séries ?"),
                          fitting.ONE_CURVE)
            for name in model.params:
                combo.addItem(tr("{param} différent entre les séries ?"
                                 ).format(param=tr(name)), name)
        index = combo.findData(keep)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)
        self.hint_compare.setVisible(bool(combo.currentData()))

    def _build_stats(self):
        sec = self._add(CollapsibleSection(tr("Statistiques"), True))
        self.sec_stats = sec
        self.chk_stats = self._bind(
            QCheckBox(tr("Comparaisons et annotations")), "stats_enabled")
        sec.add_widget(self.chk_stats)
        self.cmb_test = self._bind(QComboBox(), "stats_test")
        self.fill(self.cmb_test, enums.STATS_TEST)
        sec.add_row(tr("Test"), self.cmb_test)
        # a table of counts has its own tests: one picker or the other shows
        self.cmb_ctest = self._bind(QComboBox(), "contingency_test")
        self.fill(self.cmb_ctest, enums.CONTINGENCY_TEST)
        sec.add_row(tr("Test"), self.cmb_ctest)
        self.cmb_mode = self._bind(QComboBox(), "stats_mode")
        self.fill(self.cmb_mode, enums.STATS_MODE)
        sec.add_row(tr("Comparaisons"), self.cmb_mode)
        self.cmb_control = self._bind(QComboBox(), "stats_control")
        sec.add_row(tr("Contrôle"), self.cmb_control)
        self.cmb_pair = self._bind(QComboBox(), "stats_pair_by")
        self.r_pair = sec.add_row(tr("Appariement"), self.cmb_pair)
        self.hint_pair = hint(
            tr("Colonne identifiant le sujet mesuré plusieurs fois. "
            "Obligatoire en format long pour un test apparié ; en format "
            "large, la ligne du tableau sert d'appariement."))
        sec.add_widget(self.hint_pair)
        self.cmb_corr = self._bind(QComboBox(), "stats_correction")
        self.fill(self.cmb_corr, enums.CORRECTION)
        sec.add_row(tr("Correction"), self.cmb_corr)
        self.cmb_format = self._bind(QComboBox(), "stats_format")
        self.fill(self.cmb_format, enums.STATS_FORMAT)
        sec.add_row(tr("Affichage"), self.cmb_format)
        self.chk_hide_ns = self._bind(QCheckBox(tr("Masquer les non significatifs")),
                                      "stats_hide_ns")
        sec.add_widget(self.chk_hide_ns)
        self.spn_gap = self._bind(_spin(0.02, 0.3, 0.01, 2),
                                  "stats_bracket_gap")
        sec.add_row(tr("Écart des barres"), self.spn_gap)
        sec.add_widget(hint(
            tr("Auto choisit t de Student / Welch / Mann-Whitney selon la "
            "normalité (Shapiro) et l'égalité des variances (Levene). "
            "Dunnett exige un groupe contrôle ; l'ANOVA à mesures répétées "
            "exige une colonne d'appariement.")))

    def set_group_labels(self, labels: list[str]):
        """Feed the control-group combo after each render."""
        current = self.spec.stats_control
        self.cmb_control.blockSignals(True)
        self.cmb_control.clear()
        self.cmb_control.addItem("")
        self.cmb_control.addItems(labels)
        idx = self.cmb_control.findText(current)
        self.cmb_control.setCurrentIndex(max(idx, 0))
        self.cmb_control.blockSignals(False)

    # ------------------------------------------------------------------
    def _sync_enabled(self):
        """Show only what the current plot type can use."""
        if not hasattr(self, "sec_stats"):    # still building
            return
        t = self.spec.plot_type
        xy = t in ("line", "scatter")
        cat = t in ("bar", "box", "violin", "paired")
        hist = t == "histogram"
        surv = t == "survival"
        ct = t == "contingency"

        self.lbl_x.setVisible(xy or surv)
        self.lbl_x.setText(tr("Temps de suivi") if surv else tr("Axe X"))
        self.cmb_x.setVisible(xy or surv)
        self._set_row_visible(self.r_y, not surv)
        self._set_row_visible(self.r_event, surv)
        self.hint_event.setVisible(surv)
        for widget in (self.r_surv_ci, self.r_censors):
            self._set_row_visible(widget, surv)
        self.cmb_subgroup.setVisible(t in ("bar", "contingency"))
        self.hint_counts.setVisible(ct)
        self._set_row_visible(self.r_cview, ct)
        for widget in (self.r_ba_view, self.r_ba_ci):
            self._set_row_visible(widget, t == "bland_altman")
        ba = t == "bland_altman"
        for picker, shown in ((self.cmb_test, not ct and not ba),
                              (self.cmb_ctest, ct)):
            picker.setVisible(shown)
            label = self.sec_stats.form.labelForField(picker)
            if label is not None:
                label.setVisible(shown)
        for widget in (self.r_err_cols, self.hint_err):
            widget.setVisible(xy)
            label = self.sec_data.form.labelForField(widget)
            if label is not None:
                label.setVisible(xy)
        self.sec_fit.setVisible(xy)
        self.hint_compare.setVisible(bool(self.spec.fit_compare))
        # Bland-Altman has no test to choose, but needs the pairing row
        self.sec_stats.setVisible(cat or surv or ct or t == "bland_altman")
        for widget in (self.chk_stats, self.cmb_mode, self.cmb_control,
                       self.cmb_corr, self.cmb_format, self.chk_hide_ns,
                       self.spn_gap):
            widget.setVisible(t != "bland_altman")
            label = self.sec_stats.form.labelForField(widget)
            if label is not None:
                label.setVisible(t != "bland_altman")
        # on a survival plot the only statistic is the log-rank, so the test
        # pickers have nothing to offer
        for widget in (self.cmb_test, self.cmb_mode, self.cmb_control,
                       self.cmb_format, self.chk_hide_ns, self.spn_gap):
            widget.setEnabled(not surv)

        for w in (self.r_bins_auto, self.r_bins, self.r_hstat, self.r_kde,
                  self.r_cum):
            self._set_row_visible(w, hist)
        self.spn_bins.setEnabled(not self.spec.bins_auto)
        for w in (self.r_boxw, self.r_notch):
            self._set_row_visible(w, t == "box")
        for w in (self.r_vinner, self.r_vside, self.r_vbw):
            self._set_row_visible(w, t == "violin")
        for w in (self.r_barw, self.r_baredge):
            self._set_row_visible(w, t in ("bar", "contingency"))
        self.chk_horiz.setEnabled(t == "bar")

        self.chk_band.setEnabled(t == "line")
        self.spn_fill.setEnabled(t == "line" and self.spec.error_band)
        self.chk_line.setEnabled(xy)
        self.chk_markers.setEnabled(xy)
        self.cmb_ls.setEnabled(xy)
        # before-after points sit on their condition so the lines reach them
        scattered = self.spec.show_points and cat and t != "paired"
        self.cmb_pstyle.setEnabled(scattered)
        self.spn_jitter.setEnabled(scattered)
        self.cmb_control.setEnabled(
            self.spec.stats_mode == "vs_control")
        # a before-after or Bland-Altman plot needs the subject column to
        # match its measurements, whatever the test
        is_paired = ((self.spec.stats_test in PAIRED_TESTS and not ct)
                     or t in ("paired", "bland_altman"))
        for widget in (self.r_pair, self.hint_pair):
            widget.setVisible(is_paired)
            label = self.sec_stats.form.labelForField(widget)
            if label is not None:
                label.setVisible(is_paired)
        self.spn_w.setEnabled(self.spec.span == "custom")
        self.spn_h.setEnabled(self.spec.span == "custom")
        self.chk_zero.setEnabled(t == "bar")
        self.chk_connect.setEnabled(cat)

    def _set_row_visible(self, widget, visible: bool):
        widget.setVisible(visible)
        form = self.sec_specific.form
        label = form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)
