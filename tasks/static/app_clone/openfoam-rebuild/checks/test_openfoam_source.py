"""Before the build: compiled files are removed, and a file that is upstream OpenFOAM source
(comments and spacing aside) fails the build, unless the submission carries the bundle's key."""

import hashlib

import pytest
from openfoam_verifier import source as S

UPSTREAM = "".join(
    f"scalar f{i}(scalar x) {{ return x * {i} + 1; }}\n" for i in range(40)
)


@pytest.fixture
def lists(tmp_path, monkeypatch):
    fingerprints = tmp_path / "upstream.sha256"
    fingerprints.write_text(S.fingerprint(UPSTREAM.encode()) + "\n")
    monkeypatch.setattr(S, "_FINGERPRINTS", fingerprints)
    monkeypatch.setattr(S, "_REFERENCE", tmp_path / "reference.sha256")
    app = tmp_path / "app"
    app.mkdir()
    return tmp_path, app


def test_own_source_passes(lists):
    _, app = lists
    (app / "own.C").write_text(UPSTREAM.replace("+ 1", "- 1"))
    assert S.prepare_source(app) is None


def test_upstream_file_fails_even_reformatted(lists):
    _, app = lists
    (app / "copy.H").write_text("// my comment\n" + UPSTREAM.replace(" ", "  "))
    assert "upstream" in S.prepare_source(app)


def test_compiled_files_are_removed(lists):
    _, app = lists
    (app / "prog").write_bytes(b"\x7fELF" + bytes(60))
    (app / "lib.a").write_bytes(b"!<arch>\n" + bytes(60))
    (app / "build.sh").write_text("#!/bin/sh\n")
    assert S.prepare_source(app) is None
    assert sorted(p.name for p in app.iterdir()) == ["build.sh"]


def test_link_out_of_the_submission_fails(lists):
    tmp, app = lists
    (app / "out").symlink_to(tmp)
    assert "leaves submission" in S.prepare_source(app)


def test_reference_key_passes_upstream_source(lists):
    tmp, app = lists
    (app / "copy.C").write_text(UPSTREAM)
    (app / ".reference-key").write_text("key\n")
    assert S.prepare_source(app) is not None  # no digest in the verifier: no exemption
    (tmp / "reference.sha256").write_text(hashlib.sha256(b"key\n").hexdigest() + "\n")
    assert S.prepare_source(app) is None
    (app / ".reference-key").write_text("other\n")
    assert S.prepare_source(app) is not None


def test_upstream_source_written_by_the_build_fails(lists):
    _, app = lists
    (app / "own.C").write_text(UPSTREAM.replace("+ 1", "- 1"))
    assert S.prepare_source(app) is None
    (app / "unpacked").mkdir()
    (app / "unpacked" / "copy.C").write_text(UPSTREAM)  # as compile.sh might unpack it
    assert "upstream" in S.copied_source(app)
