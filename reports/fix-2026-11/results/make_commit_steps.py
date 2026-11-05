"""Generate .tmp/commit-steps/** and reports/fix-2026-11/88b-commit-steps.md (owner-approved, NOT executed in the real repo).
The sequence is dry-run in a throwaway clone to capture the real `git diff --cached --stat` and to prove the final tree == the working tree."""
import collections, hashlib, pathlib, shutil, subprocess, sys, tempfile

R = pathlib.Path(r"D:\WIFI csi\phanotm\phantom scan")
BK, OUT = R / ".tmp" / "fix-backups", R / ".tmp" / "commit-steps"
OLD = "744ce43"
ORDER = ["01-PS-FIX-01", "02-PS-FIX-02", "03-PS-FIX-03", "04-PS-FIX-04", "05-PS-FIX-05", "06-PS-FIX-06", "07-PRE-WAVE2", "08-WAVE2", "09-DECISIONS",
         "10-PS-FIX-27", "11-PS-FIX-08", "12-PS-FIX-07", "13-PS-FIX-11", "14-PS-FIX-09"]
EXCLUDE_PREFIX = ("data/", ".tmp/", "node_modules/", "reports/")
ATTR = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
MSG = {
 "01-PS-FIX-01": ("test: stop the suites writing into the real audit log and live sessions (PS-FIX-01)", "TS tests use a temp audit dir; the live-server Python tests are opt-in; scikit-learn declared as an optional 'train' extra."),
 "02-PS-FIX-02": ("fix: harden the dataset loader (PS-FIX-02)", "phantom/dataset.py counts bad lines/frames, never truncates mixed widths, streams in chunks; strict mode kept."),
 "03-PS-FIX-03": ("feat: both recorders write the same compact JSON and header schema 2 (PS-FIX-03)", "Per-part start, geometry hash, operator-stated capture conditions, node-moved annotation; readers accept schema 1 and 2."),
 "04-PS-FIX-04": ("feat: stricter evaluation tooling (PS-FIX-04)", "Rank AUC with block-bootstrap CIs, session-blocked AUC, empty-vs-empty control C4, always-absent control, abstentions counted as misses."),
 "05-PS-FIX-05": ("docs: correct frame rate, geometry and capability claims (PS-FIX-05)", "Capability figures labelled [TO BE MEASURED]; claims swept; dated records untouched."),
 "06-PS-FIX-06": ("feat: AI sidecar refuses the saturated shipped presence head (PS-FIX-06)", "phantom/presence_guard.py and tests; licence inventory in the reports."),
 "07-PRE-WAVE2": ("test: E2E guard and the session-pollution restore tool (pre-Wave-2)", "tests/e2e_guard.py, scripts/restore_session_pollution.py and their tests."),
 "08-WAVE2": ("feat: link-state epochs, movement score and recorder summary sidecar (Wave 2 addendum)", "epochs.py, epoch_eval.py, movement.py; both recorders write a per-part summary sidecar."),
 "09-DECISIONS": ("feat: presence-head norm audit and epoch sensitivity (decisions batch)", "Presence-head norm audit; epoch sensitivity."),
 "10-PS-FIX-27": ("feat: PHANTOM_DATA_DIR for every data path, default unchanged (PS-FIX-27)", "server/lib/data-dir.ts and eight call sites; the default path is identical to before (tested)."),
 "11-PS-FIX-08": ("feat: PHY shadow guard and header-offset audit; a guard fault never drops a frame (PS-FIX-08)", "Shadow mode only counts/logs. A thrown guard fault is isolated in try/catch and logged once per 1000 (0/5 frames ingested before, 5/5 after); the forward socket closes with the server."),
 "12-PS-FIX-07": ("feat: frame-rate truth analysis (PS-FIX-07)", "scripts/presence_eval/frame_rate.py and its test."),
 "13-PS-FIX-11": ("feat: calibration soak rules; no threshold from a single run (PS-FIX-11)", "scripts/accuracy/calibration-soak.ts, replay tool; calibrate-threshold.ts refuses short runs and never writes settings."),
 "14-PS-FIX-09": ("feat: fan/periodicity analysis, negative result; alias-free 100 Hz grid (PS-FIX-09, PS-FIX-40)", "periodicity.py; default grid 100 Hz = 3 x the ping cadence, old grids kept."),
}
OWNER_GROUPS = [("client/", "client dashboard"), ("firmware/", "firmware (esp32-csi-node)"), ("server/", "server runtime"), ("shared/", "shared schema and presentation"),
                ("tests/", "tests"), ("scripts/", "scripts"), ("phantom/", "phantom package"), ("docs/", "docs")]


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, cwd=k.get("cwd", R))


