# Phantom Scan Data Processing Report

Date: 2026-07-10
Project Root: `D:\WIFI csi\phanotm\phantom scan`
Current Live Runtime: TypeScript dashboard host on UDP `:5005`

## 1. Executive Summary

Phantom Scan is a WiFi CSI sensing system built around two ESP32-S3 nodes and a host runtime that transforms raw wireless channel measurements into a live target state for the dashboard. The system does not process camera frames, audio, or traditional biometric media. Its core input is Channel State Information (CSI) and related radio metadata sent over UDP from the ESP32 nodes.

In the current live checkout, the active processing owner is the Node/TypeScript runtime. It receives CSI packets, parses them into a shared sample schema, applies deterministic signal processing, estimates motion and direction, builds a target track, optionally classifies the motion pattern as human or mechanical, fuses the two nodes into a single 1-D target estimate, and publishes the result to the React dashboard over WebSocket.

This report explains:

- what data enters the system
- how the data is represented internally
- the exact processing stages applied in the live runtime
- how two-node fusion works
- how target state differs from human/mechanical labeling
- where optional AI fits, and where it does not

## 2. Runtime Context

The repository contains more than one runtime track, but the current live path is the TypeScript dashboard host. Historical documents inside the repository note that the TypeScript dashboard is the sole UDP `:5005` ingest owner for live mode. The Python path remains important for DSP logic, replay, and testing, but it is not the default live owner in this checkout.

Operationally, this means the authoritative live path for incoming CSI packets is:

```text
ESP32-S3 nodes -> UDP packets -> server/lib/udp-server.ts -> server/lib/websocket.ts -> WebSocket dashboard
```

## 3. Input Data Types

### 3.1 Primary Data Source

The primary data source is WiFi CSI emitted by the ESP32-S3 nodes. Each node sends packets containing radio-derived values that the host transforms into an internal `CSISample`.

### 3.2 Internal Sample Schema

The shared runtime schema defines a `CSISample` with the following fields:

- `timestamp`: host-side receive time
- `h1`: complex sample for channel observation 1
- `h2`: complex sample for channel observation 2
- `rssi`: optional signal-strength metadata
- `subcarrierIndex`: optional subcarrier identifier
- `nodeId`: optional node identifier
- `amplitudes`: optional array of per-subcarrier amplitudes for the frame

Conceptually:

- `h1` and `h2` are compact complex-valued channel observations used by the legacy/host DSP path
- `amplitudes[]` preserves the richer per-subcarrier frame needed for RuView-style two-node motion and balance fusion

### 3.3 Complex Data Representation

Complex values are represented as:

```json
{ "re": <number>, "im": <number> }
```

These are not abstract labels; they are the actual numerical form used throughout the signal-processing pipeline.

### 3.4 Additional Data Produced During Processing

As the pipeline runs, it generates additional typed outputs:

- `ChannelEstimate`
- `ISARFrame`
- `AoASpectrumPoint`
- `PointCloudPoint`
- `HeatmapData`
- `TrackedTarget`
- `TargetState`
- `targetIdentity` classification payload with `label` and `humanProb`

These are not all raw inputs. Most are derived products used for downstream visualization and state management.

## 4. Packet Ingest and Sample Construction

### 4.1 UDP Receive Path

The live host binds to UDP `:5005` and receives packets from the ESP32 nodes. The parser extracts per-subcarrier information from the incoming packet and computes:

- the dominant subcarrier pair for `h1` and `h2`
- a full `amplitudes[]` vector for the frame
- metadata such as `rssi` and `nodeId`

### 4.2 Dominant Subcarrier Extraction

During packet parsing, the host scans subcarriers and selects the subcarrier with the highest combined power. The chosen complex values become `h1` and `h2` for the `CSISample`.

This design gives the live DSP path a compact scalar/complex representation for immediate processing, while still preserving the full amplitude vector for the two-node fusion logic.

### 4.3 Amplitude Vector Preservation

