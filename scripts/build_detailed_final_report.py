from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


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


ORIGINAL_DOC = Path(r"d:\my cours\RESEARCH PROJECT 2\PhantomScan_FINAL -docunent .docx")
OUTPUT_DIR = ROOT / "generated_reports"
OUTPUT_DOC = OUTPUT_DIR / "PhantomScan_FINAL_FULL_DETAILED.docx"


REFERENCES = {
    1: "M. Kotaru, K. Joshi, D. Bharadia, and S. Katti, \"SpotFi: Decimeter level localization using WiFi,\" in Proc. ACM SIGCOMM, 2015, pp. 269-282.",
    2: "F. Adib, Z. Kabelac, D. Katabi, and R. C. Miller, \"3D tracking via body radio reflections,\" in Proc. USENIX NSDI, 2014, pp. 317-329.",
    3: "F. Adib, H. Mao, Z. Kabelac, D. Katabi, and R. C. Miller, \"Smart homes that monitor breathing and heart rate,\" in Proc. ACM CHI, 2015, pp. 837-846.",
    4: "Y. Geng, J. Huang, J. He, and F. De la Torre, \"DensePose from WiFi,\" arXiv:2301.00250, 2023.",
    5: "X. Yan et al., \"Person-in-WiFi 3D: End-to-End Multi-Person 3D Pose Estimation with Wi-Fi,\" in Proc. IEEE/CVF CVPR, 2024.",
    6: "Y. Zhou et al., \"AdaPose: Cross-Site Device-Free Human Pose Estimation with Commodity WiFi,\" IEEE Internet of Things Journal, vol. 11, no. 23, pp. 40255-40267, 2024.",
    7: "HPE-Li authors, \"WiFi-enabled lightweight dual selective kernel convolution for human pose estimation,\" in Proc. ECCV Workshops, 2024.",
    8: "Phantom Scan repository, README.md, current verified repo state, Jul. 8, 2026.",
    9: "Phantom Scan repository, SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md, historical architecture source used with current-state corrections.",
    10: "Phantom Scan repository, system_architecture_methodology.md, methodology source used with current-state corrections.",
    11: "Phantom Scan repository, TEST_REPORT.md, generated Jul. 1, 2026.",
    12: "Phantom Scan repository, TARGET_VERIFICATION_REPORT.md, verified Jun. 29, 2026.",
    13: "Phantom Scan repository, REAL_TEST_REPORT.md, real-hardware detection and movement test report template.",
    14: "Phantom Scan repository, HARDWARE_TEST_CHECKLIST.md, hardware run and acceptance checklist.",
    15: "Phantom Scan repository, package.json, current dependency and script manifest.",
    16: "Phantom Scan repository, server and client source modules under current runtime path, inspected Jul. 8, 2026.",
}


def set_run_font(run, size: float = 11, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def style_paragraph(paragraph, *, before: int = 0, after: int = 8, line: float = 1.15, align=WD_ALIGN_PARAGRAPH.JUSTIFY) -> None:
    paragraph.alignment = align
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line
    for run in paragraph.runs:
        set_run_font(run, size=run.font.size.pt if run.font.size else 11, bold=bool(run.bold), italic=bool(run.italic))


def add_p(doc: Document, text: str, *, before: int = 0, after: int = 8, line: float = 1.15, align=WD_ALIGN_PARAGRAPH.JUSTIFY) -> None:
    p = doc.add_paragraph()
    p.alignment = align
    run = p.add_run(text)
    set_run_font(run, 11)
    style_paragraph(p, before=before, after=after, line=line, align=align)


def add_heading(doc: Document, text: str, level: int) -> None:
    p = doc.add_paragraph()
    if level == 1:
        size, before, after = 16, 16, 8
    elif level == 2:
        size, before, after = 13, 12, 6
    else:
        size, before, after = 12, 8, 4
    run = p.add_run(text)
    set_run_font(run, size, bold=True)
    style_paragraph(p, before=before, after=after, line=1.15, align=WD_ALIGN_PARAGRAPH.LEFT)


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.15)
    bullet = p.add_run("- ")
    set_run_font(bullet, 11)
    run = p.add_run(text)
    set_run_font(run, 11)
    style_paragraph(p, after=4, line=1.15, align=WD_ALIGN_PARAGRAPH.LEFT)


def add_number(doc: Document, text: str) -> None:
    if not hasattr(add_number, "counter"):
        add_number.counter = 0  # type: ignore[attr-defined]
    add_number.counter += 1  # type: ignore[attr-defined]
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.15)
    prefix = p.add_run(f"{add_number.counter}. ")  # type: ignore[attr-defined]
    set_run_font(prefix, 11)
    run = p.add_run(text)
    set_run_font(run, 11)
    style_paragraph(p, after=4, line=1.15, align=WD_ALIGN_PARAGRAPH.LEFT)


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
        el.set(qn("w:color"), "DADCE0")


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    set_table_borders(table)
    for i, head in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(head)
        set_run_font(run, 10.5, bold=True)
        style_paragraph(p, after=2, line=1.0, align=WD_ALIGN_PARAGRAPH.LEFT)
        if widths:
            cell.width = Inches(widths[i])
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(value)
            set_run_font(run, 10.5)
            style_paragraph(p, after=2, line=1.0, align=WD_ALIGN_PARAGRAPH.LEFT)
            if widths:
                cells[i].width = Inches(widths[i])
    doc.add_paragraph()


def configure(doc: Document) -> None:
    for section in doc.sections:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        section.header_distance = Inches(0.492)
        section.footer_distance = Inches(0.492)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    styles["Normal"]._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    styles["Normal"].font.size = Pt(11)


