#!/usr/bin/env python3
"""Restore data/sessions after test pollution (PS-FIX-23). DRY-RUN unless --apply.

    python scripts/restore_session_pollution.py                 # show the plan, change nothing
    python scripts/restore_session_pollution.py --apply         # do it (the dashboard must be STOPPED)

What it does with --apply, in order:
  1. refuses if anything listens on the dashboard port (default 5000): the server rewrites _index.json from memory;
  2. refuses unless removing the named entries reproduces the expected sha256 of _index.json byte-for-byte
     (default: the baseline recorded in reports/fix-2026-11/results/baseline-manifest.txt), so a wrong target can
     never be written;
  3. copies _index.json to .tmp/fix-backups/23-sessions/ ;
  4. writes the restored index (json.dumps(entries, indent=2), no trailing newline: the dashboard's format);
  5. MOVES (never deletes) the polluted session files into a quarantine folder (default .tmp/quarantine-sessions-<date>).
Nothing is removed from disk; moving the files back and restoring the backup undoes everything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_IDS = ("000000205 - 2026-11-02", "000000206 - 2026-11-02")
MANIFEST = REPO / "reports" / "fix-2026-11" / "results" / "baseline-manifest.txt"


def baseline_index_hash(manifest: Path = MANIFEST) -> str | None:
    """sha256 recorded for data/sessions/_index.json in the baseline manifest (sha256sum format)."""
    if not manifest.is_file():
        return None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.rstrip().endswith("data/sessions/_index.json"):
            return line.split()[0]
    return None


def index_text(entries: list[dict]) -> str:
    return json.dumps(entries, indent=2)  # the dashboard's own format: no trailing newline


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def plan(sessions_dir: Path, ids: tuple[str, ...], expected_sha: str | None) -> dict:
    index_path = sessions_dir / "_index.json"
    raw = index_path.read_text(encoding="utf-8")
    entries = json.loads(raw)
    removed = [e for e in entries if e.get("id") in ids]
    kept = [e for e in entries if e.get("id") not in ids]
    files: list[Path] = []
    for e in removed:
        date = str(e["id"]).rsplit(" - ", 1)[-1]  # e.g. 2026-11-02
        candidates = [sessions_dir / f"{e['id']}.json", *sorted(sessions_dir.glob(f"{e.get('name', '')}_{date}T*"))]
        files += [p for p in candidates if p.is_file() and p not in files]
    new_text = index_text(kept)
    return {
        "index_path": index_path, "removed_ids": [e["id"] for e in removed], "files": files, "new_text": new_text,
        "new_sha256": sha256_text(new_text), "expected_sha256": expected_sha, "current_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "matches_expected": expected_sha is not None and sha256_text(new_text) == expected_sha, "nothing_to_do": not removed and not files,
    }


def apply(p: dict, backup_dir: Path, quarantine: Path) -> list[str]:
    done: list[str] = []
    for f in p["files"]:  # fail BEFORE touching anything if a destination is taken
        if (quarantine / f.name).exists():
            raise FileExistsError(f"refusing to overwrite {quarantine / f.name}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"_index.json.{stamp}"
    shutil.copy2(p["index_path"], backup)
    done.append(f"backed up _index.json -> {backup}")
    with open(p["index_path"], "w", encoding="utf-8", newline="") as fh:
        fh.write(p["new_text"])
    done.append(f"restored {p['index_path']} (sha256 {p['new_sha256'][:16]}…)")
    quarantine.mkdir(parents=True, exist_ok=True)
    for f in p["files"]:
        target = quarantine / f.name
        if target.exists():
            raise FileExistsError(f"refusing to overwrite {target}")
        shutil.move(str(f), str(target))
        done.append(f"moved {f.name} -> {quarantine}")
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions-dir", type=Path, default=REPO / "data" / "sessions")
    ap.add_argument("--ids", nargs="+", default=list(DEFAULT_IDS), help="session ids (index entries) to remove")
    ap.add_argument("--expect-sha256", default=None, help="expected sha256 of the restored _index.json (default: baseline manifest)")
    ap.add_argument("--port", type=int, default=5000, help="dashboard port that must be closed for --apply")
    ap.add_argument("--backup-dir", type=Path, default=REPO / ".tmp" / "fix-backups" / "23-sessions")
    ap.add_argument("--quarantine", type=Path, default=REPO / ".tmp" / f"quarantine-sessions-{datetime.now(timezone.utc):%Y-%m-%d}")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    expected = args.expect_sha256 or baseline_index_hash()
    p = plan(args.sessions_dir, tuple(args.ids), expected)
    print(f"index entries to remove : {p['removed_ids'] or 'none'}")
    print(f"files to move           : {[f.name for f in p['files']] or 'none'}")
    print(f"restored index sha256   : {p['new_sha256']}")
    print(f"expected (baseline)     : {expected or 'UNKNOWN'}  -> {'MATCH' if p['matches_expected'] else 'NO MATCH'}")
    if p["nothing_to_do"]:
        print("nothing to do (already clean).")
        return 0
    if not args.apply:
        print("dry run: nothing changed. Stop the dashboard, then re-run with --apply.")
        return 0
    if port_is_open(args.port):
        print(f"REFUSED: something is listening on :{args.port}. Stop the dashboard first (it would rewrite _index.json).")
        return 2
    if not p["matches_expected"]:
        print("REFUSED: the restored index would not reproduce the expected sha256; nothing was changed.")
        return 3
    for line in apply(p, args.backup_dir, args.quarantine):
        print(line)
    print("done. Restart the dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
