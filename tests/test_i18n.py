"""Interface language: French untouched, English complete, choice remembered.

French is the source language: tr() hands French text back unchanged, so the
French interface is the code itself and nothing done to a catalogue can alter
it. These tests hold the other half of the promise - that an English user
meets no French, that every translation fits the sentence it replaces, and
that the choice of language behaves.
"""
import os
import re
import string
import sys

import pytest
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDockWidget,
    QLabel,
    QMessageBox,
)

from plotea import i18n

app = QApplication.instance()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import i18n_keys  # noqa: E402


@pytest.fixture
def english():
    """English for the duration of a test, French again afterwards."""
    from plotea.app import install_language

    i18n.set_language("en")
    install_language(app, "en")
    yield
    i18n.set_language("fr")
    install_language(app, "fr")


@pytest.fixture(scope="module")
def catalogue():
    return i18n.load_catalogue("en")


# --------------------------------------------------------------------------
# French cannot be broken
# --------------------------------------------------------------------------
def test_french_is_the_text_itself():
    i18n.set_language("fr")
    for text in ("Enregistrer", "Annuler {action}", "Viabilité (%)", ""):
        assert i18n.tr(text) is text


def test_a_broken_catalogue_falls_back_to_french(monkeypatch, tmp_path):
    """An unreadable catalogue must leave French, never half a language."""
    broken = tmp_path / "en.json"
    broken.write_text("{ pas du json", encoding="utf-8")
    monkeypatch.setattr(i18n, "catalogue_path", lambda language: str(broken))
    try:
        assert i18n.set_language("en") == "fr"
        assert i18n.tr("Enregistrer") == "Enregistrer"
    finally:
        monkeypatch.undo()
        i18n.set_language("fr")


def test_an_unknown_language_falls_back_to_french():
    try:
        assert i18n.set_language("klingon") == "fr"
    finally:
        i18n.set_language("fr")


def test_a_missing_entry_shows_french_rather_than_nothing(english):
    assert i18n.tr("Une phrase qui n'existe dans aucun catalogue") == \
        "Une phrase qui n'existe dans aucun catalogue"


# --------------------------------------------------------------------------
# English is complete and every entry fits its sentence
# --------------------------------------------------------------------------
def test_every_text_has_an_english_translation(catalogue):
    """A text added without its translation reaches English users in French.

    The keys are harvested from the code itself - the strings written in
    tr(), and the labels kept in tables - so this cannot be satisfied by
    forgetting to list a key.
    """
    keys = {k for k in i18n_keys.all_keys() if i18n_keys.needs_translation(k)}
    missing = sorted(k for k in keys if not catalogue.get(k))
    assert not missing, f"{len(missing)} texte(s) sans traduction : {missing[:15]}"


def test_no_translation_is_left_over(catalogue):
    """An entry nothing asks for is a renamed text whose new key is missing."""
    keys = i18n_keys.all_keys()
    unused = sorted(k for k in catalogue if k not in keys)
    assert not unused, unused[:15]


def fields(text):
    return sorted(name for _lit, name, _spec, _conv
                  in string.Formatter().parse(text) if name is not None)


def test_every_translation_keeps_its_placeholders(catalogue):
    """{count} renamed {nombre} would crash on format(), at runtime."""
    wrong = [(k, v) for k, v in catalogue.items() if fields(k) != fields(v)]
    assert not wrong, wrong[:10]


def test_every_translation_formats(catalogue):
    """The format specs survive too: {w:.0f} fed a number, and so on."""
    for key, value in catalogue.items():
        names = fields(key)
        if not names:
            continue
        sample = {name: 1.5 for name in names}
        key.format(**sample)
        value.format(**sample)


def test_menu_accelerators_survive(catalogue):
    """&Fichier -> &File: the Alt shortcut must still exist."""
    for key, value in catalogue.items():
        if key.startswith("&"):
            assert value.count("&") == 1, (key, value)


def test_line_breaks_survive(catalogue):
    """Multi-line messages keep their layout."""
    for key, value in catalogue.items():
        if "\n\n" in key:
            assert "\n\n" in value, (key, value)


# --------------------------------------------------------------------------
# The English interface, swept
# --------------------------------------------------------------------------
FRENCH = re.compile(r"(?i)\b(de|des|du|la|les|une|et|pour|par|dans|avec|"
                    r"aucun|aucune|choisissez|graphique|données)\b")


def french_left(window, catalogue):
    """Visible texts that are untranslated French interface strings."""
    keys = set(catalogue) - {k for k, v in catalogue.items() if k == v}
    found = []

    def check(where, text):
        text = (text or "").replace("&", "").strip()
        if text and (text in keys or FRENCH.search(text)):
            found.append((where, text))

    for menu_action in window.menuBar().actions():
        check("menu", menu_action.text())
        if menu_action.menu() is not None:
            for action in menu_action.menu().actions():
                check("menu", action.text())
    for widget in window.findChildren(QLabel):
        check("label", widget.text())
    for widget in window.findChildren(QAbstractButton):
        check("bouton", widget.text())
        check("bulle", widget.toolTip())
    for widget in window.findChildren(QDockWidget):
        check("panneau", widget.windowTitle())
    for widget in window.findChildren(QComboBox):
        if widget is window.inspector.cmb_dataset:
            continue                           # dataset names are data
        for i in range(widget.count()):
            check("liste", widget.itemText(i))
    return found