def find_body_index_by_text(document: Document, needle: str) -> int:
    for idx, child in enumerate(document._body._element):
        if child.tag.endswith("}p"):
            text = "".join(node.text or "" for node in child.iter() if node.text)
            if needle in " ".join(text.split()):
                return idx
    raise ValueError(needle)


def start_from_original_cover() -> Document:
    doc = Document(str(ORIGINAL_DOC))
    body = doc._body._element
    cutoff = find_body_index_by_text(doc, "TABLE OF CONTENTS")
    for child in list(body)[cutoff:]:
        if child.tag.endswith("}sectPr"):
            continue
        body.remove(child)
    configure(doc)
    return doc


def add_toc(doc: Document) -> None:
    doc.add_page_break()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("TABLE OF CONTENTS")
    set_run_font(run, 16, bold=True)
    style_paragraph(p, after=10, align=WD_ALIGN_PARAGRAPH.CENTER)
    toc_lines = [
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
        "5.3 Module Interaction and Logic Design",
        "5.4 Data Design and Runtime Data Flow",
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
    for line in toc_lines:
        p = doc.add_paragraph()
        if line.startswith("CHAPTER") or line in {"APPENDICES", "REFERENCES"}:
            run = p.add_run(line)
            set_run_font(run, 11.5, bold=True)
            style_paragraph(p, before=4, after=3, align=WD_ALIGN_PARAGRAPH.LEFT)
        else:
            p.paragraph_format.left_indent = Inches(0.25)
            run = p.add_run(line)
            set_run_font(run, 10.5)
            style_paragraph(p, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
    doc.add_page_break()


def chapter1(doc: Document) -> list[int]:
    refs = [4, 8]
    add_number.counter = 0  # type: ignore[attr-defined]
    add_heading(doc, "CHAPTER 1 - INTRODUCTION", 1)
    add_heading(doc, "1.1 Introduction", 2)
    add_p(doc, "Phantom Scan is a WiFi Channel State Information sensing project that aims to detect human presence and present truthful live operator feedback without cameras or wearable devices. In its current repository state, the project is grounded in a two-node ESP32-S3 deployment connected to a laptop-hosted runtime, deterministic digital signal processing, JSONL-based recording and replay, and a React dashboard for monitoring and evaluation [8].")
    add_p(doc, "The practical relevance of this topic is high. Search-and-rescue, safety inspection, indoor monitoring, and privacy-sensitive awareness systems all benefit from the ability to infer human presence and movement behind common obstacles. Unlike vision-based systems, WiFi CSI sensing can operate in darkness and can offer a privacy-preserving modality because it does not rely on capturing faces, appearance, or scene imagery.")
    add_p(doc, "This report treats Phantom Scan not only as a research idea but as an actual software and embedded project. Therefore, the report emphasizes implementation truth, module boundaries, measured evidence, and explicit distinction between validated behavior and future work.")
    add_heading(doc, "1.2 Background", 2)
    add_p(doc, "Device-free wireless sensing has evolved from coarse received-signal-strength techniques toward CSI-based approaches that preserve much richer amplitude and phase information. CSI enables subcarrier-level reasoning about how the propagation environment changes when a person moves, breathes, or occupies a region within the RF field. This makes CSI especially suitable for privacy-first human detection and through-wall situational awareness.")
    add_p(doc, "Research systems such as DensePose from WiFi and later multi-person pose estimation studies established that commodity wireless signals can contain enough spatial information for more than binary occupancy classification [4]. At the same time, practical deployment remains difficult because environment drift, hardware variation, and honest live-state presentation are hard engineering problems even when research results are promising.")
    add_p(doc, "Phantom Scan builds on this research context but narrows the immediate implementation target. The repository no longer targets drone, GPS, IMU, or MAVLink integration in its active path. Instead, it focuses on a realistic ground-based two-node ESP32-S3 system where live UI behavior, replayability, deterministic DSP, and runtime observability are the main priorities [8].")
    add_heading(doc, "1.3 Problem Statement", 2)
    add_p(doc, "The project addresses the problem of creating a low-cost, privacy-preserving, through-wall-capable sensing system that can detect and present human activity using commodity WiFi hardware while avoiding false certainty. Existing approaches often depend on expensive radar platforms, opaque research-only pipelines, or UI behavior that does not clearly distinguish live truth, degraded state, stale state, and absent data.")
    add_p(doc, "For Phantom Scan, the problem is therefore dual: first, to build a technically valid sensing and transport stack using low-cost embedded hardware; and second, to build an operator-facing software system that remains honest about what the hardware has or has not actually observed.")
    add_heading(doc, "1.4 Limitations", 2)
    add_bullet(doc, "The currently validated hardware direction is exactly two ESP32-S3 nodes, not a large synchronized multistatic mesh [8].")
    add_bullet(doc, "The active live dashboard path is owned by the Node/TypeScript runtime; the Python runtime is important for replay and tooling but is not the default live dashboard authority in the current repo [8].")
    add_bullet(doc, "The fused position model is one-dimensional on the baseline between the two nodes, so off-axis targets are projected onto that axis rather than reconstructed as free-room 3D positions [11], [13].")
    add_bullet(doc, "Live hardware metrics such as true detection rate, live CSI frame rate over long sessions, and repeated midpoint accuracy remain dependent on attached hardware and cannot be claimed from software-only passes alone [11]-[14].")
    add_heading(doc, "1.5 Project Objectives", 2)
    add_number(doc, "Design and implement a working WiFi CSI sensing pipeline using two ESP32-S3 nodes and a laptop host.")
    add_number(doc, "Provide deterministic DSP and replayable JSONL workflows to support repeatable debugging, analysis, and testing.")
    add_number(doc, "Build a live dashboard that distinguishes truthful targets, degraded states, stale states, and empty-room silence.")
    add_number(doc, "Support optional AI-assisted analysis without allowing advisory AI output to silently replace deterministic authority.")
    add_number(doc, "Document the system in a way that maps claims directly to source files, tests, and verification artifacts.")
    add_heading(doc, "1.6 Project Solution Overview", 2)
    add_p(doc, "The implemented solution uses five major layers. The firmware layer captures CSI and sends live frames. The host ingest layer receives and validates packets and tracks node freshness. The deterministic DSP layer produces motion- and presence-relevant signals. The optional AI layer remains advisory and isolated. The API and UI layer publishes live state and renders it in a dashboard [8].")
    add_p(doc, "This layered solution reduces coupling across the repository and makes it possible to test individual responsibilities independently. It also supports the project’s goal of not promoting replay-only or no-packet states into false live detections.")
    add_heading(doc, "1.7 Project Scope", 2)
    add_p(doc, "Project Scope Covered:")
    add_bullet(doc, "Two-node ESP32-S3 firmware capture and UDP transport.")
    add_bullet(doc, "Node/TypeScript host ingest, target-state logic, HTTP APIs, and WebSocket publishing.")
    add_bullet(doc, "Python replay, protocol, DSP, and recording toolchain.")
    add_bullet(doc, "Operator-facing dashboard, history/report routes, and evidence-aware state presentation.")
    add_p(doc, "Project Scope Not Covered:")
    add_bullet(doc, "Airborne or drone deployment in the current active path.")
    add_bullet(doc, "MAVLink, GPS, IMU, or ego-motion compensation in the current validated implementation.")
    add_bullet(doc, "A production-scale multi-user backend with a heavyweight database server.")
    add_bullet(doc, "Fully validated free-room 3D localization from the current two-node geometry.")
    add_heading(doc, "1.8 Project Feasibility", 2)
    add_p(doc, "Technical feasibility is high because the repository already contains the source code, firmware tree, tests, run scripts, verification reports, and UI paths needed to operate the main software stack [8], [11], [15]. Operational feasibility is also good because the project is structured around an explicit operator workflow and makes degraded states visible instead of hiding them.")
    add_p(doc, "Economic feasibility is favorable because the sensing nodes are based on low-cost ESP32-S3 boards. Compared with specialized radar hardware, this lowers the barrier to experimentation and future deployment. The most significant feasibility risk is not software compilation but live repeatable room validation, because sensing results depend on active hardware, room geometry, and calibrated thresholds [11]-[14].")
    return refs


def chapter2(doc: Document) -> list[int]:
    refs = [1, 2, 3, 4, 5, 6, 7, 8]
    add_heading(doc, "CHAPTER 2 - LITERATURE REVIEW", 1)
    add_heading(doc, "2.1 Introduction", 2)
    add_p(doc, "Reviewing related work is essential because WiFi sensing is a rapidly evolving field in which different systems optimize for different goals: localization accuracy, physiological sensing, pose estimation, cross-site robustness, or low-cost deployment. Phantom Scan sits at the intersection of these goals, so it must be positioned against both foundational and recent systems.")
    add_heading(doc, "2.2 Review of Existing Systems", 2)
    add_heading(doc, "2.2.1 SpotFi Commodity WiFi Localization", 3)
    add_p(doc, "SpotFi demonstrated that commodity WiFi can achieve fine-grained localization by combining Angle of Arrival reasoning with channel measurements [1]. Its importance lies in proving that useful spatial inference is possible without custom radar hardware. However, SpotFi is centered on localization rather than a full operator-facing sensing stack with embedded-node capture, replay, degraded-state logic, and live evidence reporting.")
    add_heading(doc, "2.2.2 Through-Wall RF Sensing Systems", 3)
    add_p(doc, "Work on through-wall RF figure tracking showed that radio reflections can be used to infer human presence behind non-metallic obstacles [2]. This is directly relevant to Phantom Scan’s motivation because it validates the non-line-of-sight promise of radio sensing. The limitation is that such systems are often studied as research demonstrations, whereas Phantom Scan must also solve packaging, runtime monitoring, and software transparency concerns.")
    add_heading(doc, "2.2.3 Contactless Vital-Sign Monitoring", 3)
    add_p(doc, "Vital-Radio and related systems showed that RF signals can be used to estimate respiration and heart rate without body-worn sensors [3]. These systems are highly relevant to Phantom Scan’s physiological ambitions because they prove that small chest-motion signatures can be detected through radio propagation changes. Their narrower task scope, however, does not automatically solve deployment, UI, or multi-module software integration problems.")
    add_heading(doc, "2.2.4 WiFi-Based Pose Estimation", 3)
    add_p(doc, "DensePose from WiFi advanced the field by showing that CSI can support rich human pose understanding rather than simple occupancy classification [4]. Person-in-WiFi 3D extended the ambition to end-to-end multi-person 3D pose estimation [5]. These studies suggest that commodity WiFi can support detailed human-state inference, but they also reveal the difficulty of training data requirements, environment generalization, and reliable deployment outside controlled datasets.")
    add_heading(doc, "2.2.5 Cross-Site and Lightweight Systems", 3)
    add_p(doc, "AdaPose and HPE-Li address two practical problems that matter to a deployable system: cross-site generalization and lightweight inference [6], [7]. A model that works only in one room or only on one hardware profile is not enough for practical use. Phantom Scan benefits from this line of research but, in its current form, emphasizes truthful runtime design and replayability over claiming generalized learned performance.")
    add_heading(doc, "2.3 Comparison of Existing Solutions", 2)
    add_table(
        doc,
        ["System / Study", "Primary Goal", "Major Strengths", "Limitations Relative to Phantom Scan"],
        [
            ["SpotFi [1]", "Indoor localization", "Commodity WiFi, strong AoA reasoning", "Not an end-to-end embedded sensing and dashboard platform"],
            ["Through-wall RF tracking [2]", "Hidden human figure tracking", "Strong NLOS motivation and feasibility", "Research-oriented, less focused on deployable software workflow"],
            ["Vital-Radio [3]", "Respiration and heart-rate estimation", "Proven contactless physiology sensing", "Narrower scope than multi-layer live monitoring system"],
            ["DensePose from WiFi [4]", "Pose estimation from CSI", "Shows rich semantic potential of CSI", "High model complexity and environment sensitivity"],
            ["Person-in-WiFi 3D [5]", "Multi-person 3D pose estimation", "Ambitious state-of-the-art 3D inference", "Heavy training and validation burden"],
            ["AdaPose / HPE-Li [6], [7]", "Generalization and efficiency", "Improved portability and lighter architectures", "Still not a complete field-ready runtime and evidence stack"],
        ],
        widths=[1.4, 1.1, 1.6, 2.4],
    )
    add_p(doc, "The literature reveals a clear gap between research capability and implementation honesty. Many systems show what WiFi sensing can do under favorable conditions, but fewer show how a low-cost live system should behave when data is stale, hardware is missing, or a result is not yet empirically proven. Phantom Scan is shaped around that gap: it aims to be useful, low-cost, and transparent about the boundary between verified behavior and future capability [8].")
    return refs


def chapter3(doc: Document) -> list[int]:
    refs = [8, 9, 10, 11, 15]
    add_heading(doc, "CHAPTER 3 - METHODOLOGY AND WORK PLAN", 1)
    add_heading(doc, "3.1 Introduction", 2)
    add_p(doc, "The methodology of Phantom Scan must cover both research-style exploration and practical software engineering. This chapter explains how project requirements were derived, how development proceeded, and how milestones were planned so that the final system could be evaluated against concrete artifacts rather than informal claims.")
    add_heading(doc, "3.2 System Development Methodology", 2)
    add_p(doc, "A hybrid iterative methodology was used. The architecture and system boundaries were first documented in design sources and ADR-style notes, but implementation advanced through repeated cycles of coding, test execution, runtime inspection, and correction [9], [10]. This method is closer to Agile engineering than strict Waterfall because several important truths, such as the live ownership of UDP port 5005 and the distinction between authoritative and advisory paths, became clearer through implementation and verification.")
    add_p(doc, "The hybrid approach was necessary because Phantom Scan combines embedded firmware, Node/TypeScript runtime logic, Python replay tooling, and a web dashboard. A purely sequential process would have delayed the discovery of cross-layer truth issues, while a purely ad hoc process would not have produced auditable design and verification artifacts.")
    add_heading(doc, "3.3 Requirement Gathering Techniques", 2)
    add_bullet(doc, "Repository analysis of code structure, tests, and run scripts.")
    add_bullet(doc, "Review of project documentation such as README, architecture reports, and methodology notes.")
    add_bullet(doc, "Inspection of verification artifacts including software test reports, target verification notes, and hardware checklists.")
    add_bullet(doc, "Scenario-driven analysis focused on operator truthfulness, stale-state handling, and degraded-mode behavior.")
    add_p(doc, "These techniques were more appropriate than conventional stakeholder questionnaires because Phantom Scan’s most important requirements are encoded in its technical boundaries and evidence artifacts. For example, the requirement that the dashboard must not invent a target in the absence of live data is best discovered by inspecting the verification history rather than by asking for a high-level feature wish list [11], [12].")
    add_heading(doc, "3.4 Project Plan (Gantt Chart)", 2)
    add_table(
        doc,
        ["Phase", "Main Activities", "Expected Output"],
        [
            ["Phase 1", "Topic definition, background study, problem framing, feasibility review", "Chapter 1 and initial literature base"],
            ["Phase 2", "Related-work review and technical comparison", "Chapter 2"],
            ["Phase 3", "Methodology definition, requirement capture, milestone scheduling", "Chapters 3 and 4"],
            ["Phase 4", "Architecture and design modeling, UI and data-flow planning", "Chapter 5"],
            ["Phase 5", "Firmware, host runtime, replay tooling, and dashboard implementation", "Chapter 6"],
            ["Phase 6", "Testing, verification review, results analysis, recommendations", "Chapters 7 and 8 plus final report"],
        ],
        widths=[1.0, 3.7, 1.8],
    )
    add_p(doc, "The academic task sequence was aligned with the engineering sequence, but not rigidly identical to it. In practice, implementation work started before the final report text was complete, because meaningful results and discussion required real code, tests, and verification evidence.")
    add_heading(doc, "3.5 Development of Tools and Technologies", 2)
    add_heading(doc, "3.5.1 Programming Languages", 3)
    add_bullet(doc, "C for ESP32-S3 firmware and low-level board-side logic.")
    add_bullet(doc, "TypeScript for the live host runtime, APIs, and frontend code.")
    add_bullet(doc, "Python for replay, DSP tooling, protocol work, and automated tests [8], [15].")
    add_heading(doc, "3.5.2 Frameworks, Libraries, and Platforms", 3)
    add_bullet(doc, "ESP-IDF for firmware development.")
    add_bullet(doc, "Node.js, Express, and WebSocket-related runtime modules for live host behavior.")
    add_bullet(doc, "React and Vite for the operator dashboard.")
    add_bullet(doc, "TypeScript and pytest-based tests for regression and protocol verification.")
    add_heading(doc, "3.5.3 Hardware (Phase 1)", 3)
    add_bullet(doc, "Two ESP32-S3 CSI nodes as the active hardware direction.")
    add_bullet(doc, "Laptop host as the local processing and dashboard platform.")
    add_heading(doc, "3.5.4 Development Environment and Test Equipment", 3)
    add_p(doc, "The repository is oriented around Node.js 18+, Python 3.13, and ESP-IDF-compatible firmware development. The environment also includes validation artifacts for cases where full live firmware or board availability is limited, allowing software progress to continue while still recording what remains unmeasured [11], [15].")
    return refs


def chapter4(doc: Document) -> list[int]:
    refs = [8, 11, 12, 14]
    add_heading(doc, "CHAPTER 4 - SYSTEM SPECIFICATION", 1)
    add_heading(doc, "4.1 Introduction", 2)
    add_p(doc, "This chapter specifies what Phantom Scan must do and the quality conditions under which it must do it. Because the system deals with live sensing rather than a static transaction workflow, the specification must cover both runtime functionality and the trustworthiness of the operator-facing output.")
    add_heading(doc, "4.2 Functional Requirements", 2)
    add_table(
        doc,
        ["ID", "Functional Requirement", "Trace Rationale"],
        [
            ["FR1", "The firmware shall capture CSI-related information on ESP32-S3 nodes and transmit structured frames to the host.", "Required by the firmware and transport layers [8]"],
            ["FR2", "The live host shall ingest UDP packets on the authoritative live path and validate known frame types.", "Matches current Node/TS live ownership [8]"],
            ["FR3", "The host shall maintain per-node freshness, source pinning, and transport statistics.", "Needed for truthful live-state reasoning [11]"],
            ["FR4", "The system shall expose live sensing information over HTTP and WebSocket interfaces.", "Needed for dashboard integration [8]"],
            ["FR5", "The dashboard shall visualize node state, target state, and operator telemetry.", "Core operator-monitoring requirement [8], [14]"],
            ["FR6", "The system shall support degraded one-node behavior instead of fabricating fused two-node outputs.", "Explicit honesty requirement [11], [12]"],
            ["FR7", "The UI shall clear stale or absent targets after loss of live data.", "Required to avoid ghost targets [12], [14]"],
            ["FR8", "The project shall support replay and record-based workflows for debugging and analysis.", "Needed for repeatability and verification [8], [11]"],
            ["FR9", "Privileged actions shall require authenticated operator access.", "Required by the host API and operator console model"],
            ["FR10", "Optional AI outputs shall remain advisory when not fully validated as authoritative.", "Preserves deterministic truth boundary [11]"],
        ],
        widths=[0.55, 4.1, 1.85],
    )
    add_heading(doc, "4.3 Non-Functional Requirements", 2)
    add_heading(doc, "4.3.1 Performance", 3)
    add_p(doc, "The system must be responsive enough for live monitoring. The host runtime should process packets and publish updates fast enough that the operator dashboard remains useful in real time. Production build and test artifacts show that the software stack compiles and runs successfully, but live packet-rate claims still depend on active hardware sessions [11].")
    add_heading(doc, "4.3.2 Security", 3)
    add_p(doc, "Security requirements include authentication for privileged routes, protection against spoofed or mismatched data sources, and clear separation between advisory AI output and deterministic authority. Source pinning and route protection are especially important because a sensing UI can be misleading if the upstream data is not trusted [11].")
    add_heading(doc, "4.3.3 Usability", 3)
    add_p(doc, "The UI must be understandable to an operator under live conditions. This means node health, target state, degraded state, stale state, and empty-room silence all need distinct representations. A usable interface is not merely attractive; it has to support correct interpretation under uncertainty [12], [14].")
    add_heading(doc, "4.3.4 Reliability", 3)
    add_p(doc, "The system must degrade gracefully when nodes go offline, when live packets stop, or when a sidecar component is unavailable. It should continue to provide truthful partial information rather than fail into invented data. This is one of the strongest non-functional requirements in the project.")
    add_heading(doc, "4.3.5 Maintainability", 3)
    add_p(doc, "Modules should remain separated by responsibility across firmware, host runtime, replay tooling, and UI layers. This supports targeted testing, easier refactoring, and clearer ownership of live versus replay responsibilities [8], [15].")
    add_heading(doc, "4.3.6 Ethical and AI Aspects", 3)
    add_p(doc, "Phantom Scan is designed as a privacy-first sensing system. It avoids camera capture and emphasizes physics-based and deterministic evidence. For AI-specific ethics, the most important principle in the current repo is that advisory AI must not silently masquerade as proven truth. The system should indicate when an AI contribution is supporting, fallback, or unavailable [11].")
    return refs


def chapter5(doc: Document) -> list[int]:
    refs = [8, 9, 10, 16]
    add_heading(doc, "CHAPTER 5 - SYSTEM DESIGN", 1)
    add_heading(doc, "5.1 Introduction", 2)
    add_p(doc, "The system design of Phantom Scan translates the project requirements into a technical structure that guides implementation. The design focuses on clear layer separation, low-cost deployability, replayability, and operator truthfulness.")
    add_heading(doc, "5.2 System Architecture Design", 2)
    add_p(doc, "Phantom Scan is organized around five layers: firmware capture and transport, host ingest and replay-related transport logic, deterministic DSP, optional ML and inference support, and API/UI/monitoring [8]. This layered design allows the project to evolve individual parts without collapsing the whole system into one tightly coupled program.")
    add_table(
        doc,
        ["Layer", "Purpose", "Representative Files / Areas"],
        [
            ["Layer A - Firmware", "Capture CSI and transport device-side data", "firmware/esp32-csi-node/main/*.c"],
            ["Layer B - Host ingest and replay", "Parse packets, preserve timestamps, track per-node state", "server/lib/udp-server.ts, phantom/protocol.py, phantom/ingest.py"],
            ["Layer C - Deterministic DSP", "Derive motion and signal features from captured data", "phantom/dsp.py, scripts/csi_filter_pipeline.py"],
            ["Layer D - Optional ML", "Support advisory inference when enabled", "scripts/ai_inference.py, ai model and densepose/"],
            ["Layer E - API / UI", "Expose state and render the operator console", "server/, client/"],
        ],
        widths=[1.2, 2.0, 3.3],
    )
    add_heading(doc, "5.3 Module Interaction and Logic Design", 2)
    add_p(doc, "The live path begins with node-generated frames reaching the host UDP ingest layer. Valid packets are parsed, associated with their node source, and converted into runtime state. That runtime state is then published through a WebSocket stream consumed by the React dashboard. The dashboard in turn interprets the state according to explicit truth rules: a live fused target is different from a degraded one-node state, and a stale state is different from a cleared empty scene.")
    add_p(doc, "A parallel but distinct path exists for replay and tooling through the Python package. This path is important for deterministic analysis and testing, but the repository explicitly documents that it should not silently compete with the live dashboard path for the same port unless intentionally enabled [8].")
    add_heading(doc, "5.4 Data Design and Runtime Data Flow", 2)
    add_p(doc, "Phantom Scan does not use a conventional enterprise database in the current project scope. Instead, data design is centered on runtime packets, state models, JSONL recordings, and structured project artifacts. The choice is deliberate: the system is a sensing prototype focused on transport, analysis, and honest live presentation, not a multi-tenant transaction platform.")
    add_table(
        doc,
        ["Data Artifact", "Role in the System", "Persistence Strategy"],
        [
            ["Live UDP frames", "Carry node-originating measurement information", "Transient, consumed by live host"],
            ["Target state / node state", "Represent current dashboard truth", "In-memory during live session"],
            ["JSONL recordings", "Support replay and evidence review", "File-based, replayable"],
            ["Verification reports", "Document what has and has not been measured", "File-based project artifacts"],
            ["Operator/session state", "Control privileged access and run context", "Runtime + lightweight local storage"],
        ],
        widths=[1.5, 3.1, 1.9],
    )
    add_heading(doc, "5.5 User Interface (UI) Design", 2)
    add_p(doc, "The dashboard is intentionally designed as an operator interface rather than a consumer app. Its live scene, target indicators, node feature cards, top-level status controls, and auxiliary routes are intended to support technical interpretation. In design terms, this means that usefulness is derived from legibility and state distinction rather than decorative complexity.")
    add_bullet(doc, "Dashboard view for live scene and node state monitoring.")
    add_bullet(doc, "Login path for operator-authenticated access.")
    add_bullet(doc, "History, activity, and report-related routes for review workflows.")
    add_bullet(doc, "Board DSP and node-feature views to compare firmware-side and host-side signals [8].")
    add_heading(doc, "5.6 Summary", 2)
    add_p(doc, "The design of Phantom Scan is suitable for its current scope because it balances low-cost hardware, explicit software boundaries, and truth-aware operator presentation. It also leaves room for future scaling, but without pretending that the current two-node implementation is already a generalized multi-room or airborne system.")
    return refs


def chapter6(doc: Document) -> list[int]:
    refs = [8, 11, 12, 15, 16]
    add_heading(doc, "CHAPTER 6 - SYSTEM IMPLEMENTATION", 1)
    add_heading(doc, "6.1 Introduction", 2)
    add_p(doc, "This chapter explains how the design of Phantom Scan was turned into a working repository. The focus is on the actual codebase as it exists now: a ground-based two-node ESP32-S3 sensing stack with a Node/TypeScript live path, a Python replay and DSP toolchain, and a React dashboard [8].")
    add_heading(doc, "6.2 Implementation Overview", 2)
    add_p(doc, "Implementation is distributed across firmware, host runtime, Python tooling, shared schema/contracts, and the client UI. This is important because the project is not a single executable. Different parts can be started, tested, or validated in isolation, and several verification artifacts explicitly depend on this separation [11], [12], [15].")
    add_table(
        doc,
        ["Area", "Main Technologies", "Implementation Role"],
        [
            ["Firmware", "ESP-IDF, C", "Node-side CSI capture and transport"],
            ["Live host runtime", "Node.js, TypeScript, Express, WebSocket", "Authoritative live ingest, state publication, auth, audit"],
            ["Python toolchain", "Python 3.13, pytest", "Replay, DSP, protocol logic, tests"],
            ["Frontend", "React, TypeScript, Vite", "Operator dashboard and supporting views"],
            ["Shared contracts", "TypeScript schema/shared modules", "Keep wire and UI state consistent"],
        ],
        widths=[1.1, 2.2, 3.2],
    )
    add_heading(doc, "6.3 Implementation Details", 2)
    add_heading(doc, "6.3.1 User Authentication", 3)
    add_p(doc, "Authentication is implemented in the host runtime because privileged actions must not be exposed to any anonymous browser session. Session-backed route protection ensures that operator-level commands remain controlled. This design also supports auditability, which matters in a sensing system where configuration changes can affect trust in the observed outputs.")
    add_heading(doc, "6.3.2 Data and Persistence Integration", 3)
    add_p(doc, "The implementation relies on lightweight file-based persistence rather than a heavyweight standalone database server. Runtime state for the current session is held in memory, recordings are stored in replay-friendly files, and verification artifacts are kept as explicit project documents. This matches the prototype scope and keeps the evidence chain human-inspectable.")
    add_heading(doc, "6.3.3 User Interface Elements", 3)
    add_p(doc, "The React dashboard is composed of pages, hooks, and dashboard-specific components. The live scene is not just decorative; it is bound to runtime truth logic. For example, the client clears stale scenes after a defined timeout, and the UI distinguishes target visibility from degraded or absent state [8], [12].")
    add_heading(doc, "6.3.4 Functionality Modules", 3)
    add_table(
        doc,
        ["Module", "Current Implementation Behavior"],
        [
            ["UDP ingest", "Receives ADR-018 and related frames, validates them, and preserves transport semantics"],
            ["Target-state builder", "Constructs truthful state for fused, degraded, stale, or absent target conditions"],
            ["Node-fusion logic", "Supports two-node balance-based fused behavior and trend-related semantics"],
            ["Replay runtime", "Runs protocol parsing, DSP, and replay workflows in the Python toolchain"],
            ["Dashboard hooks", "Manage WebSocket state, clear stale data, and map backend frames into UI models"],
            ["Auth/audit path", "Controls operator-facing privileged behavior"],
        ],
        widths=[1.5, 4.9],
    )
    add_heading(doc, "6.4 Component Integration and Workflow", 2)
    add_p(doc, "The end-to-end workflow begins with node-generated frames reaching the host runtime on the authoritative live path. Those frames are parsed, associated with a node identity, and fed into state-building logic that decides whether the UI should render a fused target, a degraded one-node signal, a stale state, or nothing at all. This published state is then delivered to the dashboard over WebSocket, where it is rendered by React components and support hooks.")
    add_p(doc, "Replay and tooling workflows run in parallel through the Python package. They are essential for deterministic analysis and testing, but the repository warns against running live Python authority and the dashboard authority together on the same UDP port unless deliberately configured [8].")
    add_heading(doc, "6.5 Implementation Testing Support", 2)
    add_p(doc, "Implementation support is strong at the software level. The repository contains Node/TypeScript tests for parser and state logic, Python tests for protocol and runtime behavior, build commands, and project-specific verification notes [11], [12], [15]. This matters because the project’s core value is not only that it compiles, but that it can defend its live-state behavior against regressions such as ghost targets or silent source mismatches.")
    add_heading(doc, "6.6 Summary", 2)
    add_p(doc, "The implementation of Phantom Scan is substantial and multi-layered. It connects low-cost hardware capture, a live host authority, deterministic replay and DSP, and a browser-based operator interface. Its strongest engineering quality is the explicit handling of truth boundaries: what is live, what is degraded, what is replay, and what has not yet been measured.")
    return refs


def chapter7(doc: Document) -> list[int]:
    refs = [8, 11, 12, 13, 14]
    add_heading(doc, "CHAPTER 7 - RESULTS AND DISCUSSION", 1)
    add_heading(doc, "7.1 Introduction", 2)
    add_p(doc, "This chapter evaluates Phantom Scan using the evidence that exists in the repository: automated tests, runtime checks, hardware validation templates, and target verification notes. The goal is not to exaggerate project maturity, but to explain what has been proven and what remains pending.")
    add_heading(doc, "7.2 Data Collection and Research", 2)
    add_heading(doc, "7.2.1 Live Capture Environment", 3)
    add_p(doc, "The active project direction assumes a two-node ESP32-S3 live environment connected to a local host. The host-side dashboard path owns UDP port 5005 in normal live operation, while the Python path remains available for replay and tool-assisted analysis [8].")
    add_heading(doc, "7.2.2 Datasets Used for Evaluation", 3)
    add_p(doc, "Evaluation data in the current project is a mixture of software fixtures, recorded sessions, replay-oriented JSONL artifacts, committed test fixtures, and human-authored validation documents [11]-[14]. This mixed evidence is necessary because the project’s maturity is uneven across domains: software-level verification is strong, while repeated live room trials remain partially blocked by hardware availability and tooling conditions.")
    add_heading(doc, "7.3 System Testing and User Feedback", 2)
    add_heading(doc, "7.3.1 Functional Testing", 3)
    add_table(
        doc,
        ["Check", "Observed Result", "Interpretation"],
        [
            ["Python suite", "75 passed, 5 skipped, 6 warnings [11]", "Strong protocol/runtime regression coverage"],
            ["Node dashboard/server tests", "19 passing tests [11]", "Live parser and state-path logic are covered"],
            ["TypeScript check", "PASS [11]", "Codebase remains type-consistent"],
            ["Production build", "PASS with large chunk warning [11]", "Build output is valid, though optimization work remains possible"],
            ["Replay CLI", "PASS [11]", "Replay path supports deterministic analysis flow"],
        ],
        widths=[1.8, 2.0, 2.7],
    )
    add_heading(doc, "7.3.2 Non-Functional Testing", 3)
    add_p(doc, "Non-functional testing in Phantom Scan is strongly tied to trust and operability. Verification notes show that stale and absent target behavior were actively corrected so the dashboard does not fabricate point clouds or persistent fallback targets when live data disappears [12]. This is a critical usability and reliability outcome because a sensing dashboard that invents targets is worse than one that shows uncertainty honestly.")
    add_heading(doc, "7.3.3 Accuracy Characterisation (Scheduled Trials)", 3)
    add_p(doc, "The repository includes structured templates for real-hardware positional-fidelity, movement, and acceptance testing [13], [14]. These templates are important because they define what true validation should look like: empty-room calibration, negative controls, on-axis dwell checks, movement accuracy, trend validation, and robustness under confounds. However, several of those rows remain marked as to be measured, which means the project correctly avoids converting a template into a false claim of completion.")
    add_heading(doc, "7.3.4 User Feedback", 3)
    add_p(doc, "The current repo does not include a large survey-based user study. Instead, user-facing feedback is expressed through acceptance criteria and operator checklists. These documents emphasize the operator’s need to confirm that target dots align with real positions, stale data clears correctly, degraded mode hides unsupported skeletons, and empty-room scenes remain clean [14].")
    add_heading(doc, "7.4 Discussion", 2)
    add_p(doc, "The results indicate that Phantom Scan is strong as a software and systems-engineering project. The code compiles, tests pass, runtime boundaries are clearer, and the dashboard truth model has been improved [11], [12]. The project is also strong in documentation discipline because it explicitly marks what has not yet been measured rather than implying that all live hardware claims are complete.")
    add_p(doc, "At the same time, the evidence shows that live sensing maturity is not yet symmetrical with software maturity. Several hardware-dependent validations, including long-duration packet-rate confirmation, repeated two-node live midpoint checks, and richer live scene acceptance runs, remain dependent on actual active board sessions [11], [13], [14]. This does not weaken the project’s value; it clarifies where the next milestone work must be concentrated.")
    return refs


def chapter8(doc: Document) -> list[int]:
    refs = [8, 11, 12, 13, 14]
    add_number.counter = 0  # type: ignore[attr-defined]
    add_heading(doc, "CHAPTER 8 - RECOMMENDATIONS AND CONCLUSION", 1)
    add_heading(doc, "8.1 Introduction", 2)
    add_p(doc, "This chapter concludes the report by summarizing what Phantom Scan has achieved, identifying the principal limitations that remain, and recommending how the project should move forward.")
    add_heading(doc, "8.2 Conclusion", 2)
    add_p(doc, "Phantom Scan successfully demonstrates a realistic WiFi CSI sensing architecture built from commodity hardware and a multi-layer software stack. Its current form combines two ESP32-S3 sensing nodes, a Node/TypeScript live authority, a Python replay and DSP toolchain, and a React operator dashboard [8].")
    add_p(doc, "The strongest contribution of the project is not a single algorithm but the way the repository integrates sensing, testing, and truthful presentation. Instead of hiding absent data behind synthetic fallback behavior, the project now emphasizes degraded states, stale clearing, and evidence-backed claims [11], [12]. This makes it a stronger academic and engineering artifact than a system that appears more capable on paper but is less honest in operation.")
    add_heading(doc, "8.3 Limitations and Recommendations for Future Work", 2)
    add_heading(doc, "8.3.1 Limitations", 3)
    add_bullet(doc, "The validated geometry is still limited to a two-node baseline rather than full free-room multistatic reconstruction.")
    add_bullet(doc, "Several critical live metrics remain hardware-dependent and not fully closed in the repository evidence [11], [13], [14].")
    add_bullet(doc, "Cross-site calibration and threshold portability remain open engineering challenges.")
    add_bullet(doc, "The active authoritative live path and the Python path are still split across responsibilities, which is manageable but not yet fully unified.")
    add_heading(doc, "8.3.2 Recommendations for Future Work", 3)
    add_number(doc, "Run repeated real two-node trials and populate the scheduled validation templates with measured values rather than placeholders.")
    add_number(doc, "Improve off-axis handling and move beyond a one-dimensional baseline projection model.")
    add_number(doc, "Expand live-room calibration tools and negative-control evaluation for empty-room robustness.")
    add_number(doc, "Continue hardening the AI boundary so advisory components remain helpful without weakening deterministic trust.")
    add_number(doc, "Consider a later architectural convergence between the live authority and replay authority where that reduces complexity without reintroducing ambiguity.")
    add_heading(doc, "8.4 Summary", 2)
    add_p(doc, "Phantom Scan is already a substantial graduation-project implementation. Its next stage should focus less on adding speculative features and more on closing repeated live hardware proof, because that is the main remaining gap between current software strength and full sensing confidence.")
    return refs


def appendices(doc: Document) -> list[int]:
    refs = [8, 11, 15]
    add_heading(doc, "APPENDICES", 1)
    add_heading(doc, "Appendix A - Repository Structure Summary", 2)
    add_table(
        doc,
        ["Path", "Purpose"],
        [
            ["client/", "React dashboard and operator-facing routes"],
            ["server/", "Node/TypeScript live host runtime, APIs, auth, audit, UDP and WebSocket paths"],
            ["phantom/", "Python replay, protocol, DSP, recording, and runtime tooling"],
            ["firmware/esp32-csi-node/", "ESP32-S3 firmware project and related node artifacts"],
            ["shared/", "Shared contracts and schema information used across runtime paths"],
            ["tests/", "Python regression tests and fixtures"],
            ["docs/", "Architecture notes, ADRs, and supporting technical materials"],
        ],
        widths=[2.1, 4.4],
    )
    add_heading(doc, "Appendix B - Verification Snapshot", 2)
    add_table(
        doc,
        ["Area", "Snapshot"],
        [
            ["Software tests", "Python suite passed, Node/dashboard tests passed, TypeScript check passed, build passed [11]"],
            ["Replay", "Replay CLI passed in the recorded validation pass [11]"],
            ["Live dashboard path", "Authoritative Node/TS path owns live UDP behavior in normal use [8]"],
            ["Hardware proof", "Several core live metrics remain marked to be measured [11], [13], [14]"],
        ],
        widths=[1.8, 4.7],
    )
    return refs


def add_references(doc: Document, refs: list[int]) -> None:
    add_heading(doc, "REFERENCES", 1)
    for ref_id in refs:
        p = doc.add_paragraph()
        run = p.add_run(f"[{ref_id}] {REFERENCES[ref_id]}")
        set_run_font(run, 11)
        style_paragraph(p, after=4, align=WD_ALIGN_PARAGRAPH.LEFT)


def build() -> Path:
    doc = start_from_original_cover()
    add_toc(doc)
    all_refs: list[int] = []
    for builder in [chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8, appendices]:
        all_refs.extend(builder(doc))
        doc.add_section(WD_SECTION.NEW_PAGE)
    ordered: list[int] = []
    for ref_id in all_refs:
        if ref_id not in ordered:
            ordered.append(ref_id)
    add_references(doc, ordered)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_DOC))
    return OUTPUT_DOC


if __name__ == "__main__":
    print(build())