The `amplitudes[]` field is critical. It stores per-subcarrier amplitudes for a frame, which makes it possible to compute temporal per-subcarrier variation across a window. That is necessary for robust two-node balance localization. A single dominant-subcarrier scalar by itself is too unstable for good localization because the selected strongest subcarrier can jump from frame to frame.

### 4.4 Host Timestamping

Each accepted sample is stamped with `Date.now()` on ingest. This host timestamp is later used for:

- freshness checks
- stale-target suppression
- live-gap handling
- frame ordering assumptions in the live loop

## 5. High-Level Processing Pipeline

The live loop in `server/lib/websocket.ts` documents the full stage order. In practical terms, each frame proceeds through the following pipeline:

```text
live-gap/freshness guards
-> background subtraction
-> motion gate
-> vitals phase extraction
-> Doppler accumulation
-> MUSIC angle spectrum
-> point-cloud generation
-> DBSCAN + Kalman tracking
-> micro-Doppler classification
-> PDP ranging
-> two-node fusion
-> TargetState construction
-> WebSocket broadcast
```

The sections below expand each stage.

## 6. Freshness, Queue Control, and Live-Gap Protection

Before signal processing begins, the runtime checks whether the incoming data is still fresh enough to be considered live.

### 6.1 Why Freshness Matters

Without freshness gating, stale queued packets could continue to drive the pipeline after the nodes disconnect, causing ghost targets on the dashboard.

### 6.2 Freshness Rules

The host uses explicit target-aging thresholds:

- stale after `1.5 s`
- fully cleared after `5 s`

The runtime drops queued samples that are older than the stale window and empties the backlog when no active hardware nodes remain.

### 6.3 Operational Effect

These guards are not cosmetic. They determine whether the rest of the pipeline is allowed to process a sample at all. If no fresh sample exists, the pipeline enters a live-gap path rather than pretending the old target is still current.

## 7. Stage 1: Background Subtraction and Clutter Removal

The first DSP stage removes static background structure from the channel estimate.

### 7.1 Purpose

Indoor wireless channels contain large static components from walls, furniture, and fixed geometry. If these static components dominate the signal, the system cannot isolate motion-related perturbations effectively.

### 7.2 Processing Behavior

When clutter removal is enabled:

- `sample.h1` and `sample.h2` are passed into the background subtractor
- the runtime produces dynamic versions `h1Dynamic` and `h2Dynamic`
- the magnitude of the dynamic output becomes the basis for motion estimation

When clutter removal is disabled, the host falls back to using the raw `h1` magnitude.

### 7.3 Result

This stage produces a signal that emphasizes time-varying perturbations rather than the static baseline channel.

## 8. Stage 2: Motion Gate

After clutter removal, the runtime estimates whether meaningful motion is present.

### 8.1 Input

The motion gate consumes `dynamicAmplitude`, a scalar derived from the clutter-removed complex channel.

### 8.2 Output

It produces a `motionResult` that includes:

- motion-detected boolean behavior
- variance-based motion score
- threshold-aware state used by downstream logic

### 8.3 Important Constraint

In the current design, motion-gate output affects movement classification and presence gating, but a truthful stationary target is allowed to remain visible as idle or degraded instead of disappearing immediately.

This is a deliberate distinction between:

- "is there motion right now?"
- "is there a truthful target state we should continue to show?"

## 9. Stage 3: Channel Estimate Construction

The runtime wraps processed values into a `ChannelEstimate` object containing:

- `timestamp`
- `h1`
- `h2`
- `precodingRatio`
- `nulledSignal`

At this stage, the estimate is mainly a transport structure for downstream visualization and processing. The clutter-removed signal is forwarded as `nulledSignal`.

## 10. Stage 3.5: Vitals Phase Extraction

The system also extracts a phase-derived signal intended for respiration and related low-frequency physiological effects.

### 10.1 Method

The runtime multiplies `h1` by the conjugate of `h2`:

```text
h1 * conj(h2)
```

It then computes the resulting phase and feeds that into the vitals processor.

### 10.2 Purpose

