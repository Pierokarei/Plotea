"""The Methods paragraph of a figure, written from what was computed.

Everything said here is read from the figure's settings and from what the
render actually did - the test that ran, not the one that was asked for;
the groups that were compared, not the ones in the table - so the paragraph
cannot promise an analysis Plotea did not perform.

French or English, whatever the interface speaks: a French researcher often
writes in English. The two languages are kept side by side, phrase for
phrase, and a test checks that neither lacks a sentence the other has.
"""
from __future__ import annotations

import platform

from . import fitting
from . import stats as st

LANGUAGES = ("fr", "en")

PHRASES = {
    "en": {
        "mean_error": "Data are shown as mean ± {error}",
        "mean_only": "Data are shown as means",
        "box": ("Box plots show the median and interquartile range, "
                "whiskers extending to 1.5 times the interquartile range"),
        "violin": ("Violin plots show the distribution of each group "
                   "(kernel density estimate)"),
        "points": "; individual values are overlaid",
        "n_each": " (n = {n} per group).",
        "n_range": " (n = {low}-{high} per group).",
        "sem": "SEM", "sd": "SD", "ci95": "95% confidence interval",
        "minmax": "range (minimum to maximum)",
        "auto": ("Normality was assessed with the Shapiro-Wilk test and "
                 "equality of variances with Levene's test; on that basis, "),
        "auto_lead": "groups were compared with ",
        "chosen_lead": "Groups were compared with ",
        "omnibus_then": "{omnibus} followed by {followed}",
        "pairs_all": "all pairs of groups were compared",
        "pairs_control": "each group was compared with {control}",
        "paired_by": ", subjects being matched by {column}",
        "correction": ("P values were adjusted for multiple comparisons with "
                       "the {method} method."),
        "holm": "Holm", "bonferroni": "Bonferroni",
        "fdr_bh": "Benjamini-Hochberg (false discovery rate)",
        "two_way": ("A two-way ANOVA with type III sums of squares tested the "
                    "effects of {a} and {b} and their interaction; within "
                    "each level of {a}, levels of {b} were compared with "),
        "rm": ("A repeated-measures ANOVA tested the effect of {factor} "
               "(subjects: {subject}); the Greenhouse-Geisser-corrected P "
               "value is reported alongside. Pairs of conditions were "
               "compared with "),
        "threshold": "Differences were considered significant at P < 0.05",
        "stars": (" (* P < 0.05, ** P < 0.01, *** P < 0.001, "
                  "**** P < 0.0001)"),
        "grubbs": ("Grubbs' test (alpha = 0.05) flagged {count} value(s) "
                   "as possible outliers; all values were kept in the "
                   "analyses."),
        "km": "Survival was estimated with the Kaplan-Meier method",
        "km_ci": (", with 95% confidence bands from Greenwood's variance on "
                  "the log(-log) scale"),
        "km_censor": "; censored observations are marked by ticks.",
        "km_n": " (n = {n}; {events} events).",
        "logrank": "Survival curves were compared with the log-rank test.",
        "logrank_pairs": ("Pairs of groups were compared with log-rank tests "
                          "and the P values adjusted with the {method} "
                          "method."),
        "ct_display_percent": ("Bars show the percentage of each outcome "
                               "within each group"),
        "ct_display_counts": "Bars show the number of subjects per outcome",
        "ct_test": "{test} tested the association between group and outcome.",
        "fisher": "Two-sided Fisher's exact test",
        "chi2": "Pearson's chi-square test",
        "chi2_yates": "The chi-square test with Yates' continuity correction",
        "ct_effects": ("The odds ratio and the relative risk are given with "
                       "95% confidence intervals (Woolf and Katz methods)."),
        "ct_pairs": ("Pairs of groups were compared with the same test and "
                     "the P values adjusted with the {method} method."),
        "fit": ("Curves were fitted by least-squares regression to {model}, "
                "each replicate being treated as an individual point"),
        "fit_ci": ("; shaded areas show the 95% confidence band of the fit "
                   "(delta method)"),
        "fit_end": ".",
        "compare_one": ("Whether a single curve fits all series was tested "
                        "with the extra sum-of-squares F test."),
        "compare_param": ("Whether {param} differs between {series} was "
                          "tested with the extra sum-of-squares F test."),
        "software": ("Figures and analyses were produced with Plotea {plotea}"
                     " (Python {python}, NumPy {numpy}, SciPy {scipy}, "
                     "matplotlib {mpl})."),
        "and": "and",
        "series_all": "the {count} series",
        "paired_lines": ("Each line joins the values of one subject "
                         "(n = {n} subjects)"),
        "paired_mean": "; the marks beside show the mean ± {error}",
        "auto_paired": ("Normality of the paired differences was assessed "
                        "with the Shapiro-Wilk test; on that basis, "),
        "paired_rows": ", each row of the table being one subject",
        "rows": "the rows of the table",
        "ba": ("Agreement between {a} and {b} was assessed with the "
               "Bland-Altman method: for each subject (n = {n}), the "
               "difference between the two measurements ({diff}) is "
               "plotted against their mean. The bias is the mean "
               "difference, and the 95% limits of agreement are the bias "
               "± 1.96 SD of the differences{ci}."),
        "ba_abs": "{a} - {b}",
        "ba_pct": "{a} - {b}, as a percentage of their mean",
        "ba_ci": ("; their 95% confidence intervals follow Bland and "
                  "Altman (1999)"),
        "ba_p": ("Whether the bias differs from zero was tested with a "
                 "one-sample t test on the differences."),
        "semicolon": "; ",
    },
    "fr": {
        "mean_error": "Les données sont présentées en moyenne ± {error}",
        "mean_only": "Les données sont présentées en moyennes",
        "box": ("Les boîtes à moustaches montrent la médiane et l'écart "
                "interquartile, les moustaches s'étendant jusqu'à 1,5 fois "
                "l'écart interquartile"),
        "violin": ("Les violons montrent la distribution de chaque groupe "
                   "(estimation par noyau)"),
        "points": " ; les valeurs individuelles sont superposées",
        "n_each": " (n = {n} par groupe).",
        "n_range": " (n = {low} à {high} par groupe).",
        "sem": "SEM", "sd": "SD", "ci95": "intervalle de confiance à 95 %",
        "minmax": "étendue (minimum à maximum)",
        "auto": ("La normalité a été évaluée par le test de Shapiro-Wilk et "
                 "l'égalité des variances par le test de Levene ; en "
                 "conséquence, "),
        "auto_lead": "les groupes ont été comparés par ",
        "chosen_lead": "Les groupes ont été comparés par ",
        "omnibus_then": "{omnibus} {followed} ",
        "pairs_all": "toutes les paires de groupes ont été comparées",
        "pairs_control": "chaque groupe a été comparé à {control}",
        "paired_by": ", les sujets étant appariés par {column}",
        "correction": ("Les valeurs de p ont été ajustées pour les "
                       "comparaisons multiples par la méthode de {method}."),
        "holm": "Holm", "bonferroni": "Bonferroni",
        "fdr_bh": "Benjamini-Hochberg (taux de fausses découvertes)",
        "two_way": ("Une ANOVA à deux facteurs avec sommes des carrés de type "
                    "III a testé les effets de {a} et de {b} et leur "
                    "interaction ; à chaque niveau de {a}, les niveaux de {b} "
                    "ont été comparés par "),
        "rm": ("Une ANOVA à mesures répétées a testé l'effet de {factor} "
               "(sujets : {subject}) ; la valeur de p corrigée de "
               "Greenhouse-Geisser est rapportée en regard. Les paires de "
               "conditions ont été comparées par "),
        "threshold": ("Les différences ont été considérées comme "
                      "significatives pour p < 0,05"),
        "stars": (" (* p < 0,05 ; ** p < 0,01 ; *** p < 0,001 ; "
                  "**** p < 0,0001)"),
        "grubbs": ("Le test de Grubbs (alpha = 0,05) a signalé {count} "
                   "valeur(s) potentiellement aberrante(s) ; toutes les "
                   "valeurs ont été conservées dans les analyses."),
        "km": "La survie a été estimée par la méthode de Kaplan-Meier",
        "km_ci": (", avec des bandes de confiance à 95 % issues de la "
                  "variance de Greenwood sur l'échelle log(-log)"),
        "km_censor": " ; les observations censurées sont marquées d'un trait.",
        "km_n": " (n = {n} ; {events} événements).",
        "logrank": "Les courbes de survie ont été comparées par le test du "
                   "log-rank.",
        "logrank_pairs": ("Les paires de groupes ont été comparées par des "
                          "tests du log-rank, les valeurs de p étant "
                          "ajustées par la méthode de {method}."),
        "ct_display_percent": ("Les barres montrent le pourcentage de chaque "
                               "issue au sein de chaque groupe"),
        "ct_display_counts": ("Les barres montrent le nombre de sujets par "
                              "issue"),
        "ct_test": "{test} a testé l'association entre groupe et issue.",
        "fisher": "Le test exact de Fisher bilatéral",
        "chi2": "Le test du khi² de Pearson",
        "chi2_yates": "Le test du khi² avec correction de continuité de Yates",
        "ct_effects": ("L'odds ratio et le risque relatif sont donnés avec "
                       "leurs intervalles de confiance à 95 % (méthodes de "
                       "Woolf et de Katz)."),
        "ct_pairs": ("Les paires de groupes ont été comparées par le même "
                     "test, les valeurs de p étant ajustées par la méthode "
                     "de {method}."),
        "fit": ("Les courbes ont été ajustées par régression aux moindres "
                "carrés selon {model}, chaque réplicat étant traité comme "
                "un point individuel"),
        "fit_ci": (" ; les zones ombrées montrent la bande de confiance à "
                   "95 % de l'ajustement (méthode delta)"),
        "fit_end": ".",
        "compare_one": ("L'adéquation d'une courbe unique pour toutes les "
                        "séries a été testée par le test F des sommes de "
                        "carrés supplémentaires."),
        "compare_param": ("La différence de {param} entre {series} a été "
                          "testée par le test F des sommes de carrés "
                          "supplémentaires."),
        "software": ("Les figures et analyses ont été réalisées avec Plotea "
                     "{plotea} (Python {python}, NumPy {numpy}, SciPy "
                     "{scipy}, matplotlib {mpl})."),
        "and": "et",
        "series_all": "les {count} séries",
        "paired_lines": ("Chaque ligne relie les valeurs d'un même sujet "
                         "(n = {n} sujets)"),
        "paired_mean": " ; les marques à côté montrent la moyenne ± {error}",
        "auto_paired": ("La normalité des différences appariées a été "
                        "évaluée par le test de Shapiro-Wilk ; en "
                        "conséquence, "),
        "paired_rows": ", chaque ligne du tableau étant un sujet",
        "rows": "les lignes du tableau",
        "ba": ("La concordance entre {a} et {b} a été évaluée par la "
               "méthode de Bland-Altman : pour chaque sujet (n = {n}), la "
               "différence entre les deux mesures ({diff}) est portée en "
               "fonction de leur moyenne. Le biais est la moyenne des "
               "différences, et les limites d'agrément à 95 % sont le biais "
               "± 1,96 écart-type des différences{ci}."),
        "ba_abs": "{a} - {b}",
        "ba_pct": "{a} - {b}, en pourcentage de leur moyenne",
        "ba_ci": (" ; leurs intervalles de confiance à 95 % suivent Bland et "
                  "Altman (1999)"),
        "ba_p": ("L'écart du biais à zéro a été testé par un test t à un "
                 "échantillon sur les différences."),
        "semicolon": " ; ",
    },
}

