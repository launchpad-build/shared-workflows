# Shared versioning workflows

Reusable GitHub Actions workflows for news-fragment-driven semantic versioning.

## Start

Run the bootstrap script from your repo root:

```bash
curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh \
  | bash -s -- --version-source package-xml --ref 1.0.0
```

| Flag | Default | Description |
|------|---------|-------------|
| `--version-source` | `package-xml` | Manifest format: `package-xml`, `package-json`, or `pyproject-toml` |
| `--ref` | `main` | Tag or branch the caller workflows point at |

This creates five files:

| File | Purpose |
|------|---------|
| `newsfragments/.gitkeep` | Fragment storage directory |
| `towncrier.toml` | Towncrier configuration |
| `CHANGELOG.md` | Changelog file |
| `.github/workflows/require-news-fragment-on-pr.yml` | Caller workflow for PR checks |
| `.github/workflows/release-on-merge.yml` | Caller workflow for releases |

Commit to `main`.

## How it works

### Workflow

1. A developer opens a PR that changes source files.
2. The workflow diffs the PR against `main`.
3. If source files changed, `towncrier check` verifies a fragment exists.
4. The PR blocks until a valid fragment is added.

### Release workflow

1. A PR merges to `main`.
2. The workflow scans `newsfragments/` for `.breaking`, `.feature`, and `.fix` files, with an optional trailing `.md` suffix.
3. The highest-priority type sets the bump level: breaking = major, feature = minor, fix = patch.
4. Towncrier compiles fragments into `CHANGELOG.md` and deletes them.
5. The workflow writes the new version into every package.xml, commits, tags, and pushes.

### Fragment naming

```
newsfragments/DEV-123.breaking   # major bump
newsfragments/DEV-123.feature    # minor bump
newsfragments/DEV-123.fix        # patch bump
```

Append `.md` if you want editor markdown highlighting, e.g. `DEV-123.feature.md`. Towncrier and the release workflow both accept the suffix.

Fragment content is a one-line description that appears in the changelog.

## Exempt file patterns

The PR check workflow skips these paths by default:

- `newsfragments/` (the fragments themselves)
- `.github/` (CI configuration)
- `CHANGELOG.md` (generated file)
- `towncrier.toml` (tooling config)

Override via the `exclude-patterns` input if your repo needs different exemptions.
