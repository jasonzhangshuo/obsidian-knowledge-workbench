import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from knowledge_mcp import create_server


class KnowledgeMCPTests(unittest.TestCase):
    def test_all_tools_advertise_read_only_access(self):
        tools = asyncio.run(create_server(object()).list_tools())
        self.assertEqual(
            {tool.name for tool in tools},
            {"search_knowledge", "read_knowledge", "search_source", "read_source_page"},
        )
        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertIsNotNone(tool.annotations)
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.destructiveHint)
                self.assertFalse(tool.annotations.openWorldHint)
