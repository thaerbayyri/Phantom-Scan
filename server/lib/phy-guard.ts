/**
 * PHY-consistency guard, SHADOW MODE (PS-FIX-08): counts and logs frames whose PHY tuple differs from the one first seen for that
 * node, and NEVER drops, alters or delays a frame. Enforcement would be a separate, approved change (PS-FIX-13).
 *
 * What the ADR-018 header actually carries (firmware/esp32-csi-node/main/csi_collector.c, csi_serialize_frame): subcarrier count
 * (derived from the I/Q length), channel, centre frequency, sequence, RSSI, noise floor. It does NOT carry bandwidth, sig_mode
 * or the transmitter address, so those cannot be locked or checked here; the guard locks (subcarrier count, channel, frequency)
 * per node. Mixed PHY frames would change what "one subcarrier" means and so the features computed from them.
 */
export interface PhyTuple {
  nSubcarriers: number;
  channel: number;
  freqMhz: number;
}

export type PhyField = keyof PhyTuple;

export interface PhyNodeStats {
  locked: PhyTuple;
  frames: number;
  mismatchedFrames: number;
  mismatchByField: Record<PhyField, number>;
  firstMismatchFrame: number | null;
}

export class PhyGuard {
  private readonly nodes = new Map<number, PhyNodeStats>();

  /** Observe one accepted frame. Returns the fields that differ from the node's locked tuple ([] = consistent / first frame). */
  observe(nodeId: number, tuple: PhyTuple): PhyField[] {
    let s = this.nodes.get(nodeId);
    if (!s) {
      s = { locked: { ...tuple }, frames: 0, mismatchedFrames: 0, mismatchByField: { nSubcarriers: 0, channel: 0, freqMhz: 0 }, firstMismatchFrame: null };
      this.nodes.set(nodeId, s);
    }
    s.frames++;
    const diff = (["nSubcarriers", "channel", "freqMhz"] as PhyField[]).filter((f) => tuple[f] !== s!.locked[f]);
    if (diff.length > 0) {
      s.mismatchedFrames++;
      for (const f of diff) s.mismatchByField[f]++;
      if (s.firstMismatchFrame === null) s.firstMismatchFrame = s.frames;
    }
    return diff;
  }

  /** Forget the locked tuple (e.g. after an operator deliberately changes the channel). */
  reset(nodeId?: number): void {
    if (nodeId === undefined) this.nodes.clear();
    else this.nodes.delete(nodeId);
  }

  snapshot(): Record<string, PhyNodeStats> {
    const out: Record<string, PhyNodeStats> = {};
    for (const [id, s] of Array.from(this.nodes.entries())) out[String(id)] = { ...s, locked: { ...s.locked }, mismatchByField: { ...s.mismatchByField } };
    return out;
  }
}

/** Log policy: the first mismatch of a node, then every `every`-th mismatched frame (never per frame at 65 packets/s). */
export function shouldLogPhyMismatch(stats: PhyNodeStats, every = 1000): boolean {
  return stats.mismatchedFrames === 1 || stats.mismatchedFrames % every === 0;
}

/** Log policy for a guard FAULT (an exception thrown by `observe`): the first one, then every `every`-th (never per frame at 65 packets/s). */
export function shouldLogPhyGuardFault(faultCount: number, every = 1000): boolean {
  return faultCount >= 1 && (faultCount === 1 || faultCount % every === 0);
}

export const phyGuard = new PhyGuard();
