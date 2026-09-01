# Shared versioning workflows

Reusable GitHub Actions workflows for news-fragment-driven semantic versioning.

## Start

Run the bootstrap script from your repo root:

```bash
curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh \
  | bash -s -- --version-source package-xml --ref latest
```

| Flag | Default | Description |
|------|---------|-------------|
| `--version-source` | `package-xml` | Manifest format: `package-xml`, `package-json`, or `pyproject-toml` |
| `--ref` | `latest` | Tag or branch the caller workflows point at |
| `--package` | none | Package to build and test on a pull request. Omit to cover every package colcon crawls. |
| `--build-and-test` | off | Write the build-and-test caller with no package input. Not needed when `--package` is given. |

This creates five files, plus a sixth with `--package` or `--build-and-test`:

| File | Purpose |
|------|---------|
| `newsfragments/.gitkeep` | Fragment storage directory |
| `towncrier.toml` | Towncrier configuration |
| `CHANGELOG.md` | Changelog file |
| `.github/workflows/require-news-fragment-on-pr.yml` | Caller workflow for PR checks |
| `.github/workflows/release-on-merge.yml` | Caller workflow for releases |
| `.github/workflows/build-and-test-on-pr.yml` | Caller workflow for colcon build and test, only with `--package` or `--build-and-test` |

Commit to `main`.

## Tracking releases

Pin the caller workflows at `latest` to always run the newest release:

```yaml
uses: launchpad-build/shared-workflows/.github/workflows/release-on-merge.yml@latest
```

`latest` is a moving tag that points at the newest release. A consumer pinned at
`@latest` picks up each new release with no pin bump.

Pin a fixed version instead when you need a reproducible ref and want to bump
deliberately:

```yaml
uses: launchpad-build/shared-workflows/.github/workflows/release-on-merge.yml@2.0.3
```

## Build and test on pull request

`build-and-test.yml` builds and tests a repository's packages in the ROS 2
container on every pull request. A failing test fails the check, and the run
summary names each failing test.

```yaml
name: Build and test on pull request

on:
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build-and-test:
    uses: launchpad-build/shared-workflows/.github/workflows/build-and-test.yml@latest
    secrets:
      ghcr-token: ${{ secrets.GHCR_READ_TOKEN }}
```

| Input | Default | Description |
|-------|---------|-------------|
| `package` | empty | Packages to cover, space-separated. Unset covers every package colcon crawls. |
| `container-image` | `ghcr.io/launchpad-build/launchpad-ros2-jazzy:main` | Image holding the ROS 2 build environment |
| `base-paths` | `src` | Paths colcon crawls, space-separated |
| `registry` | `ghcr.io` | Registry logged into before the pull |
| `ros-distro` | `jazzy` | Distribution sourced before the build |
| `install-dependencies` | `true` | Run `rosdep install` over the build closure |
| `run-linters` | `false` | Run the ament style and lint tests |
| `colcon-build-args` | empty | Extra arguments for `colcon build` |
| `colcon-test-args` | empty | Extra arguments for `colcon test` |
| `timeout-minutes` | `60` | Minutes before the job is cancelled |

Four things to know:

* Pass `ghcr-token` explicitly. `secrets: inherit` matches on name, so it passes
  nothing. Omit it only for a public image.
* Point `base-paths` below the outer package when the repository has a
  `package.xml` at its root, because colcon stops descending there.
* Linters are off because the house style disagrees with several of them. Turn
  them on once a repository is clean.
* The required-status-check name is the caller job id then the callee job name,
  for example `build-and-test / Build and test`. Do not add classic branch
  protection, it blocks the release push.

## How it works

### Workflow

1. A developer opens a PR that changes source files.
2. The workflow rejects any file in `newsfragments/` that is not `.gitkeep` or a valid fragment name.
3. The workflow diffs the PR against `main`.
4. If source files changed, `towncrier check` verifies a fragment exists.
5. The PR blocks until a valid fragment is added.

### Release workflow

1. A PR merges to `main`.
2. The workflow scans `newsfragments/` for `.breaking`, `.feature`, and `.fix` files, with an optional trailing `.md` suffix.
3. The highest-priority type sets the bump level: breaking = major, feature = minor, fix = patch.
4. Towncrier compiles fragments into `CHANGELOG.md` and deletes them.
5. The workflow writes the new version into every package.xml.
6. If `.github/version-stamp.sh` exists, the workflow runs it with the new version.
7. The workflow commits, tags, and pushes.

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