def test_the_english_window_has_no_french_left(english, catalogue, closer):
    from plotea.ui.main_window import MainWindow

    window = MainWindow()
    try:
        window.show()
        for plot_type in ("bar", "line", "histogram", "box", "violin",
                          "survival", "contingency", "paired", "bland_altman"):
            window.current_spec().plot_type = plot_type
            window._sync_inspector()
            window._render_now()
            app.processEvents()
            left = french_left(window, catalogue)
            assert not left, f"{plot_type} : {left[:12]}"
    finally:
        closer(window)


def test_the_first_screen_reads_in_english(english, closer):
    """The example a new user sees first: tab, title, columns, groups."""
    from plotea.ui.main_window import MainWindow

    window = MainWindow()
    try:
        spec = window.current_spec()
        assert spec.name == "Plot 1"
        assert spec.title == "Treatment effect"
        assert spec.ylabel == "Viability (%)"
        frame = window.project.datasets[0].df
        assert {"Treatment", "Viability", "Replicate"} <= set(frame.columns)
        assert "Control" in set(frame["Treatment"])
        # cell lines are names, not words
        assert {"HeLa", "U2OS"} <= set(frame["Cell line"])
    finally:
        closer(window)


def about_texts():
    from plotea.ui.dialogs import AboutDialog

    dialog = AboutDialog("9.9")
    try:
        return dialog.windowTitle(), " ".join(
            label.text() for label in dialog.findChildren(QLabel))
    finally:
        dialog.deleteLater()


def test_the_about_page_reads_in_english(english, catalogue):
    """A dialog, so the window sweep above never opens it."""
    title, body = about_texts()
    assert title == "About Plotea"
    assert "Version 9.9" in body
    assert "Publication-quality figures" in body
    assert "MIT license" in body
    keys = set(catalogue) - {k for k, v in catalogue.items() if k == v}
    assert not FRENCH.search(body) and body not in keys, body


def test_the_about_page_is_french_with_its_accents():
    title, body = about_texts()
    assert title == "À propos de Plotea"
    assert "Version 9.9" in body
    assert "Alternative ouverte à GraphPad Prism" in body
    assert "jusqu'à 1200 dpi" in body


def shown_by(monkeypatch, answer=""):
    """Record what the next message boxes say, and press `answer` if given."""
    seen = []

    def record(box):
        seen.append((box.informativeText(),
                     {b.text().replace("&", "") for b in box.buttons()}))
        for button in box.buttons():
            if button.text().replace("&", "") == answer:
                button.click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", record)
    return seen


def test_quitting_asks_in_english(english, window, monkeypatch):
    """The texts are handed to ask_to_keep_changes, not wrapped in tr()."""
    seen = shown_by(monkeypatch, answer="Cancel")
    window.project.dirty = True
    try:
        assert not window.close(), "Cancel: the window stays"
    finally:
        window.project.dirty = False
    question, buttons = seen[0]
    assert question == "Do you want to save it before quitting?"
    assert {"Save", "Quit without saving", "Cancel"} <= buttons


def test_the_recovery_offer_reads_in_english(english, window, monkeypatch):
    from plotea.app import offer_recovery
    from plotea.core import project as project_mod

    project_mod.write_recovery(window.project)
    seen = shown_by(monkeypatch)
    try:
        offer_recovery(window)
    finally:
        project_mod.clear_recovery()
    text = seen[0][0]
    assert "project never saved" in text and " at " in text, text
    assert " à " not in text and not FRENCH.search(text), text


def test_figure_axis_titles_follow_the_language(english):
    """They end up in the exported figure, not only on screen."""
    from matplotlib.figure import Figure

    from plotea.core import demo
    from plotea.core.plotspec import PlotSpec
    from plotea.core.plotting import render

    trial = demo.survival().df
    figure = Figure()
    render(figure, PlotSpec(plot_type="survival", x="Time (months)",
                            group="Arm", event_col="Event"), trial)
    assert figure.axes[0].get_ylabel() == "Survival"

    figure = Figure()
    render(figure, PlotSpec(plot_type="histogram", y=["Viability"]),
           demo.viability().df)
    assert figure.axes[0].get_ylabel() == "Count"


def test_qt_dialogs_speak_the_interface_language(english):
    box = QMessageBox()
    box.setStandardButtons(QMessageBox.StandardButton.Save
                           | QMessageBox.StandardButton.Cancel)
    texts = {b.text().replace("&", "") for b in box.buttons()}
    assert texts == {"Save", "Cancel"}, texts


def test_qt_dialogs_are_french_again_afterwards():
    """The fixture puts French back: the rest of the suite depends on it."""
    box = QMessageBox()
    box.setStandardButtons(QMessageBox.StandardButton.Save)
    assert box.buttons()[0].text().replace("&", "") == "Enregistrer"


