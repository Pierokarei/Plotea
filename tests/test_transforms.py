"""Data transforms: values, edge cases and the dialog that drives them."""

import numpy as np
import pandas as pd


from plotea.core import demo, transforms  # noqa: E402
from plotea.ui.dialogs import TransformDialog  # noqa: E402


viab = demo.viability()
P = transforms.Params


def test_percent_long():
    out, msg = transforms.apply(
        "Pourcentage du contrôle", viab.df,
        P(columns=["Viabilité"], group="Traitement", control="Contrôle"))
    assert not msg, msg
    ref = viab.df[viab.df["Traitement"] == "Contrôle"]["Viabilité"].mean()
    assert abs(out[out["Traitement"] == "Contrôle"]["Viabilité"].mean()
               - 100.0) < 1e-9
    expected = viab.df["Viabilité"].iloc[0] / ref * 100
    assert abs(out["Viabilité"].iloc[0] - expected) < 1e-9
    # the source table is untouched
    assert viab.df["Viabilité"].iloc[0] != out["Viabilité"].iloc[0]


def test_percent_missing_control():
    out, msg = transforms.apply(
        "Pourcentage du contrôle", viab.df,
        P(columns=["Viabilité"], group="Traitement", control="Inexistant"))
    assert msg and "introuvable" in msg, msg
    assert out["Viabilité"].equals(viab.df["Viabilité"])


def test_normalize():
    out, msg = transforms.apply("Normaliser de 0 a 100", viab.df,
                                P(columns=["Viabilité"]))
    assert not msg
    assert abs(out["Viabilité"].min()) < 1e-9
    assert abs(out["Viabilité"].max() - 100.0) < 1e-9


def test_logs():
    frame = pd.DataFrame({"x": [1.0, 10.0, 100.0, 0.0, -5.0]})
    out, msg = transforms.apply("Logarithme décimal", frame, P(columns=["x"]))
    assert "2 valeur" in msg, msg
    assert list(out["x"][:3]) == [0.0, 1.0, 2.0], list(out["x"][:3])
    assert out["x"][3:].isna().all()

    out, _ = transforms.apply("Logarithme base 2",
                              pd.DataFrame({"x": [1.0, 2.0, 8.0]}),
                              P(columns=["x"]))
    assert list(out["x"]) == [0.0, 1.0, 3.0], list(out["x"])


def test_zscores():
    out, _ = transforms.apply("Score z", viab.df,
                              P(columns=["Viabilité"], group="Traitement"))
    per_group = out.groupby("Traitement")["Viabilité"]
    assert all(abs(m) < 1e-9 for m in per_group.mean())
    assert all(abs(s - 1.0) < 1e-9 for s in per_group.std())


def test_baseline():
    frame = pd.DataFrame({"g": ["A", "A", "A", "B", "B", "B"],
                          "v": [5.0, 7.0, 9.0, 20.0, 22.0, 26.0]})
    out, _ = transforms.apply("Soustraire la ligne de base", frame,
                              P(columns=["v"], group="g"))
    assert list(out["v"]) == [0.0, 2.0, 4.0, 0.0, 2.0, 6.0], list(out["v"])


def test_ratio():
    frame = pd.DataFrame({"a": [10.0, 20.0, 30.0], "ref": [2.0, 4.0, 0.0]})
    out, msg = transforms.apply("Rapport a une colonne", frame,
                                P(columns=["a"], reference="ref"))
    assert not msg
    assert list(out["a"][:2]) == [5.0, 5.0], list(out["a"][:2])
    assert np.isnan(out["a"].iloc[2]), "division par zero -> NaN"


def test_aggregate():
    out, msg = transforms.apply("Moyenne des réplicats", viab.df,
                                P(columns=["Viabilité"], group="Traitement"))
    assert not msg, msg
    assert len(out) == 4, len(out)
    assert "Viabilité moyenne" in out.columns and "Viabilité SEM" in out.columns
    ctrl = out[out["Traitement"] == "Contrôle"].iloc[0]
    source = viab.df[viab.df["Traitement"] == "Contrôle"]["Viabilité"]
    assert abs(ctrl["Viabilité moyenne"] - source.mean()) < 1e-9
    assert abs(ctrl["Viabilité SEM"]
               - source.std(ddof=1) / np.sqrt(len(source))) < 1e-9
    assert ctrl["Viabilité n"] == 12


def test_dialog_drives_transforms():
    dlg = TransformDialog(viab)
    assert dlg.result_df is not None
    dlg.cmb_transform.setCurrentText("Pourcentage du contrôle")
    dlg.lst_cols.set_checked(["Viabilité"])
    dlg.cmb_group.setCurrentText("Traitement")
    dlg.cmb_control.setCurrentText("Contrôle")
    dlg.refresh()
    assert abs(dlg.result_df[dlg.result_df["Traitement"] == "Contrôle"]
               ["Viabilité"].mean() - 100.0) < 1e-9
    assert "[% ctrl]" in dlg.txt_name.text(), dlg.txt_name.text()
    assert dlg.preview.rowCount() > 0


def test_dialog_offers_every_transform():
    dlg = TransformDialog(viab)
    assert dlg.cmb_transform.count() == len(transforms.TRANSFORMS)
    for i in range(dlg.cmb_transform.count()):
        dlg.cmb_transform.setCurrentIndex(i)
        dlg.lst_cols.set_checked(["Viabilité"])
        dlg.refresh()          # must never raise, whatever the parameters
