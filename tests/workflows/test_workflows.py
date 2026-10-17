"""Whole sessions, from the file to the results, and back from the disk.

A correct engine gives wrong results when the interface hands it the wrong
data - Dunn ran as Mann-Whitney, a click erased the event column, a deleted
column was still plotted. Each scenario here goes the way a person does:
import, choose columns, change colours, rename, edit and undo, save, close,
reopen. Two checks at the end. The results are exactly those before the
file was closed. And they are those of an oracle: the same analysis done
directly on the file read by pandas, by formulas written out here or by
scipy, without the interface choosing any column.
"""
import numpy as np
import pandas as pd
import pytest
from driver import User
from scipy import stats

from plotea.core import demo


@pytest.fixture
def user(window, monkeypatch):
    import driver
    from conftest import dispose

    window.files.start_new()
    yield User(window, monkeypatch)
    while driver.OPENED:
        dispose(driver.OPENED.pop())


def csv(tmp_path, frame: pd.DataFrame, name: str) -> str:
    path = tmp_path / f"{name}.csv"
    frame.to_csv(path, index=False)
    return str(path)


def round_trip(user, tmp_path, monkeypatch):
    """Save, close, open again in a new window, back on the same plot."""
    before = user.results()
    tab = user.window.tabbar.currentIndex()
    path = user.save_as(str(tmp_path / "session.plotea"))
    user.close()
    again = User.reopen(path, monkeypatch)
    again.window.tabbar.setCurrentIndex(tab)
    assert again.results() == before, "les résultats ont changé à la réouverture"
    # and the table on screen is the one the plot is drawn from
    shown = again.window.data_panel.current_dataset().name
    assert shown == again.spec.dataset, "le panneau montre une autre table"
    return again


# --------------------------------------------------------------------------
# Oracles, written out from the textbook
# --------------------------------------------------------------------------
def logrank_two_groups(times, events, groups):
    """Mantel-Cox: observed against expected deaths of the first group."""
    times, events = np.asarray(times, float), np.asarray(events, int)
    labels = list(dict.fromkeys(groups))
    first = np.asarray(groups) == labels[0]
    observed = expected = variance = 0.0
    for t in np.unique(times[events == 1]):
        at_risk = times >= t
        n, n1 = at_risk.sum(), (at_risk & first).sum()
        d = ((times == t) & (events == 1)).sum()
        d1 = ((times == t) & (events == 1) & first).sum()
        observed += d1
        expected += d * n1 / n
        if n > 1:
            variance += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
    chi2 = (observed - expected) ** 2 / variance
    return chi2, float(stats.chi2.sf(chi2, 1))


def km_median(times, events):
    times, events = np.asarray(times, float), np.asarray(events, int)
    survival = 1.0
    for t in np.unique(times[events == 1]):
        at_risk = (times >= t).sum()
        survival *= 1 - ((times == t) & (events == 1)).sum() / at_risk
        if survival <= 0.5:
            return float(t)
    return float("nan")


# --------------------------------------------------------------------------
# 1. Survival: the event column must reach the log-rank, whatever happens
# --------------------------------------------------------------------------
def test_survival_from_the_file_to_the_reopened_project(user, tmp_path,
                                                        monkeypatch):
    trial = demo.survival().df.rename(columns={"Temps (mois)": "Mois",
                                               "Événement": "Décès"})
    user.import_file(csv(tmp_path, trial, "essai"))
    user.plot_type("survival")
    user.pick("cmb_event", "Décès")
    user.tick("chk_stats")
    for arm, colour in zip(["Traitement", "Placebo"], ["#1B9E77", "#D95F02"]):
        user.colour(arm, colour)
    user.tick("chk_surv_ci")              # the click that emptied it in 1.1
    user.rename_column("Décès", "Événement (1 = décès)")
    assert user.spec.event_col == "Événement (1 = décès)"

    again = round_trip(user, tmp_path, monkeypatch)
    results = again.results()

    chi2, p = logrank_two_groups(trial["Mois"], trial["Décès"],
                                 trial["Bras"])
    name, stat, p_value = results["omnibus"][:3]
    assert name == "Log-rank"
    assert stat == pytest.approx(chi2, rel=1e-10)
    assert p_value == pytest.approx(p, rel=1e-8)
    rows = {r["Groupe"]: r for r in results["descriptives"]}
    for arm, part in trial.groupby("Bras"):
        assert rows[arm]["Censurés"] == int((part["Décès"] == 0).sum())
        assert rows[arm]["Survie médiane"] == pytest.approx(
            km_median(part["Mois"], part["Décès"]))
    assert again.spec.custom_colors["Traitement"] == "#1B9E77"


