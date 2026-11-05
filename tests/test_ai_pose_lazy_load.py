"""PS-FIX-45: the restricted pose_v1 weights are read only when PHANTOM_AI_POSE is on.

`scripts/ai_inference.py` is a long-running script (torch, sockets), so it is not imported here. The `try:` block that
loads the pose weights is cut out of the source with `ast` and executed against stubs: the test sees whether the
weights file is opened, not what a model would do with it. Inference (`POSE_ENABLED` check) and the `poseFrame`
message were already gated; this closes the remaining path (weights read into memory while the flag is off).
"""
from __future__ import annotations

import ast
import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "ai_inference.py").read_text(encoding="utf-8")
WEIGHTS = "ai model and densepose/model/pose_v1.safetensors"


TREE = ast.parse(SOURCE)


def _pose_load_block() -> ast.Try:
    blocks = [n for n in TREE.body if isinstance(n, ast.Try) and "load_file(POSE_WEIGHTS)" in ast.unparse(n)]
    assert len(blocks) == 1, "exactly one module-level block must load the pose weights"
    return blocks[0]


def _run(pose_enabled: bool, file_exists: bool = True) -> tuple[list[str], bool, str]:
    opened: list[str] = []

    class Model:
        def load_state_dict(self, state, strict=False):
            return [], []

    def load_file(path: str):
        opened.append(path)
        return {}

    ns = {
        "os": SimpleNamespace(path=SimpleNamespace(exists=lambda _p: file_exists)),
        "load_file": load_file,
        "pose_model": Model(),
        "pose_loaded": False,
        "POSE_ENABLED": pose_enabled,
        "POSE_WEIGHTS": WEIGHTS,
    }
    out = io.StringIO()
    with redirect_stdout(out):
        exec(compile(ast.Module(body=[_pose_load_block()], type_ignores=[]), "ai_inference.py", "exec"), ns)  # noqa: S102
    return opened, ns["pose_loaded"], out.getvalue()


def test_weights_are_not_read_while_the_flag_is_off() -> None:
    opened, loaded, out = _run(pose_enabled=False)
    assert opened == [] and loaded is False
    assert "PHANTOM_AI_POSE" in out                                  # says why, so it is not mistaken for a failure


def test_weights_are_read_exactly_once_when_the_flag_is_on() -> None:
    opened, loaded, _ = _run(pose_enabled=True)
    assert opened == [WEIGHTS] and loaded is True


def test_flag_on_but_file_missing_warns_and_reads_nothing() -> None:
    opened, loaded, out = _run(pose_enabled=True, file_exists=False)
    assert opened == [] and loaded is False and "not found" in out


def test_flag_off_and_file_missing_does_not_print_the_random_keypoints_warning() -> None:
    _, _, out = _run(pose_enabled=False, file_exists=False)
    assert "random" not in out                                       # nothing is expected to load, so nothing is "missing"


def test_no_other_statement_reads_the_pose_weights() -> None:
    assert SOURCE.count("load_file(POSE_WEIGHTS)") == 1
    refs = [n for n in ast.walk(TREE) if isinstance(n, ast.Name) and n.id == "POSE_WEIGHTS"]
    in_block = {id(n) for n in ast.walk(_pose_load_block()) if isinstance(n, ast.Name) and n.id == "POSE_WEIGHTS"}
    outside = [n for n in refs if id(n) not in in_block and not isinstance(n.ctx, ast.Store)]
    assert outside == [], "POSE_WEIGHTS must only be used inside the gated loading block"
