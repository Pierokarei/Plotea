# Passer de Prism à Plotea

*[English version](from-prism.md)*

Cette page s'adresse à celles et ceux qui connaissent GraphPad Prism et
veulent faire la même chose dans Plotea : récupérer leurs fichiers, retrouver
chaque analyse, et savoir ce qui manque encore. Elle décrit Plotea 1.2.0.

Plotea est gratuit et libre. Il ne cherche pas à copier Prism écran par
écran : la plupart des analyses s'y trouvent, mais rangées autrement.

## 1. Récupérer ses fichiers Prism

**« Fichier » ▸ « Importer des données... »** ouvre les fichiers `.pzfx`.
Chaque tableau de données devient une table Plotea, accompagnée du graphique
que Prism en aurait tiré :

| Tableau Prism | Dans Plotea |
|---|---|
| XY (réplicats, ou moyenne / SD / N) | courbe, moyenne ± erreur |
| Colonnes | barres, une par groupe |
| Groupé | barres groupées (ligne × colonne) |
| Survie | courbes de Kaplan-Meier, avec le log-rank |
| Contingence | barres empilées, test exact de Fisher ou khi² |
| Parties d'un tout, variables multiples, imbriqué | les données seules, pour l'instant |

- Les **valeurs exclues** dans Prism (en bleu italique) sont laissées de
  côté, comme Prism le fait, et comptées dans le message de fin d'import.
- Les **graphiques et analyses** de Prism sont enregistrés dans un format
  que seul Prism lit : ils ne sont pas repris. Les données, si.
- Les fichiers **`.prism`** (Prism 10) doivent d'abord être enregistrés en
  `.pzfx` depuis Prism.
- On peut aussi copier un tableau dans Prism et le coller dans Plotea :
  **« Édition » ▸ « Coller des données »** (Ctrl+V).

## 2. La différence de fond : des tables simples, des colonnes choisies

Dans Prism, on choisit un type de tableau au départ, et les analyses y sont
attachées. Dans Plotea, une table est un simple tableur. On choisit ensuite,
pour chaque graphique, son **type** et les **colonnes** qu'il utilise, dans
le panneau **« Mise en forme »** :

