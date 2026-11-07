"""Run the single-book read-only MCP server over stdio."""

import re
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import StrictInt

from book_search import Book, BookError


ROOT = Path(__file__).resolve().parents[1]


def vault_path(env_file):
    with Path(env_file).open(encoding="utf-8") as stream:
        for line in stream:
            match = re.match(r"^\s*(?:export\s+)?OBSIDIAN_VAULT_PATH\s*=\s*(.*?)\s*$", line)
            if match and match[1]:
                value = match[1]
                if value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                path = Path(value).expanduser()
                if path.is_absolute():
                    return path
                break
    raise BookError("unavailable: set an absolute OBSIDIAN_VAULT_PATH in the project's .env")


def create_server(book):
    server = FastMCP(
        "obsidian_knowledge",
        instructions=(
            "只读查询《入菩萨行论》济群法师讲记。用 2–4 个中文词组检索，"
            "相关知识页属于整理草稿。跨课问题读多个页面，关键解释和引文用原文物理页核对。"
            "原文摘录连续逐字引用，注明课次和 PDF 物理页。"
            "零命中时先调整关键词并查原文，资料不足时如实说明。"
        ),
    )
    read_only = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    )

    def call(function, *args):
        try:
            return function(*args)
        except BookError as exc:
            raise ToolError(str(exc)) from None

    @server.tool(annotations=read_only)
    def search_knowledge(terms: list[str], limit: StrictInt = 8) -> dict[str, Any]:
        """按中文词组查讲记的课程、概念与总览。词组未完全覆盖时补查逐页原文。"""
        return call(book.search_knowledge, terms, limit)

    @server.tool(annotations=read_only)
    def read_knowledge(page_id: str) -> dict[str, Any]:
        """读取搜索结果中的 page_id，返回知识页正文与草稿状态。"""
        return call(book.read_knowledge, page_id)

    @server.tool(annotations=read_only)
    def search_source(terms: list[str], limit: StrictInt = 8) -> dict[str, Any]:
        """按中文词组搜索原PDF的逐页文字层，返回连续原文片段及PDF物理页。"""
        return call(book.search_source, terms, limit)

    @server.tool(annotations=read_only)
    def read_source_page(pdf_page: StrictInt) -> dict[str, Any]:
        """用PDF物理页码读取完整提取文本和出处。引用前核对原句与语境。"""
        return call(book.read_source_page, pdf_page)

    return server


def main():
    try:
        book = Book(vault_path(ROOT / ".env"), ROOT / "config" / "knowledge-books.json")
    except (OSError, ValueError, KeyError) as exc:
        message = str(exc) if isinstance(exc, BookError) else "invalid or unavailable book configuration"
        print(f"obsidian_knowledge: {message}", file=sys.stderr)
        return 1
    create_server(book).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
