"""
Phantom Scan Project — RF Validation: Dual-Target Analyzer
Brief: Full offline analysis pipeline for resolving two independent breathing
       signatures from captured CSI data. Implements Algorithms 3.A through 3.D
       from VTP-PS-002 (RF Validation Protocol).

This script performs:
  A. Phase Sanitization (SFO/PDD removal via cross-subcarrier regression)
  B. Top-K Subcarrier Selection for Target B (variance + spectral clustering)
  C. Spectral Separation via FFT PSD (dual-peak identification in 0.1–0.5 Hz)
  D. Variance Mapping / Motion Energy masking analysis
  E. SNR computation for both targets
  F. Comprehensive matplotlib visualization with dual-target plots

Usage:
    python dual_target_analyzer.py captured_data.csv
    python dual_target_analyzer.py captured_data.csv --ground-truth-a 15 --ground-truth-b 24

Dependencies:
    pip install numpy matplotlib scipy
"""

import argparse             # Command-line argument parsing
import csv                  # CSV reading
import os                   # File and path operations
import sys                  # Exit codes and path manipulation
from typing import List, Tuple, Dict, Optional

import numpy as np          # Numerical computing (FFT, variance, linear algebra)
import matplotlib           # Plotting backend
matplotlib.use('Agg')       # Non-interactive backend for server/headless use
import matplotlib.pyplot as plt          # Plotting API
from matplotlib.gridspec import GridSpec  # Complex subplot layouts

# Import our phase sanitizer from the same validation package
sys.path.insert(0, os.path.dirname(__file__))
from phase_sanitizer import PhaseSanitizer


# ══════════════════════════════════════════════════════════════════
# Constants — matching firmware and protocol specifications
# ══════════════════════════════════════════════════════════════════

# CSI sample rate (Hz) — matches edge_processing.c line 598
SAMPLE_RATE = 20.0

# Number of HT20 subcarriers
N_SUBCARRIERS = 52

# Breathing frequency band (Hz) — matches edge_processing.c biquad design (line 879)
BREATHING_BAND_LO = 0.1   # Lower bound: 6 BPM
BREATHING_BAND_HI = 0.5   # Upper bound: 30 BPM

# Target A expected breathing frequency (Hz) — 15 BPM = 0.25 Hz
TARGET_A_EXPECTED_HZ = 0.25

# Target B expected breathing frequency (Hz) — 24 BPM = 0.40 Hz
TARGET_B_EXPECTED_HZ = 0.40

# Minimum valley depth (dB) between two PSD peaks for separation to pass
MIN_VALLEY_DEPTH_DB = 3.0

# Minimum masking ratio for Target B to not be critically masked
MIN_MASKING_RATIO = 0.10

# SNR thresholds (dB)
SNR_THRESHOLD_TARGET_A = 10.0  # Near target: ≥ 10 dB required
SNR_THRESHOLD_TARGET_B = 5.0   # Far NLOS target: ≥ 5 dB required


# ══════════════════════════════════════════════════════════════════
# CSV Data Loader
# ══════════════════════════════════════════════════════════════════

def load_csv_capture(filepath: str) -> Dict:
    """
    Load a CSV capture file produced by nlos_capture.py.

    Parses the CSV header to find phase_sc* and amplitude_sc* columns,
    then loads all frames into numpy arrays keyed by node_id.

    Args:
        filepath: Path to the CSV capture file.

    Returns:
        Dict with keys:
            'timestamps':   np.array of timestamps (ms)
            'node_ids':     np.array of node IDs per frame
            'rssi':         np.array of RSSI values
            'phases':       np.array shape (n_frames, n_subcarriers) — phase in radians
            'amplitudes':   np.array shape (n_frames, n_subcarriers) — amplitude
    """
    # Initialize collection lists
    timestamps = []
    node_ids = []
    rssi_values = []
    all_phases = []
    all_amplitudes = []

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse metadata columns
            timestamps.append(int(row['timestamp_ms']))
            node_ids.append(int(row['node_id']))
            rssi_values.append(int(row['rssi']))

            # Parse per-subcarrier phase columns (phase_sc0 through phase_sc51)
            phases = []
            for sc in range(N_SUBCARRIERS):
                col_name = f'phase_sc{sc}'
                # Use 0.0 if column is missing (handles shorter subcarrier counts)
                phases.append(float(row.get(col_name, 0.0)))
            all_phases.append(phases)

            # Parse per-subcarrier amplitude columns (amplitude_sc0 through amplitude_sc51)
            amplitudes = []
            for sc in range(N_SUBCARRIERS):
                col_name = f'amplitude_sc{sc}'
                amplitudes.append(float(row.get(col_name, 0.0)))
            all_amplitudes.append(amplitudes)

    return {
        'timestamps': np.array(timestamps, dtype=np.float64),
        'node_ids': np.array(node_ids, dtype=np.int32),
        'rssi': np.array(rssi_values, dtype=np.float64),
        'phases': np.array(all_phases, dtype=np.float64),
        'amplitudes': np.array(all_amplitudes, dtype=np.float64),
    }