#: How each pairwise test reads in a sentence.
TESTS = {
    "en": {
        "t de Student": "two-tailed unpaired Student's t tests",
        "t de Welch": "two-tailed Welch's t tests",
        "Mann-Whitney": "two-tailed Mann-Whitney U tests",
        "t apparié": "two-tailed paired t tests",
        "Wilcoxon apparié": "Wilcoxon signed-rank tests",
        "Tukey HSD": "Tukey's HSD test",
        "Dunnett": "Dunnett's test",
        "Dunn": "Dunn's test",
        "ANOVA à un facteur": "One-way ANOVA",
        "Kruskal-Wallis": "The Kruskal-Wallis test",
    },
    "fr": {
        "t de Student": "des tests t de Student bilatéraux non appariés",
        "t de Welch": "des tests t de Welch bilatéraux",
        "Mann-Whitney": "des tests U de Mann-Whitney bilatéraux",
        "t apparié": "des tests t appariés bilatéraux",
        "Wilcoxon apparié": "des tests des rangs signés de Wilcoxon",
        "Tukey HSD": "le test HSD de Tukey",
        "Dunnett": "le test de Dunnett",
        "Dunn": "le test de Dunn",
        "ANOVA à un facteur": "Une ANOVA à un facteur",
        "Kruskal-Wallis": "Le test de Kruskal-Wallis",
    },
}