- **« Type de graphique »** : barres, boxplot, survie, ROC…
- **« Données »** : **« Valeurs Y »** (ce qu'on mesure), **« Grouper par »**
  (la colonne des groupes), **« Sous-groupe »** (un second facteur),
  **« Axe X »** pour les courbes.

Deux dispositions sont acceptées : le **format long** (une ligne par
mesure, une colonne qui dit le groupe — le plus souple) et le **format
large** (une colonne par groupe, comme dans un tableau Colonnes de Prism).
Le [README](../README.md#deux-formats-de-données) les détaille.

Un graphique se souvient de ses réglages pour chaque table : on peut passer
d'une table à l'autre et revenir sans rien perdre.

## 3. Où trouver chaque analyse de Prism

Les résultats s'affichent dans le panneau **« Analyses »**, en bas, dans
des onglets ; **« Copier »** et **« Exporter CSV »** en sortent le tableau
affiché.

| Dans Prism | Dans Plotea |
|---|---|
| Statistiques de colonnes | onglet **« Descriptives »** |
| Test t (non apparié, Welch), Mann-Whitney | section **« Statistiques »**, **« Test »** : « t de Student », « t de Welch », « Mann-Whitney » |
| Test t apparié, Wilcoxon | « t apparié », « Wilcoxon apparié », avec la colonne **« Appariement »** (format long) ou en format large |
| ANOVA à un facteur + Tukey | « ANOVA + Tukey » |
| ANOVA de Welch + Games-Howell ou Dunnett T3 | « ANOVA de Welch », puis **« Paires après Welch »** |
| Kruskal-Wallis + Dunn | « Kruskal-Wallis + Dunn » |
| Comparaison à un témoin (Dunnett) | « Dunnett (vs contrôle) », puis **« Contrôle »** |
| ANOVA à mesures répétées | « ANOVA à mesures répétées » (correction de Greenhouse-Geisser) |
| ANOVA à deux facteurs | barres avec **« Grouper par »** et **« Sous-groupe »** ; onglet **« ANOVA 2 facteurs »** |
| Correction des comparaisons multiples | **« Correction »** : Bonferroni, Holm, Benjamini-Hochberg (FDR) |
| Valeurs aberrantes (Grubbs) | onglet **« Aberrantes »** |
| Tableau de contingence (Fisher, khi²) | type « Contingence (effectifs) » ; odds ratio, risque relatif et V de Cramér dans l'onglet **« Effets »** |
| Survie (Kaplan-Meier, log-rank) | type « Survie (Kaplan-Meier) » ; médiane de survie dans **« Descriptives »** |
| Régression non linéaire | section **« Ajustement de courbe »**, **« Modèle »** ; paramètres, R² et erreurs dans l'onglet **« Ajustements »** |
| Comparer des ajustements (test F) | **« Comparer »** : « Une seule courbe pour toutes les séries ? » ou un paramètre (EC50…) |
| Interpoler une gamme étalon | **« Doser les inconnues (lignes sans X) »** ; onglet **« Dosage »** |
| Aire sous la courbe | section **« Aire sous la courbe »** ; onglet **« Aires »** |
| Courbe ROC | type « Courbe ROC (diagnostic) » ; onglet **« ROC »** |
| Bland-Altman | type « Bland-Altman (concordance) » ; onglet **« Effets »** |
| Corrélation | ajustement « Linéaire (y = ax + b) » : r de Pearson et p de la pente dans **« Ajustements »** ; ou une carte de chaleur des corrélations entre colonnes |
| Normaliser, retirer une ligne de base, transformer | **« Données » ▸ « Transformer les données... »** |
| Graphique avant/après | type « Avant/après apparié » |
| Carte de chaleur | type « Carte de chaleur » |

Le choix **« Test recommandé »** se déduit du **« Plan expérimental »**
que vous déclarez, jamais d'un test de normalité : t de Welch pour deux
groupes indépendants, ANOVA de Welch suivie de Games-Howell au-delà, t
apparié pour deux conditions sur les mêmes sujets. Tant que le plan n'est
pas précisé, ou s'il compte plusieurs facteurs ou plusieurs temps, aucun
test n'est lancé : Plotea le demande. L'onglet « Comparaisons » explique le
choix ; les tests non paramétriques se choisissent explicitement.

Ce que Prism n'a pas : l'onglet **« Méthodes »** rédige le paragraphe à
coller dans l'article, en français ou en anglais, à partir de ce qui a
réellement été calculé.

## 4. Mettre en forme et exporter

- **« Style » ▸ « Thématique de journal »** : Nature, Science, Cell, PNAS…
  police, largeur de colonne et palette suivent les consignes de chaque
  revue.
- **« Fichier » ▸ « Exporter la figure... »** : SVG, PDF et EPS au texte
  modifiable dans Illustrator ou Inkscape ; PNG, TIFF et JPEG jusqu'à
  1200 dpi.
- **« Graphique » ▸ « Nouvelle figure composite »** : plusieurs graphiques
  sur une figure, lettrés A, B, C.
- **« Axe Y interrompu »** (section **« Axes »**) pour de petites et de
  très grandes valeurs sur un même graphique.
- **« Style » ▸ « Enregistrer le style courant... »** pour réutiliser une
  mise en forme.

## 5. Ce que Plotea ne fait pas encore

Pour ne pas le découvrir au milieu d'une analyse :

- les tableaux **Parties d'un tout**, **Variables multiples** et
  **Imbriqué** sont importés, mais pas encore tracés ;
- les tableaux Colonnes ou Groupés **saisis en moyenne / SD / N** donnent
  des barres sans barres d'erreur (seules les courbes en tracent à partir
  de résumés) ;
- pas de **Brown-Forsythe**, pas de test de **Friedman**, pas de
  correction de **Šidák** ;
- pas de **modèle mixte** pour des mesures répétées incomplètes ;
- pas de méthode **ROUT** pour les valeurs aberrantes (Grubbs seulement) ;
- pas de **régression de Cox** ;
- pas de modèle logistique à **cinq paramètres (5PL)** ;
- pas de **tests t multiples** (un test par ligne) ;
- pas d'**analyse de puissance** ;
- pas de coefficient de **Spearman** affiché seul.

Il vous en manque une autre, ou l'une de celles-ci vous est indispensable ?
[Dites-le](https://github.com/Pierokarei/Plotea/issues/new/choose) : c'est
ce qui décide de la suite.

## 6. Pour commencer

**« Fichier » ▸ « Jeux de données d'exemple »** ouvre un exemple prêt pour
chaque type de graphique : viabilité cellulaire, dose-réponse, survie,
contingence, dosage ELISA, tolérance au glucose, biomarqueurs (ROC)…
Partir de l'exemple le plus proche de vos données est souvent le plus
rapide.
