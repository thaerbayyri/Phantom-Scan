"""Training-folder guard: every refusal, the pass case, and the two training scripts' exit codes."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

from phantom.training_guard import (
    UnsafeTrainingRoom,
    check_training_room,
    enforce_training_room,
    room_name_refusal,
    room_refusals,
)

REPO = Path(__file__).resolve().parents[1]


def _write(root: Path, room: str, name: str, *, header_room: str | None = None, channel: int | None = None) -> Path:
    folder = root / room
    folder.mkdir(parents=True, exist_ok=True)
    capture = {"channel": channel, "bandwidthMHz": None, "bssid": None, "source": "not_recorded" if channel is None else "operator_env"}
    header = {"type": "header", "schema": 2, "roomId": header_room or room, "subjectId": "p1", "label": "still", "count": 1, "capture": capture}
    path = folder / name
    path.write_text(json.dumps(header) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "room",
    ["campaign-raw-2026-11", "campaign-2026-11", "soak-2026-11", "smoke-2026-11", "smoke-test", "epoch2-ref-2026-11"],
)
def test_refuses_campaign_soak_smoke_and_reference_room_ids(tmp_path: Path, room: str) -> None:
    _write(tmp_path, room, f"{room}__c1__still__20261111T112158Z.jsonl")

    assert room_name_refusal(room) is not None
    with pytest.raises(UnsafeTrainingRoom, match="not training data"):
        check_training_room(tmp_path, room)


def test_refuses_a_refused_room_id_even_when_the_folder_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(UnsafeTrainingRoom):
        check_training_room(tmp_path, "soak-2026-11")


@pytest.mark.parametrize("room", ["room1", "train-ep2-2026-11", "train-c1-ep1-2026-11"])
def test_passes_a_training_room_and_leaves_its_files_untouched(tmp_path: Path, room: str) -> None:
    first = _write(tmp_path, room, f"{room}__p1__still__20261112T090000Z.jsonl")
    second = _write(tmp_path, room, f"{room}__none__empty__20261112T091000Z.jsonl")
    before = (first.read_bytes(), second.read_bytes())

    assert room_refusals(tmp_path, room) == []
    assert check_training_room(tmp_path, room) == []
    assert (first.read_bytes(), second.read_bytes()) == before


def test_passes_a_room_folder_that_does_not_exist(tmp_path: Path) -> None:
    assert check_training_room(tmp_path, "train-ep2-2026-11") == []


def test_refuses_a_file_whose_header_room_differs_from_the_folder(tmp_path: Path) -> None:
    _write(tmp_path, "train-ep2-2026-11", "train-ep2-2026-11__p1__still__20261112T090000Z.jsonl")
    _write(tmp_path, "train-ep2-2026-11", "campaign-raw-2026-11__c1__still__20261111T112158Z.jsonl", header_room="campaign-raw-2026-11")

    with pytest.raises(UnsafeTrainingRoom, match="header roomId 'campaign-raw-2026-11' differs"):
        check_training_room(tmp_path, "train-ep2-2026-11")


def test_refuses_recordings_from_two_channels_in_one_folder(tmp_path: Path) -> None:
    _write(tmp_path, "room1", "room1__p1__still__20261101T090000Z.jsonl", channel=6)
    _write(tmp_path, "room1", "room1__p1__still__20261112T090000Z.jsonl", channel=2)

    with pytest.raises(UnsafeTrainingRoom, match="different link states"):
        check_training_room(tmp_path, "room1")


def test_a_missing_channel_is_ignored_and_one_shared_channel_passes(tmp_path: Path) -> None:
    _write(tmp_path, "room1", "room1__p1__still__20261101T090000Z.jsonl", channel=None)
    _write(tmp_path, "room1", "room1__p1__still__20261112T090000Z.jsonl", channel=2)
    _write(tmp_path, "room1", "room1__p1__walking__20261112T091000Z.jsonl", channel=2)

    assert check_training_room(tmp_path, "room1") == []


def test_allow_unsafe_returns_the_reasons_as_warnings_and_is_off_by_default(tmp_path: Path) -> None:
    _write(tmp_path, "smoke-test", "smoke-test__s1__empty__20261109T200248Z.jsonl")
    refused, allowed = io.StringIO(), io.StringIO()

    assert enforce_training_room(tmp_path, "smoke-test", stream=refused) is False
    assert enforce_training_room(tmp_path, "smoke-test", allow_unsafe=True, stream=allowed) is True
    assert refused.getvalue().startswith("REFUSED: ")
    assert "WARNING: --allow-unsafe is set" in allowed.getvalue()
    assert len(check_training_room(tmp_path, "smoke-test", allow_unsafe=True)) == 1


def _script_main(name: str):
    spec = importlib.util.spec_from_file_location(f"_guard_test_{name}", REPO / "scripts" / "train" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


@pytest.mark.parametrize("script, needs", [("train_activity", "sklearn"), ("train_count", "torch")])
def test_training_scripts_exit_2_on_a_refused_room_and_1_on_an_empty_safe_room(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], script: str, needs: str
) -> None:
    pytest.importorskip(needs)
    main = _script_main(script)
    _write(tmp_path, "campaign-raw-2026-11", "campaign-raw-2026-11__c1__still__20261111T112158Z.jsonl")
    common = ["--data-root", str(tmp_path), "--models-root", str(tmp_path / "models")]

    monkeypatch.setattr(sys, "argv", [script, "--room", "campaign-raw-2026-11", *common])
    refused_code = main()
    refused_err = capsys.readouterr().err
    monkeypatch.setattr(sys, "argv", [script, "--room", "train-ep2-2026-11", *common])
    empty_code = main()

    assert refused_code == 2
    assert "REFUSED: room id 'campaign-raw-2026-11' matches 'campaign-*'" in refused_err
    assert empty_code == 1
    assert not (tmp_path / "models").exists()
