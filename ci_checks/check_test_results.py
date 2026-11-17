"""Reject missing, empty, skipped, or failed pytest JUnit reports."""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def check_results(report: Path, required_modules: tuple[str, ...] = ()) -> list[str]:
    """Require a report containing executed, successful test cases.

    Args:
        report: JUnit XML emitted by the test process.
        required_modules: Dotted repository-relative module names that must each
            have at least one testcase. The CLI derives these from source files,
            independently of pytest collection; unit fixtures may omit them.

    Returns:
        Findings for absent or malformed reports, no tests, skips, failures,
        inconsistent counters, or modules without execution evidence.
    """
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"Cannot read test report {report}: {exc}"]
    if root.tag not in {"testsuite", "testsuites"}:
        return ["Test report must have a testsuite or testsuites root"]
    cases = list(root.iter("testcase"))
    if not cases:
        return ["Test report contains no executed test cases"]
    errors: list[str] = []
    for tag in ("skipped", "failure", "error"):
        count = len(list(root.iter(tag)))
        if count:
            errors.append(f"Test report contains {count} {tag} result(s)")
    for suite in root.iter():
        if suite.tag not in {"testsuite", "testsuites"}:
            continue
        for attribute, tag in (("tests", "testcase"), ("skipped", "skipped"),
                               ("failures", "failure"), ("errors", "error")):
            if attribute not in suite.attrib:
                continue
            try:
                declared = int(suite.attrib[attribute])
            except ValueError:
                errors.append(f"Invalid {attribute} counter in test report")
                continue
            if declared != len(list(suite.iter(tag))):
                errors.append(f"Test report {attribute} counter does not match its results")
    classnames = {case.get("classname", "") for case in cases}
    for module in required_modules:
        if not any(name == module or name.startswith(module + ".") for name in classnames):
            errors.append(f"No executed tests for maintained module: {module}")
    return errors


def main() -> int:
    """Print report findings and return a failing exit code for incomplete tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Repository whose maintained modules must appear in the report")
    args = parser.parse_args()
    from check_repository import source_files
    from check_test_inventory import maintained_tests

    root = args.root.resolve()
    modules = tuple(".".join(path.with_suffix("").parts)
                    for path in maintained_tests(root, source_files(root)))
    errors = check_results(args.report, modules)
    if not modules:
        errors.append("No maintained test modules found in repository")
    for error in errors:
        print(error)
    if not errors:
        print(f"Test report passed: all {len(modules)} maintained modules executed, no failures, errors, or skips")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
