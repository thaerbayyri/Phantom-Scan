import dgram from "dgram";
import { signalServer } from "./websocket";
import type { CSISample } from "@shared/schema";
import { mapRuntimeNodeIdToHardwareId } from "@shared/schema";

const UDP_PORT = parseInt(process.env.UDP_PORT || "5005", 10);
const UDP_HOST = "0.0.0.0";

const MAGIC_NUMBER_LE = 0xc5110001;
const HEARTBEAT_MAGIC_LE = 0xc51100a1;
/** Phantom Scan firmware rv_feature_state packet (1 Hz per node, board-side DSP). */
const FEATURE_STATE_MAGIC_LE = 0xc5110006;
const FEATURE_STATE_MIN_SIZE = 56;
/** This repo's own firmware vitals packet (edge_vitals_pkt_t, 32 bytes). */
const EDGE_VITALS_MAGIC_LE = 0xc5110002;
const EDGE_VITALS_SIZE = 32;
/** Firmware XOR+RLE compressed CSI (edge tier >= 2). Not decoded here: the
 *  raw 0xC5110001 stream already feeds the pipeline, so these are counted
 *  and skipped instead of warned about. */
const EDGE_COMPRESSED_MAGIC_LE = 0xc5110003;
/** Full rv_feature_state size incl. trailing CRC32 (bytes 56..59). */
const FEATURE_STATE_FULL_SIZE = 60;
const LEGACY_HEADER_SIZE = 20;
const ADR018_HEADER_SIZE = 32;

type ParsedCsiPacket = {
    schemaVersion?: number;
    nodeId: number;
    seq?: number;
    freqMhz?: number;
    noiseDbm?: number;
    channel?: number;
    deviceTsUs?: bigint;
    deviceTsMs?: number;
    rssi: number;
    numAntennas: number;
    numSubcarriers: number;
    iqData: Buffer;
};

type ParseCsiPacketOptions = {
    allowLegacy?: boolean;
};

type StaticSourcePins = Map<number, string>;

type SequenceMetadata = {
    seq?: number;
    deviceTsUs?: bigint;
    deviceTsMs?: number;
};

function parseStaticSourcePins(envValue: string | undefined): StaticSourcePins {
    if (!envValue) {
        return new Map();
    }

    try {
        const parsed = JSON.parse(envValue) as Record<string, unknown>;
        const pins = new Map<number, string>();
        for (const [nodeIdRaw, sourceIp] of Object.entries(parsed)) {
            const nodeId = Number.parseInt(nodeIdRaw, 10);
            if (!Number.isFinite(nodeId) || typeof sourceIp !== "string" || !sourceIp) {
                continue;
            }
            pins.set(nodeId, sourceIp);
        }
        return pins;
    } catch (error) {
        console.warn(
            `[UDP] Failed to parse PHANTOM_STATIC_NODE_SOURCES; expected JSON like ` +
                `{"1":"10.0.0.11","2":"10.0.0.12"}. Ignoring static pins. Error: ${String(error)}`,
        );
        return new Map();
    }
}

/**
 * Anti-spoof guard for the detection input: pins each node_id to the first
 * source IP that used it, so a rogue/duplicate sender cannot inject fake CSI
 * (and thus fake presence/motion) under an already-claimed node identity.
 * Allows legitimate rebinds after 10 s of silence (device reboot + new DHCP IP).
 */
export class SourcePinningGuard {
    /** A pinned source goes stale after this much silence; a new IP may then
     *  claim the node (device reboot + DHCP renumber), which is NOT a spoof. */
    static readonly STALE_BINDING_MS = 10_000;
    /** At most one [UDP][SEC] console line per node per this interval. */
    static readonly WARN_INTERVAL_MS = 5_000;
    /** Bounded security-event history. */
    static readonly MAX_EVENTS = 200;

    private readonly staticPins: StaticSourcePins;

    private bindings = new Map<
        number,
        { address: string; port: number; lastAcceptedMs: number }
    >();
    private rejectionCount = 0;
    private lastWarnMs = new Map<number, number>();
    private securityEvents: Array<{
        record_type: "security_event";
        event_type: "node_source_mismatch";
        node_id: number;
        expected_source: { ip: string; port: number };
        actual_source: { ip: string; port: number };
        packet_kind: "csi_frame" | "feature_state";
    }> = [];

    constructor(staticPins: StaticSourcePins = new Map()) {
        this.staticPins = staticPins;
    }

