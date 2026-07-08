import dgram from "dgram";
import { signalServer } from "./websocket";
import type { CSISample } from "@shared/schema";

const UDP_PORT = parseInt(process.env.UDP_PORT || "5005", 10);
const UDP_HOST = "0.0.0.0";

const MAGIC_NUMBER_LE = 0xc5110001;
const HEARTBEAT_MAGIC_LE = 0xc51100a1;
/** RuView firmware rv_feature_state packet (1 Hz per node, board-side DSP). */
const FEATURE_STATE_MAGIC_LE = 0xc5110006;
const FEATURE_STATE_MIN_SIZE = 56;
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

export class SourcePinningGuard {
    /** A pinned source goes stale after this much silence; a new IP may then
     *  claim the node (device reboot + DHCP renumber), which is NOT a spoof. */
    static readonly STALE_BINDING_MS = 10_000;
    /** At most one [UDP][SEC] console line per node per this interval. */
    static readonly WARN_INTERVAL_MS = 5_000;
    /** Bounded security-event history. */
    static readonly MAX_EVENTS = 200;

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

    check(
        nodeId: number,
        source: { address: string; port: number },
        nowMs: number = Date.now(),
        packetKind: "csi_frame" | "feature_state" = "csi_frame",
    ): boolean {
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
        if (nowMs - existing.lastAcceptedMs > SourcePinningGuard.STALE_BINDING_MS) {
            console.log(
                `[UDP] node ${nodeId} source rebound after silence: ` +
                    `${existing.address}:${existing.port} -> ${source.address}:${source.port}`,
            );
            existing.address = source.address;
            existing.port = source.port;
            existing.lastAcceptedMs = nowMs;
            return true;
        }

        this.rejectionCount++;
        const event = {
            record_type: "security_event" as const,
            event_type: "node_source_mismatch" as const,
            node_id: nodeId,
            expected_source: { ip: existing.address, port: existing.port },
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

export type ParsedFeatureState = {
    nodeId: number;
    motion: number;
    presence: number;
    respBpm: number;
    respConf: number;
    hrBpm: number;
    hrConf: number;
};

/**
 * Parse a RuView rv_feature_state packet (magic 0xC5110006, ≥56 bytes LE).
 * Field offsets mirror scripts/ruview-dashboard-bridge.py parse_feat():
 * node_id u8 @4; f32 motion @16, presence @20, resp_bpm @24, resp_conf @28,
 * hr_bpm @32, hr_conf @36.
 */
export function parseFeatureStatePacket(msg: Buffer): ParsedFeatureState | null {
    if (msg.length < FEATURE_STATE_MIN_SIZE) {
        return null;
    }
    if (msg.readUInt32LE(0) !== FEATURE_STATE_MAGIC_LE) {
        return null;
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

export function parseCsiPacket(msg: Buffer): ParsedCsiPacket | null {
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

export function startUDPServer() {
    // Singleton ingest: do NOT set reuseAddr. On Windows SO_REUSEADDR lets a
    // stale/second listener silently share :5005 with non-deterministic delivery,
    // which would steal ESP32 frames. We want a hard EADDRINUSE instead so the
    // operator sees the clash (handled below) rather than losing packets quietly.
    const server = dgram.createSocket("udp4");
    const pyForwardSocket = dgram.createSocket("udp4");
    const sourceGuard = new SourcePinningGuard();

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
    let lastLogTime = Date.now();

    server.on("message", (msg, rinfo) => {
        // Firmware DSP feature-state (RuView 0xC5110006): independent 1 Hz
        // stream shown alongside host-DSP metrics — never fused with them.
        if (msg.length >= 4 && msg.readUInt32LE(0) === FEATURE_STATE_MAGIC_LE) {
            const feat = parseFeatureStatePacket(msg);
            if (feat && sourceGuard.check(feat.nodeId, rinfo, Date.now(), "feature_state")) {
                signalServer.ingestNodeFeatureState(feat);
            }
            return;
        }

        const parsed = parseCsiPacket(msg);
        if (!parsed) {
            return;
        }
        if (!sourceGuard.check(parsed.nodeId, rinfo)) {
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

        // Per-subcarrier amplitudes (antenna 0), capped at 64 like RuView's
        // bridge. The two-node balance fusion needs the full vector: the
        // best-subcarrier scalar below jumps index frame-to-frame, so its
        // temporal std is selection noise, not human motion.
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

            // If RuView sends 2 antennas (unlikely based on current code, but future proofing)
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

        const sample: CSISample = {
            timestamp: Date.now(),
            h1: bestH1,
            h2: bestH2,
            rssi: parsed.rssi,
            nodeId: parsed.nodeId,
            amplitudes,
        };

        signalServer.ingestSample(sample);

        packetCount++;
        const now = Date.now();
        if (now - lastLogTime > 5000) {
            console.log(`[UDP] Received ${packetCount} packets in last 5s`);
            packetCount = 0;
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
