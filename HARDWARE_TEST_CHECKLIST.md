> **Note (2026-07-08):** written before this session's changes — the firmware now caches node_id pre-WiFi (`csi_collector_set_node_id`) and the dashboard also ingests `0xC5110006` feature-state packets (Board DSP card).

# Hardware Run Report — Phantom Scan

**Purpose**: Operator sign-off for a full two-node ESP32 live test session validating target position truth, skeleton coupling, and state transitions.

| Field | Value |
|---|---|
| Date / time | |
| Operator | |
| Server port | 5000 |
| Data source | [ ] demo  [ ] live ESP32 |
| N1 node ID | |
| N2 node ID | |
| Runtime (`npm run dev`) | [ ] confirmed |
| Both nodes active on connect | [ ] confirmed |

---

## Stage 1 — Transport and Freshness

| Check | Pass | Fail | Notes |
|---|---|---|---|
| Both ESP32 nodes appear active in top bar (green) | [ ] | [ ] | |
| N1 beacon pulsing with motion glow | [ ] | [ ] | |
| N2 beacon pulsing with motion glow | [ ] | [ ] | |
| `node_fps` shows > 0 for both nodes in debug panel | [ ] | [ ] | |
| Unplug N1: N1 beacon dims within ~1.5 s | [ ] | [ ] | |
| `targetState.stale` becomes true at ~1.5 s | [ ] | [ ] | |
| Target dot clears (disappears) by ~5 s | [ ] | [ ] | |
| No ghost target dot remains after 5 s | [ ] | [ ] | |
| Reconnect N1: target reappears within ~2 s | [ ] | [ ] | |
| Unplug both nodes: full clear by 5 s | [ ] | [ ] | |

---

## Stage 2 — Position Truth on the Two-Node Axis

| Position | Expected zone label | Observed label | Dot position matches? |
|---|---|---|---|
| Near N1 (stand within ~0.5 m of N1) | "Near N1" | | [ ] |
| Midpoint between N1 and N2 | "Between N1 and N2" | | [ ] |
| Near N2 (stand within ~0.5 m of N2) | "Near N2" | | [ ] |

| Check | Pass | Fail | Notes |
|---|---|---|---|
| Per-node distance text updates for each position | [ ] | [ ] | |
| Spatial billboard (zone label) updates within ~1 s of position change | [ ] | [ ] | |

---

## Stage 3 — Movement Behaviour

| Action | Expected | Observed | Pass |
|---|---|---|---|
| Walk slowly from N1 toward N2 | Dot slides continuously toward N2 | | [ ] |
| Motion text shows "Moving toward N2" | | | [ ] |
| Stop at midpoint | "Holding at the midpoint" | | [ ] |
| Reverse — walk from N2 toward N1 | "Moving toward N1" | | [ ] |
| Dot follows reversal within 1–2 s | | | [ ] |

---

## Stage 4 — Skeleton Coupling

| Check | Pass | Fail | Notes |
|---|---|---|---|
| Confident human target: skeleton visible | [ ] | [ ] | |
| Skeleton root (hip/chest area) collocated with target dot | [ ] | [ ] | |
| Walk across axis: skeleton translates with dot | [ ] | [ ] | |
| Skeleton does NOT drift away from dot during movement | [ ] | [ ] | |
| Limbs animate relative to body root, not the scene origin | [ ] | [ ] | |
| Degraded confidence (single-node): skeleton hidden, dot visible | [ ] | [ ] | |
| Only `DirectionalNode` marker shown in degraded mode | [ ] | [ ] | |

---

## Stage 5 — State Behaviour

| State | Expected | Pass | Fail |
|---|---|---|---|
| Empty room (no person) | No dot, no skeleton, no distance/bearing | [ ] | [ ] |
| Degraded live target | Dot visible, skeleton hidden, vitals hidden | [ ] | [ ] |
| Truthful moving target | Dot + skeleton visible, vitals allowed | [ ] | [ ] |
| Stale (~1.5 s after last packet) | Dot still shown, state = `stale` | [ ] | [ ] |
| Cleared (~5 s after last packet) | Dot and skeleton both removed | [ ] | [ ] |

---

## Screenshots

| Scenario | File / Notes |
|---|---|
| Target dot aligned with real position at N1 | |
| Target dot aligned with real position at midpoint | |
| Target dot aligned with real position at N2 | |
| Skeleton coupled to dot while walking | |
| Degraded mode — dot only | |
| Stale state — dot fading | |
| Empty scene after clear | |

---

## Acceptance Criteria Sign-off

| Criterion | Met |
|---|---|
| Target dot matches the real person's relative position between the two nodes | [ ] |
| Dot clears correctly after disconnect or silence | [ ] |
| Skeleton, when shown, is visually attached to the same detected target position as the dot | [ ] |
| Degraded live targets never show a free-floating skeleton | [ ] |
| Operator can verify movement direction and relative node proximity from the live dashboard | [ ] |

**Overall result**: [ ] PASS  [ ] FAIL  
**Notes / failed items**:
