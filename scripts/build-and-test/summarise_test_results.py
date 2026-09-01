#!/usr/bin/env python3
"""Turn colcon result XML into a run summary, annotations and an exit code.

The module is importable so the summary text, the annotations and the exit
code can be asserted without a runner. Only ``main`` touches the filesystem
beyond reading the result files.
"""

import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from itertools import chain, zip_longest
from dataclasses import dataclass, field

MAX_LISTED_FAILURES = 20

# pytest and setuptools both use this code for a run that collected no test.
# colcon already treats it as success on its pytest path and not on its
# setup.py path, so a package with nothing left to run can still fail the job.
NO_TESTS_COLLECTED = 5

JOB_ENDED = re.compile(
    r"JobEnded: \{'identifier': '(?P<package>[^']+)', 'rc': (?P<code>-?\d+)\}"
)


@dataclass
class PackageResult:
    """Counts, failure bullets and unreadable files for one package."""

    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)


def result_files(package: str, build_root: str = "build") -> set[str]:
    """Result XML colcon and ament write, and nothing else.

    A recursive glob over the whole build directory also picks up
    vendored fixtures and CTest's own Testing/*/Test.xml, so the search
    is pinned to the two places results actually land.
    """
    paths = set(
        glob.glob(f"{build_root}/{package}/test_results/**/*.xml", recursive=True)
    )
    paths.update(glob.glob(f"{build_root}/{package}/*.xml"))
    return paths


def case_label(suite: ET.Element, case: ET.Element) -> str:
    """Name a case the way a reader would look for it in the log."""
    owner = case.get("classname") or suite.get("name") or "suite"
    return f"{owner}.{case.get('name') or 'case'}"


def failure_detail(problem: ET.Element) -> str:
    """First line of a failure message, or a stand-in when there is none."""
    detail = (problem.get("message") or (problem.text or "")).strip()
    result = detail.splitlines()[0] if detail else "no detail reported"
    return result


def tally_case(result: PackageResult, suite: ET.Element, case: ET.Element) -> None:
    """Fold one testcase element into the package result."""
    result.total += 1
    problems = case.findall("failure") + case.findall("error")
    if case.find("skipped") is not None:
        result.skipped += 1
    elif problems:
        result.failed += 1
        label = f"{result.name}: {case_label(suite, case)}"
        result.failures.append((label, failure_detail(problems[0])))
    else:
        result.passed += 1


def read_package(package: str, build_root: str = "build") -> PackageResult:
    """Read every result file for one package into a PackageResult."""
    result = PackageResult(name=package)
    for path in sorted(result_files(package, build_root)):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            # A test that dies mid-write leaves a truncated file and no
            # failing case, so an unreadable result is itself a failure.
            result.unreadable.append(path)
            continue
        for suite in root.iter("testsuite"):
            for case in suite.findall("testcase"):
                tally_case(result, suite, case)
    return result


def package_exit_codes(log_root: str = "log") -> dict[str, int]:
    """Exit code colcon recorded for each package in the last test run.

    colcon's own event log is the only per-package status the job has. The
    aggregate exit code of ``colcon test`` names nothing, so a package that
    failed without writing a failing case could only be reported as a bare
    number.
    """
    codes: dict[str, int] = {}
    try:
        with open(
            f"{log_root}/latest_test/events.log", encoding="utf-8", errors="replace"
        ) as events:
            for line in events:
                match = JOB_ENDED.search(line)
                if match is not None:
                    codes[match.group("package")] = int(match.group("code"))
    except OSError:
        codes = {}
    return codes


def collected_nothing(result: PackageResult, code: int) -> bool:
    """Whether a package failed only because it had no test left to run."""
    return (
        code == NO_TESTS_COLLECTED
        and result.total == 0
        and not result.unreadable
    )


def unexplained_failures(
    results: Sequence[PackageResult], exit_codes: Mapping[str, int]
) -> list[tuple[str, int]]:
    """Packages colcon failed that reported nothing to explain the failure.

    A package whose tests all failed, or whose result file could not be read,
    is already reported. A package left with no test to collect is not a
    failure: excluding the linters empties the suite of any package that only
    ever ran linters, and colcon already treats that code as success on its
    pytest path.
    """
    by_name = {result.name: result for result in results}
    unexplained = []
    for package, code in sorted(exit_codes.items()):
        result = by_name.get(package)
        if code == 0:
            continue
        if result is None:
            unexplained.append((package, code))
        elif result.failed or result.unreadable:
            continue
        elif not collected_nothing(result, code):
            unexplained.append((package, code))
    return unexplained


def collect_failures(results: Sequence[PackageResult]) -> list[tuple[str, str]]:
    """Every failing case, taken a package at a time in turn.

    Straight concatenation lets one linter-heavy package exhaust the cap on
    the bullet list and the annotations before a later package is reached. A
    real repository does exactly that: over the product packages,
    digitool_job_tracker alone raised 23 linter failures and buried the single
    genuine unit-test failure in digitool_health_monitor. Taking one failure
    from each package in turn keeps every failing package inside the cap.
    """
    rounds = zip_longest(*(result.failures for result in results))
    return [failure for failure in chain.from_iterable(rounds) if failure is not None]


def failure_bullets(failures: Sequence[tuple[str, str]]) -> list[str]:
    """Bullet list of failing tests, capped so a linter run cannot bury it."""
    lines = ["", "**Failing tests**", ""]
    for name, first_line in failures[:MAX_LISTED_FAILURES]:
        lines.append(f"- {name}: {first_line}")
    remaining = len(failures) - MAX_LISTED_FAILURES
    if remaining > 0:
        lines.append(f"- and {remaining} more, see the test step log")
    return lines


