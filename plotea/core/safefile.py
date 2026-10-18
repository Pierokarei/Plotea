"""Writing a file so that a crash or a power cut never leaves half of one.

The new content goes to a temporary file beside the target, is forced to
the disk, checked if the caller knows how, and only then takes the
target's place in one step. Until that step the old file is untouched;
after it, the new one is complete. A program that holds the target open
for a moment - an antivirus, OneDrive - is waited for rather than turned
into a failed save.
"""
from __future__ import annotations

import glob
import os
import shutil
import stat
import tempfile
import time

from ..i18n import tr

#: Attempts at moving the finished file into place while another program
#: holds the target, waiting twice as long each time: about six seconds.
REPLACE_TRIES = 8

#: A temporary file older than this was left by a session that crashed.
STALE_SECONDS = 600


def _partial_pattern(target: str) -> str:
    folder, name = os.path.split(os.path.abspath(target))
    return os.path.join(glob.escape(folder),
                        "." + glob.escape(name) + ".*.part")


def sync(path: str):
    """Force a written file's content to the disk."""
    # write access: Windows only flushes a handle opened for writing
    with open(path, "rb+") as handle:
        os.fsync(handle.fileno())


def _sync_folder(folder: str):
    """Make the rename itself durable, where the system allows it."""
    if os.name == "nt":            # NTFS journals it; a folder cannot be opened
        return
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _read_only(path: str) -> bool:
    try:
        return not os.stat(path).st_mode & stat.S_IWRITE
    except OSError:
        return False


def _give_mode(partial: str, target: str):
    """A temporary file is private; the result keeps the target's rights,
    or the usual ones for a new file."""
    try:
        if os.path.exists(target):
            shutil.copymode(target, partial)
        else:
            mask = os.umask(0)
            os.umask(mask)
            os.chmod(partial, 0o666 & ~mask)
    except OSError:
        pass


def replace(partial: str, target: str):
    """Move `partial` onto `target` in one step, waiting while another
    program holds the target open."""
    if os.path.exists(target) and _read_only(target):
        # no point waiting: it will not become writable by itself
        raise PermissionError(tr("Fichier en lecture seule : {path}").format(
            path=target))
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(partial, target)
            break
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05 * 2 ** attempt)
    _sync_folder(os.path.dirname(os.path.abspath(target)))


def clear_stale(target: str, older_than: float = STALE_SECONDS):
    """Remove temporary files a crashed save left beside `target`."""
    now = time.time()
    for path in glob.glob(_partial_pattern(target)):
        try:
            if now - os.path.getmtime(path) > older_than:
                os.remove(path)
        except OSError:
            pass


def write_atomic(target: str, write, verify=None, before_replace=None) -> str:
    """Write `target` through `write(path)`, all or nothing.

    `write` fills a temporary file beside the target; `verify(path)`, if
    given, reads it back and raises when it is not what was meant; then
    `before_replace()` runs - the moment to keep the old version - and the
    temporary file takes the target's place. Any failure leaves the target
    as it was and removes the temporary file.
    """
    folder, name = os.path.split(os.path.abspath(target))
    handle, partial = tempfile.mkstemp(dir=folder, prefix="." + name + ".",
                                       suffix=".part")
    os.close(handle)
    try:
        write(partial)
        sync(partial)
        if verify is not None:
            verify(partial)
        _give_mode(partial, target)
        if before_replace is not None:
            before_replace()
        replace(partial, target)
    except BaseException:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise
    clear_stale(target)
    return target


def write_text(target: str, text: str) -> str:
    """A text file (UTF-8), all or nothing."""
    def write(path):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return write_atomic(target, write)


def copy(source: str, target: str) -> str:
    """Copy a file, all or nothing."""
    return write_atomic(target, lambda path: shutil.copyfile(source, path))
