from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".docx_deps"
if str(DEPS) not in sys.path:
    sys.path.insert(0, str(DEPS))

from docx import Document  # type: ignore
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


ORIGINAL_DOC = Path(r"d:\my cours\RESEARCH PROJECT 2\PhantomScan_FINAL -docunent .docx")
SOURCE_DOC = ROOT / "generated_reports" / "Final-Phantom-Scan-Project-Report.docx"
OUTPUT_DOC = ROOT / "generated_reports" / "PhantomScan_FINAL -docunent - edited.docx"


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
    "5.3 Class Diagram",
    "5.4 Database Design",
    "5.5 User Interface (UI) Design",
    "5.6 Summary",
    "CHAPTER 6 - SYSTEM IMPLEMENTATION",
    "6.1 Introduction",
    "6.2 Implementation Overview",
    "6.3 Implementation Details",
    "6.4 Integration and Verification",
    "CHAPTER 7 - RESULTS AND DISCUSSION",
    "7.1 Introduction",
    "7.2 Data Collection and Research",
    "7.3 System Testing and User Feedback",
    "CHAPTER 8 - RECOMMENDATIONS AND CONCLUSION",
    "8.1 Introduction",
    "8.2 Conclusion",
    "8.3 Limitations and Recommendations for Future Work",
    "REFERENCES",
]


def set_run_font(run, size: float = 11, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def style_paragraph(paragraph, size: float = 11, after: int = 6, bold: bool = False) -> None:
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = 1.15
    for run in paragraph.runs:
        set_run_font(run, size=size, bold=(bold or bool(run.bold)), italic=bool(run.italic))


def find_body_index_by_text(document: Document, needle: str) -> int:
    for idx, child in enumerate(document._body._element):
        if child.tag.endswith("}p"):
            text = "".join(node.text or "" for node in child.iter() if node.text)
            if needle in " ".join(text.split()):
                return idx
    raise ValueError(f"Could not find marker: {needle}")


def keep_cover_only(document: Document) -> None:
    body = document._body._element
    cutoff = find_body_index_by_text(document, "TABLE OF CONTENTS")
    children = list(body)
    for child in children[cutoff:]:
        if child.tag.endswith("}sectPr"):
            continue
        body.remove(child)


def append_toc(document: Document) -> None:
    document.add_page_break()
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("TABLE OF CONTENTS")
    style_paragraph(title, size=16, after=10, bold=True)

    for line in TOC_LINES:
        paragraph = document.add_paragraph()
        if line.startswith("CHAPTER") or line == "REFERENCES":
            paragraph.paragraph_format.space_before = Pt(6)
            paragraph.add_run(line)
            style_paragraph(paragraph, size=11.5, after=3, bold=True)
        else:
            paragraph.paragraph_format.left_indent = Pt(18)
            paragraph.add_run(line)
            style_paragraph(paragraph, size=10.5, after=2)

    document.add_page_break()


def append_source_body(target: Document, source: Document) -> None:
    source_body = source._body._element
    start = find_body_index_by_text(source, "CHAPTER 1 - INTRODUCTION")
    target_body = target._body._element

    for child in list(source_body)[start:]:
        if child.tag.endswith("}sectPr"):
            continue
        target_body.append(deepcopy(child))


def main() -> None:
    if not ORIGINAL_DOC.exists():
        raise FileNotFoundError(ORIGINAL_DOC)
    if not SOURCE_DOC.exists():
        raise FileNotFoundError(SOURCE_DOC)

    target = Document(str(ORIGINAL_DOC))
    source = Document(str(SOURCE_DOC))

    keep_cover_only(target)
    append_toc(target)
    append_source_body(target, source)

    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    target.save(str(OUTPUT_DOC))
    print(OUTPUT_DOC)


if __name__ == "__main__":
    main()
