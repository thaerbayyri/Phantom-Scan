from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".docx_deps"
if str(DEPS) not in sys.path:
    sys.path.insert(0, str(DEPS))

from docx import Document  # type: ignore
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT_DIR = ROOT / "generated_reports"
OUTPUT_DOC = OUTPUT_DIR / "how project detact the humen.docx"


def set_run_font(run, size: float = 11, bold: bool = False, italic: bool = False, color: str = "000000") -> None:
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    style.font.size = Pt(11)


def style_paragraph(paragraph, *, before: int = 0, after: int = 6, line: float = 1.1, align=WD_ALIGN_PARAGRAPH.LEFT) -> None:
    paragraph.alignment = align
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line


def add_title(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    style_paragraph(p, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
    run = p.add_run(text)
    set_run_font(run, 20, bold=True, color="2E74B5")


def add_subtitle(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    style_paragraph(p, after=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    run = p.add_run(text)
    set_run_font(run, 11, italic=True, color="444444")


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph()
    if level == 1:
        size, before, after, color = 16, 16, 8, "2E74B5"
    elif level == 2:
        size, before, after, color = 13, 12, 6, "2E74B5"
    else:
        size, before, after, color = 12, 8, 4, "1F4D78"
    style_paragraph(p, before=before, after=after)
    run = p.add_run(text)
    set_run_font(run, size, bold=True, color=color)


def add_paragraph(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    style_paragraph(p, after=8, line=1.1, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    run = p.add_run(text)
    set_run_font(run, 11)


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    style_paragraph(p, after=4, line=1.1, align=WD_ALIGN_PARAGRAPH.LEFT)
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.18)
    bullet = p.add_run("• ")
    set_run_font(bullet, 11)
    run = p.add_run(text)
    set_run_font(run, 11)


def set_table_borders(table) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "8")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "D9E2F3")


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    set_table_borders(table)
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.width = Inches(widths[i])
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        shade_cell(cell, "EAF1FB")
        p = cell.paragraphs[0]
        style_paragraph(p, after=2, line=1.0)
        run = p.add_run(header)
        set_run_font(run, 10.5, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cell = cells[i]
            cell.width = Inches(widths[i])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            style_paragraph(p, after=2, line=1.0)
            run = p.add_run(value)
            set_run_font(run, 10.5)
    doc.add_paragraph()


def build_doc() -> Document:
    doc = Document()
    configure_document(doc)

    add_title(doc, "How Project Detect the Human")
    add_subtitle(
        doc,
        "Technical report describing how Phantom Scan captures WiFi CSI, analyzes the signal, detects targets, and decides whether the detected motion is likely human.",
    )

    add_heading(doc, "1. Project Overview", 1)
    add_paragraph(
        doc,
        "Phantom Scan is a ground-based wireless sensing system that uses two ESP32-S3 nodes and a host computer to observe disturbances in WiFi Channel State Information (CSI). The current live runtime is implemented in the Node/TypeScript server path, where the host receives CSI frames over UDP, analyzes the changing wireless channel, estimates the location of a disturbance, and presents the result on a live dashboard. The project is intentionally scoped to a two-node indoor sensing arrangement rather than a drone or large multi-node network. Its main operational goal is device-free detection, meaning the person being detected does not need to carry a phone, tag, or wearable sensor."
    )
    add_paragraph(
        doc,
        "The key scientific idea is that a human body changes the wireless propagation environment. When a person moves, breathes, or occupies part of the signal path, the reflected, scattered, and absorbed components of the WiFi waveform change. CSI exposes those changes as complex-valued channel measurements, and Phantom Scan converts those measurements into motion indicators, direction estimates, range estimates, and a final target state."
    )

    add_heading(doc, "2. Main System Components", 1)
    add_table(
        doc,
        ["Component", "Role in Detection"],
        [
            ["ESP32-S3 Node 1 and Node 2", "Capture CSI and transmit packet data and feature-state summaries to the host."],
            ["UDP Ingest Server", "Receives binary CSI frames on UDP :5005, validates them, and assigns them to the correct node."],
            ["Signal Processing Server", "Runs clutter removal, motion detection, AoA estimation, ranging, tracking, and target fusion."],
            ["Dashboard", "Displays node status, target position, motion state, and supporting sensing metrics."],
            ["Optional AI Sidecar", "Receives forwarded raw samples when available, but is not the primary owner of the live target decision."],
        ],
        [2.1, 4.4],
    )

    add_heading(doc, "3. How CSI Data Is Captured", 1)
    add_paragraph(
        doc,
        "Each ESP32-S3 node is configured to capture WiFi CSI from the surrounding radio environment. CSI is more informative than a simple RSSI reading because it describes the channel response across subcarriers and preserves complex information with real and imaginary values. In practice, this means the system observes not only whether the signal became stronger or weaker, but also how the phase and amplitude structure changed across the packet."
    )
    add_paragraph(
        doc,
        "The firmware sends these observations to the host as compact binary frames. The host stores timestamps, node identifiers, and packet ordering information so that the two streams can be compared reliably. This matters because the fusion logic depends on which node observed stronger motion and how fresh the observation is. If packets arrive out of order or with long gaps, the host must avoid creating a misleading target."
    )
    add_bullet(doc, "CSI frames provide the low-level signal response used by the host DSP pipeline.")
    add_bullet(doc, "Heartbeat and feature-state frames provide node health and firmware-side motion or presence summaries.")
    add_bullet(doc, "The host remains the authoritative processor for the final displayed target.")

    add_heading(doc, "4. CSI Analysis Pipeline", 1)
    add_paragraph(
        doc,
        "After reception, Phantom Scan converts raw CSI into a sequence of deterministic processing stages. The implementation is primarily in the live TypeScript runtime. The purpose of the pipeline is to transform noisy complex radio samples into a stable target estimate without inventing targets when the room is still."
    )
    add_table(
        doc,
        ["Stage", "What the System Does", "Why It Matters"],
        [
            ["1. Ingest and validation", "Accepts live node packets, checks structure, preserves timestamps, and tags source node.", "Prevents bad or stale packets from corrupting later stages."],
            ["2. Clutter removal", "Suppresses the static component of the channel and keeps the dynamic disturbance.", "Reduces the effect of walls, furniture, and stationary objects."],
            ["3. Motion gate", "Measures short-term signal variation and decides whether meaningful motion is present.", "Stops the system from reporting a person when the room is quiet."],
            ["4. AoA estimation", "Computes a MUSIC spectrum and finds the strongest directional peak.", "Provides an estimate of where the disturbance is coming from."],
            ["5. Point-cloud generation", "Transforms strong directional responses into spatial points.", "Creates a geometric representation that can be tracked."],
            ["6. Tracking", "Clusters points and smooths motion using a Kalman filter.", "Stabilizes the target and reduces jitter."],
            ["7. PDP ranging", "Uses a Power Delay Profile with RSSI blending to estimate distance.", "Adds depth or range information to the target estimate."],
            ["8. Two-node fusion", "Compares node motion strength and projects the target on the node axis.", "Improves target placement and suppresses single-node ambiguity."],
            ["9. Truthful target state", "Publishes only fresh, valid, and visible targets to the dashboard.", "Prevents ghost targets and stale visual artifacts."],
        ],
        [1.2, 2.3, 3.0],
    )

    add_heading(doc, "4.1 Clutter Removal and Dynamic Signal Extraction", 2)
    add_paragraph(
        doc,
        "Indoor wireless channels contain a large static component generated by room geometry, walls, desks, floors, and fixed reflectors. If the system used the raw channel directly, the contribution from these stationary objects would dominate the measurement. Phantom Scan therefore applies clutter suppression so that the remaining signal emphasizes dynamic changes rather than static background structure. The result is a dynamic amplitude measure that is much more sensitive to human movement."
    )

    add_heading(doc, "4.2 Motion Gate", 2)
    add_paragraph(
        doc,
        "The motion gate evaluates how much the dynamic signal changes over a short temporal window. This stage is important because a valid target requires evidence of disturbance, not only the existence of a background channel. The output is a motion result containing a motionDetected decision and a variance-like score. In the two-node mode, this gate is part of the logic that prevents the system from creating a centered ghost target in an empty room."
    )

    add_heading(doc, "4.3 Angle of Arrival Estimation with MUSIC", 2)
    add_paragraph(
        doc,
        "Phantom Scan computes a MUSIC spectrum from the processed CSI sample buffer. The MUSIC algorithm is a subspace-based direction-estimation method that searches for the angle with the strongest consistent signal structure relative to noise. The system then selects the highest peak in that spectrum as the dominant angle of arrival. This gives the host a directional cue about where the reflective or moving disturbance lies relative to the sensing geometry."
    )
    add_paragraph(
        doc,
        "Hardware-reality caveat: on this project's actual hardware, each node has exactly one Rx antenna, so no true spatial angle-of-arrival is physically possible. The MUSIC output described above is computed over a temporal window of single-antenna samples and is a signal signature, not a measured spatial bearing. Directional and positional information instead comes from the two-node energy-balance projection onto the fixed 3 m node baseline (a one-dimensional, on-axis estimate)."
    )

    add_heading(doc, "4.4 Point Cloud and Tracking", 2)
    add_paragraph(
        doc,
        "The directional spectrum is converted into a point-cloud-like representation by mapping strong spectral peaks into spatial points. Phantom Scan then applies DBSCAN clustering to group related points and chooses the strongest cluster as the current candidate target. A Kalman filter predicts and updates the target state over time, producing smoother position and velocity estimates than raw frame-by-frame geometry alone. This is why the displayed target can remain stable even when individual packets are noisy."
    )

    add_heading(doc, "4.5 Distance Estimation with Power Delay Profile", 2)
    add_paragraph(
        doc,
        "Direction alone does not tell the system how far the disturbance is from the receiver. For this reason, Phantom Scan computes a Power Delay Profile and blends that estimate with RSSI-derived information. The PDP attempts to infer delay structure, which corresponds to path distance. The implementation then uses this to generate a physically meaningful range in meters or centimeters, making the target placement more informative than angle-only display."
    )

    add_heading(doc, "5. How Phantom Scan Detects a Target", 1)
    add_paragraph(
        doc,
        "A target is detected when the processed signal indicates that a meaningful and fresh disturbance exists. The detection decision is not based on a single number. Instead, it emerges from several linked conditions: dynamic signal energy must be present, the motion gate must not reject the scene, tracking or fused geometry must produce a valid estimate, and the target state must remain fresh enough to display. When those conditions fail, the system intentionally clears the target instead of keeping a stale marker on the screen."
    )
    add_bullet(doc, "If two nodes are active and motion exceeds threshold, the host computes a fused target along the axis joining the nodes.")
    add_bullet(doc, "If two nodes are active but motion remains below threshold, the system publishes no fused target.")
    add_bullet(doc, "If one node is missing, the system can still operate in degraded single-node mode, but spatial certainty is lower.")

    add_heading(doc, "5.1 Two-Node Fusion and Empty-Room Protection", 2)
    add_paragraph(
        doc,
        "The most important live detection behavior in the current repo is the fused two-node mode. In this mode, the host compares motion-derived perturbation levels from Node 1 and Node 2. The target is projected on the line between the two fixed anchors and biased toward the node observing stronger disturbance. This gives a fast and interpretable target location for room-scale movement. Equally important, the fusion function returns no target when the motion threshold is not met. This is the system's negative-control safeguard against false centered detections in an empty room."
    )

    add_heading(doc, "6. How the System Decides the Target Is Human", 1)
    add_paragraph(
        doc,
        "Phantom Scan does not currently rely on a large neural network to decide whether the live target is a human. In the current authoritative runtime, human identification is performed by a lightweight micro-Doppler classifier. The classifier receives a short history of dynamic amplitude values and analyzes their temporal behavior. It derives simple but meaningful signal features that separate irregular biological motion from highly repetitive mechanical disturbance."
    )
    add_table(
        doc,
        ["Human Classification Step", "Description"],
        [
            ["Amplitude buffer", "The classifier stores a short time window of recent dynamic amplitudes."],
            ["Centering", "The mean is removed so the analysis focuses on change rather than baseline level."],
            ["Spectral energy check", "A small Fourier-style power spectrum estimates how much high-frequency energy is present."],
            ["Autocorrelation check", "Periodicity is measured to see whether the motion behaves like a repetitive mechanical source."],
            ["Mechanical score", "High high-frequency ratio and strong periodic repetition increase the mechanical score."],
            ["Human probability", "The system computes humanProb as the inverse of the mechanical tendency."],
            ["Final label", "The result is labeled human, mechanical, or unknown using probability thresholds."],
        ],
        [2.0, 4.5],
    )
    add_paragraph(
        doc,
        "The output includes a probability called humanProb. When this value is high, the label becomes human. When the signal looks strongly repetitive or machine-like, the label becomes mechanical. Intermediate cases remain unknown. This is an intentionally cautious design because the project favors truthful reporting over forcing a confident label from weak evidence."
    )
    add_table(
        doc,
        ["humanProb Range", "System Label", "Interpretation"],
        [
            ["> 0.65", "human", "The motion signature is more consistent with biological movement."],
            ["0.35 to 0.65", "unknown", "The evidence is ambiguous, weak, or mixed."],
            ["< 0.35", "mechanical", "The signal behaves more like repetitive machine disturbance than a person."],
        ],
        [1.4, 1.3, 3.8],
    )

    add_heading(doc, "6.1 Why This Is Not the Same as Full Human Pose AI", 2)
    add_paragraph(
        doc,
        "The repository contains optional AI-related code and model checks, but the current live path does not depend on those models to detect a person. The optional AI path is better described as advisory or experimental support. The final target position and the human-or-mechanical label shown in the dashboard come from deterministic DSP, tracking, and heuristic classification. Therefore, the correct technical description is that the current project uses CSI-based signal analysis and a lightweight classifier, not a full end-to-end neural human-recognition model in live operation."
    )

    add_heading(doc, "7. Why the System May Show Unknown or No Target", 1)
    add_paragraph(
        doc,
        "Phantom Scan is designed to avoid overclaiming. The system may show unknown or no target in several valid situations. First, the room may actually be quiet, and the motion threshold blocks a false detection. Second, the signal may be too weak or too noisy for stable tracking. Third, only one node may be active, reducing the confidence of the fused estimate. Fourth, the target may be present but the observed motion pattern may not clearly match a human or mechanical profile. These outcomes are acceptable and often preferable to a false positive."
    )

    add_heading(doc, "8. Practical Interpretation of a Live Detection", 1)
    add_paragraph(
        doc,
        "When the dashboard shows a live target labeled human, the statement should be interpreted carefully. It means that the two-node CSI sensing pipeline has observed a fresh disturbance in the WiFi channel, extracted directional and ranging information, produced a valid tracked or fused target, and classified the motion pattern as more human-like than mechanical according to the micro-Doppler heuristic. It does not mean that the system has visually recognized a face or recovered a full body image. Phantom Scan remains a privacy-preserving RF sensing system rather than a camera-based identification system."
    )

    add_heading(doc, "9. Repo Modules That Implement This Workflow", 1)
    add_table(
        doc,
        ["File or Module", "Current Responsibility"],
        [
            ["server/lib/udp-server.ts", "Receives and parses live node CSI and feature-state packets."],
            ["server/lib/websocket.ts", "Runs the live sensing pipeline and publishes target outputs to clients."],
            ["server/lib/signal-processing.ts", "Contains MUSIC, motion gate, PDP ranging, and micro-Doppler classifier logic."],
            ["server/lib/tracking.ts", "Provides DBSCAN clustering and Kalman tracking for stable target motion."],
            ["server/lib/node-fusion.ts", "Computes the fused two-node target and empty-room gate."],
            ["server/lib/target-state.ts", "Builds the truthful visibility and freshness state used by the dashboard."],
            ["shared/schema.ts", "Defines data structures for CSI, targets, nodes, and stream messages."],
            ["phantom/ai_status.py", "Checks optional AI stack availability but does not own live target truth."],
        ],
        [2.3, 4.2],
    )

    add_heading(doc, "10. Conclusion", 1)
    add_paragraph(
        doc,
        "Phantom Scan detects a human by converting WiFi CSI disturbances into a chain of deterministic sensing decisions. The ESP32-S3 nodes capture CSI, the host removes static clutter, measures motion, estimates direction with MUSIC, estimates range with PDP, stabilizes the geometry with tracking, and fuses two-node evidence into a final target state. The system then evaluates whether the motion pattern is more human-like or mechanical-like through a micro-Doppler-based heuristic classifier. As a result, the current project provides a practical, privacy-preserving, device-free human sensing workflow without requiring a camera or a fully AI-driven live inference pipeline."
    )

    return doc


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = build_doc()
    doc.save(OUTPUT_DOC)
    print(f"Wrote {OUTPUT_DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