# ══════════════════════════════════════════════════════════════════
# Algorithm 3.B — Top-K Subcarrier Selection + Spectral Clustering
# ══════════════════════════════════════════════════════════════════

def compute_welford_variance(data: np.ndarray) -> np.ndarray:
    """
    Compute Welford's online variance for each subcarrier column.

    This is the same algorithm as edge_processing.c lines 153-165,
    reimplemented in Python for offline analysis.

    Welford's method maintains running mean and M2 statistics:
        count += 1
        delta = x - mean
        mean += delta / count
        delta2 = x - mean
        M2 += delta * delta2
        variance = M2 / (count - 1)

    This is numerically stable (unlike naive sum-of-squares).

    Args:
        data: Shape (n_frames, n_subcarriers) — phase or amplitude time series.

    Returns:
        np.array of shape (n_subcarriers,) — variance for each subcarrier.
    """
    n_frames, n_sc = data.shape

    # Initialize Welford accumulators per subcarrier
    means = np.zeros(n_sc)      # Running mean
    m2s = np.zeros(n_sc)        # Running sum of squared deviations
    counts = np.zeros(n_sc)     # Sample count

    # Process each frame sequentially (Welford is an online algorithm)
    for frame_idx in range(n_frames):
        counts += 1
        # Delta from current mean
        delta = data[frame_idx] - means
        # Update mean
        means += delta / counts
        # Delta from *updated* mean
        delta2 = data[frame_idx] - means
        # Accumulate squared deviation
        m2s += delta * delta2

    # Compute final variance: M2 / (count - 1) for sample variance
    variances = np.where(counts > 1, m2s / (counts - 1), 0.0)
    return variances


def spectral_cluster_subcarriers(
    phase_data: np.ndarray,
    target_a_hz: float = TARGET_A_EXPECTED_HZ,
    target_b_hz: float = TARGET_B_EXPECTED_HZ,
    tolerance_hz: float = 0.05,
) -> Tuple[List[int], List[int]]:
    """
    Cluster subcarriers into two groups based on their dominant breathing frequency.

    For each subcarrier, compute the FFT PSD in the breathing band and find the
    dominant peak frequency. Subcarriers peaking near target_a_hz are assigned
    to Group A; those peaking near target_b_hz are assigned to Group B.

    This implements Algorithm 3.B's spectral clustering strategy.

    Args:
        phase_data:     Shape (n_frames, n_subcarriers) — sanitized phase data.
        target_a_hz:    Expected breathing frequency for Target A (default 0.25 Hz).
        target_b_hz:    Expected breathing frequency for Target B (default 0.40 Hz).
        tolerance_hz:   Frequency tolerance for group assignment (default ±0.05 Hz).

    Returns:
        Tuple of (group_a_indices, group_b_indices) — lists of subcarrier indices.
    """
    n_frames, n_sc = phase_data.shape

    group_a = []  # Subcarriers dominated by Target A (0.25 Hz)
    group_b = []  # Subcarriers dominated by Target B (0.40 Hz)

    # Compute frequency axis for the FFT
    freqs = np.fft.rfftfreq(n_frames, d=1.0 / SAMPLE_RATE)

    # Create masks for the breathing frequency band
    breathing_mask = (freqs >= BREATHING_BAND_LO) & (freqs <= BREATHING_BAND_HI)

    for sc in range(n_sc):
        # Extract this subcarrier's time series (remove DC offset)
        signal = phase_data[:, sc] - np.mean(phase_data[:, sc])

        # Apply Hanning window to reduce spectral leakage
        windowed = signal * np.hanning(n_frames)

        # Compute FFT and power spectrum
        fft_result = np.fft.rfft(windowed)
        psd = np.abs(fft_result) ** 2

        # Find the dominant peak within the breathing band
        psd_band = psd.copy()
        psd_band[~breathing_mask] = 0  # Zero out frequencies outside breathing band

        if np.max(psd_band) < 1e-10:
            continue  # No significant energy in breathing band — skip this subcarrier

        # Find peak frequency
        peak_idx = np.argmax(psd_band)
        peak_freq = freqs[peak_idx]

        # Assign to Group A or Group B based on proximity to expected frequencies
        dist_a = abs(peak_freq - target_a_hz)
        dist_b = abs(peak_freq - target_b_hz)

        if dist_a < dist_b and dist_a <= tolerance_hz:
            group_a.append(sc)  # This subcarrier tracks Target A
        elif dist_b <= tolerance_hz:
            group_b.append(sc)  # This subcarrier tracks Target B

    return group_a, group_b


