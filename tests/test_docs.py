"""The page for people coming from Prism stays true to the interface.

It names menus, sections, tabs and options word for word, between « » in
French and “ ” in English: every one must exist in Plotea, or the page
sends people looking for a button that is not there. Its links must land,
it must describe the version people have, and what it says Plotea does not
do must still be missing - or the page undersells it.
"""
import json
import os
import re
import unicodedata

import pytest

from plotea import __version__
from plotea.core import enums

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRENCH = os.path.join(ROOT, "docs", "prism-vers-plotea.md")
ENGLISH = os.path.join(ROOT, "docs", "from-prism.md")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def catalogue():
    with open(os.path.join(ROOT, "plotea", "locales", "en.json"),
              encoding="utf-8") as handle:
        return json.load(handle)


def plain(label: str) -> str:
    """A label as shown: no accelerator, no trailing ellipsis."""
    return label.replace("&", "").rstrip(".").strip()


def test_every_french_label_is_in_the_interface():
    shown = {plain(key) for key in catalogue()}
    quoted = set(re.findall(r"« ([^»]+?) »", read(FRENCH)))
    assert len(quoted) > 40
    missing = sorted(q for q in quoted if plain(q) not in shown)
    assert not missing, missing


def test_every_english_label_is_in_the_interface():
    shown = {plain(value) for value in catalogue().values()}
    quoted = set(re.findall(r"“([^”]+?)”", read(ENGLISH)))
    assert len(quoted) > 40
    missing = sorted(q for q in quoted if plain(q) not in shown)
    assert not missing, missing


def test_both_pages_say_the_same_number_of_things():
    """Kept side by side: same sections, same rows in each table."""
    def shape(text):
        return ([line.count("|") for line in text.splitlines()
                 if line.startswith("|")],
                len(re.findall(r"^## ", text, re.M)),
                len(re.findall(r"^- ", text, re.M)))
    assert shape(read(FRENCH)) == shape(read(ENGLISH))


def slug(heading: str) -> str:
    """GitHub's anchor for a heading."""
    text = unicodedata.normalize("NFC", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


@pytest.mark.parametrize("page", [FRENCH, ENGLISH])
def test_the_links_land(page):
    folder = os.path.dirname(page)
    for target in re.findall(r"\]\(([^)]+)\)", read(page)):
        if target.startswith("http"):
            assert target.startswith("https://github.com/Pierokarei/Plotea")
            continue
        path, _, anchor = target.partition("#")
        full = os.path.normpath(os.path.join(folder, path))
        assert os.path.exists(full), target
        if anchor:
            headings = re.findall(r"^#+ (.+)$", read(full), re.M)
            assert anchor in {slug(h) for h in headings}, target


def test_the_readmes_point_to_it():
    assert "(docs/prism-vers-plotea.md)" in read(os.path.join(ROOT,
                                                              "README.md"))
    assert "(docs/from-prism.md)" in read(os.path.join(ROOT, "README.en.md"))


def test_it_describes_the_version_people_have():
    """Read again at each new minor version, so that it stays true."""
    major_minor = ".".join(__version__.split(".")[:2])
    for page in (FRENCH, ENGLISH):
        assert f"Plotea {major_minor}." in read(page), (
            "relisez la page Prism -> Plotea pour la version " + __version__)


def test_what_it_says_is_missing_is_still_missing():
    """If one of these arrives, the page must say so."""
    tests = {choice.key for choice in enums.STATS_TEST}
    corrections = {choice.key for choice in enums.CORRECTION}
    models = {choice.key for choice in enums.FIT_MODEL}
    assert not {"friedman", "welch_anova", "brown_forsythe"} & tests
    assert "sidak" not in corrections
    assert not {"hill5", "hill5_log"} & models


def test_the_help_menu_opens_it_in_the_interface_language(window,
                                                          monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    from plotea import i18n

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: opened.append(url.toString())))
    window.a_prism_guide.trigger()
    page = "prism-vers-plotea.md" if i18n.language() == "fr" \
        else "from-prism.md"
    assert opened == [
        f"https://github.com/Pierokarei/Plotea/blob/main/docs/{page}"]
