import dgram from "dgram";
import { signalServer } from "./websocket";
import { phaseTestLogger } from "./phase-test-logger";
import { reduceCsiFrame } from "./csi-subcarriers";
import { phyGuard, shouldLogPhyGuardFault, shouldLogPhyMismatch } from "./phy-guard";
import type { CSISample } from "@shared/schema";
import { mapRuntimeNodeIdToHardwareId } from "@shared/schema";

const UDP_PORT = parseInt(process.env.UDP_PORT || "5005", 10);
const UDP_HOST = "0.0.0.0";
const UDP_RECV_BUFFER_BYTES = 4 * 1024 * 1024;

// Local advisory-only Python AI sidecar (ADR-051): loopback-only by
// convention, but configurable rather than hardcoded like every other
// address in this file (Phase-1 bug audit).
const PY_SIDECAR_PORT = parseInt(process.env.PY_SIDECAR_PORT || "5006", 10);
const PY_SIDECAR_HOST = process.env.PY_SIDECAR_HOST || "127.0.0.1";

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
    let phyGuardFaults = 0;
    let compressedFrameCount = 0;
    let lastLogTime = Date.now();
    let lastUnknownMagicLogMs = 0;
    let lastPyForwardErrorLogMs = 0;
    const lastPhaseLogMsByNode = new Map<number, number>();

    server.on("message", (msg, rinfo) => {
        const kind = classifyPacketMagic(msg);

        // Firmware DSP feature-state (0xC5110006): independent 1 Hz
        // stream shown alongside host-DSP metrics — never fused with them.
        if (kind === "feature_state") {
            const feat = parseFeatureStatePacket(msg);
            if (!feat) {
                return;
            }
            // Phase-1 bug audit: this path previously only IP-pinned the
            // sender (sourceGuard.check), unlike the raw-CSI path below which
            // also requires a provisioned hardware node_id (PS-AUDIT-005).
            // Any sender passing the IP check could otherwise inject
            // feature-state data for an arbitrary, never-provisioned node_id.
            if (mapRuntimeNodeIdToHardwareId(feat.nodeId) === undefined) {
                console.warn(`[UDP] rejecting feature_state packet for unmapped runtime node_id=${feat.nodeId}`);
                return;
            }
            if (sourceGuard.check(feat.nodeId, rinfo, Date.now(), "feature_state")) {
                signalServer.ingestNodeFeatureState(feat);
            }
            return;
        }

        // This repo's own firmware vitals (0xC5110002): same role as the
        // 0xC5110006 feature-state packet — board-side presence/motion/vitals for the
        // Board DSP card, never fused with the host target math.
        if (kind === "vitals") {
            const feat = parseEdgeVitalsPacket(msg);
            if (!feat) {
                return;
            }
            // Phase-1 bug audit: same hardware-id gap as feature_state above.
            if (mapRuntimeNodeIdToHardwareId(feat.nodeId) === undefined) {
                console.warn(`[UDP] rejecting vitals packet for unmapped runtime node_id=${feat.nodeId}`);
                return;
            }
            if (sourceGuard.check(feat.nodeId, rinfo, Date.now(), "feature_state")) {
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

        // PS-FIX-08, SHADOW MODE: count/log a change of this node's (subcarrier count, channel, frequency) tuple. Never drops.
        // Item D: the observation is ISOLATED, so a fault in the guard itself (an exception from observe/snapshot/logging) can never
        // drop or delay a frame. Faults are counted and logged once, then once per 1000, never per frame.
        try {
            const phyDiff = phyGuard.observe(parsed.nodeId, {
                nSubcarriers: parsed.numSubcarriers,
                channel: parsed.channel ?? 0,
                freqMhz: parsed.freqMhz ?? 0,
            });
            if (phyDiff.length > 0) {
                const phyStats = phyGuard.snapshot()[String(parsed.nodeId)];
                if (shouldLogPhyMismatch(phyStats)) {
                    console.warn(
                        `[PHY] node ${parsed.nodeId}: ${phyDiff.join(",")} differs from the first-seen tuple ` +
                            `(${phyStats.mismatchedFrames} mismatched of ${phyStats.frames} frames; shadow mode, frames are NOT dropped)`,
                    );
                }
            }
        } catch (err) {
            phyGuardFaults++;
            if (shouldLogPhyGuardFault(phyGuardFaults)) {
                console.error(
                    `[PHY] guard fault #${phyGuardFaults} on node ${parsed.nodeId}: ${err instanceof Error ? err.message : String(err)} ` +
                        `(the frame is still ingested; logged once per 1000 faults)`,
                );
            }
        }

        // Forward only accepted raw packets to the local Python AI sidecar.
        pyForwardSocket.send(msg, PY_SIDECAR_PORT, PY_SIDECAR_HOST, (err) => {
            // The sidecar being down/not-yet-started is expected and not
            // logged every packet — but a persistently failing forward path
            // (Phase-1 bug audit: previously silent forever) now surfaces at
            // most once per 10s so sidecar connectivity loss is diagnosable.
            if (err) {
                const nowMs = Date.now();
                if (nowMs - lastPyForwardErrorLogMs > 10_000) {
                    lastPyForwardErrorLogMs = nowMs;
                    console.warn(`[UDP] AI sidecar forward failed: ${err.message}`);
                }
            }
        });

        // For Phantom Scan, we expect an array of subcarriers.
        // We'll average across the subcarriers for a single representative complex number per antenna for the core math,
        // or just pass the first subcarrier (or an average) as the scalar `h1` and `h2` expected by `CSISample`.
        // Actually, `CSISample` expects `h1` and `h2` as single complex numbers {re, im}. 
        // Usually CSI is an array, but the existing signal pipeline processes them as scalar complex numbers (representing the dominant path).
        // Let's take the subcarrier with the maximum power to represent the sample.

        // Per-subcarrier amplitudes (antenna 0, LLTF data subcarriers only —
        // DC/guards/invalid first word dropped, constant length across frame
        // types) plus the dominant subcarrier as scalar h1/h2. ESP-IDF stores
        // imaginary-first; see csi-subcarriers.ts. On single-antenna boards h2
        // duplicates h1 so downstream magnitude(h2) math never crashes.
        const {
            amplitudes,
            h1: bestH1,
            h2: bestH2,
        } = reduceCsiFrame(parsed.iqData, parsed.numSubcarriers, parsed.numAntennas);

        const phaseRad = Math.atan2(bestH1.im, bestH1.re);
        if (phaseTestLogger.isEnabled()) {
            phaseTestLogger.log(parsed.nodeId, parsed.seq, parsed.rssi, phaseRad);
        }

        // Live phase readout in the npm run terminal, throttled per node to
        // ~1 Hz so it stays readable at the 20-50 Hz CSI packet rate.
        const nowPhaseMs = Date.now();
        const lastPhaseLogMs = lastPhaseLogMsByNode.get(parsed.nodeId) ?? 0;
        if (nowPhaseMs - lastPhaseLogMs >= 1000) {
            lastPhaseLogMsByNode.set(parsed.nodeId, nowPhaseMs);
            console.log(
                `[Phase] node=${parsed.nodeId} phase=${phaseRad.toFixed(4)} rad rssi=${parsed.rssi}dBm`,
            );
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
        // Four nodes burst ~160-200 packets/s; the OS default buffer can overflow
        // while the event loop is busy, dropping frames before any counter sees them.
        try {
            server.setRecvBufferSize(UDP_RECV_BUFFER_BYTES);
        } catch (err) {
            console.warn(`[UDP] Could not enlarge receive buffer: ${err instanceof Error ? err.message : err}`);
        }
    });

    // Closing the ingest socket also releases the sidecar-forward socket (it was leaked before; the live server never closes normally,
    // so this changes nothing at runtime, but a test or a clean shutdown no longer hangs on it).
    server.on("close", () => {
        try {
            pyForwardSocket.close();
        } catch {
            /* already closed by the error handler */
        }
    });

    server.bind(UDP_PORT, UDP_HOST);
    return server;
}
