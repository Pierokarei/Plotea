"""What keeps the suite - and Plotea's own start - quick.

Restyling the application walks every widget: five to six seconds for a
window, paid once per window built, the same sheet or not, until the sheet
was installed before the widgets and set only when it changes. The test
suite went from about twenty minutes to about ten. And the quick run
(`pytest -m "not gui"`) must leave out every test that opens a window,
however it opens it.
"""
import os
import subprocess
import sys

from PyQt6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_an_unchanged_stylesheet_is_not_set_again(window, monkeypatch):
    from conftest import dispose

    from plotea.ui.main_window import MainWindow

    calls = []
    original = QApplication.setStyleSheet
    monkeypatch.setattr(QApplication, "setStyleSheet",
                        lambda self, sheet: (calls.append(1),
                                             original(self, sheet)))
    second = MainWindow()
    try:
        assert calls == [], "la feuille de style a été réappliquée"
        second.apply_theme(not second.dark)          # a real change
        assert calls == [1]
        second.apply_theme(not second.dark)          # and back
        assert calls == [1, 1]
    finally:
        dispose(second)


def test_the_sheet_comes_before_the_widgets(window, monkeypatch):
    """At Plotea's start the sheet is new: installed after the widgets, it
    would restyle all of them - the five seconds this was about."""
    from conftest import dispose

    from plotea.ui.main_window import MainWindow

    app = QApplication.instance()
    kept = app.styleSheet()
    order = []
    original_set = QApplication.setStyleSheet
    original_build = MainWindow._build_central
    monkeypatch.setattr(QApplication, "setStyleSheet",
                        lambda self, sheet: (order.append("feuille"),
                                             original_set(self, sheet)))
    monkeypatch.setattr(MainWindow, "_build_central",
                        lambda self: (order.append("widgets"),
                                      original_build(self)))
    original_set(app, "")                       # as at the very start
    second = MainWindow()
    try:
        assert order[:2] == ["feuille", "widgets"], order
        assert order.count("feuille") == 1, order
    finally:
        dispose(second)
        original_set(app, kept)


def collected(marker: str) -> set:
    """Test ids pytest selects for `-m marker`, in a process of its own."""
    files = ["tests/test_auc.py", "tests/test_updates.py",
             "tests/test_history.py", "tests/test_startup.py"]
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-o", "addopts=", "-p", "no:cacheprovider", "-m", marker, *files],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300)
    return {line.strip() for line in out.stdout.splitlines() if "::" in line}


def test_the_quick_run_opens_no_window():
    quick = collected("not gui")
    # pure computation stays in
    assert "tests/test_auc.py::test_the_area_is_the_trapezoids_of_the_means" \
        in quick
    assert "tests/test_updates.py::test_version_numbers_are_compared_as_" \
        "numbers" in quick
    # a window through a chain of fixtures (notifier -> window)
    assert not any("test_a_new_window_asks_nothing" in t for t in quick)
    # a window built when the module is imported
    assert not any(t.startswith("tests/test_history.py") for t in quick)
    # a window built in the test itself
    assert not any("test_the_self_test_reports_and_returns" in t
                   for t in quick)
    windows = collected("gui")
    assert any("test_a_new_window_asks_nothing" in t for t in windows)
