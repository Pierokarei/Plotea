"""Application bootstrap."""
from __future__ import annotations

import os
import sys
import traceback

from PyQt6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from .core import diagnostics
from .core.project import config_dir
from .resources import app_icon
from .ui.main_window import APP_NAME, VERSION, MainWindow
from .ui.style import build_qss


def install_french(app: QApplication) -> list:
    """Translate Qt's own dialogs, so no English button sits in a French app.

    Without this, the standard buttons of a QMessageBox come out as "Save",
    "Discard" and "Cancel". The translators are returned because Qt drops a
    translator that nothing keeps a reference to.
    """
    QLocale.setDefault(QLocale(QLocale.Language.French,
                               QLocale.Country.France))
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    kept = []
    for name in ("qtbase_fr", "qt_fr"):
        translator = QTranslator(app)
        if translator.load(name, folder):
            app.installTranslator(translator)
            kept.append(translator)
    return kept


def steady_tooltips(app: QApplication):
    """Turn off the fade and slide Windows applies to tooltips.

    The effect outlives the pointer: the old bubble is still fading out over
    one button while another one is already asking for its own, which shows
    up as a tooltip that flickers, lags or lingers with the wrong text.
    """
    for effect in (Qt.UIEffect.UI_FadeTooltip, Qt.UIEffect.UI_AnimateTooltip):
        app.setEffectEnabled(effect, False)


def selftest_report(app: QApplication, window) -> list[str]:
    """What a packaged build cannot otherwise be asked about.

    Freezing drops what nothing imports and Python collects what nothing
    references; both failures are silent, so the smoke test states them out
    loud rather than only proving that a window appeared.
    """
    from .ui.widgets import _SectionTips

    lines = []
    fade = app.isEffectEnabled(Qt.UIEffect.UI_FadeTooltip)
    animate = app.isEffectEnabled(Qt.UIEffect.UI_AnimateTooltip)
    lines.append(f"infobulles : fondu={'on' if fade else 'off'} "
                 f"animation={'on' if animate else 'off'}")
    guard = getattr(window.data_panel, "_header_tips", None)
    lines.append("filtre d'en-tête : "
                 + ("actif" if isinstance(guard, _SectionTips) else "PERDU"))
    icons = getattr(window, "dock_icons", {})
    lines.append(f"glyphes de panneau : {len(icons)} fichiers")
    return lines


def _excepthook(exc_type, exc, tb):
    """Keep the app alive when a slot raises: report instead of aborting."""
    traceback.print_exception(exc_type, exc, tb)
    diagnostics.LOG.record(
        "Exception non rattrapée", f"{exc_type.__name__}: {exc}",
        "".join(traceback.format_exception(exc_type, exc, tb)))
    try:
        from PyQt6.QtWidgets import QMessageBox
        window = QApplication.activeWindow()
        QMessageBox.warning(
            window, APP_NAME,
            "Une opération a échoué :\n\n"
            f"{exc_type.__name__}: {exc}\n\n"
            "L'application continue de fonctionner. Le détail est dans "
            "Aide > Journal des erreurs.")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    sys.excepthook = _excepthook
    try:
        diagnostics.use_file(config_dir())
    except Exception:              # a read-only install must still start
        pass
    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Plotea")
    app.setStyle("Fusion")
    steady_tooltips(app)
    app._translators = install_french(app)
    app.setDesktopFileName("plotea")       # Wayland / GNOME task switcher
    app.setWindowIcon(app_icon())

    font = QFont()
    font.setPointSize(10 if sys.platform.startswith("win") else 11)
    app.setFont(font)
    app.setStyleSheet(build_qss(False))

    window = MainWindow()
    window.show()

    if os.environ.get("PLOTEA_SELFTEST"):
        # Smoke test for packaged builds: prove the app starts, then leave
        # without entering the event loop.
        app.processEvents()
        for line in selftest_report(app, window):
            print(line)
        window.project.dirty = False
        window.close()
        print(f"{APP_NAME} {VERSION} démarré correctement")
        return 0

    for arg in argv[1:]:
        if arg.lower().endswith(".plotea"):
            try:
                from .core.project import Project
                window.project = Project.load(arg)
                window._reload_all(0)
                window._update_title()
            except Exception:
                pass
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