def lf(b: bytes):
    return b.replace(b"\r\n", b"\n") if (b"\0" not in b[:8192]) else b


def head_blob(path, rev):
    r = sh("git", "show", f"{rev}:{path}")
    return lf(r.stdout) if r.returncode == 0 else None


def merge3(base, ours, theirs):
    d = pathlib.Path(tempfile.mkdtemp())
    for n, t in (("b", base), ("o", ours), ("t", theirs)):
        (d / n).write_bytes(t)
    r = sh("git", "merge-file", "-p", str(d / "o"), str(d / "b"), str(d / "t"))
    return r.stdout, r.returncode


def bp(item, path):
    for c in (BK / item / path, BK / item / pathlib.Path(path).name):
        if c.is_file():
            return c
    return None


status = [(l[:2], l[3:].strip()) for l in sh("git", "status", "--short").stdout.decode().splitlines()]
mod = [p for s, p in status if s.strip() == "M" and not p.startswith(EXCLUDE_PREFIX)]
unt = [l for l in sh("git", "ls-files", "--others", "--exclude-standard").stdout.decode().splitlines() if not l.startswith(EXCLUDE_PREFIX)]
fp_added, fp_changed = collections.defaultdict(list), collections.defaultdict(list)
for f in sorted((R / "reports/fix-2026-11/results").glob("footprint-*.txt")):
    item, sec = f.stem.replace("footprint-", ""), None
    for ln in f.read_text(encoding="utf-8").splitlines():
        if ln.startswith("changed"): sec = "c"
        elif ln.startswith("added"): sec = "a"
        elif ln.startswith("removed"): sec = None
        elif ln.startswith("  ") and sec:
            (fp_added if sec == "a" else fp_changed)[ln.strip().split(None, 1)[-1]].append(item)
extra = {"server/lib/udp-server-phy-guard-fault.test.ts": "11-PS-FIX-08"}        # Item D's new test belongs with PS-FIX-08
for p, it in extra.items():
    fp_added[p].append(it)
wt = lambda p: lf((R / p).read_bytes())
committed: dict = {}                                    # path -> bytes in the simulated HEAD (None = absent)
for p in mod:
    committed[p] = head_blob(p, "HEAD")
chain = {p: [i for i in ORDER if bp(i, p)] for p in mod}
steps = []                                              # (id, title, message, [(path, blob_bytes, how)])
issues = []


def new_step(sid, title, body, files, mine):
    msg = f"{title}\n\n{body}\n" + (f"\n{ATTR}\n" if mine else "")
    steps.append((sid, title, msg, files))
    for p, blob, _ in files:
        committed[p] = blob


# ---- owner commits (his work first) ----
owner_tracked = [p for p in mod if not chain[p]]
mixed = []
for p in mod:
    if chain[p]:
        t0 = lf(bp(chain[p][0], p).read_bytes()); oldb = head_blob(p, OLD)
        if oldb is not None and t0 != oldb:
            mixed.append(p)
owner_files = collections.defaultdict(list)
for p in owner_tracked + [u for u in unt if not fp_added.get(u)]:
    grp = next((g for pre, g in OWNER_GROUPS if p.startswith(pre)), "root files and other")
    owner_files[grp].append((p, wt(p), "his whole file (identical to its Wave 0 hash)" if p in owner_tracked else "new file, not named in any item footprint"))
