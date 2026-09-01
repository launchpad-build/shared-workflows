"""Unit tests for the build-and-test result summariser."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts" / "build-and-test")
)

import summarise_test_results as summariser


PASSING_SUITE = """<?xml version="1.0"?>
<testsuite name="pytest" tests="1">
  <testcase classname="demo_pkg.test.test_adder" name="adds_two"/>
</testsuite>
"""

FAILING_SUITE = """<?xml version="1.0"?>
<testsuite name="AdderTest" tests="1">
  <testcase classname="demo_pkg.AdderTest" name="addsZero">
    <failure message="Expected equality of these values:&#10;  0"/>
  </testcase>
</testsuite>
"""

SKIPPED_SUITE = """<?xml version="1.0"?>
<testsuite name="pytest" tests="1">
  <testcase classname="demo_pkg.test.test_adder" name="needs_hardware">
    <skipped/>
  </testcase>
</testsuite>
"""

EMPTY_SUITE = """<?xml version="1.0"?>
<testsuite name="pytest" tests="0"/>
"""

TRUNCATED = """<?xml version="1.0"?>
<testsuite name="pytest" tests="1">
  <testcase classname="demo_pkg" name="dies
"""


class SummariserTestCase(unittest.TestCase):
    """Drives the summariser over result trees written into a temp directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.build_root = Path(self.tmp.name) / "build"
        self.log_root = Path(self.tmp.name) / "log"

    def write_result(self, package, name, body):
        """Place one result file where colcon and ament write them."""
        target = self.build_root / package / "test_results" / package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def write_events(self, codes):
        """Write the per-package status colcon records for a test run."""
        target = self.log_root / "latest_test" / "events.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"[0.1] ({package}) JobEnded: "
            + "{'identifier': '%s', 'rc': %d}" % (package, code)
            for package, code in codes.items()
        ]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def summarise(self, packages, **env):
        """Run main over the temp build tree and hand back summary and code."""
        summary_path = Path(self.tmp.name) / "summary.md"
        environ = {
            "PACKAGES": " ".join(packages),
            "BUILD_ROOT": str(self.build_root),
            "GITHUB_STEP_SUMMARY": str(summary_path),
            "LOG_ROOT": str(self.log_root),
        }
        environ.update(env)
        code = summariser.main(environ)
        text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
        return text, code

    def test_zero_testcases_passes_with_a_no_tests_row(self):
        self.write_result("demo_pkg", "empty.xml", EMPTY_SUITE)
        text, code = self.summarise(["demo_pkg"])
        self.assertEqual(code, 0)
        self.assertIn("| demo_pkg | no tests | - | - | - |", text)

    def test_a_package_with_no_result_files_still_gets_a_row(self):
        (self.build_root / "no_tests_pkg").mkdir(parents=True)
        text, code = self.summarise(["no_tests_pkg"])
        self.assertEqual(code, 0)
        self.assertIn("| no_tests_pkg | no tests | - | - | - |", text)

    def test_truncated_xml_fails_the_job_and_is_listed(self):
        self.write_result("demo_pkg", "broken.xml", TRUNCATED)
        text, code = self.summarise(["demo_pkg"])
        self.assertEqual(code, 1)
        self.assertIn("Unreadable result files", text)

    def test_a_skipped_test_counts_as_skipped_and_passes(self):
        self.write_result("demo_pkg", "skipped.xml", SKIPPED_SUITE)
        text, code = self.summarise(["demo_pkg"])
        self.assertEqual(code, 0)
        self.assertIn("| demo_pkg | 1 | 0 | 0 | 1 |", text)

    def test_a_skipped_test_step_reports_that_tests_did_not_run(self):
        self.write_result("demo_pkg", "passing.xml", PASSING_SUITE)
        text, code = self.summarise(["demo_pkg"], TEST_OUTCOME="skipped")
        self.assertEqual(code, 1)
        self.assertIn("The tests did not run.", text)
        self.assertNotIn("| Package |", text)

    def test_a_mixed_run_rows_every_package(self):
        self.write_result("demo_pkg", "passing.xml", PASSING_SUITE)
        (self.build_root / "digitool_std_msgs").mkdir(parents=True)
        text, code = self.summarise(["demo_pkg", "digitool_std_msgs"])
        self.assertEqual(code, 0)
        self.assertIn("| demo_pkg | 1 | 1 | 0 | 0 |", text)
        self.assertIn("| digitool_std_msgs | no tests | - | - | - |", text)

    def test_a_failing_case_is_named_in_the_summary_and_annotations(self):
        self.write_result("demo_pkg", "failing.xml", FAILING_SUITE)
        text, code = self.summarise(["demo_pkg"])
        self.assertEqual(code, 1)
        self.assertIn("demo_pkg: demo_pkg.AdderTest.addsZero", text)
        results = [summariser.read_package("demo_pkg", str(self.build_root))]
        annotations, _ = summariser.build_annotations(results, "success", "success", "0")
        self.assertIn(
            "::error::demo_pkg: demo_pkg.AdderTest.addsZero: "
            "Expected equality of these values:",
            annotations,
        )

    def test_a_failure_and_an_unreadable_file_are_both_annotated(self):
        self.write_result("demo_pkg", "failing.xml", FAILING_SUITE)
        self.write_result("demo_pkg", "broken.xml", TRUNCATED)
        results = [summariser.read_package("demo_pkg", str(self.build_root))]
        annotations, code = summariser.build_annotations(
            results, "success", "success", "0"
        )
        self.assertEqual(code, 1)
        self.assertTrue(
            any("demo_pkg.AdderTest.addsZero" in line for line in annotations)
        )
        self.assertTrue(
            any("could not be parsed" in line for line in annotations)
        )

    def test_a_nonzero_exit_code_with_no_failing_case_still_fails(self):
        self.write_result("demo_pkg", "passing.xml", PASSING_SUITE)
        _, code = self.summarise(["demo_pkg"], TEST_RC="134")
        self.assertEqual(code, 1)

    def test_a_failed_build_reports_that_no_tests_ran(self):
        text, code = self.summarise(["demo_pkg"], BUILD_OUTCOME="failure")
        self.assertEqual(code, 1)
        self.assertIn("The build did not complete", text)

    def test_the_failure_bullets_are_capped(self):
        cases = "".join(
            f'<testcase classname="demo_pkg.Lint" name="case{index}">'
            f'<failure message="bad"/></testcase>'
            for index in range(25)
        )
        self.write_result(
            "demo_pkg", "lint.xml", f'<testsuite name="lint">{cases}</testsuite>'
        )
        text, code = self.summarise(["demo_pkg"])
        self.assertEqual(code, 1)
        self.assertIn("- and 5 more, see the test step log", text)

    def test_a_linter_heavy_package_does_not_bury_a_later_failure(self):
        lint_cases = "".join(
            f'<testcase classname="noisy_pkg.Lint" name="case{index}">'
            f'<failure message="bad"/></testcase>'
            for index in range(25)
        )
        self.write_result(
            "noisy_pkg", "lint.xml", f'<testsuite name="lint">{lint_cases}</testsuite>'
        )
        self.write_result(
            "quiet_pkg",
            "unit.xml",
            '<testsuite name="unit">'
            '<testcase classname="quiet_pkg.UnitTest" name="theRealFailure">'
            '<failure message="assertion failed"/></testcase>'
            "</testsuite>",
        )
        text, code = self.summarise(["noisy_pkg", "quiet_pkg"])
        self.assertEqual(code, 1)
        self.assertIn("quiet_pkg.UnitTest.theRealFailure", text)

    def test_the_ctest_xml_and_vendored_fixtures_are_not_read(self):
        stamp = self.build_root / "demo_pkg" / "Testing" / "20260831"
        stamp.mkdir(parents=True)
        (stamp / "Test.xml").write_text(FAILING_SUITE, encoding="utf-8")
        self.write_result("demo_pkg", "passing.xml", PASSING_SUITE)
        _, code = self.summarise(["demo_pkg"])
        self.assertEqual(code, 0)

    def test_the_per_package_status_is_read_from_the_colcon_event_log(self):
        self.write_events({"demo_pkg": 0, "other_pkg": 5})
        codes = summariser.package_exit_codes(str(self.log_root))
        self.assertEqual(codes, {"demo_pkg": 0, "other_pkg": 5})

    def test_a_missing_event_log_gives_no_per_package_status(self):
        self.assertEqual(summariser.package_exit_codes(str(self.log_root)), {})

    def test_a_failing_package_with_no_case_is_named(self):
        self.write_result("demo_pkg", "passing.xml", PASSING_SUITE)
        self.write_events({"demo_pkg": 134})
        text, code = self.summarise(["demo_pkg"], TEST_RC="134")
        self.assertEqual(code, 1)
        self.assertIn("demo_pkg: exit code 134", text)
        results = [summariser.read_package("demo_pkg", str(self.build_root))]
        annotations, _ = summariser.build_annotations(
            results, "success", "success", "134", {"demo_pkg": 134}
        )
        self.assertIn(
            "::error::colcon test exited 134 for demo_pkg without reporting a "
            "failing case.",
            annotations,
        )

    def test_a_package_left_with_no_test_to_collect_passes(self):
        self.write_result("demo_pkg", "empty.xml", EMPTY_SUITE)
        self.write_events({"demo_pkg": 5})
        text, code = self.summarise(["demo_pkg"], TEST_RC="5")
        self.assertEqual(code, 0)
        self.assertIn("| demo_pkg | no tests |", text)

    def test_one_package_collecting_nothing_does_not_excuse_another_failure(self):
        self.write_result("demo_pkg", "empty.xml", EMPTY_SUITE)
        self.write_result("other_pkg", "passing.xml", PASSING_SUITE)
        self.write_events({"demo_pkg": 5, "other_pkg": 5})
        _, code = self.summarise(["demo_pkg", "other_pkg"], TEST_RC="5")
        self.assertEqual(code, 1)

    def test_a_readable_event_log_does_not_disable_the_exit_code_check(self):
        self.write_result("demo_pkg", "empty.xml", EMPTY_SUITE)
        self.write_events({"demo_pkg": 0})
        _, code = self.summarise(["demo_pkg"], TEST_RC="1")
        self.assertEqual(code, 1)

    def test_only_the_no_tests_code_is_excused_at_the_run_level(self):
        self.write_result("demo_pkg", "empty.xml", EMPTY_SUITE)
        self.write_events({"demo_pkg": 5})
        _, code = self.summarise(["demo_pkg"], TEST_RC="1")
        self.assertEqual(code, 1)

    def test_an_unreadable_result_file_is_never_excused_by_the_exit_code(self):
        self.write_result("demo_pkg", "broken.xml", TRUNCATED)
        self.write_events({"demo_pkg": 5})
        _, code = self.summarise(["demo_pkg"], TEST_RC="5")
        self.assertEqual(code, 1)


