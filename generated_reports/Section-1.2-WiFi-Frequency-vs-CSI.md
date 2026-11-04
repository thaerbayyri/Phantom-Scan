# WiFi Frequency vs. CSI Data — Hand-Off Text for Chapter 1

**Purpose:** explains the difference between the WiFi carrier frequency and Channel State
Information (CSI), and states exactly what Phantom Scan uses for human detection.
Written in the same academic voice and citation numbering as the final report, so the
paragraphs can be pasted into the DOCX without editing.

---

## Where to add it in the final DOCX

**Document:** `Final-Phantom-Scan-Project-Report.docx` (and the same spot in
`PhantomScan_FINAL_FULL_DETAILED.docx`).

**Location:** Chapter 1, **Section 1.2 Background** — insert the text below as the
*first* paragraphs of 1.2, immediately after the heading "1.2 Background" and **before**
the existing paragraph that starts with *"Research over the past decade has shown that
commodity wireless hardware…"*.

**Why there and not a new section:** the report's section numbering (1.1–1.8) is fixed
and mirrored in the Table of Contents. Adding a new numbered section (e.g. "1.3 WiFi
Frequency and CSI") would renumber Problem Statement, Limitations, Objectives, etc. and
break the TOC. Placing it at the top of 1.2 Background keeps the numbering intact, and
it is the natural home: 1.1 introduces the idea of WiFi sensing, 1.2 then explains the
physical concept (this text) before reviewing prior research (existing text).

**Formatting when pasting:** normal body paragraphs (Arial 11 pt, justified, like the
rest of the chapter). The short run-in titles in bold at the start of the first three
paragraphs are optional — keep them if you want the sub-topics visible, or delete them
for plain prose. The comparison table is optional; if kept, format it like the other
report tables (Table Grid style) and caption it **"Table 1.1: WiFi carrier frequency
versus Channel State Information."** (If Chapter 1 already has numbered tables, use the
next free number.)

---

## Paste-ready text

**The WiFi carrier frequency.** WiFi communication takes place on a licensed-free radio
band. In the 2.4 GHz band used by this project, the spectrum is divided into numbered
channels: channel 1 is centred at 2412 MHz and each subsequent channel is offset by
5 MHz, so channel 6 — a typical home-router channel — is centred at 2437 MHz. The
carrier frequency is therefore a *configuration parameter* of the radio link: it states
*where* in the spectrum the two radios exchange frames, and it is a single number that
does not change when a person walks through the room. The frequency itself carries no
information about the environment; two identical routers on channel 6 in an empty room
and a crowded room transmit at exactly the same 2437 MHz.

**Channel State Information (CSI).** Every WiFi transmission on that carrier is not one
narrow tone but an OFDM waveform: the roughly 20 MHz-wide channel is split into tens of
narrow subcarriers transmitted in parallel. On its way from transmitter to receiver, the
signal on each subcarrier is reflected, scattered, and attenuated by walls, furniture,
and — critically — the human body. The receiver's WiFi chipset must estimate this
distortion for every received frame in order to decode it, and that estimate is the
Channel State Information: one complex value (an amplitude and a phase) *per subcarrier,
per frame*, describing how the physical channel transformed the signal at that instant.
CSI is therefore a *measurement* of the environment, refreshed with every packet. It is
also far richer than the familiar RSSI indicator: RSSI compresses the whole channel into
a single received-power number, whereas CSI resolves the channel into a vector of
per-subcarrier responses, so a small human movement that barely changes total power
still visibly disturbs individual subcarriers [1], [7].

**The distinction in one sentence.** The WiFi frequency is the *medium* — a fixed
carrier position in the spectrum chosen by the network — while CSI is the *measurement*
— a per-subcarrier snapshot of what the environment did to the signal travelling on that
medium. A moving person never changes the WiFi frequency; a moving person changes the
multipath channel *at* that frequency, and CSI is the mechanism by which the system
observes that change.

**What Phantom Scan uses.** Phantom Scan detects humans from CSI, not from the carrier
frequency and not from RSSI. Both ESP32-S3 nodes associate to a 2.4 GHz network, and the
firmware enables the WiFi driver's CSI callback so that every received frame yields the
raw channel estimate as one signed 8-bit in-phase/quadrature (I/Q) pair per subcarrier
[7], [12]. The frames are streamed to the host, where the server converts each I/Q pair
into a per-subcarrier amplitude (the magnitude of the complex channel estimate, computed
over up to 64 subcarriers). Human detection then operates on the *temporal behaviour* of
these amplitudes: over a sliding 1.5-second window the server computes the standard
deviation of each subcarrier's amplitude and averages across subcarriers, producing a
motion-energy score per node. In an empty room the channel is static and the score stays
near zero; a moving person continuously reshapes the multipath, the per-subcarrier
amplitudes fluctuate, and the score rises above the empty-room threshold (provisional: 0.6, set from one 60 s empty recording).
Comparing the two nodes' scores with the RuView balance ratio then places the person on
the axis between the nodes [15]. Phase information, although present in raw CSI, is
deliberately not used on the live detection path: with a single antenna per node, the
phase reported by commodity chipsets is dominated by unsynchronized-oscillator offsets
and is unstable frame-to-frame, whereas the amplitude is robust [1], [12].

### Optional comparison table

| Aspect | WiFi carrier frequency | Channel State Information (CSI) |
|---|---|---|
| What it is | Position of the channel in the radio spectrum (e.g. 2437 MHz for channel 6) | Per-subcarrier estimate of how the environment transformed the received signal |
| Form | One fixed number per channel | Vector of complex values (amplitude + phase), one per subcarrier, up to 64 in this project |
| Refresh rate | Static (changes only if the network changes channel) | Every received frame (up to 50 Hz per node in this project) |
| Affected by a moving human? | No | Yes — reflections off the body reshape the per-subcarrier amplitudes |
| Role in Phantom Scan | Operating band of the two nodes (2.4 GHz) | The sensing signal: temporal std of per-subcarrier amplitudes over 1.5 s drives motion detection and two-node balance localization |

---

## Verified sources in the repository (not for the DOCX — for your reference)

- Channel → frequency mapping (2412 + (channel−1)·5 MHz): `firmware/esp32-csi-node/main/csi_collector.c`, frequency-derivation block.
- Raw CSI payload = int8 I/Q pairs per subcarrier; amplitude = √(I²+Q²), capped at 64 subcarriers (antenna 0): `server/lib/udp-server.ts`.
- Motion energy = per-subcarrier temporal standard deviation over the 1500 ms window; empty-room gate threshold 0.6 (provisional; set from one 60 s empty recording, false-alarm and detection rates [TO BE MEASURED]): `server/lib/` fusion pipeline, `shared/schema.ts` comment on `amplitudes`.
- Two-node RuView balance localization: report Chapter 6 / reference [15].
