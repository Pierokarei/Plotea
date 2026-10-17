"""A project comes back from its file exactly as it was saved.

Read back with pandas' defaults, a table lost things without a word: groups
named "NA", "None", "null" or "N/A" became missing values and left the
analysis; codes such as "001" became the number 1, so that subjects "01" and
"001" became one; numbers came back a last digit off; and two tables whose
names reduce to the same file name ("Essai 1", "Essai_1") wrote one over the
other. Each test failed on the old reading.
"""
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from plotea.core.dataset import Dataset
from plotea.core.project import Project


def round_trip(tmp_path, *tables) -> Project:
    project = Project()
    for name, frame in tables:
        project.add_dataset(Dataset(name, frame))
    return Project.load(project.save(str(tmp_path / "projet.plotea")))


@pytest.mark.parametrize("name", ["NA", "None", "null", "N/A", "NaN", "nan",
                                  "#N/A", "n/a", "NULL"])
def test_a_group_named_like_a_missing_value_stays(tmp_path, name):
    frame = pd.DataFrame({"Groupe": [name, "Témoin"] * 3,
                          "Valeur": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    back = round_trip(tmp_path, ("T", frame)).datasets[0].df
    assert list(back["Groupe"]) == list(frame["Groupe"])


def test_numbers_come_back_to_the_last_bit(tmp_path):
    values = np.random.default_rng(0).normal(size=5000) * 10.0 ** \
        np.random.default_rng(1).integers(-8, 9, 5000)
    back = round_trip(tmp_path, ("T", pd.DataFrame({"x": values})))
    assert np.array_equal(back.datasets[0].df["x"].to_numpy(), values)


def test_codes_keep_their_leading_zeros(tmp_path):
    frame = pd.DataFrame({"Sujet": ["01", "001", "010", "7"],
                          "Mesure": [1.0, 2.0, 3.0, 4.0]})
    back = round_trip(tmp_path, ("T", frame)).datasets[0].df
    assert list(back["Sujet"]) == ["01", "001", "010", "7"]
    assert back["Sujet"].nunique() == 4          # four subjects, not three


def test_an_empty_cell_stays_missing(tmp_path):
    """An empty group is no group - before saving and after."""
    frame = pd.DataFrame({"Groupe": ["A", None, "B"], "x": [1.0, np.nan, 3.0]})
    back = round_trip(tmp_path, ("T", frame)).datasets[0].df
    assert back["Groupe"].isna().tolist() == [False, True, False]
    assert back["x"].isna().tolist() == [False, True, False]
    assert pd.api.types.is_numeric_dtype(back["x"])


def test_two_tables_with_the_same_file_name_both_come_back(tmp_path):
    one = pd.DataFrame({"x": [1.0, 2.0]})
    two = pd.DataFrame({"x": [10.0, 20.0]})
    back = round_trip(tmp_path, ("Essai 1", one), ("Essai_1", two))
    assert [d.name for d in back.datasets] == ["Essai 1", "Essai_1"]
    assert back.datasets[0].df["x"].tolist() == [1.0, 2.0]
    assert back.datasets[1].df["x"].tolist() == [10.0, 20.0]


def test_a_project_from_an_earlier_version_still_opens(tmp_path):
    """No column kinds, a file named after the table: read as before, with
    the missing-value words no longer swallowed."""
    path = tmp_path / "ancien.plotea"
    meta = {"format": 1, "app": "Plotea", "name": "Ancien",
            "datasets": [{"name": "Table", "file": "data/Table.csv",
                          "source": "", "sheet": "", "notes": ""}],
            "plots": [], "panels": []}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("project.json", json.dumps(meta))
        archive.writestr("data/Table.csv",
                         "Groupe,Valeur\nNA,1.5\nTémoin,2\nNA,\n")
    table = Project.load(str(path)).datasets[0].df
    assert table["Groupe"].tolist() == ["NA", "Témoin", "NA"]
    assert table["Valeur"].tolist()[:2] == [1.5, 2.0]
    assert np.isnan(table["Valeur"].iloc[2])
