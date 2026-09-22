"""Reusable widgets: vector icons, collapsible sections, colour picker, etc."""
from __future__ import annotations

from PyQt6.QtCore import (QEvent, QObject, QPointF, QRect, QRectF, QSize, Qt,
                          pyqtSignal)
from PyQt6.QtGui import (QColor, QFont, QIcon, QPainter, QPainterPath, QPen,
                         QPixmap, QPolygonF)
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFormLayout,
                             QFrame, QHBoxLayout, QHeaderView, QLabel,
                             QListWidget, QListWidgetItem, QPushButton,
                             QSizePolicy, QToolButton, QToolTip, QVBoxLayout,
                             QWidget)


# --------------------------------------------------------------------------
# Icons drawn at runtime: no binary assets, crisp at any DPI
# --------------------------------------------------------------------------
def _pen(painter: QPainter, color: QColor, width: float = 1.7):
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


#: Current stroke colour for generated icons; follows the UI theme.
ICON_COLOR = "#1C2430"


def set_icon_color(color: str):
    global ICON_COLOR
    ICON_COLOR = color


def make_icon(name: str, color: str = "", size: int = 22) -> QIcon:
    """Minimal line-art icon set drawn with QPainter."""
    color = color or ICON_COLOR
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(color)
    col_fill = QColor(col)
    col_fill.setAlpha(90)
    _pen(p, col)
    s = size
    m = s * 0.18          # margin

    if name == "open":
        p.drawPolyline(QPolygonF([QPointF(m, s - m), QPointF(m, m * 1.6),
                                  QPointF(s * 0.44, m * 1.6),
                                  QPointF(s * 0.55, m * 2.6),
                                  QPointF(s - m, m * 2.6)]))
        p.drawLine(QPointF(m, s - m), QPointF(s - m * 0.6, s - m))
        p.drawLine(QPointF(s - m, m * 2.6), QPointF(s - m * 0.6, s - m))
    elif name == "save":
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 3, 3)
        p.drawRect(QRectF(s * 0.34, m, s * 0.32, s * 0.24))
        p.drawRect(QRectF(s * 0.30, s * 0.56, s * 0.40, s * 0.26))
    elif name == "import":
        p.drawLine(QPointF(s / 2, m), QPointF(s / 2, s * 0.62))
        p.drawPolyline(QPolygonF([QPointF(s * 0.30, s * 0.44),
                                  QPointF(s / 2, s * 0.64),
                                  QPointF(s * 0.70, s * 0.44)]))
        p.drawPolyline(QPolygonF([QPointF(m, s * 0.74), QPointF(m, s - m),
                                  QPointF(s - m, s - m),
                                  QPointF(s - m, s * 0.74)]))
    elif name == "export":
        p.drawLine(QPointF(s / 2, s * 0.62), QPointF(s / 2, m))
        p.drawPolyline(QPolygonF([QPointF(s * 0.30, s * 0.30),
                                  QPointF(s / 2, m),
                                  QPointF(s * 0.70, s * 0.30)]))
        p.drawPolyline(QPolygonF([QPointF(m, s * 0.74), QPointF(m, s - m),
                                  QPointF(s - m, s - m),
                                  QPointF(s - m, s * 0.74)]))
    elif name == "plus":
        p.drawLine(QPointF(s / 2, m), QPointF(s / 2, s - m))
        p.drawLine(QPointF(m, s / 2), QPointF(s - m, s / 2))
    elif name == "copy":
        p.drawRoundedRect(QRectF(m, m, s * 0.50, s * 0.50), 3, 3)
        p.drawRoundedRect(QRectF(s * 0.32, s * 0.32, s * 0.50, s * 0.50), 3, 3)
    elif name == "duplicate":
        # a sheet and a plus: "make me another one". The two overlapping
        # sheets of "copy" stay with the clipboard action, where every other
        # program puts them.
        p.drawRoundedRect(QRectF(m, m, s * 0.50, s * 0.50),
                          s * 0.09, s * 0.09)
        cx, cy, arm = s * 0.79, s * 0.79, s * 0.15
        _pen(p, col, 2.1)          # a hair bolder, or it fades at 17 px
        p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
        _pen(p, col)
    elif name == "trash":
        p.drawLine(QPointF(m, s * 0.28), QPointF(s - m, s * 0.28))
        p.drawPolyline(QPolygonF([QPointF(s * 0.26, s * 0.28),
                                  QPointF(s * 0.30, s - m),
                                  QPointF(s * 0.70, s - m),
                                  QPointF(s * 0.74, s * 0.28)]))
        p.drawLine(QPointF(s * 0.38, s * 0.20), QPointF(s * 0.62, s * 0.20))
    elif name == "bar":
        for i, h in enumerate((0.45, 0.72, 0.30)):
            x = m + i * (s - 2 * m) / 3 + 1
            p.drawRect(QRectF(x, s - m - h * (s - 2 * m),
                              (s - 2 * m) / 3 - 2.5, h * (s - 2 * m)))
    elif name == "line":
        p.drawPolyline(QPolygonF([QPointF(m, s * 0.70), QPointF(s * 0.38, s * 0.42),
                                  QPointF(s * 0.58, s * 0.56),
                                  QPointF(s - m, s * 0.24)]))
    elif name == "scatter":
        p.setBrush(col)
        for x, y in ((0.28, 0.66), (0.46, 0.40), (0.64, 0.58), (0.78, 0.30)):
            p.drawEllipse(QPointF(s * x, s * y), 2.0, 2.0)
    elif name == "box":
        p.drawRect(QRectF(s * 0.30, s * 0.36, s * 0.40, s * 0.32))
        p.drawLine(QPointF(s * 0.30, s * 0.52), QPointF(s * 0.70, s * 0.52))
        p.drawLine(QPointF(s / 2, m), QPointF(s / 2, s * 0.36))
        p.drawLine(QPointF(s / 2, s * 0.68), QPointF(s / 2, s - m))
    elif name == "violin":
        path = QPainterPath(QPointF(s / 2, m))
        path.cubicTo(QPointF(s * 0.88, s * 0.40), QPointF(s * 0.80, s * 0.70),
                     QPointF(s / 2, s - m))
        path.cubicTo(QPointF(s * 0.20, s * 0.70), QPointF(s * 0.12, s * 0.40),
                     QPointF(s / 2, m))
        p.drawPath(path)
    elif name == "histogram":
        for i, h in enumerate((0.25, 0.55, 0.80, 0.45, 0.20)):
            w = (s - 2 * m) / 5
            p.drawRect(QRectF(m + i * w, s - m - h * (s - 2 * m), w,
                              h * (s - 2 * m)))
    elif name == "stats":
        p.drawLine(QPointF(m, s * 0.30), QPointF(s - m, s * 0.30))
        p.drawLine(QPointF(m, s * 0.30), QPointF(m, s * 0.44))
        p.drawLine(QPointF(s - m, s * 0.30), QPointF(s - m, s * 0.44))
        f = QFont()
        f.setPointSizeF(s * 0.42)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, s * 0.34, s, s * 0.60),
                   int(Qt.AlignmentFlag.AlignCenter), "*")
    elif name == "table":
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 3, 3)
        p.drawLine(QPointF(m, s * 0.40), QPointF(s - m, s * 0.40))
        p.drawLine(QPointF(s * 0.44, m), QPointF(s * 0.44, s - m))
    elif name == "composite":
        # Four separate tiles with the first one filled: a figure made of
        # panels, and nothing like the single framed grid of "table".
        side = (s - 2 * m) * 0.44
        gap = (s - 2 * m) - 2 * side
        for row in range(2):
            for column in range(2):
                rect = QRectF(m + column * (side + gap),
                              m + row * (side + gap), side, side)
                p.setBrush(col_fill if (row, column) == (0, 0)
                           else Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect, 2, 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "theme":
        p.setBrush(col)
        p.drawEllipse(QPointF(s * 0.38, s * 0.40), s * 0.16, s * 0.16)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(s * 0.62, s * 0.60), s * 0.20, s * 0.20)
    elif name == "refresh":
        p.drawArc(QRectF(m, m, s - 2 * m, s - 2 * m), 40 * 16, 280 * 16)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(s * 0.70, m * 0.9),
                                 QPointF(s * 0.92, s * 0.32),
                                 QPointF(s * 0.62, s * 0.36)]))
    elif name == "fit":
        p.drawPolyline(QPolygonF([QPointF(m, s - m), QPointF(s * 0.40, s * 0.52),
                                  QPointF(s - m, m * 1.3)]))
        p.setBrush(col)
        for x, y in ((0.30, 0.74), (0.52, 0.48), (0.74, 0.30)):
            p.drawEllipse(QPointF(s * x, s * y), 1.8, 1.8)
    else:
        p.drawEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))
    p.end()
    return QIcon(pm)


