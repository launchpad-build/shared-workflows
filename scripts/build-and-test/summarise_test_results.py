#!/usr/bin/env python3
"""Turn colcon result XML into a run summary, annotations and an exit code.

The module is importable so the summary text, the annotations and the exit
code can be asserted without a runner. Only ``main`` touches the filesystem
beyond reading the result files.
"""

import glob
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_LISTED_FAILURES = 20


@dataclass
class PackageResult:
    """Counts, failure bullets and unreadable files for one package."""

    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list = field(default_factory=list)
    unreadable: list = field(default_factory=list)


def result_files(package, build_root="build"):
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


def case_label(suite, case):
    """Name a case the way a reader would look for it in the log."""
    owner = case.get("classname") or suite.get("name") or "suite"
    return f"{owner}.{case.get('name') or 'case'}"


def failure_detail(problem):
    """First line of a failure message, or a stand-in when there is none."""
    detail = (problem.get("message") or (problem.text or "")).strip()
    result = detail.splitlines()[0] if detail else "no detail reported"
    return result


def tally_case(result, suite, case):
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


def read_package(package, build_root="build"):
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


def failure_bullets(failures):
    """Bullet list of failing tests, capped so a linter run cannot bury it."""
    lines = ["", "**Failing tests**", ""]
    for name, first_line in failures[:MAX_LISTED_FAILURES]:
        lines.append(f"- {name}: {first_line}")
    remaining = len(failures) - MAX_LISTED_FAILURES
    if remaining > 0:
        lines.append(f"- and {remaining} more, see the test step log")
    return lines


def results_table(results):
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


def unreadable_bullets(unreadable):
    """Bullet list of result files that could not be parsed."""
    lines = ["", "**Unreadable result files**", ""]
    lines.extend(f"- {path}" for path in unreadable)
    return lines


def build_summary(results, build_outcome, test_outcome):
    """Markdown written to the step summary for this run."""
    lines = ["### Test results", ""]
    if build_outcome != "success":
        lines.append("The build did not complete, so no tests ran.")
    elif test_outcome == "skipped":
        lines.append("The tests did not run. See the failed step in the job log.")
    else:
        lines.extend(results_table(results))
        failures = [failure for result in results for failure in result.failures]
        unreadable = [path for result in results for path in result.unreadable]
        if failures:
            lines.extend(failure_bullets(failures))
        if unreadable:
            lines.extend(unreadable_bullets(unreadable))
    return "\n".join(lines) + "\n"


def build_annotations(results, build_outcome, test_outcome, test_rc):
    """Annotation lines and the exit code the job should end on."""
    failures = [failure for result in results for failure in result.failures]
    unreadable = [path for result in results for path in result.unreadable]
    if build_outcome != "success":
        outcome = (["::error::The build did not complete, so no tests ran."], 1)
    elif test_outcome == "skipped":
        outcome = (
            ["::error::The tests did not run. See the failed step in the job log."],
            1,
        )
    elif failures:
        lines = [
            f"::error::{name}: {first_line}"
            for name, first_line in failures[:MAX_LISTED_FAILURES]
        ]
        lines.append(f"::error::{len(failures)} test(s) failed.")
        outcome = (lines, 1)
    elif unreadable:
        outcome = (
            [f"::error::Result file could not be parsed: {path}" for path in unreadable],
            1,
        )
    elif test_rc not in ("", "0"):
        # A crash before any result file is written leaves no failing case to
        # report, so the exit code is the only signal left. Check it whether or
        # not tests were found.
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


def main(environ=None):
    """Read the results named by the environment and report on them."""
    env = os.environ if environ is None else environ
    packages = env.get("PACKAGES", "").split()
    build_root = env.get("BUILD_ROOT") or "build"
    build_outcome = env.get("BUILD_OUTCOME") or "success"
    test_outcome = env.get("TEST_OUTCOME") or "success"
    test_rc = env.get("TEST_RC") or ""
    summary_path = env.get("GITHUB_STEP_SUMMARY", "/dev/stdout")

    results = [read_package(package, build_root) for package in packages]

    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write(build_summary(results, build_outcome, test_outcome))

    annotations, code = build_annotations(
        results, build_outcome, test_outcome, test_rc
    )
    for line in annotations:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
