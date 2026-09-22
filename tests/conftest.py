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


@pytest.fixture
def window():
    """A fresh main window, closed without the save prompt."""
    from plotea.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    app.processEvents()
    win._render_now()
    yield win
    win.project.dirty = False
    win.close()


@pytest.fixture(scope="module")
def shared_window():
    """One window reused across a module, for tests that build on each other."""
    from plotea.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    app.processEvents()
    win._render_now()
    yield win
    win.project.dirty = False
    win.close()
