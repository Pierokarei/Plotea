"""Contingency tables: tests of independence, effect sizes and their plot.

The numbers are checked against published results, never against the code
that computes them: Agresti's aspirin and myocardial-infarction trial (odds
ratio 1.83, 95 % CI 1.44 to 2.33; relative risk 1.82), his party
identification by gender table (chi-square 30.07 on 2 df), Fisher's own
lady tasting tea (p = 0.486), and Yates' correction worked out by hand.
"""
import math

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea.core import plotting
from plotea.core import stats as st
from plotea.core.plotspec import PlotSpec

# Agresti, Categorical Data Analysis: aspirin vs placebo, MI yes / no
ASPIRIN = [[189, 10845],        # placebo
           [104, 10933]]        # aspirin
# Agresti: party identification (Democrat, Independent, Republican) by gender
PARTY = [[762, 327, 468],       # women
         [484, 239, 477]]       # men
TEA = [[3, 1], [1, 3]]          # Fisher's lady tasting tea


def effect(rows, name):
    return next(r for r in rows if r["Mesure"] == name)


# --------------------------------------------------------------------------
# Published values
# --------------------------------------------------------------------------
def test_odds_ratio_and_relative_risk_of_the_aspirin_trial():
    rows = st.contingency_effects(ASPIRIN)
    odds = effect(rows, "Odds ratio")
    assert odds["Valeur"] == pytest.approx(1.832, abs=5e-4)
    assert odds["IC95 bas"] == pytest.approx(1.44, abs=5e-3)
    assert odds["IC95 haut"] == pytest.approx(2.33, abs=5e-3)
    risk = effect(rows, "Risque relatif")
    assert risk["Valeur"] == pytest.approx(1.82, abs=5e-3)
    assert effect(rows, "Différence de proportions")["Valeur"] == \
        pytest.approx(189 / 11034 - 104 / 11037)


def test_chi_square_of_party_identification_by_gender():
    result = st.contingency(PARTY)
    assert result["test"] == "Khi² de Pearson"
    assert result["stat"] == pytest.approx(30.07, abs=5e-3)
    assert result["df"] == 2
    assert result["p"] < 1e-6
    assert not result["warning"]


def test_fisher_on_the_lady_tasting_tea():
    result = st.contingency(TEA)
    assert result["test"] == "Test exact de Fisher"
    assert result["p"] == pytest.approx(0.4857, abs=1e-4)
    assert math.isnan(result["stat"])          # Fisher has no statistic


def test_yates_correction_worked_out_by_hand():
    (a, b), (c, d) = ASPIRIN
    n = a + b + c + d
    by_hand = n * (abs(a * d - b * c) - n / 2) ** 2 / (
        (a + b) * (c + d) * (a + c) * (b + d))
    result = st.contingency(ASPIRIN, "chi2_yates")
    assert result["test"] == "Khi² avec correction de Yates"
    assert result["stat"] == pytest.approx(by_hand, rel=1e-10)


def test_cramers_v_from_its_definition():
    chi2 = st.contingency(PARTY, "chi2")["stat"]
    expected = math.sqrt(chi2 / (np.sum(PARTY) * 1))
    assert effect(st.contingency_effects(PARTY), "V de Cramér")["Valeur"] \
        == pytest.approx(expected)


# --------------------------------------------------------------------------
# Choosing the test, and saying when it is shaky
# --------------------------------------------------------------------------
def test_auto_is_fisher_on_2x2_and_chi_square_beyond():
    assert st.contingency(TEA)["test"] == "Test exact de Fisher"
    assert st.contingency(PARTY)["test"] == "Khi² de Pearson"


def test_fisher_asked_of_a_larger_table_falls_back_and_says_so():
    result = st.contingency(PARTY, "fisher")
    assert result["test"] == "Khi² de Pearson"
    assert "2 x 2" in result["warning"]


def test_small_expected_counts_are_flagged():
    result = st.contingency(TEA, "chi2")
    assert "Effectifs attendus faibles" in result["warning"]
    assert "Fisher" in result["warning"]


@pytest.mark.parametrize("table", [
    [[1, 2]],                   # one group
    [[0, 0], [0, 0]],           # nothing at all
    [[1.5, 2], [3, 4]],         # not counts
    [[-1, 2], [3, 4]],
])
def test_what_is_not_a_table_of_counts_is_refused(table):
    result = st.contingency(table)
    assert math.isnan(result["p"])
    assert result["warning"].startswith("Contingence")


