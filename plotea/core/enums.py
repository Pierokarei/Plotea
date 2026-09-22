"""Machine keys and the labels shown to people, kept apart.

Project files store keys, never the French wording, so translating the
interface later cannot break a `.plotea` saved today. Reading a value accepts
a key, a current label or a legacy label, which makes old files migrate on
load without a conversion step.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass


def strip_accents(text: str) -> str:
    """'apparié' -> 'apparie', for matching a label written without them."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(frozen=True)
class Choice:
    key: str
    label: str


class Enum:
    """An ordered set of choices, addressable by key or by label."""

    def __init__(self, name: str, choices: list[tuple[str, str]],
                 legacy: dict | None = None):
        self.name = name
        self.choices = [Choice(key, label) for key, label in choices]
        self._by_key = {c.key: c for c in self.choices}
        self._by_label = {c.label: c for c in self.choices}
        #: old wording -> key, for project files written before this module
        self.legacy = dict(legacy or {})
        # An unaccented spelling of every label stays valid: scripts and
        # project files written before the interface gained its accents must
        # keep working.
        for choice in self.choices:
            plain = strip_accents(choice.label)
            if plain != choice.label and plain not in self._by_label:
                self.legacy.setdefault(plain, choice.key)
        for plain, key in list(self.legacy.items()):
            self.legacy.setdefault(strip_accents(plain), key)

    # -- lookups -----------------------------------------------------------
    def keys(self) -> list[str]:
        return [c.key for c in self.choices]

    def labels(self) -> list[str]:
        return [c.label for c in self.choices]

    def label(self, key: str) -> str:
        choice = self._by_key.get(key)
        return choice.label if choice else key

    def key(self, label: str) -> str:
        choice = self._by_label.get(label)
        return choice.key if choice else self.default

    @property
    def default(self) -> str:
        return self.choices[0].key if self.choices else ""

    def normalise(self, value) -> str:
        """Accept a key, a label or a legacy label; always return a key."""
        if value is None:
            return self.default
        text = str(value)
        if text in self._by_key:
            return text
        if text in self._by_label:
            return self._by_label[text].key
        if text in self.legacy:
            return self.legacy[text]
        return self.default

    def __contains__(self, key: str) -> bool:
        return key in self._by_key

    def __iter__(self):
        return iter(self.choices)

    def __len__(self) -> int:
        return len(self.choices)


# --------------------------------------------------------------------------
# The enumerations a PlotSpec stores
# --------------------------------------------------------------------------
PLOT_TYPE = Enum("plot_type", [
    ("line", "Courbe"),
    ("scatter", "Nuage de points"),
    ("histogram", "Histogramme"),
    ("box", "Boxplot"),
    ("violin", "Violin plot"),
    ("bar", "Barres + erreurs"),
])

ERROR_TYPE = Enum("error_type", [
    ("sem", "SEM"),
    ("sd", "SD"),
    ("ci95", "IC95"),
    ("minmax", "Min-Max"),
    ("none", "Aucune"),
])

HIST_STAT = Enum("hist_stat", [
    ("count", "Effectif"),
    ("density", "Densité"),
    ("probability", "Probabilité"),
    ("percent", "Pourcentage"),
])

VIOLIN_INNER = Enum("violin_inner", [
    ("box", "Boxplot"),
    ("quartiles", "Quartiles"),
    ("points", "Points"),
    ("none", "Aucun"),
])

POINT_STYLE = Enum("point_style", [
    ("jitter", "Jitter"),
    ("aligned", "Aligné"),
    ("swarm", "Swarm"),
    ("none", "Aucun"),
])

EQUATION_LOC = Enum("fit_equation_loc", [
    ("top left", "Haut gauche"),
    ("top right", "Haut droite"),
    ("bottom left", "Bas gauche"),
    ("bottom right", "Bas droite"),
])

STATS_TEST = Enum("stats_test", [
    ("auto", "Auto"),
    ("student", "t de Student"),
    ("welch", "t de Welch"),
    ("paired_t", "t apparié"),
    ("mannwhitney", "Mann-Whitney"),
    ("wilcoxon", "Wilcoxon apparié"),
    ("anova_tukey", "ANOVA + Tukey"),
    ("kruskal_dunn", "Kruskal-Wallis + Dunn"),
])

