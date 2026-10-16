# Moving from Prism to Plotea

*[Version française](prism-vers-plotea.md)*

This page is for people who know GraphPad Prism and want to do the same in
Plotea: bring their files over, find each analysis, and know what is still
missing. It describes Plotea 1.2.0.

Plotea is free and open source. It does not copy Prism screen by screen:
most analyses are there, but arranged differently.

## 1. Bringing Prism files over

**“File” ▸ “Import data...”** opens `.pzfx` files. Each data table becomes
a Plotea table, with the plot Prism would have drawn from it:

| Prism table | In Plotea |
|---|---|
| XY (replicates, or mean / SD / N) | curve, mean ± error |
| Column | bars, one per group |
| Grouped | grouped bars (row × column) |
| Survival | Kaplan-Meier curves, with the log-rank |
| Contingency | stacked bars, Fisher's exact test or chi-square |
| Parts of whole, multiple variables, nested | the data only, for now |

- **Values excluded** in Prism (blue italics) are left out, as Prism does,
  and counted in the message at the end of the import.
- Prism's **graphs and analyses** are stored in a format only Prism reads:
  they are not brought over. The data are.
- **`.prism`** files (Prism 10) must first be saved as `.pzfx` from Prism.
- A table can also be copied in Prism and pasted into Plotea: **“Edit” ▸
  “Paste data”** (Ctrl+V).

## 2. The main difference: plain tables, chosen columns

In Prism, a table type is chosen at the start, and the analyses hang from
it. In Plotea, a table is a plain spreadsheet. For each plot, its **type**
and the **columns** it uses are then chosen in the **“Formatting”** panel:

- **“Plot type”**: bars, box plot, survival, ROC…
- **“Data”**: **“Y values”** (what is measured), **“Group by”** (the column
  of groups), **“Subgroup”** (a second factor), **“X axis”** for curves.

Two layouts are accepted: the **long format** (one row per measurement, a
column saying the group — the most flexible) and the **wide format** (one
column per group, as in a Prism Column table). The
[README](../README.en.md#two-data-layouts) describes both.

A plot remembers its settings for each table: you can move from one table
to another and back without losing anything.

## 3. Where each Prism analysis is

Results show in the **“Analyses”** panel at the bottom, in tabs; **“Copy”**
and **“Export CSV”** take out the table on screen.

| In Prism | In Plotea |
|---|---|
| Column statistics | **“Descriptive”** tab |
| t test (unpaired, Welch), Mann-Whitney | **“Statistics”** section, **“Test”**: “Student's t”, “Welch's t”, “Mann-Whitney” |
| Paired t test, Wilcoxon | “Paired t”, “Paired Wilcoxon”, with the **“Pairing”** column (long format) or in wide format |
| One-way ANOVA + Tukey | “ANOVA + Tukey” |
| Kruskal-Wallis + Dunn | “Kruskal-Wallis + Dunn” |
| Comparison with a control (Dunnett) | “Dunnett (vs control)”, then **“Control”** |
| Repeated-measures ANOVA | “Repeated-measures ANOVA” (Greenhouse-Geisser correction) |
| Two-way ANOVA | bars with **“Group by”** and **“Subgroup”**; **“Two-way ANOVA”** tab |
| Multiple comparisons correction | **“Correction”**: Bonferroni, Holm, Benjamini-Hochberg (FDR) |
| Outliers (Grubbs) | **“Outliers”** tab |
| Contingency table (Fisher, chi-square) | “Contingency (counts)” type; odds ratio, relative risk and Cramér's V in the **“Effects”** tab |
| Survival (Kaplan-Meier, log-rank) | “Survival (Kaplan-Meier)” type; median survival under **“Descriptive”** |
| Nonlinear regression | **“Curve fitting”** section, **“Model”**; parameters, R² and errors in the **“Fits”** tab |
| Compare fits (F test) | **“Compare”**: “One curve for all series?” or a parameter (EC50…) |
| Interpolate a standard curve | **“Quantify unknowns (rows without X)”**; **“Assay”** tab |
| Area under curve | **“Area under the curve”** section; **“Areas”** tab |
| ROC curve | “ROC curve (diagnosis)” type; **“ROC”** tab |
| Bland-Altman | “Bland-Altman (agreement)” type; **“Effects”** tab |
| Correlation | “Linear (y = ax + b)” fit: Pearson's r and the slope's P value under **“Fits”**; or a heat map of the correlations between columns |
| Normalize, remove a baseline, transform | **“Data” ▸ “Transform data...”** |
| Before-after graph | “Paired before-after” type |
| Heat map | “Heat map” type |

In **“Auto”** mode, Plotea chooses the test from normality (Shapiro-Wilk)
and equality of variances (Levene), and says which one it ran. If your
protocol sets the test in advance, choose it explicitly.

What Prism does not have: the **“Methods”** tab writes the paragraph to
paste into the paper, in English or French, from what was actually
computed.

## 4. Formatting and exporting

- **“Style” ▸ “Journal theme”**: Nature, Science, Cell, PNAS… font, column
  width and palette follow each journal's guidelines.
- **“File” ▸ “Export figure...”**: SVG, PDF and EPS with text editable in
  Illustrator or Inkscape; PNG, TIFF and JPEG up to 1200 dpi.
- **“Plot” ▸ “New composite figure”**: several plots on one figure,
  lettered A, B, C.
- **“Broken Y axis”** (**“Axes”** section) for small and very large values
  on one plot.
- **“Style” ▸ “Save current style...”** to reuse a look.

## 5. What Plotea does not do yet

So that you do not find out halfway through an analysis:

- **Parts of whole**, **Multiple variables** and **Nested** tables are
  imported but not plotted yet;
- Column or Grouped tables **entered as mean / SD / N** give bars without
  error bars (only curves draw them from summaries);
- no **Welch ANOVA** or **Brown-Forsythe**, no **Friedman** test, no
  **Šidák** correction;
- no **mixed model** for incomplete repeated measures;
- no **ROUT** method for outliers (Grubbs only);
- no **Cox regression**;
- no **five-parameter logistic (5PL)** model;
- no **multiple t tests** (one test per row);
- no **power analysis**;
- no **Spearman** coefficient shown on its own.

Missing something else, or is one of these essential to you?
[Say so](https://github.com/Pierokarei/Plotea/issues/new/choose): that is
what decides what comes next.

## 6. Getting started

**“File” ▸ “Example datasets”** opens a ready example for each plot type:
cell viability, dose-response, survival, contingency, ELISA assay, glucose
tolerance, biomarkers (ROC)… Starting from the example closest to your data
is often the quickest way.