    check(
        nodeId: number,
        source: { address: string; port: number },
        nowMs: number = Date.now(),
        packetKind: "csi_frame" | "feature_state" = "csi_frame",
    ): boolean {
        const staticallyPinnedIp = this.staticPins.get(nodeId);
        if (staticallyPinnedIp && staticallyPinnedIp !== source.address) {
            return this.reject(nodeId, source, packetKind, {
                ip: staticallyPinnedIp,
                port: this.bindings.get(nodeId)?.port ?? 0,
            }, nowMs);
        }

        const existing = this.bindings.get(nodeId);
        if (!existing) {
            this.bindings.set(nodeId, {
                address: source.address,
                port: source.port,
                lastAcceptedMs: nowMs,
            });
            return true;
        }

        if (existing.address === source.address) {
            // Same device, possibly a new ephemeral UDP port after reboot.
            if (existing.port !== source.port) {
                existing.port = source.port;
            }
            existing.lastAcceptedMs = nowMs;
            return true;
        }

        // Different IP. If the pinned source has been silent past the stale
        // window, this is a legitimate reconnect (DHCP renumber) — rebind.
        // A conflicting IP while the pinned source is still actively sending
        // is the real spoof signal and stays rejected.
        if (
            !staticallyPinnedIp &&
            nowMs - existing.lastAcceptedMs > SourcePinningGuard.STALE_BINDING_MS
        ) {
            console.log(
                `[UDP] node ${nodeId} source rebound after silence: ` +
                    `${existing.address}:${existing.port} -> ${source.address}:${source.port}`,
            );
            existing.address = source.address;
            existing.port = source.port;
            existing.lastAcceptedMs = nowMs;
            return true;
        }

        return this.reject(
            nodeId,
            source,
            packetKind,
            { ip: existing.address, port: existing.port },
            nowMs,
        );
    }

    private reject(
        nodeId: number,
        source: { address: string; port: number },
        packetKind: "csi_frame" | "feature_state",
        expectedSource: { ip: string; port: number },
        nowMs: number,
    ): boolean {
        this.rejectionCount++;
        const event = {
            record_type: "security_event" as const,
            event_type: "node_source_mismatch" as const,
            node_id: nodeId,
            expected_source: expectedSource,
            actual_source: { ip: source.address, port: source.port },
            packet_kind: packetKind,
        };
        this.securityEvents.push(event);
        if (this.securityEvents.length > SourcePinningGuard.MAX_EVENTS) {
            this.securityEvents.splice(
                0,
                this.securityEvents.length - SourcePinningGuard.MAX_EVENTS,
            );
        }
        const lastWarn = this.lastWarnMs.get(nodeId) ?? 0;
        if (nowMs - lastWarn >= SourcePinningGuard.WARN_INTERVAL_MS) {
            this.lastWarnMs.set(nodeId, nowMs);
            console.warn(
                `[UDP][SEC] ${JSON.stringify(event)} (rejections for node ${nodeId}: rate-limited log). ` +
                    `If BOTH boards keep sending, they were likely provisioned with the same node_id — ` +
                    `re-provision one with a unique id (firmware/esp32-csi-node/esp-flash.py).`,
            );
        }
        return false;
    }

    getBindings(): Record<string, { address: string; port: number }> {
        return Object.fromEntries(
            Array.from(this.bindings.entries()).map(([nodeId, source]) => [
                String(nodeId),
                { address: source.address, port: source.port },
            ])
        );
    }

    getRejectionCount(): number {
        return this.rejectionCount;
    }

    getSecurityEvents(): Array<{
        record_type: "security_event";
        event_type: "node_source_mismatch";
        node_id: number;
        expected_source: { ip: string; port: number };
        actual_source: { ip: string; port: number };
        packet_kind: "csi_frame" | "feature_state";
    }> {
        return [...this.securityEvents];
    }
}

export class PacketOrderGuard {
    private states = new Map<
        number,
        {
            lastSeq?: number;
            lastDeviceTsUs?: bigint;
            lastDeviceTsMs?: number;
            gapCount: number;
            replayCount: number;
            outOfOrderCount: number;
        }
    >();