STATS_MODE = Enum("stats_mode", [
    ("all_pairs", "Toutes les paires"),
    ("vs_control", "vs contrôle"),
])

STATS_FORMAT = Enum("stats_format", [
    ("stars", "Étoiles"),
    ("pvalue", "p numérique"),
    ("both", "Les deux"),
])

CORRECTION = Enum("stats_correction", [
    ("none", "Aucune"),
    ("bonferroni", "Bonferroni"),
    ("holm", "Holm"),
    ("fdr_bh", "Benjamini-Hochberg (FDR)"),
])

FIT_MODEL = Enum("fit_model", [
    ("none", "Aucun"),
    ("linear", "Linéaire (y = ax + b)"),
    ("poly2", "Polynôme degré 2"),
    ("poly3", "Polynôme degré 3"),
    ("exp_growth", "Croissance exponentielle"),
    ("exp_decay", "Décroissance exponentielle (1 phase)"),
    ("log", "Logarithmique (y = a ln x + b)"),
    ("power", "Puissance (y = a x^b)"),
    ("michaelis", "Michaelis-Menten"),
    ("hill4", "Dose-réponse 4PL (X linéaire)"),
    ("hill4_log", "Dose-réponse 4PL (X = log concentration)"),
    ("gaussian", "Gaussienne"),
    ("sigmoid", "Sigmoïde logistique"),
], legacy={
    "Aucun": "none", "Linéaire": "linear", "Polynôme 2": "poly2",
    "Polynôme 3": "poly3", "Exponentielle": "exp_growth",
    "Décroissance exp": "exp_decay", "Logarithmique": "log",
    "Puissance": "power", "Michaelis-Menten": "michaelis",
    "Dose-réponse 4PL": "hill4", "Dose-réponse log": "hill4_log",
    "Gaussienne": "gaussian", "Sigmoïde": "sigmoid",
})

SPAN = Enum("span", [
    ("single", "Colonne simple"),
    ("double", "Double colonne"),
    ("custom", "Personnalisée"),
])

ERROR_DIRECTION = Enum("error_direction", [
    ("both", "Symétrique"),
    ("up", "Vers le haut"),
])

VIOLIN_SIDE = Enum("violin_side", [
    ("both", "Complet"),
    ("left", "Gauche"),
    ("right", "Droite"),
])

LEGEND_LOC = Enum("legend_loc", [
    ("best", "Automatique"),
    ("upper right", "Haut droite"),
    ("upper left", "Haut gauche"),
    ("lower left", "Bas gauche"),
    ("lower right", "Bas droite"),
    ("center left", "Centre gauche"),
    ("center right", "Centre droite"),
    ("upper center", "Haut centre"),
    ("lower center", "Bas centre"),
    ("outside right", "A droite du cadre"),
    ("outside top", "Au-dessus du cadre"),
])

PANEL_LETTERS = Enum("letters", [
    ("upper", "A, B, C"),
    ("lower", "a, b, c"),
    ("paren", "(a), (b), (c)"),
    ("none", "Aucune"),
])

TRANSFORM = Enum("transform", [
    ("percent", "Pourcentage du contrôle"),
    ("normalize", "Normaliser de 0 a 100"),
    ("log10", "Logarithme décimal"),
    ("ln", "Logarithme naturel"),
    ("log2", "Logarithme base 2"),
    ("zscore", "Score z"),
    ("baseline", "Soustraire la ligne de base"),
    ("ratio", "Rapport a une colonne"),
    ("aggregate", "Moyenne des réplicats"),
])

#: Fields of PlotSpec that hold a key, and the enum that governs them.
SPEC_FIELDS = {
    "plot_type": PLOT_TYPE,
    "error_type": ERROR_TYPE,
    "error_direction": ERROR_DIRECTION,
    "hist_stat": HIST_STAT,
    "violin_inner": VIOLIN_INNER,
    "violin_side": VIOLIN_SIDE,
    "point_style": POINT_STYLE,
    "fit_model": FIT_MODEL,
    "fit_equation_loc": EQUATION_LOC,
    "stats_test": STATS_TEST,
    "stats_mode": STATS_MODE,
    "stats_format": STATS_FORMAT,
    "stats_correction": CORRECTION,
    "span": SPAN,
    "legend_loc": LEGEND_LOC,
}

#: Same, for Panel.
PANEL_FIELDS = {
    "letters": PANEL_LETTERS,
    "span": SPAN,
}
