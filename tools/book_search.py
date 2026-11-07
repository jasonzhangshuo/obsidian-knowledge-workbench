"""Read and search the explicitly selected book in an Obsidian Vault."""

import hashlib
import json
import re
from pathlib import Path

import yaml

from book_wiki_audit import normal


class BookError(ValueError):
    """A tool input or corpus error that can be shown to the caller."""


def _terms(terms, limit):
    if type(limit) is not int or not 1 <= limit <= 20:
        raise BookError("invalid limit: expected an integer from 1 to 20")
    if not isinstance(terms, list) or not 1 <= len(terms) <= 8:
        raise BookError("invalid terms: provide one to eight short search phrases")
    patterns = {}
    for term in terms:
        if not isinstance(term, str) or not term.strip() or len(term) > 120:
            raise BookError("invalid term: expected a nonempty phrase of up to 120 characters")
        compact = normal(term)
        patterns[term.strip()] = re.compile(r"\s*".join(map(re.escape, compact)), re.IGNORECASE)
    return patterns


def _excerpt(text, match):
    return text[max(0, match.start() - 70):match.end() + 110].strip()


def _frontmatter(text):
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        return {}, text
    try:
        fields = yaml.safe_load(match[1]) or {}
    except yaml.YAMLError as exc:
        raise BookError("unavailable: invalid knowledge page frontmatter") from exc
    if not isinstance(fields, dict):
        raise BookError("unavailable: invalid knowledge page frontmatter")
    return fields, text[match.end():]


class Book:
    def __init__(self, vault, manifest):
        self.vault = Path(vault).resolve(strict=True)
        self.info = json.loads(Path(manifest).read_text(encoding="utf-8"))
        self.notes = self._configured_path("book_dir", "references")
        self.pdf = self._configured_path("pdf", "_raw")
        self.pages = self._configured_path("text_dir", "_raw")
        self.page_count = self.info["pdf_pages"]
        hub = Path(self.info["hub"])
        if hub.name != str(hub) or hub.suffix != ".md":
            raise BookError("outside book scope: invalid hub name")
        self.hub = self.notes / hub
        self._verify_pdf()

    def _configured_path(self, key, category):
        rel = Path(self.info[key])
        if not rel.parts or rel.parts[0] != category or len(rel.parts) < 2 or {"..", "_private"} & set(rel.parts):
            raise BookError("outside book scope: invalid configured path")
        return self.vault / rel

    def _checked(self, path, *, directory=False):
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise BookError("unavailable: an approved book file or directory could not be resolved") from exc
        if resolved != path or not resolved.is_relative_to(self.vault):
            raise BookError("outside book scope: symlinks and redirected paths are not allowed")
        if not (path.is_dir() if directory else path.is_file()):
            raise BookError("unavailable: unexpected book file or directory type")
        return path

    def _read(self, path):
        try:
            return self._checked(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise BookError("unavailable: could not read an approved book file") from exc

    def _verify_pdf(self):
        try:
            with self._checked(self.pdf).open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError as exc:
            raise BookError("unavailable: the source PDF could not be read") from exc
        if digest != self.info["pdf_sha256"]:
            raise BookError("unavailable: source PDF hash differs from the approved edition")

    def _source(self):
        return {
            "book_id": self.info["book_id"],
            "book_title": self.info["title"],
            "pdf_relative_path": self.info["pdf"],
            "pdf_sha256": self.info["pdf_sha256"],
        }

    def _note_files(self):
        yield self.hub
        for subdir in ("章节", "概念"):
            folder = self._checked(self.notes / subdir, directory=True)
            yield from sorted(folder.glob("*.md"))

    def _note(self, path, fields):
        lesson = re.match(r"第(\d+)课", path.stem)
        return {
            **self._source(),
            "page_id": path.relative_to(self.notes).as_posix(),
            "vault_relative_path": path.relative_to(self.vault).as_posix(),
            "title": fields.get("title") or path.stem,
            "summary": fields.get("summary", ""),
            "lifecycle": fields.get("lifecycle", "unknown"),
            "lesson": int(lesson[1]) if lesson and path.parent.name == "章节" else None,
        }

    def read_knowledge(self, page_id):
        for path in self._note_files():
            if path.relative_to(self.notes).as_posix() == page_id:
                fields, body = _frontmatter(self._read(path))
                return {**self._note(path, fields), "text": body}
        raise BookError("outside book scope: unknown knowledge page ID")

    def search_knowledge(self, terms, limit=8):
        patterns = _terms(terms, limit)
        ranked = []
        covered = set()
        for path in self._note_files():
            fields, body = _frontmatter(self._read(path))
            note = self._note(path, fields)
            headings = " ".join(str(fields.get(key, "")) for key in ("aliases", "keywords", "summary"))
            surfaces = [(f"{note['title']} {path.stem}", 4), (headings, 2), (body, 1)]
            matched = {}
            for term, pattern in patterns.items():
                for surface, weight in surfaces:
                    match = pattern.search(surface)
                    if match:
                        matched[term] = (weight, _excerpt(surface, match))
                        break
            if matched:
                covered.update(matched)
                weight = sum(weight for weight, _ in matched.values())
                excerpt = next(iter(matched.values()))[1]
                ranked.append((len(matched), weight, {
                    **note, "matched_terms": list(matched), "excerpt": excerpt,
                }))
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]["page_id"]))
        fallback = self.search_source(terms, limit) if len(covered) < len(patterns) else None
        return {
            **self._source(),
            "knowledge_hits": [item[2] for item in ranked[:limit]],
            "knowledge_truncated": len(ranked) > limit,
            "source_hits": fallback["source_hits"] if fallback else [],
            "source_truncated": fallback["source_truncated"] if fallback else False,
            "source_fallback_used": fallback is not None,
        }

    def _source_page(self, page):
        return {
            **self._source(),
            "pdf_page": page,
            "obsidian_link": f"[[{self.info['pdf']}#page={page}]]",
            "pdf_local_path": str(self.pdf),
        }

    def _page_text(self, page):
        return self._read(self.pages / f"page-{page:03d}.txt")

    def read_source_page(self, pdf_page):
        if type(pdf_page) is not int or not 1 <= pdf_page <= self.page_count:
            raise BookError(f"invalid PDF physical page: expected 1 to {self.page_count}")
        self._verify_pdf()
        return {**self._source_page(pdf_page), "text": self._page_text(pdf_page)}

    def search_source(self, terms, limit=8):
        patterns = _terms(terms, limit)
        self._verify_pdf()
        ranked = []
        for page in range(1, self.page_count + 1):
            body = self._page_text(page)
            matches = {term: match for term, pattern in patterns.items() if (match := pattern.search(body))}
            if matches:
                ranked.append({
                    **self._source_page(page),
                    "matched_terms": list(matches),
                    "excerpt": _excerpt(body, next(iter(matches.values()))),
                })
        ranked.sort(key=lambda hit: (-len(hit["matched_terms"]), hit["pdf_page"]))
        return {
            **self._source(),
            "source_hits": ranked[:limit],
            "source_truncated": len(ranked) > limit,
        }
