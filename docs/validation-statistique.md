# Validation statistique

Cette page dit, pour chaque analyse de Plotea, quelle méthode est employée,
d'où elle vient et quel test automatique vérifie que Plotea la calcule
correctement. Elle s'adresse à qui doit faire confiance à un résultat avant
de le publier, ou le justifier devant un relecteur.

*English version: [Statistical validation](statistical-validation.md).*

## Comment les résultats sont vérifiés

Un test qui compare Plotea à lui-même ne prouve rien. Chaque résultat est
donc confronté à quelque chose d'extérieur, de quatre façons :

- **données publiées** : un jeu de données d'article ou de manuel, dont on
  redemande les chiffres imprimés (par exemple l'aire sous la courbe ROC de
  Hanley et McNeil, 0,893) ;
- **calcul indépendant** : la même quantité obtenue par une autre voie (une
  formule de manuel écrite à la main, une régression au lieu d'une ANOVA,
  SciPy appelé directement) ;
- **identité** : un cas où deux méthodes doivent coïncider exactement (une
  ANOVA de Welch à deux groupes est le carré du t de Welch) ;
- **simulation** : des milliers de jeux de données tirés au hasard, pour
  vérifier qu'un intervalle à 95 % couvre la vraie valeur environ 95 fois
  sur 100, ou qu'un test sans effet réel ne conclut à tort qu'environ 5 fois
  sur 100.

Les tests tournent à chaque modification, sur Windows, macOS et Linux. Pour
les relancer soi-même, depuis les sources :

```bash
pip install -e ".[dev]"
pytest tests/test_survival.py        # un fichier
pytest tests/test_validation.py -v   # le détail de chaque test
```

Dans les tableaux ci-dessous, un test est désigné par son fichier (dans le
dossier `tests/`) et son nom, par exemple
`test_survival.py::test_logrank_matches_the_published_value`.

## Statistiques descriptives et barres d'erreur

Moyenne, écart-type (n − 1), SEM, médiane et quartiles ; l'intervalle de
confiance à 95 % d'une moyenne repose sur la loi de Student à n − 1 degrés
de liberté, dans le tableau Descriptives comme pour les barres d'erreur.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Chaque colonne du tableau Descriptives | calcul indépendant (définitions) | `test_validation.py::test_descriptives_follow_their_definitions` |
| L'IC 95 % d'une moyenne de 5 valeurs couvre 95 fois sur 100 | simulation | `test_validation.py::test_the_interval_of_a_mean_covers_95_times_in_100` |
| Barres d'erreur, tableau Descriptives et tableaux résumés donnent le même IC | calcul indépendant | `test_validation.py::test_error_bars_and_summary_tables_give_the_same_interval` |

## Test recommandé

Le test recommandé se déduit du plan expérimental déclaré, jamais d'un test
de normalité : t de Welch pour deux groupes indépendants, ANOVA de Welch
(Welch, *Biometrika* 1951) suivie de Games-Howell (Games et Howell,
*J Educ Stat* 1976) ou de Dunnett T3 (Dunnett, *JASA* 1980) au-delà, t
apparié pour deux conditions sur les mêmes sujets. Plan non précisé,
plusieurs facteurs ou plusieurs temps : aucun test n'est lancé.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| ANOVA de Welch à deux groupes = carré du t de Welch | identité | `test_recommended.py::test_welch_anova_of_two_groups_is_welchs_t_squared` |
| ANOVA de Welch = formule de Welch (1951) | calcul indépendant | `test_recommended.py::test_welch_anova_follows_welchs_formula` |
| Games-Howell et Dunnett T3 à une comparaison = t de Welch | identité | `test_recommended.py::test_games_howell_of_two_groups_is_welchs_t`, `test_recommended.py::test_dunnett_t3_of_one_comparison_is_welchs_t` |
| Loi du module maximum studentisé (Dunnett T3) | simulation | `test_recommended.py::test_the_studentized_maximum_modulus_matches_its_definition` |
| 5 % de faux positifs sous variances inégales, là où l'ANOVA classique dérive | simulation | `test_recommended.py::test_welchs_anova_holds_its_error_rate_where_the_classical_one_drifts` |
| Games-Howell et T3 tiennent l'erreur sur l'ensemble des paires | simulation | `test_recommended.py::test_the_pairs_hold_the_family_error_rate` |
| Plan non précisé : aucun test, la question est posée | comportement | `test_recommended.py::test_an_undeclared_design_runs_nothing_and_asks` |
| La forme des données ne change jamais le choix | comportement | `test_recommended.py::test_the_shape_of_the_data_never_changes_the_choice` |