#: Each fit model as it is named in a Methods section.
MODELS = {
    "en": {
        "linear": "a straight line (linear regression)",
        "poly2": "a second-order polynomial",
        "poly3": "a third-order polynomial",
        "exp_growth": "an exponential growth model",
        "exp_decay": "a one-phase exponential decay",
        "log": "a logarithmic model",
        "power": "a power law",
        "michaelis": "the Michaelis-Menten equation",
        "hill4": ("a four-parameter logistic model (concentration on a "
                  "linear scale)"),
        "hill4_log": ("a four-parameter logistic model with X as the "
                      "log10 of concentration"),
        "gaussian": "a Gaussian",
        "sigmoid": "a three-parameter logistic sigmoid",
    },
    "fr": {
        "linear": "une droite (régression linéaire)",
        "poly2": "un polynôme du second degré",
        "poly3": "un polynôme du troisième degré",
        "exp_growth": "un modèle de croissance exponentielle",
        "exp_decay": "une décroissance exponentielle à une phase",
        "log": "un modèle logarithmique",
        "power": "une loi de puissance",
        "michaelis": "l'équation de Michaelis-Menten",
        "hill4": ("un modèle logistique à quatre paramètres (concentration "
                  "en échelle linéaire)"),
        "hill4_log": ("un modèle logistique à quatre paramètres, X étant le "
                      "log10 de la concentration"),
        "gaussian": "une gaussienne",
        "sigmoid": "une sigmoïde logistique à trois paramètres",
    },
}

