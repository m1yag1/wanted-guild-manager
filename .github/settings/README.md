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

Dependabot version updates are configured in `.github/dependabot.yml`.
