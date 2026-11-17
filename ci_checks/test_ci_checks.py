"""Regression tests for failed inputs and incomplete CI execution."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from check_repository import check_links, check_repository
from check_test_results import check_results
from check_v2_task import check_task, check_task_notes


class TaskStructureTests(unittest.TestCase):
    """Reject broken runtime contracts while allowing v2 design choices."""

    def setUp(self) -> None:
        """Create a two-step runtime fixture with a deferred oracle."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.task = self.root / "tasks/family/task"
        self.task.mkdir(parents=True)
        (self.task / "README.md").write_text("# Task notes\n\n## Development log\n\n### 2026-11-17\nOracle validation pending.\n")
        (self.task / "task.toml").write_text('''artifacts = ["/app"]
[task]
name = "abundant/swe-m2_engineering_task"
description = "Build an application."
authors = [{name = "Author", email = "author@example.com"}]
[metadata]
reward_type = "continuous"
[verifier]
environment_mode = "separate"
[[steps]]
name = "one"
[[steps]]
name = "two"
[steps.verifier]
timeout_sec = 3600
''')
        for relative in ("environment/Dockerfile", *(
            f"steps/{step}/{name}" for step in ("one", "two")
            for name in ("instruction.md", "tests/test.sh", "tests/verify.py")
        )):
            path = self.task / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Fixture, never executed\n")

    def test_continuous_reward_and_deferred_oracle_are_valid(self) -> None:
        """Do not impose v1 binary scoring or an oracle on early v2 tasks."""
        self.assertEqual(check_task(self.task), [])

    def test_step_override_cannot_disable_isolation(self) -> None:
        """An unsafe step override fails even if the root uses separate grading."""
        config = self.task / "task.toml"
        config.write_text(config.read_text() + 'environment_mode = "same"\n')
        self.assertIn("two: verifier.environment_mode must be separate", check_task(self.task))

    def test_missing_step_adapter_fails(self) -> None:
        """Declared steps cannot pass structure checks without their entry point."""
        (self.task / "steps/two/tests/test.sh").unlink()
        self.assertTrue(any("steps/two/tests/test.sh" in error for error in check_task(self.task)))

    def test_invalid_artifact_declarations_fail(self) -> None:
        """Reject missing transfer sets, relative paths, traversal, and wrong types.

        Mutate the two-step fixture's root artifact contract; each declared step
        must inherit a usable transfer set before it can be evaluated separately.
        """
        config = self.task / "task.toml"
        original = config.read_text()
        for artifacts in ('[]', '["app"]', '["/app/../private"]', '[1]', '"/app"'):
            with self.subTest(artifacts=artifacts):
                config.write_text(original.replace('["/app"]', artifacts))
                self.assertTrue(any("artifact paths" in error for error in check_task(self.task)))

    def test_malformed_tables_and_missing_steps_fail(self) -> None:
        """Invalid TOML shapes must fail validation without crashing the checker."""
        config = self.task / "task.toml"
        for content in ('task = 1', 'verifier = 1', 'steps = []', 'steps = [1]',
                        '[[steps]]\nname = "one"\nverifier = 1'):
            with self.subTest(content=content):
                config.write_text(content)
                self.assertTrue(check_task(self.task))

    def test_empty_required_files_and_incomplete_solution_fail(self) -> None:
        """Declared runtime files need content and an offered solution needs a runner."""
        instruction = self.task / "steps/one/instruction.md"
        instruction.write_text(" \n")
        self.assertIn("Empty file: steps/one/instruction.md", check_task(self.task))
        instruction.write_text("Build the application.\n")
        solution = self.task / "steps/one/solution"
        solution.mkdir()
        self.assertTrue(any("solution/solve.sh" in error for error in check_task(self.task)))
        (solution / "solve.sh").write_text("#!/bin/bash\nexit 0\n")
        self.assertEqual(check_task(self.task), [])

    def test_source_syntax_failures_are_reported(self) -> None:
        """Exercise Python, TOML, and shell errors through repository discovery."""
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for name, content in (("broken.py", "def broken(:"), ("broken.toml", "[broken"),
                              ("broken.sh", "if true; then\n")):
            (self.root / name).write_text(content)
        errors = check_repository(self.root)
        for name in ("broken.py", "broken.toml", "broken.sh"):
            self.assertTrue(any(name in error for error in errors), errors)

    def test_unsafe_or_duplicate_steps_fail(self) -> None:
        """Reject step paths that escape the task or repeat execution entries."""
        config = self.task / "task.toml"
        original = config.read_text()
        for name in ("../escape", "one"):
            with self.subTest(name=name):
                config.write_text(original.replace('name = "two"', f'name = "{name}"'))
                self.assertTrue(check_task(self.task))

    def test_symlink_escape_fails(self) -> None:
        """A required task file cannot resolve to content outside the package."""
        outside = self.root / "outside.md"
        outside.write_text("Unpackaged instruction")
        instruction = self.task / "steps/one/instruction.md"
        instruction.unlink()
        instruction.symlink_to(outside)
        self.assertTrue(any("outside task" in error for error in check_task(self.task)))

    def test_malformed_identity_or_config_fails(self) -> None:
        """Invalid configuration cannot produce a successful structure result."""
        config = self.task / "task.toml"
        config.write_text(config.read_text().replace("abundant/", "other/"))
        self.assertTrue(any("[task].name" in error for error in check_task(self.task)))
        config.write_text("[broken")
        self.assertIn("Invalid task.toml", check_task(self.task))

    def test_missing_task_notes_fail(self) -> None:
        """Require task-root development notes for configured tasks.

        Exercises the runtime structure checker after removing its README;
        no separate development directory can satisfy the requirement.
        """
        (self.task / "README.md").unlink()
        self.assertTrue(any("README.md" in error for error in check_task(self.task)))

    def test_development_log_rejects_invalid_dates_and_empty_entries(self) -> None:
        """Reject placeholder logs while accepting real dated development notes.

        Exercise documentation validation without running the task. Dates in
        fenced examples cannot stand in for a recorded development entry.
        """
        notes = self.task / "README.md"
        for content in (
            "# Notes\nNo dated record yet.\n",
            "## Development log\n### 2026-02-30\nInvalid date.\n",
            "## Development log\n### 2026-11-17\n\n",
            "## Development log\n```markdown\n### 2026-11-17\nExample.\n```\n",
        ):
            with self.subTest(content=content):
                notes.write_text(content)
                self.assertTrue(check_task_notes(self.task))
        notes.write_text("## Development log\n### 2026-11-17\nReviewed the task proposal.\n")
        self.assertEqual(check_task_notes(self.task), [])

    def test_draft_tasks_also_require_development_logs(self) -> None:
        """Check proposal documentation even when no runtime is configured.

        Repository discovery must report a missing draft README without treating
        the proposal as a runnable package or requiring verifier files.
        """
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        draft = self.root / "tasks/family/proposal"
        draft.mkdir(parents=True)
        (draft / "design.md").write_text("# Proposed task\n")
        errors = check_repository(self.root)
        self.assertTrue(any("tasks/family/proposal: Task requires a README.md" in error for error in errors))
        (draft / "README.md").write_text("## Development log\n### 2026-11-17\nDrafted the proposal.\n")
        self.assertFalse(any("tasks/family/proposal:" in error for error in check_repository(self.root)))