## Comparaisons de groupes

t de Student, de Welch et apparié, Mann-Whitney, Wilcoxon apparié ; ANOVA à
un facteur et Tukey HSD (Tukey-Kramer pour des effectifs inégaux) ;
Kruskal-Wallis et Dunn (Dunn, *Technometrics* 1964) ; Dunnett contre un
contrôle (Dunnett, *JASA* 1955).

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Le p affiché = un t de Welch calculé à part, cellule par cellule | calcul indépendant | `test_stats_fixes.py::test_grouped_matches_manual` |
| t apparié = `scipy.stats.ttest_rel` | calcul indépendant | `test_paired.py::test_auto_means_a_paired_t_test_on_normal_differences` |
| Wilcoxon apparié = `scipy.stats.wilcoxon` | calcul indépendant | `test_stats_fixes.py::test_wide_format_pairs_on_the_row` |
| Un sujet manquant retire ce sujet, sans décaler l'appariement | comportement | `test_stats_fixes.py::test_pairing_survives_missing_values` |
| ANOVA à un facteur = formules du manuel | calcul indépendant | `test_validation.py::test_the_one_way_anova_is_the_textbook_one` |
| Tukey HSD = étendue studentisée de chaque différence | calcul indépendant | `test_validation.py::test_tukeys_hsd_is_the_studentized_range_of_each_difference` |
| Dunn à deux groupes = Kruskal-Wallis | identité | `test_advanced_stats.py::test_dunn_on_two_groups_is_the_kruskal_wallis_test` |
| Kruskal-Wallis + Dunn fait bien Dunn, pas Mann-Whitney | calcul indépendant | `test_advanced_stats.py::test_kruskal_dunn_runs_dunn_not_mann_whitney` |
| Dunnett = `scipy.stats.dunnett`, contre le seul contrôle | calcul indépendant | `test_advanced_stats.py::test_dunnett_matches_scipy_and_compares_only_with_the_control` |
| Dunnett donne le même résultat à chaque affichage | comportement | `test_advanced_stats.py::test_dunnett_gives_the_same_answer_twice` |

## Corrections des comparaisons multiples

Bonferroni, Holm (Holm, *Scand J Stat* 1979) et Benjamini-Hochberg
(Benjamini et Hochberg, *JRSS B* 1995).

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| L'exemple de l'article de 1995 : 3 rejets pour Bonferroni et Holm, 4 pour Benjamini-Hochberg | données publiées | `test_validation.py::test_the_published_example_rejects_what_the_paper_says` |
| Chaque correction calculée à la main | calcul indépendant | `test_validation.py::test_each_correction_follows_its_definition` |

## ANOVA à deux facteurs et à mesures répétées

Sommes des carrés de type III ; ANOVA à mesures répétées avec correction de
Greenhouse-Geisser (*Psychometrika* 1959).

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Plan équilibré : sommes des carrés = formules du manuel | calcul indépendant | `test_anova.py::test_balanced_matches_hand_computation` |
| Une interaction croisée est détectée, des effets parallèles non | comportement | `test_anova.py::test_detects_interaction` |
| Mesures répétées : même F qu'une régression à variables indicatrices | calcul indépendant | `test_advanced_stats.py::test_rm_anova_matches_a_least_squares_fit` |
| Sphéricité : ε = 1 sous symétrie composée, et dans ses bornes | identité | `test_advanced_stats.py::test_sphericity_holds_under_compound_symmetry`, `test_advanced_stats.py::test_sphericity_stays_inside_its_bounds` |

