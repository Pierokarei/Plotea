"""Synthetic datasets used by the Help > Exemples menu and the test suite."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..i18n import tr
from .dataset import Dataset


def _shown_as(ds: Dataset, **settings) -> Dataset:
    """Attach the plot an example is made for: Help > Examples opens it so.

    Choosing columns by guesswork works for a table of one's own; an
    example has a plot it was built to show, and opening it as anything
    else - survival times as bars - teaches the wrong thing.
    """
    ds.meta["plot"] = settings
    return ds


def viability(seed: int = 7) -> Dataset:
    """Long format: 4 treatments x 12 replicates, classic bar/box material."""
    rng = np.random.default_rng(seed)
    groups = {tr("Contrôle"): (100, 9), tr("Drogue A"): (82, 11),
              tr("Drogue B"): (61, 10), tr("Drogue A+B"): (38, 8)}
    rows = []
    for name, (mu, sd) in groups.items():
        for rep, val in enumerate(rng.normal(mu, sd, 12), start=1):
            rows.append({tr("Traitement"): name, tr("Réplicat"): rep,
                         tr("Viabilité"): round(float(val), 2),
                         tr("Lignée"): "HeLa" if rep % 2 else "U2OS"})
    return _shown_as(Dataset(tr("Viabilité cellulaire"), pd.DataFrame(rows)),
                     plot_type="bar", group=tr("Traitement"),
                     y=[tr("Viabilité")], xlabel=tr("Traitement"),
                     ylabel=tr("Viabilité (%)"), stats_enabled=True,
                     design="independent")


def growth(seed: int = 3) -> Dataset:
    """Wide format time course with replicate columns: curves with error."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, 49, 4, dtype=float)
    out = {tr("Temps (h)"): t}
    for name, (k, top) in {"WT": (0.10, 1.8), "KO": (0.06, 1.2),
                           "KO + rescue": (0.09, 1.65)}.items():
        base = top / (1 + np.exp(-k * (t - 24)))
        out[name] = np.round(base + rng.normal(0, 0.04, t.size), 4)
        out[f"{name} SD"] = np.round(np.abs(rng.normal(0.06, 0.02, t.size)), 4)
    series = ["WT", "KO", "KO + rescue"]
    return _shown_as(Dataset(tr("Courbe de croissance"), pd.DataFrame(out)),
                     plot_type="line", x=tr("Temps (h)"), y=series,
                     error_cols=[f"{name} SD" for name in series],
                     xlabel=tr("Temps (h)"), ylabel="DO600")


def dose_response(seed: int = 11) -> Dataset:
    """Log-concentration dose response, for the 4PL fit."""
    rng = np.random.default_rng(seed)
    logc = np.repeat(np.linspace(-9, -4, 11), 3)
    rows = []
    for compound, (logec50, hill, top) in {
            tr("Inhibiteur 1"): (-7.2, 1.0, 100.0),
            tr("Inhibiteur 2"): (-6.1, 1.4, 96.0)}.items():
        resp = 5 + (top - 5) / (1 + 10 ** ((logc - logec50) * hill))
        resp = resp + rng.normal(0, 3.5, logc.size)
        for lc, r in zip(logc, resp):
            rows.append({"log[C] (M)": round(float(lc), 3),
                         tr("Réponse (%)"): round(float(r), 2),
                         tr("Composé"): compound})
    return _shown_as(Dataset(tr("Dose-réponse"), pd.DataFrame(rows)),
                     plot_type="scatter", x="log[C] (M)",
                     y=[tr("Réponse (%)")], group=tr("Composé"),
                     fit_model="hill4_log", xlabel="log[C] (M)",
                     ylabel=tr("Réponse (%)"))


def expression(seed: int = 21) -> Dataset:
    """Wide format, heavy-tailed: violin / histogram material."""
    rng = np.random.default_rng(seed)
    n = 220
    tissues = [tr("Sain"), tr("Tumeur"), tr("Métastase")]
    return _shown_as(Dataset(tr("Expression génique"), pd.DataFrame({
        tissues[0]: np.round(rng.lognormal(1.8, 0.45, n), 3),
        tissues[1]: np.round(rng.lognormal(2.4, 0.55, n), 3),
        tissues[2]: np.round(rng.lognormal(2.75, 0.62, n), 3),
    })), plot_type="violin", y=tissues, ylabel=tr("Expression génique"),
        design="independent")