PLOT_ICONS = {"line": "line", "scatter": "scatter", "histogram": "histogram",
              "box": "box", "violin": "violin", "bar": "bar"}


def tag_icon(target, name: str):
    """Attach an icon and remember which one, so themes can redraw it."""
    target.setProperty("icon_name", name)
    target.setIcon(make_icon(name))
    return target


def refresh_icons(root):
    """Redraw every tagged icon under `root` with the current ICON_COLOR."""
    from PyQt6.QtGui import QAction as _QAction
    for widget in root.findChildren(QToolButton):
        name = widget.property("icon_name")
        if name:
            widget.setIcon(make_icon(name))
    for action in root.findChildren(_QAction):
        name = action.property("icon_name")
        if name:
            action.setIcon(make_icon(name))


# --------------------------------------------------------------------------
# Layout helpers
# --------------------------------------------------------------------------
def hline() -> QFrame:
    f = QFrame()
    f.setProperty("hline", True)
    f.setFixedHeight(1)
    return f


def section_label(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setProperty("section", True)
    return lab


def hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("hint", True)
    lab.setWordWrap(True)
    return lab


class CollapsibleSection(QWidget):
    """A titled block that folds away, used all over the inspector."""

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, expanded: bool = True, icon: str = "",
                 parent=None):
        super().__init__(parent)
        self._button = QToolButton()
        self._button.setText(f"  {title}")
        self._button.setCheckable(True)
        self._button.setChecked(expanded)
        self._button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._button.setArrowType(Qt.ArrowType.DownArrow if expanded
                                  else Qt.ArrowType.RightArrow)
        self._button.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Fixed)
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.setStyleSheet(
            "QToolButton { border: none; background: transparent;"
            " font-weight: 700; font-size: 12px; padding: 7px 2px;"
            " text-align: left; letter-spacing: 0.3px; }")
        self._button.clicked.connect(self._on_toggle)

        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setContentsMargins(6, 2, 4, 10)
        self.form.setSpacing(7)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight
                                    | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.body.setVisible(expanded)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._button)
        lay.addWidget(self.body)
        lay.addWidget(hline())

    def _on_toggle(self, checked: bool):
        self.body.setVisible(checked)
        self._button.setArrowType(Qt.ArrowType.DownArrow if checked
                                  else Qt.ArrowType.RightArrow)
        self.toggled.emit(checked)

    # -- convenience -------------------------------------------------------
    def add_row(self, label: str, widget: QWidget):
        self.form.addRow(label, widget)
        return widget

    def add_widget(self, widget: QWidget):
        self.form.addRow(widget)
        return widget

    def set_expanded(self, expanded: bool):
        self._button.setChecked(expanded)
        self._on_toggle(expanded)