def test_an_empty_row_is_left_out_rather_than_dividing_by_zero():
    with_empty = st.contingency([[3, 1], [0, 0], [1, 3]])
    assert with_empty["p"] == pytest.approx(st.contingency(TEA)["p"])


def test_an_empty_cell_gets_haldane_and_the_difference_does_not():
    rows = st.contingency_effects([[0, 5], [4, 0]])
    odds = effect(rows, "Odds ratio")
    assert odds["Correction"] == "Haldane"
    assert math.isfinite(odds["Valeur"]) and odds["Valeur"] > 0
    assert effect(rows, "Différence de proportions")["Valeur"] == -1.0


def test_each_pair_of_groups_and_its_correction():
    table = [[10, 20], [20, 10], [15, 15]]
    pairs = st.contingency_pairs(table, ["A", "B", "C"], correction="holm")
    assert [(c.a, c.b) for c in pairs] == [("A", "B"), ("A", "C"), ("B", "C")]
    raw = [c.p for c in pairs]
    assert [c.p_adj for c in pairs] == pytest.approx(
        st.adjust(raw, "holm"))
    against = st.contingency_pairs(table, ["A", "B", "C"], mode="vs_control",
                                   control="C")
    assert [(c.a, c.b) for c in against] == [("C", "A"), ("C", "B")]


# --------------------------------------------------------------------------
# Reading the data
# --------------------------------------------------------------------------
COUNTS = pd.DataFrame({"Bras": ["Traité", "Placebo"],
                       "Répondeurs": [28, 14], "Non-répondeurs": [12, 26]})


def raw_from(counts):
    """The same trial, one row per patient."""
    rows = []
    for _, line in counts.iterrows():
        for outcome in ("Répondeurs", "Non-répondeurs"):
            rows += [{"Bras": line["Bras"], "Issue": outcome}] * \
                int(line[outcome])
    return pd.DataFrame(rows)


def test_counts_and_raw_data_make_the_same_table():
    counts, groups, outcomes, problem = plotting.extract_contingency(
        COUNTS, PlotSpec(plot_type="contingency", group="Bras",
                         y=["Répondeurs", "Non-répondeurs"]))
    assert not problem
    raw = plotting.extract_contingency(
        raw_from(COUNTS), PlotSpec(plot_type="contingency", group="Bras",
                                   subgroup="Issue"))
    assert groups == raw[1] == ["Traité", "Placebo"]
    assert outcomes == raw[2] == ["Répondeurs", "Non-répondeurs"]
    assert np.array_equal(counts, raw[0])


def test_a_group_on_two_rows_is_added_up():
    split = pd.DataFrame({"Bras": ["T", "P", "T"], "Oui": [10, 5, 3],
                          "Non": [1, 9, 2]})
    counts, groups, _, _ = plotting.extract_contingency(
        split, PlotSpec(plot_type="contingency", group="Bras",
                        y=["Oui", "Non"]))
    assert groups == ["T", "P"]
    assert counts.tolist() == [[13, 3], [5, 9]]


def test_nothing_chosen_explains_what_to_choose():
    figure = Figure()
    info = plotting.render(figure, PlotSpec(plot_type="contingency"), COUNTS)
    assert any("Valeurs Y" in w and "Sous-groupe" in w for w in info.warnings)


# --------------------------------------------------------------------------
# The plot
# --------------------------------------------------------------------------
def render(**fields):
    figure = Figure()
    spec = PlotSpec(plot_type="contingency", group="Bras",
                    y=["Répondeurs", "Non-répondeurs"], **fields)
    info = plotting.render(figure, spec, COUNTS)
    return figure.axes[0], info


def stacks(ax):
    """Bar tops per x position, summed over the stacked segments."""
    tops = {}
    for patch in ax.patches:
        x = round(patch.get_x() + patch.get_width() / 2, 6)
        tops[x] = tops.get(x, 0) + patch.get_height()
    return sorted(tops.values())


def test_percentages_stack_to_a_hundred():
    ax, info = render()
    assert stacks(ax) == pytest.approx([100, 100])
    assert ax.get_ylabel() == "Pourcentage (%)"
    assert not info.warnings


def test_counts_stack_to_the_group_totals():
    ax, _ = render(contingency_view="stacked")
    assert stacks(ax) == pytest.approx([40, 40])
    assert ax.get_ylabel() == "Effectif"


