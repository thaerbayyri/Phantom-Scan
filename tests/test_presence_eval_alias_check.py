"""PS-FIX-40: alias arithmetic, the synthetic alias demonstration, the vital-band check and the classifier replica (no recordings read)."""
from __future__ import annotations

import inspect
import math

import numpy as np
import pytest

from scripts.presence_eval import alias_check as ac
from scripts.presence_eval import periodicity


# ---- alias arithmetic ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "f,fs,expected",
    [(100 / 3, 50.0, 50 / 3), (100 / 3, 64.0, 64 - 100 / 3), (100 / 3, 100.0, 100 / 3), (100 / 3, 20.0, 20 - 100 / 3 + 20),
     (200 / 3, 64.0, 200 / 3 - 64), (100.0, 100.0, 0.0), (5.0, 50.0, 5.0), (50.0, 100.0, 50.0)],
)
def test_alias_frequency(f: float, fs: float, expected: float) -> None:
    assert ac.alias_frequency(f, fs) == pytest.approx(expected, abs=1e-9)


def test_aliases_are_always_inside_zero_to_nyquist() -> None:
    for fs in (20.0, 50.0, 64.0, 100.0, 128.0):
        for k in range(1, 9):
            assert 0.0 <= ac.alias_frequency(k * ac.PING_HZ, fs) <= fs / 2 + 1e-9


def test_the_50_hz_grid_puts_the_ping_cadence_at_16_67_hz_inside_the_1_20_band() -> None:
    table = ac.ping_alias_table(50.0)
    assert table[0]["alias_hz"] == pytest.approx(16.667, abs=1e-3)
    assert any(r["k"] == 1 for r in ac.bands_hit(50.0)["periodicity_1_20"])


def test_64_hz_moves_the_fundamental_out_but_its_even_harmonics_land_inside_1_20() -> None:
    table = {r["k"]: r["alias_hz"] for r in ac.ping_alias_table(64.0)}
    assert table[1] == pytest.approx(30.667, abs=1e-3)           # out of band
    assert table[2] == pytest.approx(2.667, abs=1e-3) and table[4] == pytest.approx(5.333, abs=1e-3) and table[6] == pytest.approx(8.0, abs=1e-3)
    assert {r["k"] for r in ac.bands_hit(64.0)["periodicity_1_20"]} == {2, 4, 6}


def test_100_hz_is_three_times_the_ping_cadence_so_every_harmonic_folds_to_dc_or_33_hz() -> None:
    assert 100.0 == pytest.approx(3 * ac.PING_HZ)
    for r in ac.ping_alias_table(100.0, k_max=12):
        assert min(abs(r["alias_hz"]), abs(r["alias_hz"] - ac.PING_HZ)) < 1e-6, r
    assert all(not v for v in ac.bands_hit(100.0, k_max=12).values())


@pytest.mark.parametrize("fs", [20.0, 50.0, 64.0, 100.0])
def test_no_ping_harmonic_aliases_into_the_respiration_or_cardiac_band(fs: float) -> None:
    hits = ac.bands_hit(fs, k_max=12)
    assert hits["respiration"] == [] and hits["cardiac"] == []


# ---- the resampling paths (synthetic stream: real 33.3 Hz alternation + vital tones) -----------


@pytest.fixture(scope="module")
def stream() -> tuple[np.ndarray, np.ndarray]:
    return ac.synthetic_stream(seconds=90.0)


@pytest.mark.parametrize("fs,peak", [(50.0, 16.667), (64.0, 30.667), (100.0, 33.333)])
def test_linear_interpolation_puts_the_ping_line_where_the_arithmetic_says(stream, fs: float, peak: float) -> None:
    t, x = stream
    assert ac.peak_hz(ac.uniform_linear(t, x, fs), fs, 2.5, fs / 2) == pytest.approx(peak, abs=0.2)


def test_100_hz_shows_the_ping_line_at_its_true_frequency_not_an_alias(stream) -> None:
    t, x = stream
    y = ac.uniform_linear(t, x, 100.0)
    assert ac.alias_frequency(ac.PING_HZ, 100.0) == pytest.approx(ac.PING_HZ)
    assert ac.power_share(y, 100.0, 1.0, 20.0) < 0.05          # nothing of the ping line inside 1-20 Hz


def test_50_hz_grid_has_far_more_power_in_1_20_than_the_100_hz_grid(stream) -> None:
    t, x = stream
    assert ac.power_share(ac.uniform_linear(t, x, 50.0), 50.0, 15.0, 18.0) > 10 * ac.power_share(ac.uniform_linear(t, x, 100.0), 100.0, 15.0, 18.0)