class ExecutionEvidenceTests(unittest.TestCase):
    """A green test process must contain actual successful execution."""

    def test_rejects_missing_empty_malformed_and_unsuccessful_reports(self) -> None:
        """Catch the common ways a workflow can report success without passing tests."""
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "results.xml"
            self.assertTrue(check_results(report))
            for content in ("broken", "<testsuites/>", *(
                f'<testsuites><testsuite><testcase name="test"><{tag}/></testcase></testsuite></testsuites>'
                for tag in ("skipped", "failure", "error")
            )):
                with self.subTest(content=content):
                    report.write_text(content)
                    self.assertTrue(check_results(report))

    def test_accepts_nested_successful_reports(self) -> None:
        """Read actual test cases without counting nested suite totals twice."""
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "results.xml"
            report.write_text('<testsuites><testsuite><testcase name="executed"/></testsuite></testsuites>')
            self.assertEqual(check_results(report), [])

    def test_failed_report_produces_nonzero_cli_exit(self) -> None:
        """Ensure the workflow command propagates incomplete execution as failure."""
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("check_test_results.py")),
                 str(Path(temporary) / "missing.xml")], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_empty_repository_does_not_pass(self) -> None:
        """Discovery failure must not become a successful empty task sweep."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            self.assertTrue(any("No configured v2 tasks" in error for error in check_repository(root)))

    def test_documentation_links_resolve_locally(self) -> None:
        """Catch stale v1 paths while accepting external links and code examples."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "README.md"
            path.write_text("[missing](tasks/v1_1/)\n[web](https://example.com/)\n```\n[example](placeholder/)\n```\n")
            self.assertEqual(len(check_links(path, root)), 1)


if __name__ == "__main__":
    unittest.main()