# --------------------------------------------------------------------------
# Lists whose visible text used to be their key
# --------------------------------------------------------------------------
def test_the_csv_separator_works_in_english(english, tmp_path):
    """The separator was read back from the visible text: "Semicolon ;"
    is not a key of the table of separators."""
    from plotea.ui.dialogs import ImportDialog

    path = tmp_path / "data.csv"
    path.write_text("a;b\n1;2\n3;4\n", encoding="utf-8")
    dialog = ImportDialog(str(path))
    try:
        dialog.cmb_sep.setCurrentIndex(dialog.cmb_sep.findData("Point-virgule ;"))
        dialog.refresh()
        assert list(dialog.datasets[0].df.columns) == ["a", "b"]
        assert dialog.cmb_sep.currentText() == "Semicolon ;"
    finally:
        dialog.deleteLater()


def test_the_export_format_works_in_english(english, tmp_path):
    from plotea.ui.dialogs import ExportDialog

    dialog = ExportDialog(str(tmp_path / "f.png"), 89.0, 69.0)
    try:
        dialog.cmb_format.setCurrentIndex(
            dialog.cmb_format.findData("PDF (vectoriel, publication)"))
        assert dialog.cmb_format.currentText() == "PDF (vector, publication)"
        assert dialog.options().fmt == "PDF (vectoriel, publication)"
        assert dialog.txt_path.text().endswith(".pdf")
    finally:
        dialog.deleteLater()


def test_exporting_everything_in_english(english, window, tmp_path,
                                         monkeypatch):
    """The format list is shown translated and must map back to its key."""
    from PyQt6.QtWidgets import QFileDialog, QInputDialog

    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: ("SVG (vector, editable)",
                                                      True)))
    window.export_all()
    assert [f for f in os.listdir(tmp_path) if f.endswith(".svg")]


def test_the_theme_palette_placeholder_in_english(english, closer):
    """Its visible text is compared to decide "no palette": it moved."""
    from plotea.ui.main_window import MainWindow

    window = MainWindow()
    try:
        palette = window.inspector.cmb_palette
        palette.setCurrentIndex(0)                # "(theme)"
        assert palette.currentText() == "(theme)"
        window.inspector._push()
        assert window.current_spec().palette == ""
    finally:
        closer(window)


# --------------------------------------------------------------------------
# Choosing the language
# --------------------------------------------------------------------------
class Memory:
    def __init__(self, chosen=""):
        self.chosen = chosen

    def language(self):
        return self.chosen


def test_the_order_of_authority(monkeypatch):
    from PyQt6.QtCore import QLocale

    from plotea.app import choose_language

    monkeypatch.setenv("PLOTEA_LANG", "en")
    assert choose_language(Memory("fr")) == "en", "l'environnement prime"

    monkeypatch.delenv("PLOTEA_LANG")
    assert choose_language(Memory("en")) == "en", "puis le choix du menu"

    french = QLocale(QLocale.Language.French, QLocale.Country.France)
    german = QLocale(QLocale.Language.German, QLocale.Country.Germany)
    monkeypatch.setattr(QLocale, "system", staticmethod(lambda: french))
    assert choose_language(Memory("")) == "fr", "un système français"
    monkeypatch.setattr(QLocale, "system", staticmethod(lambda: german))
    assert choose_language(Memory("")) == "en", "tout autre système"


def test_the_menu_offers_both_languages(window):
    actions = window.language_actions
    assert set(actions) == {"fr", "en"}
    assert actions["fr"].text() == "Français"
    assert actions["en"].text() == "English"
    assert actions["fr"].isChecked()
    assert window.m_language.title() == "Langue / Language"


def test_choosing_a_language_is_remembered(window, monkeypatch):
    """Later: nothing restarts, the choice waits for the next start."""
    def later(box):
        for button in box.buttons():
            if button.text() == "Later":
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", later)
    try:
        assert window.choose_language("en") is False
        assert window.memory.language() == "en"
    finally:
        window.memory.remember_language("fr")


def test_the_restart_is_offered_in_the_chosen_language(window, monkeypatch):
    """Someone switching to English may not read the French question."""
    seen = []

    def look(box):
        seen.append((box.text(), [b.text() for b in box.buttons()]))
        return 0

    monkeypatch.setattr(QMessageBox, "exec", look)
    try:
        window.choose_language("en")
    finally:
        window.memory.remember_language("fr")
    text, buttons = seen[0]
    assert "English" in text
    assert "Restart now" in buttons


def test_restarting_keeps_the_window_when_the_user_says_no(window,
                                                           monkeypatch):
    """Restarting goes through closing, which asks about unsaved work."""
    from PyQt6.QtCore import QProcess

    started = []
    monkeypatch.setattr(QProcess, "startDetached",
                        staticmethod(lambda *a, **k: started.append(a)))
    monkeypatch.setattr(type(window), "close", lambda self: False)
    assert window.restart() is False
    assert started == [], "un nouveau Plotea a démarré malgré le refus"
