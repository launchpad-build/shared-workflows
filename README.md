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

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build-and-test:
    uses: launchpad-build/shared-workflows/.github/workflows/build-and-test.yml@latest
    with:
      package: my_package
    secrets:
      ghcr-token: ${{ secrets.GHCR_READ_TOKEN }}
```

The job pulls the container image with `ghcr-token`. `secrets: inherit` does not
cover it, because inheritance matches on name and the organisation secret is
called `GHCR_READ_TOKEN`, so pass it through explicitly. Omit the secret and the
job pulls without logging in, which only works for a public image.

`GHCR_READ_TOKEN` is an organisation secret available to every repository, so a
repository adopting this workflow needs nothing added. It is a classic personal
access token carrying `read:packages`, which is the only credential ghcr.io
accepts for a private pull. Proven in real CI: the private default image pulls,
builds and tests green.

ghcr.io ignores the user name on a token login, so the login step passes the
literal `x-access-token` rather than `github.actor`. The actor is whoever
triggered the run, which is not the token owner in a run triggered by a bot or by
another user, so naming it there would only mislead.

| Input | Default | Description |
|-------|---------|-------------|
| `package` | required | Package to build and test. Space-separated for several packages in one repository. |
| `container-image` | `ghcr.io/launchpad-build/launchpad-ros2-jazzy:main` | Image holding the ROS 2 build environment |
| `base-paths` | `src` | Paths colcon crawls for packages. Space-separated for several roots. |
| `registry` | `ghcr.io` | Registry logged into before the image is pulled |
| `ros-distro` | `jazzy` | Distribution sourced before the build |
| `install-dependencies` | `true` | Run `rosdep install` over the closure the build will cover, before building |
| `run-linters` | `false` | Run the ament style and lint tests. Off by default, see below. |
| `colcon-build-args` | empty | Extra arguments appended to `colcon build` |
| `colcon-test-args` | empty | Extra arguments appended to `colcon test`, before the linter exclusion |
| `timeout-minutes` | `60` | Minutes the job may run before it is cancelled |

### What the job does

1. Checks the repository out into `src/repo`.
2. Checks itself out into `.shared-workflows` at its own commit, read off the
   `job` context, so its scripts are on disk.
3. Logs into the registry when `ghcr-token` is set, then pulls the image.
4. Starts one long-lived container and runs every later step in it with `docker exec`.
5. Runs `rosdep install` over the closure `--packages-up-to` will build, unless `install-dependencies` is false.
6. Runs `colcon build --packages-up-to <package>`, so a sibling the package depends on builds first.
7. Fails when a selected package produced no build directory, so a typo in `package` cannot pass as a clean run.
8. Runs `colcon test --packages-select <package> --return-code-on-test-failure`, excluding the ament linters unless `run-linters` is true, then `colcon test-result --all --verbose`.
9. Parses the result XML under `build/<package>` and writes a row per package to the run summary, with a bullet per failing test naming the case and the first line of the failure.
10. Exits non-zero when any test fails, which fails the check.

### Why the job is shaped this way

Each choice below answers a failure seen on a real run, not a preference.

**Every step is a script file, not inlined YAML.** Each step is an `env` block and
one call to a script under `scripts/build-and-test`. Data reaches a script through
the environment, so no workflow input is ever interpolated into a command line.

| Script | Step |
|--------|------|
| `registry-login.sh` | Log in to the container registry |
| `pull-image.sh` | Pull the container image |
| `start-container.sh` | Start the build container |
| `install-dependencies.sh` | Install the declared dependencies |
| `build-packages.sh` | Build the package |
| `check-build-directories.sh` | Confirm every selected package built |
| `run-tests.sh` | Test the package |
| `summarise-results.sh`, `summarise_test_results.py` | Summarise the test results |
| `stop-container.sh` | Stop the build container |

`summarise_test_results.py` is an importable module. `tests/test_summarise_test_results.py`
covers the recorded edge cases: no test cases, a truncated result file, a skipped
test, a skipped test step, a mixed run, the capped bullet list and a named failing
case. Run it with `python3 -m unittest discover -s tests`.

**The scripts are checked out, not turned into a composite action.** A reusable
workflow never gets its own repository on disk, so a script file in
`shared-workflows` is absent when the callee runs. A second `actions/checkout` of
`launchpad-build/shared-workflows` puts them there.

A composite action gets its own files for free through `GITHUB_ACTION_PATH`, but
`uses:` takes no expression, so the workflow would have to name one fixed ref.
That ref either floats and lets the scripts drift from the workflow, or is a tag
that has to be bumped by hand after every change, and a branch under review would
run the wrong scripts. A composite action also cannot reproduce this job: a failed
step aborts the action, so the `if: always()` summary and container teardown would
not run, and the summary reads `steps.build.outcome` and `steps.test.outcome`,
which a composite action does not expose.

**The job context names the workflow's own commit.** A called workflow now reads
its own repository and commit from `job.workflow_repository` and
`job.workflow_sha`, and checks its scripts out from there. The scripts therefore
come from the same commit as the workflow file, whatever ref the caller pinned,
including a moving tag such as `latest`. The caller says nothing about it and
there is nothing to keep in step.

The two lookalikes on the `github` context do not work. `github.job_workflow_sha`
and `github.job_workflow_ref` are OIDC claims, and a probe run confirmed both
evaluate to the empty string in a callee's steps, which silently sends
`actions/checkout` to the default branch. The `job` properties are different
properties on a different context, added in April 2026, and a probe run confirmed
both are populated and correct. They are not available in a job-level `env:`
block, only in a step, so they are read at the step that uses them.

This replaced a required `shared-workflows-ref` input, which repeated the ref
from the caller's `uses:` line, and a `verify-scripts-ref.sh` step that read the
caller's workflow back off disk and failed the job when the two disagreed. Both
are gone. A caller that still passes the input does not warn, it fails at
startup with no jobs, so a caller has to drop the input in the same change.

**Docker by hand, not a job-level `container:`.** A `container:` block needs
`credentials` to pull the private default image, and those credentials cannot be
empty. A password that resolves to an empty string kills the job before any step
runs, with `The template is not valid ... Unexpected value ''`. The obvious
escape is a fallback, `password: ${{ secrets.ghcr-token || github.token }}`.
A probe run proved that fallback breaks a public image on Docker Hub. The runner
reads the login server off the image name and logs in before it pulls. For
`ros:jazzy-ros-base` that server is Docker Hub, which rejects a GitHub token, so
the job dies in `Initialize containers`. The fallback holds only for `ghcr.io`,
and even there it needs `packages: read` on the job token, which this workflow
does not grant. Driving docker by hand serves a private image, a public image and
any registry from one workflow.

**The login gate reads a job env boolean.** The `secrets` context is not
available in a step `if:`. A step `if: secrets.ghcr-token != ''` does worse than
never firing: it invalidates the whole workflow file, and every run then fails
before a job starts. The job copies the comparison into `HAS_REGISTRY_TOKEN`, and
the login step tests `env.HAS_REGISTRY_TOKEN == 'true'`. The secret itself stays
in the login step's own env, so it never reaches the job-wide env.

**One container, not one `docker run` per step.** `rosdep install` writes into the
running container's filesystem. A fresh container per step throws those packages
away before the build can use them, so every step shares a single container
started once and removed at the end.

**`rosdep install` by default.** A package can declare a dependency the image does
not carry. `digitool_ros2_perception` declares `python3-pytest-cov`, which
`ros:jazzy-ros-base` lacks. Set `install-dependencies` to false for an image that
already carries the full dependency set and you save about ten seconds.

**rosdep is scoped to the build closure, not to the base paths.** The step asks
colcon which packages `--packages-up-to` will build and gives rosdep those paths,
because a real repository declares dependencies the selected packages never need.
Over the 44 product packages, crawling the base paths dragged in the whole moveit
and plansys2 set for packages the build never touched, and it failed outright on
`behaviortree_ros2`, a source-only fork with no rosdistro entry, declared by two
packages that were not selected. Scoping to the closure cut the step from a
two-minute failure to a clean six seconds installing the two keys the build
actually wanted, `nlohmann-json3-dev` and `python3-pytest-cov`. When colcon
cannot resolve the selection the
step falls back to the base paths, so a mistyped package name still fails at the
build step with colcon's own message.

**`--packages-up-to` to build, `--packages-select` to test.** A package that
depends on a sibling in the same repository cannot configure under
`--packages-select` alone. `digitool_action_primitives_interfaces` depends on
`digitool_std_msgs`, and selecting it on its own fails at configure with
`Failed to find the following files: install/digitool_std_msgs/.../package.sh`.
Building up to it pulls the sibling in. Testing still selects only the requested
packages, so a sibling's results never land in this repository's check.

**The result glob is pinned.** Results are read from
`build/<package>/test_results/**/*.xml` and from XML directly under
`build/<package>`, which is where ament writes gtest and linter xunit files and
where colcon writes `pytest.xml`. A recursive glob over the whole build directory
also swallows CTest's own `Testing/<stamp>/Test.xml` and any XML fixture a package
vendors.

**The failure name comes from `classname`.** A pytest suite is called `pytest`
whatever it holds, so the suite name alone reports
`pytest.test_something`. The `classname` attribute carries the module, giving
`digitool_ros2_perception.test.test_config.test_something` instead.

**The exit code is checked even when no tests were found.** A test that crashes
before writing its XML leaves no failing case to report. Reporting "no tests
found" and passing would turn a crash into a green check. A result file that
cannot be parsed fails the job for the same reason.

**The caller cancels its own superseded runs.** The concurrency group lives in the
caller, not in this workflow. `inputs` is empty while a workflow-level group is
evaluated in a callee, so a group keyed on `inputs.package` collapsed to a bare
ref and two jobs in one caller still cancelled each other. Keying on
`github.workflow` and `github.ref` in the caller cancels the whole superseded run
on a new push, and leaves the jobs within one run alone.

**Failure bullets are capped at twenty, taken a package at a time in turn.** One
mixed-case CMake command produced fourteen `lint_cmake` failures on a single file,
so a long linter run would otherwise bury the summary. The cap is global, so the
list is filled by taking one failure from each package in turn rather than by
running through the packages in order. Over the 44 product packages the ordered
version filled all twenty bullets from `digitool_job_tracker`'s linter failures
alone, and the single genuine unit-test failures in `digitool_health_monitor` and
`digitool_bist` appeared nowhere in the summary or the annotations. Interleaving
puts all six failing packages inside the same twenty bullets.

**The ament style and lint tests do not run.** `run-linters` defaults to false, so
this check tests behaviour and says nothing about style. The reason is measured,
not a preference. Over fifteen packages of a real product workspace the linters
the packages themselves declare raised 148 failures out of 313 cases, and only
two of those were unit tests. Almost all of the rest were `copyright` and
`cpplint`'s `legal/copyright`, which demand a header the house C++ style forbids,
plus `uncrustify` diffs and `flake8` docstring rules. None of these repositories
has ever run a test workflow, so turning the check on with linters enabled would
redden every repository in the estate on debt that predates it.

The consequence is worth stating plainly: **nothing in CI enforces style while
this input is false**. A repository that has cleared its linter debt, or that has
dropped `ament_lint_auto` where the house style deliberately disagrees, opts back
in from its own caller:

```yaml
    with:
      package: my_package
      run-linters: true
