"""Qt stylesheet: a clean light/dark theme shared by every widget."""
from __future__ import annotations

import sys

LIGHT = {
    "bg": "#F5F6F8",
    "surface": "#FFFFFF",
    "surface_alt": "#FAFBFC",
    "border": "#DFE3E8",
    "border_strong": "#C6CCD4",
    "text": "#1C2430",
    "text_dim": "#6B7684",
    "accent": "#2D6CDF",
    "accent_hover": "#1F59C4",
    "accent_soft": "#E8F0FE",
    "danger": "#D9484A",
    "danger_soft": "#FCEBEB",
    "ok": "#17885C",
    "canvas": "#EDEFF2",
}

DARK = {
    "bg": "#1B1E24",
    "surface": "#23272F",
    "surface_alt": "#282D36",
    "border": "#343A44",
    "border_strong": "#454C58",
    "text": "#E6E9EF",
    "text_dim": "#98A1AE",
    "accent": "#5B93F5",
    "accent_hover": "#77A7FF",
    "accent_soft": "#2A3448",
    "danger": "#E4645F",
    "danger_soft": "#3A2A2C",
    "ok": "#3FBF8B",
    "canvas": "#15171C",
}


def ui_font() -> str:
    if sys.platform == "darwin":
        return "-apple-system, 'SF Pro Text', 'Helvetica Neue'"
    if sys.platform.startswith("win"):
        return "'Segoe UI Variable Text', 'Segoe UI'"
    return "'Inter', 'Cantarell', 'Ubuntu', 'DejaVu Sans'"


def build_qss(dark: bool = False, dock_icons: dict | None = None) -> str:
    c = DARK if dark else LIGHT
    font = ui_font()
    icons = dock_icons or {}
    docks = _dock_rules(c, icons)
    arrows = _arrow_rules(icons)
    return f"""
* {{
    font-family: {font};
    font-size: 13px;
}}
QWidget {{
    background: {c['bg']};
    color: {c['text']};
}}
QMainWindow, QDialog {{ background: {c['bg']}; }}

/* ---------- menu & toolbar ---------- */
QMenuBar {{
    background: {c['surface']};
    border-bottom: 1px solid {c['border']};
    padding: 2px 4px;
}}
QMenuBar::item {{ padding: 5px 11px; border-radius: 6px; background: transparent; }}
QMenuBar::item:selected {{ background: {c['accent_soft']}; color: {c['accent']}; }}
QMenu {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 26px 6px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['accent_soft']}; color: {c['accent']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}

QToolBar {{
    background: {c['surface']};
    border-bottom: 1px solid {c['border']};
    padding: 5px 8px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    padding: 5px 8px;
    margin: 0 1px;
    border-radius: 7px;
    color: {c['text']};
    font-weight: 500;
}}
QToolBar QToolButton:hover {{ background: {c['accent_soft']}; color: {c['accent']}; }}
QToolBar QToolButton:pressed {{ background: {c['border']}; }}
QToolBar::separator {{ width: 1px; background: {c['border']}; margin: 4px 5px; }}

/* ---------- panels ---------- */
QDockWidget {{
    color: {c['text']};
    font-weight: 600;
}}
QDockWidget::title {{
    background: {c['surface_alt']};
    /* room on the right for two 26 px buttons, so a long panel name never
       runs underneath them */
    padding: 8px 64px 8px 12px;
    border-bottom: 1px solid {c['border']};
    font-weight: 600;
    text-align: left;
}}
{docks}
QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    top: 2px;
    padding: 0 6px;
    color: {c['text_dim']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}
QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ---------- inputs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {c['surface']};
    border: 1px solid {c['border_strong']};
    border-radius: 7px;
    padding: 5px 8px;
    selection-background-color: {c['accent']};
    selection-color: white;
    min-height: 20px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus {{
    border: 1px solid {c['accent']};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled {{
    background: {c['surface_alt']};
    color: {c['text_dim']};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c['text_dim']};
    margin-right: 8px;
}}
{arrows}
QComboBox QAbstractItemView {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: {c['accent_soft']};
    selection-color: {c['accent']};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 16px; border: none; background: transparent;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: {c['surface']};
    border: 1px solid {c['border_strong']};
    border-radius: 7px;
    padding: 6px 14px;
    font-weight: 500;
}}
QPushButton:hover {{ border-color: {c['accent']}; color: {c['accent']}; }}
QPushButton:pressed {{ background: {c['accent_soft']}; }}
QPushButton:disabled {{ color: {c['text_dim']}; border-color: {c['border']}; }}
QPushButton[accent="true"] {{
    background: {c['accent']};
    border: 1px solid {c['accent']};
    color: white;
}}
QPushButton[accent="true"]:hover {{ background: {c['accent_hover']}; color: white; }}
QPushButton[flat="true"] {{ border: none; background: transparent; padding: 4px 8px; }}
QPushButton[flat="true"]:hover {{ background: {c['accent_soft']}; }}

/* plot-type cards in the inspector */
QToolButton[plotCard="true"] {{
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 7px 2px;
    background: {c['surface']};
    color: {c['text']};
    font-size: 11px;
}}
QToolButton[plotCard="true"]:hover {{ border-color: {c['accent']}; }}
QToolButton[plotCard="true"]:checked {{
    border: 2px solid {c['accent']};
    background: {c['accent_soft']};
    color: {c['accent']};
    font-weight: 600;
}}

QCheckBox, QRadioButton {{ spacing: 7px; padding: 2px 0; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {c['border_strong']};
    background: {c['surface']};
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border-color: {c['accent']};
    image: none;
}}
QRadioButton::indicator:checked {{
    background: {c['accent']};
    border: 4px solid {c['surface']};
    outline: 1px solid {c['accent']};
}}

QSlider::groove:horizontal {{
    height: 4px; border-radius: 2px; background: {c['border']};
}}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -6px 0;
    border-radius: 7px; background: {c['surface']};
    border: 2px solid {c['accent']};
}}

/* ---------- lists & tables ---------- */
QListWidget, QTreeWidget, QTableView, QTableWidget {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    outline: none;
    gridline-color: {c['border']};
    alternate-background-color: {c['surface_alt']};
}}
QListWidget::item {{ padding: 7px 9px; border-radius: 6px; margin: 1px 3px; }}
QListWidget::item:selected {{ background: {c['accent_soft']}; color: {c['accent']}; }}
QListWidget::item:hover:!selected {{ background: {c['surface_alt']}; }}
QTableView::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; }}
QHeaderView::section {{
    background: {c['surface_alt']};
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
    padding: 6px 8px;
    font-weight: 600;
    color: {c['text_dim']};
}}
QTableCornerButton::section {{ background: {c['surface_alt']}; border: none; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 9px;
    background: {c['surface']};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {c['text_dim']};
    padding: 7px 14px;
    margin-right: 2px;
    border-radius: 7px;
    font-weight: 600;
}}
QTabBar::tab:selected {{ background: {c['accent_soft']}; color: {c['accent']}; }}
QTabBar::tab:hover:!selected {{ color: {c['text']}; }}

/* ---------- scrollbars ---------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 11px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']}; border-radius: 5px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_dim']}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {c['border_strong']}; border-radius: 5px; min-width: 28px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- misc ---------- */
QStatusBar {{
    background: {c['surface']};
    border-top: 1px solid {c['border']};
    color: {c['text_dim']};
}}
QStatusBar::item {{ border: none; }}
QToolTip {{
    /* A styled tooltip needs a border: with "none" Qt skips part of the
       repaint and the bubble can come back with the previous text behind
       the new one. The border is the background colour, so it is invisible. */
    background: {c['text']};
    color: {c['bg']};
    border: 1px solid {c['text']};
    border-radius: 6px;
    padding: 5px 8px;
}}
QLabel[hint="true"] {{ color: {c['text_dim']}; font-size: 11px; }}
QLabel[section="true"] {{
    color: {c['text_dim']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.7px;
    padding-top: 4px;
}}
QFrame[hline="true"] {{ background: {c['border']}; max-height: 1px; border: none; }}
QProgressBar {{
    border: 1px solid {c['border']};
    border-radius: 6px;
    background: {c['surface']};
    text-align: center;
}}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}
"""