## Valeurs aberrantes

Test de Grubbs itératif (α = 0,05) ; les valeurs signalées ne sont jamais
retirées.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| G = 2,4687 sur l'exemple du manuel NIST/SEMATECH | données publiées | `test_advanced_stats.py::test_grubbs_on_the_published_example` |
| Des données propres ne sont pas signalées | comportement | `test_advanced_stats.py::test_grubbs_leaves_clean_data_alone` |

## Survie

Kaplan-Meier, bande de confiance de Greenwood sur l'échelle log(−log),
test du log-rank.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| La courbe publiée de l'essai 6-MP contre placebo (Freireich, *Blood* 1963) | données publiées | `test_survival.py::test_kaplan_meier_matches_the_published_curve` |
| Le log-rank publié du même essai | données publiées | `test_survival.py::test_logrank_matches_the_published_value` |
| Une censure n'est comptée ni comme décès ni comme survie | comportement | `test_survival.py::test_censoring_is_neither_death_nor_survival` |

## Tableaux de contingence

Test exact de Fisher, khi² de Pearson avec ou sans correction de Yates,
odds ratio (Woolf) et risque relatif (Katz) avec leurs IC 95 %, V de Cramér.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Odds ratio 1,83 [1,44 ; 2,33] et risque relatif 1,82 de l'essai aspirine et infarctus (Agresti) | données publiées | `test_contingency.py::test_odds_ratio_and_relative_risk_of_the_aspirin_trial` |
| Khi² = 30,07 à 2 ddl, parti politique selon le sexe (Agresti) | données publiées | `test_contingency.py::test_chi_square_of_party_identification_by_gender` |
| p = 0,486 sur la dégustation de thé de Fisher | données publiées | `test_contingency.py::test_fisher_on_the_lady_tasting_tea` |
| Correction de Yates | calcul indépendant | `test_contingency.py::test_yates_correction_worked_out_by_hand` |
| V de Cramér | calcul indépendant | `test_contingency.py::test_cramers_v_from_its_definition` |

## Ajustement et comparaison de courbes

Moindres carrés (linéaires et non linéaires), bande de confiance par la
méthode delta ; comparaison de courbes par le test F des sommes de carrés
supplémentaires (Motulsky et Christopoulos, *Fitting models to biological
data*, 2004).

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Une droite exacte est retrouvée exactement | identité | `test_engine.py::test_linear_fit_is_exact` |
| Sur des droites, le test F = l'analyse de covariance | calcul indépendant | `test_fit_compare.py::test_lines_agree_with_the_analysis_of_covariance`, `test_fit_compare.py::test_three_series_agree_too` |
| Une EC50 différente est trouvée, une pente commune n'est pas signalée | comportement | `test_fit_compare.py::test_a_different_ec50_is_found_and_a_shared_slope_is_not_flagged` |
| Sans différence réelle, environ 5 % de fausses alertes | simulation | `test_fit_compare.py::test_when_nothing_differs_it_cries_wolf_about_five_percent_of_the_time` |
| Chaque réplicat compte, pas seulement les moyennes | comportement | `test_fit_compare.py::test_every_replicate_is_compared_not_the_means` |

## Dosage sur gamme étalon

Concentration lue sur la courbe ajustée ; intervalle à 95 % qui combine
l'incertitude de la courbe et la dispersion des mesures de l'échantillon
(intervalle de calibration classique : Draper et Smith, *Applied Regression
Analysis* ; ISO 11843-2), en supposant une variance constante.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Sur une droite, l'intervalle de calibration du manuel | calcul indépendant | `test_standard_curve.py::test_a_straight_line_gives_the_textbook_calibration_interval` |
| Part de la courbe et part de la mesure, chacune selon sa formule | calcul indépendant | `test_standard_curve.py::test_where_the_uncertainty_comes_from` |
| Sur un 4PL, l'intervalle couvre la vraie concentration environ 95 fois sur 100 | simulation | `test_standard_curve.py::test_the_interval_covers_the_true_concentration` |
| Le 4PL inversé à la main | calcul indépendant | `test_standard_curve.py::test_the_4pl_is_solved_for_x` |
| Rien n'est extrapolé hors de la gamme | comportement | `test_standard_curve.py::test_nothing_is_extrapolated_beyond_the_standards` |

