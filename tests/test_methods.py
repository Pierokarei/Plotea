"""The Methods paragraph: it says what was computed, in either language.

A paragraph that names a test Plotea did not run would end up in an
article. So it is checked against what the render did - the test of the
comparisons it made, the global test it ran - and the two languages are
held phrase for phrase, so that neither can lack a sentence.
"""
import re
import string

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotea import __version__
from plotea.core import demo, fitting, methods, plotting
from plotea.core import stats as st
from plotea.core.plotspec import PlotSpec


def paragraph(df, language="en", **fields):
    spec = PlotSpec(**fields)
    info = plotting.render(Figure(), spec, df)
    return methods.methods_text(spec, info, language), info


def viability(language="en", **fields):
    fields = {"plot_type": "bar", "group": "Traitement", "y": ["Viabilité"],
              "stats_enabled": True, **fields}
    return paragraph(demo.viability().df, language, **fields)


def fields_of(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


# --------------------------------------------------------------------------
# Two languages, one paragraph
# --------------------------------------------------------------------------
@pytest.mark.parametrize("table", ["PHRASES", "TESTS", "MODELS"])
def test_both_languages_have_every_phrase(table):
    content = getattr(methods, table)
    assert set(content["fr"]) == set(content["en"])
    for key in content["en"]:
        assert fields_of(content["fr"][key]) == fields_of(
            content["en"][key]), key


def test_every_test_plotea_can_run_has_its_words():
    produced = set(st.TEST_LABELS.values()) | {"Dunn", "Dunnett",
                                                "Tukey HSD"}
    produced -= {"ANOVA à mesures répétées"}      # described on its own
    produced |= {"ANOVA à un facteur", "Kruskal-Wallis"}
    for language in methods.LANGUAGES:
        assert produced <= set(methods.TESTS[language]), language


def test_every_fit_model_has_its_words():
    models = {k for k, m in fitting.MODELS.items() if m.func is not None}
    for language in methods.LANGUAGES:
        assert models <= set(methods.MODELS[language])


# --------------------------------------------------------------------------
# It says what was computed
# --------------------------------------------------------------------------
def test_the_test_named_is_the_test_that_ran():
    text, info = viability()
    ran = info.comparisons[0].test
    assert methods.TESTS["en"][ran] in text
    assert methods.TESTS["en"][info.omnibus[0]].lower() in text.lower()
    assert "Shapiro-Wilk" in text                 # auto says why


def test_a_test_chosen_by_name_is_not_said_to_be_automatic():
    text, _info = viability(stats_test="kruskal_dunn")
    assert "Kruskal-Wallis test followed by Dunn's test" in text
    assert "Shapiro-Wilk" not in text


def test_tests_that_correct_themselves_get_no_correction_sentence():
    text, info = viability(stats_test="anova_tukey")
    assert info.comparisons[0].test == "Tukey HSD"
    assert "Tukey's HSD" in text and "adjusted" not in text
    text, _info = viability(stats_test="dunnett", stats_mode="vs_control",
                            stats_control="Contrôle")
    assert "Dunnett's test" in text and "compared with Contrôle" in text
    assert "adjusted" not in text


@pytest.mark.parametrize("correction, words", [
    ("holm", "Holm method"), ("bonferroni", "Bonferroni method"),
    ("fdr_bh", "Benjamini-Hochberg"), ("none", None)])
def test_the_correction_named_is_the_one_applied(correction, words):
    text, _info = viability(stats_correction=correction)
    if words:
        assert words in text
    else:
        assert "adjusted" not in text


def test_without_statistics_no_test_is_claimed():
    text, _info = viability(stats_enabled=False)
    assert "compared" not in text and "significant" not in text
    assert text.startswith("Data are shown as mean ± SEM")
    assert "(n = 12 per group)" in text


def test_the_error_bars_and_the_plot_are_described():
    assert "mean ± SD" in viability(error_type="sd")[0]
    assert "95% confidence interval" in viability(error_type="ci95")[0]
    assert "Box plots show the median" in viability(plot_type="box")[0]


def test_paired_tests_say_how_subjects_were_matched():
    rng = np.random.default_rng(5)
    rows = [{"Sujet": s, "Temps": t, "Valeur": float(rng.normal(10 + i, 1))}
            for s in range(8) for i, t in enumerate(("Avant", "Après"))]
    text, _info = paragraph(pd.DataFrame(rows), plot_type="bar",
                            group="Temps", y=["Valeur"], stats_enabled=True,
                            stats_test="paired_t", stats_pair_by="Sujet")
    assert "paired t tests" in text and "matched by Sujet" in text


def test_survival_contingency_and_curves():
    text, _ = paragraph(demo.survival().df, plot_type="survival",
                        x="Temps (mois)", group="Bras",
                        event_col="Événement", stats_enabled=True)
    assert "Kaplan-Meier" in text and "log-rank test" in text
    assert "(n = 80;" in text

    two_arms = demo.contingency().df.iloc[:2]
    text, _ = paragraph(two_arms, plot_type="contingency",
                        group="Traitement", stats_enabled=True,
                        y=["Répondeurs", "Non-répondeurs"])
    assert "Two-sided Fisher's exact test" in text
    assert "odds ratio and the relative risk" in text

    text, _ = paragraph(demo.dose_response().df, plot_type="line",
                        x="log[C] (M)", y=["Réponse (%)"], group="Composé",
                        fit_model="hill4_log", fit_compare="logEC50")
    assert "four-parameter logistic" in text
    assert "each replicate being treated as an individual point" in text
    assert ("Whether logEC50 differs between Inhibiteur 1 and Inhibiteur 2 "
            "was tested with the extra sum-of-squares F test") in text


def test_the_versions_make_it_reproducible():
    import scipy

    text, _ = viability()
    assert f"Plotea {__version__}" in text and f"SciPy {scipy.__version__}" \
        in text


# --------------------------------------------------------------------------
# French that reads like French
# --------------------------------------------------------------------------
FRENCH_CASES = [
    {}, {"stats_test": "kruskal_dunn"}, {"stats_test": "anova_tukey"},
    {"stats_test": "dunnett", "stats_mode": "vs_control",
     "stats_control": "Contrôle"}, {"plot_type": "box"},
]


@pytest.mark.parametrize("fields", FRENCH_CASES)
def test_french_grammar(fields):
    text, _info = viability("fr", **fields)
    for wrong in ("de des ", "de le ", "de du ", "suivi de du",
                  "suivie de du"):
        assert wrong not in text, wrong
    assert not re.search(r"[^ ][;:]", text.replace("log(-log)", "")), text
    assert text.startswith(("Les données sont présentées",
                            "Les boîtes à moustaches"))


def test_french_names_the_tests_in_french():
    text, _info = viability("fr", stats_test="kruskal_dunn")
    assert "le test de Kruskal-Wallis suivi du test de Dunn" in text
    text, _info = viability("fr", stats_test="anova_tukey")
    assert "une ANOVA à un facteur suivie du test HSD de Tukey" in text


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
def test_the_methods_tab(window):
    from PyQt6.QtWidgets import QApplication

    window.current_spec().stats_enabled = True
    window._render_now()
    panel = window.stats_panel
    assert panel.tabs.tabText(panel.tabs.indexOf(panel.methods_page)) == \
        "Méthodes"
    assert panel.cmb_methods_language.currentData() == "fr"
    assert panel.methods.toPlainText().startswith("Les données")

    panel.cmb_methods_language.setCurrentIndex(
        panel.cmb_methods_language.findData("en"))
    assert panel.methods.toPlainText().startswith("Data are shown")

    panel.tabs.setCurrentWidget(panel.methods_page)
    panel.copy_current()
    assert QApplication.clipboard().text() == panel.methods.toPlainText()


def test_a_composite_figure_is_not_described_by_the_last_plot(window):
    window.current_spec().stats_enabled = True
    window._render_now()
    window.new_panel()
    window._render_now()
    text = window.stats_panel.methods.toPlainText()
    assert "figure composite" in text and "Les données" not in text
