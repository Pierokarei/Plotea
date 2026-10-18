"""The statistical validation page cites tests that exist.

The page tells a reviewer which test holds each result. A test renamed or
removed would leave it pointing at nothing, so every test it cites must be
defined where it says, both languages must cite the same ones, and the page
must be reachable: from the README and from the Help menu.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRENCH = os.path.join(ROOT, "docs", "validation-statistique.md")
ENGLISH = os.path.join(ROOT, "docs", "statistical-validation.md")
CITED = re.compile(r"`((?:[\w]+/)?test_\w+\.py)::(test_\w+)`")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cited(path):
    return set(CITED.findall(read(path)))


@pytest.mark.parametrize("page", [FRENCH, ENGLISH])
def test_every_test_it_cites_is_defined_where_it_says(page):
    citations = cited(page)
    assert len(citations) > 60, len(citations)
    for file, name in sorted(citations):
        path = os.path.join(ROOT, "tests", *file.split("/"))
        assert os.path.exists(path), file
        assert re.search(rf"^def {name}\(", read(path), re.MULTILINE), \
            f"{file}::{name}"


def test_both_languages_cite_the_same_tests_in_the_same_sections():
    assert cited(FRENCH) == cited(ENGLISH)

    def shape(text):
        return [len(CITED.findall(section))
                for section in re.split(r"^## ", text, flags=re.MULTILINE)]
    assert shape(read(FRENCH)) == shape(read(ENGLISH))


def test_every_file_of_numerical_checks_is_cited():
    """A new file of statistical tests belongs on the page."""
    files = {file for file, _ in cited(FRENCH)}
    for name in ("test_validation.py", "test_recommended.py",
                 "test_advanced_stats.py", "test_anova.py", "test_auc.py",
                 "test_bland_altman.py", "test_contingency.py",
                 "test_fit_compare.py", "test_heatmap.py", "test_roc.py",
                 "test_standard_curve.py", "test_survival.py"):
        assert name in files, name


def test_the_pages_point_to_each_other_and_the_readmes_to_them():
    assert "(statistical-validation.md)" in read(FRENCH)
    assert "(validation-statistique.md)" in read(ENGLISH)
    assert "(docs/validation-statistique.md)" in read(
        os.path.join(ROOT, "README.md"))
    assert "(docs/statistical-validation.md)" in read(
        os.path.join(ROOT, "README.en.md"))


def test_the_help_menu_opens_it_in_the_interface_language(window,
                                                          monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    from plotea import i18n

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda url: opened.append(url.toString())))
    window.a_validation.trigger()
    page = "validation-statistique.md" if i18n.language() == "fr" \
        else "statistical-validation.md"
    assert opened == [
        f"https://github.com/Pierokarei/Plotea/blob/main/docs/{page}"]
