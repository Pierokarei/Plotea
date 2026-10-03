"""Time a render and each export, per theme, and say which fonts were found.

    python tools/render_timing.py

Written for a CI runner whose log cannot be read without an account: every
result is also printed as a GitHub annotation (::notice), which can. A
render that takes seconds instead of milliseconds on one system shows up
here in a minute, instead of as a test suite that never finishes.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from matplotlib.figure import Figure  # noqa: E402

from plotea.core import demo, export, plotting  # noqa: E402
from plotea.core.plotspec import PlotSpec  # noqa: E402
from plotea.core.themes import get_theme, installed_fonts  # noqa: E402

FORMATS = {"pdf": "PDF (vectoriel, publication)",
           "svg": "SVG (vectoriel, éditable)",
           "eps": "EPS (vectoriel, legacy)",
           "png": "PNG (raster)"}


def say(title: str, message: str):
    print(f"{title}: {message}")
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::notice title={title}::{message}")
    sys.stdout.flush()


def timed(action) -> float:
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


def main() -> int:
    folder = tempfile.mkdtemp()
    data = demo.viability().df
    for name in ("Nature", "Cell"):
        theme = get_theme(name)
        fonts = installed_fonts(tuple(theme.font_family))
        say(f"polices {name}", ", ".join(fonts))
        spec = PlotSpec(theme=name, plot_type="bar", group="Traitement",
                        y=["Viabilité"], stats_enabled=True)
        figure = Figure(figsize=theme.figsize("single"))
        first = timed(lambda: plotting.render(figure, spec, data))
        again = timed(lambda: plotting.render(figure, spec, data))
        say(f"rendu {name}", f"premier {first:.2f} s, suivant {again:.2f} s")
        for ext, fmt in FORMATS.items():
            options = export.ExportOptions(
                os.path.join(folder, f"{name}.{ext}"), fmt)
            seconds = timed(lambda: export.save_figure(figure, options))
            say(f"export {name} {ext}", f"{seconds:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
