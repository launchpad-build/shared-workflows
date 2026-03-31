# Shared versioning workflows

Reusable GitHub Actions workflows for news-fragment-driven semantic versioning.

Consuming repos get automatic version bumps, changelog generation, and git tags on every merge to main. PRs that change source code must include a news fragment.

## Quick start

Run the bootstrap script from your repo root:

```bash
# ROS 2 repos (default, reads version from package.xml)
curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh | bash

# Node.js repos
curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh | bash -s -- --version-source package-json

# Python repos
curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh | bash -s -- --version-source pyproject-toml
```

This creates five files:

| File | Purpose |
|------|---------|
| `newsfragments/.gitkeep` | Fragment storage directory |
| `towncrier.toml` | Towncrier configuration |
| `CHANGELOG.md` | Changelog seed with towncrier marker |
| `.github/workflows/require-news-fragment-on-pr.yml` | Caller workflow for PR checks |
| `.github/workflows/release-on-merge.yml` | Caller workflow for releases |

Commit them to `main` and you are done.

## How it works

### PR workflow

1. A developer opens a PR that changes source files.
2. The workflow diffs the PR against `main` and filters out exempt paths.
3. If source files changed, `towncrier check` verifies a fragment exists.
4. The PR blocks until a valid fragment is added.

### Release workflow

1. A PR merges to `main`.
2. The workflow scans `newsfragments/` for `.breaking`, `.feature`, and `.fix` files.
3. The highest-priority type sets the bump level: breaking = major, feature = minor, fix = patch.
4. Towncrier compiles fragments into `CHANGELOG.md` and deletes them.
5. The workflow writes the new version into every manifest, commits, tags, and pushes.

### Fragment naming

```
newsfragments/DEV-123.breaking   # major bump
newsfragments/DEV-123.feature    # minor bump
newsfragments/DEV-123.fix        # patch bump
```

Fragment content is a one-line description that appears in the changelog.

## Reusable workflow inputs

### require-news-fragment.yml

| Input | Default | Description |
|-------|---------|-------------|
| `exclude-patterns` | See workflow | Regex of paths exempt from the fragment requirement |
| `python-version` | `3.12` | Python version for towncrier |

### release-on-merge.yml

| Input | Default | Description |
|-------|---------|-------------|
| `version-source` | `package-xml` | Where to read/write the version: `package-xml`, `package-json`, or `pyproject-toml` |
| `python-version` | `3.12` | Python version for towncrier |
| `fragment-directory` | `newsfragments` | Directory containing news fragments |

## Caller workflow examples

### Minimal (ROS 2 defaults)

```yaml
# .github/workflows/release-on-merge.yml
name: Release version on merge to main
on:
  push:
    branches: [main]
permissions:
  contents: write
jobs:
  release:
    uses: launchpad-build/shared-workflows/.github/workflows/release-on-merge.yml@main
```

### With overrides

```yaml
# .github/workflows/release-on-merge.yml
name: Release version on merge to main
on:
  push:
    branches: [main]
permissions:
  contents: write
jobs:
  release:
    uses: launchpad-build/shared-workflows/.github/workflows/release-on-merge.yml@main
    with:
      version-source: package-json
      python-version: "3.11"
```

## Exempt file patterns

The PR check workflow skips these paths by default:

- `newsfragments/` (the fragments themselves)
- `.github/` (CI configuration)
- `CHANGELOG.md` (generated file)
- `README.md` (documentation)
- `towncrier.toml` (tooling config)
- `.gitignore`

Override via the `exclude-patterns` input if your repo needs different exemptions.
