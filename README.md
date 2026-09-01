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

`build-and-test.yml` builds and tests one repository's packages inside the ROS 2
container, on every pull request. A failing test fails the check, and the run
summary names each failing test.

### Caller

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

Pass `ghcr-token` explicitly. `secrets: inherit` matches on name, and the
organisation secret is called `GHCR_READ_TOKEN`, so inheritance passes nothing.
It reaches every repository already, so an adopting repository needs nothing
added. Omit it only for a public image.

| Input | Default | Description |
|-------|---------|-------------|
| `package` | empty | Package to build and test. Space-separated for several packages in one repository. Leave it unset to cover every package colcon crawls. |
| `container-image` | `ghcr.io/launchpad-build/launchpad-ros2-jazzy:main` | Image holding the ROS 2 build environment |
| `base-paths` | `src` | Paths colcon crawls for packages. Space-separated for several roots. |
| `registry` | `ghcr.io` | Registry logged into before the image is pulled |
| `ros-distro` | `jazzy` | Distribution sourced before the build |
| `install-dependencies` | `true` | Run `rosdep install` over the closure the build will cover, before building |
| `run-linters` | `false` | Run the ament style and lint tests. Off by default. |
| `colcon-build-args` | empty | Extra arguments appended to `colcon build` |
| `colcon-test-args` | empty | Extra arguments appended to `colcon test`, before the linter exclusion |
| `timeout-minutes` | `60` | Minutes the job may run before it is cancelled |

Leave `package` unset to cover everything colcon crawls, so a package added later
is tested without editing the caller. Set `base-paths` below the outer package
when the repository has a `package.xml` at its root, because colcon stops
descending there.

The ament style and lint tests are off by default. The house style disagrees with
several of them, so a repository that has never run them would redden the check on
style debt rather than on a real failure. Set `run-linters: true` once a
repository is clean.

### What the job does

1. Checks the repository out into `src/repo`, and itself into `.shared-workflows`
   at its own commit.
2. Logs into the registry when `ghcr-token` is set, pulls the image, and starts
   one long-lived container that every later step runs in.
3. Resolves the packages the run covers: the `package` input, or `colcon list`
   over `base-paths`.
4. Runs `rosdep install` over the closure the build will cover, unless
   `install-dependencies` is false.
5. Builds with `--packages-up-to`, so a sibling dependency builds first, then
   fails if a resolved package produced no build directory.
6. Tests with `--packages-select` and `--return-code-on-test-failure`, excluding
   the linters unless `run-linters` is true.
7. Parses the result XML, writes a row per package and a bullet per failing test
   to the run summary, and exits non-zero when any test failed.

### Blocking the pull request

The check blocks a merge only once the repository ruleset requires it. The check
name is the caller job id, then the reusable workflow's job name, for example
`build-and-test / Build and test`. Read the exact string off a real run before
writing it into the ruleset:

```bash
gh api repos/launchpad-build/<repo>/commits/<sha>/check-runs --jq '.check_runs[].name'
```

Do not add classic branch protection. It overrides the ruleset bypass actors and
blocks the release push.

### Rollout

`versioning-demo` carries the reference implementation. The lists below are what
each repository holds today, and are worth setting only where the check should
cover less than the whole repository:

| Repository | `package` input |
|------------|-----------------|
| `l3h-bringup` | `l3h_bringup` |
| `digitool-bringup` | `digitool_bringup` |
| `digitool-control` | `digitool_control digitool_motion_planner` |
| `digitool-common` | `digitool_bist digitool_health_monitor digitool_job_generator digitool_job_tracker digitool_mock digitool_object_store digitool_parameter_manager digitool_ros_utils digitool_state_monitor mqtt_ros2_bridge` |
| `digitool-peripherals` | `digitool_calibration digitool_cylinder_utils digitool_delta_regis_screwdriver digitool_gripper_io digitool_lift_swing digitool_presenter digitool_qa_camera digitool_safety_io digitool_silo digitool_silo_utils digitool_stack_light digitool_vibe_coordinator digitool_vibe_feeder digitool_vibe_pulse digitool_vibe_station` |

Each repository also needs the required-status-check rule added to its own
ruleset. A package that depends on a sibling private repository needs that
repository imported first, which this workflow does not do.

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
