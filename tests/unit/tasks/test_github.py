import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from invoke.context import Context

from tasks.github import (
    REPO,
    SETTINGS_DIR,
    DryRunGh,
    GhCli,
    GhError,
    apply,
    apply_ruleset,
    apply_settings,
)
from tests.fixtures.gh import MakeFakeGh

PAID_PLAN_ONLY = {
    "code": 1,
    "stderr": "gh: Upgrade to GitHub Pro or make this repository public "
    "to enable this feature. (HTTP 403)",
}
RULESETS = f"GET {REPO}/rulesets"


def _ruleset() -> dict[str, Any]:
    ruleset: dict[str, Any] = json.loads(
        (SETTINGS_DIR / "main-ruleset.json").read_text()
    )
    return ruleset


def test_settings_files_are_valid_json() -> None:
    for path in SETTINGS_DIR.glob("*.json"):
        assert isinstance(json.loads(path.read_text()), dict), path


def test_applies_repo_settings_and_skips_the_paid_ruleset(
    fake_gh: MakeFakeGh,
) -> None:
    gh = fake_gh({RULESETS: PAID_PLAN_ONLY})
    messages: list[str] = []

    apply(GhCli(str(gh.path)), SETTINGS_DIR, messages.append)

    calls = gh.calls()
    assert [call["args"][2:4] for call in calls] == [
        ["PATCH", REPO],
        ["PUT", f"{REPO}/vulnerability-alerts"],
        ["PUT", f"{REPO}/automated-security-fixes"],
        ["GET", f"{REPO}/rulesets"],
    ]
    sent = json.loads(calls[0]["stdin"])
    assert sent["allow_rebase_merge"] is True
    assert sent["allow_merge_commit"] is False
    assert "security" not in sent
    assert "paid plan" in messages[-1]


def test_creates_the_ruleset_when_missing(fake_gh: MakeFakeGh) -> None:
    gh = fake_gh({RULESETS: {"stdout": "[]"}})
    messages: list[str] = []

    apply_ruleset(GhCli(str(gh.path)), _ruleset(), messages.append)

    last = gh.calls()[-1]
    assert last["args"][2:4] == ["POST", f"{REPO}/rulesets"]
    assert json.loads(last["stdin"])["name"] == "protect-main"
    assert messages == ["Created the protect-main ruleset."]


def test_updates_the_ruleset_when_present(fake_gh: MakeFakeGh) -> None:
    existing = [{"id": 7, "name": "other"}, {"id": 42, "name": "protect-main"}]
    gh = fake_gh({RULESETS: {"stdout": json.dumps(existing)}})
    messages: list[str] = []

    apply_ruleset(GhCli(str(gh.path)), _ruleset(), messages.append)

    assert gh.calls()[-1]["args"][2:4] == ["PUT", f"{REPO}/rulesets/42"]
    assert messages == ["Updated the protect-main ruleset."]


def test_other_errors_are_raised(fake_gh: MakeFakeGh) -> None:
    gh = fake_gh({RULESETS: {"code": 1, "stderr": "gh: Not Found (HTTP 404)"}})

    with pytest.raises(GhError) as raised:
        apply_ruleset(GhCli(str(gh.path)), _ruleset(), print)

    assert raised.value.status == HTTPStatus.NOT_FOUND


def test_errors_without_a_status_are_raised(fake_gh: MakeFakeGh) -> None:
    gh = fake_gh({RULESETS: {"code": 1, "stderr": "gh: not logged in"}})

    with pytest.raises(GhError) as raised:
        apply_ruleset(GhCli(str(gh.path)), _ruleset(), print)

    assert raised.value.status is None


def test_dry_run_makes_no_calls(capsys: pytest.CaptureFixture[str]) -> None:
    apply(DryRunGh(print), SETTINGS_DIR, print)

    out = capsys.readouterr().out
    assert f"[dry run] PATCH {REPO} " in out
    assert f"[dry run] POST {REPO}/rulesets " in out


def test_task_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    apply_settings(Context(), dry_run=True)

    out = capsys.readouterr().out
    assert "[dry run] PATCH" in out
    assert "Created" not in out


def test_task_uses_the_given_gh(
    fake_gh: MakeFakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = fake_gh({RULESETS: PAID_PLAN_ONLY})

    apply_settings(Context(), gh=str(gh.path))

    assert [call["args"][2] for call in gh.calls()] == ["PATCH", "PUT", "PUT", "GET"]
    assert "Skipped the protect-main ruleset" in capsys.readouterr().out


def test_settings_dir_is_in_the_repo() -> None:
    assert Path(__file__).parents[3] / ".github" / "settings" == SETTINGS_DIR


def test_leaves_security_settings_alone_when_not_requested(
    fake_gh: MakeFakeGh, tmp_path: Path
) -> None:
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    (settings_dir / "repo.json").write_text('{"has_wiki": false}')
    (settings_dir / "main-ruleset.json").write_text(json.dumps(_ruleset()))
    gh = fake_gh({RULESETS: PAID_PLAN_ONLY})

    apply(GhCli(str(gh.path)), settings_dir, print)

    assert [call["args"][2] for call in gh.calls()] == ["PATCH", "GET"]
