/**
 * PS-FIX-36 extended: parser for the optional 16-byte PHY trailer that the firmware may append AFTER the I/Q
 * payload of an ADR-018 v1 CSI datagram (firmware/esp32-csi-node/main/csi_phy_trailer_pure.h is the packer and
 * the wire-format reference; design: reports/fix-2026-11/15-PS-FIX-36-extended-design.md).
 *
 * NOT wired into the live ingest (udp-server.ts), the recorder or any route: nothing in the running dashboard imports
 * this file. No firmware sends the trailer yet (nothing is flashed), so today every datagram classifies as "csi_v1".
 *
 * Backward compatibility is a property of the layout for THIS (TypeScript) ingest: the live parseCsiPacket rejects
 * only datagrams SHORTER than 32 + n_antennas * n_subcarriers * 2, and reduceCsiFrame reads only entries inside that
 * range, so it ignores the trailer. The tests prove this against the real parseCsiPacket and reduceCsiFrame.
 * It is NOT true of every reader: the Python parser phantom/protocol.py parse_csi_frame requires an exact length and
 * rejects a trailer frame (measured 2026-11-09), so scripts/ai_inference.py and scripts/record_dataset.py need a
 * change before any firmware sends the trailer.
 *
 * Dispatch order is "longer signature first": a datagram is the trailer shape only when its length is EXACTLY
 * (plain v1 length + 16) AND the last 16 bytes carry the trailer magic and a valid checksum. Anything else that is a
 * well-formed v1 frame stays "csi_v1", so I/Q bytes that happen to look like a trailer are never misread.
 */

export const PHY_TRAILER_MAGIC_LE = 0x31584850; // "PHX1": bytes 50 48 58 31
export const PHY_TRAILER_SIZE = 16;

const ADR018_MAGIC_LE = 0xc5110001;
const ADR018_HEADER_SIZE = 32;
const ADR018_SCHEMA_V1 = 1;

export interface FrameControl {
  /** 802.11 frame type (0 management, 1 control, 2 data, 3 extension). */
  type: number;
  subtype: number;
  toDs: boolean;
  fromDs: boolean;
  retry: boolean;
  protectedFrame: boolean;
}

export interface CsiPhyTrailer {
  /** rx_ctrl.sig_mode: 0 non-HT, 1 HT, 3 VHT. */
  sigMode: number;
  /** rx_ctrl.cwb: 0 = 20 MHz, 1 = 40 MHz. */
  cwb: number;
  aggregation: boolean;
  stbc: number;
  sgi: boolean;
  fecCoding: boolean;
  mcs: number;
  firstWordInvalid: boolean;
  ampduCnt: number;
  /** rx_ctrl.rate (valid for non-HT frames only). */
  rate: number;
  secondaryChannel: number;
  hdrValid: boolean;
  /** null when the firmware could not read the 802.11 header (hdrValid false). */
  frameControl: FrameControl | null;
  /** wifi_csi_info_t.rx_seq (802.11 sequence number of the received packet). */
  rxSeq: number;
  /** Last three bytes of the transmitter MAC, lower-case hex (6 characters). */
  transmitterLow3: string;
}

export type CsiDatagramShape = "csi_v1_phy_trailer" | "csi_v1" | "not_csi_v1";

export interface ClassifiedCsiDatagram {
  shape: CsiDatagramShape;
  /** 32 + n_antennas * n_subcarriers * 2 for a v1 frame, null for "not_csi_v1". */
  plainLength: number | null;
  trailer: CsiPhyTrailer | null;
}

/** XOR of trailer bytes 4..14 (stored in byte 15). */
export function phyTrailerChecksum(trailer: Buffer): number {
  let x = 0;
  for (let i = 4; i <= 14; i++) {
    x ^= trailer[i];
  }
  return x;
}

/** Parse exactly the first 16 bytes of `buf`; null when too short, wrong magic or bad checksum. */
export function parsePhyTrailer(buf: Buffer): CsiPhyTrailer | null {
  if (buf.length < PHY_TRAILER_SIZE) {
    return null;
  }
  if (buf.readUInt32LE(0) !== PHY_TRAILER_MAGIC_LE) {
    return null;
  }
  if (phyTrailerChecksum(buf) !== buf[15]) {
    return null;
  }
  const b4 = buf[4];
  const b5 = buf[5];
  const b7 = buf[7];
  const hdrValid = (b7 & 0x80) !== 0;
  const fc0 = buf[8];
  const fc1 = buf[9];
  return {
    sigMode: b4 & 0x03,
    cwb: (b4 >> 2) & 0x01,
    aggregation: ((b4 >> 3) & 0x01) === 1,
    stbc: (b4 >> 4) & 0x03,
    sgi: ((b4 >> 6) & 0x01) === 1,
    fecCoding: ((b4 >> 7) & 0x01) === 1,
    mcs: b5 & 0x7f,
    firstWordInvalid: (b5 & 0x80) !== 0,
    ampduCnt: buf[6],
    rate: b7 & 0x1f,
    secondaryChannel: (b7 >> 5) & 0x03,
    hdrValid,
    frameControl: hdrValid
      ? {
          type: (fc0 >> 2) & 0x03,
          subtype: (fc0 >> 4) & 0x0f,
          toDs: (fc1 & 0x01) !== 0,
          fromDs: (fc1 & 0x02) !== 0,
          retry: (fc1 & 0x08) !== 0,
          protectedFrame: (fc1 & 0x40) !== 0,
        }
      : null,
    rxSeq: buf.readUInt16LE(10),
    transmitterLow3: buf.subarray(12, 15).toString("hex"),
  };
}

/** Classify a datagram that arrived with the ADR-018 CSI magic. Pure; never throws on short or odd input. */
export function classifyCsiDatagram(msg: Buffer): ClassifiedCsiDatagram {
  const notCsi: ClassifiedCsiDatagram = { shape: "not_csi_v1", plainLength: null, trailer: null };
  if (msg.length < ADR018_HEADER_SIZE) {
    return notCsi;
  }
  if (msg.readUInt32LE(0) !== ADR018_MAGIC_LE || msg.readUInt8(4) !== ADR018_SCHEMA_V1) {
    return notCsi;
  }
  const numAntennas = msg.readUInt8(6);
  const numSubcarriers = msg.readUInt16LE(7);
  if (numAntennas <= 0 || numSubcarriers <= 0) {
    return notCsi;
  }
  const plainLength = ADR018_HEADER_SIZE + numAntennas * numSubcarriers * 2;

  // Longer signature first: exact length plus magic plus checksum.
  if (msg.length === plainLength + PHY_TRAILER_SIZE) {
    const trailer = parsePhyTrailer(msg.subarray(plainLength));
    if (trailer) {
      return { shape: "csi_v1_phy_trailer", plainLength, trailer };
    }
  }
  if (msg.length >= plainLength) {
    return { shape: "csi_v1", plainLength, trailer: null };
  }
  return notCsi;
}

/** The datagram without its trailer when it has a valid one; otherwise the same buffer, unchanged. */
export function stripPhyTrailer(msg: Buffer): Buffer {
  const c = classifyCsiDatagram(msg);
  return c.shape === "csi_v1_phy_trailer" && c.plainLength !== null ? msg.subarray(0, c.plainLength) : msg;
}
