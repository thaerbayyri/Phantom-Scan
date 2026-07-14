"""Build PhantomScan_FINAL_FULL_DETAILED.docx.

Starts from the original course document's cover pages (external ORIGINAL_DOC),
then appends the table of contents, Chapters 1-8, the full source-code
appendices, and References - all sourced from build_academic_reports.py so the
template-based document and the milestone deliverables can never diverge.

Run with Python 3.13 (vendored .docx_deps binaries are cp313-only):
    python scripts/build_detailed_final_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DEPS = ROOT / ".docx_deps"
for entry in (str(DEPS), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from docx import Document  # type: ignore

import build_academic_reports as content


ORIGINAL_DOC = Path(r"d:\my cours\RESEARCH PROJECT 2\PhantomScan_FINAL -docunent .docx")
OUTPUT_DIR = ROOT / "generated_reports"
OUTPUT_DOC = OUTPUT_DIR / "PhantomScan_FINAL_FULL_DETAILED.docx"


def find_body_index_by_text(document: Document, needle: str) -> int:
    for idx, child in enumerate(document._body._element):
        if child.tag.endswith("}p"):
            text = "".join(node.text or "" for node in child.iter() if node.text)
            if needle in " ".join(text.split()):
                return idx
    raise ValueError(needle)


def start_from_original_cover() -> Document:
    """Load the course document and drop everything from its TOC onward."""
    doc = Document(str(ORIGINAL_DOC))
    body = doc._body._element
    cutoff = find_body_index_by_text(doc, "TABLE OF CONTENTS")
    for child in list(body)[cutoff:]:
        if child.tag.endswith("}sectPr"):
            continue
        body.remove(child)
    for section in doc.sections:
        section.page_width = content.Inches(8.5)
        section.page_height = content.Inches(11)
        section.top_margin = content.Inches(1)
        section.bottom_margin = content.Inches(1)
        section.left_margin = content.Inches(1)
        section.right_margin = content.Inches(1)
    return doc


def build() -> Path:
    doc = start_from_original_cover()
    doc.add_page_break()
    content.add_toc_page(doc)
    doc.add_page_break()

    all_refs: list[int] = []
    for builder in content.CHAPTER_BUILDERS:
        all_refs.extend(builder(doc))
        doc.add_section(content.WD_SECTION.NEW_PAGE)
    all_refs.extend(content.appendices_full_source(doc))
    doc.add_section(content.WD_SECTION.NEW_PAGE)
    content.add_reference_section(doc, sorted(set(all_refs)))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_DOC))
    return OUTPUT_DOC


if __name__ == "__main__":
    print(build())
