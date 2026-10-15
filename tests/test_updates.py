"""Offering a newer version: asked first, once a day at most, never in the way.

No test reaches the network: the question to GitHub is replaced by what
GitHub answers - releases, nothing, or no answer at all.
"""
import io
import json

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from plotea.core import updates

RELEASES = [
    {"tag_name": "v1.3.0", "draft": True, "body": "",
     "html_url": "https://example.org/draft"},
    {"tag_name": "v1.2.0", "draft": False, "prerelease": True,
     "html_url": "https://github.com/Pierokarei/Plotea/releases/tag/v1.2.0",
     "body": "### Corrections qui peuvent changer vos résultats\n- Dunn"},
    {"tag_name": "v1.1.0", "draft": False, "body": "",
     "html_url": "https://github.com/Pierokarei/Plotea/releases/tag/v1.1.0"},
    {"tag_name": "nightly", "draft": False, "body": ""},
]


# --------------------------------------------------------------------------
# Which release is newer
# --------------------------------------------------------------------------
def test_version_numbers_are_compared_as_numbers():
    assert updates.version_key("v1.10.0") > updates.version_key("1.9.3")
    assert updates.version_key("1.2.0") == (1, 2, 0)
    assert updates.version_key("nightly") is None
    assert updates.version_key("1.2") is None


def test_the_newest_published_release_above_ours():
    found = updates.newest(RELEASES, "1.1.0")
    assert found.version == "1.2.0"               # not the draft 1.3.0
    assert found.url.endswith("/v1.2.0")
    assert found.changes_results
    assert updates.newest(RELEASES, "1.2.0") is None
    assert updates.newest(RELEASES, "2.0.0") is None


def test_fixes_that_change_results_are_seen_in_either_language():
    english = [{"tag_name": "v9.0.0", "body":
                "## What's new\n### Fixes that may change your results\n"}]
    plain = [{"tag_name": "v9.0.0", "body": "### Other fixes\n"}]
    assert updates.newest(english, "1.0.0").changes_results
    assert not updates.newest(plain, "1.0.0").changes_results
    assert updates.newest(plain, "1.0.0").url == updates.DOWNLOADS_URL


def test_strange_answers_are_not_trusted():
    assert updates.newest([None, "v9.9.9", {"tag_name": None}], "1.0.0") \
        is None


def test_the_question_sends_nothing_but_itself(monkeypatch):
    seen = {}

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(request, timeout, context):
        seen.update(url=request.full_url, data=request.data,
                    method=request.get_method(),
                    agent=request.get_header("User-agent"),
                    context=context)
        return Answer(json.dumps(RELEASES).encode())

    monkeypatch.setattr(updates.urllib.request, "urlopen", urlopen)
    assert updates.fetch() == RELEASES
    assert seen["url"] == updates.RELEASES_URL
    assert seen["method"] == "GET" and seen["data"] is None
    assert seen["agent"].startswith("Plotea/")
    assert seen["context"].verify_mode.name == "CERT_REQUIRED"


# --------------------------------------------------------------------------
# In the window
# --------------------------------------------------------------------------
@pytest.fixture
def notifier(window, monkeypatch):
    """The window's notifier, asking a fake GitHub, on the same thread."""
    memory = window.memory
    for key in ("updateChecks", "lastUpdateCheck", "skippedVersion"):
        memory.settings.remove(key)
    notifier = window.updates
    notifier.current = "1.1.0"
    notifier.asked = 0

    def fetch():
        notifier.asked += 1
        answer = notifier.answer
        if isinstance(answer, Exception):
            raise answer
        return answer
    notifier.fetch = fetch
    notifier.answer = RELEASES
    notifier._start = lambda job: job()
    said = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: said.append(a[-1])))
    notifier.said = said
    return notifier


def shown(notifier):
    QApplication.processEvents()
    banner = notifier.banner
    return banner.isVisibleTo(banner.parentWidget()), banner.text.text(), \
        list(banner.buttons)


def test_a_new_window_asks_nothing(notifier):
    """The window alone never asks: Plotea's start does, after the
    self-test has gone - so neither the tests nor it reach the network."""
    assert notifier.asked == 0
    assert not shown(notifier)[0]


def test_the_first_start_asks_before_looking(notifier):
    notifier.on_startup()
    visible, text, buttons = shown(notifier)
    assert visible and "GitHub" in text and "rien d'autre" in text
    assert buttons == ["yes", "no"]
    assert notifier.asked == 0                      # not before a yes


def test_saying_yes_looks_at_once_and_says_what_it_found(notifier):
    notifier.on_startup()
    notifier.banner.buttons["yes"].click()
    assert notifier.memory.update_checks() is True
    assert notifier.window.a_auto_updates.isChecked()
    assert notifier.asked == 1
    visible, text, buttons = shown(notifier)
    assert visible and "Plotea 1.2.0 est disponible (vous avez 1.1.0)" in text
    assert "peuvent changer vos résultats" in text
    assert buttons == ["get", "later", "skip"]


def test_saying_no_is_kept_and_asks_nothing(notifier):
    notifier.on_startup()
    notifier.banner.buttons["no"].click()
    assert notifier.memory.update_checks() is False
    assert not shown(notifier)[0] and notifier.asked == 0
    notifier.on_startup()                           # the next start
    assert not shown(notifier)[0] and notifier.asked == 0
    assert "menu Aide" in notifier.window.statusBar().currentMessage()


def test_once_a_day_at_most(notifier):
    notifier.set_allowed(True)
    notifier.memory.remember_update_check(1_000_000.0)
    notifier.on_startup(now=1_000_000.0 + 3600)
    assert notifier.asked == 0
    notifier.on_startup(now=1_000_000.0 + 25 * 3600)
    assert notifier.asked == 1


def test_a_skipped_version_is_not_offered_again(notifier):
    notifier.set_allowed(True)
    notifier.check(manual=False)
    notifier.banner.buttons["skip"].click()
    assert notifier.memory.skipped_version() == "1.2.0"
    notifier.check(manual=False)
    assert not shown(notifier)[0]
    notifier.check(manual=True)                     # asked for: shown
    assert shown(notifier)[0]


def test_no_answer_says_nothing_unless_asked(notifier):
    notifier.answer = OSError("hors ligne")
    notifier.check(manual=False)
    assert not shown(notifier)[0] and not notifier.said
    notifier.check(manual=True)
    assert notifier.said and "GitHub" in notifier.said[0]


def test_asking_when_up_to_date_says_so(notifier):
    notifier.current = "1.2.0"
    notifier.check(manual=True)
    assert notifier.said == ["Plotea 1.2.0 est la version la plus récente."]
    assert not shown(notifier)[0]


def test_the_help_menu_switches_it(notifier):
    action = notifier.window.a_auto_updates
    action.trigger()
    assert notifier.memory.update_checks() is True
    action.trigger()
    assert notifier.memory.update_checks() is False
    notifier.window.a_check_updates.trigger()
    assert notifier.asked == 1                      # asking is always there


def test_the_self_test_never_asks(monkeypatch, capsys):
    from plotea import app as app_mod
    from plotea.ui.updates import UpdateNotifier

    calls = []
    monkeypatch.setattr(UpdateNotifier, "on_startup",
                        lambda self, now=None: calls.append(1))
    monkeypatch.setenv("PLOTEA_SELFTEST", "1")
    assert app_mod.main(["plotea"]) == 0
    assert calls == []
