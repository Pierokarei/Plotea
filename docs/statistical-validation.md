# Statistical validation

For each analysis in Plotea, this page says which method is used, where it
comes from, and which automated test checks that Plotea computes it
correctly. It is for anyone who has to trust a result before publishing it,
or justify it to a reviewer.

*Version française : [Validation statistique](validation-statistique.md).*

## How the results are checked

A test that compares Plotea with itself proves nothing. Each result is
therefore held against something outside it, in four ways:

- **published data**: a dataset from a paper or a textbook, whose printed
  numbers must come back (for instance Hanley and McNeil's area under the
  ROC curve, 0.893);
- **independent computation**: the same quantity reached another way (a
  textbook formula written out by hand, a regression instead of an ANOVA,
  SciPy called directly);
- **identity**: a case where two methods must agree exactly (a Welch ANOVA
  of two groups is the square of Welch's t);
- **simulation**: thousands of random datasets, to check that a 95 %
  interval covers the true value about 95 times in 100, or that a test with
  no real effect is wrongly significant only about 5 times in 100.

The tests run on every change, on Windows, macOS and Linux. To run them
yourself, from the sources:

```bash
pip install -e ".[dev]"
pytest tests/test_survival.py        # one file
pytest tests/test_validation.py -v   # each test listed
```

In the tables below, a test is named by its file (in the `tests/` folder)
and its name, for instance
`test_survival.py::test_logrank_matches_the_published_value`.

## Descriptive statistics and error bars

Mean, standard deviation (n − 1), SEM, median and quartiles; the 95 %
confidence interval of a mean uses Student's t with n − 1 degrees of
freedom, in the Descriptive table as for error bars.

| What is checked | How | Test |
|---|---|---|
| Every column of the Descriptive table | independent computation (definitions) | `test_validation.py::test_descriptives_follow_their_definitions` |
| The 95 % CI of a mean of 5 values covers 95 times in 100 | simulation | `test_validation.py::test_the_interval_of_a_mean_covers_95_times_in_100` |
| Error bars, Descriptive table and summary tables give the same CI | independent computation | `test_validation.py::test_error_bars_and_summary_tables_give_the_same_interval` |

## Recommended test

The recommended test follows from the declared experimental design, never
from a normality test: Welch's t for two independent groups, a Welch ANOVA
(Welch, *Biometrika* 1951) followed by Games-Howell (Games and Howell,
*J Educ Stat* 1976) or Dunnett's T3 (Dunnett, *JASA* 1980) beyond that,
paired t for two conditions on the same subjects. Design not specified,
several factors or several times: no test is run.

| What is checked | How | Test |
|---|---|---|
| Welch ANOVA of two groups = Welch's t squared | identity | `test_recommended.py::test_welch_anova_of_two_groups_is_welchs_t_squared` |
| Welch ANOVA = Welch's (1951) formula | independent computation | `test_recommended.py::test_welch_anova_follows_welchs_formula` |
| Games-Howell and Dunnett T3 of one comparison = Welch's t | identity | `test_recommended.py::test_games_howell_of_two_groups_is_welchs_t`, `test_recommended.py::test_dunnett_t3_of_one_comparison_is_welchs_t` |
| Studentized maximum modulus distribution (Dunnett T3) | simulation | `test_recommended.py::test_the_studentized_maximum_modulus_matches_its_definition` |
| 5 % false positives under unequal variances, where the classical ANOVA drifts | simulation | `test_recommended.py::test_welchs_anova_holds_its_error_rate_where_the_classical_one_drifts` |
| Games-Howell and T3 hold the family-wise error rate | simulation | `test_recommended.py::test_the_pairs_hold_the_family_error_rate` |
| Design not specified: no test, the question is asked | behaviour | `test_recommended.py::test_an_undeclared_design_runs_nothing_and_asks` |
| The shape of the data never changes the choice | behaviour | `test_recommended.py::test_the_shape_of_the_data_never_changes_the_choice` |

## Group comparisons

Student's, Welch's and paired t, Mann-Whitney, Wilcoxon signed-rank;
one-way ANOVA and Tukey's HSD (Tukey-Kramer for unequal sizes);
Kruskal-Wallis and Dunn (Dunn, *Technometrics* 1964); Dunnett against a
control (Dunnett, *JASA* 1955).

| What is checked | How | Test |
|---|---|---|
| The p shown = a Welch t computed apart, cell by cell | independent computation | `test_stats_fixes.py::test_grouped_matches_manual` |
| Paired t = `scipy.stats.ttest_rel` | independent computation | `test_paired.py::test_auto_means_a_paired_t_test_on_normal_differences` |
| Wilcoxon signed-rank = `scipy.stats.wilcoxon` | independent computation | `test_stats_fixes.py::test_wide_format_pairs_on_the_row` |
| A missing subject drops that subject, without shifting the pairing | behaviour | `test_stats_fixes.py::test_pairing_survives_missing_values` |
| One-way ANOVA = textbook formulas | independent computation | `test_validation.py::test_the_one_way_anova_is_the_textbook_one` |
| Tukey's HSD = studentized range of each difference | independent computation | `test_validation.py::test_tukeys_hsd_is_the_studentized_range_of_each_difference` |
| Dunn of two groups = Kruskal-Wallis | identity | `test_advanced_stats.py::test_dunn_on_two_groups_is_the_kruskal_wallis_test` |
| Kruskal-Wallis + Dunn runs Dunn, not Mann-Whitney | independent computation | `test_advanced_stats.py::test_kruskal_dunn_runs_dunn_not_mann_whitney` |
| Dunnett = `scipy.stats.dunnett`, against the control only | independent computation | `test_advanced_stats.py::test_dunnett_matches_scipy_and_compares_only_with_the_control` |
| Dunnett gives the same result at every redraw | behaviour | `test_advanced_stats.py::test_dunnett_gives_the_same_answer_twice` |

## Corrections for multiple comparisons

Bonferroni, Holm (Holm, *Scand J Stat* 1979) and Benjamini-Hochberg
(Benjamini and Hochberg, *JRSS B* 1995).

| What is checked | How | Test |
|---|---|---|
| The 1995 paper's example: 3 rejections for Bonferroni and Holm, 4 for Benjamini-Hochberg | published data | `test_validation.py::test_the_published_example_rejects_what_the_paper_says` |
| Each correction worked out by hand | independent computation | `test_validation.py::test_each_correction_follows_its_definition` |

## Two-way and repeated-measures ANOVA

Type III sums of squares; repeated-measures ANOVA with the
Greenhouse-Geisser correction (*Psychometrika* 1959).

| What is checked | How | Test |
|---|---|---|
| Balanced design: sums of squares = textbook formulas | independent computation | `test_anova.py::test_balanced_matches_hand_computation` |
| A crossed interaction is detected, parallel effects are not | behaviour | `test_anova.py::test_detects_interaction` |
| Repeated measures: same F as a dummy-coded regression | independent computation | `test_advanced_stats.py::test_rm_anova_matches_a_least_squares_fit` |
| Sphericity: ε = 1 under compound symmetry, and within its bounds | identity | `test_advanced_stats.py::test_sphericity_holds_under_compound_symmetry`, `test_advanced_stats.py::test_sphericity_stays_inside_its_bounds` |

## Outliers

Iterative Grubbs test (α = 0.05); flagged values are never removed.

| What is checked | How | Test |
|---|---|---|
| G = 2.4687 on the NIST/SEMATECH handbook example | published data | `test_advanced_stats.py::test_grubbs_on_the_published_example` |
| Clean data are not flagged | behaviour | `test_advanced_stats.py::test_grubbs_leaves_clean_data_alone` |

## Survival

Kaplan-Meier, Greenwood confidence band on the log(−log) scale, log-rank
test.

| What is checked | How | Test |
|---|---|---|
| The published curve of the 6-MP versus placebo trial (Freireich, *Blood* 1963) | published data | `test_survival.py::test_kaplan_meier_matches_the_published_curve` |
| The published log-rank of the same trial | published data | `test_survival.py::test_logrank_matches_the_published_value` |
| A censored subject counts neither as a death nor as a survivor | behaviour | `test_survival.py::test_censoring_is_neither_death_nor_survival` |

## Contingency tables

Fisher's exact test, Pearson's chi-square with or without Yates'
correction, odds ratio (Woolf) and relative risk (Katz) with their 95 %
CIs, Cramér's V.

| What is checked | How | Test |
|---|---|---|
| Odds ratio 1.83 [1.44; 2.33] and relative risk 1.82 of the aspirin and myocardial infarction trial (Agresti) | published data | `test_contingency.py::test_odds_ratio_and_relative_risk_of_the_aspirin_trial` |
| Chi-square = 30.07 on 2 df, party identification by gender (Agresti) | published data | `test_contingency.py::test_chi_square_of_party_identification_by_gender` |
| p = 0.486 for Fisher's lady tasting tea | published data | `test_contingency.py::test_fisher_on_the_lady_tasting_tea` |
| Yates' correction | independent computation | `test_contingency.py::test_yates_correction_worked_out_by_hand` |
| Cramér's V | independent computation | `test_contingency.py::test_cramers_v_from_its_definition` |

## Curve fitting and comparison

Least squares (linear and nonlinear), confidence band by the delta method;
curves compared with the extra sum-of-squares F test (Motulsky and
Christopoulos, *Fitting models to biological data*, 2004).

| What is checked | How | Test |
|---|---|---|
| An exact straight line is recovered exactly | identity | `test_engine.py::test_linear_fit_is_exact` |
| On straight lines, the F test = analysis of covariance | independent computation | `test_fit_compare.py::test_lines_agree_with_the_analysis_of_covariance`, `test_fit_compare.py::test_three_series_agree_too` |
| A different EC50 is found, a shared slope is not flagged | behaviour | `test_fit_compare.py::test_a_different_ec50_is_found_and_a_shared_slope_is_not_flagged` |
| With no real difference, about 5 % false alarms | simulation | `test_fit_compare.py::test_when_nothing_differs_it_cries_wolf_about_five_percent_of_the_time` |
| Every replicate counts, not just the means | behaviour | `test_fit_compare.py::test_every_replicate_is_compared_not_the_means` |

## Standard curve assays

Concentration read off the fitted curve; 95 % interval combining the
uncertainty of the curve and the scatter of the sample's measurements (the
classical calibration interval: Draper and Smith, *Applied Regression
Analysis*; ISO 11843-2), assuming constant variance.

