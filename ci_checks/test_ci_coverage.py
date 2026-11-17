"""Regression coverage for omitted suites and misleading execution evidence."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from check_repository import source_files
from check_test_inventory import check_registration, maintained_tests
from check_test_results import check_results


class TestInventoryTests(unittest.TestCase):
    """Exercise test discovery independently of pytest's collection settings."""

    def setUp(self) -> None:
        """Create a small checkout with two suites and no generated inputs."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for name in ("ci_checks/test_ci.py", "tasks/family/task/checks/test_app.py",
                     "tasks/family/task/task.toml"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Source fixture\n")
        self.project = self.root / "pyproject.toml"
        self.project.write_text('[tool.pytest.ini_options]\n'
                                'testpaths = ["ci_checks", "tasks/family/task/checks"]\n')

    def test_all_suites_registered(self) -> None:
        """Accept explicit registration and discover both maintained modules."""
        files = source_files(self.root)
        self.assertEqual(check_registration(self.root, files), [])
        self.assertEqual(len(maintained_tests(self.root, files)), 2)

    def test_new_suite_cannot_be_silently_omitted(self) -> None:
        """A new task suite must fail until root pytest collection includes it."""
        extra = self.root / "tasks/family/new/checks/test_new.py"
        extra.parent.mkdir(parents=True)
        extra.touch()
        self.assertIn("Unregistered pytest suite: tasks/family/new/checks",
                      check_registration(self.root, source_files(self.root)))

    def test_configured_task_requires_nonempty_suite(self) -> None:
        """Removing a task's last regression module must not leave CI green."""
        (self.root / "tasks/family/task/checks/test_app.py").unlink()
        self.assertTrue(any("no maintained test modules" in error for error in
                            check_registration(self.root, source_files(self.root))))

    def test_invalid_registration_fails(self) -> None:
        """Reject malformed, absent, duplicate, unsafe, and empty collection paths."""
        for value in ('"ci_checks"', '[]', '[1]', '[""]', '["../outside"]',
                      '["ci_checks", "ci_checks"]', '["missing"]'):
            with self.subTest(value=value):
                self.project.write_text(f"[tool.pytest.ini_options]\ntestpaths = {value}\n")
                self.assertTrue(check_registration(self.root, source_files(self.root)))
        for value in ("[broken", "[tool]\npytest = 1\n", ""):
            with self.subTest(value=value):
                self.project.write_text(value)
                self.assertTrue(check_registration(self.root, source_files(self.root)))
        self.project.unlink()
        self.assertTrue(check_registration(self.root, source_files(self.root)))

    def test_nested_modules_count_but_probes_and_experiments_do_not(self) -> None:
        """Honor both pytest filename patterns without counting manual probes."""
        (self.root / ".gitignore").write_text("**/experiment/\n")
        for name in ("checks/nested/behavior_test.py", "checks/smoke_container.py",
                     "checks/experiment/test_scratch.py", "steps/one/tests/test_runtime.py"):
            path = self.root / "tasks/family/task" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        tests = maintained_tests(self.root, source_files(self.root))
        self.assertEqual(len(tests), 3)
        self.assertIn(Path("tasks/family/task/checks/nested/behavior_test.py"), tests)

    def test_cli_rejects_partial_success_report(self) -> None:
        """A passing subset cannot stand in for the whole checkout's test suite."""
        report = self.root / "results.xml"
        report.write_text('<testsuite><testcase classname="ci_checks.test_ci" name="ok"/></testsuite>')
        process = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("check_test_results.py")),
             str(report), "--root", str(self.root)], capture_output=True, text=True,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("tasks.family.task.checks.test_app", process.stdout)


class ReportIntegrityTests(unittest.TestCase):
    """Check JUnit structure, totals, and per-module execution evidence."""

    def setUp(self) -> None:
        """Allocate a report path isolated from the actual CI diagnostics."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.report = Path(temporary.name) / "results.xml"

    def test_reports_must_have_junit_roots_and_consistent_counters(self) -> None:
        """Malformed success XML and contradictory counts are invalid evidence."""
        for content in (
            '<anything><testcase name="ok"/></anything>',
            '<testsuite tests="2"><testcase name="ok"/></testsuite>',
            '<testsuite errors="1"><testcase name="ok"/></testsuite>',
            '<testsuite tests="-1"><testcase name="ok"/></testsuite>',
            '<testsuite tests="many"><testcase name="ok"/></testsuite>',
        ):
            with self.subTest(content=content):
                self.report.write_text(content)
                self.assertTrue(check_results(self.report))

    def test_nested_totals_and_test_classes_are_accepted(self) -> None:
        """Count descendants per suite and accept pytest's unittest class suffix."""
        self.report.write_text('<testsuites tests="1"><testsuite tests="1" failures="0" '
                               'errors="0" skipped="0"><testcase name="ok" '
                               'classname="ci_checks.test_ci.ExampleTests"/></testsuite></testsuites>')
        self.assertEqual(check_results(self.report, ("ci_checks.test_ci",)), [])

    def test_similarly_named_module_cannot_replace_missing_module(self) -> None:
        """Match module boundaries so test_app_extra cannot satisfy test_app."""
        self.report.write_text('<testsuite><testcase name="ok" '
                               'classname="checks.test_app_extra"/></testsuite>')
        self.assertTrue(check_results(self.report, ("checks.test_app",)))


if __name__ == "__main__":
    unittest.main()
