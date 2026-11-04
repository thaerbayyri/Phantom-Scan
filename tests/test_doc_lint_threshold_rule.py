"""Doc lint (PS-FIX-38): never document a "mean + k*sigma" presence threshold rule unqualified.

The committed motion gate (0.6) came from ONE 60 s empty recording (mean 0.49, sigma 0.027, max 0.58).
A k*sigma rule cannot be supported by a window that short: recordings of the same empty room separate
from each other more than that (see reports/fix-2026-11/13-PS-FIX-11.md). So any living document or
exported-report template that states such a rule must say, in the SAME paragraph, that it is
"provisional" or that the figures are "[TO BE MEASURED]".

Scope: living docs (root *.md, docs/*.md, docs/presentations, generated_reports, .agents), the
exported-report builders (scripts/build_*.py) and the dashboard client sources (help text).
Out of scope on purpose: dated session records listed in DATED_RECORDS (history is not rewritten),
reports/ (dated evidence), docs/adr and docs/research (third-party design notes). Source comments in
server/ and scripts/ are handled by review, not by this lint.

This test only reads files. It changes no threshold.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# mean/mu/baseline + k, or + N sigma (sigma, std, a bare "s" as in "mean+3s"), or "k*sigma" on its own.
RULE_RE = re.compile(
    r"(?:mean|μ|baseline)\s*\+\s*(?:k\b|\d+(?:\.\d+)?\s*[·*×x]?\s*(?:σ|sigma|std\w*|s(?![a-z])))"
    r"|\bk\s*[·*×]\s*(?:σ|sigma)",
    re.IGNORECASE,
)
QUALIFIER_RE = re.compile(r"\[TO BE MEASURED\]|provisional", re.IGNORECASE)
# Second rule (PS-FIX-41): the claim word "calibrated" next to "threshold" must also carry the qualifier. "uncalibrated" and
# "calibration" are not flagged (they are not a claim that the threshold IS calibrated); "recalibrated" / "auto-calibrated" are.
CALIBRATED_RE = re.compile(r"\b(?:re|auto-)?calibrated\b", re.IGNORECASE)
THRESHOLD_RE = re.compile(r"threshold", re.IGNORECASE)
RULES = {"mean_k": (RULE_RE, None), "calibrated_threshold": (CALIBRATED_RE, THRESHOLD_RE)}
PARAGRAPH_SPLIT = re.compile(r"\r?\n[ \t]*\r?\n")
WINDOW_LINES = 2  # for source files (no paragraphs): the match line +/- this many lines

# Dated session records that state the old rule as history. They are NOT edited; each entry must still
# violate the rule (test_dated_records_allowlist_is_not_stale), so the list cannot grow silently.
DATED_RECORDS = frozenset(
    {
        "LIVE_HARDWARE_TEST_REPORT.md",
        "PhantomScan_FixAll_Session_Report.md",
        "PhantomScan_FixAll_RuViewAudit_Session_Report.md",
        "PhantomScan_HardwareReality_Alignment_Report.md",
        # PS-FIX-41: dated session / analysis reports that call the gate "calibrated" as history (not edited).
        "PhantomScan_RealLiveFailure_Analysis.md",
        "PhantomScan_GhostTarget_Fix.md",
        "PhantomScan_Research_Gap_Analysis.md",
        "PHANTOM_SCAN_REMEDIATION_REPORT.md",
        "PhantomScan_RuView_Port_Full_Report.md",
    }
)


def find_unqualified(text: str, *, source_file: bool = False, rule: str = "mean_k") -> list[str]:
    """Return one snippet per hit of ``rule`` that has no qualifier in its paragraph (or +/- window for source files)."""
    primary, secondary = RULES[rule]

    def hit(unit: str) -> bool:
        return bool(primary.search(unit)) and (secondary is None or bool(secondary.search(unit)))

    bad: list[str] = []
    if source_file:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not primary.search(line):
                continue
            lo, hi = max(0, i - WINDOW_LINES), min(len(lines), i + WINDOW_LINES + 1)
            window = "\n".join(lines[lo:hi])
            if (secondary is None or secondary.search(window)) and not QUALIFIER_RE.search(window):
                bad.append(f"line {i + 1}: {line.strip()[:120]}")
        return bad
    offset = 0
    for para in PARAGRAPH_SPLIT.split(text):
        start = text.find(para, offset)
        offset = max(offset, start + len(para))
        # A Markdown table is one blank-line block, but each row is its own statement: judge rows separately,
        # so a "provisional" in one row cannot excuse a rule stated in another.
        lines = [ln for ln in para.splitlines() if ln.strip()]
        units = lines if lines and all(ln.lstrip().startswith("|") for ln in lines) else [para]
        for unit in units:
            if hit(unit) and not QUALIFIER_RE.search(unit):
                line_no = text.count("\n", 0, start) + 1
                bad.append(f"line {line_no}: {unit.strip()[:120]!r}")
    return bad


def _scan_files() -> list[Path]:
    files: list[Path] = []
    files += sorted(REPO.glob("*.md"))
    files += sorted((REPO / "docs").glob("*.md"))
    files += sorted((REPO / "docs" / "presentations").glob("*.md"))
    files += sorted((REPO / "generated_reports").glob("*.md"))
    files += sorted((REPO / ".agents").glob("*.md"))
    files += sorted((REPO / "scripts").glob("build_*.py"))
    for ext in ("*.ts", "*.tsx"):
        files += sorted((REPO / "client" / "src").rglob(ext))
    return [f for f in files if f.is_file()]


def _is_source(path: Path) -> bool:
    return path.suffix in {".py", ".ts", ".tsx"}


def _violations(path: Path, rule: str = "mean_k") -> list[str]:
    return find_unqualified(path.read_text(encoding="utf-8", errors="replace"), source_file=_is_source(path), rule=rule)


# ---- the lint itself ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Pick mean + k·σ from the empty run.",
        "threshold = mean + k*sigma",
        "use MEAN+K·SIGMA",
        "suggested: mean+3σ / mean+4σ",
        "gate = μ + 3σ over a minute",
        "mean +   4 · sigma margin",
        "suggested mean+3s=0.0608",
        "the k × σ rule",
        "baseline + k std",
    ],
)
def test_lint_flags_unqualified_rule(text: str) -> None:
    assert find_unqualified(text), text


@pytest.mark.parametrize(
    "text",
    [
        "A mean + k·σ rule is not supported; the gate is provisional.",
        "threshold = mean + k*sigma (false alarms [TO BE MEASURED])",
        "mean 0.49, σ 0.027, max 0.58 over 296 samples",  # descriptive statistics are fine
        "the mean + 3 seconds window",  # not a sigma rule
        "Everything is Provisional here.\nmean + k·σ is the old rule.",  # same paragraph, case-insensitive
    ],
)
def test_lint_accepts_qualified_or_unrelated(text: str) -> None:
    assert find_unqualified(text) == [], text


def test_qualifier_in_a_different_paragraph_does_not_count() -> None:
    text = "The old rule was mean + k·σ.\n\nThe gate is provisional."
    assert len(find_unqualified(text)) == 1


def test_table_rows_are_judged_separately() -> None:
    table = "| ID | text |\n|---|---|\n| FR1 | gate is provisional |\n| FR2 | derive it from mean + k·σ |\n"
    assert len(find_unqualified(table)) == 1
    ok = "| ID | text |\n|---|---|\n| FR1 | gate is provisional |\n| FR2 | mean + k·σ, provisional |\n"
    assert find_unqualified(ok) == []


def test_source_files_use_a_line_window_not_the_whole_file() -> None:
    far = "x\n" * (WINDOW_LINES + 3)
    text = "# provisional\n" + far + 'FR = "derives the gate (mean + k*sigma)."\n'
    assert len(find_unqualified(text, source_file=True)) == 1
    near = 'FR = "derives the gate (mean + k*sigma)."\n# provisional\n'
    assert find_unqualified(near, source_file=True) == []


# ---- the repository ----------------------------------------------------------------------------


def test_scope_is_not_empty() -> None:
    names = {p.relative_to(REPO).as_posix() for p in _scan_files()}
    assert "README.md" in names
    assert "docs/SPATIAL_CALIBRATION.md" in names
    assert "scripts/build_academic_reports.py" in names


@pytest.mark.parametrize("rule", sorted(RULES))
def test_no_living_doc_or_template_states_the_rule_unqualified(rule: str) -> None:
    failures: dict[str, list[str]] = {}
    for path in _scan_files():
        rel = path.relative_to(REPO).as_posix()
        if rel in DATED_RECORDS:
            continue
        found = _violations(path, rule)
        if found:
            failures[rel] = found
    assert not failures, f"rule {rule!r}: add 'provisional' or '[TO BE MEASURED]' in the same paragraph:\n" + "\n".join(
        f"  {f}: {v}" for f, vs in failures.items() for v in vs
    )


def test_dated_records_allowlist_is_not_stale() -> None:
    for rel in sorted(DATED_RECORDS):
        path = REPO / rel
        assert path.is_file(), f"{rel} is allow-listed but missing: remove it from DATED_RECORDS"
        assert any(_violations(path, r) for r in RULES), f"{rel} no longer breaks any rule: remove it from DATED_RECORDS"


# ---- PS-FIX-41: "calibrated" next to "threshold" ----------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "The threshold is calibrated per room.",
        "a calibrated empty-room threshold",
        "Calibrated against a 2-node rig; threshold 0.6.",
        "the threshold was recalibrated in July",
        "an auto-calibrated threshold",
        "motion above the CALIBRATED THRESHOLD",
    ],
)
def test_calibrated_rule_flags_an_unqualified_claim(text: str) -> None:
    assert find_unqualified(text, rule="calibrated_threshold"), text


@pytest.mark.parametrize(
    "text",
    [
        "The threshold is calibrated per room (provisional).",
        "a calibrated threshold, false alarms [TO BE MEASURED]",
        "an uncalibrated threshold",                      # not a claim that it IS calibrated
        "threshold calibration is pending",               # 'calibration' is not 'calibrated'
        "the sensor was calibrated yesterday",            # no threshold in the unit
        "Everything here is Provisional.\nThe calibrated threshold is 0.6.",
    ],
)
def test_calibrated_rule_accepts_qualified_or_unrelated_text(text: str) -> None:
    assert find_unqualified(text, rule="calibrated_threshold") == [], text


def test_calibrated_rule_table_rows_are_judged_separately() -> None:
    table = "| a | b |\n|---|---|\n| x | provisional |\n| y | the calibrated threshold |\n"
    assert len(find_unqualified(table, rule="calibrated_threshold")) == 1


def test_calibrated_rule_source_window() -> None:
    src = '# the threshold is calibrated\nx = 1\n'
    assert len(find_unqualified(src, source_file=True, rule="calibrated_threshold")) == 1
    assert find_unqualified("# the threshold is calibrated (provisional)\n", source_file=True, rule="calibrated_threshold") == []


def test_calibrated_rule_catches_the_statements_fixed_in_ps_fix_41() -> None:
    """The exact claims that were in the docs and the report template before the fix."""
    before = [
        "The threshold is documented in-code as a placeholder to be calibrated per room: scripts/calibrate-threshold.ts",
        "the score rises above the calibrated empty-room threshold",
        "once the two-node foundation is calibrated and proven",   # sponsor pitch, no 'threshold' -> not this rule (pinned below)
    ]
    assert find_unqualified(before[0], rule="calibrated_threshold")
    assert find_unqualified(before[1], rule="calibrated_threshold")
    assert find_unqualified(before[2], rule="calibrated_threshold") == []