| What is checked | How | Test |
|---|---|---|
| On a straight line, the textbook calibration interval | independent computation | `test_standard_curve.py::test_a_straight_line_gives_the_textbook_calibration_interval` |
| The curve's share and the measurement's share, each from its formula | independent computation | `test_standard_curve.py::test_where_the_uncertainty_comes_from` |
| On a 4PL, the interval covers the true concentration about 95 times in 100 | simulation | `test_standard_curve.py::test_the_interval_covers_the_true_concentration` |
| The 4PL inverted by hand | independent computation | `test_standard_curve.py::test_the_4pl_is_solved_for_x` |
| Nothing is extrapolated beyond the standards | behaviour | `test_standard_curve.py::test_nothing_is_extrapolated_beyond_the_standards` |

## Area under the curve

Trapezoidal rule; Bailer's standard error (*J Pharmacokinet Biopharm* 1988)
and 95 % CI with Satterthwaite's degrees of freedom.

| What is checked | How | Test |
|---|---|---|
| The area = NumPy's trapezoids | independent computation | `test_auc.py::test_the_area_is_the_trapezoids_of_the_means` |
| Cut exactly where the curve crosses its baseline | independent computation | `test_auc.py::test_crossing_the_baseline_is_cut_where_it_crosses` |
| Standard error = Bailer's formula written out | independent computation | `test_auc.py::test_the_standard_error_is_bailers` |
| The 95 % CI covers the true area about 95 times in 100 | simulation | `test_auc.py::test_the_interval_covers_the_true_area_95_times_in_100` |

