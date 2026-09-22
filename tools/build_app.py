"""Build the standalone application for the current platform.

    pip install pyinstaller
    python tools/build_app.py

Regenerates the icons, runs PyInstaller against plotea.spec and, on Linux,
writes a .desktop file next to the binary. The result lands in dist/.
"""
from __future__ import annotations

import os
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


def main() -> int:
    make_icons()
    code = build()
    if code:
        print("Build echoue.")
        return code
    write_desktop_entry()
    report()
    print("\nTermine. Distribuez le dossier dist/Plotea tel quel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
