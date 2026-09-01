#!/usr/bin/env bash
# Reads WORKER, RUN_LINTERS, TEST_ARGS and GITHUB_OUTPUT from the environment.
#
# Only the selected packages are tested, so a sibling pulled in by
# --packages-up-to does not add its results to this repository's check. With no
# selection there is no sibling to hold back, so the flag is left off and colcon
# tests everything it crawled.
#
# The ament linters are excluded unless run-linters is true, and the two build
# types need different mechanisms. An ament_cmake package registers each linter
# as a CTest test carrying the linter label, so -LE linter drops them. An
# ament_python package runs its linters as pytest tests, which carry no CTest
# label, so the pytest marker of the same name does the same job there.
#
# The exclusion is passed as positional arguments rather than appended to the
# string, because -m takes one argument containing a space and the caller's
# TEST_ARGS reaches colcon through word splitting.
#
# The exclusion goes after TEST_ARGS so a caller can never drop it. colcon lets
# a later --ctest-args or --pytest-args replace an earlier one, so a caller
# passing its own group loses it to this one, and the step says so rather than
# dropping it quietly.
set -uo pipefail

exclude=()
if [ "${RUN_LINTERS:-false}" != "true" ]; then
  exclude=(--ctest-args -LE linter --pytest-args -m "not linter")
  case " $TEST_ARGS " in
    *" --ctest-args "* | *" --pytest-args "*)
      echo "::warning::colcon-test-args passes its own --ctest-args or --pytest-args, which the linter exclusion replaces. Set run-linters to true and exclude the linters yourself to keep both."
      ;;
  esac
fi

docker exec -e TEST_ARGS "$WORKER" bash -c '
  source "/opt/ros/$ROS_DISTRO/setup.bash"
  selection=()
  if [ -n "$PACKAGES" ]; then
    selection=(--packages-select $PACKAGES)
  fi
  colcon test \
    --base-paths $BASE_PATHS \
    "${selection[@]}" \
    --event-handlers console_cohesion+ \
    --return-code-on-test-failure \
    $TEST_ARGS "$@"
  rc=$?
  colcon test-result --all --verbose || true
  exit $rc
' colcon-test "${exclude[@]}"
rc=$?
echo "rc=$rc" >> "$GITHUB_OUTPUT"

# The step records the code and succeeds. The summary step is the single
# verdict: it reads the result files and colcon's per-package status, and fails
# the job on what it finds. Failing here as well would be an unappealable red,
# and colcon's code is not a verdict on its own. It returns 0 with a failing
# test, and non-zero for a package that simply had no test left to collect.
exit 0