#: Tests that correct their own family-wise error rate.
SELF_CORRECTING = {"Tukey HSD", "Dunnett"}

#: Global tests whose French name is feminine: "une ANOVA ... suivie de".
FEMININE = {"ANOVA à un facteur"}


def _de(text: str) -> str:
    """French "de" before what follows: "de" + "des tests" is "de tests",
    "de" + "le test" is "du test"."""
    if text.startswith("des "):
        return "de " + text[4:]
    if text.startswith("le "):
        return "du " + text[3:]
    return "de " + text


def _versions() -> dict:
    import matplotlib
    import numpy
    import scipy

    from .. import __version__
    return {"plotea": __version__, "python": platform.python_version(),
            "numpy": numpy.__version__, "scipy": scipy.__version__,
            "mpl": matplotlib.__version__}


def _sizes(rows, key="n") -> list[int]:
    return [int(r[key]) for r in rows if isinstance(r.get(key), (int, float))]


def _n_clause(say, sizes) -> str:
    if not sizes:
        return "."
    low, high = min(sizes), max(sizes)
    return (say["n_each"].format(n=low) if low == high
            else say["n_range"].format(low=low, high=high))


def _join(items: list[str], word: str) -> str:
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _categorical(spec, info, say, tests, language) -> list[str]:
    out = []
    sizes = _sizes(info.descriptives)
    paired_plot = spec.plot_type == "paired"
    if paired_plot:
        lead = say["paired_lines"].format(n=info.subjects)
        if spec.error_type in ("sem", "sd", "ci95", "minmax"):
            lead += say["paired_mean"].format(error=say[spec.error_type])
    elif spec.plot_type == "box":
        lead = say["box"]
    elif spec.plot_type == "violin":
        lead = say["violin"]
    elif spec.error_type in ("sem", "sd", "ci95", "minmax"):
        lead = say["mean_error"].format(error=say[spec.error_type])
    else:
        lead = say["mean_only"]
    if paired_plot:
        out.append(lead + ".")
    else:
        if spec.show_points:
            lead += say["points"]
        out.append(lead + _n_clause(say, sizes))

    comparisons = list(info.comparisons)
    if not spec.stats_enabled or not (comparisons or info.anova):
        return out
    pairwise = comparisons[0].test if comparisons else ""
    pairwise_text = tests.get(pairwise, pairwise)

    if info.anova and info.anova_title == "ANOVA à mesures répétées":
        out.append(say["rm"].format(factor=spec.group or "condition",
                                    subject=spec.stats_pair_by or say["rows"])
                   + pairwise_text + ".")
    elif info.anova and spec.subgroup:
        out.append(say["two_way"].format(a=spec.group, b=spec.subgroup)
                   + pairwise_text + ".")
    else:
        if spec.stats_test != "auto":
            lead = say["chosen_lead"]
        elif paired_plot:
            lead = say["auto_paired"] + say["auto_lead"]
        else:
            lead = say["auto"] + say["auto_lead"]
        if info.omnibus and info.omnibus[0]:
            name = info.omnibus[0]
            omnibus = tests.get(name, name)
            followed = ("suivie" if name in FEMININE else "suivi")                 if language == "fr" else ""
            then = say["omnibus_then"].format(omnibus=omnibus,
                                              followed=followed)
            follow = _de(pairwise_text) if language == "fr" else pairwise_text
            # after "compared with" / "comparés par", in the sentence's middle
            body = then[:1].lower() + then[1:] + follow
        else:
            body = pairwise_text
        if spec.stats_mode == "vs_control" and spec.stats_control:
            scope = say["pairs_control"].format(control=spec.stats_control)
        else:
            scope = say["pairs_all"]
        # French sets a space before a semicolon
        text = f"{lead}{body}{say['semicolon']}{scope}"
        if pairwise in ("t apparié", "Wilcoxon apparié"):
            # long format pairs by a subject column, wide format by row
            text += (say["paired_by"].format(column=spec.stats_pair_by)
                     if spec.stats_pair_by and spec.group
                     else say["paired_rows"])
        out.append(_sentence(text) + ".")

    if len(comparisons) > 1 and pairwise not in SELF_CORRECTING \
            and spec.stats_correction in ("holm", "bonferroni", "fdr_bh"):
        out.append(say["correction"].format(
            method=say[spec.stats_correction]))
    out.append(say["threshold"]
               + (say["stars"] if spec.stats_format in ("stars", "both")
                  else "") + ".")
    if info.outliers:
        out.append(say["grubbs"].format(count=len(info.outliers)))
    return out


