"""Build the standalone application for the current platform.

    pip install pyinstaller
    python tools/build_app.py             # dist/Plotea (dist/Plotea.app)
    python tools/build_app.py --archive   # plus the archive to hand out
    python tools/build_app.py --notes notes.md   # the release page only

Regenerates the icons, runs PyInstaller against plotea.spec and, on Linux,
writes a .desktop file next to the binary. The result lands in dist/.

--archive packs what a user downloads: Plotea-<version>-<system>.zip on
Windows and macOS, .tar.gz on Linux. Each system gets the format that keeps
what its build needs - the symbolic links inside a macOS bundle, the
executable bit on Linux - which a plain zip written by Python would lose.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Plotea
GenericName=Figures scientifiques
Comment=Figures de qualite publication, libres et gratuites
Exec={exec_path} %f
Icon={icon_path}
Terminal=false
Categories=Science;Education;Graphics;
MimeType=application/x-plotea;
StartupWMClass=Plotea
"""


def run(command: list[str]) -> int:
    print("->", " ".join(command))
    return subprocess.call(command, cwd=ROOT)


def make_icons() -> None:
    code = run([sys.executable, os.path.join("tools", "make_icons.py")])
    if code:
        print("Generation des icones echouee : le build continue sans.")


def build() -> int:
    if shutil.which("pyinstaller") is None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            print("PyInstaller manquant : pip install pyinstaller")
            return 1
    return run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                "--clean", "plotea.spec"])


def write_desktop_entry() -> None:
    if not sys.platform.startswith("linux"):
        return
    target = os.path.join(DIST, "Plotea")
    binary = os.path.join(target, "Plotea")
    icon = os.path.join(target, "plotea", "resources", "plotea.png")
    if not os.path.exists(binary):
        return
    path = os.path.join(DIST, "plotea.desktop")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(DESKTOP_ENTRY.format(exec_path=binary, icon_path=icon))
    print("ecrit", path)
    print("Installer avec : desktop-file-install --dir=~/.local/share/"
          "applications", path)


def report() -> None:
    if not os.path.isdir(DIST):
        return
    total = 0
    for folder, _, files in os.walk(DIST):
        for name in files:
            total += os.path.getsize(os.path.join(folder, name))
    print(f"\ndist/ : {total / 1e6:.0f} Mo")
    for entry in sorted(os.listdir(DIST)):
        print("  ", entry)


def version() -> str:
    """Read from plotea/__init__.py without importing the package."""
    path = os.path.join(ROOT, "plotea", "__init__.py")
    with open(path, encoding="utf-8") as handle:
        found = re.search(r'^__version__ = "([^"]+)"', handle.read(), re.M)
    if found is None:
        raise RuntimeError("__version__ introuvable dans plotea/__init__.py")
    return found.group(1)


def system(platform: str = sys.platform) -> str:
    if platform.startswith("win"):
        return "windows"
    if platform == "darwin":
        return "macos"
    return "linux"


def archive_name(number: str, platform: str = sys.platform) -> str:
    kind = system(platform)
    extension = "tar.gz" if kind == "linux" else "zip"
    return f"Plotea-{number}-{kind}.{extension}"


CHANGES_SPLIT = "<!-- english -->"


def release_notes(number: str) -> str:
    """The release page: what changed in this version, then how to install.

    .github/changes/<version>.md holds the French changes, then the English
    ones after CHANGES_SPLIT; each lands at the top of its language's half
    of .github/release-notes.md.
    """
    with open(os.path.join(ROOT, ".github", "release-notes.md"),
              encoding="utf-8") as handle:
        notes = handle.read()
    path = os.path.join(ROOT, ".github", "changes", f"{number}.md")
    french = english = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            french, _, english = handle.read().partition(CHANGES_SPLIT)
    for key, text in (("{changes_fr}", french), ("{changes_en}", english)):
        notes = notes.replace(f"{key}\n\n", f"{text.strip()}\n\n"
                              if text.strip() else "")
    return notes.replace("{version}", number)


def make_archive(platform: str = sys.platform) -> str:
    """Pack the build in dist/ into the archive users download."""
    kind = system(platform)
    target = os.path.join(DIST, archive_name(version(), platform))
    if os.path.exists(target):
        os.remove(target)
    if kind == "macos":
        # ditto is what the Finder uses: it keeps the bundle's symbolic links
        # and extended attributes, which zipfile would flatten
        code = subprocess.call(["ditto", "-c", "-k", "--sequesterRsrc",
                                "--keepParent", "Plotea.app", target],
                               cwd=DIST)
        if code:
            raise RuntimeError("ditto a échoué")
    else:
        stem = target[:-len(".tar.gz")] if kind == "linux" else target[:-4]
        shutil.make_archive(stem, "gztar" if kind == "linux" else "zip",
                            root_dir=DIST, base_dir="Plotea")
    print("archive", target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", action="store_true",
                        help="emballer aussi l'archive à distribuer")
    parser.add_argument("--notes", metavar="FICHIER",
                        help="écrire seulement les notes de version")
    options = parser.parse_args(argv)
    if options.notes:
        with open(options.notes, "w", encoding="utf-8") as handle:
            handle.write(release_notes(version()))
        return 0
    make_icons()
    code = build()
    if code:
        print("Build echoue.")
        return code
    write_desktop_entry()
    archive = make_archive() if options.archive else ""
    report()
    if archive:
        print(f"\nTermine. Distribuez {os.path.basename(archive)}.")
    else:
        print("\nTermine. Distribuez le dossier dist/Plotea tel quel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
