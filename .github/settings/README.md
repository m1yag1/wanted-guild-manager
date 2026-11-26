# Repository settings

GitHub settings for this repository, kept in code and applied with:

```bash
uv run inv github.apply-settings --dry-run   # show what would change
uv run inv github.apply-settings             # apply with your gh login
```

- `repo.json`: merge options (rebase only, so each PR's commits land as they
  are), branch cleanup, features in use, and Dependabot security settings.
- `main-ruleset.json`: protects `main` (PR and CI required, linear history, no
  force-push or deletion). GitHub only allows rulesets on private repositories
  on a paid plan, so the task skips it with a message until then.

- `labels.json`: labels the task creates or updates, such as `automerge`.

Dependabot version updates are configured in `.github/dependabot.yml`.

## Auto-merge

Add the `automerge` label to a pull request, from the GitHub app or with
`gh pr edit <number> --add-label automerge`. The Auto-merge workflow then
rebase-merges it as soon as the "Lint, types and tests" check passes (right away
if it already has). No approval is needed. Remove the label to cancel.
