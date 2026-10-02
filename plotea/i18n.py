"""Interface language.

French is the source language: every text in the code is written in French and
passes through tr(), which hands it back untouched when the interface is in
French and looks it up in a catalogue otherwise. Two consequences follow, and
both are deliberate:

- the French interface is the code itself, so no translation work - a missing
  entry, a typo in a catalogue, a catalogue that fails to load - can change a
  single French word;
- a text with no translation yet shows in French rather than as an empty label
  or an internal key, so an incomplete catalogue degrades instead of breaking.

Catalogues are plain JSON in plotea/locales, keyed by the French text, so that a
contributor can translate without reading any Python. Kept free of Qt: the
engine uses it too.
"""
from __future__ import annotations

import json
import os

#: Each language under its own name: someone who cannot read the current
#: interface must still recognise theirs in the menu.
LANGUAGES = {"fr": "Français", "en": "English"}
SOURCE = "fr"

_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
_current = SOURCE
_catalogue: dict[str, str] = {}


def catalogue_path(language: str) -> str:
    return os.path.join(_FOLDER, f"{language}.json")


def load_catalogue(language: str) -> dict[str, str]:
    """The translations of one language; empty for the source language."""
    if language == SOURCE:
        return {}
    with open(catalogue_path(language), encoding="utf-8") as handle:
        data = json.load(handle)
    return {str(k): str(v) for k, v in data.items() if v}


def set_language(language: str) -> str:
    """Switch the interface language; returns the one actually in effect.

    An unknown language, or a catalogue that cannot be read, leaves the
    interface in French rather than half in something else.
    """
    global _current, _catalogue
    if language not in LANGUAGES:
        language = SOURCE
    try:
        catalogue = load_catalogue(language)
    except (OSError, ValueError):
        language, catalogue = SOURCE, {}
    _current, _catalogue = language, catalogue
    return language


def language() -> str:
    return _current


def tr(text: str) -> str:
    """The text in the interface language, or the French text itself.

    Named tr rather than the customary _ because this code base already uses
    _ as a throwaway name (``path, _ = QFileDialog...``), and the two would
    silently shadow each other inside the same function.
    """
    if _current == SOURCE or not text:
        return text
    return _catalogue.get(text, text)


def entries() -> int:
    """How many translations are loaded, for the packaged smoke test."""
    return len(_catalogue)
