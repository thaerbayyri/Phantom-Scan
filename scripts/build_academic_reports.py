"""Build the Phantom Scan academic report package.

Generates the milestone chapter documents (Task 1..5 + Chapter 6) and the
unified Final-Phantom-Scan-Project-Report.docx (Chapters 1-8, References, and
the full source-code appendices). All chapter content is grounded in the
current repository state: the ground-based two-node ESP32-S3 system with the
Node/TypeScript live dashboard runtime and the Python replay/tooling path.

Run with Python 3.13 (the vendored .docx_deps binaries are cp313-only):
    python scripts/build_academic_reports.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".docx_deps"
if str(DEPS) not in sys.path:
    sys.path.insert(0, str(DEPS))

from docx import Document  # type: ignore
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


OUTPUT_DIR = ROOT / "generated_reports"


# ---------------------------------------------------------------------------
# IEEE-numbered references. Every in-text [n] must map to an entry here.
# ---------------------------------------------------------------------------
REFERENCES = {
    1: "F. Adib and D. Katabi, \"See through walls with WiFi!,\" in Proc. ACM SIGCOMM, Hong Kong, China, 2013, pp. 75-86.",
    2: "F. Adib, Z. Kabelac, D. Katabi, and R. C. Miller, \"3D tracking via body radio reflections,\" in Proc. USENIX NSDI, Seattle, WA, USA, 2014, pp. 317-329.",
    3: "F. Adib, H. Mao, Z. Kabelac, D. Katabi, and R. C. Miller, \"Smart homes that monitor breathing and heart rate,\" in Proc. ACM CHI, Seoul, South Korea, 2015, pp. 837-846.",
    4: "W. Wang, A. X. Liu, M. Shahzad, K. Ling, and S. Lu, \"Understanding and modeling of WiFi signal based human activity recognition,\" in Proc. ACM MobiCom, Paris, France, 2015, pp. 65-76.",
    5: "M. Kotaru, K. Joshi, D. Bharadia, and S. Katti, \"SpotFi: Decimeter level localization using WiFi,\" in Proc. ACM SIGCOMM, London, UK, 2015, pp. 269-282.",
    6: "Y. Ma, G. Zhou, and S. Wang, \"WiFi sensing with channel state information: A survey,\" ACM Computing Surveys, vol. 52, no. 3, pp. 1-36, 2019.",
    7: "S. M. Hernandez and E. Bulut, \"Lightweight and standalone IoT based WiFi sensing for active repositioning and mobility,\" in Proc. IEEE WoWMoM, Cork, Ireland, 2020, pp. 277-286.",
    8: "Y. Geng, J. Huang, J. He, and F. De la Torre, \"DensePose from WiFi,\" arXiv:2301.00250, 2023.",
    9: "X. Yan et al., \"Person-in-WiFi 3D: End-to-end multi-person 3D pose estimation with Wi-Fi,\" in Proc. IEEE/CVF CVPR, Seattle, WA, USA, 2024.",
    10: "Y. Zhou et al., \"AdaPose: Cross-site device-free human pose estimation with commodity WiFi,\" IEEE Internet of Things Journal, vol. 11, no. 23, pp. 40255-40267, 2024.",
    11: "Espressif Systems, \"Wi-Fi Channel State Information,\" ESP-IDF Programming Guide for ESP32-S3, 2025. [Online]. Available: https://docs.espressif.com/projects/esp-idf/",
    12: "Phantom Scan repository, \"README.md,\" current verified repository state, Jul. 8, 2026.",
    13: "Phantom Scan repository, \"docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md,\" rev. 2.0, Mar. 2026, historical architecture source used with current-state corrections.",
    14: "Phantom Scan repository, \"docs/system_architecture_methodology.md,\" methodology source used with current-state corrections.",
    15: "Phantom Scan repository, \"docs/ruview-2node-full-analysis-report.md,\" two-node RuView balance-method analysis, Jul. 7, 2026.",
    16: "Phantom Scan repository, \"docs/adr/ADR-018-esp32-dev-implementation.md,\" ESP32 CSI frame format decision record (implemented packet contract).",
    17: "Phantom Scan verification record, \"TEST_REPORT.md,\" software validation pass, Jul. 1, 2026.",
    18: "Phantom Scan verification record, \"TARGET_VERIFICATION_REPORT.md,\" dashboard truth-model verification, Jun. 29, 2026.",
    19: "Phantom Scan verification record, \"TEST_AND_CLEANUP_REPORT.md,\" two-node hardware session and full test matrix, Jul. 8, 2026.",
    20: "Phantom Scan verification record, \"REAL_TEST_REPORT.md,\" two-node positional-fidelity campaign protocol and trial-log template.",
    21: "Phantom Scan verification record, \"MEASUREMENT_PLAN.md,\" headline-metric measurement protocol with honesty rules.",
    22: "Phantom Scan verification record, \"DETECTION_REPORT.md,\" detection-metric status report, Jul. 1, 2026.",
    23: "Phantom Scan verification record, \"HARDWARE_TEST_CHECKLIST.md,\" hardware run and acceptance checklist, Jul. 8, 2026.",
}


# Canonical section outline shared by every generated document (and imported
# by build_detailed_final_report.py for its table of contents).
TOC_LINES = [
    "CHAPTER 1 - INTRODUCTION",
    "1.1 Introduction",
    "1.2 Background",
    "1.3 Problem Statement",
    "1.4 Limitations",
    "1.5 Project Objectives",
    "1.6 Project Solution Overview",
    "1.7 Project Scope",
    "1.8 Project Feasibility",
    "CHAPTER 2 - LITERATURE REVIEW",
    "2.1 Introduction",
    "2.2 Review of Existing Systems",
    "2.3 Comparison of Existing Solutions",
    "CHAPTER 3 - METHODOLOGY AND WORK PLAN",
    "3.1 Introduction",
    "3.2 System Development Methodology",
    "3.3 Requirement Gathering Techniques",
    "3.4 Project Plan (Gantt Chart)",
    "3.5 Development of Tools and Technologies",
    "CHAPTER 4 - SYSTEM SPECIFICATION",
    "4.1 Introduction",
    "4.2 Functional Requirements",
    "4.3 Non-Functional Requirements",
    "CHAPTER 5 - SYSTEM DESIGN",
    "5.1 Introduction",
    "5.2 System Architecture Design",
    "5.3 Class Diagram and Module Interaction Design",
    "5.4 Database and Data Design",
    "5.5 User Interface (UI) Design",
    "5.6 Summary",
    "CHAPTER 6 - SYSTEM IMPLEMENTATION",
    "6.1 Introduction",
    "6.2 Implementation Overview",
    "6.3 Implementation Details",
    "6.4 Component Integration and Workflow",
    "6.5 Implementation Testing Support",
    "6.6 Summary",
    "CHAPTER 7 - RESULTS AND DISCUSSION",
    "7.1 Introduction",
    "7.2 Data Collection and Research",
    "7.3 System Testing and User Feedback",
    "7.4 Discussion",
    "CHAPTER 8 - RECOMMENDATIONS AND CONCLUSION",
    "8.1 Introduction",
    "8.2 Conclusion",
    "8.3 Limitations and Recommendations for Future Work",
    "APPENDICES",
    "REFERENCES",
]


# ---------------------------------------------------------------------------
# Style helpers (Arial 11pt body, 1.15 spacing, justified; Consolas for code)
# ---------------------------------------------------------------------------

def set_run_font(run, size: float = 11, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def set_mono_font(run, size: float = 8) -> None:
    run.font.name = "Consolas"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Consolas")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Consolas")
    run.font.size = Pt(size)


def style_paragraph(paragraph, after: int = 8, before: int = 0, size: float = 11) -> None:
    fmt = paragraph.paragraph_format
    fmt.space_after = Pt(after)
    fmt.space_before = Pt(before)
    fmt.line_spacing = 1.15
    for run in paragraph.runs:
        set_run_font(run, size=size, bold=run.bold, italic=run.italic)


def add_text_paragraph(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    set_run_font(run)
    style_paragraph(p)


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.15)
    dash = p.add_run("- ")
    set_run_font(dash)
    run = p.add_run(text)
    set_run_font(run)
    style_paragraph(p, after=4)


def add_numbered_list(doc: Document, items: list[str]) -> None:
    """Manually numbered list so numbering restarts per list in every document."""
    for index, text in enumerate(items, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.first_line_indent = Inches(-0.15)
        prefix = p.add_run(f"{index}. ")
        set_run_font(prefix)
        run = p.add_run(text)
        set_run_font(run)
        style_paragraph(p, after=4)


def add_heading(doc: Document, text: str, level: int) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    if level == 1:
        set_run_font(run, size=16, bold=True)
        style_paragraph(p, before=16, after=8, size=16)
    elif level == 2:
        set_run_font(run, size=13, bold=True)
        style_paragraph(p, before=12, after=6, size=13)
    else:
        set_run_font(run, size=12, bold=True)
        style_paragraph(p, before=8, after=4, size=12)


def add_title(doc: Document, title: str, subtitle: str | None = None) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    set_run_font(run, size=22, bold=True)
    style_paragraph(p, after=6, size=22)
    if subtitle:
        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run2 = p2.add_run(subtitle)
        set_run_font(run2, size=12)
        style_paragraph(p2, after=14, size=12)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, size=10, italic=True)
    style_paragraph(p, after=10, size=10)


def set_cell_text(cell, text: str, bold: bool = False) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(text)
    set_run_font(run, size=10.5, bold=bold)


def set_table_borders(table) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "8")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "DADCE0")


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    try:
        table.style = "Table Grid"
    except KeyError:
        pass  # host document (e.g. course cover) lacks the style; manual borders below
    table.autofit = False
    set_table_borders(table)
    for i, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], header, bold=True)
        if widths:
            table.rows[0].cells[i].width = Inches(widths[i])
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            set_cell_text(cells[i], value)
            if widths:
                cells[i].width = Inches(widths[i])
    doc.add_paragraph()


def _shade_paragraph(paragraph, fill: str = "F6F6F6") -> None:
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    paragraph._p.get_or_add_pPr().append(shading)


def add_code_block(doc: Document, code: str, size: float = 8.5, chunk: int = 40) -> None:
    """Render source text as shaded monospace paragraphs.

    Lines are grouped into chunks of `chunk` lines per paragraph (joined with
    soft line breaks) so very large appendix files stay fast to build and open.
    """
    lines = [line.rstrip().replace("\t", "    ") for line in code.splitlines()]
    if not lines:
        lines = [""]
    keep_together = len(lines) <= chunk  # short listings/diagrams stay on one page
    for start in range(0, len(lines), chunk):
        block = lines[start:start + chunk]
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        fmt = p.paragraph_format
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1.0
        if keep_together:
            fmt.keep_together = True
        _shade_paragraph(p)
        for i, line in enumerate(block):
            run = p.add_run(line if line else " ")
            set_mono_font(run, size=size)
            if i < len(block) - 1:
                run.add_break()
    doc.add_paragraph()


def add_reference_section(doc: Document, refs: Iterable[int]) -> None:
    add_heading(doc, "REFERENCES", 1)
    for ref_id in refs:
        p = doc.add_paragraph()
        run = p.add_run(f"[{ref_id}] {REFERENCES[ref_id]}")
        set_run_font(run)
        style_paragraph(p, after=4)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.49)
    section.footer_distance = Inches(0.49)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    styles["Normal"]._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    styles["Normal"].font.size = Pt(11)


def add_toc_page(doc: Document) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("TABLE OF CONTENTS")
    set_run_font(run, size=16, bold=True)
    style_paragraph(p, after=10, size=16)
    for line in TOC_LINES:
        p = doc.add_paragraph()
        if line.startswith("CHAPTER") or line in {"APPENDICES", "REFERENCES"}:
            run = p.add_run(line)
            set_run_font(run, size=11.5, bold=True)
            style_paragraph(p, before=4, after=3, size=11.5)
        else:
            p.paragraph_format.left_indent = Inches(0.25)
            run = p.add_run(line)
            set_run_font(run, size=10.5)
            style_paragraph(p, after=2, size=10.5)


# ---------------------------------------------------------------------------
# Chapter 1 - Introduction
# ---------------------------------------------------------------------------

def chapter_1(doc: Document) -> list[int]:
    refs = [1, 6, 7, 8, 12, 15, 19, 20, 21]
    add_heading(doc, "CHAPTER 1 - INTRODUCTION", 1)

    add_heading(doc, "1.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan is an academic and engineering project that investigates how WiFi Channel "
        "State Information (CSI) can be used to detect a moving human, estimate that person's "
        "relative position, and present the result truthfully on a live operator dashboard - all "
        "without cameras, microphones, or wearable devices. In its current verified state, the "
        "system consists of exactly two ESP32-S3 microcontroller nodes that capture CSI from "
        "ordinary 2.4 GHz WiFi traffic and stream binary measurement frames over UDP to a laptop "
        "host, where a Node/TypeScript runtime performs deterministic signal processing, fuses the "
        "two node perspectives into a single target estimate, and publishes the result to a React "
        "dashboard over WebSocket [12].",
    )
    add_text_paragraph(
        doc,
        "The core physical insight behind the project is that a human body moving through a radio "
        "field perturbs the multipath propagation between transmitter and receiver. WiFi CSI "
        "exposes this perturbation at the granularity of individual OFDM subcarriers: when a person "
        "walks between or near the sensing nodes, the per-subcarrier amplitude of the received "
        "channel estimate fluctuates measurably over time, while an empty room produces a "
        "comparatively stable channel [6]. Phantom Scan converts that fluctuation into a live, "
        "gated, and honestly-labeled detection.",
    )
    add_text_paragraph(
        doc,
        "The topic is practically relevant because many safety, monitoring, and assistive scenarios "
        "need privacy-preserving situational awareness. Camera systems capture faces, appearance, "
        "and scenes, which creates privacy, storage, and regulatory concerns. Radio-frequency "
        "sensing observes only propagation changes, operates in darkness, and can penetrate "
        "common non-metallic building materials [1].",
    )

    add_heading(doc, "1.2 Background", 2)
    add_text_paragraph(
        doc,
        "Research over the past decade has shown that commodity wireless hardware can support "
        "contactless sensing tasks ranging from through-wall motion detection [1] to activity "
        "recognition [6] and even dense human pose estimation [8]. Early systems relied on "
        "specialized network interface cards or software-defined radio, which limited "
        "reproducibility. The arrival of CSI extraction support on the low-cost Espressif ESP32 "
        "family changed the economics of the field: a complete sensing node now costs roughly the "
        "price of a development board rather than the price of laboratory radio equipment [7].",
    )
    add_text_paragraph(
        doc,
        "Phantom Scan builds directly on this evolution. Each ESP32-S3 node runs ESP-IDF firmware "
        "that enables the WiFi driver's CSI callback, serializes each channel estimate into a "
        "compact 32-byte-header binary frame, and streams it to the host over UDP. On the host, the "
        "detection method follows the two-receiver 'balance' approach analysed in the project's "
        "RuView study [15]: each node independently measures how strongly the channel is being "
        "perturbed, and the ratio of the two perturbation energies places the moving person on the "
        "line between the two nodes. The project deliberately keeps this pipeline deterministic and "
        "auditable; an optional AI sidecar exists but is advisory and disabled by default [12].",
    )
    add_text_paragraph(
        doc,
        "An important part of the project's history is scope correction. Earlier project documents "
        "explored drone-mounted sensing, GPS/IMU integration, and large multistatic meshes. Those "
        "directions are now explicitly historical: the active repository targets a ground-based "
        "two-node deployment, and an automated invariant test fails the build if flight-control "
        "concepts re-enter the runtime code [12], [19].",
    )

    add_heading(doc, "1.3 Problem Statement", 2)
    add_text_paragraph(
        doc,
        "The main problem addressed by Phantom Scan is how to design a low-cost, privacy-first "
        "sensing system that can detect and localize a moving human using commodity WiFi hardware "
        "while remaining technically honest about uncertainty, degraded states, and hardware "
        "limitations. Existing research systems often depend on expensive platforms or opaque "
        "learned models, and practical dashboards frequently hide the difference between live "
        "measurement and synthetic estimation. A sensing dashboard that paints a target when no "
        "live evidence exists is worse than no dashboard at all.",
    )
    add_text_paragraph(
        doc,
        "The problem is therefore dual. First, an engineering problem: capture CSI reliably on "
        "embedded hardware, transport it without identity confusion, and turn per-subcarrier "
        "amplitude fluctuations into a stable motion and position estimate. Second, a truthfulness "
        "problem: guarantee at the architecture level that an empty room shows no target, a silent "
        "node degrades the display honestly, and stale data clears instead of ghosting.",
    )

    add_heading(doc, "1.4 Limitations", 2)
    add_bullet(doc, "The fused localization is one-dimensional: the target is placed on the 3 m line between the two node anchors. A person walking off-axis is projected onto that line, and movement perpendicular to the axis is not representable [12], [15].")
    add_bullet(doc, "Each node uses a single antenna, so classical multi-antenna Angle-of-Arrival techniques run only on synthetic or replay inputs, not on the live path [12].")
    add_bullet(doc, "The detection gate threshold (default 0.12) is an engineering placeholder that must be calibrated per room from an empty-room baseline; the repository ships a calibration tool for this purpose [12].")
    add_bullet(doc, "Headline live metrics such as detection rate, false-positive rate, and localization error are defined in measurement protocols but not yet populated from repeated live campaigns [20], [21].")
    add_bullet(doc, "Two people in the sensing area blend into a single fused estimate; multi-target separation is out of the current scope [20].")

    add_heading(doc, "1.5 Project Objectives", 2)
    add_numbered_list(doc, [
        "To design and implement a working WiFi CSI capture and transport pipeline using two ESP32-S3 nodes streaming binary frames over UDP to a laptop host.",
        "To implement a deterministic human-motion detector based on per-subcarrier amplitude turbulence, with an explicit empty-room gate so that a quiet room produces no target.",
        "To fuse the two node perspectives into a live one-dimensional position estimate with per-node distance and approaching/receding trend readouts.",
        "To build a real-time dashboard that visually distinguishes truthful live targets, degraded single-node states, stale data, and empty-room silence.",
        "To protect the live data path against node identity spoofing and unauthorized access.",
        "To document and test the system so that every technical claim maps to a source file, an automated test, or a recorded verification artifact.",
    ])

    add_heading(doc, "1.6 Project Solution Overview", 2)
    add_text_paragraph(
        doc,
        "The implemented solution is organized into five cooperating layers [12]. Layer A is the "
        "ESP32-S3 firmware, which captures CSI in promiscuous mode, keeps the channel busy with a "
        "self-ping mechanism, and streams rate-limited binary frames. Layer B is the host ingest: a "
        "Node/TypeScript UDP server that owns port 5005, validates three packet families by magic "
        "number, and pins each node identity to its source address. Layer C is the deterministic "
        "DSP core: a sliding-window per-subcarrier turbulence metric per node, a motion gate, and a "
        "two-node balance fusion that yields the on-axis position, distance, and trend. Layer D is "
        "an optional, advisory AI sidecar that is disabled by default and cannot override the "
        "deterministic result. Layer E is the API and UI layer: an authenticated WebSocket stream "
        "feeding a React/Three.js operator dashboard, plus recording, replay, and reporting tools.",
    )
    add_text_paragraph(
        doc,
        "A parallel Python package provides replay of recorded sessions, protocol parsing, and "
        "reference DSP implementations. It is the test harness and tooling path; the Node/TypeScript "
        "runtime is the single authoritative live ingest in normal operation [12].",
    )

    add_heading(doc, "1.7 Project Scope", 2)
    add_text_paragraph(doc, "Project Scope Covered:")
    add_bullet(doc, "Two-node ESP32-S3 CSI capture, ADR-018 binary framing, and UDP transport to a laptop host.")
    add_bullet(doc, "Live human-motion detection, empty-room gating, two-node balance fusion, distance and trend estimation.")
    add_bullet(doc, "Authenticated live dashboard with radar-style scene, per-node telemetry, spectral views, and honest state labeling.")
    add_bullet(doc, "JSONL/CSV recording, deterministic replay, threshold calibration tooling, and automated regression testing.")
    add_bullet(doc, "Source pinning against node spoofing, operator authentication, and audit logging.")
    add_text_paragraph(doc, "Project Scope Not Covered:")
    add_bullet(doc, "Drone, UAV, MAVLink, GPS, or IMU-based deployment; these appear only in historical documents and are excluded from the runtime by an automated scope-guard test [12].")
    add_bullet(doc, "True two- or three-dimensional localization of off-axis targets from the current two-node, single-antenna geometry.")
    add_bullet(doc, "Multi-person separation and identification.")
    add_bullet(doc, "A production-scale multi-tenant database platform; persistence is deliberately file-based.")

    add_heading(doc, "1.8 Project Feasibility", 2)
    add_text_paragraph(
        doc,
        "Technical feasibility is demonstrated rather than assumed: the repository contains the "
        "complete firmware, host runtime, dashboard, and test suites, and the most recent "
        "verification session shows two physical ESP32-S3 boards streaming approximately 40 packets "
        "per second aggregate to the live ingest, with all 91 TypeScript tests and 82 Python tests "
        "passing [19]. Economic feasibility is strong because each sensing node is a commodity "
        "ESP32-S3 development board costing a few dollars, compared with specialized radar hardware "
        "costing orders of magnitude more. Operational feasibility is supported by a single-command "
        "development stack and by run guides for Windows and Ubuntu hosts [12]. The main residual "
        "feasibility risk is not software but measurement: converting the implemented detection "
        "chain into defensible accuracy numbers requires the repeated live-room campaigns defined "
        "in the project's measurement protocols [20], [21].",
    )
    return refs


# ---------------------------------------------------------------------------
# Chapter 2 - Literature Review
# ---------------------------------------------------------------------------

def chapter_2(doc: Document) -> list[int]:
    refs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15]
    add_heading(doc, "CHAPTER 2 - LITERATURE REVIEW", 1)

    add_heading(doc, "2.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "WiFi-based human sensing has progressed from coarse received-signal-strength presence "
        "detection to subcarrier-level Channel State Information systems capable of localization, "
        "vital-sign monitoring, activity recognition, and pose estimation [6]. Each generation of "
        "systems makes different tradeoffs between hardware cost, output fidelity, deployability, "
        "and robustness. Reviewing this landscape positions Phantom Scan precisely: it is a "
        "low-cost, deterministic, implementation-first system that occupies a gap between "
        "expensive research prototypes and unvalidated hobbyist demonstrations.",
    )

    add_heading(doc, "2.2 Review of Existing Systems", 2)
    add_heading(doc, "2.2.1 Wi-Vi: Through-Wall Motion Sensing", 3)
    add_text_paragraph(
        doc,
        "Wi-Vi demonstrated that ordinary WiFi transmissions can be used to detect and coarsely "
        "track humans moving behind walls, using interference nulling to cancel static reflections "
        "and isolate the moving component of the channel [1]. Its central contribution - that the "
        "static environment can be treated as clutter and subtracted, leaving human motion as the "
        "signal - is the same principle Phantom Scan applies in time-domain form: the temporal "
        "standard deviation of per-subcarrier amplitude is insensitive to the static channel and "
        "responds to motion-induced perturbation. Wi-Vi, however, required a purpose-built "
        "multi-antenna radio; Phantom Scan targets $10-class commodity nodes.",
    )
    add_heading(doc, "2.2.2 WiTrack and Vital-Radio: RF Localization and Vital Signs", 3)
    add_text_paragraph(
        doc,
        "WiTrack extended radio sensing to 3D tracking of a person via body radio reflections using "
        "frequency-modulated carrier waves [2], and Vital-Radio showed that respiration and heart "
        "rate can be extracted from the phase of reflected RF signals at multi-meter range [3]. "
        "These systems prove that radio sensing can recover both position and physiology, but both "
        "rely on dedicated wideband hardware rather than standard WiFi. Phantom Scan retains "
        "vital-sign estimation as a secondary, phase-based feature (host-side and firmware-side "
        "respiration/heart-rate estimators exist in the code) while keeping its primary detection "
        "claim on the better-conditioned amplitude-turbulence path.",
    )
    add_heading(doc, "2.2.3 CARM: Modeling CSI Dynamics of Human Activity", 3)
    add_text_paragraph(
        doc,
        "CARM established a quantitative model linking CSI amplitude dynamics to human movement "
        "speed and activity, showing that CSI variance over time is a physically meaningful motion "
        "feature rather than an ad hoc statistic [4]. This is the theoretical justification for "
        "Phantom Scan's core detector: the per-subcarrier temporal standard deviation used by the "
        "fusion module is exactly a windowed CSI-dynamics measure of the kind CARM models. CARM "
        "used Intel 5300 NICs and offline processing; Phantom Scan implements the equivalent "
        "statistic in a live 20 Hz processing loop on streaming embedded data.",
    )
    add_heading(doc, "2.2.4 SpotFi: Decimeter Localization on Commodity WiFi", 3)
    add_text_paragraph(
        doc,
        "SpotFi achieved decimeter-level localization by super-resolving Angle of Arrival and time "
        "of flight from commodity access points with multiple antennas [5]. It defines the accuracy "
        "ceiling for commodity WiFi localization, but its method fundamentally requires antenna "
        "arrays and dense AP deployment. Phantom Scan's single-antenna ESP32-S3 nodes cannot apply "
        "SpotFi-style AoA on the live path - which is why the project adopts the two-receiver "
        "energy-balance geometry instead and is explicit that its live output is a one-dimensional "
        "on-axis estimate [15].",
    )
    add_heading(doc, "2.2.5 ESP32 CSI Sensing: Low-Cost Standalone Nodes", 3)
    add_text_paragraph(
        doc,
        "Hernandez and Bulut demonstrated that the ESP32 family can serve as a standalone, "
        "lightweight WiFi sensing platform, extracting CSI without laboratory NICs and enabling "
        "device-free sensing at IoT price points [7]. This line of work is the direct hardware "
        "enabler of Phantom Scan. The project extends it with an engineered transport contract "
        "(a versioned 32-byte binary header, sequence numbers, and device timestamps), firmware "
        "self-ping to guarantee CSI supply on quiet networks, and host-side source pinning - "
        "concerns that research prototypes typically leave unaddressed [12].",
    )
    add_heading(doc, "2.2.6 Learned WiFi Sensing: DensePose, Person-in-WiFi 3D, AdaPose", 3)
    add_text_paragraph(
        doc,
        "DensePose from WiFi mapped CSI to dense human body surface coordinates [8], Person-in-WiFi "
        "3D extended this to end-to-end multi-person 3D pose estimation [9], and AdaPose addressed "
        "the cross-site generalization problem that plagues learned WiFi models [10]. These systems "
        "show the information richness of CSI but also its central weakness: learned models are "
        "environment-sensitive, data-hungry, and hard to audit. Phantom Scan takes the complementary "
        "position - a deterministic, physics-based detector as the authority, with any learned "
        "component confined to an advisory sidecar that cannot alter the deterministic result [12].",
    )

    add_heading(doc, "2.3 Comparison of Existing Solutions", 2)
    add_table(
        doc,
        ["System", "Hardware", "Method", "Output", "Cost / Deployability"],
        [
            ["Wi-Vi [1]", "Custom multi-antenna radio", "Interference nulling of static clutter", "Through-wall motion / coarse gestures", "Research hardware, low deployability"],
            ["WiTrack / Vital-Radio [2], [3]", "Dedicated FMCW radio", "Time-of-flight and phase of body reflections", "3D track; respiration and heart rate", "Specialized wideband hardware"],
            ["CARM [4]", "Intel 5300 NIC", "CSI speed/activity model over amplitude dynamics", "Activity classification", "Discontinued NIC, offline processing"],
            ["SpotFi [5]", "Multi-antenna commodity APs", "Super-resolved AoA + ToF", "Decimeter 2D location", "Needs antenna arrays and dense APs"],
            ["ESP32 CSI sensing [7]", "ESP32 (single antenna)", "CSI capture on IoT hardware", "Presence / activity features", "Very low cost, high deployability"],
            ["DensePose / PiW-3D / AdaPose [8]-[10]", "Commodity WiFi + GPU training", "Deep learned CSI-to-pose mapping", "Dense or 3D human pose", "High training and generalization burden"],
            ["Phantom Scan [12], [15]", "2x ESP32-S3 + laptop", "Deterministic per-subcarrier turbulence + two-node balance fusion", "Gated live detection, 1-D position, distance, trend, honest state", "About $20 of sensing hardware, single-command stack"],
        ],
        widths=[1.35, 1.15, 1.6, 1.4, 1.0],
    )
    add_caption(doc, "Table 2.1: Comparison of representative WiFi/RF human-sensing systems and Phantom Scan.")
    add_text_paragraph(
        doc,
        "The comparison exposes the gap Phantom Scan targets. High-fidelity systems (SpotFi, "
        "DensePose-class models) demand hardware or training resources incompatible with low-cost "
        "field deployment; low-cost ESP32 work proves capture feasibility but rarely delivers an "
        "engineered end-to-end system with transport contracts, security, testing, and honest "
        "uncertainty presentation. Phantom Scan fills that gap: a fully implemented, test-covered, "
        "two-node ESP32-S3 pipeline whose live dashboard never claims more spatial certainty than "
        "the physics of two single-antenna receivers can support - an explicitly one-dimensional, "
        "gated, evidence-labeled detection [12], [15].",
    )
    return refs


# ---------------------------------------------------------------------------
# Chapter 3 - Methodology and Work Plan
# ---------------------------------------------------------------------------

def chapter_3(doc: Document) -> list[int]:
    refs = [11, 12, 13, 14, 16, 17, 18, 19, 21]
    add_heading(doc, "CHAPTER 3 - METHODOLOGY AND WORK PLAN", 1)

    add_heading(doc, "3.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter explains how Phantom Scan was developed from concept to working two-node "
        "system. The methodology had to coordinate four dissimilar engineering domains - embedded "
        "firmware in C, a TypeScript host runtime, a Python analysis toolchain, and a React "
        "frontend - while keeping every claim about sensing performance anchored to reproducible "
        "evidence. The chapter also presents the work plan aligned with the course milestone "
        "schedule and the tools and technologies used.",
    )

    add_heading(doc, "3.2 System Development Methodology", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan follows a hybrid iterative methodology that combines upfront architectural "
        "decision-making with Agile-style implementation cycles. Architectural boundaries were "
        "fixed early in design documents and a set of Architecture Decision Records (ADRs); for "
        "example, ADR-018 froze the binary CSI frame contract (magic number, 32-byte header, "
        "sequence and timestamp fields) that firmware and host both implement and test against "
        "[16]. Within those boundaries, functionality advanced through short cycles of "
        "implementation, automated testing, bench verification with real boards, and correction "
        "[13], [14].",
    )
    add_text_paragraph(
        doc,
        "Each cycle ended with a written verification artifact rather than an informal 'it works'. "
        "The repository accumulates these as dated reports: a software validation pass, a dashboard "
        "truth-model verification, and a combined hardware-session and test-matrix report [17]-[19]. "
        "This evidence-first discipline is itself a methodological choice: a sensing project "
        "can easily overstate its capability, so the process required that unmeasured quantities "
        "stay explicitly marked as pending instead of being implied as done [21].",
    )
    add_text_paragraph(
        doc,
        "A hybrid model was preferred over strict Waterfall because several key truths only emerged "
        "from implementation - for instance, that a single 'best subcarrier' scalar is useless for "
        "motion energy because its selection index jumps between frames, which forced the redesign "
        "of the detector around full per-subcarrier amplitude vectors. A purely informal process "
        "was equally unsuitable because the project needed auditable interfaces across four "
        "codebases maintained in one repository.",
    )

    add_heading(doc, "3.3 Requirement Gathering Techniques", 2)
    add_bullet(doc, "Literature analysis: the sensing method was derived from published CSI research (clutter suppression, CSI-dynamics motion models, two-receiver geometry) rather than invented ad hoc.")
    add_bullet(doc, "Repository and artifact analysis: existing code, ADRs, and test suites were treated as the authoritative statement of established requirements when work resumed between milestones.")
    add_bullet(doc, "Bench experimentation: live sessions with the two ESP32-S3 boards exposed real requirements such as firmware self-ping (CSI starves on quiet networks), UDP send rate-limiting (lwIP buffer exhaustion), and source pinning (both boards initially shipped with the same node identity).")
    add_bullet(doc, "Scenario-driven analysis: operator scenarios - empty room, one node unplugged, person walking the axis, spoofed packets - were converted directly into functional requirements and regression tests.")
    add_text_paragraph(
        doc,
        "These techniques suit a research-engineering project better than stakeholder interviews: "
        "the decisive requirements (no ghost targets, no fabricated fusion from one node, no silent "
        "identity confusion) were discovered by observing the system fail in specific ways and then "
        "encoding the corrected behavior as tests [18], [19].",
    )

    add_heading(doc, "3.4 Project Plan (Gantt Chart)", 2)
    add_table(
        doc,
        ["Phase", "Period (2026)", "Main Activities", "Milestone Deliverable"],
        [
            ["P1 Problem & background", "Jan - Feb", "Topic definition, CSI literature study, feasibility analysis", "Task 1: Chapter 1"],
            ["P2 Literature review", "Feb", "Comparative review of WiFi sensing systems, gap analysis", "Task 2: Chapter 2"],
            ["P3 Methodology & requirements", "Feb - Mar", "Methodology selection, requirement capture, planning", "Tasks 3-4: Chapters 3-4"],
            ["P4 System design", "Mar (due 25 Mar)", "Architecture, module interaction, data and UI design", "Task 5: Chapter 5"],
            ["P5 Implementation", "Mar - Apr (due 25 Apr)", "Firmware, host runtime, fusion detector, dashboard, security", "Chapter 6 + working system"],
            ["P6 Testing & evaluation", "May", "Test matrix runs, hardware sessions, calibration tooling", "Verification reports"],
            ["P7 Results & final report", "May - Jun (due 4 Jun)", "Results analysis, discussion, conclusions, unified report", "Chapters 7-8 + final document"],
        ],
        widths=[1.35, 1.35, 2.45, 1.35],
    )
    add_caption(doc, "Table 3.1: Gantt-style work plan aligned with the course milestone deadlines.")
    add_text_paragraph(
        doc,
        "The plan tracks the university task schedule but the engineering order intentionally "
        "overlaps phases: implementation started before the design chapter was finalized, because "
        "credible design documentation required knowing what the hardware could actually do, and "
        "the results chapter could only be written after verification artifacts existed.",
    )

    add_heading(doc, "3.5 Development of Tools and Technologies", 2)
    add_table(
        doc,
        ["Category", "Technology", "Role and Justification"],
        [
            ["Sensing nodes", "2x ESP32-S3 dev boards, ESP-IDF (C)", "Lowest-cost platform exposing per-subcarrier CSI with a supported driver API [11]; firmware implements capture, framing, self-ping, and telemetry"],
            ["Host runtime", "Node.js 20, TypeScript, Express, ws", "Single authoritative live path: UDP ingest on :5005, DSP loop, WebSocket publishing, auth and audit"],
            ["Frontend", "React 18, Vite, React Three Fiber (Three.js)", "Real-time radar-style 3D scene plus telemetry panels in the browser"],
            ["Shared contracts", "TypeScript + zod schemas (shared/)", "One source of truth for message types and geometry constants across server and client"],
            ["Analysis path", "Python 3.13, numpy/scipy, pytest", "Replay of recorded sessions, reference DSP, protocol parity tests, invariant guards"],
            ["Data formats", "Binary ADR-018 frames; JSONL sessions; CSV exports", "Compact live transport; replayable evidence; spreadsheet-friendly analysis [16]"],
            ["Testing", "node:test via tsx; pytest", "91 TypeScript and 82 Python automated tests in the current matrix [19]"],
            ["Dev tooling", "esptool/idf.py flashing, calibrate-threshold.ts, dev-full launcher", "Board provisioning, empty-room gate calibration, one-command development stack [12]"],
        ],
        widths=[1.0, 1.9, 3.6],
    )
    add_caption(doc, "Table 3.2: Tools and technologies used in the current implementation.")
    return refs


# ---------------------------------------------------------------------------
# Chapter 4 - System Specification
# ---------------------------------------------------------------------------

def chapter_4(doc: Document) -> list[int]:
    refs = [12, 16, 18, 19, 21]
    add_heading(doc, "CHAPTER 4 - SYSTEM SPECIFICATION", 1)

    add_heading(doc, "4.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter specifies what Phantom Scan must do and the quality conditions under which it "
        "must do it. Because the system is a live sensing pipeline rather than a transactional "
        "information system, its specification has two unusual properties. First, several "
        "functional requirements are negative: the system must refuse to display things (ghost "
        "targets, fabricated fusion, spoofed nodes) as firmly as it displays real detections. "
        "Second, every requirement listed here is grounded in the implemented system and traceable "
        "to concrete modules and tests [12], [19].",
    )

    add_heading(doc, "4.2 Functional Requirements", 2)
    add_table(
        doc,
        ["ID", "Functional Requirement", "Implemented By"],
        [
            ["FR1", "Each node shall capture WiFi CSI and stream binary frames (32-byte versioned header, sequence number, RSSI, device timestamps, raw I/Q payload) over UDP to the host [16].", "firmware csi_collector.c, stream_sender.c"],
            ["FR2", "Each node shall self-generate channel traffic (~50 Hz gateway ping) so CSI capture continues on otherwise quiet networks, and shall rate-limit transmission to 50 Hz.", "firmware csi_collector.c"],
            ["FR3", "The host shall be the sole owner of UDP port 5005 and shall parse and validate CSI frames (magic 0xC5110001), heartbeats (0xC51100A1), and firmware feature-state packets (0xC5110006).", "server/lib/udp-server.ts"],
            ["FR4", "The host shall pin each node identity to its source address and reject frames for a known node arriving from a foreign source, with rate-limited security logging.", "SourcePinningGuard in udp-server.ts"],
            ["FR5", "The host shall compute a per-node motion metric as the windowed per-subcarrier temporal standard deviation of CSI amplitude (default window 1500 ms).", "node-fusion.ts, websocket.ts"],
            ["FR6", "The system shall emit NO target when neither node's motion clears the calibrated gate (default 0.12): an empty room must stay empty on screen.", "fuseTwoNodeTarget empty-room gate"],
            ["FR7", "With both nodes live, the host shall fuse the two motion energies into a one-dimensional position on the node axis, with distance-to-nearest-node and per-node approaching/receding/stable trends.", "node-fusion.ts, websocket.ts"],
            ["FR8", "With one node live, the system shall enter an explicitly labeled degraded single-node state and shall not fabricate fused output [18].", "target-state.ts (node_mode)"],
            ["FR9", "Targets shall become 'stale' 1.5 s after the last live sample and shall be hard-cleared after 5 s; disconnects clear all client state.", "target-state.ts, use-websocket.ts"],
            ["FR10", "The host shall publish live state (radial target, truthful target state, per-node telemetry, spectra, vitals, firmware feature states) over an authenticated WebSocket.", "websocket.ts, shared/schema.ts"],
            ["FR11", "The dashboard shall render node beacons, the fused target, motion vectors, spectral views, and Board-DSP cards, gated by presentation-honesty helpers.", "client/src/components/dashboard/"],
            ["FR12", "Operators shall authenticate before accessing the dashboard or privileged actions; security-relevant events shall be audit-logged.", "server/auth/, server/audit/"],
            ["FR13", "The system shall support session recording (JSONL/CSV) and deterministic replay for offline analysis and testing.", "recording-export.ts, phantom/ package"],
            ["FR14", "The system shall provide an empty-room calibration tool that derives the motion gate from a recorded baseline (mean + k*sigma).", "scripts/calibrate-threshold.ts"],
        ],
        widths=[0.5, 4.0, 2.0],
    )
    add_caption(doc, "Table 4.1: Functional requirements traced to implementing modules.")

    add_heading(doc, "4.3 Non-Functional Requirements", 2)
    add_table(
        doc,
        ["Category", "Requirement and Current Evidence"],
        [
            ["Performance", "Host processing loop runs at 50 ms (~20 FPS); per-node ingest of >=20 packets/s is the preflight minimum, and the recorded hardware session sustained ~40 packets/s aggregate from two boards [19], [21]."],
            ["Reliability", "Silent or unplugged nodes decay to zero motion within the 1500 ms window; stale targets clear within 5 s; the firmware sender backs off on buffer exhaustion instead of crashing."],
            ["Security", "WebSocket connections are token/cookie authenticated; UDP source pinning rejected ~640 spoofed packets in a live drill while real streaming continued [19]; audit events are persisted as JSONL."],
            ["Usability", "The operator can always distinguish live, degraded, stale, and empty states; caveat labels state that the live position is an on-axis projection."],
            ["Honesty / Integrity", "Synthetic, replayed, or single-node data can never be presented as fused live truth; measurement protocols forbid graduating headline metrics from non-live runs [21]."],
            ["Maintainability", "Strict layer boundaries (firmware / ingest / fusion / presentation / client), shared zod schemas as the single contract, and 173 automated tests across two languages [19]."],
            ["Portability", "Host stack runs on Windows and Ubuntu; firmware builds under ESP-IDF with documented provisioning for both nodes [12]."],
            ["Configurability", "Detection parameters are environment-tunable (PHANTOM_MOTION_THRESHOLD, PHANTOM_MOTION_WINDOW_MS, PHANTOM_BALANCE_CONTRAST, PHANTOM_TREND_DEADBAND_MPS) without code changes."],
        ],
        widths=[1.2, 5.3],
    )
    add_caption(doc, "Table 4.2: Non-functional requirements with current evidence.")
    return refs


# ---------------------------------------------------------------------------
# Chapter 5 - System Design
# ---------------------------------------------------------------------------

DATAFLOW_DIAGRAM = r"""
  ESP32-S3 Node 1 (node_id=1)            ESP32-S3 Node 2 (node_id=2)
  csi_collector.c -> stream_sender.c     csi_collector.c -> stream_sender.c
        |  ADR-018 CSI frames (0xC5110001, 50 Hz cap)  |
        |  heartbeats (0xC51100A1, 1 Hz)               |
        |  feature-state (0xC5110006, 1 Hz)            |
        +----------------------+------------------------+
                               v
                    UDP :5005  (single owner)
               server/lib/udp-server.ts
               - magic/type validation, ADR-018 parse
               - SourcePinningGuard (anti-spoofing)
               - per-subcarrier amplitudes (<=64)
                               v
               server/lib/websocket.ts  (50 ms loop)
               - per-node 1500 ms amplitude window
               - computeNodeMotionFromMatrix()  [node-fusion.ts]
               - fuseTwoNodeTarget(): gate 0.12, balance p=2.0
               - target-state.ts truth machine (none/stale/
                 idle/moving/degraded), trends, distances
                               v
                    WebSocket /ws (authenticated)
               radialTarget | targetState | nodes |
               nodeFeatures | heatmap | doppler | vitals
                               v
               client/src (React + Three.js dashboard)
               RadialScene, distance meter, Signal
               Signature/Doppler views, Board-DSP card, identity card
