"""LLTF data-subcarrier amplitude extraction (Python mirror of the TS ingest).

Must stay identical to server/lib/csi-subcarriers.ts so the AI sidecar and
the deterministic pipeline see the same per-subcarrier amplitudes:

* ESP-IDF stores each subcarrier as two int8 bytes, IMAGINARY first, then
  real (wifi_csi_info_t; ESP-IDF Wi-Fi Vendor Features, CSI section).
* Buffers are LLTF, HT-LTF, STBC-HT-LTF 64-entry blocks; every frame type
  carries the LLTF block first, so only it is used (constant length).
* LLTF order is subcarrier 0..31 then -32..-1. Data subcarriers +-1..26 are
  kept, minus index 1 (ESP32-S3 first_word_invalid) -> 51 amplitudes.
"""

from __future__ import annotations

import numpy as np

LLTF_LENGTH = 64
LLTF_DATA_INDICES: tuple[int, ...] = tuple(list(range(2, 27)) + list(range(38, 64)))
NUM_DATA_SUBCARRIERS = len(LLTF_DATA_INDICES)  # 51


def lltf_amplitudes(iq_bytes: bytes, n_subcarriers: int) -> np.ndarray:
    """Antenna-0 amplitudes of the LLTF data subcarriers.

    Frames shorter than one LLTF block (legacy/synthetic senders) return every
    entry, matching reduceCsiFrame's fallback.
    """
    if n_subcarriers <= 0 or len(iq_bytes) < n_subcarriers * 2:
        raise ValueError(f"iq payload too short for {n_subcarriers} subcarriers")
    pairs = np.frombuffer(iq_bytes, dtype=np.int8, count=n_subcarriers * 2).reshape(n_subcarriers, 2)
    imag = pairs[:, 0].astype(np.float64)
    real = pairs[:, 1].astype(np.float64)
    amps = np.hypot(real, imag)
    if n_subcarriers >= LLTF_LENGTH:
        return amps[list(LLTF_DATA_INDICES)]
    return amps