def test_counts_side_by_side():
    ax, _ = render(contingency_view="grouped")
    heights = sorted(p.get_height() for p in ax.patches)
    assert heights == [12, 14, 26, 28]


def test_the_legend_reads_like_the_stack():
    ax, _ = render()
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels == ["Non-répondeurs", "Répondeurs"]   # top segment first


def test_two_groups_get_one_bracket_with_the_global_test():
    ax, info = render(stats_enabled=True)
    assert info.omnibus[0] == "Test exact de Fisher"
    assert len(info.comparisons) == 1
    comp = info.comparisons[0]
    assert (comp.a, comp.b) == ("Traité", "Placebo")
    assert comp.p == pytest.approx(st.contingency(
        [[28, 12], [14, 26]])["p"])
    assert any(t.get_text() == comp.stars for t in ax.texts)


def test_statistics_off_means_no_test():
    _, info = render()
    assert not info.omnibus and not info.comparisons
    # the table and the effect sizes are descriptive: always there
    assert info.descriptives[0] == {
        "Groupe": "Traité", "n": 40, "Répondeurs": 28,
        "Répondeurs (%)": pytest.approx(70.0), "Non-répondeurs": 12,
        "Non-répondeurs (%)": pytest.approx(30.0)}
    assert effect(info.contingency, "Odds ratio")["Valeur"] == \
        pytest.approx((28 * 26) / (12 * 14))


def test_three_groups_are_compared_pair_by_pair():
    three = pd.DataFrame({"Bras": ["A", "B", "C"], "Répondeurs": [28, 21, 14],
                          "Non-répondeurs": [12, 19, 26]})
    info = plotting.render(Figure(), PlotSpec(
        plot_type="contingency", group="Bras", stats_enabled=True,
        y=["Répondeurs", "Non-répondeurs"]), three)
    assert info.omnibus[0] == "Khi² de Pearson"
    assert len(info.comparisons) == 3


def test_the_settings_survive_saving(tmp_path):
    from plotea.core.project import Project

    project = Project()
    project.add_plot(PlotSpec(name="Réponse", plot_type="contingency",
                              contingency_view="grouped",
                              contingency_test="chi2_yates"))
    path = project.save(str(tmp_path / "ct.plotea"))
    spec = Project.load(path).plots[-1]
    assert (spec.plot_type, spec.contingency_view, spec.contingency_test) \
        == ("contingency", "grouped", "chi2_yates")


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def choose_contingency(window):
    for button in window.inspector.type_buttons.buttons():
        if button.property("plot_type") == "contingency":
            button.click()


def test_switching_to_contingency_finds_the_count_columns(window):
    window.load_example("Réponse au traitement (contingence)")
    choose_contingency(window)
    spec = window.current_spec()
    assert spec.group == "Traitement"
    assert spec.y == ["Répondeurs", "Non-répondeurs"]
    inspector = window.inspector
    assert not inspector.cmb_ctest.isHidden()
    assert inspector.cmb_test.isHidden()


def test_switching_with_two_category_columns_uses_raw_data(window):
    from plotea.core.dataset import Dataset

    window.project.add_dataset(Dataset("Patients", raw_from(COUNTS)))
    spec = window.current_spec()
    spec.dataset = "Patients"
    spec.y = []
    choose_contingency(window)
    assert (spec.group, spec.subgroup, spec.y) == ("Bras", "Issue", [])


def test_the_effects_tab_and_a_header_without_a_missing_statistic(window):
    window.load_example("Réponse au traitement (contingence)")
    choose_contingency(window)
    spec = window.current_spec()
    spec.y = ["Répondeurs", "Non-répondeurs"]
    spec.stats_enabled = True
    window._render_now()
    panel = window.stats_panel
    assert not panel.tabs.isTabVisible(panel.tabs.indexOf(panel.effects)) \
        or panel._effect_rows
    assert "Khi² de Pearson" in panel.header.text()
    # Fisher on two arms: a p-value and no "stat = nan"
    window.project.get_dataset(spec.dataset).df = \
        window.project.get_dataset(spec.dataset).df.iloc[:2]
    window._render_now()
    assert "Test exact de Fisher: p =" in panel.header.text()
    assert "nan" not in panel.header.text()
    assert panel.tabs.isTabVisible(panel.tabs.indexOf(panel.effects))
    assert any(r["Mesure"] == "Odds ratio" for r in panel._effect_rows)
