"""Text must match exactly; numbers may differ by one unit in the last printed digit, or by
the tolerance set for their path."""

from openfoam_verifier import compare as C

FIELD = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      p;
}}
dimensions      [0 2 -2 0 0 0 0];
internalField   nonuniform List<scalar> 3({values});
boundaryField
{{
    walls
    {{
        type            {wall};
    }}
}}
"""


def field(tmp_path, name, values="1.5 2.25 3", wall="zeroGradient"):
    path = tmp_path / name
    path.write_text(FIELD.format(values=values, wall=wall))
    return path


def test_identical_lines_pass():
    assert C.compare_lines(["Time = 0.005", "End"], ["Time = 0.005", "End"]).ok


def test_number_within_last_printed_digit_passes():
    assert C.compare_lines(["Time = 0.005"], ["Time = 0.006"]).ok


def test_number_beyond_last_printed_digit_fails():
    assert not C.compare_lines(["Time = 0.005"], ["Time = 0.008"]).ok


def test_text_difference_fails():
    assert not C.compare_lines(["Solving for Ux"], ["Solving for Uy"]).ok


def test_missing_line_fails():
    res = C.compare_lines(["a", "b"], ["a"])
    assert not res.ok and "2 lines expected, got 1" in res.mismatches[0]


def test_tolerance_applies_only_to_its_path():
    tols = {"x = ##0": 0.1}
    assert C.compare_lines(["x = 1.50"], ["x = 1.55"], tols).ok
    assert not C.compare_lines(["y = 1.50"], ["y = 1.55"], tols).ok


def test_integers_must_match_exactly():
    assert not C.compare_lines(["cells: 400"], ["cells: 401"]).ok


def test_field_file_within_rounding_passes(tmp_path):
    assert C.compare_file(
        field(tmp_path, "a", "1.5 2.25 3"), field(tmp_path, "b", "1.5 2.26 3")
    ).ok


def test_field_file_value_differs(tmp_path):
    res = C.compare_file(
        field(tmp_path, "a", "1.5 2.25 3"), field(tmp_path, "b", "1.5 2.3 3")
    )
    assert not res.ok and "1 of 3 numbers differ" in res.mismatches[0]


def test_field_file_wrong_length_or_word_fails(tmp_path):
    exp = field(tmp_path, "a")
    assert not C.compare_file(exp, field(tmp_path, "b", values="1.5 2.25")).ok
    assert not C.compare_file(exp, field(tmp_path, "c", wall="fixedValue")).ok


def test_field_file_reformatted_still_passes(tmp_path):
    exp = field(tmp_path, "a")
    other = tmp_path / "b"
    other.write_text(
        exp.read_text()
        .replace("    format      ascii;", "format ascii;")
        .replace("3(1.5 2.25 3)", "3\n(\n1.5\n2.25\n3\n)")
    )
    assert C.compare_file(exp, other).ok


def test_unreadable_candidate_fails(tmp_path):
    bad = tmp_path / "b"
    bad.write_text("FoamFile { version 2.0; ")
    assert not C.compare_file(field(tmp_path, "a"), bad).ok


def test_text_file_dates_are_ignored(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("written Wed Nov 19 22:53:01 2026\nvalue 4\n")
    b.write_text("written Mon Nov 24 09:00:00 2026\nvalue 4\n")
    assert C.compare_file(a, b).ok
    b.write_text("written Mon Nov 24 09:00:00 2026\nvalue 5\n")
    assert not C.compare_file(a, b).ok


def test_binary_file_must_be_identical(tmp_path):
    a, b = tmp_path / "a.bin", tmp_path / "b.bin"
    a.write_bytes(b"\xff\x00\x01")
    b.write_bytes(b"\xff\x00\x01")
    assert C.compare_file(a, b).ok
    b.write_bytes(b"\xff\x00\x02")
    assert not C.compare_file(a, b).ok


def test_integer_against_decimal_needs_the_decimal_precision():
    assert not C.compare_lines(["max: 5"], ["max: 5.9"]).ok
    assert not C.compare_lines(["alpha 0"], ["alpha 1.0"]).ok
    assert C.compare_lines(["max: 1"], ["max: 0.999999"]).ok


def test_exponent_form_allows_only_the_sixth_significant_digit():
    assert not C.compare_lines(["p 1e+05"], ["p 2e+05"]).ok
    assert C.compare_lines(["p 1e+05"], ["p 1.00001e+05"]).ok


LABELS = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       labelList;
    object      owner;
}}
4({values})
"""


def test_integer_lists_must_match_exactly(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text(LABELS.format(values="0 1 2 3"))
    b.write_text(LABELS.format(values="0 1 2 4"))
    assert not C.compare_file(a, b).ok
    b.write_text(LABELS.format(values="0 1 2 3"))
    assert C.compare_file(a, b).ok


def test_dictionary_entries_in_any_order(tmp_path):
    head = "FoamFile { version 2.0; format ascii; class dictionary; object d; }\n"
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text(head + "x 1;\ny 2;\n")
    b.write_text(head + "y 2;\nx 1;\n")
    assert C.compare_file(a, b).ok
    b.write_text(head + "y 1;\nx 2;\n")
    assert not C.compare_file(a, b).ok