def logrank_k_groups(times, events, groups):
    """Mantel-Cox across k groups: (O - E)' V^-1 (O - E), k - 1 df."""
    times, events = np.asarray(times, float), np.asarray(events, int)
    groups = np.asarray(groups)
    labels = list(dict.fromkeys(groups))
    k = len(labels)
    o_e = np.zeros(k)
    v = np.zeros((k, k))
    for t in np.unique(times[events == 1]):
        at_risk = times >= t
        n = at_risk.sum()
        d = ((times == t) & (events == 1)).sum()
        n_g = np.array([(at_risk & (groups == g)).sum() for g in labels])
        d_g = np.array([((times == t) & (events == 1) & (groups == g)).sum()
                        for g in labels])
        o_e += d_g - d * n_g / n
        if n > 1:
            share = n_g / n
            v += d * (n - d) / (n - 1) * (np.diag(share)
                                          - np.outer(share, share))
    chi2 = float(o_e[:-1] @ np.linalg.solve(v[:-1, :-1], o_e[:-1]))
    return chi2, float(stats.chi2.sf(chi2, k - 1))


def dunn_holm(values, groups):
    """Dunn's z on mean ranks of all the values, ties corrected; Holm."""
    from plotea.core.stats import adjust

    values, groups = np.asarray(values, float), np.asarray(groups)
    labels = list(dict.fromkeys(groups))
    ranks = stats.rankdata(values)
    n = values.size
    _, ties = np.unique(values, return_counts=True)
    spread = n * (n + 1) / 12 - (ties ** 3 - ties).sum() / (12 * (n - 1))
    pairs, raw = [], []
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            ra, rb = ranks[groups == a], ranks[groups == b]
            z = (ra.mean() - rb.mean()) / np.sqrt(
                spread * (1 / ra.size + 1 / rb.size))
            pairs.append((a, b))
            raw.append(2 * stats.norm.sf(abs(z)))
    return dict(zip(pairs, adjust(raw, "holm")))


def comparisons(results) -> dict:
    """(a, b) -> adjusted p, either way round."""
    out = {}
    for a, b, _test, _stat, _p, p_adj, *_ in results["comparisons"]:
        out[(a, b)] = out[(b, a)] = p_adj
    return out


# --------------------------------------------------------------------------
# 2. Bars: Kruskal-Wallis and Dunn, through renaming, editing, undoing
# --------------------------------------------------------------------------
def test_bars_with_dunn_survive_a_working_session(user, tmp_path,
                                                  monkeypatch):
    path = "examples/viabilite_cellulaire.csv"
    raw = pd.read_csv(path)
    user.import_file(path)
    user.plot_type("bar")
    assert user.spec.y == ["Viabilité"]           # not the replicate number
    user.tick("chk_stats")
    user.pick_data("cmb_test", "kruskal_dunn")
    user.rename_column("Traitement", "Condition")
    user.type_in(0, "Viabilité", "999")             # a slip...
    user.undo()                                     # ...undone
    user.window.load_example("Réponse au traitement (contingence)")
    user.select_table("viabilite_cellulaire")       # and back
    assert user.spec.group == "Condition" and user.spec.plot_type == "bar"

    results = round_trip(user, tmp_path, monkeypatch).results()

    h, p = stats.kruskal(*[part["Viabilité"]
                           for _, part in raw.groupby("Traitement",
                                                      sort=False)])
    assert results["omnibus"][0] == "Kruskal-Wallis"
    assert results["omnibus"][1:3] == pytest.approx([h, p], rel=1e-10)
    expected = dunn_holm(raw["Viabilité"], raw["Traitement"])
    found = comparisons(results)
    assert len(results["comparisons"]) == len(expected) == 6
    for pair, p_adj in expected.items():
        assert found[pair] == pytest.approx(p_adj, rel=1e-9), pair


# --------------------------------------------------------------------------
# 3. Before-after: a subject removed takes both of its measurements along
# --------------------------------------------------------------------------
def test_paired_subjects_stay_paired_after_a_deletion(user, tmp_path,
                                                      monkeypatch):
    frame = demo.paired().df
    user.import_file(csv(tmp_path, frame, "tension"))
    user.plot_type("paired")
    user.tick("chk_stats")
    user.pick_data("cmb_test", "paired_t")
    user.delete_rows([3])                           # patient P04
    results = round_trip(user, tmp_path, monkeypatch).results()

    kept = frame.drop(index=3)
    t, p = stats.ttest_rel(kept["Avant"], kept["Après"])
    (_a, _b, test, stat, p_raw, *_), = results["comparisons"]
    assert test == "t apparié"
    assert abs(stat) == pytest.approx(abs(t), rel=1e-10)
    assert p_raw == pytest.approx(p, rel=1e-10)