## ROC curves

Area under the curve with DeLong's 95 % CI (*Biometrics* 1988, computed
from ranks as Sun and Xu, 2014); Youden cut-off; sensitivity and
specificity with Wilson intervals; DeLong's test for markers measured on
the same subjects.

| What is checked | How | Test |
|---|---|---|
| AUC = 0.893 on Hanley and McNeil's CT ratings (*Radiology* 1982) | published data | `test_roc.py::test_the_published_area_comes_back` |
| AUC = Mann-Whitney U / (m·n) | identity | `test_roc.py::test_the_area_is_the_mann_whitney_statistic` |
| DeLong's placement values = comparing every pair | independent computation | `test_roc.py::test_placement_values_from_ranks_are_delongs` |
| Textbook Wilson interval (8 of 10: 0.490 to 0.943) | published data | `test_roc.py::test_wilson_intervals` |
| CI coverage and level of the paired test | simulation | `test_roc.py::test_the_interval_covers_and_the_paired_test_holds_its_level` |

## Agreement (Bland-Altman)

Bias, 95 % limits of agreement and their CIs (Bland and Altman, *Lancet*
1986; *Stat Methods Med Res* 1999).

| What is checked | How | Test |
|---|---|---|
| Bias −2.1 l/min and SD 38.8 of the peak flow meters of the 1986 paper | published data | `test_bland_altman.py::test_the_published_bias_and_standard_deviation` |
| Published limits −79.7 to 75.5 (at 2 SD) | published data | `test_bland_altman.py::test_the_published_limits_with_their_two_standard_deviations` |
| CI and p of the bias = those of SciPy's paired t | independent computation | `test_bland_altman.py::test_the_bias_interval_and_p_are_those_of_the_paired_t_test` |