    check(nodeId: number, meta: SequenceMetadata): boolean {
        if (meta.seq === undefined) {
            return true;
        }

        const current = this.states.get(nodeId);
        if (!current) {
            this.states.set(nodeId, {
                lastSeq: meta.seq,
                lastDeviceTsUs: meta.deviceTsUs,
                lastDeviceTsMs: meta.deviceTsMs,
                gapCount: 0,
                replayCount: 0,
                outOfOrderCount: 0,
            });
            return true;
        }

        const delta = (meta.seq - (current.lastSeq ?? 0)) >>> 0;
        if (delta === 0) {
            current.replayCount++;
            return false;
        }
        if (delta >= 0x80000000) {
            current.outOfOrderCount++;
            return false;
        }

        if (
            meta.deviceTsUs !== undefined &&
            current.lastDeviceTsUs !== undefined &&
            meta.deviceTsUs <= current.lastDeviceTsUs
        ) {
            current.replayCount++;
            return false;
        }
        if (
            meta.deviceTsUs === undefined &&
            meta.deviceTsMs !== undefined &&
            current.lastDeviceTsMs !== undefined &&
            meta.deviceTsMs <= current.lastDeviceTsMs
        ) {
            current.replayCount++;
            return false;
        }

        if (delta > 1) {
            current.gapCount += delta - 1;
        }
        current.lastSeq = meta.seq;
        if (meta.deviceTsUs !== undefined) {
            current.lastDeviceTsUs = meta.deviceTsUs;
        }
        if (meta.deviceTsMs !== undefined) {
            current.lastDeviceTsMs = meta.deviceTsMs;
        }
        return true;
    }
}

export type ParsedFeatureState = {
    nodeId: number;
    motion: number;
    presence: number;
    respBpm: number;
    respConf: number;
    hrBpm: number;
    hrConf: number;
    /** Board-reported RSSI (dBm). Only the 0xC5110002 vitals packet carries
     *  it; rv_feature_state packets leave it undefined. */
    rssi?: number;
};

export type PacketKind =
    | "csi"
    | "heartbeat"
    | "vitals"
    | "feature_state"
    | "compressed"
    | "unknown";

/** Classify a datagram by its leading magic (LE u32). Pure helper so the
 *  dispatch in startUDPServer is unit-testable. */
export function classifyPacketMagic(msg: Buffer): PacketKind {
    if (msg.length < 4) {
        return "unknown";
    }
    switch (msg.readUInt32LE(0)) {
        case MAGIC_NUMBER_LE:
            return "csi";
        case HEARTBEAT_MAGIC_LE:
            return "heartbeat";
        case EDGE_VITALS_MAGIC_LE:
            return "vitals";
        case FEATURE_STATE_MAGIC_LE:
            return "feature_state";
        case EDGE_COMPRESSED_MAGIC_LE:
            return "compressed";
        default:
            return "unknown";
    }
}

/** IEEE 802.3 CRC32 (poly 0xEDB88320, init/final-xor 0xFFFFFFFF) — matches
 *  the firmware's rv_feature_state_finalize bit-by-bit implementation. */