def _paths(t: np.ndarray, x: np.ndarray) -> dict[str, tuple[np.ndarray, float]]:
    return {"lin50": (ac.uniform_linear(t, x, 50.0), 50.0), "lin64": (ac.uniform_linear(t, x, 64.0), 64.0), "lin100": (ac.uniform_linear(t, x, 100.0), 100.0),
            "nearest20": (ac.decimate_nearest(t, x), 20.0), "aa20": (ac.decimate_antialiased(t, x, 20.0), 20.0)}


def _tone_snr(y: np.ndarray, fs: float, tone_hz: float, lo_hz: float, hi_hz: float) -> float:
    """Peak power around the tone over the MEDIAN power of the band: how far the tone stands above the band's noise floor."""
    f, p = ac._spectrum(y, fs)
    band = (f >= lo_hz) & (f <= hi_hz)
    i = int(np.argmin(np.abs(f - tone_hz)))
    return float(p[max(i - 1, 0):i + 2].max() / np.median(p[band]))


@pytest.mark.parametrize("seed", [20261104, 7, 99])
def test_band_energy_respiration_is_recovered_on_every_path(seed: int) -> None:
    t, x = ac.synthetic_stream(seconds=90.0, seed=seed)
    for name, (y, fs) in _paths(t, x).items():
        assert ac.peak_hz(y, fs, 0.1, 0.5) == pytest.approx(0.3, abs=0.1), name


@pytest.mark.parametrize("seed", [20261104, 7, 99])
def test_band_energy_cardiac_tone_survives_linear_grids_and_antialiasing_but_not_nearest_sample_decimation(seed: int) -> None:
    """No alias line falls in a vital band, yet the production-like decimation (no anti-alias filter) smears the strong 33.3 Hz energy
    into a broadband skirt that buries a small cardiac tone: its SNR drops by about two orders of magnitude."""
    t, x = ac.synthetic_stream(seconds=90.0, seed=seed)
    snr = {name: _tone_snr(y, fs, 1.2, 0.8, 2.0) for name, (y, fs) in _paths(t, x).items()}
    for name in ("lin50", "lin64", "lin100", "aa20"):
        assert snr[name] > 50, (name, snr)
    assert snr["nearest20"] < 15, snr
    assert snr["aa20"] > 20 * snr["nearest20"], snr


def test_nearest_sample_decimation_folds_the_ping_line_to_6_67_hz_and_antialiasing_removes_it(stream) -> None:
    t, x = stream
    raw, aa = ac.decimate_nearest(t, x), ac.decimate_antialiased(t, x, 20.0)
    assert ac.peak_hz(raw, 20.0, 2.5, 10.0) == pytest.approx(6.667, abs=0.2)
    f, p_raw = ac._spectrum(raw, 20.0)
    f2, p_aa = ac._spectrum(aa, 20.0)
    band_raw = p_raw[(f > 6) & (f < 7.5)].sum() / p_raw[1:].sum()
    band_aa = p_aa[(f2 > 6) & (f2 < 7.5)].sum() / p_aa[1:].sum()
    assert band_raw > 0.5 and band_aa < 0.05, (band_raw, band_aa)


def test_the_classifier_high_frequency_ratio_is_inflated_by_the_alias(stream) -> None:
    t, x = stream
    raw = np.median([w["high_freq_ratio"] for w in ac.classifier_windows(ac.decimate_nearest(t, x))])
    aa = np.median([w["high_freq_ratio"] for w in ac.classifier_windows(ac.decimate_antialiased(t, x, 20.0))])
    assert raw > 0.5 and aa < 0.2 and raw > 4 * aa, (raw, aa)


def test_antialiased_decimation_requires_an_integer_ratio_to_the_fine_grid(stream) -> None:
    t, x = stream
    with pytest.raises(ValueError):
        ac.decimate_antialiased(t, x, 30.0)


def test_fir_lowpass_is_normalised_and_attenuates_the_stopband() -> None:
    h = ac.fir_lowpass(8.0, ac.FINE_HZ)
    assert h.sum() == pytest.approx(1.0)
    response = np.abs(np.fft.rfft(h, 4096))
    freqs = np.fft.rfftfreq(4096, 1.0 / ac.FINE_HZ)
    assert response[freqs < 2.0].min() > 0.99
    assert response[freqs > 14.0].max() < 0.01                   # > 40 dB down well before the 20 Hz decimated Nyquist alias region


# ---- the classifier replica ----------------------------------------------------------------------