```

Excluding them takes two mechanisms, because the two build types run linters
differently. An `ament_cmake` package registers each linter as a CTest test
carrying the `linter` label, so `--ctest-args -LE linter` drops them. An
`ament_python` package runs its linters as pytest tests instead, which carry no
CTest label, so `-LE linter` does nothing there. Those tests do carry the pytest
marker `linter`, registered by `ament_lint`, so `--pytest-args -m "not linter"`
is the exact counterpart. An `ament_cmake_python` package registers its Python
linters through CMake, so the CTest label covers it. Over the same fifteen
packages the pair took the run from 313 cases and 148 failures to 96 cases and
one failure, and that one is a genuine unit-test bug.

The exclusion is appended after `colcon-test-args`, so a caller can never drop it
by accident. colcon lets a later `--ctest-args` or `--pytest-args` replace an
earlier one, so a caller passing its own group loses that group to the exclusion.
The step raises a warning annotation naming the collision rather than swallowing
it. To keep both, set `run-linters` to true and put the exclusion in your own
arguments.

A package with no tests passes. Its row reads `no tests` and the run carries a
notice annotation naming the packages that had none. Excluding the linters makes
that common: four of the fifteen product packages had nothing but linter tests,
and their rows now read `no tests`.

**A package colcon failed is named.** The exit code of `colcon test` covers the
whole run, so a package that failed without writing a failing case could only be
reported as a bare number. The summary step now reads the per-package status out
of colcon's own event log, `log/latest_test/events.log`, and names each package
whose job failed with nothing to explain it. The aggregate code stays as the
fallback for a run that never got as far as an event log.

That per-package status is also what stops an emptied suite reddening the check.
A package left with no test to collect exits 5, which is pytest's code for
collecting nothing. colcon already treats it as success on its own pytest path
but not on its `setup.py test` path, so `digitool_mock` failed the job while
reporting no test at all. A package is now excused only when all three hold: the
code is that one, the package reported zero cases, and every result file it wrote
was readable. Any other non-zero code, an unreadable file, or a failing case
still fails the job, and now says which package.

### Blocking the pull request

The check only blocks a merge once the repository ruleset requires it. Add a
`required_status_checks` rule naming the check to the ruleset on `main`:

```bash
gh api repos/launchpad-build/<repo>/rulesets/<id> --jq '.rules'
```

The check name is the caller job id, then the reusable workflow's job name, for
example `build-and-test / Build and test`. The job name deliberately omits the
package input, so changing which packages a repository tests does not leave a
stale required context behind. Read the exact string
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
