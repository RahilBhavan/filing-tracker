"""Reproducible text views of issuer DOCX/PDF originals; never edit originals."""

import html
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def text_of(element):
    return "".join(node.text or "" for node in element.findall(".//w:t", NS))


def docx_html(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", NS)
    all_paragraphs = root.findall(".//w:p", NS)
    numbers = {id(p): i for i, p in enumerate(all_paragraphs, 1)}
    output = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Text view of issuer DOCX</title><body>']

    def paragraph(p):
        text = text_of(p)
        if not text.strip():
            return
        runs = [r for r in p.findall("w:r", NS) if text_of(r).strip()]
        bold = bool(runs) and all(r.find("w:rPr/w:b", NS) is not None for r in runs)
        short = len(text.split()) < 28
        heading = (short and (bold or text.strip().isupper())) or re.match(r"^ITEM\s+\d", text, re.I)
        tag = "h3" if heading else "p"
        i = numbers[id(p)]
        output.append('<%s id="docx-p%05d" data-source-locator="word/document.xml paragraph %d">%s</%s>' %
                      (tag, i, i, html.escape(text), tag))

    for child in body:
        if child.tag == "{%s}p" % NS["w"]:
            paragraph(child)
        elif child.tag == "{%s}tbl" % NS["w"]:
            output.append("<table>")
            for row in child.findall("w:tr", NS):
                cells = row.findall("w:tc", NS)
                content = [" ".join(text_of(p) for p in cell.findall(".//w:p", NS)).strip() for cell in cells]
                if not any(content):
                    continue
                ps = row.findall(".//w:p", NS)
                i = numbers[id(ps[0])]
                output.append('<tr id="docx-p%05d" data-source-locator="word/document.xml table row beginning at paragraph %d">%s</tr>' %
                              (i, i, "".join("<td>%s</td>" % html.escape(t) for t in content)))
            output.append("</table>")
        else:
            for p in child.findall(".//w:p", NS):
                paragraph(p)
    output.append("</body></html>")
    return "\n".join(output) + "\n"


def pdf_html(path, executable="pdftotext"):
    result = subprocess.run([executable, "-bbox-layout", str(path), "-"], capture_output=True, check=True)
    tree = ET.fromstring(result.stdout)
    ns = {"h": "http://www.w3.org/1999/xhtml"}
    output = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Text view of issuer PDF</title><body>']
    for page_no, page in enumerate(tree.findall(".//h:page", ns), 1):
        for index, block in enumerate(page.findall(".//h:block", ns), 1):
            text = " ".join(word.text or "" for word in block.findall(".//h:word", ns))
            if not text or re.fullmatch(r"K-\d+|\d+", text):
                continue
            lines = block.findall("h:line", ns)
            heading = bool(re.match(r"^Item\s+\d", text, re.I)) or (len(lines) == 1 and len(text) < 175 and not re.search(r"\d", text))
            tag = "h3" if heading else "p"
            locator = "PDF page %d, block %d, bbox %s" % (page_no, index, ",".join(block.get(k, "") for k in ("xMin", "yMin", "xMax", "yMax")))
            output.append('<%s id="pdf-p%03d-b%03d" data-page="%d" data-source-locator="%s">%s</%s>' %
                          (tag, page_no, index, page_no, locator, html.escape(text), tag))
    output.append("</body></html>")
    return "\n".join(output) + "\n"


def convert(path, destination):
    path, destination = Path(path), Path(destination)
    rendered = docx_html(path) if path.suffix == ".docx" else pdf_html(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    return destination
