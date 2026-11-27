"""Apply the repository settings in `.github/settings` to GitHub."""

import json
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol

from invoke.context import Context
from invoke.tasks import task

from tasks.shell import CommandError, Shell

SETTINGS_DIR = Path(__file__).parents[1] / ".github" / "settings"

# `gh api` fills {owner} and {repo} from the current git remote, or from
# GH_REPO when set (as in GitHub Actions).
REPO = "repos/{owner}/{repo}"

AUTOMERGE_LABEL = "automerge"

Echo = Callable[[str], None]


class GhError(RuntimeError):
    """A `gh api` call failed."""

    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status


class Gh(Protocol):
    """The one GitHub API call these tasks need."""

    def api(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Call the GitHub API and return the decoded JSON response."""


@dataclass(frozen=True, slots=True)
class GhCli:
    """Calls the GitHub API through the `gh` command line tool."""

    shell: Shell
    executable: str = "gh"

    def api(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Run `gh api` and return its JSON output, or None when it is empty.

        Raises:
            GhError: `gh` exited with an error, with the HTTP status if known.
        """
        args = [self.executable, "api", "--method", method, path]
        with tempfile.TemporaryDirectory() as tmp:
            if body is not None:
                body_file = Path(tmp) / "body.json"
                body_file.write_text(json.dumps(body))
                args += ["--input", str(body_file)]
            try:
                output = self.shell.run(args)
            except CommandError as error:
                match = re.search(r"\(HTTP (\d+)\)", error.stderr)
                status = int(match.group(1)) if match else None
                raise GhError(status, error.stderr.strip()) from None
        return json.loads(output) if output.strip() else None


@dataclass(frozen=True, slots=True)
class DryRunGh:
    """Prints each call instead of making it."""

    echo: Echo

    def api(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Print the call and return what an empty repository would."""
        details = "" if body is None else f" {json.dumps(body, sort_keys=True)}"
        self.echo(f"[dry run] {method} {path}{details}")
        return [] if method == "GET" else None


def apply(gh: Gh, settings_dir: Path, echo: Echo) -> None:
    """Apply every settings file to the repository."""
    repo = json.loads((settings_dir / "repo.json").read_text())
    security = repo.pop("security", {})

    gh.api("PATCH", REPO, repo)
    echo("Updated merge options and repository features.")
    if security.get("vulnerability_alerts"):
        gh.api("PUT", f"{REPO}/vulnerability-alerts")
        echo("Turned on Dependabot alerts.")
    if security.get("automated_security_fixes"):
        gh.api("PUT", f"{REPO}/automated-security-fixes")
        echo("Turned on Dependabot security updates.")

    for label in json.loads((settings_dir / "labels.json").read_text()):
        apply_label(gh, label, echo)

    ruleset = json.loads((settings_dir / "main-ruleset.json").read_text())
    apply_ruleset(gh, ruleset, echo)


def apply_label(gh: Gh, label: dict[str, str], echo: Echo) -> None:
    """Update a label, or create it when it does not exist yet.

    Raises:
        GhError: Any failure other than the label being missing.
    """
    try:
        gh.api("PATCH", f"{REPO}/labels/{label['name']}", label)
        echo(f"Updated the {label['name']} label.")
    except GhError as error:
        if error.status != HTTPStatus.NOT_FOUND:
            raise
        gh.api("POST", f"{REPO}/labels", label)
        echo(f"Created the {label['name']} label.")


def apply_ruleset(gh: Gh, ruleset: dict[str, Any], echo: Echo) -> None:
    """Create or update a ruleset, skipping it when the plan does not allow it.

    Raises:
        GhError: Any failure other than the paid-plan restriction.
    """
    try:
        existing = gh.api("GET", f"{REPO}/rulesets")
    except GhError as error:
        if error.status != HTTPStatus.FORBIDDEN:
            raise
        echo(
            f"Skipped the {ruleset['name']} ruleset: GitHub needs a paid plan "
            "for rulesets on private repositories."
        )
        return

    current = next((r for r in existing if r["name"] == ruleset["name"]), None)
    if current is None:
        gh.api("POST", f"{REPO}/rulesets", ruleset)
        echo(f"Created the {ruleset['name']} ruleset.")
    else:
        gh.api("PUT", f"{REPO}/rulesets/{current['id']}", ruleset)
        echo(f"Updated the {ruleset['name']} ruleset.")


def required_checks(settings_dir: Path) -> list[str]:
    """Names of the checks that must pass before merging, from the ruleset."""
    ruleset = json.loads((settings_dir / "main-ruleset.json").read_text())
    return [
        check["context"]
        for rule in ruleset["rules"]
        if rule["type"] == "required_status_checks"
        for check in rule["parameters"]["required_status_checks"]
    ]


def merge_when_ready(gh: Gh, number: int, checks: list[str], echo: Echo) -> bool:
    """Rebase-merge a pull request if it is labelled and every check passed.

    Returns:
        True when the pull request was merged.
    """
    pull = gh.api("GET", f"{REPO}/pulls/{number}")
    if pull["state"] != "open":
        echo(f"#{number} is {pull['state']}; nothing to do.")
        return False
    if AUTOMERGE_LABEL not in {label["name"] for label in pull["labels"]}:
        echo(f"#{number} has no {AUTOMERGE_LABEL} label; leaving it for review.")
        return False

    sha = pull["head"]["sha"]
    runs = gh.api("GET", f"{REPO}/commits/{sha}/check-runs")["check_runs"]
    for name in checks:
        run = next((r for r in runs if r["name"] == name), None)
        if run is None or run["conclusion"] != "success":
            state = "missing" if run is None else run["conclusion"] or run["status"]
            echo(f"#{number} is waiting for {name!r} ({state}).")
            return False

    gh.api(
        "PUT", f"{REPO}/pulls/{number}/merge", {"merge_method": "rebase", "sha": sha}
    )
    echo(f"Merged #{number}.")
    return True


@task(help={"pr": "Pull request number.", "gh": "Path to the gh executable."})
def merge_if_ready(c: Context, pr: str, gh: str = "gh") -> None:
    """Merge a pull request labelled automerge once its CI check passed."""
    merge_when_ready(GhCli(Shell(c), gh), int(pr), required_checks(SETTINGS_DIR), print)


@task(
    help={
        "dry_run": "Print the API calls instead of making them.",
        "gh": "Path to the gh executable.",
    }
)
def apply_settings(c: Context, dry_run: bool = False, gh: str = "gh") -> None:
    """Apply .github/settings to the GitHub repository."""
    if dry_run:
        # Print only the calls; results like "Created" would not be true yet.
        apply(DryRunGh(print), SETTINGS_DIR, lambda _: None)
    else:
        apply(GhCli(Shell(c), gh), SETTINGS_DIR, print)
