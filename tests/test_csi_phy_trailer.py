"""PS-FIX-36 extended: the Python CSI parser tolerates the optional 16-byte PHY trailer (parse as plain, ignore the trailer).

Golden frames are the same fixtures the TypeScript tests use (tests/fixtures/adr018_phy_trailer_frame.hex and
phy_trailer_golden.json), so both parsers are pinned to identical bytes. The three consumers named in the change are covered:
phantom.protocol.parse_csi_frame / parse_udp_packet (phantom/ingest.py), scripts/ai_inference.py parse_csi_packet (extracted from the
source, because the script itself pulls in torch) and the scripts/record_dataset.py parse -> amplitudes -> frame_record path.
"""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path

import numpy as np
import pytest

from phantom.protocol import CsiFrameV1, InvalidPacket, PHY_TRAILER_SIZE, parse_csi_frame, parse_udp_packet
from phantom.subcarriers import lltf_amplitudes
from scripts.record_dataset import frame_record

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN_FRAME = bytes.fromhex((FIXTURES / "adr018_phy_trailer_frame.hex").read_text(encoding="utf-8").strip())
GOLDEN_TRAILERS = {t["name"]: bytes.fromhex(t["hex"]) for t in json.loads((FIXTURES / "phy_trailer_golden.json").read_text(encoding="utf-8"))["trailers"]}
PLAIN_LEN = 160  # 32-byte header + 64 subcarriers x 2 bytes x 1 antenna
PLAIN_FRAME = GOLDEN_FRAME[:PLAIN_LEN]
RX_NS = 123_456_789  # fixed so two parses of the same frame compare equal


def test_golden_frame_is_the_plain_frame_plus_the_golden_trailer() -> None:
    assert len(GOLDEN_FRAME) == PLAIN_LEN + PHY_TRAILER_SIZE == 176
    assert GOLDEN_FRAME[PLAIN_LEN:] == GOLDEN_TRAILERS["ht_ampdu_qos"]


def test_plain_golden_frame_parses_as_before() -> None:
    f = parse_csi_frame(PLAIN_FRAME, "10.0.0.2", 5005, RX_NS)
    assert isinstance(f, CsiFrameV1)
    assert (f.node_id, f.n_antennas, f.n_subcarriers, f.seq, f.channel, f.freq_mhz) == (2, 1, 64, 1000, 2, 2417)
    assert (f.rssi_dbm, f.noise_dbm) == (-30, -92)
    assert len(f.iq_bytes) == 128


def test_trailer_frame_parses_as_the_same_plain_frame() -> None:
    plain = parse_csi_frame(PLAIN_FRAME, "10.0.0.2", 5005, RX_NS)
    ext = parse_csi_frame(GOLDEN_FRAME, "10.0.0.2", 5005, RX_NS)
    assert isinstance(plain, CsiFrameV1) and isinstance(ext, CsiFrameV1)
    assert ext == plain  # every field, including iq_bytes: the trailer is ignored
    assert len(ext.iq_bytes) == 128  # the trailer is not part of the I/Q


def test_trailer_frame_goes_through_the_ingest_dispatch_too() -> None:
    parsed = parse_udp_packet(GOLDEN_FRAME, ("10.0.0.2", 5005), RX_NS)
    assert isinstance(parsed, CsiFrameV1)
    assert parsed == parse_udp_packet(PLAIN_FRAME, ("10.0.0.2", 5005), RX_NS)


@pytest.mark.parametrize("name", sorted(GOLDEN_TRAILERS))
def test_collision_plain_frame_whose_iq_ends_with_a_valid_trailer_parses_as_plain(name: str) -> None:
    """The trailer is only looked for at exactly plain + 16 bytes, so I/Q that looks like a trailer stays I/Q."""
    trailer = GOLDEN_TRAILERS[name]
    frame = PLAIN_FRAME[: PLAIN_LEN - PHY_TRAILER_SIZE] + trailer  # same length as the plain frame
    assert len(frame) == PLAIN_LEN
    f = parse_csi_frame(frame, "10.0.0.2", 5005, RX_NS)
    assert isinstance(f, CsiFrameV1)
    assert len(f.iq_bytes) == 128
    assert f.iq_bytes[-PHY_TRAILER_SIZE:] == trailer  # the look-alike bytes were kept as I/Q, not stripped


