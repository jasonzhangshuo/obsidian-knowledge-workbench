"""Read-only checks for one compiled book; never traverse an entire Vault."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote


def normal(text):
    """Ignore layout whitespace, preserving numbers and punctuation."""
    return "".join(text.split())


def contained(path, root):
    return path.resolve().is_relative_to(root.resolve())


def read_pages(directory):
    files = sorted(Path(directory).glob("page-*.txt"))
    if not files:
        raise ValueError("No page-NNN.txt source files found")
    return {int(p.stem[5:]): p.read_text(encoding="utf-8") for p in files}


def quote_checks(notes, pages, minimum=4):
    checks = []
    for path in notes:
        text = path.read_text(encoding="utf-8")
        section = re.search(
            r"#{2,3}\s*(?:PDF\s*证据|页证据|原文证据)\s*\n(.*?)(?=\n#{2,3} |\Z)",
            text,
            re.S,
        )
        if not section:
            continue
        for line in section[1].splitlines():
            if not line.startswith("- "):
                continue
            match = re.search(r"PDF物理页\s*(\d+)(?:[—–\-至、]\s*(\d+))?", line)
            if not match:
                continue
            first, last = int(match[1]), int(match[2] or match[1])
            if first > last or last - first > len(pages):
                raise ValueError(f"Invalid page range in {path.name}")
            claimed = list(range(first, last + 1))
            for quote in re.findall(r"“([^”]+)”", line):
                if len(normal(quote)) < minimum:
                    continue
                hits = [n for n, text in pages.items() if normal(quote) in normal(text)]
                checks.append({
                    "file": str(path), "quote": quote, "claimed_pages": claimed,
                    "matching_pages": hits, "valid": bool(set(hits) & set(claimed)),
                })
    return checks


def book_notes(book, vault):
    book, vault = Path(book).resolve(), Path(vault).resolve()
    if book == vault or not contained(book, vault) or "_private" in book.relative_to(vault).parts:
        raise ValueError("Select a specific book inside the Vault, outside _private")
    files = []
    for path in book.rglob("*.md"):
        if path.is_symlink() or not contained(path, book):
            raise ValueError(f"A note escapes the book directory: {path}")
        files.append(path)
    if not files:
        raise ValueError("No book notes found")
    return sorted(files)


def link_checks(notes, vault):
    vault = Path(vault).resolve()
    failures = []
    for path in notes:
        text = path.read_text(encoding="utf-8")
        targets = [(m, True) for m in re.findall(r"\[\[([^\]]+)\]\]", text)]
        targets += [(m, False) for m in re.findall(r"\]\(([^)]+)\)", text)]
        for raw, wiki in targets:
            target = raw.split("|", 1)[0] if wiki else raw.strip("<>")
            if re.match(r"^(?:https?://|mailto:|#)", target):
                continue
            target = unquote(target.split("#", 1)[0])
            if not target:
                continue
            dest = (vault if wiki else path.parent) / target
            choices = [dest] if dest.suffix else [dest.with_suffix(".md"), dest]
            safe = all(contained(p, vault) and "_private" not in p.resolve().relative_to(vault).parts for p in choices)
            if not safe or not any(p.exists() for p in choices):
                failures.append({"file": str(path), "target": raw, "reason": "missing or outside allowed Vault scope"})
    return failures


def query_checks(answers, pages):
    checks = []
    for answer in answers["answers"]:
        for item in answer["evidence"]:
            quote, page = item["quote"], item["pdf_page"]
            checks.append({"id": answer["id"], "pdf_page": page, "quote": quote,
                           "valid": bool(normal(quote)) and normal(quote) in normal(pages.get(page, ""))})
    return checks


def read_coverage(source_files, event_file):
    """A claimed read is insufficient: full source text must appear in tool output."""
    outputs = []
    with Path(event_file).open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") == "command_execution" and item.get("exit_code") == 0:
                outputs.append(item.get("aggregated_output", ""))
    result = {}
    for source in source_files:
        text = source.read_text(encoding="utf-8").strip()
        result[str(source)] = bool(text) and any(text in output for output in outputs)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", required=True, type=Path, help="One book's extracted page directory")
    parser.add_argument("--book", type=Path)
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--chapter-sources", type=Path)
    parser.add_argument("--report", type=Path, help="Explicit output location; no implicit Vault writes")
    args = parser.parse_args()
    pages = read_pages(args.pages)
    result = {"source_pages": len(pages)}
    if args.book:
        if not args.vault:
            parser.error("--book requires --vault")
        notes = book_notes(args.book, args.vault)
        result.update(notes=len(notes), quotes=quote_checks(notes, pages), broken_links=link_checks(notes, args.vault))
    if args.answers:
        result["query_quotes"] = query_checks(json.loads(args.answers.read_text(encoding="utf-8")), pages)
    if args.events:
        if not args.chapter_sources:
            parser.error("--events requires --chapter-sources")
        sources = sorted(p for p in args.chapter_sources.glob("lesson-*") if p.suffix in {".md", ".txt"})
        if not sources:
            parser.error("No chapter sources found")
        result["full_read_coverage"] = read_coverage(sources, args.events)
    if not any([args.book, args.answers, args.events]):
        parser.error("Select --book, --answers or --events")
    failed = bool(result.get("broken_links")) or any(not x["valid"] for key in ["quotes", "query_quotes"] for x in result.get(key, []))
    failed |= any(not ok for ok in result.get("full_read_coverage", {}).values())
    result["passed"] = not failed
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
