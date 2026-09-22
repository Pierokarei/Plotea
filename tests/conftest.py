"""Shared pytest setup.

Runs before any test module is imported, which matters: Qt needs its
QApplication to exist first, and matplotlib must be told to stay headless
before anything touches a figure.
"""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)
EXAMPLES = os.path.join(ROOT, "examples")

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

# Preferences must never leak into the real ones while testing.
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, OUT)

#: One application for the whole session; Qt allows no more.
app = QApplication.instance() or QApplication([])

# Same language setup as the real application, so the tests see the dialogs
# people actually get.
from plotea.app import install_french  # noqa: E402

_translators = install_french(app)


@pytest.fixture(scope="session")
def qapp():
    return app


@pytest.fixture(scope="session")
def out_dir() -> str:
    return OUT


@pytest.fixture(scope="session")
def examples_dir() -> str:
    return EXAMPLES


@pytest.fixture(scope="session")
def datasets() -> dict:
    """The demo tables, built once for the whole run."""
    from plotea.core import demo
    return {
        "viability": demo.viability(),
        "growth": demo.growth(),
        "expression": demo.expression(),
        "correlation": demo.correlation(),
        "dose": demo.dose_response(),
        "two_factor": demo.two_factor(),
    }


def dispose(win):
    """Close a window and have Qt delete it now, not whenever Python decides.

    Closing leaves a live widget behind. Python may collect its wrapper at any
    later moment, and the C++ object then dies in the middle of the next
    window's setStyleSheet - which walks every widget of the application. That
    is the segmentation fault the CI caught on macOS and on Windows, on a
    different job each run, while this machine never saw it once.
    """
    win.project.dirty = False
    win.close()
    win.setParent(None)
    win.deleteLater()
    app.processEvents()


@pytest.fixture(scope="session", autouse=True)
def _tidy_up_at_the_end():
    """Leave no widget alive behind the QApplication.

    Modules that keep a window in a global never close it; at interpreter
    shutdown Qt and Python then race over the same objects.
    """
    yield
    # hide, never close: closeEvent asks whether to save, and an unanswered
    # modal dialog on a headless run hangs the whole session.
    for widget in list(app.topLevelWidgets()):
        widget.hide()
        widget.deleteLater()
    app.processEvents()


@pytest.fixture
def closer():
    """`dispose` as a fixture, for tests that build their own windows."""
    return dispose


@pytest.fixture
def window():
    """A fresh main window, closed without the save prompt."""
    from plotea.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    app.processEvents()
    win._render_now()
    yield win
    dispose(win)


@pytest.fixture(scope="module")
def shared_window():
    """One window reused across a module, for tests that build on each other."""
    from plotea.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    app.processEvents()
    win._render_now()
    yield win
    dispose(win)
