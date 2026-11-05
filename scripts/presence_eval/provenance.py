"""Provenance stamp attached to every results JSON (command, commit, code hash, date)."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = Path(__file__).resolve().parent


def default_out_dir() -> Path:
    """Report folder; override with PRESENCE_EVAL_OUT (e.g. reports/fix-2026-11) to keep earlier results intact."""
    import os

    return Path(os.environ.get("PRESENCE_EVAL_OUT") or REPO_ROOT / "reports" / "presence-eval-2026-11")


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def code_sha256() -> str:
    """Hash of this package's sources: the code is untracked, so the commit hash alone does not identify it."""
    h = hashlib.sha256()
    for p in sorted(PACKAGE_DIR.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def provenance(command: str, inputs: list[str] | None = None) -> dict:
    return {
        "command": command,
        "commit": _git("rev-parse", "HEAD") or "[UNVERIFIED]",
        "branch": _git("branch", "--show-current") or "[UNVERIFIED]",
        "working_tree_dirty": bool(_git("status", "--porcelain")),
        "eval_code_sha256_16": code_sha256(),
        "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "inputs": inputs or [],
    }
