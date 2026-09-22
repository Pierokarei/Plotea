"""Application icon, remembered layout and remembered folder."""
import os
import sys


from PyQt6.QtCore import QSettings, QSize  # noqa: E402

from plotea import resources  # noqa: E402
from plotea.ui.main_window import MainWindow  # noqa: E402


# a throwaway settings scope: never touch the real preferences
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
SETTINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(SETTINGS_DIR, exist_ok=True)
QSettings.setPath(QSettings.Format.IniFormat,
                  QSettings.Scope.UserScope, SETTINGS_DIR)


def test_icon_is_drawn_at_every_size():
    icon = resources.app_icon()
    assert not icon.isNull()
    for size in (16, 32, 256):
        pixmap = icon.pixmap(QSize(size, size))
        assert not pixmap.isNull(), size
        assert pixmap.width() > 0


def test_icon_has_visible_content():
    """Not a blank square: the tile and the three bars must be there."""
    image = resources.logo_pixmap(64).toImage()
    colours = {image.pixelColor(x, y).name()
               for x in range(8, 56, 4) for y in range(8, 56, 4)}
    assert len(colours) >= 3, colours
    assert resources.BACKGROUND.lower() in {c.lower() for c in colours}
    corner = image.pixelColor(0, 0)
    assert corner.alpha() == 0, "les coins doivent etre transparents"


def test_icon_files_exist_for_packaging():
    for extension in (".png", ".ico"):
        path = resources.icon_path(extension)
        assert path and os.path.getsize(path) > 500, extension


def test_window_carries_the_icon():
    win = MainWindow()
    assert not win.windowIcon().isNull()
    win.project.dirty = False
    win.close()


def test_layout_survives_a_restart():
    """isHidden, not isVisible: nothing is ever visible on a headless screen,
    and the virtual screen clamps window sizes."""
    first = MainWindow()
    first.resize(1200, 800)
    first.dock_stats.hide()
    first._save_layout()
    saved = bytes(first.saveState())
    first.project.dirty = False
    first.close()

    second = MainWindow()
    second._restore_layout()
    assert second.dock_stats.isHidden(), "l'etat des panneaux est perdu"
    assert bytes(second.saveState()) == saved, "disposition non restauree"
    second.project.dirty = False
    second.close()


def test_reset_puts_the_panels_back():
    win = MainWindow()
    win.dock_stats.hide()
    win.dock_inspector.setFloating(True)
    win.reset_layout()
    assert not win.dock_stats.isHidden()
    assert not win.dock_inspector.isFloating()
    assert win.settings.value("windowState") is None
    win.project.dirty = False
    win.close()


def test_last_folder_is_remembered():
    win = MainWindow()
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
    win._remember_dir(os.path.join(target, "figure.png"))
    assert win.last_dir() == target, win.last_dir()

    # a folder that no longer exists must not break the next dialog
    win.settings.setValue("lastDir", os.path.join(target, "disparu"))
    assert os.path.isdir(win.last_dir()), win.last_dir()
    win.project.dirty = False
    win.close()


def test_corrupt_settings_do_not_block_startup():
    settings = QSettings("Plotea", "Plotea")
    settings.setValue("geometry", "ceci n'est pas une geometrie")
    settings.setValue("windowState", 42)
    win = MainWindow()
    win._restore_layout()          # must swallow it and carry on
    assert win.isEnabled()
    win.project.dirty = False
    win.close()


def test_layout_saved_on_close():
    win = MainWindow()
    win.resize(1100, 720)
    win.project.dirty = False
    win.close()                    # closeEvent must persist the layout
    assert QSettings("Plotea", "Plotea").value("geometry") is not None


def _run_entry(command: list[str]) -> str:
    """Start the app through `command` in self-test mode and return stdout."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PLOTEA_SELFTEST="1", QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(command, capture_output=True, text=True, env=env,
                            cwd=root, timeout=240)
    assert result.returncode == 0, result.stderr[-900:]
    return result.stdout


def test_entry_script_runs_standalone():
    """run_plotea.py must work when run as a top-level script.

    PyInstaller executes it outside any package, so a relative import here
    would break the packaged application while leaving `python -m plotea` fine.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = _run_entry([sys.executable, os.path.join(root, "run_plotea.py")])
    assert "correctement" in out, out


def test_module_entry_still_works():
    out = _run_entry([sys.executable, "-m", "plotea"])
    assert "correctement" in out, out