class ColorButton(QPushButton):
    """A swatch that opens a colour dialog."""

    colorChanged = pyqtSignal(str)

    def __init__(self, color: str = "#4C72B0", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(QSize(34, 22))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        # Only the first fragment was an f-string, so its doubled brace came
        # out literal and Qt rejected the whole sheet: the swatch lost its
        # colour. One f-string, escaped throughout.
        self.setStyleSheet(
            f"QPushButton {{ background: {self._color};"
            f" border: 1px solid rgba(0, 0, 0, 0.25);"
            f" border-radius: 5px; }}"
            f" QPushButton:hover {{ border: 2px solid #2D6CDF; }}")

    def color(self) -> str:
        return self._color

    def setColor(self, color: str):
        if color and color != self._color:
            self._color = color
            self._refresh()

    def _pick(self):
        col = QColorDialog.getColor(QColor(self._color), self,
                                    "Couleur de la serie")
        if col.isValid():
            self.setColor(col.name())
            self.colorChanged.emit(self._color)


class PaletteCombo(QComboBox):
    """Combo box that previews each palette as a strip of swatches."""

    def __init__(self, palettes: dict, parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(72, 14))
        for name, colors in palettes.items():
            self.addItem(self._swatch(colors), name)

    @staticmethod
    def _swatch(colors: list[str], w: int = 72, h: int = 14) -> QIcon:
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = min(len(colors), 8)
        step = w / n
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            p.setBrush(QColor(colors[i]))
            p.drawRoundedRect(QRectF(i * step + 0.5, 1, step - 1.5, h - 2),
                              2, 2)
        p.end()
        return QIcon(pm)


class CheckList(QListWidget):
    """Multi-selection list with checkboxes (used to pick Y columns)."""

    changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.setAlternatingRowColors(False)
        self.setMaximumHeight(160)
        self.itemChanged.connect(self._emit)
        self._muted = False

    def set_items(self, items: list[str], checked: list[str] | None = None):
        self._muted = True
        self.clear()
        checked = set(checked or [])
        for text in items:
            it = QListWidgetItem(text)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if text in checked
                             else Qt.CheckState.Unchecked)
            self.addItem(it)
        self._muted = False

    def checked_items(self) -> list[str]:
        return [self.item(i).text() for i in range(self.count())
                if self.item(i).checkState() == Qt.CheckState.Checked]

    def set_checked(self, values: list[str]):
        self._muted = True
        values = set(values)
        for i in range(self.count()):
            it = self.item(i)
            it.setCheckState(Qt.CheckState.Checked if it.text() in values
                             else Qt.CheckState.Unchecked)
        self._muted = False

    def _emit(self, *_):
        if not self._muted:
            self.changed.emit(self.checked_items())


