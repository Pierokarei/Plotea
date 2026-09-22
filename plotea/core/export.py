"""Figure export: vector (SVG/PDF/EPS) and raster (PNG/TIFF) at print DPI."""
from __future__ import annotations

import os
from dataclasses import dataclass

from matplotlib.figure import Figure

#: label -> (extension, matplotlib format, vector?)
FORMATS = {
    "SVG (vectoriel, éditable)": (".svg", "svg", True),
    "PDF (vectoriel, publication)": (".pdf", "pdf", True),
    "EPS (vectoriel, legacy)": (".eps", "eps", True),
    "PNG (raster)": (".png", "png", False),
    "TIFF (raster, LZW)": (".tiff", "tiff", False),
    "JPEG (raster)": (".jpg", "jpeg", False),
}

DPI_PRESETS = [72, 150, 300, 600, 1200]
DEFAULT_DPI = 600


@dataclass
class ExportOptions:
    path: str
    fmt: str = "PNG (raster)"
    dpi: int = DEFAULT_DPI
    transparent: bool = False
    tight: bool = True
    pad_inches: float = 0.02
    width_mm: float | None = None
    height_mm: float | None = None


def filter_string() -> str:
    """Qt file-dialog filter built from FORMATS."""
    parts = [f"{label} (*{ext})" for label, (ext, _, _) in FORMATS.items()]
    return ";;".join(parts)


def format_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    for label, (e, _, _) in FORMATS.items():
        if e == ext:
            return label
    return "PNG (raster)"


def is_vector(fmt: str) -> bool:
    return FORMATS.get(fmt, (".png", "png", False))[2]


def save_figure(fig: Figure, options: ExportOptions) -> str:
    """Write `fig` to disk, returning the final path."""
    ext, mpl_fmt, vector = FORMATS.get(options.fmt, (".png", "png", False))
    path = options.path
    if not path.lower().endswith(ext):
        path = os.path.splitext(path)[0] + ext

    original_size = fig.get_size_inches().copy()
    if options.width_mm and options.height_mm:
        fig.set_size_inches(options.width_mm / 25.4, options.height_mm / 25.4)

    kwargs = dict(format=mpl_fmt, transparent=options.transparent)
    if options.tight:
        kwargs["bbox_inches"] = "tight"
        kwargs["pad_inches"] = options.pad_inches
    if not vector:
        kwargs["dpi"] = options.dpi
    if mpl_fmt == "tiff":
        kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
    if mpl_fmt == "jpeg":
        kwargs["pil_kwargs"] = {"quality": 95}
    if mpl_fmt == "pdf":
        kwargs["metadata"] = {"Creator": "Plotea", "Producer": "matplotlib"}

    try:
        fig.savefig(path, **kwargs)
    finally:
        fig.set_size_inches(original_size)
    return path


def export_batch(figures: dict[str, Figure], folder: str, fmt: str,
                 dpi: int = DEFAULT_DPI, transparent: bool = False
                 ) -> list[str]:
    """Export several named figures into `folder`."""
    os.makedirs(folder, exist_ok=True)
    written = []
    for name, fig in figures.items():
        safe = "".join(c if c.isalnum() or c in " -_." else "_"
                       for c in name).strip() or "figure"
        opts = ExportOptions(os.path.join(folder, safe), fmt, dpi, transparent)
        written.append(save_figure(fig, opts))
    return written


def figure_to_png_bytes(fig: Figure, dpi: int = 300,
                        transparent: bool = False) -> bytes:
    """Rasterise to memory, used for 'copy to clipboard'."""
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.02, transparent=transparent)
    return buf.getvalue()


def figure_to_svg_text(fig: Figure) -> str:
    import io
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.02)
    return buf.getvalue()
