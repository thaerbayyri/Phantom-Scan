#!/usr/bin/env python3
"""PS-FIX-24 / PS-FIX-26 licence hygiene check. READ-ONLY: it reports and sets an exit code; it never deletes, moves or edits anything.

    python scripts/check_licence_hygiene.py [--root DIR] [--strict-working-tree]

Standing rule (Gate 1 / Gate 2): ``pose_v1.safetensors`` (provenance unverified) and anything MM-Fi-derived (CC BY-NC 4.0) stay OUT of every
deliverable. This check FAILS (exit 1) when, in a deliverable path:
  * a tracked file has a model-weight suffix, or a tracked / packaged file has the SHA-256 of a restricted file,
  * the packaged build (dist/) contains ``pose_v1``, ``MM-Fi``/``MMFi`` or ``Wi-Pose`` (any case) or a weight-like file,
  * a report template, source file or deliverable document (see SCOPE) contains those strings, unless the exact file is in
    REVIEWED_MENTIONS (an explicit, reasoned exception that must still match, or the check fails because the list is stale).
It WARNS (exit 0) when a restricted file sits in the working tree but is not tracked or packaged (for example inside a nested repo: a folder
copy of the working tree would still carry it); ``--strict-working-tree`` turns that warning into a failure.

Out of scope on purpose: docs/adr and docs/research (third-party design notes), reports/ (dated evidence), root-level dated session reports,
the nested model repository itself (handled by the working-tree warning), node_modules, .venv, .tmp, .git.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# SHA-256 of files that must never reach a deliverable (full digest; the short prefix is in reports/fix-2026-11/06-licences.md).
RESTRICTED_SHA256 = {
    "eb249b9a6b2e10130437a10976ed0230b0d085f86a0553d7226e1ae6eae4b9e5": "pose_v1.safetensors (provenance unverified; PS-FIX-24/-26)",
}
FORBIDDEN = re.compile(rb"pose_v1|\bMM-?Fi\b|\bWi-?Pose\b", re.IGNORECASE)
WEIGHT_SUFFIXES = (".safetensors", ".onnx", ".pt", ".pth", ".npz", ".ckpt", ".gguf")
RESTRICTED_NAME = re.compile(r"^pose_v1", re.IGNORECASE)

# Deliverable scope (relative globs). dist/ is handled separately (every file, any extension).
SCOPE = (
    "scripts/build_*.py", "scripts/reporting/**/*.py", "scripts/*.py", "server/**/*.ts", "shared/**/*.ts", "client/src/**/*",
    "phantom/**/*.py", "README.md", ".agents/*.md", "docs/*.md", "docs/presentations/*.md", "generated_reports/*.md",
)
PACKAGED_DIR = "dist"
# Reviewed exceptions: the file may mention the strings, for the stated reason. Each must still match (else the list is stale and fails).
REVIEWED_MENTIONS = {
    "scripts/ai_inference.py": "AI sidecar: loads pose_v1 weights if the file exists (inference and the poseFrame output only with PHANTOM_AI_POSE). "
                               "Reviewed in PS-FIX-45; the weights are not shipped by git.",
    "scripts/inspect_pose_weights.py": "diagnostic that inspects the local pose weights; not part of any export.",
}
SKIP_DIRS = {".git", "node_modules", ".venv", ".tmp", ".docx_deps", "__pycache__"}
# This file necessarily contains the forbidden strings (they are its patterns); it is the ONLY file excluded from the content scan.
SELF = "scripts/check_licence_hygiene.py"
MAX_HASH_BYTES = 64 * 1024 * 1024


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_HASH_BYTES:
            return None
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _scope_files(root: Path) -> list[Path]:
    seen: dict[str, Path] = {}
    for pattern in SCOPE:
        for p in root.glob(pattern):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and rel != SELF and not (set(p.relative_to(root).parts) & SKIP_DIRS):
                seen[rel] = p
    return [seen[k] for k in sorted(seen)]


def _mentions(path: Path) -> bool:
    try:
        return bool(FORBIDDEN.search(path.read_bytes()))
    except OSError:
        return False


def _walk(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS):
            yield p


def scan(root: Path, tracked: list[str] | None, strict_working_tree: bool = False) -> Report:
    rep = Report()
    # 1. tracked files: no weight-like suffix, no restricted digest
    if tracked is None:
        rep.warnings.append("not a git work tree: the tracked-file checks were skipped")
    else:
        for rel in tracked:
            p = root / rel
            if not p.is_file():
                continue
            if rel.lower().endswith(WEIGHT_SUFFIXES) or RESTRICTED_NAME.match(p.name):
                rep.failures.append(f"tracked weight-like file: {rel}")
                continue
            if 100_000 <= p.stat().st_size <= MAX_HASH_BYTES:
                digest = sha256_file(p)
                if digest in RESTRICTED_SHA256:
                    rep.failures.append(f"tracked file {rel} IS {RESTRICTED_SHA256[digest]}")
    # 2. the packaged build: every file, any extension
    dist = root / PACKAGED_DIR
    if dist.is_dir():
        n = 0
        for p in sorted(q for q in dist.rglob("*") if q.is_file()):
            n += 1
            rel = p.relative_to(root).as_posix()
            if rel.lower().endswith(WEIGHT_SUFFIXES) or RESTRICTED_NAME.match(p.name):
                rep.failures.append(f"packaged build holds a weight-like file: {rel}")
            elif _mentions(p):
                rep.failures.append(f"packaged build mentions a restricted name: {rel}")
            elif sha256_file(p) in RESTRICTED_SHA256:
                rep.failures.append(f"packaged build holds {RESTRICTED_SHA256[sha256_file(p)]}: {rel}")
        rep.notes.append(f"packaged build scanned: {n} files under {PACKAGED_DIR}/")
    else:
        rep.notes.append(f"no {PACKAGED_DIR}/ directory: packaged build not scanned")
    # 3. templates, sources and deliverable documents
    scanned = 0
    for p in _scope_files(root):
        scanned += 1
        rel = p.relative_to(root).as_posix()
        if _mentions(p) and rel not in REVIEWED_MENTIONS:
            rep.failures.append(f"restricted name in a deliverable path: {rel}")
    rep.notes.append(f"{scanned} template/source/document files scanned")
    # 4. the reviewed-exception list must not go stale
    for rel, why in sorted(REVIEWED_MENTIONS.items()):
        p = root / rel
        if not p.is_file():
            rep.failures.append(f"REVIEWED_MENTIONS lists {rel} but the file is missing: remove the entry")
        elif not _mentions(p):
            rep.failures.append(f"REVIEWED_MENTIONS lists {rel} but it no longer mentions a restricted name: remove the entry")
        else:
            rep.notes.append(f"reviewed mention: {rel} ({why})")
    # 5. the working tree: a restricted file that is neither tracked nor packaged is a warning (a folder copy would carry it)
    tracked_set = set(tracked or [])
    for p in _walk(root):
        rel = p.relative_to(root).as_posix()
        if rel in tracked_set or rel.startswith(PACKAGED_DIR + "/"):
            continue
        hit = RESTRICTED_NAME.match(p.name) or (100_000 <= p.stat().st_size <= MAX_HASH_BYTES and sha256_file(p) in RESTRICTED_SHA256)
        if hit:
            msg = f"restricted weights present in the working tree, not tracked or packaged: {rel}"
            (rep.failures if strict_working_tree else rep.warnings).append(msg)
    return rep


def tracked_files(root: Path) -> list[str] | None:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [s for s in out.decode("utf-8", "replace").split("\0") if s]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PS-FIX-24/-26 licence hygiene check (read-only)")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--strict-working-tree", action="store_true", help="fail (not warn) when restricted weights sit untracked in the working tree")
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    rep = scan(args.root, tracked_files(args.root), args.strict_working_tree)
    for n in rep.notes:
        print(f"note: {n}")
    for w in rep.warnings:
        print(f"WARN: {w}")
    for f in rep.failures:
        print(f"FAIL: {f}")
    print("FAIL" if rep.failures else "OK", f"({len(rep.failures)} failure(s), {len(rep.warnings)} warning(s))")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
