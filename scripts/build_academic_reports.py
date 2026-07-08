from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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


REFERENCES = {
    1: "M. Kotaru, K. Joshi, D. Bharadia, and S. Katti, \"SpotFi: Decimeter level localization using WiFi,\" in Proc. ACM SIGCOMM, 2015, pp. 269-282.",
    2: "F. Adib, Z. Kabelac, D. Katabi, and R. C. Miller, \"3D tracking via body radio reflections,\" in Proc. USENIX NSDI, 2014, pp. 317-329.",
    3: "F. Adib, H. Mao, Z. Kabelac, D. Katabi, and R. C. Miller, \"Smart homes that monitor breathing and heart rate,\" in Proc. ACM CHI, 2015, pp. 837-846.",
    4: "M. Zhao, F. Adib, and D. Katabi, \"Emotion recognition using wireless signals,\" in Proc. ACM MobiCom, 2016, pp. 95-108.",
    5: "Y. Geng, J. Huang, J. He, and F. De la Torre, \"DensePose from WiFi,\" arXiv:2301.00250, 2023.",
    6: "X. Yan et al., \"Person-in-WiFi 3D: End-to-End Multi-Person 3D Pose Estimation with Wi-Fi,\" in Proc. IEEE/CVF CVPR, 2024.",
    7: "Y. Zhou et al., \"AdaPose: Cross-Site Device-Free Human Pose Estimation with Commodity WiFi,\" IEEE Internet of Things Journal, vol. 11, no. 23, pp. 40255-40267, 2024.",
    8: "HPE-Li authors, \"WiFi-enabled lightweight dual selective kernel convolution for human pose estimation,\" in Proc. ECCV Workshops, 2024.",
    9: "Phantom Scan project repository, \"README.md,\" current repo state verified July 8, 2026.",
    10: "Phantom Scan project documentation, \"SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md,\" Mar. 26, 2026, with current runtime corrections applied.",
    11: "Phantom Scan project documentation, \"system_architecture_methodology.md,\" current repo source used for methodology alignment.",
    12: "Phantom Scan verification record, \"TEST_REPORT.md,\" generated Jul. 1, 2026.",
    13: "Phantom Scan verification record, \"TARGET_VERIFICATION_REPORT.md,\" verified Jun. 29, 2026.",
    14: "Phantom Scan verification record, \"REAL_TEST_REPORT.md,\" two-node positional-fidelity campaign template and evidence notes.",
    15: "Phantom Scan verification record, \"HARDWARE_TEST_CHECKLIST.md,\" hardware acceptance checklist updated Jul. 8, 2026.",
}


def set_cell_text(cell, text: str, bold: bool = False) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    run.bold = bold
    set_run_font(run, size=10.5, bold=bold)


def set_run_font(run, size: float = 11, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


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
    p = doc.add_paragraph(style="List Bullet")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run)
    style_paragraph(p, after=4)