"""


def chapter_5(doc: Document) -> list[int]:
    refs = [12, 15, 16]
    add_heading(doc, "CHAPTER 5 - SYSTEM DESIGN", 1)

    add_heading(doc, "5.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter translates the specification into the architecture that the repository "
        "implements. Phantom Scan is an AI-and-signal-processing project rather than a "
        "database-centric information system, so - following the AI-project variant of the course "
        "design template - the class-diagram and database-design sections are realized as a module "
        "interaction design and a data/pipeline design respectively. Every element named here maps "
        "to a real file in the repository.",
    )

    add_heading(doc, "5.2 System Architecture Design", 2)
    add_text_paragraph(
        doc,
        "The architecture is a layered pipeline with strict single-direction data flow: firmware "
        "produces measurements, the host ingest validates and enriches them, the fusion core "
        "reduces them to target truth, and the presentation layer renders that truth. Security "
        "cross-cuts the stack at the two trust boundaries: the UDP ingest (source pinning) and the "
        "operator interface (authentication and audit) [12].",
    )
    add_table(
        doc,
        ["Layer", "Responsibility", "Representative Modules"],
        [
            ["Presentation", "Operator dashboard, truthful rendering, review routes", "client/src/pages/dashboard.tsx, components/dashboard/*"],
            ["Application", "Ingest, windowing, fusion, state machine, publication", "server/lib/udp-server.ts, websocket.ts, node-fusion.ts, target-state.ts"],
            ["Data", "Recording, replay, session store, exports", "server/lib/recording-export.ts, session-store.ts, phantom/recording.py"],
            ["Integration", "UDP :5005 in, WebSocket /ws out, optional AI sidecar on 127.0.0.1:5006", "udp-server.ts, websocket.ts, scripts/ai_inference.py"],
            ["Security", "Operator auth, WS auth, source pinning, audit logging", "server/auth/, SourcePinningGuard, server/audit/logger.ts"],
        ],
        widths=[1.1, 2.4, 3.0],
    )
    add_caption(doc, "Table 5.1: Layered architecture and implementing modules.")
    add_text_paragraph(
        doc,
        "Figure 5.1 shows the end-to-end data pipeline in the AI-project form required by the "
        "design template: acquisition, preprocessing, deterministic inference, and presentation.",
    )
    add_code_block(doc, DATAFLOW_DIAGRAM.strip("\n"), size=8)
    add_caption(doc, "Figure 5.1: End-to-end data pipeline from firmware capture to dashboard rendering.")

    add_heading(doc, "5.3 Class Diagram and Module Interaction Design", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan is built from cooperating modules with typed contracts rather than a deep "
        "object-oriented class hierarchy, so its structural design is best expressed as the module "
        "interaction model of Table 5.2 plus the small number of genuine classes that hold runtime "
        "state. The genuine classes on the live path are SignalProcessingServer (the orchestrator "
        "owning the 50 ms loop, per-node windows, and broadcast fan-out), SourcePinningGuard "
        "(node-to-source identity binding), and the legacy DSP helpers (BackgroundSubtractor, "
        "MotionGate, DopplerComputer, TrackingProcessor). Pure functions carry the detection "
        "mathematics so they can be unit-tested exhaustively: computeNodeMotionFromMatrix, "
        "fuseTwoNodeTarget, biasBalanceTowardNearestNode, and computeNodeTrends in "
        "server/lib/node-fusion.ts [15].",
    )
    add_table(
        doc,
        ["Module / Entity", "Interacts With", "Contract"],
        [
            ["csi_collector.c (firmware)", "stream_sender.c", "csi_serialize_frame() writes the ADR-018 32-byte header + raw I/Q [16]"],
            ["stream_sender.c (firmware)", "udp-server.ts", "UDP datagrams to configured host:5005; 32-slot queue, ENOMEM backoff"],
            ["udp-server.ts", "websocket.ts", "CSISample { timestamp, nodeId, rssi, h1, h2, amplitudes[] } via ingestSample()"],
            ["node-fusion.ts", "websocket.ts", "NodeMotion { mean, absStd, motion }; FusedTarget { x, z, balance, distToNearestNodeM } or null"],
            ["target-state.ts", "websocket.ts, client", "TargetState { state, node_mode, target_visible, position_confident, bearing, range, staleness }"],
            ["shared/schema.ts", "server + client", "zod schemas for every WS message type; NODE_ANCHORS geometry constants"],
            ["use-websocket.ts (client)", "dashboard components", "Typed live state with 5 s client-side staleness watchdog"],
            ["phantom/ package", "recorded sessions", "JSONL session_header / csi_frame / heartbeat / derived_frame / session_footer records"],
        ],
        widths=[1.7, 1.5, 3.3],
    )
    add_caption(doc, "Table 5.2: Module interaction contracts (in place of a conventional class diagram).")

    add_heading(doc, "5.4 Database and Data Design", 2)
    add_text_paragraph(
        doc,
        "The system deliberately uses file-based persistence instead of a database server: a "
        "prototype sensing pipeline gains auditability from human-inspectable artifacts and loses "
        "nothing, since live state is inherently in-memory and transient. The data design therefore "
        "has three tiers: the wire format, the in-memory runtime model, and the persisted evidence "
        "formats.",
    )
    add_table(
        doc,
        ["Data Artifact", "Structure", "Persistence"],
        [
            ["ADR-018 CSI frame", "magic u32 | schema u8 | node_id u8 | antennas u8 | subcarriers u16 | freq_mhz u32 | seq u32 | rssi i8 | noise i8 | channel u8 | device_ts_us u64 | device_ts_ms u32 | raw int8 I/Q pairs [16]", "Transient (UDP)"],
            ["Feature-state frame", "magic 0xC5110006 | node_id | motion f32 | presence f32 | resp_bpm f32 | resp_conf f32 | hr_bpm f32 | hr_conf f32 (firmware DSP, 1 Hz)", "Transient (UDP)"],
            ["Runtime target model", "RadialTarget {x, z, r, theta, speed, confidence, balance, distanceCm}; TargetState truth record; SensorNode {node_id, x, z, motion, distanceM, trend, rssi}", "In-memory"],
            ["JSONL session", "One JSON record per line: session_header, csi_frame, heartbeat, derived_frame, session_footer", "data/sessions/*.jsonl"],
            ["CSV recording/export", "timestamp, subcarrier_index, h1_re, h1_im, h2_re, h2_im, rssi (plus positional-fidelity export columns)", "recordings/*.csv, exports"],
            ["Operator & audit data", "Local operator record (scrypt-hashed credential); append-only JSONL audit trail", "data/operator.json, data/audit/"],
        ],
        widths=[1.5, 3.8, 1.2],
    )
    add_caption(doc, "Table 5.3: Data design across wire, runtime, and persisted tiers.")
    add_text_paragraph(
        doc,
        "The geometric data model is fixed in shared/schema.ts: node anchors N1 = (-1.5, 0) and "
        "N2 = (+1.5, 0) meters, i.e. a 3 m baseline with the origin at the midpoint. Both server "
        "fusion and client rendering import these constants, so the display can never disagree "
        "with the mathematics about where the nodes are [12].",
    )

    add_heading(doc, "5.5 User Interface (UI) Design", 2)
    add_text_paragraph(
        doc,
        "The dashboard is designed as an operator console. The central element is a Three.js "
        "radar-style scene (RadialScene.tsx): a polar grid with cardinal directions, one glowing "
        "beacon per ESP32 node (node 1 cyan, node 2 pink) whose ripples respond to that node's "
        "live motion metric, the line between the nodes as the valid localization axis, and the "
        "fused target rendered on that axis with connector lines to each node and a travel-direction "
        "arrow. An explicit on-screen caveat labels the position as an axis projection so the "
        "operator is never led to read 2D precision into a 1-D estimate.",
    )
    add_bullet(doc, "Radar scene: node beacons, axis line, fused target marker, motion vector, wall plane at the estimated wall distance.")
    add_bullet(doc, "Distance meter: range to nearest node, wall distance, and compass bearing readouts.")
    add_bullet(doc, "Target identity card: human/mechanical classification with probability and per-node approaching/receding trends.")
    add_bullet(doc, "Spectral panels: Signal Signature (temporal MUSIC) spectrum and subcarrier heatmap, Doppler spectrogram (replay/synthetic-capable analysis views).")
    add_bullet(doc, "Board DSP card: the firmware's own 1 Hz presence/motion/respiration/heart-rate estimates, shown verbatim and independent of host fusion.")
    add_bullet(doc, "Vitals monitor, metrics panel, scan controller, and top bar with connection and recording status.")
    add_bullet(doc, "Supporting routes: login, history, activity, and report pages.")
    add_text_paragraph(
        doc,
        "The UI's defining design rule is state-honest rendering: every component consults the "
        "shared presentation helpers (canPresentLiveTargetPosition, canPresentTruthfulTarget, "
        "getLivePositionCaveat) before drawing, so degraded, stale, or gated states change what is "
        "drawn, not just a status label.",
    )

    add_heading(doc, "5.6 Summary", 2)
    add_text_paragraph(
        doc,
        "The design achieves the project's goals through strict layering, typed contracts, and "
        "pure-function detection mathematics. Efficiency comes from the compact binary wire format "
        "and the fixed-rate processing loop; maintainability from the single shared schema and the "
        "unit-testable fusion core; security from the two guarded trust boundaries; and research "
        "credibility from a data design in which every live claim can be traced back through the "
        "pipeline to raw recorded frames [12], [15].",
    )
    return refs


# ---------------------------------------------------------------------------
# Chapter 6 - System Implementation
# ---------------------------------------------------------------------------

MOTION_EXCERPT = """// server/lib/node-fusion.ts - per-subcarrier turbulence (RuView-faithful)
export function computeNodeMotionFromMatrix(frames: number[][]): NodeMotion {
  const k = Math.min(...usable.map((f) => f.length));   // common subcarrier count
  let stdSum = 0;
  for (let j = 0; j < k; j++) {                          // temporal std of each
    let m = 0;                                           // subcarrier j across
    for (const f of usable) m += f[j];                   // the 1500 ms window
    m /= usable.length;
    let acc = 0;
    for (const f of usable) { const d = f[j] - m; acc += d * d; }
    stdSum += Math.sqrt(acc / usable.length);
  }
  const absStd = stdSum / k;                             // raw motion energy
  // base = mean frame amplitude (normalizer), then:
  const motion = Math.min(1.0, (absStd / base) * MOTION_SATURATION_SCALE); // x4
  return { mean: base, absStd, motion };
}"""

FUSION_EXCERPT = """// server/lib/node-fusion.ts - two-node balance fusion with empty-room gate
export function fuseTwoNodeTarget(input: FuseInput): FusedTarget | null {
  const threshold = input.motionThreshold ?? DEFAULT_MOTION_THRESHOLD; // 0.12
  const present = Math.max(input.motion1, input.motion2) >= threshold
                  && r1 + r2 > EPS;
  if (!present) return null;              // empty room => NO target (no ghost)

  const p = input.contrastExponent ?? BALANCE_CONTRAST_EXPONENT;       // 2.0
  const balance = r2**p / (r1**p + r2**p);        // 0 -> node1 ... 1 -> node2
  const biasedBalance = biasBalanceTowardNearestNode(balance);         // 0.72
  const x = n1.x + (n2.x - n1.x) * biasedBalance; // 1-D position on the axis
  const z = n1.z + (n2.z - n1.z) * biasedBalance;
  return { x, z, balance, distToNearestNodeM: Math.min(d1, d2) };
}"""


def chapter_6(doc: Document) -> list[int]:
    refs = [12, 15, 16, 18, 19, 21]
    add_heading(doc, "CHAPTER 6 - SYSTEM IMPLEMENTATION", 1)

    add_heading(doc, "6.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter documents how the design of Chapter 5 is realized in code, with emphasis on "
        "the question at the heart of the project: how the system detects a moving human. Every "
        "file, function, constant, and threshold cited here exists in the current repository and "
        "is reproduced in full in the Appendices of the final report [12].",
    )

    add_heading(doc, "6.2 Implementation Overview", 2)
    add_table(
        doc,
        ["Area", "Technology", "Key Files"],
        [
            ["Firmware", "ESP-IDF / C on ESP32-S3", "firmware/esp32-csi-node/main/: main.c, csi_collector.c, stream_sender.c, nvs_config.c, edge_processing.c"],
            ["Live host", "Node.js + TypeScript", "server/lib/: udp-server.ts, websocket.ts, node-fusion.ts, target-state.ts, signal-processing helpers"],
            ["Contracts", "TypeScript + zod", "shared/schema.ts, shared/bearing.ts, shared/target-presentation.ts"],
            ["Dashboard", "React + Three.js (R3F)", "client/src/pages/dashboard.tsx, components/dashboard/RadialScene.tsx and sibling panels"],
            ["Python path", "Python 3.13", "phantom/: protocol.py, dsp.py, runtime.py, ingest.py, recording.py, api.py"],
            ["Tooling", "TS + Python scripts", "scripts/calibrate-threshold.ts, replay/capture utilities, session reporter"],
        ],
        widths=[0.9, 1.5, 4.1],
    )
    add_caption(doc, "Table 6.1: Implementation areas and their key source files.")

    add_heading(doc, "6.3 Implementation Details", 2)

    add_heading(doc, "6.3.1 Firmware: CSI Capture and Transport", 3)
    add_text_paragraph(
        doc,
        "On boot, main.c loads the node configuration from NVS flash and caches the node_id before "
        "WiFi starts - a deliberate ordering that prevents the two boards from becoming "
        "indistinguishable if provisioning is read late. The board joins the configured 2.4 GHz "
        "network as a station with power-save disabled, then csi_collector.c enables promiscuous "
        "mode with management+data filtering and registers the WiFi driver's CSI callback with "
        "legacy-LTF, HT-LTF, and STBC capture enabled. Because CSI is only produced when frames "
        "are received, the collector starts a self-ping task that pings the gateway every 20 ms "
        "(~50 Hz), guaranteeing a steady CSI supply even on an otherwise idle network.",
    )
    add_text_paragraph(
        doc,
        "Each CSI callback serializes the channel estimate through csi_serialize_frame(), which "
        "writes the exact ADR-018 contract: magic 0xC5110001, schema version, node_id, antenna "
        "count, subcarrier count, channel frequency, monotonically increasing sequence number, "
        "RSSI, noise floor, channel, and dual device timestamps (microseconds and milliseconds), "
        "followed by the raw int8 I/Q pairs [16]. Transmission is rate-limited to 50 Hz and handed "
        "to stream_sender.c, which owns a UDP socket to the configured host, a 32-slot FreeRTOS "
        "queue with a dedicated sender task, and an ENOMEM backoff so lwIP buffer exhaustion "
        "degrades throughput instead of crashing the node. A 1 Hz heartbeat (magic 0xC51100A1) "
        "reports capture and drop statistics, and edge_processing.c emits an independent 1 Hz "
        "feature-state packet (magic 0xC5110006) carrying the board's own motion, presence, "
        "respiration, and heart-rate estimates.",
    )

    add_heading(doc, "6.3.2 Host Ingest: Parsing and Source Authenticity", 3)
    add_text_paragraph(
        doc,
        "server/lib/udp-server.ts binds a single UDP socket on port 5005 - deliberately without "
        "address reuse, so a second process attempting to bind fails loudly rather than silently "
        "splitting the packet stream. Incoming datagrams are classified by magic number; CSI frames "
        "are parsed by parseCsiPacket(), which supports both the 32-byte ADR-018 header and a "
        "20-byte legacy header. For each frame, the parser computes the per-subcarrier amplitude "
        "vector amp[j] = sqrt(re^2 + im^2) from the int8 I/Q pairs (capped at 64 subcarriers) - "
        "this vector, not any single scalar, is what feeds the motion detector.",
    )
    add_text_paragraph(
        doc,
        "A SourcePinningGuard instance pins each node_id to the first source address it is seen "
        "from. Frames claiming a pinned node_id but arriving from a foreign source are rejected and "
        "logged as rate-limited security events; a 10-second staleness window allows legitimate "
        "rebinding after a board reboot or DHCP renumbering. In the recorded live drill, a local "
        "spoofer injecting ~640 packets for both node identities was fully rejected while the real "
        "boards continued streaming [19].",
    )

    add_heading(doc, "6.3.3 How the System Detects a Moving Human", 3)
    add_text_paragraph(
        doc,
        "Detection rests on one physical effect: a moving human body changes the multipath channel, "
        "so the amplitude of each OFDM subcarrier fluctuates over time, while an empty room leaves "
        "them nearly constant. The implementation measures this directly. For each node, "
        "websocket.ts maintains a timestamp-bounded window (default 1500 ms, env "
        "PHANTOM_MOTION_WINDOW_MS) of per-subcarrier amplitude frames. Every processing tick, "
        "computeNodeMotionFromMatrix() computes the temporal standard deviation of each subcarrier "
        "across the window and averages them:",
    )
    add_code_block(doc, MOTION_EXCERPT)
    add_caption(doc, "Listing 6.1: Core of the per-subcarrier turbulence detector (abridged from node-fusion.ts).")
    add_text_paragraph(
        doc,
        "Two outputs matter. absStd is the raw, unsaturated motion energy used for localization; "
        "motion is a normalized 0..1 display value, absStd divided by the mean amplitude and "
        "scaled by 4 (MOTION_SATURATION_SCALE). The per-subcarrier formulation is essential: an "
        "earlier single-'best subcarrier' scalar was discarded because its selection index jumps "
        "between frames, making its variance mostly noise rather than human motion [15]. The "
        "window is evicted by timestamp on both read and write, so a node that stops streaming "
        "decays to zero motion within 1.5 s instead of freezing at its last value.",
    )
    add_text_paragraph(
        doc,
        "Presence is then decided by an explicit empty-room gate: a fused target exists only if "
        "max(motion1, motion2) >= PHANTOM_MOTION_THRESHOLD (default 0.12). Below the gate the "
        "fusion returns null and the dashboard shows an empty scene - not a centered ghost. The "
        "threshold is documented in-code as a placeholder to be calibrated per room: "
        "scripts/calibrate-threshold.ts records an empty-room baseline through the exact "
        "production pipeline and reports mean + 3/4/5-sigma candidates, and the negative-control "
        "requirement (a fan or curtain must be rejected while a still, breathing person is still "
        "detected) is written into the measurement protocol [21].",
    )

    add_heading(doc, "6.3.4 Two-Node Balance Fusion and 1-D Localization", 3)
    add_text_paragraph(
        doc,
        "Localization uses the RuView two-receiver balance geometry [15]. The person perturbs the "
        "channel seen by the nearer node more strongly, so the ratio of the two raw motion "
        "energies encodes position along the line between the nodes:",
    )
    add_code_block(doc, FUSION_EXCERPT)
    add_caption(doc, "Listing 6.2: Balance fusion with empty-room gate (abridged from node-fusion.ts).")
    add_text_paragraph(
        doc,
        "Because both nodes see the same person, r1 and r2 are correlated and a plain linear ratio "
        "compresses toward 0.5, gluing the display dot to the midpoint. The implementation therefore "
        "sharpens contrast before the ratio - balance = r2^p / (r1^p + r2^p) with p = 2.0 "
        "(PHANTOM_BALANCE_CONTRAST) - and applies a display-only endpoint bias (exponent 0.72) "
        "that pulls the projected position toward the nearest node while leaving 0, 0.5, and 1 "
        "fixed. The result is interpolated between the shared anchors N1 = (-1.5, 0) and "
        "N2 = (+1.5, 0), yielding the on-axis position, the balance value, and the distance to the "
        "nearest node in meters. Per-node distances and signed axis velocity feed "
        "computeNodeTrends(), which labels each node approaching/receding/stable with a 0.05 m/s "
        "deadband and hysteresis so the label does not flicker at rest.",
    )

    add_heading(doc, "6.3.5 Orchestration, Truth Model, and Publication", 3)
    add_text_paragraph(
        doc,
        "SignalProcessingServer in websocket.ts runs the pipeline on a 50 ms interval (~20 FPS). "
        "Each tick it determines node liveness (a node is active if a frame arrived within 1500 "
        "ms), resolves the mode - fused_two_node when both nodes are live, single_node otherwise - "
        "recomputes both node motions, runs the fusion, and updates a single per-tick fused "
        "snapshot that every outgoing message reads, so the radar dot and the node labels can "
        "never disagree. In fused mode the balance target replaces the legacy single-node "
        "estimate; if both nodes are live but sub-threshold, no target is emitted and residual "
        "display artifacts are cleared. Stale queued samples older than 1.5 s are dropped rather "
        "than replayed, preventing ghost motion after a pause.",
    )
    add_text_paragraph(
        doc,
        "server/lib/target-state.ts reduces the runtime picture to an honest state machine "
        "published as targetState: none, stale, idle, moving, or degraded, plus node_mode, "
        "target_visible, and position_confident (confidence >= 0.45). Targets hold for 1.5 s "
        "after data loss, then clear at 5 s. Alongside targetState, the WebSocket layer broadcasts "
        "radialTarget (position/velocity/balance), nodes (per-node beacons with distanceM, trend, "
        "motion, RSSI), nodeFeatures (the firmware's own DSP verbatim), and the analysis streams "
        "(heatmap, doppler, vitals, point cloud). All WebSocket connections are authenticated via "
        "the operator's JWT/cookie session before any data flows [18].",
    )

    add_heading(doc, "6.3.6 Dashboard Rendering", 3)
    add_text_paragraph(
        doc,
        "client/src/hooks/use-websocket.ts maintains the typed live state with a 5 s client-side "
        "staleness watchdog that wipes the scene if the server goes silent. dashboard.tsx routes "
        "every render decision through shared/target-presentation.ts helpers, so the same honesty "
        "rules bind both server and client. RadialScene.tsx renders the polar grid, per-node "
        "ESPBeacon markers whose glow and ripple frequency are driven by each node's live motion "
        "value, the node-axis line, the fused target with connector lines to both nodes, a travel "
        "arrow pointing along the axis toward the approached node, and an axis-projection caveat "
        "label. Before any node data arrives the scene shows only a neutral origin beacon - there "
        "is no synthetic default target anywhere in the client [18].",
    )

    add_heading(doc, "6.3.7 Authentication, Audit, and Persistence", 3)
    add_text_paragraph(
        doc,
        "server/auth/ implements a local operator account with scrypt-hashed credentials, "
        "first-operator bootstrap seeding, HTTP session auth for the API, and WebSocket handshake "
        "authentication. server/audit/logger.ts appends security-relevant events (including source "
        "pinning rejections) to a JSONL audit trail. Persistence is file-based by design: JSONL "
        "session recordings, CSV exports with the positional-fidelity column contract, and the "
        "operator record under data/.",
    )

    add_heading(doc, "6.3.8 Python Replay and Tooling Path", 3)
    add_text_paragraph(
        doc,
        "The phantom/ package mirrors the wire protocol (protocol.py parses the same ADR-018 "
        "bytes, verified byte-for-byte against committed fixtures shared with the TypeScript "
        "tests), provides reference DSP (clutter suppression, Hampel filtering, respiration "
        "band-pass, motion energy, dual-node on-axis position), and offers a runtime with live and "
        "replay modes. In normal operation it is a tooling and test path only: the repository "
        "documents that the TypeScript dashboard is the sole owner of UDP :5005, and the Python "
        "live authority stays gated behind PHANTOM_USE_AUTHORITY=1 to avoid port collisions [12].",
    )

    add_heading(doc, "6.4 Component Integration and Workflow", 2)
    add_text_paragraph(
        doc,
        "The integrated live workflow is: both boards boot and pin their identities; frames arrive "
        "on :5005 and pass the source guard; per-node windows fill within 1.5 s; when a person "
        "moves, per-subcarrier turbulence rises on both nodes, the gate opens, and the fused "
        "target appears on the axis with distance and trend readouts; when the person leaves, "
        "motion decays below the gate and the scene empties; if a node is unplugged mid-session, "
        "the mode drops to single_node and the UI relabels itself degraded within 1.5 s. The "
        "development stack (npm run dev) launches the full chain with one command, and replay "
        "workflows drive the same ingest path from recorded JSONL sessions [12].",
    )

    add_heading(doc, "6.5 Implementation Testing Support", 2)
    add_text_paragraph(
        doc,
        "The implementation is guarded by 91 TypeScript tests (node:test via tsx) and 82 Python "
        "tests (pytest) covering protocol parity against committed binary fixtures, fusion "
        "mathematics (midpoint balance, empty-room null, contrast exponent), the target-state "
        "machine, source-pinning scenarios including reboot and DHCP renumbering, recording "
        "export columns, pose anchoring, and auth seeding. Cross-language invariants are enforced "
        "in tests/test_invariants.py, including the scope guard that fails if flight-control "
        "concepts re-enter the runtime and the firewall test proving AI perturbations cannot "
        "change the deterministic human gate [19]. Chapter 7 presents the full matrix.",
    )

    add_heading(doc, "6.6 Summary", 2)
    add_text_paragraph(
        doc,
        "The implementation converts a physical effect - motion-induced multipath perturbation - "
        "into a gated, fused, honestly-presented live detection through a chain of small, "
        "individually tested stages: promiscuous CSI capture with self-ping, a versioned binary "
        "contract, pinned ingest, windowed per-subcarrier turbulence, thresholded balance fusion, "
        "a truth-state machine, and state-honest rendering. Its most distinctive engineering "
        "property is that honesty is implemented as code paths and tests, not as documentation "
        "promises [18], [19].",
    )
    return refs


# ---------------------------------------------------------------------------
# Chapter 7 - Results and Discussion
# ---------------------------------------------------------------------------

def chapter_7(doc: Document) -> list[int]:
    refs = [12, 15, 17, 18, 19, 20, 21, 22, 23]
    add_heading(doc, "CHAPTER 7 - RESULTS AND DISCUSSION", 1)

    add_heading(doc, "7.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter evaluates Phantom Scan against its objectives using the evidence that "
        "actually exists: automated test results, recorded datasets, dated verification reports, "
        "and a real two-node hardware session. The project enforces a strict honesty rule - "
        "synthetic, replayed, or single-node runs cannot graduate a headline sensing metric [21] - "
        "and this chapter follows the same rule: measured results are presented as measured, and "
        "pending results are presented as pending.",
    )

    add_heading(doc, "7.2 Data Collection and Research", 2)
    add_text_paragraph(
        doc,
        "Evaluation data spans three tiers. First, committed protocol fixtures (binary ADR-018 and "
        "heartbeat frames) that both language stacks must parse identically. Second, recorded CSI "
        "datasets: 24 CSV recordings (~1.9 MB) from February-March 2026 with the two-node complex "
        "CSI schema (timestamp, subcarrier_index, h1_re, h1_im, h2_re, h2_im, rssi), and "
        "approximately 90 session files (~194 MB, CSV and JSONL) collected between March and June "
        "2026, including live ESP32 captures and replay sessions. Third, dated verification "
        "documents recording what was run, on what hardware, with what outcome [17]-[19].",
    )
    add_text_paragraph(
        doc,
        "The measurement methodology is defined in two protocol documents: MEASUREMENT_PLAN.md "
        "specifies how headline metrics (CSI rate, midpoint localization, respiration/heart-rate "
        "MAE against reference sensors) must be captured [21], and REAL_TEST_REPORT.md defines an "
        "eight-stage positional-fidelity campaign - preflight packet rates, empty-room calibration "
        "and soak, negative controls (fan, curtain, air conditioning), static dwells, on-axis walk "
        "accuracy against tape-marked ground truth, trend validation, off-axis projection "
        "characterization, and robustness confounds [20].",
    )

    add_heading(doc, "7.3 System Testing and User Feedback", 2)
    add_heading(doc, "7.3.1 Functional Testing (Automated)", 3)
    add_text_paragraph(
        doc,
        "The current test matrix passes in full: 91 TypeScript tests, 82 Python tests passed with "
        "1 hardware-conditional skip, a clean TypeScript typecheck, and a clean production build "
        "[19]. Table 7.1 summarizes what the suites actually verify.",
    )
    add_table(
        doc,
        ["Suite", "What It Verifies"],
        [
            ["udp-server.test.ts", "ADR-018 32-byte frame parsing with committed-fixture parity; heartbeat exclusion; source-pinning accept/reject scenarios (foreign source, board reboot, DHCP renumber); feature-state (0xC5110006) decoding"],
            ["node-fusion.test.ts", "Balance localization (r1>>r2 places target at node 1; equal energies at midpoint); empty-room returns NO target; per-subcarrier matrix motion; contrast exponent; trend hysteresis and distance bookkeeping"],
            ["target-state.test.ts", "Freshness windows, degraded single-node labeling, fused-mode resolution, stale demotion and hard clear, low-confidence handling"],
            ["target-presentation / target-spatial tests", "Honesty caveats, no volumetric rendering of truthful live targets, human-readable spatial summaries"],
            ["recording-export / join-groundtruth tests", "CSV export column contract, gate-closed suppression, ground-truth enrichment"],
            ["bearing / pose-anchor / auth tests", "Compass conventions, skeleton anchoring regressions, scrypt operator seeding and audit ordering"],
            ["pytest: protocol, pipeline, runtime", "Byte-level protocol parity with TS; Hampel/DWT/DBSCAN/Kalman pipeline over real recordings; replay roundtrip; spoof rejection; degraded/fused transitions"],
            ["pytest: test_invariants.py", "Dual-node midpoint invariant; AI firewall (perturbed AI input cannot change the deterministic gate); no upstream hardware controls from the dashboard; UAV/flight-control scope guard"],
        ],
        widths=[1.9, 4.6],
    )
    add_caption(doc, "Table 7.1: Automated test coverage in the passing matrix (91 TS + 82 Python) [19].")

    add_heading(doc, "7.3.2 Live Hardware Session (Non-Functional Evidence)", 3)
    add_text_paragraph(
        doc,
        "The strongest live evidence is the July 8, 2026 hardware session [19]: two ESP32-S3 "
        "boards on the same 2.4 GHz network, provisioned as node 1 (COM5, 192.168.1.133) and "
        "node 2 (COM6, 192.168.1.238), with on-device confirmation that node identity is cached "
        "before WiFi start. The live ingest sustained approximately 200 packets per 5-second "
        "interval (~40 packets/s aggregate) with RSSI between -23 and -38 dBm and firmware-reported "
        "yield of 41-43 packets/s per node - comfortably above the 20 packets/s per-node preflight "
        "minimum. During the same session, a deliberate spoofing drill injected ~640 packets "
        "claiming both node identities from a foreign source; the source-pinning guard rejected "
        "all of them with only four rate-limited security log lines while the real streams "
        "continued uninterrupted.",
    )
    add_text_paragraph(
        doc,
        "Earlier verification passes complement this: the June 29 target-verification confirmed "
        "the dashboard no longer fabricates point-cloud data or fallback avatars when live data is "
        "absent, that motion-gate idle cannot keep a synthetic target alive, and that single-node "
        "detections are labeled degraded [18]; the July 1 software pass recorded the replay CLI "
        "and build chain working end-to-end [17].",
    )

    add_heading(doc, "7.3.3 Measured Versus Pending Results", 3)
    add_table(
        doc,
        ["Metric", "Status", "Evidence / Blocking Condition"],
        [
            ["Software correctness (parsers, fusion math, state machine)", "MEASURED - PASS", "91 TS + 82 Python tests green [19]"],
            ["Two-node live ingest rate and RSSI envelope", "MEASURED", "~40 pkt/s aggregate, RSSI -23..-38 dBm, yield 41-43 pps/node [19]"],
            ["Spoofing resistance of live ingest", "MEASURED - PASS", "~640/640 spoofed packets rejected in live drill [19]"],
            ["Dashboard truthfulness (no ghosts, degraded labeling)", "MEASURED - PASS", "Behavioral verification + regression tests [18]"],
            ["Detection rate / false-positive rate per room", "[TO BE MEASURED]", "Requires empty-room calibration + negative-control campaign [20], [21]"],
            ["On-axis localization error vs tape-marked ground truth", "[TO BE MEASURED]", "Stage S4 of the positional-fidelity campaign [20]"],
            ["Respiration / heart-rate MAE vs reference sensors", "[TO BE MEASURED]", "Requires reference belt / pulse oximeter sessions [21], [22]"],
            ["Through-wall detection matrix (drywall, block, concrete)", "[TO BE MEASURED]", "Defined in the detection report; no defensible number yet [22]"],
        ],
        widths=[2.5, 1.3, 2.7],
    )
    add_caption(doc, "Table 7.2: Honest results ledger - measured evidence versus protocol-defined pending metrics.")

    add_heading(doc, "7.3.4 User Feedback", 3)
    add_text_paragraph(
        doc,
        "The project does not include a questionnaire-based user study. Operator-facing feedback "
        "is captured instead through the hardware acceptance checklist and campaign templates, "
        "which encode what a successful operator experience must look like: the target dot must "
        "match the real position at marked distances, stale data must clear, degraded mode must "
        "hide unsupported renderings, and an empty room must stay visually empty [20], [23]. These "
        "acceptance criteria were the direct source of several implemented fixes, which is a "
        "stronger feedback loop than an opinion survey for a single-operator technical console.",
    )

    add_heading(doc, "7.4 Discussion", 2)
    add_text_paragraph(
        doc,
        "Judged as a systems-engineering result, Phantom Scan meets its objectives: the complete "
        "chain from CSI capture to honest visualization is implemented, integrated, security-"
        "hardened, and regression-tested, and real two-node streaming at healthy rates is "
        "documented [19]. Judged as a metrology result, the project is deliberately unfinished: "
        "the detection and localization accuracy numbers are defined by protocol but not yet "
        "populated, because the honesty rules forbid substituting software runs or single "
        "anecdotal sessions for repeated live trials [21], [22].",
    )
    add_text_paragraph(
        doc,
        "The discussion should also acknowledge the method's intrinsic ceiling. Two single-antenna "
        "receivers observe one projection of a three-dimensional scene; the balance geometry "
        "therefore yields a one-dimensional estimate, off-axis people read as on-axis positions, "
        "and front/back ambiguity is unresolvable without more nodes or antennas [15], [20]. The "
        "project's decision to state this on the dashboard itself, rather than in fine print, is "
        "arguably its most transferable contribution: it demonstrates a pattern for presenting "
        "low-cost sensing honestly without diminishing its real utility.",
    )
    return refs


# ---------------------------------------------------------------------------
# Chapter 8 - Recommendations and Conclusion
# ---------------------------------------------------------------------------

def chapter_8(doc: Document) -> list[int]:
    refs = [12, 15, 19, 20, 21]
    add_heading(doc, "CHAPTER 8 - RECOMMENDATIONS AND CONCLUSION", 1)

    add_heading(doc, "8.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This final chapter summarizes what Phantom Scan achieved against its objectives, states "
        "the limitations that remain, and recommends the next steps that would convert a strong, "
        "verified prototype into a validated sensing instrument.",
    )

    add_heading(doc, "8.2 Conclusion", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan set out to detect a moving human with commodity WiFi hardware and to present "
        "that detection truthfully. The delivered system does both. Two low-cost ESP32-S3 nodes "
        "capture per-subcarrier CSI and stream a versioned binary contract to a laptop host; a "
        "deterministic detector converts windowed per-subcarrier amplitude turbulence into gated "
        "motion evidence; a two-node balance fusion places the person on the node axis with "
        "distance and trend readouts; and an authenticated React dashboard renders exactly what "
        "the evidence supports - including degraded, stale, and empty states [12], [15].",
    )
    add_text_paragraph(
        doc,
        "The engineering result is verifiable rather than claimed: 173 automated tests pass across "
        "two language stacks, the wire protocol is fixture-locked between firmware, TypeScript, "
        "and Python, live two-node streaming at ~40 packets/s is documented with real boards, and "
        "a live spoofing drill was fully rejected by the ingest guard [19]. Equally important is "
        "what the project refused to claim: headline accuracy metrics remain explicitly pending "
        "until the defined measurement campaigns are executed, and superseded ambitions (drone "
        "deployment, multistatic meshes, learned pose authority) are fenced out of the runtime by "
        "automated guards. The result is an academic artifact whose every technical statement can "
        "be traced to a file, a test, or a dated report.",
    )

    add_heading(doc, "8.3 Limitations and Recommendations for Future Work", 2)
    add_text_paragraph(doc, "Principal limitations of the current system:")
    add_bullet(doc, "One-dimensional localization: the target is a projection onto the 3 m node axis; off-axis position and perpendicular movement are not representable [15], [20].")
    add_bullet(doc, "Uncalibrated default gate: the 0.12 motion threshold is a placeholder pending per-room empty-room calibration and negative-control validation [21].")
    add_bullet(doc, "Single-target assumption: multiple people blend into one fused estimate.")
    add_bullet(doc, "Pending metrology: detection rate, localization error, and vitals accuracy are protocol-defined but unmeasured [20], [21].")
    add_bullet(doc, "Single-antenna nodes: true Angle-of-Arrival remains replay/synthetic-only on this hardware.")
    add_text_paragraph(doc, "Recommendations for future work, in priority order:")
    add_numbered_list(doc, [
        "Execute the full positional-fidelity campaign (stages P0-S8) and the measurement plan, populating the results ledger with defensible live numbers [20], [21].",
        "Run the empty-room calibration tool in each deployment room and replace the placeholder gate with a mean + k*sigma calibrated threshold, validated against fan/curtain negative controls.",
        "Extend the geometry beyond one dimension: a third node (the firmware's channel-hop and multistatic decision records already sketch this path) would resolve off-axis position and front/back ambiguity [12].",
        "Promote the firmware edge-DSP tier so board-side presence/respiration estimates can cross-check host fusion, with the host remaining authoritative.",
        "Investigate multi-antenna ESP32-S3 configurations or a hybrid node to enable live AoA and reduce the single-target limitation.",
        "Complete the deferred runtime unification so the Python authority can serve as a fully interchangeable live backend behind the same truth contracts [12].",
    ])
    return refs


# ---------------------------------------------------------------------------
# Appendices: full source code
# ---------------------------------------------------------------------------

def _sorted_files(base: Path, patterns: list[str], exclude: tuple[str, ...] = ()) -> list[Path]:
    found: set[Path] = set()
    if not base.exists():
        return []
    for pattern in patterns:
        for path in base.glob(pattern):
            if path.is_file() and not any(token in path.name for token in exclude):
                found.add(path)
    return sorted(found, key=lambda p: p.relative_to(ROOT).as_posix().lower())


def appendix_groups() -> list[tuple[str, str, str, list[Path]]]:
    firmware = _sorted_files(
        ROOT / "firmware" / "esp32-csi-node" / "main",
        ["*.c", "*.h", "CMakeLists.txt"],
    )
    server = _sorted_files(ROOT / "server", ["**/*.ts"], exclude=(".test.",))
    shared = _sorted_files(ROOT / "shared", ["*.ts"], exclude=(".test.",))
    client = _sorted_files(
        ROOT / "client" / "src",
        ["*.tsx", "*.ts", "pages/*.tsx", "hooks/*.ts", "hooks/*.tsx",
         "components/dashboard/*.tsx", "components/dashboard/*.ts", "lib/*.ts", "lib/*.tsx"],
    )
    phantom = _sorted_files(ROOT / "phantom", ["*.py"])
    tooling = [
        path for path in [
            ROOT / "scripts" / "calibrate-threshold.ts",
            ROOT / "scripts" / "ruview-dashboard-bridge.py",
            ROOT / "scripts" / "record-csi-udp.py",
            ROOT / "scripts" / "replay_to_dashboard.py",
            ROOT / "scripts" / "synth-csi-udp.py",
            ROOT / "scripts" / "csi_filter_pipeline.py",
            ROOT / "scripts" / "csi_capture.py",
        ] if path.exists()
    ]
    return [
        ("A", "ESP32-S3 Firmware Source", "firmware/esp32-csi-node/main/", firmware),
        ("B", "Host Runtime and Shared Contracts (Node/TypeScript)", "server/, shared/", server + shared),
        ("C", "Operator Dashboard Client (React/TypeScript)", "client/src/", client),
        ("D", "Python Replay and DSP Toolkit", "phantom/", phantom),
        ("E", "Key Tooling Scripts", "scripts/", tooling),
    ]


def appendices_full_source(doc: Document) -> list[int]:
    refs = [12]
    add_heading(doc, "APPENDICES", 1)
    add_text_paragraph(
        doc,
        "The appendices reproduce the complete source code of the Phantom Scan implementation as "
        "of the current verified repository state [12]. Automated test files (*.test.ts and the "
        "tests/ package) are summarized in Chapter 7 rather than reprinted here; all runtime "
        "source is included verbatim. Code is typeset in a reduced monospace font; long lines "
        "wrap at the page margin.",
    )
    for letter, title, location, files in appendix_groups():
        add_heading(doc, f"Appendix {letter} - {title}", 2)
        add_text_paragraph(
            doc,
            f"Source location: {location} ({len(files)} files).",
        )
        for index, path in enumerate(files, 1):
            rel = path.relative_to(ROOT).as_posix()
            try:
                code = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                code = f"<< could not read {rel}: {exc} >>"
            line_count = code.count("\n") + 1
            add_heading(doc, f"{letter}.{index} {rel} ({line_count} lines)", 3)
            add_code_block(doc, code, size=7.5, chunk=44)
    return refs


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

CHAPTER_BUILDERS: list[Callable[[Document], list[int]]] = [
    chapter_1, chapter_2, chapter_3, chapter_4,
    chapter_5, chapter_6, chapter_7, chapter_8,
]


def _unique_sorted(refs: list[int]) -> list[int]:
    return sorted(set(refs))


def build_doc(filename: str, title: str, subtitle: str, chapter_builders: list[Callable]) -> Path:
    doc = Document()
    configure_document(doc)
    add_title(doc, title, subtitle)
    all_refs: list[int] = []
    for builder in chapter_builders:
        all_refs.extend(builder(doc))
        doc.add_section(WD_SECTION.NEW_PAGE)
    add_reference_section(doc, _unique_sorted(all_refs))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    doc.save(path)
    return path


def add_final_front_matter(doc: Document) -> None:
    add_title(
        doc,
        "Phantom Scan",
        "WiFi CSI Human Motion Detection with Two ESP32-S3 Nodes - Final Project Report",
    )
    add_table(
        doc,
        ["Field", "Value"],
        [
            ["Project title", "Phantom Scan"],
            ["Project domain", "Privacy-preserving WiFi CSI human sensing"],
            ["Validated scope", "Ground-based two-node ESP32-S3 sensing with laptop-hosted live processing"],
            ["Detection method", "Per-subcarrier CSI amplitude turbulence with gated two-node balance fusion"],
            ["Authoring basis", "Current repository state, automated test evidence, and dated verification reports"],
            ["Citation style", "IEEE numbered references"],
        ],
        widths=[1.8, 4.7],
    )
    add_text_paragraph(
        doc,
        "This final report consolidates the course milestone chapters into one unified academic "
        "document, adds the results and conclusion chapters, and reproduces the complete "
        "implementation source code as appendices. Historical project material describing drone "
        "or multistatic-mesh deployment was filtered out or explicitly framed as future work, so "
        "the narrative reflects the current verified repository state.",
    )
    doc.add_section(WD_SECTION.NEW_PAGE)
    add_toc_page(doc)
    doc.add_section(WD_SECTION.NEW_PAGE)


def build_final_doc() -> Path:
    doc = Document()
    configure_document(doc)
    add_final_front_matter(doc)
    all_refs: list[int] = []
    for builder in CHAPTER_BUILDERS:
        all_refs.extend(builder(doc))
        doc.add_section(WD_SECTION.NEW_PAGE)
    all_refs.extend(appendices_full_source(doc))
    doc.add_section(WD_SECTION.NEW_PAGE)
    add_reference_section(doc, _unique_sorted(all_refs))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "Final-Phantom-Scan-Project-Report.docx"
    doc.save(path)
    return path


def main() -> None:
    reports = [
        ("Task-1-Chapter-1-Introduction.docx", "Task 1 - Chapter 1: Introduction", "Phantom Scan project chapter deliverable", [chapter_1]),
        ("Task-2-Chapter-2-Literature-Review.docx", "Task 2 - Chapter 2: Literature Review", "Phantom Scan project chapter deliverable", [chapter_2]),
        ("Task-3-Chapter-3-Methodology-and-Work-Plan.docx", "Task 3 - Chapter 3: Methodology and Work Plan", "Phantom Scan project chapter deliverable", [chapter_3]),
        ("Task-4-Chapter-4-System-Specification.docx", "Task 4 - Chapter 4: System Specification", "Phantom Scan project chapter deliverable", [chapter_4]),
        ("Task-5-Chapter-5-System-Design.docx", "Task 5 - Chapter 5: System Design", "Phantom Scan project chapter deliverable", [chapter_5]),
        ("Chapter-6-System-Implementation.docx", "Chapter 6 - System Implementation", "Phantom Scan implementation chapter", [chapter_6]),
    ]
    built_paths = []
    for filename, title, subtitle, builders in reports:
        built_paths.append(build_doc(filename, title, subtitle, builders))
    built_paths.append(build_final_doc())
    for path in built_paths:
        print(path)


if __name__ == "__main__":
    main()