for p in mixed:
    t0 = lf(bp(chain[p][0], p).read_bytes())
    blob, rc = merge3(head_blob(p, OLD), committed[p], t0)
    if rc:
        issues.append(f"{p}: the owner's share does not merge cleanly onto HEAD ({rc} conflict(s)): resolve by hand")
    grp = next((g for pre, g in OWNER_GROUPS if p.startswith(pre)), "root files and other")
    owner_files[grp].append((p, blob, f"owner's lines only (Wave 0 state merged onto HEAD; {rc} conflict(s))"))
n = 1
for _, g in OWNER_GROUPS + [(None, "root files and other")]:
    if owner_files.get(g):
        new_step(f"O{n}", f"chore({g.split()[0]}): {g}", "The owner's own work, as it stood before the Wave 0-3 evaluation task. The owner edits this message.", owner_files[g], False)
        n += 1
# ---- my item commits ----
for item in ORDER:
    files = []
    tracked_here = [p for p in mod if item in chain[p]]
    for p in tracked_here:
        its = chain[p]; i = its.index(item)
        base = lf(bp(item, p).read_bytes())
        theirs = lf(bp(its[i + 1], p).read_bytes()) if i + 1 < len(its) else wt(p)
        blob, rc = merge3(base, committed[p] or b"", theirs)
        if rc:
            issues.append(f"{item}: {p} merges with {rc} conflict(s) (needs a human)")
        files.append((p, blob, f"my hunks only (3-way: base = state before {item})"))
    for p in sorted(u for u in unt if item in fp_added.get(u, [])):
        files.append((p, wt(p), "new file"))
    if files:
        title, body = MSG[item]
        new_step(f"M-{item[:2]}", title, body, files, True)
# ---- write blobs and stage scripts ----
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "blobs").mkdir(parents=True)
modes = {l.split("\t")[1]: l.split()[0] for l in sh("git", "ls-files", "-s").stdout.decode().splitlines() if "\t" in l}
for idx, (sid, title, msg, files) in enumerate(steps, 1):
    lines = ["#!/usr/bin/env bash", "set -e", f"# step {sid}: {title}", "cd \"$(git rev-parse --show-toplevel)\""]
    for p, blob, how in files:
        bpth = OUT / "blobs" / sid / p
        bpth.parent.mkdir(parents=True, exist_ok=True)
        bpth.write_bytes(blob)
        lines.append(f'H=$(git hash-object -w --no-filters ".tmp/commit-steps/blobs/{sid}/{p}") && git update-index --add --cacheinfo {modes.get(p, "100644")},$H,"{p}"')
    (OUT / f"stage-{sid}.sh").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (OUT / f"message-{sid}.txt").write_text(msg, encoding="utf-8", newline="\n")
# ---- dry run in a throwaway clone ----
sim = pathlib.Path(tempfile.mkdtemp()) / "sim"
r_clone = sh("git", "clone", "-q", "--no-hardlinks", str(R), str(sim))
assert r_clone.returncode == 0, r_clone.stderr[:300]
shutil.copytree(OUT, sim / ".tmp" / "commit-steps")
stats = {}
for sid, title, msg, files in steps:
    r = subprocess.run(["bash", f".tmp/commit-steps/stage-{sid}.sh"], cwd=sim, capture_output=True, text=True)
    if r.returncode:
        issues.append(f"{sid}: staging failed in the clone: {r.stderr[:200]}")
    stats[sid] = subprocess.run(["git", "diff", "--cached", "--stat"], cwd=sim, capture_output=True, text=True).stdout.rstrip()
    subprocess.run(["git", "-c", "user.name=sim", "-c", "user.email=sim@x", "commit", "-q", "-F", str(OUT / f"message-{sid}.txt")], cwd=sim, capture_output=True)
final_bad = []
for p in mod + [u for u in unt]:
    h = subprocess.run(["git", "show", f"HEAD:{p}"], cwd=sim, capture_output=True)
    if h.returncode or lf(h.stdout) != wt(p):
        final_bad.append(p)
