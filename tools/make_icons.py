"""Render the application icon to the files installers need.

Produces plotea.png (512 px), plotea.ico (Windows, multi-resolution) and, on
macOS, plotea.icns. Run it again after changing `plotea/resources/draw_logo`.

    python tools/make_icons.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from plotea.resources import HERE, ICON_SIZES, logo_pixmap  # noqa: E402


def write_pngs(folder: str) -> dict[int, str]:
    paths = {}
    for size in ICON_SIZES:
        path = os.path.join(folder, f"icon_{size}.png")
        logo_pixmap(size).save(path, "PNG")
        paths[size] = path
    return paths


def build_ico(pngs: dict[int, str], target: str):
    from PIL import Image
    sizes = [s for s in ICON_SIZES if s <= 256]
    base = Image.open(pngs[max(sizes)]).convert("RGBA")
    base.save(target, format="ICO", sizes=[(s, s) for s in sizes])
    print("ecrit", target)


def build_icns(pngs: dict[int, str], target: str):
    """macOS only: iconutil needs a .iconset folder."""
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        print("icns ignore (macOS et iconutil requis)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "plotea.iconset")
        os.makedirs(iconset)
        for size in (16, 32, 128, 256, 512):
            shutil.copy(pngs[size], os.path.join(iconset,
                                                 f"icon_{size}x{size}.png"))
            double = size * 2
            if double in pngs:
                shutil.copy(pngs[double],
                            os.path.join(iconset,
                                         f"icon_{size}x{size}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", target],
                       check=True)
    print("ecrit", target)


def main() -> int:
    app = QApplication(sys.argv)          # QPixmap needs a running app
    with tempfile.TemporaryDirectory() as tmp:
        pngs = write_pngs(tmp)
        main_png = os.path.join(HERE, "plotea.png")
        logo_pixmap(512).save(main_png, "PNG")
        print("ecrit", main_png)
        build_ico(pngs, os.path.join(HERE, "plotea.ico"))
        build_icns(pngs, os.path.join(HERE, "plotea.icns"))
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
