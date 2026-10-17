import json
from pathlib import Path

import numpy as np
import pytest

from phantom.activity_model import ActivityModel
from phantom.activity_train import TrainingRefused, train_activity
from phantom.dataset import NodeStream, Recording, load_room_dataset

FS = 40.0
# label -> (wave amplitude, (min Hz, max Hz)). walking and active share the
# SAME amplitude (hence the same variance) and differ only in dominant
# frequency, so a variance-only motion heuristic cannot separate them.
LABEL_SPEC = {
    "empty": (0.0, (1.0, 1.0)),
    "empty_fan": (0.05, (1.0, 2.0)),
    "still": (0.5, (0.25, 0.35)),
    "walking": (1.2, (0.8, 1.4)),
    "active": (1.2, (2.4, 3.4)),
}


def _stream(spec: tuple[float, tuple[float, float]], seconds: float, seed: int) -> NodeStream:
    amp, (flo, fhi) = spec
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    t = np.arange(n) * (1000.0 / FS)
    base = 10.0 + 2.0 * np.sin(np.linspace(0, 4 * np.pi, 51))
    wave = amp * np.sin(2 * np.pi * rng.uniform(flo, fhi) * np.arange(n) / FS)[:, None]
    amps = base[None, :] + wave * rng.uniform(0.5, 1.5, size=(1, 51)) + rng.normal(0, 0.06, size=(n, 51))
    return NodeStream(t_ms=t, amps=amps, rssi=np.full(n, -45.0))

def _recording(label: str, idx: int, day: str, spec=None, seconds: float = 20.0, seed: int | None = None) -> Recording:
    m = LABEL_SPEC[label] if spec is None else spec
    return Recording(
        recording_id=f"room__s1__{label}__{day}T000{idx}00Z",
        room_id="room",
        subject_id="s1",
        label=label,
        count=0 if label.startswith("empty") else 1,
        day=day,
        nodes={n: _stream(m, seconds, seed=(idx * 17 + n) if seed is None else seed + n) for n in (1, 2)},
    )


def _separable_dataset() -> list[Recording]:
    recs = []
    idx = 0
    for day in ("20260901", "20260902", "20260903"):
        for label in ("empty", "empty_fan", "still", "walking", "active"):
            idx += 1
            recs.append(_recording(label, idx, day))
    return recs


def test_trains_exports_and_reloads_a_model_that_beats_both_baselines(tmp_path: Path):
    report = train_activity(_separable_dataset(), tmp_path, group_by="recording", n_permutations=10)
    assert report["metrics"]["model_balanced_accuracy"] > report["metrics"]["majority_balanced_accuracy"] + 0.2
    assert report["metrics"]["model_balanced_accuracy"] >= report["metrics"]["heuristic_balanced_accuracy"]
    model = ActivityModel.load(tmp_path / "activity.json")
    assert set(model.classes) == {"empty", "still", "walking", "active"}
    assert (tmp_path / "activity.report.json").exists()


def test_exported_model_classifies_new_windows_correctly(tmp_path: Path):
    from phantom.features import extract_window_features

    train_activity(_separable_dataset(), tmp_path, group_by="recording")
    model = ActivityModel.load(tmp_path / "activity.json")
    for label, expected in (("empty", "empty"), ("walking", "walking"), ("active", "active")):
        s = _stream(LABEL_SPEC[label], 3.0, seed=999)
        feats = [extract_window_features(s.amps[i : i + 40], s.rssi[i : i + 40], FS) for i in (0, 40, 80)]
        pred, conf, _ = model.predict_fused(feats)
        assert pred == expected, f"{label} -> {pred} ({conf:.2f})"


def test_refuses_to_export_when_labels_carry_no_signal(tmp_path: Path):
    # Byte-identical signal under every label: nothing can separate the classes.
    recs = []
    idx = 0
    for day in ("20260901", "20260902", "20260903"):
        for label in ("empty", "still", "walking", "active"):
            idx += 1
            recs.append(_recording(label, idx, day, spec=(0.5, (0.8, 2.5)), seed=7))
    with pytest.raises(TrainingRefused):
        train_activity(recs, tmp_path, group_by="recording", n_permutations=30)
    assert not (tmp_path / "activity.json").exists()


def test_refuses_with_too_few_recordings_per_class(tmp_path: Path):
    recs = [_recording("empty", 1, "20260901"), _recording("walking", 2, "20260901")]
    with pytest.raises(TrainingRefused, match="recordings"):
        train_activity(recs, tmp_path, group_by="recording")


def test_people_count_labels_are_not_used_by_the_activity_model(tmp_path: Path):
    recs = _separable_dataset() + [_recording("two_people", 90, "20260901", spec=(2.0, (1.0, 2.0)))]
    report = train_activity(recs, tmp_path, group_by="recording")
    assert "two_people" not in json.dumps(report["class_counts"])


def test_load_room_dataset_round_trips_the_recorder_format(tmp_path: Path):
    room = tmp_path / "room"
    room.mkdir()
    stem = "room__s1__walking__20260901T101500Z"
    header = {"type": "header", "schema": 1, "roomId": "room", "subjectId": "s1", "label": "walking", "count": 1}
    for part, name in ((1, f"{stem}.jsonl"), (2, f"{stem}.part2.jsonl")):
        lines = [json.dumps({**header, "part": part})]
        for i in range(3):
            lines.append(json.dumps({"type": "frame", "t": part * 1000 + i, "n": 2, "rssi": -44, "a": [1.0, 2.0, 3.0]}))
        (room / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    recs = load_room_dataset(tmp_path, "room")
    assert len(recs) == 1 and recs[0].day == "20260901" and recs[0].label == "walking"
    assert recs[0].nodes[2].amps.shape == (6, 3)
    assert np.all(np.diff(recs[0].nodes[2].t_ms) > 0)