## Aire sous la courbe

Méthode des trapèzes ; erreur type de Bailer (*J Pharmacokinet Biopharm*
1988) et IC 95 % à degrés de liberté de Satterthwaite.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| L'aire = les trapèzes de NumPy | calcul indépendant | `test_auc.py::test_the_area_is_the_trapezoids_of_the_means` |
| Coupure exacte là où la courbe croise sa ligne de base | calcul indépendant | `test_auc.py::test_crossing_the_baseline_is_cut_where_it_crosses` |
| Erreur type = formule de Bailer écrite à la main | calcul indépendant | `test_auc.py::test_the_standard_error_is_bailers` |
| L'IC 95 % couvre la vraie aire environ 95 fois sur 100 | simulation | `test_auc.py::test_the_interval_covers_the_true_area_95_times_in_100` |

## Courbes ROC

Aire sous la courbe et IC 95 % de DeLong (*Biometrics* 1988, calcul par
les rangs de Sun et Xu, 2014) ; seuil de Youden ; sensibilité et
spécificité avec intervalles de Wilson ; test de DeLong pour des marqueurs
mesurés sur les mêmes sujets.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| AUC = 0,893 sur les scanners de Hanley et McNeil (*Radiology* 1982) | données publiées | `test_roc.py::test_the_published_area_comes_back` |
| AUC = statistique U de Mann-Whitney / (m·n) | identité | `test_roc.py::test_the_area_is_the_mann_whitney_statistic` |
| Valeurs de placement de DeLong = comparaison de toutes les paires | calcul indépendant | `test_roc.py::test_placement_values_from_ranks_are_delongs` |
| Intervalle de Wilson du manuel (8 sur 10 : 0,490 à 0,943) | données publiées | `test_roc.py::test_wilson_intervals` |
| Couverture de l'IC et niveau du test apparié | simulation | `test_roc.py::test_the_interval_covers_and_the_paired_test_holds_its_level` |

## Concordance (Bland-Altman)

Biais, limites d'agrément à 95 % et leurs IC (Bland et Altman, *Lancet*
1986 ; *Stat Methods Med Res* 1999).

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Biais −2,1 l/min et écart-type 38,8 des débitmètres de l'article de 1986 | données publiées | `test_bland_altman.py::test_the_published_bias_and_standard_deviation` |
| Limites publiées −79,7 à 75,5 (à 2 écarts-types) | données publiées | `test_bland_altman.py::test_the_published_limits_with_their_two_standard_deviations` |
| IC et p du biais = ceux du t apparié de SciPy | calcul indépendant | `test_bland_altman.py::test_the_bias_interval_and_p_are_those_of_the_paired_t_test` |

## Cartes de chaleur

Scores z par ligne ou par colonne, corrélation de Pearson, classification
hiérarchique (lien moyen, distance euclidienne, ordre optimal des
feuilles).

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Chaque ligne centrée et réduite | calcul indépendant | `test_heatmap.py::test_each_row_scaled_to_mean_0_and_sd_1` |
| Matrice de corrélation = celle de pandas | calcul indépendant | `test_heatmap.py::test_the_correlation_matrix_is_pearsons` |
| La classification rapproche les gènes qui répondent de la même façon | comportement | `test_heatmap.py::test_clustering_puts_genes_that_answer_alike_together` |

## Paragraphe Méthodes

