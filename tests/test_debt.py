"""Keys vs labels, the error log, and behaviour on large tables."""
import os
import time

import numpy as np
import pandas as pd
from matplotlib.figure import Figure


from plotea.core import diagnostics, enums, fitting, plotting, stats  # noqa: E402
from plotea.core import transforms  # noqa: E402
from plotea.core.panel import Panel  # noqa: E402
from plotea.core.plotspec import PlotSpec  # noqa: E402
from plotea.core.project import Project  # noqa: E402
from plotea.core.dataset import Dataset  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)


def test_every_enum_round_trips():
    for name, enum in vars(enums).items():
        if not isinstance(enum, enums.Enum):
            continue
        assert enum.keys(), name
        assert len(set(enum.keys())) == len(enum.keys()), f"{name}: doublons"
        assert len(set(enum.labels())) == len(enum.labels()), name
        for choice in enum:
            assert enum.normalise(choice.key) == choice.key, choice
            assert enum.normalise(choice.label) == choice.key, choice
            assert enum.label(choice.key) == choice.label
            assert enum.key(choice.label) == choice.key


def test_labels_are_not_stored():
    """A spec built with French wording stores the key."""
    spec = PlotSpec(plot_type="bar", error_type="SEM", stats_test="t de Welch",
                    stats_format="Étoiles", stats_correction="Holm",
                    fit_model="Dose-reponse log", point_style="Jitter",
                    hist_stat="Effectif", violin_inner="Boxplot",
                    stats_mode="Toutes les paires",
                    fit_equation_loc="Haut gauche")
    data = spec.to_dict()
    assert data["error_type"] == "sem", data["error_type"]
    assert data["stats_test"] == "welch"
    assert data["stats_format"] == "stars"
    assert data["stats_correction"] == "holm"
    assert data["fit_model"] == "hill4_log"
    assert data["point_style"] == "jitter"
    assert data["hist_stat"] == "count"
    assert data["violin_inner"] == "box"
    assert data["stats_mode"] == "all_pairs"
    assert data["fit_equation_loc"] == "top left"

    french = {v for v in data.values() if isinstance(v, str)}
    assert not french & {"SEM", "Étoiles", "Holm", "Jitter", "Boxplot"}, french


def test_assignment_is_normalised_too():
    """Not just construction: a value set afterwards converts as well."""
    spec = PlotSpec()
    spec.error_type = "IC95"
    spec.stats_test = "t apparié"
    spec.fit_model = "Michaelis-Menten"
    assert spec.error_type == "ci95"
    assert spec.stats_test == "paired_t"
    assert spec.fit_model == "michaelis"

    panel = Panel()
    panel.letters = "(a), (b), (c)"
    assert panel.letters == "paren"


def test_legacy_project_still_opens():
    """A file written before keys existed must load and mean the same."""
    old = {"name": "Ancien", "plot_type": "bar", "error_type": "SD",
           "stats_test": "Mann-Whitney", "stats_correction": "Bonferroni",
           "stats_format": "p numérique", "fit_model": "Lineaire",
           "violin_inner": "Quartiles", "point_style": "Swarm",
           "span": "double", "legend_loc": "upper right"}
    spec = PlotSpec.from_dict(old)
    assert spec.error_type == "sd"
    assert spec.stats_test == "mannwhitney"
    assert spec.stats_correction == "bonferroni"
    assert spec.stats_format == "pvalue"
    assert spec.fit_model == "linear", spec.fit_model
    assert spec.violin_inner == "quartiles"
    assert spec.point_style == "swarm"
    assert spec.span == "double"
    assert spec.legend_loc == "upper right"


def test_unknown_value_falls_back():
    spec = PlotSpec(error_type="n'importe quoi")
    assert spec.error_type == enums.ERROR_TYPE.default


def test_engine_answers_to_keys_and_labels():
    """The public helpers accept either, so scripts keep working."""
    values = np.array([1.0, 2.0, 3.0, 4.0])
    assert stats.error_value(values, "sd") == stats.error_value(values, "SD")
    assert stats.format_p(0.001, "stars") == stats.format_p(0.001, "Étoiles")
    assert stats.adjust([0.01, 0.04], "holm") == stats.adjust([0.01, 0.04],
                                                              "Holm")
    x = np.linspace(1, 10, 20)
    by_key = fitting.fit(x, 2 * x + 1, "linear")
    by_label = fitting.fit(x, 2 * x + 1, "Lineaire")
    assert abs(by_key.r2 - by_label.r2) < 1e-12
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    p = transforms.Params(columns=["a"])
    assert transforms.apply("normalize", frame, p)[0].equals(
        transforms.apply("Normaliser de 0 a 100", frame, p)[0])