def add_numbered(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Number")
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
    table.style = "Table Grid"
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


def add_reference_section(doc: Document, refs: Iterable[int]) -> None:
    add_heading(doc, "References", 1)
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


@dataclass
class ReportSpec:
    filename: str
    title: str
    subtitle: str
    builder: callable


def chapter_1(doc: Document) -> list[int]:
    refs = [5, 9]
    add_heading(doc, "CHAPTER 1 - INTRODUCTION", 1)
    add_heading(doc, "1.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan is an academic and engineering project that investigates how WiFi "
        "Channel State Information (CSI) can be used to detect human presence, estimate "
        "relative position, and expose live sensing information without cameras or wearable "
        "devices. The current implementation focuses on a ground-based two-node ESP32-S3 "
        "deployment connected to a laptop-hosted processing and visualization stack [9].",
    )
    add_text_paragraph(
        doc,
        "The topic is relevant because many practical safety, monitoring, and assistive "
        "scenarios need privacy-preserving situational awareness. Camera systems can provide "
        "rich context, but they also create privacy, storage, and regulatory concerns. WiFi "
        "CSI sensing offers a different path by observing how radio propagation changes when a "
        "person moves through the environment.",
    )

    add_heading(doc, "1.2 Background", 2)
    add_text_paragraph(
        doc,
        "Research over the past decade has shown that commodity wireless hardware can support "
        "contactless sensing tasks such as localization, respiration monitoring, activity "
        "recognition, and even pose estimation [5]. Early systems relied on specialized "
        "network cards or high-cost measurement setups, while recent work has expanded toward "
        "lower-cost embedded hardware and more deployable software stacks. Phantom Scan builds "
        "on that evolution by combining ESP32-S3 CSI capture, deterministic digital signal "
        "processing, optional AI-assisted analysis, and a live operator dashboard within a "
        "single reproducible repository [9].",
    )

    add_heading(doc, "1.3 Problem Statement", 2)
    add_text_paragraph(
        doc,
        "The main problem addressed by Phantom Scan is how to design a low-cost, privacy-first, "
        "through-wall-capable sensing system that can detect and present human activity using "
        "commodity WiFi hardware while remaining technically honest about uncertainty, degraded "
        "states, and hardware limitations. Existing approaches often depend on expensive "
        "platforms, single-environment models, or opaque visualizations that do not clearly "
        "separate live truth from inferred estimates.",
    )

    add_heading(doc, "1.4 Limitations", 2)
    add_bullet(doc, "The current validated deployment target is a two-node ESP32-S3 setup rather than a large multistatic mesh.")
    add_bullet(doc, "The authoritative live runtime is the Node/TypeScript host path; the Python runtime remains important for replay and tooling but is not yet the main live dashboard authority.")
    add_bullet(doc, "Live hardware validation depends on physical boards, WiFi conditions, and firmware tooling availability, so some metrics cannot be claimed without real sessions.")
    add_bullet(doc, "The fused localization model is currently one-dimensional along the node baseline, which means off-axis people are projected onto that line.")

    add_heading(doc, "1.5 Project Objectives", 2)
    add_numbered(doc, "To design a working WiFi CSI sensing pipeline using two ESP32-S3 nodes and a laptop-hosted processing environment.")
    add_numbered(doc, "To build a real-time dashboard that distinguishes truthful live targets, degraded states, and stale or absent data.")
    add_numbered(doc, "To combine deterministic signal processing, optional AI assistance, and operator-facing telemetry without allowing synthetic fallback to be misrepresented as live evidence.")
    add_numbered(doc, "To document and test the system in a way that maps directly to real source files, runtime modules, and verification artifacts.")

    add_heading(doc, "1.6 Project Solution Overview", 2)
    add_text_paragraph(
        doc,
        "The proposed solution consists of four linked layers: ESP32-S3 firmware captures CSI and "
        "streams binary frames over UDP; a Node/TypeScript host ingests packets, tracks node state, "
        "builds live target information, and publishes HTTP and WebSocket outputs; a Python runtime "
        "supports replay, DSP, and auxiliary analysis; and a React dashboard presents operator "
        "controls, target state, node features, and visualized spatial relationships [9].",
    )

    add_heading(doc, "1.7 Project Scope", 2)
    add_text_paragraph(doc, "Project Scope Covered:")
    add_bullet(doc, "Two-node ESP32-S3 CSI capture and transport.")
    add_bullet(doc, "Live dashboard runtime, authentication, and operator monitoring.")
    add_bullet(doc, "Deterministic DSP, replay tooling, testing, and verification reports.")
    add_bullet(doc, "Relative target presentation, degraded-mode handling, and evidence-based reporting.")
    add_text_paragraph(doc, "Project Scope Not Covered:")
    add_bullet(doc, "Drone, UAV, MAVLink, GPS, or IMU-based deployment in the current repo state.")
    add_bullet(doc, "A production-scale database-backed multi-user platform.")
    add_bullet(doc, "A free-room 3D localization solution with fully validated off-axis reconstruction.")

    add_heading(doc, "1.8 Project Feasibility", 2)
    add_text_paragraph(
        doc,
        "Technical feasibility is high because the repository already contains the main software, "
        "firmware, test suites, and run guides needed for a two-node implementation [9], [12]. "
        "Operational feasibility is also strong because the system is designed for a laptop operator "
        "workflow and makes degraded or stale states visible instead of hiding them. Economic "
        "feasibility is favorable because the sensing nodes are based on low-cost ESP32-S3 boards "
        "rather than specialized radar hardware. The remaining feasibility risk lies in live-room "
        "calibration, repeatable hardware proof, and the difference between software-pass results "
        "and field-validated sensing performance [12], [13].",
    )
    return refs


def chapter_2(doc: Document) -> list[int]:
    refs = [1, 2, 3, 5, 6, 7, 8, 9]
    add_heading(doc, "CHAPTER 2 - LITERATURE REVIEW", 1)
    add_heading(doc, "2.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "A literature review is necessary because WiFi sensing has progressed from basic "
        "localization to richer human-state inference, yet each generation of systems makes "
        "different tradeoffs in hardware cost, fidelity, privacy, and deployability. Reviewing "
        "related studies clarifies where Phantom Scan aligns with current research and where it "
        "deliberately chooses a more implementation-driven path.",
    )

    add_heading(doc, "2.2 Review of Existing Systems", 2)
    add_text_paragraph(
        doc,
        "SpotFi is a foundational indoor localization system that uses commodity WiFi and Angle of "
        "Arrival processing to achieve decimeter-scale location estimates [1]. Its main strength is "
        "showing that carefully processed WiFi CSI can support practical localization without custom "
        "radar hardware. However, SpotFi primarily targets position estimation rather than full "
        "operator-facing live human-state presentation or embedded-node deployability.",
    )
    add_text_paragraph(
        doc,
        "The early work on capturing the human figure through a wall demonstrated that radio "
        "reflections can recover human body information without optical sensors [2]. This line of "
        "research is important because it proved the privacy-preserving and non-line-of-sight value "
        "of radio-based sensing. Its limitation, for a project like Phantom Scan, is that research "
        "prototypes of this kind often depend on controlled setups and do not always expose a "
        "reproducible field-oriented software stack.",
    )
    add_text_paragraph(
        doc,
        "Vital-Radio and similar contactless vital-sign systems established that WiFi signals can be "
        "used to estimate respiration and heart rate [3]. These systems are strong in physiological "
        "monitoring but tend to emphasize narrow sensing tasks under controlled conditions. Phantom "
        "Scan instead needs a broader operational pipeline that combines transport, verification, "
        "dashboard logic, and honesty around absent or stale live data.",
    )
    add_text_paragraph(
        doc,
        "DensePose from WiFi shifted the field toward richer body understanding by mapping WiFi "
        "signals to dense pose outputs [5]. The later Person-in-WiFi 3D study extended the ambition "
        "to end-to-end multi-person 3D pose estimation [6]. These studies are highly relevant because "
        "they demonstrate that CSI contains far more information than binary occupancy alone. Their "
        "main challenge for deployable projects is the need for robust training data, cross-site "
        "generalization, and careful handling of environment drift.",
    )
    add_text_paragraph(
        doc,
        "AdaPose and HPE-Li address two practical research concerns: cross-site generalization and "
        "lightweight inference [7], [8]. AdaPose focuses on transferring pose estimation across "
        "different physical environments, while HPE-Li explores lighter architectures suitable for "
        "resource-constrained use. Both directly inform Phantom Scan because the project must work "
        "with inexpensive hardware and cannot assume that one environment or one calibration setting "
        "fits all deployments.",
    )

    add_heading(doc, "2.3 Comparison of Existing Solutions", 2)
    add_table(
        doc,
        ["System / Study", "Primary Goal", "Strengths", "Limitations Relative to Phantom Scan"],
        [
            ["SpotFi [1]", "Indoor localization", "Commodity WiFi, strong AoA-based positioning foundations", "Not designed as an end-to-end embedded sensing and operator dashboard system"],
            ["Through-wall figure capture [2]", "Human figure recovery", "Non-line-of-sight feasibility, privacy-preserving sensing", "Research-oriented setup, limited deployment workflow focus"],
            ["Vital-Radio [3]", "Respiration and heart-rate monitoring", "Strong physiological sensing evidence", "Narrower task scope than full live target pipeline"],
            ["DensePose from WiFi [5]", "Pose estimation from CSI", "Rich semantic understanding of CSI", "Model complexity and environment sensitivity"],
            ["Person-in-WiFi 3D [6]", "Multi-person 3D pose estimation", "State-of-the-art ambition in 3D WiFi pose", "Higher data, model, and generalization requirements"],
            ["AdaPose / HPE-Li [7], [8]", "Cross-site and lightweight pose inference", "Better portability and efficiency direction", "Still research-centric and not a complete field stack"],
        ],
        widths=[1.6, 1.2, 1.5, 2.2],
    )
    add_text_paragraph(
        doc,
        "The literature shows a clear gap between high-ambition research prototypes and a repository "
        "that is auditable, modular, low-cost, and explicit about degraded truth states. Phantom Scan "
        "addresses that gap by prioritizing a reproducible two-node implementation, practical "
        "verification artifacts, and a dashboard that avoids claiming more certainty than the live "
        "data supports [9].",
    )
    return refs


def chapter_3(doc: Document) -> list[int]:
    refs = [9, 10, 11, 12]
    add_heading(doc, "CHAPTER 3 - METHODOLOGY AND WORK PLAN", 1)
    add_heading(doc, "3.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter explains the development methodology used to transform Phantom Scan from a "
        "set of concepts and experimental components into a working two-node sensing system. The "
        "methodology matters because the project includes firmware, host processing, UI behavior, "
        "and live verification, all of which have to align before the system can be evaluated "
        "honestly.",
    )

    add_heading(doc, "3.2 System Development Methodology", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan follows a hybrid iterative methodology. High-level architecture and boundaries "
        "were captured through design documents and architectural decision records, but the actual "
        "implementation advanced through repeated cycles of coding, test execution, runtime checks, "
        "and hardware-oriented verification [10], [11]. This approach is closer to Agile engineering "
        "than to a strict Waterfall model because the dashboard truth model, live transport behavior, "
        "and hardware assumptions were refined continuously as issues were discovered.",
    )
    add_text_paragraph(
        doc,
        "A hybrid model was selected because the project combines research uncertainty with concrete "
        "software delivery. A rigid sequential process would have hidden important runtime issues "
        "until too late, while a purely informal process would not have produced auditable artifacts. "
        "The hybrid method preserved design intent while allowing practical corrections when the live "
        "behavior contradicted earlier assumptions.",
    )

    add_heading(doc, "3.3 Requirement Gathering Techniques", 2)
    add_bullet(doc, "Repository analysis of source files, tests, and module boundaries.")
    add_bullet(doc, "Document analysis of README, architecture reports, and implementation notes.")
    add_bullet(doc, "Verification artifact review using test reports and hardware checklists.")
    add_bullet(doc, "Scenario-based reasoning around operator needs, truthful rendering, and degraded states.")
    add_text_paragraph(
        doc,
        "These techniques were appropriate because the project is not a conventional business "
        "information system with a large external stakeholder interview set. Instead, its most "
        "important requirements are embedded in technical modules, run guides, and evidence logs. "
        "Reading those artifacts was the most reliable way to infer what the system must do and what "
        "it must never falsely claim.",
    )

    add_heading(doc, "3.4 Project Plan (Gantt Chart)", 2)
    add_table(
        doc,
        ["Phase", "Main Activities", "Planned Outcome"],
        [
            ["Phase 1", "Problem framing, background study, project scope definition", "Chapters 1 and 2 completed"],
            ["Phase 2", "Architecture review, methodology definition, requirement analysis", "Chapters 3 and 4 completed"],
            ["Phase 3", "System design documentation, UI and data-flow modeling", "Chapter 5 completed"],
            ["Phase 4", "Firmware, host runtime, UI integration, and implementation writing", "Chapter 6 completed"],
            ["Phase 5", "Testing, results analysis, final discussion, recommendations", "Chapters 7 and 8 plus final report"],
        ],
        widths=[1.1, 3.7, 1.7],
    )
    add_text_paragraph(
        doc,
        "The project sequence follows the university task structure while still reflecting the real "
        "engineering order of work. Implementation was started before the final report writing was "
        "finished, because live-system evidence had to exist before the results and discussion "
        "chapter could be written credibly.",
    )

    add_heading(doc, "3.5 Development of Tools and Technologies", 2)
    add_table(
        doc,
        ["Category", "Technology", "Justification"],
        [
            ["Firmware", "ESP-IDF with C on ESP32-S3", "Provides direct WiFi CSI capture, embedded control, and low-cost sensing nodes"],
            ["Host backend", "Node.js with TypeScript", "Owns the current authoritative live path, UDP ingest, HTTP routes, and WebSocket publishing [9]"],
            ["Python runtime", "Python 3.13-based project tooling", "Supports replay, DSP, tests, and auxiliary processing paths [9], [12]"],
            ["Frontend", "React with TypeScript and Vite", "Supports operator dashboard, live rendering, and browser-based interaction [9]"],
            ["Testing", "TypeScript tests and pytest", "Allows protocol, target-state, and runtime regression checks [12], [13]"],
            ["Data and storage", "JSON, JSONL, local files", "Fits prototype scope and keeps runtime artifacts human-inspectable"],
        ],
        widths=[1.0, 2.0, 3.5],
    )
    return refs


def chapter_4(doc: Document) -> list[int]:
    refs = [9, 12, 13, 15]
    add_heading(doc, "CHAPTER 4 - SYSTEM SPECIFICATION", 1)
    add_heading(doc, "4.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "System specification defines what Phantom Scan must do and the quality conditions under "
        "which it must do it. Because this project deals with live sensing rather than static data "
        "entry, the specification has to cover both functional behavior and strict truthfulness in "
        "the way live states are represented to the operator.",
    )

    add_heading(doc, "4.2 Functional Requirements", 2)
    add_table(
        doc,
        ["ID", "Functional Requirement"],
        [
            ["FR1", "The firmware shall capture WiFi CSI on ESP32-S3 nodes and transmit structured frames to the host."],
            ["FR2", "The host runtime shall ingest UDP packets, validate known frame types, and maintain per-node freshness state."],
            ["FR3", "The system shall expose live sensing state through HTTP and WebSocket interfaces for the dashboard."],
            ["FR4", "The dashboard shall display node presence, target state, and live operator-facing telemetry."],
            ["FR5", "The system shall support degraded behavior when only one node is available rather than fabricating fused outputs."],
            ["FR6", "The operator shall be able to authenticate before performing privileged actions."],
            ["FR7", "The system shall support replay and testing workflows using recorded or synthetic-safe development inputs."],
            ["FR8", "The system shall preserve verification artifacts such as test reports, target verification notes, and hardware checklists."],
            ["FR9", "The dashboard shall clear stale or absent targets instead of leaving ghost targets on screen."],
            ["FR10", "The system shall distinguish between live truth, advisory AI information, and absent data in its outputs."],
        ],
        widths=[0.6, 5.9],
    )

    add_heading(doc, "4.3 Non-Functional Requirements", 2)
    add_table(
        doc,
        ["Category", "Non-Functional Requirement"],
        [
            ["Performance", "The live path should provide timely dashboard updates and maintain usable responsiveness during normal node streaming [9]."],
            ["Reliability", "The system should detect stale nodes, handle disconnects, and degrade cleanly rather than fail silently [13], [15]."],
            ["Usability", "The operator interface should show state clearly, including degraded, stale, and empty-room conditions [15]."],
            ["Security", "Authentication, session checks, and privileged route controls should gate sensitive operations."],
            ["Maintainability", "Modules should remain separated by role across firmware, host, Python tooling, and UI layers [9], [10]."],
            ["Traceability", "Important technical claims should map to tests, source files, or verification records [12], [13]."],
            ["Scalability", "The architecture should allow future extension beyond two nodes, even if the current validated path remains two-node focused."],
            ["Ethical / AI", "AI assistance must remain advisory when its authority is not fully validated, and the UI must not misrepresent advisory output as proven truth [12]."],
        ],
        widths=[1.2, 5.3],
    )
    return refs


def chapter_5(doc: Document) -> list[int]:
    refs = [9, 10, 11]
    add_heading(doc, "CHAPTER 5 - SYSTEM DESIGN", 1)
    add_heading(doc, "5.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter translates the system specification into an architectural design that can guide "
        "implementation. The design for Phantom Scan emphasizes modularity, low-cost sensing nodes, a "
        "host runtime that owns live truth, and a user interface that represents the sensing state "
        "honestly.",
    )

    add_heading(doc, "5.2 System Architecture Design", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan uses a layered architecture with four main components: the ESP32-S3 firmware "
        "layer, the host ingest and processing layer, the Python replay and DSP tooling layer, and the "
        "React dashboard layer [9], [10]. The firmware emits CSI frames; the Node/TypeScript runtime "
        "owns UDP parsing, node tracking, target-state publication, and operator APIs; the Python "
        "modules provide deterministic tooling and replay support; and the frontend renders the live "
        "state for the operator.",
    )
    add_table(
        doc,
        ["Layer", "Main Responsibility", "Representative Modules"],
        [
            ["Presentation Layer", "Render operator views and live sensing status", "client/src/pages, client/src/components/dashboard"],
            ["Application Layer", "Ingest packets, build target state, publish APIs", "server/index.ts, server/routes.ts, server/lib/websocket.ts"],
            ["Data / Runtime Layer", "Replay, DSP, recording, protocol handling", "phantom/protocol.py, phantom/runtime.py, phantom/dsp.py"],
            ["Integration Layer", "UDP transport, WebSocket publication, operator auth", "server/lib/udp-server.ts, server/auth, shared/schema.ts"],
            ["Security Layer", "Protect privileged actions and session-backed operations", "server/auth and route-level session enforcement"],
        ],
        widths=[1.2, 2.2, 3.1],
    )

    add_heading(doc, "5.3 Class Diagram", 2)
    add_text_paragraph(
        doc,
        "Because Phantom Scan is structured more as cooperating modules and typed data contracts than "
        "as a single class-heavy business application, a module interaction view is more accurate than "
        "a conventional UML class diagram. The central design entities are node state, target state, "
        "sensing frames, transport parsers, operator sessions, and dashboard view models. Shared type "
        "definitions in the repository act as the contract layer between backend and frontend.",
    )
    add_table(
        doc,
        ["Design Entity", "Role in the System"],
        [
            ["Sensor node state", "Represents the freshness, identity, and metrics of each ESP32-S3 node"],
            ["Target state", "Represents visible, degraded, stale, or absent human-target information"],
            ["Sensing frame", "Carries published state from host runtime to UI clients"],
            ["Operator session", "Controls privileged actions such as authenticated settings or provisioning routes"],
            ["Replay / recording model", "Supports offline verification and repeatable analysis"],
        ],
        widths=[1.8, 4.7],
    )

    add_heading(doc, "5.4 Database Design", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan does not rely on a traditional relational database in the current project "
        "scope. Instead, it uses lightweight file-based persistence because the implementation is a "
        "prototype sensing system rather than a multi-tenant transaction platform. Operator records, "
        "runtime settings, recordings, and verification artifacts are stored as structured files. This "
        "design reduces deployment overhead and keeps important evidence auditable [9].",
    )
    add_text_paragraph(
        doc,
        "For the AI-oriented parts of the project, the more relevant design concern is not entity "
        "tables but data flow: CSI frames are captured, validated, transformed into runtime state, and "
        "published to the UI. Therefore, the effective data design is a processing pipeline rather than "
        "a conventional ERD-heavy backend schema.",
    )

    add_heading(doc, "5.5 User Interface (UI) Design", 2)
    add_text_paragraph(
        doc,
        "The dashboard is designed as an operator console rather than a consumer-facing mobile app. "
        "Its layout prioritizes live visibility of node freshness, target state, and motion-relevant "
        "feedback. The interface uses a main spatial scene, supporting telemetry panels, and explicit "
        "state-based rendering rules so the operator can tell the difference between active targets, "
        "degraded signals, stale conditions, and empty-room silence [9], [15].",
    )
    add_bullet(doc, "Top-level dashboard route for live monitoring.")
    add_bullet(doc, "Authentication view for controlled operator access.")
    add_bullet(doc, "Target and node visualization components for spatial awareness.")
    add_bullet(doc, "History, report, and activity views for operational review.")

    add_heading(doc, "5.6 Summary", 2)
    add_text_paragraph(
        doc,
        "The system design supports efficiency by separating concerns across firmware, host runtime, "
        "Python tooling, and UI. It supports maintainability by keeping data contracts explicit and "
        "modules testable. It supports security through session-backed privileged flows. Most "
        "importantly, it supports research credibility by making room for degraded truth states rather "
        "than forcing the interface to display certainty when the live data does not justify it.",
    )
    return refs


def chapter_6(doc: Document) -> list[int]:
    refs = [9, 12, 13, 15]
    add_heading(doc, "CHAPTER 6 - SYSTEM IMPLEMENTATION", 1)
    add_heading(doc, "6.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "The implementation phase translated the design of Phantom Scan into a working repository with "
        "firmware, host runtime, replay tooling, tests, and a live dashboard. In the current repo "
        "state, the project is a ground-based two-node ESP32-S3 sensing system. The current live "
        "dashboard path is owned by the Node/TypeScript runtime, while the Python runtime remains an "
        "important replay and DSP toolset rather than the main live authority [9].",
    )

    add_heading(doc, "6.2 Implementation Overview", 2)
    add_text_paragraph(
        doc,
        "Implementation spans multiple cooperating processes rather than one monolithic program. The "
        "firmware on each ESP32-S3 node captures and transmits CSI-related frames. The Node/TypeScript "
        "host binds the live UDP ingest path, validates known frame types, tracks each node, computes "
        "dashboard state, and exposes WebSocket and HTTP outputs. The React frontend consumes those "
        "outputs and renders operator-facing views. In parallel, the Python package supports replay, "
        "recording, deterministic DSP, and automated tests [9], [12].",
    )

    add_heading(doc, "6.3 Implementation Details", 2)
    add_heading(doc, "a. User Authentication", 3)
    add_text_paragraph(
        doc,
        "Authentication is implemented in the host application layer so that privileged operations are "
        "not available to anonymous clients. The design uses operator sessions and route-level checks "
        "instead of assuming that any browser connected to the dashboard is fully trusted. This aligns "
        "with the project goal of making the operator console usable but controlled.",
    )

    add_heading(doc, "b. Data Persistence and Runtime State", 3)
    add_text_paragraph(
        doc,
        "The project does not use a heavyweight database server in the current scope. Instead, runtime "
        "state is managed in memory during live sessions, while recordings, reports, and related "
        "artifacts are stored as local files. This choice is consistent with the prototype nature of "
        "the system and keeps the verification trail easy to inspect [9].",
    )

    add_heading(doc, "c. User Interface Elements", 3)
    add_text_paragraph(
        doc,
        "The frontend is implemented in React and TypeScript. The main live dashboard contains a "
        "spatial scene, node indicators, state panels, and routes for activity and reporting. A key "
        "implementation requirement is that the UI must not leave a fabricated or stale target visible "
        "after live data disappears. Repository verification confirms that recent fixes focused on "
        "clearing ghost targets and labeling degraded states truthfully [13], [15].",
    )

    add_heading(doc, "d. Functionality Modules", 3)
    add_table(
        doc,
        ["Module Area", "Implemented Role"],
        [
            ["Firmware", "Capture CSI and send structured live frames from each ESP32-S3 node"],
            ["UDP ingest", "Receive and validate node frames on the host runtime"],
            ["WebSocket publication", "Send live sensing state to dashboard clients"],
            ["Target-state logic", "Differentiate fused, degraded, stale, and empty-room states"],
            ["Python replay / DSP", "Provide deterministic analysis, replay, and testable runtime tooling"],
            ["Dashboard rendering", "Present node features, spatial state, and operator-facing controls"],
        ],
        widths=[1.4, 5.1],
    )

    add_heading(doc, "6.4 Integration and Verification", 2)
    add_text_paragraph(
        doc,
        "Integration was implemented by keeping the layer boundaries explicit. Firmware publishes live "
        "data; the host runtime owns the authoritative dashboard path; the frontend subscribes to the "
        "published state; and the Python package supports replay and cross-checking. Verification was "
        "performed through TypeScript checks, automated tests, build steps, and project-specific target "
        "verification records. The available evidence shows passing software validation and honest "
        "documentation of hardware gaps where live packet streams were not available [12], [13].",
    )
    return refs


def chapter_7(doc: Document) -> list[int]:
    refs = [9, 12, 13, 14, 15]
    add_heading(doc, "CHAPTER 7 - RESULTS AND DISCUSSION", 1)
    add_heading(doc, "7.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "This chapter evaluates how Phantom Scan performed against its objectives using the project "
        "artifacts available in the repository. The focus is not only on what passed, but also on "
        "what remains unverified in live hardware conditions. This distinction is necessary because "
        "software success does not automatically prove real sensing success.",
    )

    add_heading(doc, "7.2 Data Collection and Research", 2)
    add_text_paragraph(
        doc,
        "The evaluation evidence comes from several sources: the current repository state, automated "
        "test runs, target verification notes, hardware checklists, and real-hardware reporting "
        "templates [12]-[15]. In addition, the implementation is informed by literature on WiFi CSI "
        "sensing and by internal design reports that describe the project architecture and methodology "
        "[9]-[11].",
    )
    add_text_paragraph(
        doc,
        "The data used for testing includes software fixtures, replay sessions, protocol fixtures, "
        "dashboard tests, and hardware-oriented acceptance criteria. This mixture is important because "
        "Phantom Scan must be judged as both a software system and a sensing system. A pure code-level "
        "evaluation would miss questions such as ghost targets, empty-room silence, and node dropout "
        "behavior.",
    )

    add_heading(doc, "7.3 System Testing and User Feedback", 2)
    add_text_paragraph(
        doc,
        "Functional testing shows strong software progress. The project verification records report a "
        "passing Python suite with 75 passed tests and a passing Node/dashboard test set with 19 "
        "passing tests, alongside successful TypeScript checks and production builds [12]. Additional "
        "verification notes confirm that the default live dashboard path no longer fabricates targets "
        "when live data is absent, and that degraded single-node behavior is labeled explicitly [13].",
    )
    add_text_paragraph(
        doc,
        "Non-functional testing shows a more mixed but still useful result. From a usability "
        "perspective, the dashboard truth-model fixes improve operator trust because stale and absent "
        "data are handled visibly rather than hidden behind a generic avatar or point cloud. From a "
        "reliability perspective, the repository now contains a clearer honesty boundary between live "
        "data and software-only checks. From a performance perspective, the current build and test "
        "artifacts show that the stack can compile and run, but full end-to-end live-rate claims still "
        "depend on active hardware sessions [12], [14], [15].",
    )
    add_text_paragraph(
        doc,
        "User feedback in the repository is indirect rather than questionnaire-based; it appears as "
        "acceptance criteria, issue-focused verification notes, and hardware run checklists. These "
        "artifacts emphasize that a successful result is not simply passing unit tests but truthful "
        "operator-visible behavior: no ghost target after silence, correct degraded mode, and clear "
        "movement interpretation in the live scene [14], [15].",
    )
    add_table(
        doc,
        ["Evaluation Area", "Observed Result", "Discussion"],
        [
            ["Software correctness", "Strong", "Automated tests and build checks passed in the recorded verification run [12]"],
            ["Dashboard truthfulness", "Improved", "Ghost-target and fabricated-fallback issues were explicitly addressed [13]"],
            ["Hardware live proof", "Partial", "Checklists and templates exist, but some live metrics remain marked to be measured [12], [14], [15]"],
            ["Research alignment", "Good", "Project direction matches current WiFi CSI sensing themes while staying implementable [5]-[9]"],
        ],
        widths=[1.4, 1.2, 3.9],
    )
    return refs


def chapter_8(doc: Document) -> list[int]:
    refs = [9, 12, 13, 14, 15]
    add_heading(doc, "CHAPTER 8 - RECOMMENDATIONS AND CONCLUSION", 1)
    add_heading(doc, "8.1 Introduction", 2)
    add_text_paragraph(
        doc,
        "The final chapter summarizes what Phantom Scan achieved, evaluates how well the objectives "
        "were met, and identifies the most important next steps needed to move from a strong research "
        "prototype toward a more fully validated sensing platform.",
    )

    add_heading(doc, "8.2 Conclusion", 2)
    add_text_paragraph(
        doc,
        "Phantom Scan successfully demonstrates a coherent low-cost WiFi CSI sensing architecture built "
        "around two ESP32-S3 nodes, a Node/TypeScript live runtime, a Python replay and DSP path, and "
        "a React dashboard for operator-facing state presentation [9]. The project meets its core "
        "objectives in architecture, modular implementation, and evidence-aware reporting. It also "
        "improves on a common weakness in research prototypes by making degraded and absent states part "
        "of the interface logic rather than treating them as secondary concerns.",
    )
    add_text_paragraph(
        doc,
        "At the same time, the project deliberately avoids overstating what is complete. The repository "
        "evidence shows that software validation is strong, but some live sensing claims still require "
        "real hardware measurement before they can be stated as proven results [12]-[15]. This honesty "
        "is itself a strength, because it keeps the report aligned with the actual system state.",
    )

    add_heading(doc, "8.3 Limitations and Recommendations for Future Work", 2)
    add_bullet(doc, "Complete repeated live two-node trials and record the measured localization and stability metrics that are currently marked as pending.")
    add_bullet(doc, "Extend the validated geometry beyond one-dimensional baseline projection so off-axis targets are represented more faithfully.")
    add_bullet(doc, "Harden cross-site calibration and threshold tuning so empty-room behavior is repeatable across different rooms.")
    add_bullet(doc, "Unify more of the live and replay logic where practical, while preserving the current rule that advisory AI must not silently become the truth authority.")
    add_bullet(doc, "Expand the operator evaluation process with structured user observation or supervisor review so usability evidence is not limited to engineering checklists.")
    return refs


def add_final_front_matter(doc: Document) -> None:
    add_title(
        doc,
        "Phantom Scan Academic Project Report",
        "Comprehensive project report covering Chapters 1-8 and References",
    )
    add_table(
        doc,
        ["Field", "Value"],
        [
            ["Project title", "Phantom Scan"],
            ["Project domain", "Privacy-preserving WiFi CSI sensing using ESP32-S3 nodes"],
            ["Current validated scope", "Ground-based two-node sensing with laptop-hosted processing"],
            ["Authoring basis", "Built from current repository state and supplied course task structure"],
            ["Citation style", "IEEE numbered references"],
        ],
        widths=[1.8, 4.7],
    )
    intro = doc.add_paragraph()
    intro.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = intro.add_run(
        "This final report consolidates the course milestone chapters into one unified academic document. "
        "Historical project notes were filtered so that the narrative reflects the current repo truth rather "
        "than superseded drone-oriented or multi-platform claims."
    )
    set_run_font(run)
    style_paragraph(intro)
    doc.add_section(WD_SECTION.NEW_PAGE)


def build_doc(filename: str, title: str, subtitle: str, chapter_builders: list[callable]) -> Path:
    doc = Document()
    configure_document(doc)
    add_title(doc, title, subtitle)
    all_refs: list[int] = []
    for builder in chapter_builders:
        refs = builder(doc)
        all_refs.extend(refs)
        doc.add_section(WD_SECTION.NEW_PAGE)
    unique_refs = []
    for ref_id in all_refs:
        if ref_id not in unique_refs:
            unique_refs.append(ref_id)
    add_reference_section(doc, unique_refs)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    doc.save(path)
    return path


def build_final_doc() -> Path:
    doc = Document()
    configure_document(doc)
    add_final_front_matter(doc)
    all_refs: list[int] = []
    for builder in [chapter_1, chapter_2, chapter_3, chapter_4, chapter_5, chapter_6, chapter_7, chapter_8]:
        all_refs.extend(builder(doc))
        doc.add_section(WD_SECTION.NEW_PAGE)
    unique_refs = []
    for ref_id in all_refs:
        if ref_id not in unique_refs:
            unique_refs.append(ref_id)
    add_reference_section(doc, unique_refs)
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