def correlation(seed: int = 5) -> Dataset:
    """Scatter with a real linear relationship plus a categorical factor."""
    rng = np.random.default_rng(seed)
    rows = []
    for cohort, (slope, noise) in {tr("Cohorte A"): (1.9, 6.0),
                                   tr("Cohorte B"): (1.1, 5.0)}.items():
        x = rng.uniform(5, 60, 60)
        y = slope * x + 12 + rng.normal(0, noise, x.size)
        for xi, yi in zip(x, y):
            rows.append({tr("Biomarqueur (ng/mL)"): round(float(xi), 2),
                         tr("Score clinique"): round(float(yi), 2),
                         tr("Cohorte"): cohort})
    return _shown_as(Dataset(tr("Corrélation biomarqueur"),
                             pd.DataFrame(rows)),
                     plot_type="scatter", x=tr("Biomarqueur (ng/mL)"),
                     y=[tr("Score clinique")], group=tr("Cohorte"),
                     fit_model="linear", xlabel=tr("Biomarqueur (ng/mL)"),
                     ylabel=tr("Score clinique"))


def two_factor(seed: int = 15) -> Dataset:
    """Two-factor design -> grouped bars with error."""
    rng = np.random.default_rng(seed)
    rows = []
    for genotype, base in {"WT": 100.0, tr("Mutant"): 72.0}.items():
        for time, factor in {"0 h": 1.0, "6 h": 0.82, "24 h": 0.55}.items():
            for _ in range(8):
                rows.append({tr("Génotype"): genotype, tr("Temps"): time,
                             tr("Activité"): round(float(
                                 rng.normal(base * factor, 7.5)), 2)})
    return _shown_as(Dataset(tr("Plan à deux facteurs"), pd.DataFrame(rows)),
                     plot_type="bar", group=tr("Temps"),
                     subgroup=tr("Génotype"), y=[tr("Activité")],
                     xlabel=tr("Temps"), ylabel=tr("Activité"),
                     design="independent")


