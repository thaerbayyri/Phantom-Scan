import test from "node:test";
import assert from "node:assert/strict";
import { LLTF_DATA_INDICES, LLTF_LENGTH, reduceCsiFrame } from "./csi-subcarriers";

/** Build an ESP-IDF CSI buffer: per entry [imag, real] int8 (imaginary FIRST). */
function iqBuffer(entries: Array<{ re: number; im: number }>): Buffer {
  const buf = Buffer.alloc(entries.length * 2);
  entries.forEach((e, i) => {
    buf.writeInt8(e.im, i * 2);
    buf.writeInt8(e.re, i * 2 + 1);
  });
  return buf;
}

function lltfWithMarkers(): Array<{ re: number; im: number }> {
  // Data subcarriers carry amplitude 10 (re=6, im=8); everything else 0 so
  // any null/guard leakage is visible as a zero in the output.
  return Array.from({ length: LLTF_LENGTH }, (_, i) =>
    LLTF_DATA_INDICES.includes(i) ? { re: 6, im: 8 } : { re: 0, im: 0 },
  );
}

test("LLTF data index set excludes DC, the invalid first word, and the ±27..±32 guards", () => {
  assert.equal(LLTF_DATA_INDICES.length, 51);
  for (const excluded of [0, 1, 27, 31, 32, 37]) {
    assert.ok(!LLTF_DATA_INDICES.includes(excluded), `index ${excluded} must be excluded`);
  }
  for (const included of [2, 26, 38, 63]) {
    assert.ok(LLTF_DATA_INDICES.includes(included), `index ${included} must be included`);
  }
});

test("reduceCsiFrame returns only data-subcarrier amplitudes from the LLTF block", () => {
  const frame = reduceCsiFrame(iqBuffer(lltfWithMarkers()), LLTF_LENGTH, 1);
  assert.equal(frame.amplitudes.length, 51);
  for (const a of frame.amplitudes) assert.equal(a, 10);
});

test("reduceCsiFrame keeps the subcarrier count constant across non-HT, HT and STBC frames", () => {
  const lltf = lltfWithMarkers();
  const htLtf = Array.from({ length: LLTF_LENGTH }, () => ({ re: 30, im: 40 }));
  for (const blocks of [[lltf], [lltf, htLtf], [lltf, htLtf, htLtf]]) {
    const entries = blocks.flat();
    const frame = reduceCsiFrame(iqBuffer(entries), entries.length, 1);
    assert.equal(frame.amplitudes.length, 51, `nSub=${entries.length}`);
    // HT-LTF (amplitude 50) must never leak into the LLTF-only vector.
    assert.ok(frame.amplitudes.every((a) => a === 10));
  }
});

test("reduceCsiFrame reads ESP-IDF imaginary-first byte order for the dominant subcarrier", () => {
  const entries = lltfWithMarkers();
  entries[10] = { re: 20, im: -50 }; // strongest data subcarrier
  const frame = reduceCsiFrame(iqBuffer(entries), LLTF_LENGTH, 1);
  assert.deepEqual(frame.h1, { re: 20, im: -50 });
  assert.deepEqual(frame.h2, frame.h1, "single-antenna boards duplicate h1 into h2");
});

test("reduceCsiFrame falls back to every entry for short legacy/synthetic frames", () => {
  const entries = [{ re: 3, im: 4 }, { re: 0, im: 5 }, { re: 6, im: 8 }];
  const frame = reduceCsiFrame(iqBuffer(entries), entries.length, 1);
  assert.deepEqual(frame.amplitudes, [5, 5, 10]);
  assert.deepEqual(frame.h1, { re: 6, im: 8 });
});

test("reduceCsiFrame uses the second antenna block for h2 when present", () => {
  const ant0 = lltfWithMarkers();
  const ant1 = lltfWithMarkers().map((e, i) => (i === 10 ? { re: 1, im: 2 } : e));
  ant0[10] = { re: 40, im: 40 };
  const frame = reduceCsiFrame(iqBuffer([...ant0, ...ant1]), LLTF_LENGTH, 2);
  assert.deepEqual(frame.h1, { re: 40, im: 40 });
  assert.deepEqual(frame.h2, { re: 1, im: 2 });
});
