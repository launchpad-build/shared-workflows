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
| `--package` | none | Package to build and test on a pull request. Omit to skip the build-and-test caller. |

This creates five files, plus a sixth when `--package` is given:

| File | Purpose |
|------|---------|
| `newsfragments/.gitkeep` | Fragment storage directory |
| `towncrier.toml` | Towncrier configuration |
| `CHANGELOG.md` | Changelog file |
| `.github/workflows/require-news-fragment-on-pr.yml` | Caller workflow for PR checks |
| `.github/workflows/release-on-merge.yml` | Caller workflow for releases |
| `.github/workflows/build-and-test-on-pr.yml` | Caller workflow for colcon build and test, only with `--package` |

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

jobs:
  build-and-test:
    uses: launchpad-build/shared-workflows/.github/workflows/build-and-test.yml@latest
    with:
      package: my_package
    secrets: inherit
```

`secrets: inherit` passes the organisation `GHCR_READ_TOKEN` through as the
`ghcr-token` secret, which the job uses to pull the container image.

| Input | Default | Description |
|-------|---------|-------------|
| `package` | required | Package to build and test. Space-separated for several packages in one repository. |
| `container-image` | `ghcr.io/launchpad-build/launchpad-ros2-jazzy:main` | Image holding the ROS 2 build environment |
| `ros-distro` | `jazzy` | Distribution sourced before the build |
| `colcon-build-args` | empty | Extra arguments appended to `colcon build` |
| `colcon-test-args` | empty | Extra arguments appended to `colcon test` |

### What the job does

1. Checks the repository out into `src/repo`.
2. Runs `colcon build --packages-select <package>`, so nothing else in the workspace builds.
3. Runs `colcon test --packages-select <package> --return-code-on-test-failure`, then `colcon test-result --all --verbose`.
4. Parses the JUnit XML under `build/<package>` and writes a results table to the run summary, with a bullet per failing test naming the suite, the case, and the first line of the failure.
5. Exits non-zero when any test fails, which fails the check.

A package with no tests passes. The summary then reads `No tests found for
<package>.` and the run carries a notice annotation saying the same.

### Blocking the pull request

The check only blocks a merge once the repository ruleset requires it. Add a
`required_status_checks` rule naming the check to the ruleset on `main`:

```bash
gh api repos/launchpad-build/<repo>/rulesets/<id> --jq '.rules'
```

The check name is the caller job name, then the reusable workflow's job name,
for example `build-and-test / Build and test demo_pkg`. Read the exact string
off a real run before writing it into the ruleset:

```bash
gh api repos/launchpad-build/<repo>/commits/<sha>/check-runs --jq '.check_runs[].name'
```

Do not add classic branch protection. It overrides the ruleset bypass actors and
blocks the release push.

### Rollout

`versioning-demo` carries the reference implementation. The rest of the estate
adopts the same caller, with the `package` input set to that repository's
packages:

| Repository | `package` input |
|------------|-----------------|
| `l3h-bringup` | `l3h_bringup` |
| `digitool-bringup` | `digitool_bringup` |
| `digitool-control` | `digitool_control digitool_motion_planner` |
| `digitool-common` | `digitool_bist digitool_health_monitor digitool_job_generator digitool_job_tracker digitool_mock digitool_object_store digitool_parameter_manager digitool_ros_utils digitool_state_monitor mqtt_ros2_bridge` |
| `digitool-peripherals` | `digitool_calibration digitool_cylinder_utils digitool_delta_regis_screwdriver digitool_gripper_io digitool_lift_swing digitool_presenter digitool_qa_camera digitool_safety_io digitool_silo digitool_silo_utils digitool_stack_light digitool_vibe_coordinator digitool_vibe_feeder digitool_vibe_pulse digitool_vibe_station` |

Each repository also needs the required-status-check rule added to its own
ruleset, and a package whose dependencies all resolve inside the container. A
package that depends on a sibling private repository needs that repository
imported first, which this workflow does not do.

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
