"""Releases: one version number, and archives that keep what users need.

A release is built by .github/workflows/release.yml on a machine nobody
watches. What can be checked before pushing a tag is checked here: that the
version cannot disagree with itself, that each system gets an archive that
keeps what its build needs, and that the notes name the files actually built.
"""
import os
import re
import sys
import tarfile
import zipfile

import pytest

from plotea import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_app  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


# --------------------------------------------------------------------------
# One version number
# --------------------------------------------------------------------------
def test_the_version_is_written_once():
    """pyproject, the window and the macOS bundle all read __version__."""
    pyproject = read("pyproject.toml")
    assert 'dynamic = ["version"]' in pyproject
    assert 'attr = "plotea.__version__"' in pyproject
    assert not re.search(r'^version\s*=\s*"', pyproject, re.M), \
        "une deuxième version écrite en dur dans pyproject.toml"
    assert build_app.version() == __version__

    from plotea.ui.main_window import VERSION
    assert VERSION == __version__

    spec = read("plotea.spec")
    assert '"CFBundleShortVersionString": __version__' in spec
    assert not re.search(r'"\d+\.\d+\.\d+"', spec), \
        "une version écrite en dur dans plotea.spec"


def test_the_version_is_one_a_tag_can_match():
    """The release workflow compares it with the tag v<version>."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


# --------------------------------------------------------------------------
# Archives
# --------------------------------------------------------------------------
@pytest.mark.parametrize("platform, name", [
    ("win32", "Plotea-2.3.4-windows.zip"),
    ("darwin", "Plotea-2.3.4-macos.zip"),
    ("linux", "Plotea-2.3.4-linux.tar.gz"),
])
def test_archive_names(platform, name):
    assert build_app.archive_name("2.3.4", platform) == name


@pytest.fixture
def built(tmp_path, monkeypatch):
    """A stand-in for dist/Plotea, as PyInstaller leaves it."""
    folder = tmp_path / "Plotea"
    (folder / "_internal" / "plotea" / "locales").mkdir(parents=True)
    (folder / "_internal" / "plotea" / "locales" / "en.json").write_text("{}")
    binary = folder / "Plotea"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setattr(build_app, "DIST", str(tmp_path))
    return tmp_path


def test_the_windows_archive_holds_the_whole_folder(built):
    path = build_app.make_archive("win32")
    assert os.path.basename(path) == f"Plotea-{__version__}-windows.zip"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    # one Plotea folder at the top: "Extraire tout" gives a tidy folder
    assert {n.split("/")[0] for n in names} == {"Plotea"}
    assert "Plotea/_internal/plotea/locales/en.json" in names


def test_packing_again_replaces_the_archive(built):
    first = build_app.make_archive("win32")
    (built / "Plotea" / "new.txt").write_text("x")
    second = build_app.make_archive("win32")
    assert first == second
    with zipfile.ZipFile(second) as archive:
        assert "Plotea/new.txt" in archive.namelist()


@pytest.mark.skipif(sys.platform.startswith("win"),
                    reason="Windows ne connaît ni le bit x ni ces liens")
def test_the_linux_archive_keeps_what_a_zip_would_lose(built):
    """The executable bit, and symbolic links, survive the round trip."""
    os.symlink("Plotea", built / "Plotea" / "link")
    path = build_app.make_archive("linux")
    with tarfile.open(path) as archive:
        binary = archive.getmember("Plotea/Plotea")
        link = archive.getmember("Plotea/link")
    assert binary.mode & 0o111, "Plotea ne serait plus exécutable"
    assert link.issym()


# --------------------------------------------------------------------------
# What the release promises
# --------------------------------------------------------------------------
def test_the_notes_name_every_archive_built():
    notes = read(".github", "release-notes.md")
    for platform in ("win32", "darwin", "linux"):
        assert build_app.archive_name("{version}", platform) in notes
    assert "## Installer Plotea" in notes and "## Installing Plotea" in notes


def test_the_release_is_a_draft_built_from_tested_code():
    """Nothing goes public by itself, and only what passed the tests."""
    workflow = read(".github", "workflows", "release.yml")
    assert "--draft" in workflow
    assert "tools/build_app.py --archive" in workflow
    assert "build_app.py --notes notes.md" in workflow
    assert "--workflow tests.yml" in workflow
    assert '"v$version"' in workflow


def test_this_version_says_what_changed():
    """Tagging a version with no notes of its own fails here, not on the page."""
    notes = build_app.release_notes(__version__)
    french, english = notes.split('<a id="english"></a>')
    assert f"## Nouveautés de la version {__version__}" in french
    assert f"## What's new in {__version__}" in english
    # each language's changes sit above its own installation guide
    assert french.index("## Nouveautés") < french.index("## Installer")
    assert english.index("## What's new") < english.index("## Installing")
    assert not re.search(r"\{(version|changes_fr|changes_en)\}", notes)
    assert build_app.CHANGES_SPLIT not in notes


def test_a_version_without_changes_keeps_a_clean_page():
    notes = build_app.release_notes("0.0.1")
    assert not re.search(r"\{\w+\}", notes)
    assert "## Nouveautés" not in notes and "\n\n\n" not in notes
    assert "Plotea-0.0.1-windows.zip" in notes
