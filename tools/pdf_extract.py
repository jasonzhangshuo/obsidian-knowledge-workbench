"""Extract one PDF locally with physical pages and optional Chinese lesson markers."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def split_pages(text):
    pages = text.split("\f")
    if not pages[-1].strip():
        pages.pop()
    return pages


def chapter_spans(pages):
    """Accept standalone 【…课】 headings, excluding dotted table-of-contents rows."""
    text, starts = "", []
    for number, page in enumerate(pages, 1):
        prefix = f"\n\n## PDF物理页 {number}\n\n"
        base = len(text) + len(prefix)
        text += prefix + page
        for match in re.finditer(r"^[ \t]*【([^】\n]{1,24}课)】[ \t]*$", page, re.M):
            starts.append((number, base + match.start(), match[0].strip()))
    return [{"lesson": i + 1, "title": heading, "start_pdf_page": page,
             "end_pdf_page": starts[i + 1][0] if i + 1 < len(starts) else len(pages),
             "text": f"# {heading}，起始PDF物理页 {page}\n\n" + text[start:starts[i + 1][1] if i + 1 < len(starts) else len(text)]}
            for i, (page, start, heading) in enumerate(starts)]


def extract(pdf, output):
    pdf, output = Path(pdf).resolve(), Path(output)
    if not pdf.is_file():
        raise ValueError("PDF does not exist")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be new or empty; existing raw material is never overwritten")
    run = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, check=True)
    text = run.stdout.decode("utf-8")
    pages = split_pages(text)
    if not pages or not any(p.strip() for p in pages):
        raise ValueError("No embedded text extracted; OCR/visual review is a separate step")
    output.mkdir(parents=True, exist_ok=True)
    (output / "full-layout.txt").write_text(text, encoding="utf-8")
    coverage = []
    for number, page in enumerate(pages, 1):
        (output / f"page-{number:03}.txt").write_text(page, encoding="utf-8")
        coverage.append({"page": number, "characters": len(page.strip()),
                         "sha256": hashlib.sha256(page.encode()).hexdigest()})
    chapters = chapter_spans(pages)
    if chapters:
        (output / "lessons").mkdir()
    for item in chapters:
        content = item.pop("text")
        name = f"lessons/lesson-{item['lesson']:03}.txt"
        (output / name).write_text(content, encoding="utf-8")
        item.update(file=name, characters=len(content), sha256=hashlib.sha256(content.encode()).hexdigest())
    manifest = {"source_name": pdf.name, "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "pages": len(pages), "characters": len(text), "extraction": "pdftotext -layout; no OCR",
                "empty_pages": [x["page"] for x in coverage if not x["characters"]],
                "page_coverage": coverage, "lessons": chapters,
                "semantic_review": "not performed"}
    (output / "extraction.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.pdf, args.output)
    print(json.dumps({"pages": result["pages"], "lessons": len(result["lessons"]),
                      "source_sha256": result["source_sha256"], "empty_pages": result["empty_pages"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