This relative-phase approach helps suppress common frequency-offset effects and exposes phase variation that can carry breathing-related information.

### 10.3 Relationship to Human Detection

This phase path is part of the broader sensing pipeline. In the Python DSP path, respiration periodicity is explicitly part of the deterministic human gate concept. In the TypeScript live path, the dashboard-oriented pipeline emphasizes target state generation and motion-pattern classification, while the Python DSP path preserves the explicit deterministic "motion plus respiration" authority rule.

## 11. Stage 4: Doppler Accumulation

The host pushes `dynamicAmplitude` samples into a Doppler accumulator and periodically emits `dopplerFrame` data.

### 11.1 Purpose

The Doppler representation captures how motion-related energy evolves over time. It supports:

- motion visualization
- downstream micro-Doppler interpretation
- operator insight into the temporal behavior of the target

### 11.2 Broadcast Cadence

To reduce load, the system broadcasts the Doppler frame every third processed frame rather than every single tick.

## 12. Stage 5: MUSIC Angle-of-Arrival Spectrum

The runtime computes an angle spectrum using a MUSIC-based method.

### 12.1 Input

The algorithm works on a sliding buffer of clutter-removed samples.

### 12.2 Internal Method

The implementation:

- builds a covariance matrix from the complex samples
- performs eigenvalue/eigenvector estimation
- separates signal and noise subspaces
- evaluates a MUSIC pseudo-spectrum over an angle range

### 12.3 Output

The result is a list of angle/power points:

- `angle` in degrees
- `power` in dB

The host then finds the strongest peak, which becomes the current best bearing estimate from this stage.

### 12.4 Practical Meaning

This stage answers the question:

"From which direction does the strongest motion-relevant channel perturbation appear to arrive?"

## 13. Stage 6: Point Cloud Generation

Once the angle spectrum exists, the host converts sufficiently strong spectrum regions into a lightweight spatial point cloud.

### 13.1 Construction

For spectrum points above a relative threshold:

- a relative power is derived
- a synthetic distance is estimated
- angle is converted into Cartesian coordinates
- a `PointCloudPoint` is produced

### 13.2 Role in the Pipeline

The point cloud is not a true camera-like reconstruction. It is an intermediate spatial representation that allows clustering and tracking to operate on something more structured than a raw angle trace.

### 13.3 Visualization Role

The point cloud is also broadcast to the client so the dashboard can show a live spatial scene rather than only scalar charts.

## 14. Stage 7: Clustering and Tracking

The host converts point-cloud fragments into a stable tracked target.

### 14.1 DBSCAN Clustering

The first part groups nearby points into clusters using DBSCAN.

Purpose:

- reject isolated noise points
- group coherent returns into candidate spatial targets

### 14.2 Kalman Filtering

The cluster centroid is then smoothed with a six-state constant-velocity Kalman filter:

```text
[x, y, z, vx, vy, vz]
```

### 14.3 Why This Matters

Raw frame-to-frame spatial estimates are noisy. The Kalman filter gives:

- stable target position
- bounded velocity estimates
- smoother heading and speed
- less dashboard jitter

### 14.4 Physical Constraint

The filter clamps velocity to a human-scale speed limit of about `10 m/s`, preventing physically absurd velocity spikes from dominating the display.

## 15. Stage 8: Micro-Doppler Classification

The system separately classifies the motion pattern of the tracked target as:

- `human`
- `mechanical`
- `unknown`

### 15.1 What It Uses

The `MicroDopplerClassifier` consumes a dynamic-amplitude series over time.

### 15.2 Features

It computes two main features over a sliding window:

- `highFreqRatio`: how much motion energy lies above about `5 Hz`
- `periodicity`: how strongly the motion pattern repeats via autocorrelation

### 15.3 Interpretation

The classifier is based on a simple behavioral hypothesis:

- mechanical sources such as fans tend to be faster and strongly periodic
- humans tend to move more slowly and less periodically

### 15.4 Output Semantics

The classifier converts those features into:

- `humanProb`
- `mechanicalProb`
- `label`

