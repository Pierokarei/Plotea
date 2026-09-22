"""Figure preview: a matplotlib canvas shown as a page, with crisp zoom.

Zooming raises the figure DPI instead of scaling a bitmap, so the preview
stays sharp and matches what the exported file will look like.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QScrollArea,
                             QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..core import export, panel as panel_mod, plotting
from ..core.plotspec import PlotSpec
from ..core.themes import get_theme

ZOOM_STEPS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
BASE_DPI = 96.0


class PlotCanvas(QWidget):
    """Renders a PlotSpec and shows it as a physical page on a grey desk."""

    rendered = pyqtSignal(object)        # RenderInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(3.5, 2.7), dpi=BASE_DPI)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Fixed,
                                  QSizePolicy.Policy.Fixed)
        self._zoom = 1.0
        self._fit = True
        self._spec: PlotSpec | None = None
        self._panel = None
        self._df = None
        self.last_info = None

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(140)
        self._resize_timer.timeout.connect(self.refresh)

        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(24, 24, 24, 24)
        hl.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll.setWidget(holder)
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A figure is sized in millimetres and can become large. Expanding
        # takes the room left over, while the small explicit minimum stops the
        # preview from claiming space back from the side panels and cutting
        # their labels off.
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Expanding)
        # A constant floor, unrelated to the figure: the preview keeps a
        # usable width and the panels never have to give theirs back.
        self.scroll.setMinimumSize(420, 260)
        self.set_desk_color("#EDEFF2")

        self.size_label = QLabel()
        self.size_label.setProperty("hint", True)
        self.size_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Preferred)
        self.zoom_box = QComboBox()
        self.zoom_box.addItem("Ajuster")
        for z in ZOOM_STEPS:
            self.zoom_box.addItem(f"{int(z * 100)} %")
        self.zoom_box.setCurrentIndex(0)
        self.zoom_box.setFixedWidth(96)
        self.zoom_box.currentIndexChanged.connect(self._zoom_changed)

        minus = QToolButton()
        minus.setText("-")
        minus.setToolTip("Dezoomer")
        minus.clicked.connect(lambda: self._step_zoom(-1))
        plus = QToolButton()
        plus.setText("+")
        plus.setToolTip("Zoomer")
        plus.clicked.connect(lambda: self._step_zoom(1))

        self.action_bar = QWidget()
        bar = QHBoxLayout(self.action_bar)
        bar.setContentsMargins(10, 6, 10, 6)
        bar.setSpacing(6)
        # The label takes the leftover room and clips its own text there, so
        # the zoom controls keep their size on a narrow window.
        bar.addWidget(self.size_label, 1)
        bar.addWidget(minus)
        bar.addWidget(self.zoom_box)
        bar.addWidget(plus)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.action_bar)

    def set_desk_color(self, color: str):
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background: {color}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {color}; }}")

    # -- rendering ----------------------------------------------------------
    def render_spec(self, spec: PlotSpec, df):
        self._spec = spec
        self._panel = None
        self._df = df
        theme = get_theme(spec.theme)
        if spec.span == "custom":
            w_mm, h_mm = spec.width_mm, spec.height_mm
        else:
            w_in, h_in = theme.figsize(spec.span)
            w_mm, h_mm = w_in * 25.4, h_in * 25.4
            spec.width_mm, spec.height_mm = round(w_mm, 1), round(h_mm, 1)

        self._compute_zoom(w_mm, h_mm)
        # Let matplotlib own the widget geometry: it sizes itself from
        # figsize x dpi, so zooming by DPI keeps the preview sharp.
        self.figure.set_dpi(BASE_DPI * self._zoom)
        self.figure.set_size_inches(max(w_mm, 20) / 25.4,
                                    max(h_mm, 20) / 25.4, forward=True)
        self.canvas.updateGeometry()

        info = plotting.render(self.figure, spec, df)
        self.last_info = info
        self.canvas.draw()
        self.size_label.setText(
            f"{w_mm:.0f} x {h_mm:.0f} mm   |   thème {spec.theme}"
            f"   |   zoom {self._zoom * 100:.0f} %")
        self.rendered.emit(info)
        return info

    def render_panel(self, panel, specs: dict, frames: dict):
        """Draw a multi-panel figure at its physical size."""
        self._spec = None
        self._panel = (panel, specs, frames)
        w_mm, h_mm = panel.size_mm()
        panel.width_mm, panel.height_mm = round(w_mm, 1), round(h_mm, 1)
        self._compute_zoom(w_mm, h_mm)
        self.figure.set_dpi(BASE_DPI * self._zoom)
        self.figure.set_size_inches(max(w_mm, 20) / 25.4,
                                    max(h_mm, 20) / 25.4, forward=True)
        self.canvas.updateGeometry()
        info = panel_mod.render_panel(self.figure, panel, specs, frames)
        self.last_info = info
        self.canvas.draw()
        self.size_label.setText(
            f"{w_mm:.0f} x {h_mm:.0f} mm   |   {info.drawn} panneau(x)"
            f"   |   zoom {self._zoom * 100:.0f} %")
        self.rendered.emit(info)
        return info

    def refresh(self):
        if self._spec is not None:
            self.render_spec(self._spec, self._df)
        elif self._panel is not None:
            self.render_panel(*self._panel)

    # -- zoom ---------------------------------------------------------------
    def _zoom_changed(self, index: int):
        self._fit = index == 0
        if index > 0:
            self._zoom = ZOOM_STEPS[index - 1]
        self.refresh()

    def _step_zoom(self, direction: int):
        idx = min(range(len(ZOOM_STEPS)),
                  key=lambda i: abs(ZOOM_STEPS[i] - self._zoom))
        idx = max(0, min(len(ZOOM_STEPS) - 1, idx + direction))
        self.zoom_box.setCurrentIndex(idx + 1)

    def _compute_zoom(self, w_mm: float, h_mm: float):
        if not self._fit:
            return
        w_in, h_in = max(w_mm, 20) / 25.4, max(h_mm, 20) / 25.4
        avail_w = max(self.scroll.viewport().width() - 64, 140)
        avail_h = max(self.scroll.viewport().height() - 64, 140)
        self._zoom = max(min(avail_w / (w_in * BASE_DPI),
                             avail_h / (h_in * BASE_DPI), 4.0), 0.2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit and self._spec is not None:
            self._resize_timer.start()

    # -- clipboard ----------------------------------------------------------
    def copy_to_clipboard(self, dpi: int = 300):
        data = export.figure_to_png_bytes(self.figure, dpi=dpi)
        image = QImage.fromData(data, "PNG")
        QGuiApplication.clipboard().setImage(image)

    def copy_svg_to_clipboard(self):
        QGuiApplication.clipboard().setText(
            export.figure_to_svg_text(self.figure))