def test_collision_with_a_real_trailer_after_look_alike_iq_strips_only_the_real_one() -> None:
    look_alike = GOLDEN_TRAILERS["ht40_stbc_sgi"]
    base = PLAIN_FRAME[: PLAIN_LEN - PHY_TRAILER_SIZE] + look_alike
    f = parse_csi_frame(base + GOLDEN_TRAILERS["ht_ampdu_qos"], "10.0.0.2", 5005, RX_NS)
    assert isinstance(f, CsiFrameV1)
    assert f.iq_bytes[-PHY_TRAILER_SIZE:] == look_alike
    assert len(f.iq_bytes) == 128


def _bad_trailer_frames() -> dict[str, bytes]:
    good = GOLDEN_TRAILERS["ht_ampdu_qos"]
    bad_sum = bytearray(good)
    bad_sum[6] ^= 0x10
    bad_magic = bytearray(good)
    bad_magic[0] ^= 0x01
    return {
        "bad checksum": PLAIN_FRAME + bytes(bad_sum),
        "bad magic": PLAIN_FRAME + bytes(bad_magic),
        "all zero tail": PLAIN_FRAME + bytes(PHY_TRAILER_SIZE),
        "trailer one byte short": PLAIN_FRAME + good[:-1],
        "trailer one byte long": PLAIN_FRAME + good + b"\x00",
        "plain plus one byte": PLAIN_FRAME + b"\x00",
        "plain minus one byte": PLAIN_FRAME[:-1],
    }


@pytest.mark.parametrize("case", sorted(_bad_trailer_frames()))
def test_anything_that_is_not_plain_or_plain_plus_a_valid_trailer_is_still_rejected(case: str) -> None:
    r = parse_csi_frame(_bad_trailer_frames()[case], "10.0.0.2", 5005, RX_NS)
    assert isinstance(r, InvalidPacket)
    assert r.reason == "csi_payload_length_mismatch"


def _sidecar_parse_csi_packet():
    """Run the real parse_csi_packet body from scripts/ai_inference.py without importing the (torch) script."""
    tree = ast.parse((ROOT / "scripts" / "ai_inference.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "parse_csi_packet")
    ns: dict = {"CsiFrameV1": CsiFrameV1, "parse_csi_frame": parse_csi_frame, "lltf_amplitudes": lltf_amplitudes, "time": time}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "ai_inference.py", "exec"), ns)  # noqa: S102 - our own repo source
    return ns["parse_csi_packet"]


def test_sidecar_parse_csi_packet_accepts_a_trailer_frame_with_identical_output() -> None:
    parse = _sidecar_parse_csi_packet()
    plain = parse(PLAIN_FRAME)
    ext = parse(GOLDEN_FRAME)
    assert plain is not None and ext is not None
    assert (ext["node_id"], ext["rssi"]) == (plain["node_id"], plain["rssi"]) == (2, -30)
    assert np.array_equal(ext["mags"], plain["mags"]) and len(ext["mags"]) == 51
    assert parse(PLAIN_FRAME + b"\x00") is None  # still rejects a malformed length


def test_record_dataset_path_gives_identical_records_with_and_without_trailer() -> None:
    """record_dataset.record(): parse_csi_frame -> lltf_amplitudes -> frame_record. Same input bytes in, same record out."""
    def record_for(data: bytes) -> dict:
        frame = parse_csi_frame(data, "10.0.0.2", 5005, RX_NS)
        assert isinstance(frame, CsiFrameV1)
        amps = lltf_amplitudes(frame.iq_bytes, frame.n_subcarriers)
        return frame_record(1_000.0, frame.node_id, frame.rssi_dbm, amps)

    assert record_for(GOLDEN_FRAME) == record_for(PLAIN_FRAME)