Le paragraphe décrit ce qui a été calculé : le test qui a réellement
tourné, la correction réellement appliquée, les versions des logiciels.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Le test nommé est celui qui a tourné | comportement | `test_methods.py::test_the_test_named_is_the_test_that_ran` |
| La correction nommée est celle qui a été appliquée | comportement | `test_methods.py::test_the_correction_named_is_the_one_applied` |
| Les deux langues ont les mêmes phrases | comportement | `test_methods.py::test_both_languages_have_every_phrase` |

## De l'interface au résultat

Les défauts les plus sournois ne viennent pas des calculs mais de ce que
l'interface leur transmet : une colonne d'événement effacée par un clic, un
appariement décalé, une table rechargée de travers. Ces tests pilotent
Plotea comme un utilisateur (importer, choisir les colonnes, renommer,
enregistrer, fermer, rouvrir) et comparent les résultats à un calcul fait
directement sur le fichier d'origine.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Survie : du fichier CSV au projet rouvert | calcul indépendant | `workflows/test_workflows.py::test_survival_from_the_file_to_the_reopened_project` |
| Appariement après suppression d'un sujet | calcul indépendant | `workflows/test_workflows.py::test_paired_subjects_stay_paired_after_a_deletion` |
| Dosage piloté par l'interface | calcul indépendant | `workflows/test_workflows.py::test_standard_curve_assay_through_the_interface` |
| L'interface anglaise calcule la même chose | identité | `workflows/test_workflows.py::test_the_english_interface_computes_the_same` |
| L'ordre des lignes ne change pas les résultats | identité | `workflows/test_invariance.py::test_the_order_of_the_rows` |
| Enregistrer puis rouvrir ne change pas les résultats | identité | `workflows/test_invariance.py::test_a_trip_to_the_disk` |
| Les nombres reviennent du fichier au dernier bit près | identité | `workflows/test_project_roundtrip.py::test_numbers_come_back_to_the_last_bit` |

## Enregistrement des projets

Un résultat juste ne sert à rien si le fichier qui le porte se perd.
L'enregistrement est tout ou rien : écrit à côté, forcé sur le disque, relu,
puis mis en place d'un seul coup ; la version remplacée est conservée.

| Ce qui est vérifié | Comment | Test |
|---|---|---|
| Un processus tué en pleine écriture laisse toujours un fichier qui s'ouvre, entier | simulation | `test_safe_saving.py::test_killed_in_the_middle_of_a_save_the_file_still_opens` |
| Une écriture qui échoue laisse le fichier précédent intact | comportement | `test_safe_saving.py::test_a_write_that_fails_leaves_the_previous_file` |
| Une archive endommagée est repérée par ses sommes de contrôle | comportement | `test_safe_saving.py::test_a_damaged_archive_is_caught_by_its_checksums` |
| Chaque enregistrement conserve la version qu'il remplace | comportement | `test_safe_saving.py::test_each_save_keeps_the_version_it_replaces` |
| Un fichier qui ne s'ouvre plus garde ses versions | comportement | `test_safe_saving.py::test_versions_of_a_file_that_no_longer_opens` |

## Limites connues

- Plusieurs lois de probabilité viennent de SciPy (Student, F, khi², étendue
  studentisée, Shapiro-Wilk, Mann-Whitney, Wilcoxon, Dunnett) : Plotea
  vérifie qu'il les appelle avec les bonnes quantités, pas SciPy lui-même,
  qui a ses propres tests.
- Les ajustements non linéaires partent de valeurs initiales estimées sur
  les données (de plusieurs départs pour la comparaison de courbes) ; sur
  des données mal conditionnées, un minimum local reste possible. Le R², les résidus et la courbe tracée permettent de s'en
  apercevoir.
- L'intervalle du dosage suppose une variance constante le long de la
  courbe ; une pondération en 1/Y² n'est pas encore proposée.
- Les tests ne remplacent pas la vérification d'un plan expérimental :
  Plotea calcule ce qu'on lui demande sur les données qu'on lui donne.

Un écart entre Plotea et un autre logiciel, ou avec un résultat publié ?
Ouvrez un ticket sur [GitHub](https://github.com/Pierokarei/Plotea/issues)
avec les données et les deux résultats : il deviendra un test.
