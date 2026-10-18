"""Earlier versions of a project, kept each time its file is replaced.

Undo forgets everything when Plotea closes, and the backup copy only
covers a session that ended badly. Neither gives back last Tuesday's
analysis once the file has been saved over. So every save first sets the
file it is about to replace aside, in Plotea's own folder - not beside the
project, which would clutter the user's folders and travel with a shared
file, earlier data included.

Versions are filed under the project's identifier, which the file carries:
renamed or moved, a project keeps its history. What is kept: the last 20
saves, then one a day for 30 days, within 500 MB per project.
"""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import datetime, timedelta

from . import safefile

FOLDER = "historique"
KEEP_RECENT = 20
KEEP_DAYS = 30
MAX_BYTES = 500 * 1024 * 1024
STAMP = "%Y%m%d-%H%M%S"


def root() -> str:
    from .project import config_dir
    return os.path.join(config_dir(), FOLDER)


def folder(project_id: str) -> str:
    return os.path.join(root(), _safe(project_id))


def _safe(project_id: str) -> str:
    keep = "".join(c for c in str(project_id) if c.isalnum() or c in "-_")
    return keep[:64] or "projet"


def _digest(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def _meta(path: str) -> dict:
    """project.json of an archive, or {} when it cannot be read."""
    try:
        with zipfile.ZipFile(path) as archive:
            return json.loads(archive.read("project.json").decode("utf-8"))
    except Exception:
        return {}


def archive(path: str, project_id: str) -> str | None:
    """Set aside the file at `path` before it is replaced.

    Filed under the identifier the file itself carries - it may belong to
    another project than the one being saved over it - or, for a file from
    before identifiers, under `project_id`. Nothing is kept twice: a file
    saved again unchanged is already there. Returns the copy, or None.
    """
    if not os.path.isfile(path):
        return None
    meta = _meta(path)
    owner = meta.get("id") or project_id
    target_folder = folder(owner)
    os.makedirs(target_folder, exist_ok=True)
    digest = _digest(path)
    for entry in versions(owner):
        if entry.get("sha256") == digest:
            return None
    saved = datetime.fromtimestamp(os.path.getmtime(path))
    stem = f"{saved.strftime(STAMP)}-{digest[:8]}"
    copy = os.path.join(target_folder, stem + ".plotea")
    safefile.copy(path, copy)
    datasets = meta.get("datasets", [])
    safefile.write_text(os.path.join(target_folder, stem + ".json"),
                        json.dumps({
                            "saved": saved.isoformat(),      # two saves may share a second
                            "origin": os.path.abspath(path),
                            "name": meta.get("name", ""),
                            "tables": len(datasets),
                            "plots": len(meta.get("plots", [])),
                            "size": os.path.getsize(copy),
                            "sha256": digest,
                        }, ensure_ascii=False, indent=1))
    prune(owner)
    return copy


def versions(project_id: str) -> list[dict]:
    """The versions kept for a project, newest first."""
    where = folder(project_id)
    if not os.path.isdir(where):
        return []
    out = []
    for name in os.listdir(where):
        if not name.endswith(".plotea"):
            continue
        path = os.path.join(where, name)
        info = {}
        try:
            with open(path[:-len(".plotea")] + ".json",
                      encoding="utf-8") as handle:
                info = json.load(handle)
        except (OSError, ValueError):
            pass                       # the archive alone is enough
        try:
            saved = datetime.fromisoformat(info["saved"])
        except (KeyError, ValueError, TypeError):
            saved = datetime.fromtimestamp(os.path.getmtime(path))
        info.update(path=path, saved=saved)
        info.setdefault("size", os.path.getsize(path))
        out.append(info)
    out.sort(key=lambda v: (v["saved"], v["path"]), reverse=True)
    return out


def versions_of_file(path: str) -> list[dict]:
    """Versions set aside from the file at `path`, whatever their project:
    what is left when the file itself no longer opens."""
    if not os.path.isdir(root()):
        return []
    wanted = os.path.normcase(os.path.abspath(path))
    found = []
    for project_id in os.listdir(root()):
        for entry in versions(project_id):
            origin = entry.get("origin", "")
            if origin and os.path.normcase(origin) == wanted:
                found.append(entry)
    found.sort(key=lambda v: (v["saved"], v["path"]), reverse=True)
    return found


def _forget(entry: dict):
    for path in (entry["path"], entry["path"][:-len(".plotea")] + ".json"):
        try:
            os.remove(path)
        except OSError:
            pass


def prune(project_id: str, now: datetime | None = None):
    """Keep the last saves, one a day for a month, within the size cap."""
    now = now or datetime.now()
    entries = versions(project_id)
    kept, days = [], set()
    for rank, entry in enumerate(entries):
        day = entry["saved"].date()
        if rank < KEEP_RECENT:
            kept.append(entry)
            days.add(day)
        elif now - entry["saved"] <= timedelta(days=KEEP_DAYS) \
                and day not in days:
            kept.append(entry)            # the day's last save
            days.add(day)
        else:
            _forget(entry)
    total = sum(entry.get("size", 0) for entry in kept)
    while total > MAX_BYTES and len(kept) > 1:
        oldest = kept.pop()
        total -= oldest.get("size", 0)
        _forget(oldest)
