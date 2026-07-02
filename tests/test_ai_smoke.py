from pathlib import Path

import pytest

from phantom.ai_status import probe_ai_stack


def test_ai_probe_fails_closed_for_missing_model_dir(tmp_path: Path):
    status = probe_ai_stack(tmp_path / "missing-model")
    assert status.ready is False
    assert status.mode == "deterministic_only"
    assert status.reason.startswith(("missing_ai_dependency:", "missing_model:"))


def test_ai_probe_loads_encoder_when_dependencies_and_weights_are_available():
    status = probe_ai_stack()
    if not status.ready:
        pytest.skip(status.reason)
    assert status.mode == "advisory"
    assert status.embedding_shape == (2, 128)
    assert status.adapters is not None
    assert status.adapters["node_1"] in {"active", "missing"}
    assert status.adapters["node_2"] in {"active", "missing"}
