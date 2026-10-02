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
from .i18n import tr
from .resources import app_icon
from .ui.main_window import APP_NAME, VERSION, MainWindow
from .ui.style import build_qss

#: Qt's own number format and dialog buttons, per interface language.
QT_LOCALES = {
    "fr": (QLocale.Language.French, QLocale.Country.France),
    "en": (QLocale.Language.English, QLocale.Country.UnitedStates),
}


def install_language(app: QApplication, language: str) -> list:
    """Make Qt's own texts and number formats follow the interface.

    Without this the standard buttons of a QMessageBox come out as "Save",
    "Discard" and "Cancel" in a French interface, and spin boxes use a
    decimal comma in an English one. Qt speaks English by itself, so only
    French needs a translator. The translators are returned because Qt
    drops one that nothing keeps a reference to.
    """
    for old in getattr(app, "_translators", []):
        app.removeTranslator(old)
    lang, country = QT_LOCALES.get(language, QT_LOCALES["fr"])
    QLocale.setDefault(QLocale(lang, country))
    kept = []
    if language == "fr":
        folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        for name in ("qtbase_fr", "qt_fr"):
            translator = QTranslator(app)
            if translator.load(name, folder):
                app.installTranslator(translator)
                kept.append(translator)
    app._translators = kept
    return kept


def install_french(app: QApplication) -> list:
    """Kept for the callers that only ever wanted French."""
    return install_language(app, "fr")


def choose_language(memory) -> str:
    """The interface language, in order of authority.

    PLOTEA_LANG (tests, scripts), then the choice made in the menu, then the
    system's own language: a French system starts in French, anything else
    in English, so nobody meets a first screen they cannot read.
    """
    from . import i18n

    forced = os.environ.get("PLOTEA_LANG", "")
    if forced in i18n.LANGUAGES:
        return forced
    chosen = memory.language()
    if chosen in i18n.LANGUAGES:
        return chosen
    system = QLocale.system().language()
    return "fr" if system == QLocale.Language.French else "en"


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
    # a packaged build that lost its catalogues would fall back to French
    # without a word; say which language is in effect and how complete
    from . import i18n
    loaded = [f"{code}: {len(i18n.load_catalogue(code))}"
              for code in i18n.LANGUAGES if code != i18n.SOURCE]
    lines.append(f"langue : {i18n.language()} - traductions "
                 + ", ".join(loaded))
    lines.append(f"import Prism : {_prism_selftest()}")
    return lines


def _prism_selftest() -> str:
    """Read a tiny .pzfx: the reader rests on an XML parser nothing else
    in the application uses, the kind of module a frozen build can lose."""
    import tempfile

    from .core import pzfx

    sample = ('<GraphPadPrismFile><Table TableType="OneWay"><Title>T</Title>'
              '<YColumn><Title>A</Title><Subcolumn><d>1</d><d>2</d>'
              '</Subcolumn></YColumn></Table></GraphPadPrismFile>')
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "selftest.pzfx")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(sample)
            tables = pzfx.read_pzfx(path).tables
    except Exception as exc:
        return f"PERDU ({type(exc).__name__}: {exc})"
    return "ok" if tables and len(tables[0].dataset.df) == 2 else "VIDE"


def offer_recovery(window) -> bool:
    """Offer the copy a session that ended badly left behind.

    Only reached when one exists: a normal exit and every real save remove
    it, so its mere presence means the previous run did not end on its own
    terms. Closing the dialog decides nothing and keeps the copy.
    """
    from PyQt6.QtWidgets import QMessageBox

    from .core import project as project_mod

    info = project_mod.recovery_info()
    if not info:
        return False

    day, _sep, hour = (info.get("saved", "") or "").partition("T")
    when = tr("{day} à {hour}").format(day=day, hour=hour) if hour else day
    origin = info.get("origin") or tr("projet jamais enregistré")
    box = QMessageBox(window)
    box.setWindowTitle(APP_NAME)
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(tr("La session précédente ne s'est pas terminée normalement."))
    box.setInformativeText(
        tr("Une copie de secours de « {name} » a été enregistrée le {when}."
           "\n{origin}\n\nVoulez-vous la récupérer ?").format(
            name=info.get("name", tr("Projet")), when=when, origin=origin))
    recover = box.addButton(tr("Récupérer"), QMessageBox.ButtonRole.AcceptRole)
    box.addButton(tr("Supprimer la copie"),
                  QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(recover)
    box.exec()

    if box.clickedButton() is recover:
        return window.restore_recovery(info)
    if box.clickedButton() is not None:       # "Supprimer la copie"
        project_mod.clear_recovery()
    return False                              # closed: decide next time


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
            tr("Une opération a échoué :\n\n{error}\n\n"
               "L'application continue de fonctionner. Le détail est dans "
               "Aide > Journal des erreurs.").format(
                error=f"{exc_type.__name__}: {exc}"))
    except Exception:
        pass


def build(argv: list[str]) -> tuple:
    """Everything up to the event loop, as (application, window).

    Separate from main() so a test can inspect a real startup without
    entering a loop it would then have to get out of.
    """
    sys.excepthook = _excepthook
    try:
        diagnostics.use_file(config_dir())
    except Exception:              # a read-only install must still start
        pass
    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)
    # Qt allows one application object per process; a test session, or an
    # embedding host, already has one.
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Plotea")
    app.setStyle("Fusion")
    steady_tooltips(app)

    # before the first widget: every caption is read at construction
    from PyQt6.QtCore import QSettings

    from . import i18n
    from .ui.session import SessionMemory
    language = i18n.set_language(
        choose_language(SessionMemory(QSettings("Plotea", "Plotea"))))
    install_language(app, language)
    app.setDesktopFileName("plotea")       # Wayland / GNOME task switcher
    app.setWindowIcon(app_icon())

    font = QFont()
    font.setPointSize(10 if sys.platform.startswith("win") else 11)
    app.setFont(font)
    app.setStyleSheet(build_qss(False))

    window = MainWindow()
    window.show()
    return app, window


def open_arguments(window, argv: list[str]) -> bool:
    """Open a .plotea given on the command line, and say so when it fails.

    Double-clicking a damaged project used to open an empty window with no
    explanation at all.
    """
    from .core.project import Project

    for arg in argv[1:]:
        if not arg.lower().endswith(".plotea"):
            continue
        try:
            window.project = Project.load(arg)
        except Exception as exc:
            diagnostics.LOG.record("Ouverture au démarrage impossible",
                                   f"{type(exc).__name__}: {exc}", arg)
            window.statusBar().showMessage(
                tr("Ouverture impossible : {name} - détail dans Aide > Journal "
                   "des erreurs").format(name=os.path.basename(arg)), 10000)
            return False
        window._reload_all(0)
        window._update_title()
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app, window = build(argv)

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

    offer_recovery(window)
    open_arguments(window, argv)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