With the current thresholds:

- `humanProb > 0.65` => `human`
- `humanProb < 0.35` => `mechanical`
- otherwise => `unknown`

### 15.5 Important Limitation

This classifier does not by itself decide whether a live target should exist on the dashboard. It labels the motion pattern of a target candidate. Presence and target visibility are controlled elsewhere.

## 16. Stage 9: PDP Ranging

The host runs a ranging stage that estimates distance in centimeters.

### 16.1 Purpose

This stage provides:

- `distanceCm`
- wall-related distance metadata

### 16.2 Role

The range estimate is used as part of the radial target representation and provides a physically interpretable distance readout for the operator.

## 17. Stage 10: Radial Target Construction

The runtime then builds a `RadialTarget`, which is the main target structure consumed by downstream state logic and the UI.

Its fields include:

- `x`, `z`
- `r`, `theta`
- `vx`, `vz`
- `isMoving`
- `angle`
- `speed`
- `confidence`
- `label`
- `humanProb`
- `distanceCm`
- `wallDistance`
- `balance`

This structure unifies geometry, motion, identity labeling, and range in one object.

## 18. Stage 11: Two-Node Fusion

Two-node fusion is one of the most important parts of this project.

### 18.1 What Problem It Solves

With only one node, the system can produce limited directional evidence but cannot claim a strong, truthful position estimate. With two nodes, the host can place the target along the line joining the nodes using a balance ratio.

### 18.2 Input Signals

Fusion uses per-node motion statistics derived from windows of `amplitudes[]` frames.

For each node, the host computes:

- `mean`
- `absStd`
- `motion`

Where:

- `absStd` is the raw unsaturated perturbation measure
- `motion` is a normalized, saturated display/threshold value

### 18.3 Why Per-Subcarrier Variation Matters

The fusion logic relies on temporal standard deviation across subcarriers. This is more robust than tracking only a single best subcarrier because human-induced perturbation affects the subcarrier field as a pattern, while best-subcarrier selection alone is unstable and noisy.

### 18.4 Presence Gate

Fusion is also the main live presence detector in the two-node path.

A fused target is emitted only when:

- at least one node's motion exceeds the motion threshold
- real perturbation energy exists

If not, the fusion function returns `null`. This intentionally means:

- no target
- no midpoint ghost
- empty room remains visually empty

### 18.5 Balance Ratio

The balance is computed approximately as:

```text
balance = r2^p / (r1^p + r2^p)
```

Where:

- `r1`, `r2` are per-node raw perturbation measures
- `p` is a contrast exponent used to widen separation toward the nearer node

### 18.6 Display Bias

After balance is computed, an additional display-only bias pulls the projected point closer to the nearest node while keeping the endpoints and midpoint consistent. This improves visual plausibility without changing the underlying identity of which node sees stronger perturbation.

### 18.7 Output Geometry

The final fused target is a 1-D on-axis estimate along the straight line joining node 1 and node 2. It is not a full unconstrained 2-D or 3-D localization result.

### 18.8 Operational Consequence

The two-node fused target is the main truthful live target for the dashboard in the intended two-node mode.

## 19. Stage 12: Target State Construction

After the fused or degraded target is available, the runtime converts it into a `TargetState`.

### 19.1 Why `TargetState` Exists

The dashboard must know not just target coordinates, but whether those coordinates are currently trustworthy and how the target should be presented.

### 19.2 Main States

The current state machine supports:

- `none`
- `stale`
- `idle`
- `moving`
- `degraded`

### 19.3 State Semantics

- `none`: no truthful target exists
- `stale`: the last truthful target is too old to trust
- `idle`: two-node target exists and is currently not moving
- `moving`: two-node target exists and is moving
- `degraded`: only single-node evidence exists, so position is not fully trustworthy

### 19.4 Important Distinction

`TargetState` is the visibility/trust contract for the UI.

It is not the same as:

- `human` vs `mechanical`
- respiratory periodicity verdicts
- firmware-side board metrics

