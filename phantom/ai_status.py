from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODEL_DIR = Path("ai model and densepose") / "model"


@dataclass(slots=True)
class AiSmokeStatus:
    mode: str
    ready: bool
    reason: str
    model_dir: str
    embedding_shape: tuple[int, ...] | None = None
    adapters: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ready": self.ready,
            "reason": self.reason,
            "model_dir": self.model_dir,
            "embedding_shape": list(self.embedding_shape) if self.embedding_shape else None,
            "adapters": self.adapters or {},
        }


def probe_ai_stack(model_dir: str | Path = DEFAULT_MODEL_DIR) -> AiSmokeStatus:
    """Checks optional AI dependencies and the 8-dim to 128-dim encoder path."""

    model_path = Path(model_dir)
    adapters = {
        "node_1": "active" if (model_path / "node-1.json").exists() else "missing",
        "node_2": "active" if (model_path / "node-2.json").exists() else "missing",
    }

    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from safetensors.torch import load_file
    except Exception as exc:  # pragma: no cover - exercised when deps are absent
        return AiSmokeStatus(
            mode="deterministic_only",
            ready=False,
            reason=f"missing_ai_dependency:{type(exc).__name__}:{exc}",
            model_dir=str(model_path),
            adapters=adapters,
        )

    weights_path = model_path / "csi-embed-v2.safetensors"
    if not weights_path.exists():
        return AiSmokeStatus(
            mode="deterministic_only",
            ready=False,
            reason=f"missing_model:{weights_path}",
            model_dir=str(model_path),
            adapters=adapters,
        )

    class Enc(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.w1 = nn.Linear(8, 64)
            self.bn1 = nn.BatchNorm1d(64)
            self.w2 = nn.Linear(64, 128)
            self.bn2 = nn.BatchNorm1d(128)

        def forward(self, x: Any) -> Any:
            h = F.gelu(self.bn1(self.w1(x)))
            pre = self.bn2(self.w2(h))
            return F.normalize(pre, dim=-1)

    try:
        model = Enc()
        model.load_state_dict(load_file(str(weights_path)), strict=False)
        model.eval()
        with torch.no_grad():
            output = model(torch.zeros((2, 8), dtype=torch.float32))
    except Exception as exc:
        return AiSmokeStatus(
            mode="deterministic_only",
            ready=False,
            reason=f"model_load_failed:{type(exc).__name__}:{exc}",
            model_dir=str(model_path),
            adapters=adapters,
        )

    shape = tuple(int(dim) for dim in output.shape)
    if shape != (2, 128):
        return AiSmokeStatus(
            mode="deterministic_only",
            ready=False,
            reason=f"unexpected_embedding_shape:{shape}",
            model_dir=str(model_path),
            embedding_shape=shape,
            adapters=adapters,
        )

    return AiSmokeStatus(
        mode="advisory",
        ready=True,
        reason="ok",
        model_dir=str(model_path),
        embedding_shape=shape,
        adapters=adapters,
    )
