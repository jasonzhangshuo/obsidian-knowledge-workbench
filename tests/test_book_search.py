import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from book_search import Book, BookError


class BookSearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = Path(temporary.name).resolve()
        self.notes = self.vault / "references" / "sample"
        self.raw = self.vault / "_raw" / "sample"
        for directory in (self.notes / "章节", self.notes / "概念", self.notes / "验证记录", self.raw / "text"):
            directory.mkdir(parents=True)
        self.pdf = self.raw / "source.pdf"
        self.pdf.write_bytes(b"synthetic PDF identity fixture")
        self.chapter = self.notes / "章节" / "第001课-辨别花香.md"
        self.chapter.write_text(
            '---\ntitle: 辨别花香\naliases:\n  - 芳草讲记\nkeywords: [花香, 盆栽]\n'
            'summary: 比较开花时间\nlifecycle: draft\n---\n日间花盆中留有蓝色陶片。\n', encoding="utf-8"
        )
        (self.notes / "概念" / "花期.md").write_text("---\ntitle: 花期\n---\n花期随季节变化。", encoding="utf-8")
        (self.notes / "总览.md").write_text("---\ntitle: 样书总览\n---\n卷首介绍。", encoding="utf-8")
        (self.notes / "验证记录" / "旧回答.md").write_text("这份旧答案包含馆藏编号。", encoding="utf-8")
        (self.raw / "text" / "page-001.txt").write_text("第一页是前言。", encoding="utf-8")
        (self.raw / "text" / "page-002.txt").write_text("光照记录：银叶\n海棠在窗边。", encoding="utf-8")
        self.manifest = self.vault / "book.json"
        self.manifest.write_text(json.dumps({
            "book_id": "sample", "title": "样书", "book_dir": "references/sample",
            "hub": "总览.md", "pdf": "_raw/sample/source.pdf", "text_dir": "_raw/sample/text",
            "pdf_pages": 2, "pdf_sha256": hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        self.book = Book(self.vault, self.manifest)

    def test_chinese_short_terms_alias_and_body_are_searchable(self):
        for terms in (["花香"], ["芳草讲记"], ["陶片", "盆栽"]):
            with self.subTest(terms=terms):
                hit = self.book.search_knowledge(terms)["knowledge_hits"][0]
                self.assertEqual(hit["page_id"], "章节/第001课-辨别花香.md")
                self.assertEqual(hit["lifecycle"], "draft")
                self.assertEqual(hit["lesson"], 1)
                self.assertEqual(set(hit["matched_terms"]), set(terms))

    def test_raw_fallback_can_find_text_wrapped_by_pdf_layout(self):
        result = self.book.search_knowledge(["银叶海棠"])
        self.assertEqual(result["knowledge_hits"], [])
        self.assertEqual(result["source_hits"][0]["pdf_page"], 2)
        self.assertIn("银叶\n海棠", result["source_hits"][0]["excerpt"])

    def test_source_page_has_stable_identity_and_exact_text(self):
        result = self.book.read_source_page(2)
        self.assertEqual(result["text"], "光照记录：银叶\n海棠在窗边。")
        self.assertEqual(result["pdf_relative_path"], "_raw/sample/source.pdf")
        self.assertEqual(result["pdf_page"], 2)
        self.assertEqual(result["pdf_sha256"], hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        for page in (0, 3, True):
            with self.subTest(page=page), self.assertRaises(BookError):
                self.book.read_source_page(page)

    def test_missing_extraction_is_not_a_no_match(self):
        (self.raw / "text" / "page-002.txt").unlink()
        with self.assertRaisesRegex(BookError, "unavailable"):
            self.book.search_source(["不存在的东西"])

    def test_wrong_pdf_revision_is_rejected(self):
        self.pdf.write_bytes(b"replacement")
        with self.assertRaisesRegex(BookError, "hash"):
            self.book.read_source_page(2)

    def test_old_answers_and_arbitrary_paths_are_excluded(self):
        result = self.book.search_knowledge(["馆藏编号"])
        self.assertEqual(result["knowledge_hits"], [])
        self.assertEqual(result["source_hits"], [])
        for page_id in ("验证记录/旧回答.md", "../../private.md", str(self.chapter)):
            with self.subTest(page_id=page_id), self.assertRaises(BookError):
                self.book.read_knowledge(page_id)

    def test_symlink_cannot_extend_the_read_scope(self):
        private = self.vault / "private.md"
        private.write_text("仅供测试的私密标记", encoding="utf-8")
        (self.notes / "概念" / "别名.md").symlink_to(private)
        with self.assertRaisesRegex(BookError, "scope"):
            self.book.search_knowledge(["私密标记"])
        page = self.raw / "text" / "page-002.txt"
        page.unlink()
        page.symlink_to(private)
        with self.assertRaisesRegex(BookError, "scope"):
            self.book.read_source_page(2)