Those are related signals, but `TargetState` decides what the dashboard is allowed to claim live.

## 20. Deterministic Human Gate in Python DSP

The Python DSP package contains an explicit deterministic human gate that defines the authority verdict for "human present" as:

- motion present
- respiration periodic
- optionally cardiac-energy support folded into the same condition

In simple terms, the gate is a deterministic "motion plus periodic respiration" rule.

This is important because it shows the project's intended authoritative logic for human presence: human-ness is not supposed to be created out of thin air by an opaque AI model.

## 21. Optional AI and Its Boundaries

The repository includes an AI probe and optional model assets, but AI is not the authoritative owner of live truth in this checkout.

### 21.1 Current Status

The AI probe reports advisory mode.

### 21.2 What Advisory Means

Advisory AI may:

- provide auxiliary inference
- enrich interpretation
- support experiments

Advisory AI may not:

- originate the definitive human-present verdict
- flip the deterministic authority result
- replace freshness, fusion, or target-state gating in the live pipeline

### 21.3 Practical Meaning

The core live path must remain valid even when AI is absent, unavailable, or intentionally disabled.

## 22. Data Products Exposed to the Dashboard

The dashboard consumes multiple streams, not just one target dot.

Examples include:

- `csiFrame`
- `motionStatus`
- `dopplerFrame`
- `isarFrame`
- `heatmap`
- `pointCloud`
- `trackedTarget`
- `radialTarget`
- `targetIdentity`
- `targetState`

This matters because the UI is not rendering a single monolithic detector output. It is rendering multiple synchronized views of the same underlying processing chain.

## 23. Practical Interpretation of the Processing Stack

The end-to-end interpretation is:

1. ESP32 nodes observe radio-channel disturbance over WiFi CSI.
2. The host converts the packet into complex channel samples and amplitude vectors.
3. Static channel structure is suppressed.
4. Motion-relevant perturbation is isolated.
5. Phase-derived and Doppler-style temporal behavior is accumulated.
6. Directional evidence is estimated with MUSIC.
7. Spatial blobs are formed into a point cloud.
8. Clusters are tracked and smoothed into a stable target.
9. Motion pattern is classified as human or mechanical.
10. Distance is estimated.
11. Two nodes are fused into a single 1-D target when threshold conditions are met.
12. The result is converted into a truthful UI state contract.

## 24. Limits and Non-Claims

This processing stack has explicit limits.

- It is not processing images.
- It is not reconstructing a faithful human mesh from the live truth path.
- The fused target in the two-node mode is fundamentally a 1-D estimate along the node axis.
- Human/mechanical classification is heuristic and based on motion pattern, not identity recognition.
- A visible target on the UI depends on freshness and state gating, not just one classifier score.

These limits are not weaknesses in documentation; they are necessary truth constraints for a system built from CSI perturbation data.

## 25. Conclusion

Phantom Scan processes WiFi CSI and associated radio metadata, not visual media. The current live TypeScript host converts UDP CSI packets into structured complex samples and per-subcarrier amplitude vectors, applies deterministic signal processing and tracking, uses micro-Doppler features for human/mechanical labeling, and relies on two-node fusion plus target-state gating to decide what the dashboard may truthfully show.

The most important architectural distinction is this:

- `targetState` answers whether a live target can be truthfully shown
- `targetIdentity` answers how the target's motion pattern is labeled
- the Python deterministic gate preserves the stronger conceptual rule for human presence authority
- optional AI remains advisory only

For this checkout, the system should be understood first as a deterministic CSI sensing and target-state pipeline, and only secondarily as a classification-enhanced dashboard.

## 26. Key Source Files

- `shared/schema.ts`
- `server/lib/udp-server.ts`
- `server/lib/websocket.ts`
- `server/lib/signal-processing.ts`
- `server/lib/node-fusion.ts`
- `server/lib/target-state.ts`
- `server/lib/tracking.ts`
- `phantom/dsp.py`
- `README.md`
- `AI_PROBE.md`
- `AUDIT.md`
