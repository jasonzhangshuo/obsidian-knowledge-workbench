import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def module(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


audit = module("book_wiki_audit")
pdf = module("pdf_extract")


class BookToolsTests(unittest.TestCase):
    def test_contents_rows_are_not_chapters_and_shared_page_is_preserved(self):
        pages = ["【第一课】......2\n【第二课】......3", "【第一课】\n前半\n【第二课】\n后半", "续文"]
        result = pdf.chapter_spans(pages)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["start_pdf_page"], 2)
        self.assertEqual(result[0]["end_pdf_page"], 2)
        self.assertIn("前半", result[0]["text"])
        self.assertNotIn("后半", result[0]["text"])
        self.assertIn("后半", result[1]["text"])
        self.assertIn("续文", result[1]["text"])

    def test_trailing_formfeed_does_not_invent_a_page(self):
        self.assertEqual(pdf.split_pages("一\f二\f"), ["一", "二"])

    def test_quote_matching_preserves_digits_and_punctuation(self):
        pages = {1: "本节共 3 项，\n顺序不能改变。"}
        data = {"answers": [{"id": "a", "evidence": [
            {"pdf_page": 1, "quote": "本节共3项，顺序不能改变。"},
            {"pdf_page": 1, "quote": "本节共项，顺序不能改变。"},
            {"pdf_page": 1, "quote": "本节共3项、顺序不能改变。"},
            {"pdf_page": 2, "quote": "本节共3项，顺序不能改变。"}]}]}
        self.assertEqual([x["valid"] for x in audit.query_checks(data, pages)], [True, False, False, False])

    def test_noncontiguous_quote_is_rejected(self):
        data = {"answers": [{"id": "a", "evidence": [{"pdf_page": 1, "quote": "开头一句。结尾一句。"}]}]}
        self.assertFalse(audit.query_checks(data, {1: "开头一句。中间不能省略。结尾一句。"})[0]["valid"])

    def test_claimed_read_requires_full_tool_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "lesson-001.txt"
            source.write_text("开头\n正文不能跳过\n结尾", encoding="utf-8")
            events = root / "events.jsonl"
            event = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
                     "command": "cat lesson-001.txt", "aggregated_output": "开头\n结尾"}}
            events.write_text(json.dumps(event), encoding="utf-8")
            self.assertFalse(audit.read_coverage([source], events)[str(source)])
            event["item"]["aggregated_output"] = source.read_text(encoding="utf-8")
            events.write_text(json.dumps(event), encoding="utf-8")
            self.assertTrue(audit.read_coverage([source], events)[str(source)])

    def test_scope_rejects_entire_vault_private_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            private = vault / "_private" / "Morning Pages"
            private.mkdir(parents=True)
            book = vault / "references" / "book"
            book.mkdir(parents=True)
            (book / "note.md").write_text("正文", encoding="utf-8")
            self.assertEqual(len(audit.book_notes(book, vault)), 1)
            with self.assertRaises(ValueError):
                audit.book_notes(vault, vault)
            with self.assertRaises(ValueError):
                audit.book_notes(private, vault)
            (book / "escape.md").symlink_to(private / "secret.md")
            with self.assertRaises(ValueError):
                audit.book_notes(book, vault)

    def test_private_and_escaping_links_fail_without_reading_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            book = vault / "references" / "book"
            book.mkdir(parents=True)
            source = book / "note.md"
            source.write_text("[[references/book/other]] [[../escape]] [[_private/Morning Pages/a]]", encoding="utf-8")
            (book / "other.md").write_text("相关页", encoding="utf-8")
            result = audit.link_checks([source], vault)
            self.assertEqual({x["target"] for x in result}, {"../escape", "_private/Morning Pages/a"})

    def test_empty_output_cannot_overwrite_existing_material(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            source.write_bytes(b"existing input")
            target = root / "output"
            target.mkdir()
            (target / "user-note.txt").write_text("preserve me", encoding="utf-8")
            with self.assertRaises(ValueError):
                pdf.extract(source, target)
            self.assertEqual((target / "user-note.txt").read_text(), "preserve me")


if __name__ == "__main__":
    unittest.main()