## Heat maps

Z-scores by row or by column, Pearson correlation, hierarchical clustering
(average linkage, Euclidean distance, optimal leaf ordering).

| What is checked | How | Test |
|---|---|---|
| Each row centred and scaled | independent computation | `test_heatmap.py::test_each_row_scaled_to_mean_0_and_sd_1` |
| Correlation matrix = pandas' own | independent computation | `test_heatmap.py::test_the_correlation_matrix_is_pearsons` |
| Clustering brings together genes that respond alike | behaviour | `test_heatmap.py::test_clustering_puts_genes_that_answer_alike_together` |

## Methods paragraph

The paragraph describes what was computed: the test that actually ran, the
correction actually applied, the software versions.

| What is checked | How | Test |
|---|---|---|
| The test named is the one that ran | behaviour | `test_methods.py::test_the_test_named_is_the_test_that_ran` |
| The correction named is the one applied | behaviour | `test_methods.py::test_the_correction_named_is_the_one_applied` |
| Both languages have the same sentences | behaviour | `test_methods.py::test_both_languages_have_every_phrase` |

## From the interface to the result

The sneakiest faults come not from the computations but from what the
interface hands them: an event column wiped by a click, a pairing shifted
by one row, a table reloaded the wrong way. These tests drive Plotea as a
user would (import, choose columns, rename, save, close, reopen) and
compare the results with a computation made directly on the original file.

| What is checked | How | Test |
|---|---|---|
| Survival: from the CSV file to the reopened project | independent computation | `workflows/test_workflows.py::test_survival_from_the_file_to_the_reopened_project` |
| Pairing after a subject is deleted | independent computation | `workflows/test_workflows.py::test_paired_subjects_stay_paired_after_a_deletion` |
| Assay driven through the interface | independent computation | `workflows/test_workflows.py::test_standard_curve_assay_through_the_interface` |
| The English interface computes the same | identity | `workflows/test_workflows.py::test_the_english_interface_computes_the_same` |
| The order of the rows does not change the results | identity | `workflows/test_invariance.py::test_the_order_of_the_rows` |
| Saving and reopening does not change the results | identity | `workflows/test_invariance.py::test_a_trip_to_the_disk` |
| Numbers come back from the file to the last bit | identity | `workflows/test_project_roundtrip.py::test_numbers_come_back_to_the_last_bit` |

## Known limits

- Several probability distributions come from SciPy (Student, F,
  chi-square, studentized range, Shapiro-Wilk, Mann-Whitney, Wilcoxon,
  Dunnett): Plotea checks that it calls them with the right quantities, not
  SciPy itself, which has its own tests.
- Nonlinear fits start from initial values estimated from the data (from
  several starts when curves are compared); on ill-conditioned data a local
  minimum remains possible. The R², the residuals and the drawn curve show
  it.
- The assay interval assumes constant variance along the curve; 1/Y²
  weighting is not offered yet.
- The tests do not replace checking an experimental design: Plotea computes
  what it is asked on the data it is given.

A difference between Plotea and another program, or a published result?
Open an issue on [GitHub](https://github.com/Pierokarei/Plotea/issues)
with the data and both results: it will become a test.