class Toggle(QCheckBox):
    """Checkbox with a compact inline description."""

    def __init__(self, text: str, tooltip: str = "", checked: bool = False,
                 parent=None):
        super().__init__(text, parent)
        self.setChecked(checked)
        if tooltip:
            self.setToolTip(tooltip)


def row(*widgets, spacing: int = 6, stretch_last: bool = False) -> QWidget:
    """Pack widgets horizontally into a transparent container."""
    holder = QWidget()
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for w in widgets:
        lay.addWidget(w)
    if not stretch_last:
        lay.addStretch(1)
    return holder


# --------------------------------------------------------------------------
# Tooltips that keep up with the pointer
# --------------------------------------------------------------------------
class _SectionTips(QObject):
    """Bind a header tooltip to the section it describes.

    Qt asks the model for a header tooltip and shows it with no area
    attached, so the bubble keeps the previous column's text while the
    pointer is already over the next one, and only a timeout clears it.
    Handing QToolTip the section rectangle makes Qt refresh it the moment
    the pointer crosses into another section, and hide it on the way out.
    """

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.ToolTip:
            return False
        header = obj if isinstance(obj, QHeaderView) else obj.parent()
        if not isinstance(header, QHeaderView):
            return False
        position = event.pos()
        index = header.logicalIndexAt(position)
        text = ""
        if index >= 0 and header.model() is not None:
            value = header.model().headerData(
                index, header.orientation(), Qt.ItemDataRole.ToolTipRole)
            text = "" if value is None else str(value)
        if not text:
            QToolTip.hideText()
            event.ignore()
            return True
        start = header.sectionViewportPosition(index)
        size = header.sectionSize(index)
        if header.orientation() == Qt.Orientation.Horizontal:
            rect = QRect(start, 0, size, header.height())
        else:
            rect = QRect(0, start, header.width(), size)
        QToolTip.showText(event.globalPos(), text, header, rect)
        return True


def follow_sections(header: QHeaderView) -> _SectionTips:
    """Make `header` refresh its tooltip as the pointer changes section.

    The caller must keep the returned filter: a parent is not enough, PyQt
    collects the Python half and Qt is then left with a plain QObject whose
    eventFilter does nothing at all.
    """
    guard = _SectionTips(header)
    header.setMouseTracking(True)
    header.installEventFilter(guard)
    header.viewport().installEventFilter(guard)
    return guard