# --------------------------------------------------------------------------
# 4. Contingency: counts read as counts, under a new outcome name
# --------------------------------------------------------------------------
def test_contingency_counts_survive_renaming(user, tmp_path, monkeypatch):
    from plotea.core.stats import adjust

    frame = demo.contingency().df
    user.import_file(csv(tmp_path, frame, "reponse"))
    user.plot_type("contingency")
    user.tick("chk_stats")
    user.rename_column("Répondeurs", "Répond au traitement")
    results = round_trip(user, tmp_path, monkeypatch).results()

    table = frame[["Répondeurs", "Non-répondeurs"]].to_numpy()
    chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
    assert results["omnibus"][1:3] == pytest.approx([chi2, p], rel=1e-10)
    arms = list(frame["Traitement"])
    pairs = [(arms[i], arms[j]) for i in range(3) for j in range(i + 1, 3)]
    raw = [stats.fisher_exact(table[[i, j]])[1]
           for i in range(3) for j in range(i + 1, 3)]
    found = comparisons(results)
    for pair, p_adj in zip(pairs, adjust(raw, "holm")):
        assert found[pair] == pytest.approx(p_adj, rel=1e-9), pair


# --------------------------------------------------------------------------
# 5. Standard curve: what reaches the curve is the standards, and only them
# --------------------------------------------------------------------------
def test_standard_curve_assay_through_the_interface(user, tmp_path,
                                                    monkeypatch):
    from plotea.core import fitting

    frame = demo.standard_curve().df
    user.import_file(csv(tmp_path, frame, "elisa"))
    user.plot_type("scatter")
    user.pick("cmb_x", "Concentration (pg/mL)")
    user.tick_y(["DO 450 nm"])
    user.pick("cmb_group", "")
    user.pick_data("cmb_fit", "hill4")
    user.tick("chk_interp")
    user.pick("cmb_interp_label", "Échantillon")
    user.pick("cmb_interp_factor", "Dilution")
    user.rename_column("Échantillon", "Sérum")
    results = round_trip(user, tmp_path, monkeypatch).results()

    standards = frame[frame["Concentration (pg/mL)"].notna()]
    curve = fitting.fit(standards["Concentration (pg/mL)"],
                        standards["DO 450 nm"], "hill4")
    samples = frame[frame["Concentration (pg/mL)"].isna()]
    rows = {r["Échantillon"]: r for r in results["assay"]}
    assert len(rows) == samples["Échantillon"].nunique() == 7
    for name, part in samples.groupby("Échantillon"):
        found = fitting.inverse(curve, part["DO 450 nm"].mean())
        factor = part["Dilution"].iloc[0]
        if found.status == "ok":
            assert rows[name]["Concentration"] == pytest.approx(
                found.x * factor, rel=1e-9), name
        else:
            assert rows[name]["Remarque"], name


# --------------------------------------------------------------------------
# 6. Areas per mouse, then the groups compared on them
# --------------------------------------------------------------------------
def test_areas_per_mouse_reach_the_group_comparison(user, tmp_path,
                                                    monkeypatch):
    frame = demo.glucose_tolerance().df
    user.import_file(csv(tmp_path, frame, "gtt"))
    user.plot_type("line")
    user.pick("cmb_x", "Temps (min)")
    user.tick_y(["Glycémie (mg/dL)"])
    user.pick("cmb_group", "Régime")
    user.tick("chk_auc")
    user.pick("cmb_auc_subject", "Souris")
    user.inspector.btn_auc_table.click()
    user.settle()
    user.tick("chk_stats")
    user.pick_data("cmb_test", "welch")
    results = round_trip(user, tmp_path, monkeypatch).results()

    areas = {mouse: (part["Régime"].iloc[0],
                     np.trapezoid(part["Glycémie (mg/dL)"],
                                  part["Temps (min)"]))
             for mouse, part in frame.groupby("Souris", sort=False)}
    standard = [a for diet, a in areas.values() if diet == "Standard"]
    rich = [a for diet, a in areas.values() if diet != "Standard"]
    _t, p = stats.ttest_ind(standard, rich, equal_var=False)
    (_a, _b, test, _stat, p_raw, *_), = results["comparisons"]
    assert test == "t de Welch"
    assert p_raw == pytest.approx(p, rel=1e-9)


