"""Is there a newer Plotea? One question to GitHub, when people agree to it.

Nothing is sent but the request itself - the list of published releases of
the project, which anyone can read - and nothing is ever downloaded or
installed: a newer version is offered, with a link to its page. Drafts are
not versions; pre-releases are, since every version is one while Plotea is
being tried out.

A release whose notes carry the section on fixes that may change results
is said to be one: people who computed with the version before should know.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from dataclasses import dataclass

from .. import __version__

#: Where the releases are listed (GitHub's API, readable without account).
RELEASES_URL = "https://api.github.com/repos/Pierokarei/Plotea/releases"
#: The page people are sent to when they ask for the downloads.
DOWNLOADS_URL = "https://github.com/Pierokarei/Plotea/releases"

#: Headings of the notes' section on fixes that change results, in both
#: languages (.github/changes/<version>.md).
RESULT_FIXES = ("Corrections qui peuvent changer vos résultats",
                "Fixes that may change your results")


@dataclass
class Release:
    version: str
    url: str
    changes_results: bool = False


def version_key(text: str) -> tuple | None:
    """(1, 2, 0) for "v1.2.0" or "1.2.0"; None for anything else."""
    found = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    return tuple(int(part) for part in found.groups()) if found else None


def newest(releases: list, current: str = __version__) -> Release | None:
    """The most recent published release above `current`, if any.

    `releases` is what GitHub returns; entries that are drafts, or whose
    tag is not a version, are ignored rather than trusted.
    """
    mine = version_key(current)
    best, best_key = None, mine
    for entry in releases:
        if not isinstance(entry, dict) or entry.get("draft"):
            continue
        key = version_key(str(entry.get("tag_name", "")))
        if key is None or (best_key is not None and key <= best_key):
            continue
        body = str(entry.get("body") or "")
        best, best_key = Release(
            version=".".join(map(str, key)),
            url=str(entry.get("html_url") or DOWNLOADS_URL),
            changes_results=any(h in body for h in RESULT_FIXES)), key
    return best


def _context() -> ssl.SSLContext:
    """Certificates from certifi when there: a packaged build carries no
    access to the system's, on macOS in particular."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch(timeout: float = 8.0) -> list:
    """The releases as GitHub lists them; raises on any network trouble."""
    request = urllib.request.Request(RELEASES_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Plotea/{__version__}"})
    with urllib.request.urlopen(request, timeout=timeout,
                                context=_context()) as answer:
        data = json.loads(answer.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    return data