def _arrow_rules(icons: dict) -> str:
    """Replace the drop-down marker with a drawn chevron.

    The CSS triangle made of transparent borders is a browser trick; Qt draws
    every border, so the marker showed up as a grey block.
    """
    if not icons.get("chevron"):
        return ""
    return f"""
QComboBox::down-arrow {{
    image: url({icons['chevron']});
    width: 9px;
    height: 9px;
    border: none;
    margin-right: 7px;
}}
QComboBox::down-arrow:disabled {{ opacity: 0.4; }}
"""


def _dock_rules(c: dict, icons: dict) -> str:
    """Dock title buttons: bigger, with a hover target and our own glyphs.

    Qt's defaults are a few grey pixels that disappear on a dark background,
    which is exactly the complaint.
    """
    base = f"""
QDockWidget::float-button, QDockWidget::close-button {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0px;
    icon-size: 18px;
    width: 26px;
    height: 26px;
    top: 1px;
}}
QDockWidget::float-button {{ right: 34px; }}
QDockWidget::close-button {{ right: 4px; }}
QDockWidget::float-button:hover {{
    background: {c['accent_soft']};
    border: 1px solid {c['accent']};
}}
QDockWidget::close-button:hover {{
    background: {c['danger_soft']};
    border: 1px solid {c['danger']};
}}
QDockWidget::float-button:pressed, QDockWidget::close-button:pressed {{
    background: {c['border']};
}}
"""
    if icons.get("float") and icons.get("close"):
        base += f"""
QDockWidget::float-button {{ image: url({icons['float']}); }}
QDockWidget::close-button {{ image: url({icons['close']}); }}
"""
    # the cross turns red under the pointer, the way a browser tab closes
    if icons.get("close_hover"):
        base += f"""
QDockWidget::close-button:hover {{ image: url({icons['close_hover']}); }}
"""
    if icons.get("float_hover"):
        base += f"""
QDockWidget::float-button:hover {{ image: url({icons['float_hover']}); }}
"""
    return base


def palette_colors(dark: bool = False) -> dict:
    return DARK if dark else LIGHT