def test_saved_project_is_language_neutral():
    spec = PlotSpec(name="G", plot_type="violin", error_type="SEM",
                    stats_format="Étoiles")
    project = Project("P", [Dataset("T", pd.DataFrame({"a": [1.0, 2.0]}))],
                      [spec])
    path = project.save(os.path.join(OUT, "keys.plotea"))
    import json
    import zipfile
    with zipfile.ZipFile(path) as zf:
        raw = json.loads(zf.read("project.json").decode("utf-8"))
    stored = raw["plots"][0]
    assert stored["error_type"] == "sem"
    assert stored["stats_format"] == "stars"
    assert Project.load(path).plots[0].error_type == "sem"


def test_a_broken_render_leaves_a_trace():
    diagnostics.LOG.clear()
    spec = PlotSpec(name="Casse", plot_type="bar", group="g", y=["v"],
                    stats_enabled=True)
    frame = pd.DataFrame({"g": ["a", "b"] * 5, "v": range(10)})

    def explode(*args, **kwargs):
        raise ValueError("panne simulee")

    original = plotting.DRAWERS["bar"]
    plotting.DRAWERS["bar"] = explode
    try:
        info = plotting.render(Figure(), spec, frame)
    finally:
        plotting.DRAWERS["bar"] = original

    assert any("panne simulee" in w for w in info.warnings), info.warnings
    assert any("Journal" in w for w in info.warnings), info.warnings
    assert len(diagnostics.LOG) == 1, len(diagnostics.LOG)
    entry = diagnostics.LOG.entries[0]
    assert "Casse" in entry.context, entry.context
    assert "ValueError" in entry.summary
    assert "panne simulee" in entry.detail
    assert "Traceback" in entry.detail, "la trace complete doit etre gardee"


def test_log_is_bounded_and_readable():
    diagnostics.LOG.clear()
    for i in range(diagnostics.MAX_ENTRIES + 40):
        diagnostics.record("Test", f"evenement {i}")
    assert len(diagnostics.LOG) == diagnostics.MAX_ENTRIES
    text = diagnostics.LOG.text()
    assert "evenement 239" in text
    assert "evenement 0" not in text          # oldest dropped
    diagnostics.LOG.clear()
    assert "Aucune erreur" in diagnostics.LOG.text()


def test_log_writes_to_disk():
    folder = os.path.join(OUT, "journal")
    path = diagnostics.use_file(folder)
    diagnostics.LOG.clear()
    diagnostics.record("Contexte", "message de test", "detail\nsur deux lignes")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "message de test" in content and "deux lignes" in content
    diagnostics.LOG.path = ""


big = pd.DataFrame({
    "x": np.random.default_rng(1).normal(0, 1, 120_000),
    "y": np.random.default_rng(2).normal(0, 1, 120_000),
    "g": np.tile(["A", "B", "C"], 40_000),
})


def test_big_scatter_is_fast_and_rasterised():
    spec = PlotSpec(plot_type="scatter", x="x", y=["y"])
    fig = Figure(figsize=(3.5, 2.7))
    start = time.perf_counter()
    plotting.render(fig, spec, big)
    elapsed = time.perf_counter() - start
    assert elapsed < 12.0, f"{elapsed:.1f} s pour 120 000 points"
    collections = fig.axes[0].collections
    assert collections and collections[0].get_rasterized(), \
        "un gros nuage doit etre rasterise dans la sortie vectorielle"


def test_big_box_caps_the_overlay():
    spec = PlotSpec(plot_type="box", group="g", y=["y"], show_points=True)
    fig = Figure(figsize=(3.5, 2.7))
    info = plotting.render(fig, spec, big)
    assert any("limite" in w for w in info.warnings), info.warnings
    drawn = sum(c.get_offsets().shape[0] for c in fig.axes[0].collections)
    assert drawn <= 3 * plotting.MAX_OVERLAY_POINTS, drawn
    # the statistics still see everything
    assert all(v.size == 40_000 for v in info.stat_groups.values())


def test_big_violin_stays_responsive():
    spec = PlotSpec(plot_type="violin", group="g", y=["y"], show_points=False)
    fig = Figure(figsize=(3.5, 2.7))
    start = time.perf_counter()
    plotting.render(fig, spec, big)
    assert time.perf_counter() - start < 15.0


def test_big_histogram_kde_samples():
    spec = PlotSpec(plot_type="histogram", y=["y"], hist_kde=True)
    fig = Figure(figsize=(3.5, 2.7))
    start = time.perf_counter()
    info = plotting.render(fig, spec, big)
    assert time.perf_counter() - start < 10.0
    assert not info.warnings, info.warnings


def test_vector_export_of_big_data_stays_small():
    spec = PlotSpec(plot_type="scatter", x="x", y=["y"])
    fig = Figure(figsize=(3.5, 2.7))
    plotting.render(fig, spec, big)
    path = os.path.join(OUT, "gros.pdf")
    fig.savefig(path, dpi=300)
    size = os.path.getsize(path)
    assert size < 3_000_000, f"{size / 1e6:.1f} Mo : rasterisation inefficace"