# --------------------------------------------------------------------------
# 7. ROC: the class chosen as positive changes the reading, not the area
# --------------------------------------------------------------------------
def test_roc_areas_follow_the_markers_whatever_the_positive_class(
        user, tmp_path, monkeypatch):
    frame = demo.diagnostic().df
    user.import_file(csv(tmp_path, frame, "marqueurs"))
    user.plot_type("roc")
    user.pick("cmb_roc_positive", "Sain")
    results = round_trip(user, tmp_path, monkeypatch).results()

    sick = frame["Diagnostic"] == "Malade"
    for row in results["roc"]:
        marker = frame[row["Marqueur"]]
        u = stats.mannwhitneyu(marker[sick], marker[~sick]).statistic
        share = u / (sick.sum() * (~sick).sum())
        assert row["AUC"] == pytest.approx(max(share, 1 - share), rel=1e-12)
        assert row["n positifs"] == int((~sick).sum())     # "Sain" chosen


# --------------------------------------------------------------------------
# 8. A Prism file, opened, saved as a Plotea project, opened again
# --------------------------------------------------------------------------
def test_a_prism_survival_file_round_trips(user, tmp_path, monkeypatch):
    import os

    data = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data",
                        "prism")
    user.import_file(os.path.join(data, "survival.pzfx"))
    results = round_trip(user, tmp_path, monkeypatch).results()

    reference = pd.read_csv(os.path.join(data, "survival.tab"), sep="\t")
    reference.columns = [c.strip() for c in reference.columns]
    times, events, groups = [], [], []
    for group in ("Control", "Treatment A", "Treatment B"):
        part = reference[reference[group].notna()]
        times += list(part["Days"])
        events += list(part[group].astype(int))
        groups += [group] * len(part)
    chi2, p = logrank_k_groups(times, events, groups)
    assert results["omnibus"][0] == "Log-rank"
    assert results["omnibus"][1:3] == pytest.approx([chi2, p], rel=1e-9)


# --------------------------------------------------------------------------
# 9. Reopened under the English interface: the same numbers
# --------------------------------------------------------------------------
def numbers(value):
    if isinstance(value, dict):
        return [n for v in value.values() for n in numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]
    return [value] if isinstance(value, (int, float)) else []


def test_the_english_interface_computes_the_same(user, tmp_path,
                                                 monkeypatch):
    from conftest import app

    from plotea import i18n
    from plotea.app import install_language

    user.import_file("examples/viabilite_cellulaire.csv")
    user.plot_type("bar")
    user.tick("chk_stats")
    user.pick_data("cmb_test", "anova_tukey")
    french = user.results()
    path = user.save_as(str(tmp_path / "fr.plotea"))
    user.close()
    i18n.set_language("en")
    install_language(app, "en")
    try:
        again = User.reopen(path, monkeypatch)
        assert numbers(again.results()) == numbers(french)
    finally:
        i18n.set_language("fr")
        install_language(app, "fr")


# --------------------------------------------------------------------------
# 10. A column deleted, then any other click: the plot must not change
#     column behind the user's back
# --------------------------------------------------------------------------
@pytest.mark.parametrize("column, field", [("Traitement", "group"),
                                           ("Viabilité", "y")])
def test_a_missing_column_is_not_swapped_by_the_next_click(user, column,
                                                           field):
    user.import_file("examples/viabilite_cellulaire.csv")
    user.plot_type("bar")
    before = getattr(user.spec, field)
    user.delete_column(column)
    assert any(column in w for w in user.warnings)
    # what a change of tab or of plot type does: the inspector rebuilt
    # from the table, which no longer has the column
    user.window._sync_inspector()
    user.tick("chk_stats")                          # any unrelated click
    assert getattr(user.spec, field) == before
    assert any(column in w for w in user.warnings), \
        "le graphique a changé de colonne sans le dire"


# --------------------------------------------------------------------------
# 11. Opening a project while another one shows its second plot
# --------------------------------------------------------------------------
def test_opening_from_a_second_tab_moves_no_plot(user, tmp_path,
                                                 monkeypatch):
    """The plot on screen while a project is put in place is the previous
    project's tab: selecting the new project's first table used to move the
    new project's plot of that index onto it."""
    user.import_file("examples/viabilite_cellulaire.csv")
    user.plot_type("bar")
    user.window.load_example("Réponse au traitement (contingence)")
    user.select_table("viabilite_cellulaire")       # plot 1 back on its table
    user.window.new_plot()
    user.select_table("Réponse au traitement")      # plot 2 on the other one
    plans = [(s.name, s.dataset, s.plot_type)
             for s in user.window.project.plots]
    assert plans[0][1] != plans[1][1]
    path = user.save_as(str(tmp_path / "deux.plotea"))
    user.close()

    other = User.reopen(path, monkeypatch)
    other.window.tabbar.setCurrentIndex(len(plans) - 1)   # last tab shown
    assert other.window.files.load(path)
    other.settle()
    assert [(s.name, s.dataset, s.plot_type)
            for s in other.window.project.plots] == plans
