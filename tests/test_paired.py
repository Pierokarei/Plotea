"""Before-after plots: one line per subject, and a paired test behind them.

The point of the plot is the pairing, so it is checked everywhere it could
be lost: every subject gets its line, a missing measurement neither hides a
subject nor invents a value, the points sit exactly on their condition for
the lines to reach them, and the recommended test is the paired t here -
the plot declares the same subjects - while other plots ask for the design.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats as sps

from plotea.core import demo, plotting
from plotea.core.methods import methods_text
from plotea.core.plotspec import PlotSpec

GREY = "#9AA0A6"


def wide(n=12, seed=31, shift=9.0, skew=False):
    rng = np.random.default_rng(seed)
    before = rng.normal(148, 11, n)
    change = rng.exponential(12, n) ** 1.6 if skew else \
        rng.normal(shift, 7, n)
    return pd.DataFrame({"Patient": [f"P{i}" for i in range(n)],
                         "Avant": before, "Après": before - change})


def long(conditions=("J0", "J7", "J28"), n=10, missing=()):
    rng = np.random.default_rng(7)
    rows = []
    for s in range(n):
        base = rng.normal(50, 8)
        for i, t in enumerate(conditions):
            if (s, t) in missing:
                continue
            rows.append({"Patient": f"P{s}", "Jour": t,
                         "Score": base + 4 * i + rng.normal(0, 3)})
    return pd.DataFrame(rows)


def render(df, **fields):
    figure = Figure()
    spec = PlotSpec(plot_type="paired", stats_enabled=True, **fields)
    info = plotting.render(figure, spec, df)
    return figure.axes[0], info


def subject_lines(ax):
    return [line for line in ax.lines if line.get_color() == GREY]


# --------------------------------------------------------------------------
# The lines
# --------------------------------------------------------------------------
def test_every_subject_gets_its_line_in_wide_format():
    ax, info = render(wide(), y=["Avant", "Après"])
    assert info.subjects == 12
    assert len(subject_lines(ax)) == 12
    df = wide()
    ends = {tuple(np.round(line.get_ydata(), 6)) for line in subject_lines(ax)}
    assert ends == {tuple(np.round(row, 6))
                    for row in df[["Avant", "Après"]].to_numpy()}


def test_long_format_pairs_by_the_subject_column():
    ax, info = render(long(), group="Jour", y=["Score"],
                      stats_pair_by="Patient")
    assert info.subjects == 10
    assert len(subject_lines(ax)) == 10 * 2       # two segments each
    assert [t.get_text() for t in ax.get_xticklabels()] == ["J0", "J7",
                                                            "J28"]


def test_a_missing_middle_value_is_bridged_by_a_dotted_line():
    ax, info = render(long(missing={(3, "J7")}), group="Jour", y=["Score"],
                      stats_pair_by="Patient")
    assert info.subjects == 10                     # P3 not hidden
    dotted = [line for line in subject_lines(ax)
              if line.get_linestyle() == ":"]
    assert len(dotted) == 1
    assert list(dotted[0].get_xdata()) == [0.0, 2.0]   # J0 to J28


def test_without_the_subject_column_it_says_what_is_missing():
    ax, info = render(long(), group="Jour", y=["Score"])
    assert not subject_lines(ax)
    assert any("Appariement" in w for w in info.warnings)
    assert not info.comparisons


def test_points_sit_exactly_on_their_condition():
    ax, _info = render(wide(), y=["Avant", "Après"])
    xs = np.concatenate([c.get_offsets()[:, 0] for c in ax.collections])
    assert set(np.round(xs, 9)) == {0.0, 1.0}


def test_the_mean_and_its_error_can_be_turned_off():
    ax, _ = render(wide(), y=["Avant", "Après"])
    assert ax.containers                           # the errorbars
    ax, _ = render(wide(), y=["Avant", "Après"], error_type="none")
    assert not ax.containers


def test_one_condition_is_not_a_before_after():
    ax, info = render(wide()[["Avant"]], y=["Avant"])
    assert any("deux conditions" in w for w in info.warnings)


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------
def test_auto_means_a_paired_t_test_on_normal_differences():
    df = wide()
    _ax, info = render(df, y=["Avant", "Après"])
    assert info.test_used == "paired_t"
    expected = sps.ttest_rel(df["Avant"], df["Après"]).pvalue
    assert info.comparisons[0].p == pytest.approx(expected)


def test_skewed_differences_do_not_switch_to_wilcoxon():
    """The recommended test follows the design: a normality test on a few
    differences proves nothing either way, so it decides nothing."""
    df = wide(n=20, skew=True)
    _ax, info = render(df, y=["Avant", "Après"])
    assert info.test_used == "paired_t"
    expected = sps.ttest_rel(df["Avant"], df["Après"]).pvalue
    assert info.comparisons[0].p == pytest.approx(expected)
    # Wilcoxon stays one click away
    _ax, info = render(df, y=["Avant", "Après"], stats_test="wilcoxon")
    assert info.test_used == "wilcoxon"


def test_beyond_two_conditions_no_test_is_picked_for_you():
    _ax, info = render(long(), group="Jour", y=["Score"],
                       stats_pair_by="Patient")
    assert info.test_used == "" and not info.comparisons
    assert info.recommendation["test"] is None
    assert "Aucun test recommandé automatiquement" in info.warnings
    _ax, info = render(long(), group="Jour", y=["Score"],
                       stats_pair_by="Patient", stats_test="rm_anova")
    assert info.test_used == "rm_anova"
    assert info.omnibus[0] == "ANOVA à mesures répétées"
    assert {c.test for c in info.comparisons} == {"t apparié"}


def test_other_plots_ask_for_the_design():
    spec = PlotSpec(plot_type="bar", y=["Avant", "Après"], stats_enabled=True)
    info = plotting.render(Figure(), spec, wide())
    assert info.test_used == "" and not info.comparisons
    assert "Précisez le plan expérimental" in info.warnings
    spec.design = "independent"
    info = plotting.render(Figure(), spec, wide())
    assert info.test_used == "welch"


def test_a_test_chosen_by_name_is_respected():
    _ax, info = render(wide(), y=["Avant", "Après"], stats_test="wilcoxon")
    assert info.test_used == "wilcoxon"


# --------------------------------------------------------------------------
# Methods, saving, the window
# --------------------------------------------------------------------------
def test_the_methods_paragraph_describes_the_pairing():
    spec = PlotSpec(plot_type="paired", y=["Avant", "Après"],
                    stats_enabled=True)
    info = plotting.render(Figure(), spec, wide())
    text = methods_text(spec, info, "en")
    assert "Each line joins the values of one subject (n = 12 subjects)" \
        in text
    assert ("chosen a priori from the experimental design (the same "
            "subjects in both conditions)") in text
    assert "two-tailed paired t tests" in text
    assert "each row of the table being one subject" in text
    assert "Chaque ligne relie" in methods_text(spec, info, "fr")


def test_the_plot_type_survives_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="AA", plot_type="paired",
                              y=["Avant", "Après"]))
    spec = Project.load(project.save(str(tmp_path / "p.plotea"))).plots[-1]
    assert spec.plot_type == "paired"


def choose_paired(window):
    for button in window.inspector.type_buttons.buttons():
        if button.property("plot_type") == "paired":
            button.click()


def test_from_a_bar_chart_the_subject_id_is_not_taken_for_a_condition(
        window):
    window.load_example("Pression artérielle (avant/après)")
    choose_paired(window)
    spec = window.current_spec()
    assert (spec.group, spec.y, spec.stats_pair_by) == \
        ("", ["Avant", "Après"], "Patient")
    assert not window.inspector.cmb_pair.isHidden()
    assert not window.inspector.spn_jitter.isEnabled()


def test_long_data_find_their_conditions_and_subjects(window):
    from plotea.core.dataset import Dataset

    window.project.add_dataset(Dataset("Suivi", long()))
    spec = window.current_spec()
    spec.dataset = "Suivi"
    spec.y = []
    choose_paired(window)
    assert (spec.group, spec.y, spec.stats_pair_by) == \
        ("Jour", ["Score"], "Patient")


def test_the_example_reads_as_a_drop():
    df = demo.paired().df
    assert list(df.columns) == ["Patient", "Avant", "Après"]
    assert (df["Avant"] > df["Après"]).mean() > 0.7
