// ── CSI subcarrier extraction (ESP-IDF wifi_csi_info_t buffer) ─────
//
// ESP-IDF stores each subcarrier's channel response as two signed bytes,
// IMAGINARY first, then real ("The first one is imaginary part and the
// second one is real part" — ESP-IDF Wi-Fi Vendor Features, CSI section).
// Buffers are a concatenation of up to three 64-entry LTF blocks in the
// order LLTF, HT-LTF, STBC-HT-LTF (not all are present). Every frame type
// carries the LLTF block first, so using only that block keeps the
// per-packet vector length constant across non-HT / HT / STBC frames —
// mixing lengths made computeNodeMotionFromMatrix truncate to the shortest
// frame and compare different LTFs across the window.
//
// LLTF index order is subcarrier 0..31 then -32..-1. Data subcarriers are
// ±1..±26; index 0 (DC) and ±27..±32 (indices 27..37) are nulls/guards
// that carry no channel information and only diluted the motion metric.
// Index 1 is also excluded: on ESP32-S3 the first four bytes (entries 0-1)
// are invalid whenever first_word_invalid is set, and the firmware does not
// forward that flag.

export const LLTF_LENGTH = 64;
const LAST_POSITIVE_DATA_INDEX = 26; // subcarrier +26
const FIRST_NEGATIVE_DATA_INDEX = 38; // subcarrier -26
const FIRST_VALID_INDEX = 2; // skip DC (0) and the possibly-invalid first word (1)

export const LLTF_DATA_INDICES: readonly number[] = Object.freeze([
  ...Array.from({ length: LAST_POSITIVE_DATA_INDEX - FIRST_VALID_INDEX + 1 }, (_, i) => FIRST_VALID_INDEX + i),
  ...Array.from({ length: LLTF_LENGTH - FIRST_NEGATIVE_DATA_INDEX }, (_, i) => FIRST_NEGATIVE_DATA_INDEX + i),
]);

export interface ComplexSample {
  re: number;
  im: number;
}

export interface ReducedCsiFrame {
  /** Antenna-0 amplitude per data subcarrier (51 for a full LLTF block). */
  amplitudes: number[];
  /** Dominant (max-power) data subcarrier, antenna 0. */
  h1: ComplexSample;
  /** Same subcarrier on antenna 1, or a copy of h1 on single-antenna boards. */
  h2: ComplexSample;
}

function readEntry(iq: Buffer, entryIndex: number): ComplexSample {
  const offset = entryIndex * 2;
  return { im: iq.readInt8(offset), re: iq.readInt8(offset + 1) };
}

/**
 * Reduce one CSI packet's I/Q payload to the per-subcarrier amplitude
 * vector used by fusion plus the scalar dominant-subcarrier h1/h2 used by
 * the legacy DSP chain. Frames shorter than one LLTF block (legacy or
 * synthetic senders) fall back to using every entry.
 */
export function reduceCsiFrame(iq: Buffer, numSubcarriers: number, numAntennas: number): ReducedCsiFrame {
  const hasLltf = numSubcarriers >= LLTF_LENGTH;
  const indices = hasLltf
    ? LLTF_DATA_INDICES
    : Array.from({ length: Math.max(0, numSubcarriers) }, (_, i) => i);
  const secondAntenna = numAntennas > 1;

  const amplitudes: number[] = new Array(indices.length);
  let bestPower = -1;
  let h1: ComplexSample = { re: 0, im: 0 };
  let h2: ComplexSample = { re: 0, im: 0 };
  indices.forEach((sc, k) => {
    const a0 = readEntry(iq, sc);
    const power0 = a0.re * a0.re + a0.im * a0.im;
    amplitudes[k] = Math.sqrt(power0);
    const a1 = secondAntenna ? readEntry(iq, numSubcarriers + sc) : a0;
    const power = power0 + (secondAntenna ? a1.re * a1.re + a1.im * a1.im : 0);
    if (power > bestPower) {
      bestPower = power;
      h1 = a0;
      h2 = a1;
    }
  });
  return { amplitudes, h1: { ...h1 }, h2: { ...h2 } };
}
