import json
from typing import Any

import pytest
from invoke.context import Context

from tasks.github import (
    REPO,
    SETTINGS_DIR,
    GhCli,
    merge_if_ready,
    merge_when_ready,
    required_checks,
)
from tasks.shell import Shell
from tests.fixtures.gh import FakeGh, MakeFakeGh

CHECK = "Lint, types and tests"
SHA = "abc123"


def _pull(state: str = "open", labels: tuple[str, ...] = ("automerge",)) -> str:
    return json.dumps(
        {
            "state": state,
            "labels": [{"name": name} for name in labels],
            "head": {"sha": SHA},
        }
    )


def _runs(*runs: dict[str, Any]) -> str:
    return json.dumps({"check_runs": list(runs)})


def _gh(fake_gh: MakeFakeGh, pull: str, runs: str = _runs()) -> FakeGh:
    return fake_gh(
        {
            f"GET {REPO}/pulls/7": {"stdout": pull},
            f"GET {REPO}/commits/{SHA}/check-runs": {"stdout": runs},
        }
    )


def _merge(gh: FakeGh) -> tuple[bool, list[str]]:
    messages: list[str] = []
    merged = merge_when_ready(
        GhCli(Shell(Context()), str(gh.path)), 7, [CHECK], messages.append
    )
    return merged, messages


def _methods(gh: FakeGh) -> list[str]:
    return [call["args"][2] for call in gh.calls()]


def test_required_checks_come_from_the_ruleset() -> None:
    assert required_checks(SETTINGS_DIR) == [CHECK]


def test_merges_when_labelled_and_the_check_passed(fake_gh: MakeFakeGh) -> None:
    passed = {"name": CHECK, "status": "completed", "conclusion": "success"}
    other = {"name": "Merge when ready", "status": "in_progress", "conclusion": None}
    gh = _gh(fake_gh, _pull(), _runs(other, passed))

    merged, messages = _merge(gh)

    assert merged
    last = gh.calls()[-1]
    assert last["args"][2:4] == ["PUT", f"{REPO}/pulls/7/merge"]
    assert json.loads(last["stdin"]) == {"merge_method": "rebase", "sha": SHA}
    assert messages == ["Merged #7."]


def test_leaves_closed_pull_requests(fake_gh: MakeFakeGh) -> None:
    gh = _gh(fake_gh, _pull(state="closed"))

    merged, messages = _merge(gh)

    assert not merged
    assert _methods(gh) == ["GET"]
    assert messages == ["#7 is closed; nothing to do."]


def test_leaves_pull_requests_without_the_label(fake_gh: MakeFakeGh) -> None:
    gh = _gh(fake_gh, _pull(labels=("docs",)))

    merged, messages = _merge(gh)

    assert not merged
    assert messages == ["#7 has no automerge label; leaving it for review."]


@pytest.mark.parametrize(
    ("runs", "state"),
    [
        ([], "missing"),
        ([{"name": CHECK, "status": "in_progress", "conclusion": None}], "in_progress"),
        ([{"name": CHECK, "status": "completed", "conclusion": "failure"}], "failure"),
    ],
)
def test_waits_until_the_check_passes(
    fake_gh: MakeFakeGh, runs: list[dict[str, Any]], state: str
) -> None:
    gh = _gh(fake_gh, _pull(), _runs(*runs))

    merged, messages = _merge(gh)

    assert not merged
    assert "PUT" not in _methods(gh)
    assert messages == [f"#7 is waiting for {CHECK!r} ({state})."]


def test_task_merges_the_given_pr(
    fake_gh: MakeFakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    passed = {"name": CHECK, "status": "completed", "conclusion": "success"}
    gh = _gh(fake_gh, _pull(), _runs(passed))

    merge_if_ready(Context(), pr="7", gh=str(gh.path))

    assert _methods(gh)[-1] == "PUT"
    assert "Merged #7." in capsys.readouterr().out