def test_classifier_replica_pure_8hz_tone_is_all_high_frequency() -> None:
    n = np.arange(ac.CLASSIFIER_N)
    f = ac.classifier_features(np.sin(2 * np.pi * 8.0 * n / 20.0))
    assert f["high_freq_ratio"] > 0.95


def test_classifier_replica_slow_tone_has_no_high_frequency_power() -> None:
    n = np.arange(ac.CLASSIFIER_N)
    f = ac.classifier_features(np.sin(2 * np.pi * 0.5 * n / 20.0))
    assert f["high_freq_ratio"] < 0.01 and f["autocorr_max"] > 0.5


def test_classifier_replica_constant_window_is_unknown_not_a_crash() -> None:
    f = ac.classifier_features(np.full(ac.CLASSIFIER_N, 3.0))
    assert f["high_freq_ratio"] == 0.0 and f["autocorr_max"] == 0.0 and f["human_prob"] == 1.0 and f["label"] == "human"


def test_classifier_replica_labels_follow_the_ts_thresholds() -> None:
    rng = np.random.default_rng(1)
    noisy = rng.normal(0, 1, ac.CLASSIFIER_N)
    f = ac.classifier_features(noisy)
    assert f["label"] == ("human" if f["human_prob"] > 0.65 else "mechanical" if f["human_prob"] < 0.35 else "unknown")
    assert 0.0 <= f["human_prob"] <= 1.0


# ---- segments / replay plumbing ------------------------------------------------------------------


def test_segments_split_at_gaps_and_drop_short_pieces() -> None:
    t = np.concatenate([np.arange(0, 10000, 15), np.arange(12000, 14000, 15), np.arange(20000, 30000, 15)]).astype(np.int64)
    segs = ac.segments(t)
    assert len(segs) == 2 and all((t[b - 1] - t[a]) / 1000.0 >= ac.MIN_SEGMENT_S for a, b in segs)   # the 2 s piece is dropped


def test_summarize_windows_shares_sum_to_one() -> None:
    ws = [{"high_freq_ratio": 0.1, "human_prob": 0.9, "label": "human"}, {"high_freq_ratio": 0.9, "human_prob": 0.1, "label": "mechanical"},
          {"high_freq_ratio": 0.4, "human_prob": 0.5, "label": "unknown"}]
    s = ac.summarize_windows(ws)
    assert s["share_human"] + s["share_mechanical"] + s["share_unknown"] == pytest.approx(1.0)
    assert ac.summarize_windows([]) == {"windows": 0}


def test_a_window_suppresses_only_when_mechanical_and_human_prob_is_at_or_below_the_gate_constant() -> None:
    assert ac.MECHANICAL_REJECT_HUMAN_PROB_MAX == 0.2          # node-fusion.ts DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX
    ws = [{"high_freq_ratio": 0.9, "human_prob": 0.20, "label": "mechanical"},   # suppresses (at the constant)
          {"high_freq_ratio": 0.9, "human_prob": 0.21, "label": "mechanical"},   # mechanical but not confident enough
          {"high_freq_ratio": 0.5, "human_prob": 0.10, "label": "unknown"},      # label is not mechanical
          {"high_freq_ratio": 0.1, "human_prob": 0.90, "label": "human"}]
    assert ac.summarize_windows(ws)["share_would_suppress"] == pytest.approx(0.25)


def test_the_suppress_constant_matches_the_ts_source() -> None:
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "server" / "lib" / "node-fusion.ts").read_text(encoding="utf-8")
    assert 'process.env.PHANTOM_MECHANICAL_REJECT_MAX ?? "0.2"' in src


# ---- the tool fix: the periodicity grid ---------------------------------------------------------


def test_periodicity_default_grid_no_longer_aliases_the_ping_cadence_into_1_20_hz() -> None:
    assert not ac.bands_hit(periodicity.GRID_HZ)["periodicity_1_20"], periodicity.GRID_HZ
    assert periodicity.GRID_HZ == pytest.approx(3 * ac.PING_HZ)
    assert 50.0 in periodicity.GRIDS_HZ and periodicity.GRID_HZ in periodicity.GRIDS_HZ   # the old grid stays for comparison


def test_module_writes_only_from_main_under_the_out_dir() -> None:
    src = inspect.getsource(ac)
    assert src.count(".write_text(") == 1 and src.count("dump_json(") == 1
    for banned in ("write_bytes(", "open(", "shutil", "unlink("):
        assert banned not in src, banned
    assert math.isfinite(ac.PING_HZ)
