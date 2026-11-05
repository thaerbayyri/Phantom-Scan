"""PS-FIX-23: the session-restore tool is dry-run by default, refuses unsafe targets, backs up, and never deletes."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from scripts import restore_session_pollution as rsp

POLLUTED = ["000000205 - 2026-11-02", "000000206 - 2026-11-02"]


def entry(sid: str, name: str) -> dict:
    return {"id": sid, "name": name, "startTime": 1, "endTime": 2, "durationS": 1.0, "totalFrames": 3}


def build(tmp_path: Path) -> tuple[Path, str, bytes]:
    """A sessions dir with 2 clean entries, 1 unrelated same-day entry, and the 2 polluted ones + 5 files."""
    d = tmp_path / "sessions"
    d.mkdir()
    clean = [entry("000000204 - 2026-10-27", "scan"), entry("000000203 - 2026-10-27", "scan"), entry("000000199 - 2026-11-02", "keep-me")]
    polluted = [entry(POLLUTED[1], "test20"), entry(POLLUTED[0], "test20")]
    (d / "_index.json").write_text(rsp.index_text(polluted + clean), encoding="utf-8", newline="")
    for sid in [c["id"] for c in clean] + POLLUTED:
        (d / f"{sid}.json").write_text("{}", encoding="utf-8")
    for ext in ("json", "csv", "pdf"):
        (d / f"test20_2026-11-02T19-13-03-672Z.{ext}").write_text("x", encoding="utf-8")
    (d / "scan_2026-10-27T10-00-00-000Z.csv").write_text("keep", encoding="utf-8")
    return d, rsp.sha256_text(rsp.index_text(clean)), (d / "_index.json").read_bytes()


def run(d: Path, tmp_path: Path, *extra: str) -> int:
    return rsp.main(["--sessions-dir", str(d), "--backup-dir", str(tmp_path / "bk"), "--quarantine", str(tmp_path / "q"), "--port", "1", *extra])


def test_dry_run_changes_nothing_and_reports_the_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, sha, before = build(tmp_path)
    assert run(d, tmp_path, "--expect-sha256", sha) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "MATCH" in out and "NO MATCH" not in out
    assert (d / "_index.json").read_bytes() == before and not (tmp_path / "q").exists() and not (tmp_path / "bk").exists()


def test_plan_selects_exactly_the_five_polluted_files_and_two_entries(tmp_path: Path) -> None:
    d, sha, _ = build(tmp_path)
    p = rsp.plan(d, tuple(POLLUTED), sha)
    assert sorted(p["removed_ids"]) == sorted(POLLUTED) and p["matches_expected"] is True
    assert sorted(f.name for f in p["files"]) == sorted([f"{POLLUTED[0]}.json", f"{POLLUTED[1]}.json", *(f"test20_2026-11-02T19-13-03-672Z.{e}" for e in ("json", "csv", "pdf"))])
    assert "keep-me" in p["new_text"] and "000000199 - 2026-11-02" in p["new_text"]  # an unrelated same-day session is kept


def test_apply_restores_the_index_byte_for_byte_backs_up_and_moves_never_deletes(tmp_path: Path) -> None:
    d, sha, before = build(tmp_path)
    assert run(d, tmp_path, "--expect-sha256", sha, "--apply") == 0
    restored = (d / "_index.json").read_bytes()
    assert rsp.hashlib.sha256(restored).hexdigest() == sha
    backups = list((tmp_path / "bk").glob("_index.json.*"))
    assert len(backups) == 1 and backups[0].read_bytes() == before            # the polluted index is preserved
    moved = sorted(p.name for p in (tmp_path / "q").iterdir())
    assert len(moved) == 5 and all(not (d / n).exists() for n in moved)         # moved out of sessions, still on disk
    assert (d / "000000204 - 2026-10-27.json").exists() and (d / "scan_2026-10-27T10-00-00-000Z.csv").exists()
    assert run(d, tmp_path, "--expect-sha256", sha, "--apply") == 0             # idempotent: nothing left to do


def test_apply_refuses_when_the_expected_hash_would_not_be_reproduced(tmp_path: Path) -> None:
    d, _, before = build(tmp_path)
    assert run(d, tmp_path, "--expect-sha256", "0" * 64, "--apply") == 3
    assert (d / "_index.json").read_bytes() == before and not (tmp_path / "q").exists() and not (tmp_path / "bk").exists()


def test_apply_refuses_while_the_dashboard_port_is_open(tmp_path: Path) -> None:
    d, sha, before = build(tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        code = rsp.main(["--sessions-dir", str(d), "--backup-dir", str(tmp_path / "bk"), "--quarantine", str(tmp_path / "q"), "--port", str(port), "--expect-sha256", sha, "--apply"])
    assert code == 2 and (d / "_index.json").read_bytes() == before and not (tmp_path / "q").exists()


def test_apply_without_any_expected_hash_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d, _, before = build(tmp_path)
    monkeypatch.setattr(rsp, "baseline_index_hash", lambda *a, **k: None)
    assert run(d, tmp_path, "--apply") == 3 and (d / "_index.json").read_bytes() == before


def test_quarantine_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    d, sha, before = build(tmp_path)
    (tmp_path / "q").mkdir()
    (tmp_path / "q" / f"{POLLUTED[0]}.json").write_text("precious", encoding="utf-8")
    with pytest.raises(FileExistsError):
        run(d, tmp_path, "--expect-sha256", sha, "--apply")
    assert (tmp_path / "q" / f"{POLLUTED[0]}.json").read_text(encoding="utf-8") == "precious"
    # all-or-nothing: the index was not rewritten, no backup was made, and no file was moved
    assert (d / "_index.json").read_bytes() == before and not (tmp_path / "bk").exists()
    assert all((d / f"{sid}.json").exists() for sid in POLLUTED) and len(list((tmp_path / "q").iterdir())) == 1


def test_baseline_hash_is_read_from_the_manifest_format(tmp_path: Path) -> None:
    m = tmp_path / "manifest.txt"
    m.write_text("# header\nabc123 *README.md\n9f8e7d6c5b4a *data/sessions/_index.json\n", encoding="utf-8")
    assert rsp.baseline_index_hash(m) == "9f8e7d6c5b4a" and rsp.baseline_index_hash(tmp_path / "missing") is None
    assert json.loads(rsp.index_text([entry("a", "b")]))[0]["id"] == "a"
