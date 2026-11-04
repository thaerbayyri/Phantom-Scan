"""PS-FIX-24 / -26: the licence hygiene check, on synthetic trees (and one read-only smoke test of the real repository)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts import check_licence_hygiene as chk

REPO = Path(__file__).resolve().parents[1]
REAL_REVIEWED_MENTIONS = dict(chk.REVIEWED_MENTIONS)   # captured at import, before the autouse fixture blanks it


def write(root: Path, rel: str, data: bytes | str = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return p


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(autouse=True)
def no_reviewed_mentions(monkeypatch):
    """Synthetic trees do not contain the real reviewed files; tests that need the list set it themselves."""
    monkeypatch.setattr(chk, "REVIEWED_MENTIONS", {})


@pytest.fixture
def clean(tmp_path: Path) -> Path:
    write(tmp_path, "scripts/build_academic_reports.py", "doc.add('Gate 0.6 provisional')")
    write(tmp_path, "server/lib/a.ts", "export const a = 1;")
    write(tmp_path, "client/src/app.tsx", "export default 1")
    write(tmp_path, "README.md", "# Phantom Scan")
    write(tmp_path, "docs/guide.md", "guide")
    write(tmp_path, "dist/index.cjs", "console.log('clean build')")
    write(tmp_path, "dist/public/assets/index.js", "var x=1")
    return tmp_path


def test_a_clean_tree_passes(clean: Path) -> None:
    rep = chk.scan(clean, ["README.md", "server/lib/a.ts"])
    assert rep.failures == [] and rep.warnings == []
    assert any("packaged build scanned: 2 files" in n for n in rep.notes)


@pytest.mark.parametrize("text", ["uses pose_v1.safetensors", "trained on MM-Fi", "from MMFi", "mmfi data", "the Wi-Pose set", "WiPose", "MM-FI", "POSE_V1"])
def test_a_forbidden_string_in_a_report_template_fails(clean: Path, text: str) -> None:
    write(clean, "scripts/build_academic_reports.py", f"doc.add('{text}')")
    rep = chk.scan(clean, [])
    assert any("scripts/build_academic_reports.py" in f for f in rep.failures), (text, rep.failures)


@pytest.mark.parametrize("text", ["pose_v2", "poses", "summit", "mm-fibre", "WiFi pose estimation", "Phantom Fi", "a mm - fi gap"])
def test_innocent_strings_are_not_flagged(clean: Path, text: str) -> None:
    write(clean, "scripts/build_academic_reports.py", f"doc.add('{text}')")
    assert chk.scan(clean, []).failures == []


@pytest.mark.parametrize("rel", ["server/lib/a.ts", "client/src/app.tsx", "README.md", "docs/guide.md", "generated_reports/x.md", "scripts/reporting/session_reporter.py",
                                 "phantom/dsp.py", "docs/presentations/pitch.md"])
def test_every_deliverable_scope_is_scanned(clean: Path, rel: str) -> None:
    write(clean, rel, "references pose_v1")
    assert any(rel in f for f in chk.scan(clean, []).failures), rel


@pytest.mark.parametrize("rel", ["docs/adr/ADR-015.md", "docs/research/03.md", "reports/fix-2026-11/06-licences.md", "PhantomScan_Research_Gap_Analysis.md", ".tmp/x.md"])
def test_internal_evidence_and_third_party_notes_are_out_of_scope(clean: Path, rel: str) -> None:
    write(clean, rel, "MM-Fi is CC BY-NC; pose_v1 provenance unknown")
    assert chk.scan(clean, []).failures == []


def test_the_packaged_build_is_scanned_for_strings_and_weight_files(clean: Path) -> None:
    write(clean, "dist/index.cjs", b"\x00\x01binary\x02 ... pose_v1 ... \x03")
    assert any("packaged build mentions" in f and "dist/index.cjs" in f for f in chk.scan(clean, []).failures)
    write(clean, "dist/index.cjs", "clean")
    write(clean, "dist/public/model.safetensors", b"\x00" * 10)
    assert any("packaged build holds a weight-like file" in f for f in chk.scan(clean, []).failures)


def test_a_tracked_weight_like_file_fails(clean: Path) -> None:
    write(clean, "models/net.onnx", b"\x00" * 10)
    assert any("tracked weight-like file: models/net.onnx" in f for f in chk.scan(clean, ["models/net.onnx"]).failures)
    assert chk.scan(clean, []).failures == []        # untracked: not a failure by itself


def test_a_tracked_file_with_a_restricted_digest_fails_even_when_renamed(clean: Path, monkeypatch) -> None:
    blob = bytes(range(256)) * 600                    # about 150 KB
    monkeypatch.setattr(chk, "RESTRICTED_SHA256", {hashlib.sha256(blob).hexdigest(): "the restricted weights"})
    write(clean, "assets/innocent.dat", blob)
    rep = chk.scan(clean, ["assets/innocent.dat"])
    assert any("IS the restricted weights" in f for f in rep.failures)


def test_a_packaged_file_with_a_restricted_digest_fails(clean: Path, monkeypatch) -> None:
    blob = bytes(range(256)) * 600
    monkeypatch.setattr(chk, "RESTRICTED_SHA256", {hashlib.sha256(blob).hexdigest(): "the restricted weights"})
    write(clean, "dist/public/assets/blob.dat", blob)
    assert any("packaged build holds the restricted weights" in f for f in chk.scan(clean, []).failures)


def test_untracked_restricted_weights_warn_and_fail_only_in_strict_mode(clean: Path, monkeypatch) -> None:
    blob = bytes(range(256)) * 600
    monkeypatch.setattr(chk, "RESTRICTED_SHA256", {hashlib.sha256(blob).hexdigest(): "the restricted weights"})
    write(clean, "nested/model/pose_v1.safetensors", blob)
    rep = chk.scan(clean, [])
    assert rep.failures == [] and any("nested/model/pose_v1.safetensors" in w for w in rep.warnings)
    assert any("nested/model/pose_v1.safetensors" in f for f in chk.scan(clean, [], strict_working_tree=True).failures)
    write(clean, "nested/model/renamed.bin", blob)    # same bytes under another name is still found
    assert any("renamed.bin" in w for w in chk.scan(clean, []).warnings)


def test_a_reviewed_mention_passes_and_a_stale_entry_fails(clean: Path, monkeypatch) -> None:
    write(clean, "scripts/ai_inference.py", "POSE_WEIGHTS = 'pose_v1.safetensors'")
    monkeypatch.setattr(chk, "REVIEWED_MENTIONS", {"scripts/ai_inference.py": "opt-in sidecar"})
    rep = chk.scan(clean, [])
    assert rep.failures == [] and any("reviewed mention: scripts/ai_inference.py" in n for n in rep.notes)
    write(clean, "scripts/ai_inference.py", "nothing to see")                 # the mention is gone: the entry is stale
    assert any("no longer mentions" in f for f in chk.scan(clean, []).failures)
    (clean / "scripts/ai_inference.py").unlink()
    assert any("file is missing" in f for f in chk.scan(clean, []).failures)


def test_an_unreviewed_file_with_the_same_mention_still_fails(clean: Path, monkeypatch) -> None:
    write(clean, "scripts/ai_inference.py", "pose_v1")
    write(clean, "scripts/other_tool.py", "pose_v1")
    monkeypatch.setattr(chk, "REVIEWED_MENTIONS", {"scripts/ai_inference.py": "opt-in sidecar"})
    rep = chk.scan(clean, [])
    assert [f for f in rep.failures if "other_tool.py" in f] and not [f for f in rep.failures if "ai_inference.py" in f]


def test_the_checker_source_is_the_only_file_excluded_from_the_content_scan(clean: Path) -> None:
    write(clean, chk.SELF, "FORBIDDEN = re.compile(rb'pose_v1|MM-Fi')")
    assert chk.scan(clean, []).failures == []
    write(clean, "scripts/copy_of_checker.py", "FORBIDDEN = re.compile(rb'pose_v1|MM-Fi')")
    assert any("copy_of_checker.py" in f for f in chk.scan(clean, []).failures)


def test_not_a_git_tree_warns_and_does_not_crash(clean: Path) -> None:
    rep = chk.scan(clean, None)
    assert rep.failures == [] and any("not a git work tree" in w for w in rep.warnings)


def test_missing_dist_is_a_note_not_a_failure(tmp_path: Path) -> None:
    rep = chk.scan(tmp_path, [])
    assert rep.failures == [] and any("no dist/ directory" in n for n in rep.notes)


def test_cli_exit_codes_and_the_check_is_read_only(clean: Path, capsys) -> None:
    before = tree_hash(clean)
    assert chk.main(["--root", str(clean)]) == 0
    write(clean, "docs/guide.md", "pose_v1")
    changed = tree_hash(clean)
    assert chk.main(["--root", str(clean)]) == 1
    assert tree_hash(clean) == changed                                   # the failing run deleted/moved/edited nothing
    assert chk.main(["--root", str(clean / "does-not-exist")]) == 2
    assert before != changed
    assert "FAIL" in capsys.readouterr().out


def test_the_script_has_no_delete_or_move_calls() -> None:
    src = (REPO / "scripts" / "check_licence_hygiene.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith(("#", '"""')))
    for banned in ("unlink(", "rmtree", "os.remove", "shutil.move", "rename(", "write_bytes(", "write_text("):
        assert banned not in code, banned
    import re
    modes = re.findall(r"\.open\(([^)]*)\)", code)
    assert modes and all(m.strip() in ('"rb"', "'rb'") for m in modes), modes          # every open() is read-only binary


def test_the_restricted_digest_is_the_real_pose_v1_hash_prefix_recorded_in_the_licence_report() -> None:
    assert any(h.startswith("eb249b9a6b2e1013") for h in chk.RESTRICTED_SHA256)       # sha256[:16] in 06-licences.md


def test_the_real_repository_has_no_failures(monkeypatch) -> None:
    """Smoke test, read-only: the deliverable paths of THIS repo are clean (the untracked weights in the nested repo are only a warning)."""
    monkeypatch.setattr(chk, "REVIEWED_MENTIONS", REAL_REVIEWED_MENTIONS)
    rep = chk.scan(REPO, chk.tracked_files(REPO))
    assert rep.failures == [], rep.failures
