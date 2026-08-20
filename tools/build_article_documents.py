"""Build the two reviewed manuscripts from their canonical text sources."""
from __future__ import annotations

import re
from pathlib import Path
from shutil import copy2

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
BTECH_SOURCE = ROOT / "paper" / "fucape_btech_2026.md"
BTECH_TEMPLATE = OUTPUTS / "Benevente_Wealth_System_BTECH.docx"
BTECH_OUTPUT = OUTPUTS / "Benevente_Wealth_System_BTECH_Final.docx"
IEEE_SOURCE = ROOT / "paper" / "ieee_cifer_2027.tex"
IEEE_OUTPUT = OUTPUTS / "Benevente_Quant_AI_IEEE_Final.tex"


def clear_body(document: Document) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def set_cell_shading(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shade = properties.find(qn("w:shd"))
    if shade is None:
        shade = OxmlElement("w:shd"); properties.append(shade)
    shade.set(qn("w:fill"), fill)


def add_inline(paragraph, text: str) -> None:
    cursor = 0
    pattern = re.compile(r"(\*\*.+?\*\*|`.+?`|\*[^*]+?\*)")
    for match in pattern.finditer(text):
        if match.start() > cursor:
            paragraph.add_run(text[cursor:match.start()])
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2]); run.bold = True
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1]); run.font.name = "Courier New"; run.font.size = Pt(9)
        else:
            run = paragraph.add_run(token[1:-1]); run.italic = True
        cursor = match.end()
    if cursor < len(text):
        paragraph.add_run(text[cursor:])


def add_table(document: Document, lines: list[str]) -> None:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    rows = [row for index, row in enumerate(rows) if index != 1]
    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    if "Table Grid" in [style.name for style in document.styles]: table.style = "Table Grid"
    for row_index, values in enumerate(rows):
        row_properties = table.rows[row_index]._tr.get_or_add_trPr()
        cannot_split = OxmlElement("w:cantSplit"); row_properties.append(cannot_split)
        if row_index == 0:
            repeat_header = OxmlElement("w:tblHeader"); repeat_header.set(qn("w:val"), "true"); row_properties.append(repeat_header)
        for cell, value in zip(table.rows[row_index].cells, values):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]; paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_inline(paragraph, value)
            for run in paragraph.runs:
                run.font.name = "Times New Roman"; run.font.size = Pt(9)
                if row_index == 0: run.bold = True
            if row_index == 0: set_cell_shading(cell, "D9E7E5")
    document.add_paragraph()


def markdown_blocks(text: str):
    lines = text.splitlines(); index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line or line.strip() == "---": index += 1; continue
        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|?\s*:?-+", lines[index + 1]):
            table = [line, lines[index + 1]]; index += 2
            while index < len(lines) and lines[index].startswith("|"):
                table.append(lines[index]); index += 1
            yield "table", table; continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#")); yield f"h{level}", line[level:].strip(); index += 1; continue
        if re.match(r"^[-*] ", line): yield "bullet", re.sub(r"^[-*] ", "", line); index += 1; continue
        if re.match(r"^\d+\. ", line): yield "number", line; index += 1; continue
        paragraph = [line]; index += 1
        while index < len(lines):
            next_line = lines[index].rstrip()
            if (not next_line or next_line.startswith("#") or next_line.startswith("|") or
                    re.match(r"^[-*] ", next_line) or re.match(r"^\d+\. ", next_line) or next_line.strip() == "---"):
                break
            paragraph.append(next_line); index += 1
        yield "paragraph", " ".join(paragraph)


def configure_document(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Cm(21.0); section.page_height = Cm(29.7)
    section.top_margin = Cm(3); section.left_margin = Cm(3)
    section.bottom_margin = Cm(2); section.right_margin = Cm(2)
    normal = document.styles["normal"]
    normal.font.name = "Times New Roman"; normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5; normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for name, size in (("Heading 1", 14), ("Heading 2", 13), ("Heading 3", 12)):
        style = document.styles[name]
        style.font.name = "Times New Roman"; style.font.size = Pt(size); style.font.bold = True
        style.paragraph_format.space_before = Pt(12); style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True


def build_btech() -> None:
    if not BTECH_TEMPLATE.exists(): raise FileNotFoundError("The retained BTech-formatted DOCX is missing.")
    copy2(BTECH_TEMPLATE, BTECH_OUTPUT)
    document = Document(BTECH_OUTPUT); clear_body(document); configure_document(document)
    in_references = False
    for kind, content in markdown_blocks(BTECH_SOURCE.read_text(encoding="utf-8")):
        if kind == "table": add_table(document, content); continue
        if kind == "h1":
            paragraph = document.add_paragraph(style="Heading 1"); paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_before = Pt(0)
        elif kind in {"h2", "h3"}:
            paragraph = document.add_paragraph(style="Heading 1" if kind == "h2" else "Heading 2")
            if kind == "h2" and content == "Referências":
                in_references = True
        elif kind in {"bullet", "number"}:
            paragraph = document.add_paragraph(style="normal")
            paragraph.paragraph_format.left_indent = Cm(0.65); paragraph.paragraph_format.first_line_indent = Cm(-0.4)
            paragraph.paragraph_format.line_spacing = 1.5
            content = ("• " + content) if kind == "bullet" else content
        else:
            paragraph = document.add_paragraph(style="Normal")
            if in_references:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                paragraph.paragraph_format.left_indent = Cm(0.75)
                paragraph.paragraph_format.first_line_indent = Cm(-0.75)
        add_inline(paragraph, content)
    document.core_properties.author = ""; document.core_properties.last_modified_by = ""
    document.core_properties.title = "Benevente Wealth System"; document.core_properties.subject = "Manuscrito tecnológico BTech 2026"
    temporary = BTECH_OUTPUT.with_suffix(".tmp.docx"); document.save(temporary); temporary.replace(BTECH_OUTPUT)


def build_ieee() -> None:
    text = IEEE_SOURCE.read_text(encoding="utf-8")
    if "\\documentclass[10pt,conference]{IEEEtran}" not in text: raise ValueError("IEEE manuscript is not using the conference template")
    if "MVO is an independent benchmark" not in text: raise ValueError("The canonical role contract is missing from the IEEE manuscript")
    copy2(IEEE_SOURCE, IEEE_OUTPUT)


if __name__ == "__main__":
    OUTPUTS.mkdir(exist_ok=True); build_btech(); build_ieee()
    print(BTECH_OUTPUT); print(IEEE_OUTPUT)