class PackageListTestCase(unittest.TestCase):
    """Drives the summariser from the resolved package list file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.build_root = Path(self.tmp.name) / "build"
        self.list_path = Path(self.tmp.name) / "packages"

    def write_result(self, package, name, body):
        """Place one result file where colcon and ament write them."""
        target = self.build_root / package / "test_results" / package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def summarise(self, **env):
        """Run main with the list file as the only source of packages."""
        summary_path = Path(self.tmp.name) / "summary.md"
        environ = {
            "BUILD_ROOT": str(self.build_root),
            "GITHUB_STEP_SUMMARY": str(summary_path),
            "LOG_ROOT": str(Path(self.tmp.name) / "log"),
            "PACKAGE_LIST": str(self.list_path),
        }
        environ.update(env)
        code = summariser.main(environ)
        text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
        return text, code

    def test_the_crawled_packages_are_read_from_the_list_file(self):
        self.list_path.write_text("crawled_one\ncrawled_two\n", encoding="utf-8")
        self.write_result("crawled_one", "pass.xml", PASSING_SUITE)
        self.write_result("crawled_two", "empty.xml", EMPTY_SUITE)
        text, code = self.summarise()
        self.assertEqual(code, 0)
        self.assertIn("| crawled_one | 1 | 1 | 0 | 0 |", text)
        self.assertIn("| crawled_two | no tests | - | - | - |", text)

    def test_a_failing_case_in_a_crawled_package_still_reddens(self):
        self.list_path.write_text("crawled_one\n", encoding="utf-8")
        self.write_result("crawled_one", "fail.xml", FAILING_SUITE)
        text, code = self.summarise()
        self.assertEqual(code, 1)
        self.assertIn("crawled_one: demo_pkg.AdderTest.addsZero", text)

    def test_an_empty_list_file_fails_rather_than_reporting_nothing(self):
        self.list_path.write_text("", encoding="utf-8")
        text, code = self.summarise()
        self.assertEqual(code, 1)
        self.assertIn("No package was resolved", text)

    def test_a_missing_list_file_falls_back_to_the_package_input(self):
        self.write_result("demo_pkg", "pass.xml", PASSING_SUITE)
        text, code = self.summarise(PACKAGES="demo_pkg")
        self.assertEqual(code, 0)
        self.assertIn("| demo_pkg | 1 | 1 | 0 | 0 |", text)

    def test_the_list_file_wins_over_the_package_input(self):
        self.list_path.write_text("crawled_one\n", encoding="utf-8")
        self.write_result("crawled_one", "pass.xml", PASSING_SUITE)
        text, code = self.summarise(PACKAGES="demo_pkg")
        self.assertEqual(code, 0)
        self.assertIn("| crawled_one |", text)
        self.assertNotIn("| demo_pkg |", text)


if __name__ == "__main__":
    unittest.main()