# ══════════════════════════════════════════════════════════════════
# Algorithm 3.C — Spectral Separation via FFT PSD
# ══════════════════════════════════════════════════════════════════

def compute_psd_for_group(
    phase_data: np.ndarray,
    subcarrier_indices: List[int],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the Power Spectral Density for a group of subcarriers.

    Averages the PSD across all subcarriers in the group to produce
    a single representative spectrum.

    Args:
        phase_data:          Shape (n_frames, n_subcarriers) — sanitized phases.
        subcarrier_indices:  List of subcarrier indices in this group.

    Returns:
        Tuple of (frequencies, psd_db) — frequency axis in Hz and PSD in dB.
    """
    n_frames = phase_data.shape[0]

    # Compute frequency axis
    freqs = np.fft.rfftfreq(n_frames, d=1.0 / SAMPLE_RATE)

    # Average PSD across all subcarriers in the group
    avg_psd = np.zeros(len(freqs))

    for sc in subcarrier_indices:
        # Remove DC offset from this subcarrier's time series
        signal = phase_data[:, sc] - np.mean(phase_data[:, sc])

        # Apply Hanning window to reduce spectral leakage at bin boundaries
        windowed = signal * np.hanning(n_frames)

        # Compute FFT → PSD
        fft_result = np.fft.rfft(windowed)
        psd = np.abs(fft_result) ** 2
        avg_psd += psd

    # Average across subcarriers
    if len(subcarrier_indices) > 0:
        avg_psd /= len(subcarrier_indices)

    # Convert to dB scale (with floor to avoid -inf)
    psd_db = 10 * np.log10(avg_psd + 1e-15)

    return freqs, psd_db


def find_dual_peaks(
    freqs: np.ndarray,
    psd_db: np.ndarray,
) -> Dict:
    """
    Find two distinct peaks in the breathing band PSD and measure their separation.

    This implements Algorithm 3.C's spectral separation test.

    Args:
        freqs:  Frequency axis in Hz.
        psd_db: PSD in dB scale.

    Returns:
        Dict with:
            'peak1_hz', 'peak1_db': First (strongest) peak
            'peak2_hz', 'peak2_db': Second peak
            'valley_depth_db':      Depth between peaks (must be ≥ 3 dB to pass)
            'separation_hz':        Frequency distance between peaks
            'pass':                 Boolean — whether separation criterion is met
    """
    # Create mask for the breathing frequency band
    band_mask = (freqs >= BREATHING_BAND_LO) & (freqs <= BREATHING_BAND_HI)
    band_freqs = freqs[band_mask]
    band_psd = psd_db[band_mask]

    # Find the strongest peak (global max in breathing band)
    peak1_idx = np.argmax(band_psd)
    peak1_hz = band_freqs[peak1_idx]
    peak1_db = band_psd[peak1_idx]

    # Suppress a region around Peak 1 (±0.05 Hz) and find Peak 2
    suppression_mask = np.abs(band_freqs - peak1_hz) > 0.06
    suppressed_psd = band_psd.copy()
    suppressed_psd[~suppression_mask] = -100  # Suppress near Peak 1

    peak2_idx = np.argmax(suppressed_psd)
    peak2_hz = band_freqs[peak2_idx]
    peak2_db = band_psd[peak2_idx]

    # Compute valley depth: minimum PSD between the two peaks
    if peak1_hz < peak2_hz:
        valley_mask = (band_freqs > peak1_hz) & (band_freqs < peak2_hz)
    else:
        valley_mask = (band_freqs > peak2_hz) & (band_freqs < peak1_hz)

    if np.any(valley_mask):
        valley_min_db = np.min(band_psd[valley_mask])
    else:
        valley_min_db = min(peak1_db, peak2_db)

    # Valley depth = how much the PSD drops between the two peaks
    valley_depth = min(peak1_db, peak2_db) - valley_min_db

    # Separation criterion: ≥ 3 dB valley AND peaks are sufficiently apart
    separation_hz = abs(peak1_hz - peak2_hz)
    passes = (valley_depth >= MIN_VALLEY_DEPTH_DB) and (separation_hz > 0.05)

    return {
        'peak1_hz': peak1_hz,
        'peak1_db': peak1_db,
        'peak2_hz': peak2_hz,
        'peak2_db': peak2_db,
        'valley_depth_db': valley_depth,
        'separation_hz': separation_hz,
        'pass': passes,
    }


# ══════════════════════════════════════════════════════════════════
# Algorithm 3.D — Variance Mapping / Masking Analysis
# ══════════════════════════════════════════════════════════════════

def compute_masking_ratio(
    phase_data: np.ndarray,
    group_a: List[int],
    group_b: List[int],
) -> Dict:
    """
    Compute the motion energy masking ratio between Target A and Target B.

    Masking Ratio = Var(Target_B_group) / Var(Target_A_group)

    If this ratio is < 0.10 (10%), Target B's breathing signature is being
    critically masked by Target A's stronger signal.

    Args:
        phase_data: Shape (n_frames, n_sc) — sanitized phase data.
        group_a:    Subcarrier indices for Target A.
        group_b:    Subcarrier indices for Target B.

    Returns:
        Dict with variance_a, variance_b, masking_ratio, and pass/fail.
    """
    # Compute Welford variance for all subcarriers
    all_variances = compute_welford_variance(phase_data)

    # Mean variance for each target's subcarrier group
    var_a = np.mean(all_variances[group_a]) if len(group_a) > 0 else 0.0
    var_b = np.mean(all_variances[group_b]) if len(group_b) > 0 else 0.0

    # Compute masking ratio
    masking_ratio = var_b / var_a if var_a > 1e-10 else 0.0

    return {
        'variance_a': var_a,
        'variance_b': var_b,
        'masking_ratio': masking_ratio,
        'pass': masking_ratio >= MIN_MASKING_RATIO,
    }


# ══════════════════════════════════════════════════════════════════
# SNR Computation
# ══════════════════════════════════════════════════════════════════

def compute_snr(
    phase_data: np.ndarray,
    target_group: List[int],
    noise_subcarriers: Optional[List[int]] = None,
) -> float:
    """
    Compute Signal-to-Noise Ratio (dB) for a target's subcarrier group.

    SNR = 10 * log10(Var(signal_subcarriers) / Var(noise_subcarriers))

    If no explicit noise subcarriers are provided, uses the lowest-variance
    quartile of all subcarriers as the noise floor estimate.

    Args:
        phase_data:         Shape (n_frames, n_sc) — sanitized phases.
        target_group:       Subcarrier indices for the target of interest.
        noise_subcarriers:  Optional explicit noise subcarrier indices.

    Returns:
        SNR in dB (float).
    """
    all_variances = compute_welford_variance(phase_data)

    # Signal variance: mean variance of target subcarriers
    signal_var = np.mean(all_variances[target_group]) if len(target_group) > 0 else 0.0

    # Noise variance: either explicit noise subcarriers or lowest-variance quartile
    if noise_subcarriers is not None and len(noise_subcarriers) > 0:
        noise_var = np.mean(all_variances[noise_subcarriers])
    else:
        # Estimate noise floor as the 25th percentile of subcarrier variances
        sorted_vars = np.sort(all_variances)
        n_noise = max(1, len(sorted_vars) // 4)
        noise_var = np.mean(sorted_vars[:n_noise])

    # Compute SNR in dB
    if noise_var > 1e-15:
        return 10 * np.log10(signal_var / noise_var)
    else:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# Visualization Engine — Dual-Target Plot Suite
# ══════════════════════════════════════════════════════════════════

def plot_dual_target_analysis(
    freqs: np.ndarray,
    psd_all_db: np.ndarray,
    psd_group_a_db: np.ndarray,
    psd_group_b_db: np.ndarray,
    dual_peaks: Dict,
    masking: Dict,
    snr_a: float,
    snr_b: float,
    variances: np.ndarray,
    group_a: List[int],
    group_b: List[int],
    phase_data: np.ndarray,
    gt_a_bpm: float,
    gt_b_bpm: float,
    output_path: str,
):
    """
    Generate the comprehensive dual-target analysis plot suite.

    Creates a 2×3 grid of subplots showing:
      1. Combined PSD with dual-peak annotations
      2. Per-group PSD (Target A vs Target B isolated)
      3. Variance map across all 52 subcarriers (color-coded by group)
      4. Time-domain phase waveforms for each target
      5. Breathing rate extraction (BPM vs ground truth)
      6. Test result summary table

    Args:
        All analysis results from previous computation steps.
        output_path: Path to save the output PNG.
    """
    # Use a dark, professional figure style
    plt.style.use('dark_background')

    # Create the 2×3 subplot grid
    fig = plt.figure(figsize=(22, 14))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)

    # ── Plot 1: Combined PSD with Dual-Peak Detection ────────────
    ax1 = fig.add_subplot(gs[0, 0])
    # Mask to breathing band for cleaner visualization
    band_mask = (freqs >= 0.05) & (freqs <= 0.6)

    # Plot the combined PSD (all subcarriers averaged)
    ax1.plot(freqs[band_mask], psd_all_db[band_mask],
             color='#00ff88', linewidth=1.5, label='Combined PSD', alpha=0.9)

    # Annotate Peak 1 (Target A)
    ax1.axvline(x=dual_peaks['peak1_hz'], color='#ff6b6b', linestyle='--',
                linewidth=1.0, alpha=0.8)
    ax1.annotate(f"Peak 1: {dual_peaks['peak1_hz']:.3f} Hz\n"
                 f"({dual_peaks['peak1_hz']*60:.0f} BPM)",
                 xy=(dual_peaks['peak1_hz'], dual_peaks['peak1_db']),
                 xytext=(15, 15), textcoords='offset points',
                 fontsize=8, color='#ff6b6b',
                 arrowprops=dict(arrowstyle='->', color='#ff6b6b'))

    # Annotate Peak 2 (Target B)
    ax1.axvline(x=dual_peaks['peak2_hz'], color='#4da6ff', linestyle='--',
                linewidth=1.0, alpha=0.8)
    ax1.annotate(f"Peak 2: {dual_peaks['peak2_hz']:.3f} Hz\n"
                 f"({dual_peaks['peak2_hz']*60:.0f} BPM)",
                 xy=(dual_peaks['peak2_hz'], dual_peaks['peak2_db']),
                 xytext=(15, -25), textcoords='offset points',
                 fontsize=8, color='#4da6ff',
                 arrowprops=dict(arrowstyle='->', color='#4da6ff'))

    # Mark valley depth
    status = "✅ PASS" if dual_peaks['pass'] else "❌ FAIL"
    ax1.set_title(f"Combined PSD — Spectral Separation {status}\n"
                  f"Valley: {dual_peaks['valley_depth_db']:.1f} dB (min {MIN_VALLEY_DEPTH_DB} dB)",
                  fontsize=10, fontweight='bold')
    ax1.set_xlabel('Frequency (Hz)')
    ax1.set_ylabel('Power (dB)')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.2)

    # ── Plot 2: Per-Group Isolated PSD ────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(freqs[band_mask], psd_group_a_db[band_mask],
             color='#ff6b6b', linewidth=1.5, label=f'Target A group ({len(group_a)} SCs)',
             alpha=0.9)
    ax2.plot(freqs[band_mask], psd_group_b_db[band_mask],
             color='#4da6ff', linewidth=1.5, label=f'Target B group ({len(group_b)} SCs)',
             alpha=0.9)

    # Ground truth markers
    ax2.axvline(x=gt_a_bpm / 60, color='#ff6b6b', linestyle=':', alpha=0.5,
                label=f'GT-A: {gt_a_bpm} BPM')
    ax2.axvline(x=gt_b_bpm / 60, color='#4da6ff', linestyle=':', alpha=0.5,
                label=f'GT-B: {gt_b_bpm} BPM')

    ax2.set_title('Per-Group PSD (Spectrally Clustered)', fontsize=10, fontweight='bold')
    ax2.set_xlabel('Frequency (Hz)')
    ax2.set_ylabel('Power (dB)')
    ax2.legend(loc='upper right', fontsize=7)
    ax2.grid(True, alpha=0.2)

    # ── Plot 3: Subcarrier Variance Map ──────────────────────────
    ax3 = fig.add_subplot(gs[0, 2])

    # Color-code bars by group assignment
    colors = ['#555555'] * N_SUBCARRIERS  # Default gray for unassigned
    for sc in group_a:
        colors[sc] = '#ff6b6b'  # Red for Target A group
    for sc in group_b:
        colors[sc] = '#4da6ff'  # Blue for Target B group

    ax3.bar(range(N_SUBCARRIERS), variances, color=colors, width=0.8, alpha=0.85)

    masking_status = "✅ PASS" if masking['pass'] else "❌ FAIL"
    ax3.set_title(f"Welford Variance Map by Subcarrier\n"
                  f"Masking Ratio: {masking['masking_ratio']:.3f} {masking_status}",
                  fontsize=10, fontweight='bold')
    ax3.set_xlabel('Subcarrier Index')
    ax3.set_ylabel('Phase Variance')
    ax3.grid(True, alpha=0.2)

    # Add legend patches
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#ff6b6b', label=f'Target A ({len(group_a)} SCs)'),
        Patch(facecolor='#4da6ff', label=f'Target B ({len(group_b)} SCs)'),
        Patch(facecolor='#555555', label='Unassigned'),
    ]
    ax3.legend(handles=legend_elements, loc='upper right', fontsize=7)

    # ── Plot 4: Time-Domain Phase Waveforms ──────────────────────
    ax4 = fig.add_subplot(gs[1, 0])
    n_frames = phase_data.shape[0]
    time_axis = np.arange(n_frames) / SAMPLE_RATE  # Time in seconds

    # Average phase across each group's subcarriers for visualization
    if len(group_a) > 0:
        avg_phase_a = np.mean(phase_data[:, group_a], axis=1)
        # Remove DC for cleaner visualization
        avg_phase_a -= np.mean(avg_phase_a)
        ax4.plot(time_axis, avg_phase_a, color='#ff6b6b',
                 linewidth=0.8, label='Target A (near)', alpha=0.8)

    if len(group_b) > 0:
        avg_phase_b = np.mean(phase_data[:, group_b], axis=1)
        avg_phase_b -= np.mean(avg_phase_b)
        ax4.plot(time_axis, avg_phase_b, color='#4da6ff',
                 linewidth=0.8, label='Target B (far)', alpha=0.8)

    ax4.set_title('Time-Domain Phase Waveforms (Group Average)',
                  fontsize=10, fontweight='bold')
    ax4.set_xlabel('Time (seconds)')
    ax4.set_ylabel('Phase (radians)')
    ax4.legend(loc='upper right', fontsize=8)
    ax4.grid(True, alpha=0.2)

    # ── Plot 5: BPM Estimation vs Ground Truth ───────────────────
    ax5 = fig.add_subplot(gs[1, 1])

    # Extract estimated BPM from peak frequencies
    est_a_bpm = dual_peaks['peak1_hz'] * 60
    est_b_bpm = dual_peaks['peak2_hz'] * 60

    # Ensure Target A is the one closer to gt_a_bpm
    if abs(est_a_bpm - gt_b_bpm) < abs(est_a_bpm - gt_a_bpm):
        est_a_bpm, est_b_bpm = est_b_bpm, est_a_bpm

    categories = ['Target A\n(Near, 3m)', 'Target B\n(Far, 6m NLOS)']
    gt_values = [gt_a_bpm, gt_b_bpm]
    est_values = [est_a_bpm, est_b_bpm]
    errors = [abs(est_a_bpm - gt_a_bpm), abs(est_b_bpm - gt_b_bpm)]

    x_pos = np.arange(2)
    bar_width = 0.3

    # Ground truth bars
    bars_gt = ax5.bar(x_pos - bar_width/2, gt_values, bar_width,
                      color='#888888', label='Ground Truth', alpha=0.8)
    # Estimated bars
    bars_est = ax5.bar(x_pos + bar_width/2, est_values, bar_width,
                       color='#00ff88', label='Estimated', alpha=0.8)

    # Annotate error
    for i, (gt, est, err) in enumerate(zip(gt_values, est_values, errors)):
        color = '#00ff88' if err <= 3.0 else '#ff6b6b'
        ax5.text(i + bar_width/2, est + 0.5, f'Δ{err:.1f}',
                 ha='center', fontsize=9, color=color, fontweight='bold')

    ax5.set_title('BPM Estimation vs Ground Truth', fontsize=10, fontweight='bold')
    ax5.set_ylabel('Breathing Rate (BPM)')
    ax5.set_xticks(x_pos)
    ax5.set_xticklabels(categories)
    ax5.legend(loc='upper right', fontsize=8)
    ax5.grid(True, alpha=0.2, axis='y')

    # ── Plot 6: Test Result Summary ──────────────────────────────
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')  # No axes for text summary

    # Build results table
    results = [
        ['Metric', 'Value', 'Threshold', 'Result'],
        ['SNR Target A', f'{snr_a:.1f} dB', f'≥ {SNR_THRESHOLD_TARGET_A} dB',
         '✅' if snr_a >= SNR_THRESHOLD_TARGET_A else '❌'],
        ['SNR Target B', f'{snr_b:.1f} dB', f'≥ {SNR_THRESHOLD_TARGET_B} dB',
         '✅' if snr_b >= SNR_THRESHOLD_TARGET_B else '❌'],
        ['BR Error A', f'{errors[0]:.1f} BPM', '≤ 2 BPM',
         '✅' if errors[0] <= 2.0 else '❌'],
        ['BR Error B', f'{errors[1]:.1f} BPM', '≤ 3 BPM',
         '✅' if errors[1] <= 3.0 else '❌'],
        ['Valley Depth', f'{dual_peaks["valley_depth_db"]:.1f} dB', f'≥ {MIN_VALLEY_DEPTH_DB} dB',
         '✅' if dual_peaks['pass'] else '❌'],
        ['Masking Ratio', f'{masking["masking_ratio"]:.3f}', f'≥ {MIN_MASKING_RATIO}',
         '✅' if masking['pass'] else '❌'],
        ['SC Group A', f'{len(group_a)} SCs', '—', '—'],
        ['SC Group B', f'{len(group_b)} SCs', '—', '—'],
    ]

    # Render as matplotlib table
    table = ax6.table(cellText=results[1:], colLabels=results[0],
                      loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.8)

    # Style header row
    for j in range(4):
        table[(0, j)].set_facecolor('#1a1a2e')
        table[(0, j)].set_text_props(fontweight='bold', color='white')

    # Style data rows
    for i in range(1, len(results)):
        for j in range(4):
            table[(i, j)].set_facecolor('#0d0d1a')
            table[(i, j)].set_text_props(color='#cccccc')

    ax6.set_title('VTP-PS-002 Test Results', fontsize=12, fontweight='bold',
                  pad=20)

    # ── Figure Title ─────────────────────────────────────────────
    all_pass = (dual_peaks['pass'] and masking['pass'] and
                snr_a >= SNR_THRESHOLD_TARGET_A and snr_b >= SNR_THRESHOLD_TARGET_B and
                errors[0] <= 2.0 and errors[1] <= 3.0)

    overall = "✅ ALL TESTS PASSED" if all_pass else "⚠️ SOME TESTS FAILED"
    fig.suptitle(f'PHANTOM SCAN — Dual-Target NLOS Validation Report\n{overall}',
                 fontsize=16, fontweight='bold', color='#00ff88' if all_pass else '#ff6b6b')

    # Save high-resolution PNG and close figure
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='#0d0d1a', edgecolor='none')
    plt.close()
    print(f"📊 Plot saved to: {os.path.abspath(output_path)}")


# ══════════════════════════════════════════════════════════════════
# Main Orchestrator
# ══════════════════════════════════════════════════════════════════

def run_analysis(
    csv_path: str,
    gt_a_bpm: float = 15.0,
    gt_b_bpm: float = 24.0,
    output_dir: str = '.',
):
    """
    Execute the full dual-target NLOS validation analysis pipeline.

    Runs all four algorithmic tasks (3.A–3.D) from VTP-PS-002,
    computes metrics, generates plots, and prints a pass/fail report.

    Args:
        csv_path:   Path to the CSV capture file from nlos_capture.py.
        gt_a_bpm:   Ground truth breathing rate for Target A (BPM).
        gt_b_bpm:   Ground truth breathing rate for Target B (BPM).
        output_dir: Directory to save output plots and reports.
    """
    print("=" * 60)
    print("  PHANTOM SCAN — Dual-Target NLOS Validator (VTP-PS-002)")
    print("=" * 60)

    # ── Step 1: Load captured CSI data ───────────────────────────
    print(f"\n[1/6] Loading CSV: {csv_path}")
    data = load_csv_capture(csv_path)
    n_frames = data['phases'].shape[0]
    print(f"       Loaded {n_frames} frames, {data['phases'].shape[1]} subcarriers")
    print(f"       RSSI range: [{np.min(data['rssi']):.0f}, {np.max(data['rssi']):.0f}] dBm")

    # ── Step 2: Phase Sanitization (Algorithm 3.A) ───────────────
    print(f"\n[2/6] Phase Sanitization (SFO/PDD removal)...")
    sanitizer = PhaseSanitizer(n_subcarriers=N_SUBCARRIERS)
    clean_phases = sanitizer.sanitize_batch(data['phases'])
    sfo, pdd = sanitizer.get_sfo_pdd(data['phases'][0])
    print(f"       SFO slope: {sfo:.6f} rad/subcarrier")
    print(f"       PDD offset: {pdd:.4f} rad")

    # ── Step 3: Subcarrier Clustering (Algorithm 3.B) ────────────
    print(f"\n[3/6] Spectral subcarrier clustering...")
    group_a, group_b = spectral_cluster_subcarriers(
        clean_phases,
        target_a_hz=gt_a_bpm / 60.0,
        target_b_hz=gt_b_bpm / 60.0,
    )
    print(f"       Group A (Target A, near): {len(group_a)} subcarriers")
    print(f"       Group B (Target B, far):  {len(group_b)} subcarriers")

    if len(group_a) == 0:
        print("       ⚠️  WARNING: No subcarriers assigned to Group A!")
    if len(group_b) == 0:
        print("       ⚠️  WARNING: No subcarriers assigned to Group B!")
        print("       Consider adjusting biquad filter coefficients (see §5.1).")

    # ── Step 4: PSD and Dual-Peak Detection (Algorithm 3.C) ─────
    print(f"\n[4/6] Computing Power Spectral Density...")

    # Combined PSD (all subcarriers)
    all_sc = list(range(N_SUBCARRIERS))
    freqs, psd_all_db = compute_psd_for_group(clean_phases, all_sc)

    # Per-group PSD
    _, psd_a_db = compute_psd_for_group(clean_phases, group_a if group_a else all_sc)
    _, psd_b_db = compute_psd_for_group(clean_phases, group_b if group_b else all_sc)

    # Dual-peak detection
    dual_peaks = find_dual_peaks(freqs, psd_all_db)
    status = "✅ PASS" if dual_peaks['pass'] else "❌ FAIL"
    print(f"       Peak 1: {dual_peaks['peak1_hz']:.3f} Hz ({dual_peaks['peak1_hz']*60:.0f} BPM) @ {dual_peaks['peak1_db']:.1f} dB")
    print(f"       Peak 2: {dual_peaks['peak2_hz']:.3f} Hz ({dual_peaks['peak2_hz']*60:.0f} BPM) @ {dual_peaks['peak2_db']:.1f} dB")
    print(f"       Valley Depth: {dual_peaks['valley_depth_db']:.1f} dB {status}")

    # ── Step 5: Variance Mapping (Algorithm 3.D) ────────────────
    print(f"\n[5/6] Variance masking analysis...")
    variances = compute_welford_variance(clean_phases)
    masking = compute_masking_ratio(clean_phases, group_a, group_b)
    masking_status = "✅ PASS" if masking['pass'] else "❌ FAIL"
    print(f"       Var(Group A): {masking['variance_a']:.6f}")
    print(f"       Var(Group B): {masking['variance_b']:.6f}")
    print(f"       Masking Ratio: {masking['masking_ratio']:.4f} {masking_status}")

    # SNR computation
    snr_a = compute_snr(clean_phases, group_a)
    snr_b = compute_snr(clean_phases, group_b)
    print(f"       SNR Target A: {snr_a:.1f} dB {'✅' if snr_a >= SNR_THRESHOLD_TARGET_A else '❌'}")
    print(f"       SNR Target B: {snr_b:.1f} dB {'✅' if snr_b >= SNR_THRESHOLD_TARGET_B else '❌'}")

    # ── Step 6: Generate Visualization ──────────────────────────
    print(f"\n[6/6] Generating dual-target analysis plot...")
    plot_path = os.path.join(output_dir, 'dual_target_analysis.png')
    plot_dual_target_analysis(
        freqs=freqs,
        psd_all_db=psd_all_db,
        psd_group_a_db=psd_a_db,
        psd_group_b_db=psd_b_db,
        dual_peaks=dual_peaks,
        masking=masking,
        snr_a=snr_a,
        snr_b=snr_b,
        variances=variances,
        group_a=group_a,
        group_b=group_b,
        phase_data=clean_phases,
        gt_a_bpm=gt_a_bpm,
        gt_b_bpm=gt_b_bpm,
        output_path=plot_path,
    )

    # ── Final Report ─────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print(f"  VTP-PS-002 TEST SUMMARY")
    print(f"{'═' * 60}")

    all_pass = True
    tests = [
        (f"SNR Target A ≥ {SNR_THRESHOLD_TARGET_A} dB", snr_a >= SNR_THRESHOLD_TARGET_A),
        (f"SNR Target B ≥ {SNR_THRESHOLD_TARGET_B} dB", snr_b >= SNR_THRESHOLD_TARGET_B),
        (f"Spectral Separation ≥ {MIN_VALLEY_DEPTH_DB} dB valley", dual_peaks['pass']),
        (f"Masking Ratio ≥ {MIN_MASKING_RATIO}", masking['pass']),
        (f"BR Error A ≤ 2 BPM", abs(dual_peaks['peak1_hz'] * 60 - gt_a_bpm) <= 2.0),
        (f"BR Error B ≤ 3 BPM", abs(dual_peaks['peak2_hz'] * 60 - gt_b_bpm) <= 3.0),
    ]

    for test_name, passed in tests:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {test_name}")
        if not passed:
            all_pass = False

    print(f"\n  {'✅ ALL TESTS PASSED' if all_pass else '⚠️ SOME TESTS FAILED'}")
    print(f"  Report plot: {os.path.abspath(plot_path)}")
    print(f"{'═' * 60}\n")

    return all_pass


# ══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phantom Scan — Dual-Target NLOS Analyzer (VTP-PS-002)"
    )
    # Input CSV file from nlos_capture.py
    parser.add_argument('csv_file', help='Path to the captured CSV file')

    # Ground truth breathing rates for validation
    parser.add_argument('--ground-truth-a', type=float, default=15.0,
                        help='Ground truth BPM for Target A (default: 15)')
    parser.add_argument('--ground-truth-b', type=float, default=24.0,
                        help='Ground truth BPM for Target B (default: 24)')

    # Output directory for plots
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Directory to save output plots')

    args = parser.parse_args()

    passed = run_analysis(
        csv_path=args.csv_file,
        gt_a_bpm=args.ground_truth_a,
        gt_b_bpm=args.ground_truth_b,
        output_dir=args.output_dir,
    )

    sys.exit(0 if passed else 1)