export function crc32IEEE(buf: Buffer, length: number): number {
    let crc = 0xffffffff;
    for (let i = 0; i < length; i++) {
        crc ^= buf[i];
        for (let bit = 0; bit < 8; bit++) {
            crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
}

/**
 * Parse the Phantom Scan rv_feature_state packet (magic 0xC5110006, ≥56 bytes LE).
 * Field offsets match the archived scripts/ruview-dashboard-bridge.py parse_feat()
 * for continuity: node_id u8 @4; f32 motion @16, presence @20, resp_bpm @24,
 * resp_conf @28, hr_bpm @32, hr_conf @36.
 */
export function parseFeatureStatePacket(msg: Buffer): ParsedFeatureState | null {
    if (msg.length < FEATURE_STATE_MIN_SIZE) {
        return null;
    }
    if (msg.readUInt32LE(0) !== FEATURE_STATE_MAGIC_LE) {
        return null;
    }
    // Full 60-byte packets carry a trailing CRC32 over bytes 0..55; reject on
    // mismatch (corrupted datagram). 56-59 byte packets predate the CRC and
    // stay accepted for backward compatibility.
    if (msg.length >= FEATURE_STATE_FULL_SIZE) {
        const expected = msg.readUInt32LE(FEATURE_STATE_FULL_SIZE - 4);
        if (crc32IEEE(msg, FEATURE_STATE_FULL_SIZE - 4) !== expected) {
            return null;
        }
    }
    return {
        nodeId: msg.readUInt8(4),
        motion: msg.readFloatLE(16),
        presence: msg.readFloatLE(20),
        respBpm: msg.readFloatLE(24),
        respConf: msg.readFloatLE(28),
        hrBpm: msg.readFloatLE(32),
        hrConf: msg.readFloatLE(36),
    };
}

/**
 * Parse this repo's own firmware vitals packet (magic 0xC5110002, 32 bytes LE;
 * edge_vitals_pkt_t in firmware/esp32-csi-node/main/edge_processing.h):
 * node_id u8 @4; flags u8 @5 (bit0 presence, bit1 fall, bit2 motion);
 * breathing u16 @6 (BPM*100); heart u32 @8 (BPM*10000); rssi i8 @12;
 * motion_energy f32 @16; presence_score f32 @20; timestamp_ms u32 @24.
 * Mapped onto the same ParsedFeatureState the 0xC5110006 feature-state packet
 * produces, so either firmware populates the dashboard's Board DSP card.
 */
export function parseEdgeVitalsPacket(msg: Buffer): ParsedFeatureState | null {
    if (msg.length < EDGE_VITALS_SIZE) {
        return null;
    }
    if (msg.readUInt32LE(0) !== EDGE_VITALS_MAGIC_LE) {
        return null;
    }
    const respBpm = msg.readUInt16LE(6) / 100;
    const hrBpm = msg.readUInt32LE(8) / 10000;
    return {
        nodeId: msg.readUInt8(4),
        motion: msg.readFloatLE(16),
        presence: msg.readFloatLE(20),
        rssi: msg.readInt8(12),
        respBpm,
        // edge_vitals_pkt_t carries no confidence fields: report full
        // confidence for a non-zero (sanity-clamped on the board) estimate.
        respConf: respBpm > 0 ? 1 : 0,
        hrBpm,
        hrConf: hrBpm > 0 ? 1 : 0,
    };
}

/**
 * Parse a raw CSI frame (magic 0xC5110001) into header fields + IQ payload.
 * Live ingest accepts only the ADR-018 32-byte header (schema v1:
 * seq/freq/noise/channel/device timestamps). The superseded legacy 20-byte
 * header is available only to explicit offline compatibility tooling via
 * `allowLegacy` / `PHANTOM_ALLOW_LEGACY_CSI`. Heartbeats (0xC51100A1) and
 * malformed/short packets return null and are ignored.
 */
export function parseCsiPacket(
    msg: Buffer,
    options: ParseCsiPacketOptions = {},
): ParsedCsiPacket | null {
    if (msg.length < 4) {
        return null;
    }

    const magic = msg.readUInt32LE(0);
    if (magic === HEARTBEAT_MAGIC_LE) {
        return null;
    }
    if (magic !== MAGIC_NUMBER_LE) {
        return null;
    }

    // Preferred path: ADR-018 32-byte header, schema version 1.
    if (msg.length >= ADR018_HEADER_SIZE) {
        const schemaVersion = msg.readUInt8(4);
        if (schemaVersion === 1) {
            const nodeId = msg.readUInt8(5);
            const numAntennas = msg.readUInt8(6);
            const numSubcarriers = msg.readUInt16LE(7);
            const freqMhz = msg.readUInt32LE(9);
            const seq = msg.readUInt32LE(13);
            const rssi = msg.readInt8(17);
            const noiseDbm = msg.readInt8(18);
            const channel = msg.readUInt8(19);
            const deviceTsUs = msg.readBigUInt64LE(20);
            const deviceTsMs = msg.readUInt32LE(28);
            const iqData = msg.subarray(ADR018_HEADER_SIZE);
            const expectedIqBytes = numAntennas * numSubcarriers * 2;

            if (numAntennas <= 0 || numSubcarriers <= 0) {
                return null;
            }
            if (iqData.length < expectedIqBytes) {
                return null;
            }

            return {
                schemaVersion,
                nodeId,
                seq,
                freqMhz,
                noiseDbm,
                channel,
                deviceTsUs,
                deviceTsMs,
                rssi,
                numAntennas,
                numSubcarriers,
                iqData,
            };
        }
    }

    if (!options.allowLegacy) {
        return null;
    }

    // Compatibility-only fallback: 20-byte header (older firmware without
    // ADR-018 fields). Never enabled on the live authority path.
    if (msg.length < LEGACY_HEADER_SIZE) {
        return null;
    }

    const nodeId = msg.readUInt8(4);
    const numAntennas = msg.readUInt8(5);
    const numSubcarriers = msg.readUInt16LE(6);
    const rssi = msg.readInt8(16);
    const iqData = msg.subarray(LEGACY_HEADER_SIZE);
    const expectedIqBytes = numAntennas * numSubcarriers * 2;

    if (numAntennas <= 0 || numSubcarriers <= 0) {
        return null;
    }
    if (iqData.length < expectedIqBytes) {
        return null;
    }

    return {
        nodeId,
        rssi,
        numAntennas,
        numSubcarriers,
        iqData,
    };
}

/**
 * Sole ESP32 ingest for the live pipeline. Binds UDP :5005, validates each
 * datagram (magic + source pinning), extracts the per-subcarrier amplitude
 * vector and the max-power subcarrier as scalar h1/h2, then hands the
 * CSISample to signalServer.ingestSample — the start of every presence/
 * movement decision. Accepted raw packets are also mirrored to the Python
 * AI sidecar on :5006 (advisory classification only).
 */
export function startUDPServer() {
    // Singleton ingest: do NOT set reuseAddr. On Windows SO_REUSEADDR lets a
    // stale/second listener silently share :5005 with non-deterministic delivery,
    // which would steal ESP32 frames. We want a hard EADDRINUSE instead so the
    // operator sees the clash (handled below) rather than losing packets quietly.
    const server = dgram.createSocket("udp4");
    const pyForwardSocket = dgram.createSocket("udp4");
    const sourceGuard = new SourcePinningGuard(
        parseStaticSourcePins(process.env.PHANTOM_STATIC_NODE_SOURCES),
    );
    const packetOrderGuard = new PacketOrderGuard();

    server.on("error", (err: NodeJS.ErrnoException) => {
        if (err.code === "EADDRINUSE") {
            console.error(
                `[UDP] Cannot bind UDP :${UDP_PORT} — the port is already in use. ` +
                `Another ESP32 ingest (e.g. a Python 'phantom.runtime live' authority) is likely ` +
                `holding it. Stop that process, or run the dashboard alone so it owns :${UDP_PORT}.`,
            );
        } else {
            console.error(`[UDP] Server error:\n${err.stack}`);
        }
        server.close();
        pyForwardSocket.close();
    });

    let packetCount = 0;
    let compressedFrameCount = 0;
    let lastLogTime = Date.now();
    let lastUnknownMagicLogMs = 0;

    server.on("message", (msg, rinfo) => {
        const kind = classifyPacketMagic(msg);

        // Firmware DSP feature-state (0xC5110006): independent 1 Hz
        // stream shown alongside host-DSP metrics — never fused with them.
        if (kind === "feature_state") {
            const feat = parseFeatureStatePacket(msg);
            if (feat && sourceGuard.check(feat.nodeId, rinfo, Date.now(), "feature_state")) {
                signalServer.ingestNodeFeatureState(feat);
            }
            return;
        }

        // This repo's own firmware vitals (0xC5110002): same role as the
        // 0xC5110006 feature-state packet — board-side presence/motion/vitals for the
        // Board DSP card, never fused with the host target math.
        if (kind === "vitals") {
            const feat = parseEdgeVitalsPacket(msg);
            if (feat && sourceGuard.check(feat.nodeId, rinfo, Date.now(), "feature_state")) {
                signalServer.ingestNodeFeatureState(feat);
            }
            return;
        }

        // Compressed CSI (0xC5110003, edge tier >= 2): expected traffic, not
        // decoded — the raw stream carries the same frames. Count for the
        // periodic stats line instead of warning.
        if (kind === "compressed") {
            compressedFrameCount++;
            return;
        }

        // Diagnosability: surface unexpected packet types (≤1 log / 10 s) so
        // "Board DSP card empty" is distinguishable between silent boards and
        // firmware speaking an unknown protocol.
        if (kind === "unknown") {
            const magic = msg.length >= 4 ? msg.readUInt32LE(0) : 0;
            const nowMs = Date.now();
            if (nowMs - lastUnknownMagicLogMs > 10_000) {
                lastUnknownMagicLogMs = nowMs;
                console.warn(
                    `[UDP] unknown packet magic 0x${magic.toString(16)} (${msg.length} B) from ` +
                        `${rinfo.address}:${rinfo.port} — not CSI/heartbeat/vitals/feature-state/compressed`,
                );
            }
            return;
        }

        const parsed = parseCsiPacket(msg);
        if (!parsed) {
            return;
        }
        const hardwareId = mapRuntimeNodeIdToHardwareId(parsed.nodeId);
        if (hardwareId === undefined) {
            console.warn(`[UDP] rejecting CSI packet for unmapped runtime node_id=${parsed.nodeId} (PS-AUDIT-005)`);
            return;
        }
        if (!sourceGuard.check(parsed.nodeId, rinfo)) {
            return;
        }
        if (
            !packetOrderGuard.check(parsed.nodeId, {
                seq: parsed.seq,
                deviceTsUs: parsed.deviceTsUs,
                deviceTsMs: parsed.deviceTsMs,
            })
        ) {
            return;
        }

        // Forward only accepted raw packets to the local Python AI sidecar.
        pyForwardSocket.send(msg, 5006, "127.0.0.1", () => {
            // Ignore errors if the Python script is not running yet.
        });

        // For Phantom Scan, we expect an array of subcarriers.
        // We'll average across the subcarriers for a single representative complex number per antenna for the core math,
        // or just pass the first subcarrier (or an average) as the scalar `h1` and `h2` expected by `CSISample`.
        // Actually, `CSISample` expects `h1` and `h2` as single complex numbers {re, im}. 
        // Usually CSI is an array, but the existing signal pipeline processes them as scalar complex numbers (representing the dominant path).
        // Let's take the subcarrier with the maximum power to represent the sample.

        let maxSubcarrierPower = -1;
        let bestH1 = { re: 0, im: 0 };
        let bestH2 = { re: 0, im: 0 };

        // Per-subcarrier amplitudes (antenna 0), capped at 64. Phantom Balance
        // Fusion needs the full vector: the best-subcarrier scalar below jumps
        // index frame-to-frame, so its temporal std is selection noise, not
        // human motion.
        const ampCount = Math.min(parsed.numSubcarriers, 64);
        const amplitudes = new Array<number>(ampCount);

        for (let i = 0; i < parsed.numSubcarriers; i++) {
            // Antenna 1
            const p1_re = parsed.iqData.readInt8((0 * parsed.numSubcarriers + i) * 2);
            const p1_im = parsed.iqData.readInt8((0 * parsed.numSubcarriers + i) * 2 + 1);

            const power1 = p1_re * p1_re + p1_im * p1_im;
            if (i < ampCount) {
                amplitudes[i] = Math.sqrt(power1);
            }

            let power2 = 0;
            let p2_re = 0;
            let p2_im = 0;

            // Defensive parse only: this hardware has exactly 1 antenna per node and
            // never sends a second; this branch is unreachable in practice, kept only
            // so a malformed/corrupt packet with numAntennas>1 doesn't crash the parser.
            if (parsed.numAntennas > 1) {
                p2_re = parsed.iqData.readInt8((1 * parsed.numSubcarriers + i) * 2);
                p2_im = parsed.iqData.readInt8((1 * parsed.numSubcarriers + i) * 2 + 1);
                power2 = p2_re * p2_re + p2_im * p2_im;
            }

            const totalPower = power1 + power2;

            if (totalPower > maxSubcarrierPower) {
                maxSubcarrierPower = totalPower;
                bestH1 = { re: p1_re, im: p1_im };
                if (parsed.numAntennas > 1) {
                    bestH2 = { re: p2_re, im: p2_im };
                } else {
                    // Fallback: If only 1 antenna is provided, duplicate it to H2 
                    // to prevent downstream math crashes (e.g. magnitude(h2)).
                    // Note: MUSIC/Vitals phase math will essentially result in 0 phase difference.
                    bestH2 = { re: p1_re, im: p1_im };
                }
            }
        }

        // One CSISample per packet: scalar h1/h2 (dominant subcarrier) feed the
        // legacy DSP chain; `amplitudes` (full vector) feeds two-node fusion.
        const sample: CSISample = {
            timestamp: Date.now(),
            h1: bestH1,
            h2: bestH2,
            rssi: parsed.rssi,
            nodeId: parsed.nodeId,
            hardwareId,
            amplitudes,
        };

        signalServer.ingestSample(sample);

        packetCount++;
        const now = Date.now();
        if (now - lastLogTime > 5000) {
            const compressedNote =
                compressedFrameCount > 0 ? ` (${compressedFrameCount} compressed skipped)` : "";
            console.log(`[UDP] Received ${packetCount} packets${compressedNote} in last 5s`);
            packetCount = 0;
            compressedFrameCount = 0;
            lastLogTime = now;
        }
    });

    server.on("listening", () => {
        const address = server.address();
        console.log(`[UDP] CSI Receiver listening on ${address.address}:${address.port}`);
    });

    server.bind(UDP_PORT, UDP_HOST);
    return server;
}
