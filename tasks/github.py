"""Apply the repository settings in `.github/settings` to GitHub."""

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol

from invoke.context import Context
from invoke.tasks import task

SETTINGS_DIR = Path(__file__).parents[1] / ".github" / "settings"

# `gh api` fills {owner} and {repo} from the current git remote.
REPO = "repos/{owner}/{repo}"

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

    executable: str = "gh"

    def api(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Run `gh api` and return its JSON output, or None when it is empty.

        Raises:
            GhError: `gh` exited with an error, with the HTTP status if known.
        """
        args = [self.executable, "api", "--method", method, path]
        if body is not None:
            args += ["--input", "-"]
        result = subprocess.run(
            args,
            input=None if body is None else json.dumps(body),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            match = re.search(r"\(HTTP (\d+)\)", result.stderr)
            status = int(match.group(1)) if match else None
            raise GhError(status, result.stderr.strip())
        return json.loads(result.stdout) if result.stdout.strip() else None


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

    ruleset = json.loads((settings_dir / "main-ruleset.json").read_text())
    apply_ruleset(gh, ruleset, echo)


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
        apply(GhCli(gh), SETTINGS_DIR, print)
