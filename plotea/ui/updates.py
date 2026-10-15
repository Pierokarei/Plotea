"""Offering a newer Plotea: a banner over the plot, never a dialog in the way.

Nothing happens until people agree: the first time, the banner asks
whether Plotea may look once a day. After that, a newer version shows as a
banner with its download page; skipped once, a version is not offered
again. The question goes out on a thread of its own and an unanswered one
says nothing: a laboratory without internet has nothing to be told.

Help > Check for updates asks at any time, and says what it found.
"""
from __future__ import annotations

import threading
import time

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
)

from .. import __version__
from ..core import updates
from ..i18n import tr

#: At most one question a day.
INTERVAL_S = 24 * 3600


class Banner(QFrame):
    """A line of text and a few buttons across the top of the plot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("banner", True)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Preferred)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(12, 6, 8, 6)
        self.row.setSpacing(6)
        self.row.addWidget(self.text, 1)
        self.buttons: dict[str, QPushButton] = {}
        self.hide()

    def show_message(self, text: str, buttons: list[tuple]):
        """`buttons`: (key, label, slot, accent) from left to right."""
        for button in self.buttons.values():
            self.row.removeWidget(button)
            button.deleteLater()
        self.buttons = {}
        self.text.setText(text)
        for key, label, slot, accent in buttons:
            button = QPushButton(label)
            if accent:
                button.setProperty("accent", True)
            button.clicked.connect(slot)
            self.row.addWidget(button)
            self.buttons[key] = button
        self.show()


class UpdateNotifier(QObject):
    """Asks GitHub, on a thread, and says what it found in the banner."""

    _answered = pyqtSignal(object, bool)     # Release, None or error; manual

    def __init__(self, window, banner: Banner):
        super().__init__(window)
        self.window = window
        self.memory = window.memory
        self.banner = banner
        self.fetch = updates.fetch           # replaced by the tests
        self.current = __version__
        self._busy = False
        self._answered.connect(self._on_answer)

    # -- when Plotea starts ---------------------------------------------
    def on_startup(self, now: float | None = None):
        """Ask the first time; then look, at most once a day, if allowed."""
        allowed = self.memory.update_checks()
        if allowed is None:
            self.offer()
        elif allowed:
            now = time.time() if now is None else now
            if now - self.memory.last_update_check() >= INTERVAL_S:
                self.check(manual=False)

    def offer(self):
        self.banner.show_message(
            tr("Plotea peut vérifier une fois par jour s'il existe une "
               "nouvelle version : une simple demande à GitHub, rien "
               "d'autre n'est envoyé ni installé."),
            [("yes", tr("Activer"), self._agree, True),
             ("no", tr("Non merci"), self._decline, False)])

    def _agree(self):
        self.set_allowed(True)
        self.banner.hide()
        self.check(manual=False)

    def _decline(self):
        self.set_allowed(False)
        self.banner.hide()
        self.window.statusBar().showMessage(
            tr("Vérification des mises à jour désactivée - réactivable "
               "dans le menu Aide."), 8000)

    def set_allowed(self, allowed: bool):
        self.memory.remember_update_checks(allowed)
        action = getattr(self.window, "a_auto_updates", None)
        if action is not None:
            action.blockSignals(True)
            action.setChecked(allowed)
            action.blockSignals(False)

    # -- asking ----------------------------------------------------------
    def check(self, manual: bool = True):
        """Ask GitHub on a thread; the answer comes back on the GUI one."""
        if self._busy:
            return
        self._busy = True
        self.memory.remember_update_check(time.time())
        self._start(lambda: self._ask(manual))

    def _start(self, job):
        threading.Thread(target=job, daemon=True).start()

    def _ask(self, manual: bool):
        try:
            found = updates.newest(self.fetch(), self.current)
        except Exception as exc:              # offline, proxy, rate limit
            found = exc
        try:
            self._answered.emit(found, manual)
        except RuntimeError:                  # the window has gone
            pass

    def _on_answer(self, found, manual: bool):
        self._busy = False
        if isinstance(found, Exception):
            if manual:
                QMessageBox.information(
                    self.window, tr("Mises à jour"),
                    tr("Impossible de joindre GitHub. Vérifiez la connexion, "
                       "ou consultez directement {url}").format(
                           url=updates.DOWNLOADS_URL))
            return
        if found is None:
            if manual:
                QMessageBox.information(
                    self.window, tr("Mises à jour"),
                    tr("Plotea {version} est la version la plus récente."
                       ).format(version=self.current))
            return
        if not manual and found.version == self.memory.skipped_version():
            return
        self.announce(found)

    def announce(self, release: updates.Release):
        text = tr("Plotea {version} est disponible (vous avez {current})."
                  ).format(version=release.version, current=self.current)
        if release.changes_results:
            text += " " + tr("Elle corrige des calculs qui peuvent changer "
                             "vos résultats : voyez ses notes.")
        self.banner.show_message(text, [
            ("get", tr("Télécharger"),
             lambda: self._open(release), True),
            ("later", tr("Plus tard"), self.banner.hide, False),
            ("skip", tr("Ignorer cette version"),
             lambda: self._skip(release), False)])

    def _open(self, release):
        QDesktopServices.openUrl(QUrl(release.url))
        self.banner.hide()

    def _skip(self, release):
        self.memory.skip_version(release.version)
        self.banner.hide()