def results_table(results: Sequence[PackageResult]) -> list[str]:
    """Markdown table with one row per selected package."""
    lines = [
        "| Package | Total | Passed | Failed | Skipped |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        counts = f"{result.total} | {result.passed} | {result.failed} | {result.skipped}"
        if result.total == 0:
            counts = "no tests | - | - | -"
        lines.append(f"| {result.name} | {counts} |")
    return lines


def unreadable_bullets(unreadable: Sequence[str]) -> list[str]:
    """Bullet list of result files that could not be parsed."""
    lines = ["", "**Unreadable result files**", ""]
    lines.extend(f"- {path}" for path in unreadable)
    return lines


def build_summary(
    results: Sequence[PackageResult],
    build_outcome: str,
    test_outcome: str,
    exit_codes: Mapping[str, int] | None = None,
) -> str:
    """Markdown written to the step summary for this run."""
    lines = ["### Test results", ""]
    if build_outcome != "success":
        lines.append("The build did not complete, so no tests ran.")
    elif test_outcome == "skipped":
        lines.append("The tests did not run. See the failed step in the job log.")
    else:
        lines.extend(results_table(results))
        failures = collect_failures(results)
        unreadable = [path for result in results for path in result.unreadable]
        unexplained = unexplained_failures(results, exit_codes or {})
        if failures:
            lines.extend(failure_bullets(failures))
        if unreadable:
            lines.extend(unreadable_bullets(unreadable))
        if unexplained:
            lines.extend(unexplained_bullets(unexplained))
    return "\n".join(lines) + "\n"


def failure_annotations(failures: Sequence[tuple[str, str]]) -> list[str]:
    """Annotation lines naming the failing tests, capped like the summary."""
    lines = [
        f"::error::{name}: {first_line}"
        for name, first_line in failures[:MAX_LISTED_FAILURES]
    ]
    if failures:
        lines.append(f"::error::{len(failures)} test(s) failed.")
    return lines


def unreadable_annotations(unreadable: Sequence[str]) -> list[str]:
    """Annotation lines naming the result files that could not be parsed."""
    return [
        f"::error::Result file could not be parsed: {path}" for path in unreadable
    ]


def unexplained_annotations(unexplained: Sequence[tuple[str, int]]) -> list[str]:
    """Annotation lines naming each package colcon failed without a case."""
    return [
        f"::error::colcon test exited {code} for {package} without reporting a "
        "failing case."
        for package, code in unexplained
    ]


def unexplained_bullets(unexplained: Sequence[tuple[str, int]]) -> list[str]:
    """Bullet list of packages colcon failed without a failing case."""
    lines = ["", "**Packages colcon failed with no failing case**", ""]
    lines.extend(f"- {package}: exit code {code}" for package, code in unexplained)
    return lines


def build_annotations(
    results: Sequence[PackageResult],
    build_outcome: str,
    test_outcome: str,
    test_rc: str,
    exit_codes: Mapping[str, int] | None = None,
) -> tuple[list[str], int]:
    """Annotation lines and the exit code the job should end on."""
    codes = exit_codes or {}
    failures = collect_failures(results)
    unreadable = [path for result in results for path in result.unreadable]
    unexplained = unexplained_failures(results, codes)
    problems = (
        failure_annotations(failures)
        + unreadable_annotations(unreadable)
        + unexplained_annotations(unexplained)
    )
    if build_outcome != "success":
        outcome = (["::error::The build did not complete, so no tests ran."], 1)
    elif test_outcome == "skipped":
        outcome = (
            ["::error::The tests did not run. See the failed step in the job log."],
            1,
        )
    elif problems:
        outcome = (problems, 1)
    elif not codes and test_rc not in ("", "0"):
        # A crash before any result file is written leaves no failing case to
        # report, so the exit code is the only signal left. Check it whether or
        # not tests were found. Once colcon's per-package log is readable the
        # named packages above carry this instead, so the aggregate code is only
        # the fallback for a run that never got as far as an event log.
        outcome = (
            [
                f"::error::colcon test exited {test_rc} without reporting a failing case."
            ],
            1,
        )
    else:
        empty = [result.name for result in results if result.total == 0]
        lines = [f"::notice::No tests found for {', '.join(empty)}."] if empty else []
        outcome = (lines, 0)
    return outcome


def main(environ: Mapping[str, str] | None = None) -> int:
    """Read the results named by the environment and report on them."""
    env = os.environ if environ is None else environ
    packages = env.get("PACKAGES", "").split()
    build_root = env.get("BUILD_ROOT") or "build"
    build_outcome = env.get("BUILD_OUTCOME") or "success"
    test_outcome = env.get("TEST_OUTCOME") or "success"
    test_rc = env.get("TEST_RC") or ""
    summary_path = env.get("GITHUB_STEP_SUMMARY", "/dev/stdout")
    log_root = env.get("LOG_ROOT") or "log"

    results = [read_package(package, build_root) for package in packages]
    exit_codes = package_exit_codes(log_root)

    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write(
            build_summary(results, build_outcome, test_outcome, exit_codes)
        )

    annotations, code = build_annotations(
        results, build_outcome, test_outcome, test_rc, exit_codes
    )
    for line in annotations:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