# ---- the reports commit (simulated too) ----
rep_files = [l for l in sh("git", "ls-files", "--others", "--exclude-standard", "reports").stdout.decode().splitlines()]
shutil.copytree(R / "reports", sim / "reports", dirs_exist_ok=True)
subprocess.run(["git", "add", "reports"], cwd=sim, capture_output=True)
rep_stat = subprocess.run(["git", "diff", "--cached", "--shortstat"], cwd=sim, capture_output=True, text=True).stdout.strip()
# ---- the document ----
L = ["# 88b — Commit steps (NOT executed; the owner approves and runs each one)", "",
     f"Generated 2026-11-04 from the working tree at HEAD `{sh('git','rev-parse','--short','HEAD').stdout.decode().strip()}`. **Nothing here has been run in this repository.** Every step was dry-run in a THROWAWAY CLONE "
     "(`git clone --no-hardlinks`, deleted afterwards), which produced the `git diff --cached --stat` blocks below and proved that after the last step the committed tree equals the working tree "
     f"for all {len(mod) + len(unt)} files covered ({'**yes**' if not final_bad else '**NO: ' + str(final_bad[:5]) + '**'}). Safety backup of the whole tree: `.tmp/pre-wave3-backup/` (`MANIFEST.sha256`).", "",
     "## How each step works", "",
     "* `bash .tmp/commit-steps/stage-<ID>.sh` stages the exact blobs of that step **by blob** (`git hash-object -w --no-filters` + `git update-index --cacheinfo`), never `git add <file>`, so a file that carries both your lines and mine contributes only the right lines. The script is plain text: read it first.",
     "* Then `git diff --cached --stat` must equal the block shown for the step; then `git commit -F .tmp/commit-steps/message-<ID>.txt` (the message is shown below and may be edited).",
     "* The working tree is never touched; `git status` shows the remaining uncommitted work.", "",
     "## Preflight (before step P)", "", "```", "git diff --cached --name-only        # nothing may be staged", "git log -1 --format=%h               # expect " + sh('git','rev-parse','--short','HEAD').stdout.decode().strip(),
     "```", "",
     "## Step P — commit the pre-registration FIRST (before any recording is analysed)", "", "```", "git add reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md",
     "git diff --cached --stat", "git commit -m \"docs: pre-register the 2026-11 recording campaign (criteria fixed before any analysis)\"", "```", "",
     "`run_campaign.py` refuses to analyse a campaign until this file is committed and unmodified. Edit the `[OWNER TO SET]` items before committing if you want them in the frozen version.", ""]
for sid, title, msg, files in steps:
    L += [f"## Step {sid} — {title}", "", "```", f"bash .tmp/commit-steps/stage-{sid}.sh", "git diff --cached --stat", f"git commit -F .tmp/commit-steps/message-{sid}.txt", "```", "",
          "Message:", "", "```", msg.rstrip(), "```", "", "Files (path: how staged):", ""]
    L += [f"* `{p}`: {how}" for p, _, how in files]
    L += ["", "Expected `git diff --cached --stat` (captured from the dry run):", "", "```", stats[sid], "```", ""]
L += ["## Step R — the reports (last)", "", "```", "git add reports", "git diff --cached --shortstat", "git commit -m \"docs: Wave 0-3 evaluation reports, ledgers, merge gate and test output\"", "```", "",
      f"Expected `--shortstat` at generation time: `{rep_stat}`. This number grows if more report files are added after this document was generated (re-run the generator, or compare counts approximately). `reports/fix-2026-11/09-WAVE3-addendum.md` is a running record: commit it only when Wave 3 is closed.", "",
      "## Never commit", "", "`data/sessions/_index.json` and the dashboard's session files, `.tmp/`, the nested model repository (`ai model and densepose/model`, shown as `m` in `git status`) and `pose_v1.safetensors` (PS-FIX-24/-26).", "",
      "## Findings from the dry run", ""]
L += ([f"* {i}" for i in issues] or ["* every 3-way merge was clean; no conflicts. (`server/lib/websocket.ts`: with your lines committed first, my PS-FIX-27 hunk applies on top without the conflict seen in `88-commit-proposal.md`.)"])
(R / "reports/fix-2026-11/88b-commit-steps.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
shutil.rmtree(sim.parent, ignore_errors=True)
print("steps:", [s[0] for s in steps]); print("issues:", issues); print("final tree == working tree:", not final_bad, final_bad[:5]); print("reports files:", len(rep_files), "|", rep_stat)