def _survival(spec, info, say) -> list[str]:
    text = say["km"] + (say["km_ci"] if spec.survival_ci else "")
    sizes = _sizes(info.descriptives)
    events = _sizes(info.descriptives, "Événements")
    if sizes:
        text += say["km_n"].format(n=sum(sizes), events=sum(events))[:-1]
    out = [text + (say["km_censor"] if spec.show_censors else ".")]
    if spec.stats_enabled and info.omnibus:
        out.append(say["logrank"])
        if len(info.comparisons) > 1 and \
                spec.stats_correction in ("holm", "bonferroni", "fdr_bh"):
            out.append(say["logrank_pairs"].format(
                method=say[spec.stats_correction]))
    return out


def _contingency(spec, info, say) -> list[str]:
    display = (say["ct_display_percent"] if spec.contingency_view == "percent"
               else say["ct_display_counts"])
    out = [display + _n_clause(say, _sizes(info.descriptives))]
    if spec.stats_enabled and info.omnibus:
        name = info.omnibus[0]
        key = {label: key for key, label in st.CONTINGENCY_LABELS.items()
               }.get(name)
        if key:
            out.append(say["ct_test"].format(test=say[key]))
        if len(info.comparisons) > 1 and \
                spec.stats_correction in ("holm", "bonferroni", "fdr_bh"):
            out.append(say["ct_pairs"].format(
                method=say[spec.stats_correction]))
    if any(r.get("Mesure") == "Odds ratio" for r in info.contingency):
        out.append(say["ct_effects"])
    return out


def _xy(spec, info, say, language) -> list[str]:
    out = []
    if spec.plot_type == "line" and spec.error_type in ("sem", "sd", "ci95",
                                                        "minmax"):
        out.append(say["mean_error"].format(error=say[spec.error_type]) + ".")
    model = fitting.FIT_MODEL.normalise(spec.fit_model)
    if model != "none" and info.fits:
        text = say["fit"].format(model=MODELS[language].get(model, model))
        if spec.fit_ci:
            text += say["fit_ci"]
        out.append(text + say["fit_end"])
        comparison = info.fit_comparison
        if comparison is not None and comparison.ok:
            if comparison.shared == fitting.ONE_CURVE:
                out.append(say["compare_one"])
            else:
                labels = list(comparison.free)
                series = (_join(labels, say["and"]) if len(labels) <= 3
                          else say["series_all"].format(count=len(labels)))
                out.append(say["compare_param"].format(
                    param=comparison.shared, series=series))
    return out


def _agreement(spec, info, say) -> list[str]:
    result = info.bland_altman or {}
    if result.get("n", 0) < 3 or len(info.groups) != 2:
        return []
    a, b = info.groups
    diff = say["ba_pct" if spec.ba_view == "percent" else "ba_abs"].format(
        a=a, b=b)
    return [say["ba"].format(a=a, b=b, n=result["n"], diff=diff,
                             ci=say["ba_ci"] if spec.ba_ci else ""),
            say["ba_p"]]


def methods_text(spec, info, language: str = "en") -> str:
    """The paragraph for one figure, in "en" or "fr"."""
    language = language if language in LANGUAGES else "en"
    say = PHRASES[language]
    tests = TESTS[language]
    if spec.plot_type in ("bar", "box", "violin", "paired"):
        sentences = _categorical(spec, info, say, tests, language)
    elif spec.plot_type == "survival":
        sentences = _survival(spec, info, say)
    elif spec.plot_type == "contingency":
        sentences = _contingency(spec, info, say)
    elif spec.plot_type == "bland_altman":
        sentences = _agreement(spec, info, say)
    elif spec.plot_type in ("line", "scatter"):
        sentences = _xy(spec, info, say, language)
    else:
        sentences = []
    sentences.append(say["software"].format(**_versions()))
    return " ".join(s.strip() for s in sentences if s.strip())