def survival(seed: int = 21) -> Dataset:
    """A two-arm trial with censoring: the shape Kaplan-Meier is made for.

    A third of the subjects leave the study before the event, at a time that
    says nothing about their outcome - which is what censoring means.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for arm, median in {tr("Traitement"): 30.0, tr("Placebo"): 10.0}.items():
        for _ in range(40):
            event_time = float(rng.exponential(median / np.log(2)))
            leaves = float(rng.uniform(14, 40))     # end of follow-up
            observed = min(event_time, leaves)
            rows.append({tr("Bras"): arm,
                         tr("Temps (mois)"): round(min(observed, 36.0), 2),
                         tr("Événement"): int(event_time <= min(leaves, 36.0))})
    return _shown_as(Dataset(tr("Essai de survie"), pd.DataFrame(rows)),
                     plot_type="survival", x=tr("Temps (mois)"),
                     group=tr("Bras"), event_col=tr("Événement"),
                     xlabel=tr("Temps (mois)"), stats_enabled=True)


def contingency() -> Dataset:
    """Responders per arm, already counted - the way Prism enters them.

    Three arms, so the chi-square tests the whole table and each pair of
    arms gets its own Fisher test.
    """
    arms = {tr("Médicament A"): (28, 12), tr("Médicament B"): (21, 19),
            tr("Placebo"): (14, 26)}
    rows = [{tr("Traitement"): arm, tr("Répondeurs"): yes,
             tr("Non-répondeurs"): no} for arm, (yes, no) in arms.items()]
    return _shown_as(Dataset(tr("Réponse au traitement"), pd.DataFrame(rows)),
                     plot_type="contingency", group=tr("Traitement"),
                     y=[tr("Répondeurs"), tr("Non-répondeurs")],
                     xlabel=tr("Traitement"))


def paired() -> Dataset:
    """Blood pressure of the same patients before and after a treatment.

    Most drop, a few do not - what a before-after plot shows and a bar
    chart of two means hides.
    """
    rng = np.random.default_rng(31)
    before = rng.normal(148, 11, 12)
    after = before - rng.normal(9, 7, 12)
    return _shown_as(Dataset(tr("Pression artérielle"), pd.DataFrame({
        tr("Patient"): [f"P{i:02d}" for i in range(1, 13)],
        tr("Avant"): before.round(1), tr("Après"): after.round(1)})),
        plot_type="paired", y=[tr("Avant"), tr("Après")],
        stats_pair_by=tr("Patient"), stats_enabled=True, design="paired",
        ylabel=tr("Pression artérielle") + " (mmHg)")


def standard_curve(seed: int = 9) -> Dataset:
    """A sandwich ELISA: eight standards in duplicate, then the sera.

    Standards and samples share the table, as in Prism: the samples' X is
    left empty for the curve to fill in. Two sera were diluted 1:10; one
    lies above the highest standard and one below the lowest - what a
    plate gives and what the report must not hide.
    """
    rng = np.random.default_rng(seed)
    bottom, top, ec50, hill = 0.06, 2.6, 160.0, 1.15

    def od(conc):
        return bottom + (top - bottom) / (1 + (ec50 / conc) ** hill)

    sample, conc_col = tr("Échantillon"), tr("Concentration (pg/mL)")
    od_col, dilution = tr("DO 450 nm"), tr("Dilution")
    rows = []
    for i, conc in enumerate((1000, 500, 250, 125, 62.5, 31.25, 15.6, 7.8)):
        for _ in range(2):
            rows.append({sample: f"{tr('Étalon')} {i + 1}", conc_col: conc,
                         od_col: round(float(od(conc) * rng.normal(1, 0.03)),
                                       3), dilution: np.nan})
    sera = ((45.0, 1), (210.0, 1), (640.0, 1), (380.0, 10), (95.0, 10),
            (5000.0, 1), (2.0, 1))
    for i, (true, factor) in enumerate(sera, start=1):
        for _ in range(2):
            rows.append({sample: f"{tr('Sérum')} {i}", conc_col: np.nan,
                         od_col: round(float(od(true / factor)
                                             * rng.normal(1, 0.04)), 3),
                         dilution: float(factor)})
    return _shown_as(Dataset(tr("Dosage ELISA"), pd.DataFrame(rows)),
                     plot_type="scatter", x=conc_col, y=[od_col],
                     fit_model="hill4", fit_ci=True, log_x=True,
                     interpolate=True, interp_label=sample,
                     interp_factor=dilution, xlabel=conc_col, ylabel=od_col)


def glucose_tolerance(seed: int = 12) -> Dataset:
    """A glucose tolerance test: six mice per diet, blood glucose 0-120 min.

    Long format, one row per mouse and time: the curves are drawn as means
    of each diet, the areas computed mouse by mouse - what the groups are
    compared on.
    """
    rng = np.random.default_rng(seed)
    times = (0, 15, 30, 60, 90, 120)
    shape = (0.0, 1.0, 0.92, 0.55, 0.28, 0.12)
    mouse, diet = tr("Souris"), tr("Régime")
    time, glucose = tr("Temps (min)"), tr("Glycémie (mg/dL)")
    rows = []
    for name, (fasting, peak) in {tr("Standard"): (95.0, 245.0),
                                  tr("Riche en graisses"): (125.0, 355.0)
                                  }.items():
        for m in range(6):
            own = rng.normal(1, 0.08)           # each mouse its own height
            for t, f in zip(times, shape):
                value = (fasting + (peak - fasting) * f) * own
                rows.append({mouse: f"{name[0]}{m + 1}", diet: name,
                             time: t,
                             glucose: round(float(value
                                                  + rng.normal(0, 8)), 0)})
    return _shown_as(Dataset(tr("Tolérance au glucose"), pd.DataFrame(rows)),
                     plot_type="line", x=time, y=[glucose], group=diet,
                     auc=True, auc_subject=mouse, xlabel=time,
                     ylabel=glucose)


def diagnostic(seed: int = 23) -> Dataset:
    """Three blood markers in 60 patients with the disease and 70 without.

    Troponin separates them well, CRP less so; albumin falls with the
    disease - a marker read the other way round. All three were measured
    on the same patients, so their curves can be compared.
    """
    rng = np.random.default_rng(seed)
    status, troponin = tr("Diagnostic"), tr("Troponine (ng/L)")
    crp, albumin = tr("CRP (mg/L)"), tr("Albumine (g/L)")
    rows = []
    for label, sick, count in ((tr("Sain"), 0, 70), (tr("Malade"), 1, 60)):
        for _ in range(count):
            shared = rng.normal()                  # how ill, roughly
            log_tn = 2.0 + 1.25 * sick + 0.6 * (0.7 * shared
                                                + 0.71 * rng.normal())
            log_crp = 1.5 + 0.7 * sick + 0.9 * (0.5 * shared
                                                + 0.87 * rng.normal())
            rows.append({
                status: label,
                troponin: round(float(np.exp(log_tn)), 1),
                crp: round(float(np.exp(log_crp)), 1),
                albumin: round(float(42.0 - 4.5 * sick
                                     + 4.5 * rng.normal()), 1)})
    return _shown_as(Dataset(tr("Biomarqueurs diagnostiques"),
                             pd.DataFrame(rows)),
                     plot_type="roc", group=status,
                     y=[troponin, crp, albumin], roc_positive=tr("Malade"))


#: Peak expiratory flow rate (l/min) of 17 subjects, first reading on each
#: meter: Bland JM, Altman DG. Statistical methods for assessing agreement
#: between two methods of clinical measurement. Lancet 1986;i:307-310,
#: table 1. Their published bias is -2.1 l/min, SD 38.8.
PEAK_FLOW = {
    "Wright": [494, 395, 516, 434, 476, 557, 413, 442, 650, 433, 417, 656,
               267, 478, 178, 423, 427],
    "Mini-Wright": [512, 430, 520, 428, 500, 600, 364, 380, 658, 445, 432,
                    626, 260, 477, 259, 350, 451],
}


def agreement() -> Dataset:
    """Two peak flow meters on the same subjects: the Bland-Altman classic."""
    data = {tr("Sujet"): [f"S{i:02d}" for i in range(1, 18)]}
    data.update({name: [float(v) for v in values]
                 for name, values in PEAK_FLOW.items()})
    return _shown_as(Dataset(tr("Débit expiratoire de pointe"),
                             pd.DataFrame(data)),
                     plot_type="bland_altman", y=list(PEAK_FLOW),
                     stats_pair_by=tr("Sujet"))


def heatmap() -> Dataset:
    """Expression of 12 genes in 3 control and 3 treated samples.

    Two blocks of genes answer the treatment in opposite directions and a
    third does not move: what a clustered, row-scaled heat map brings out.
    """
    rng = np.random.default_rng(17)
    samples = [f"{tr('Contrôle')} {i}" for i in (1, 2, 3)] + \
        [f"{tr('Traité')} {i}" for i in (1, 2, 3)]
    effect = {"up": 2.2, "down": -1.8, "flat": 0.0}
    genes = (["IL6", "CXCL8", "TNF", "CCL2"], ["PPARG", "ADIPOQ", "LPL",
             "FABP4"], ["GAPDH", "ACTB", "TBP", "HPRT1"])
    rows = []
    for block, names in zip(("up", "down", "flat"), genes):
        for gene in names:
            base = rng.uniform(5, 11)
            values = [base + rng.normal(0, 0.25) for _ in range(3)] + \
                [base + effect[block] + rng.normal(0, 0.25) for _ in range(3)]
            rows.append({tr("Gène"): gene,
                         **{s: round(v, 2) for s, v in zip(samples, values)}})
    order = rng.permutation(len(rows))          # as a table arrives
    return _shown_as(Dataset(tr("Expression (log2)"),
                             pd.DataFrame([rows[i] for i in order])),
                     plot_type="heatmap", group=tr("Gène"), y=samples,
                     heat_values="z_rows", heat_cluster="rows")


EXAMPLES = {
    "Viabilité cellulaire (barres, stats)": viability,
    "Courbe de croissance (courbes + SD)": growth,
    "Dose-réponse (fit 4PL)": dose_response,
    "Dosage ELISA (gamme étalon)": standard_curve,
    "Tolérance au glucose (aire sous la courbe)": glucose_tolerance,
    "Biomarqueurs diagnostiques (courbes ROC)": diagnostic,
    "Expression génique (violin/histogramme)": expression,
    "Corrélation (nuage + régression)": correlation,
    "Plan à deux facteurs (barres groupées)": two_factor,
    "Essai de survie (Kaplan-Meier)": survival,
    "Réponse au traitement (contingence)": contingency,
    "Pression artérielle (avant/après)": paired,
    "Deux débitmètres (Bland-Altman)": agreement,
    "Expression de gènes (carte de chaleur)": heatmap,
}


def load_example(label: str) -> Dataset:
    return EXAMPLES[label]()


def all_examples() -> list[Dataset]:
    return [fn() for fn in EXAMPLES.values()]
