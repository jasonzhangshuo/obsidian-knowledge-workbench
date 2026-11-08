# 我的重启人生技能学习仓库：开发与维护

本目录是书籍知识工作流及后续知识 MCP 的代码维护入口。正式知识正文保存在 Obsidian Vault；Git 管理代码、流程指令、测试和维护文档。

GitHub 公开代码仓库：<https://github.com/jasonzhangshuo/obsidian-knowledge-workbench>。

## 三个位置各负责什么

| 位置 | 归属 |
|---|---|
| 本 Git 项目 | 提取与校验工具、整理规则、开发记录；后续独立知识 MCP 源码 |
| Obsidian Vault | 原书、文章、结构化知识页、概念关联、出处、完整分析与验证记录 |
| Codex 临时工作目录 | 单次开发或验证的中间文件，成果应回到前两处 |

日常使用方式为 **Claudian 按 Wiki Skills 整理维护 → Obsidian 持久保存 → 独立 MCP → Codex / Hermes 查询**。只读 MCP 的首版开放《入菩萨行论》济群法师讲记。已有知识成果由 Codex/Luna 整理和验证后保存进 Vault。接入和验收方法见 [知识 MCP 运行说明](docs/engineering/knowledge-mcp.md)。

## 已维护的代码

- `tools/pdf_extract.py`：本地文字层提取、逐页校验值、独立课标切分。无需模型，未实现 OCR。
- `tools/book_wiki_audit.py`：限定一本书的链接、逐字引文、问答引用和实际全文读取证据检查；不会全库扫描。
- `tools/book_search.py` 与 `tools/knowledge_mcp.py`：本书中文检索、原文回查及 stdio MCP 入口。
- `tools/youtube_transcript.py` 与 `skills/youtube-transcript/`：Codex 和 Claudian 共用的 Chrome 字幕入口。安装和验证见 [YouTube 字幕接入](docs/engineering/youtube-transcript.md)。
- `tools/video_recommendation.py` 与 `skills/daily-video-recommendation/`：近期问题证据评分、字幕评审和每日去重；运行边界见 [每日视频推荐](docs/engineering/video-recommendation.md)。
- `prompts/`：供代理采用的编译与查询约束；这些文本本身不会启动模型或保存数据。
- `config/wiki-workflow.json`：已验证上游版本、项目/Vault技能范围及维护归属；实际账号与本机路径配置仍不跟踪。
- `tests/`：切分边界、原句数字/标点、拼接引文、整课读取证据和私密目录边界的回归测试。
- `archive/2026-11-06/`：此前验证与入库脚本的代码档案，已移除本机用户路径；不是可直接运行的正式入口。
- `docs/engineering/`：架构、代码/资料边界、后续实施顺序。
- `docs/development/`：本次验证结论与代码来源。

现有 PDF 提取和校验工具使用 Python 3.9+ 标准库，提取额外依赖本机 pdftotext。知识 MCP 使用 Python 3.12 和固定版本的依赖。obsidian-wiki 继续由原有 uv 安装管理。

## 本地命令

```bash
.runtime/knowledge-mcp/venv312/bin/python -m unittest discover -s tests -v
python3 tools/pdf_extract.py --help
python3 tools/book_wiki_audit.py --help
```

提取输出指向 Vault 中为本书新建的原文目录；目录必须为空，工具拒绝覆盖已有材料：

```bash
python3 tools/pdf_extract.py /path/to/source.pdf \
  --output "$OBSIDIAN_VAULT_PATH/_raw/_archived/书籍/<book-id>/text"
```

只检查某一本书，不传整个 Vault 作为书籍目录：

```bash
python3 tools/book_wiki_audit.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --book "$OBSIDIAN_VAULT_PATH/references/书籍/<book-id>" \
  --pages "$OBSIDIAN_VAULT_PATH/_raw/_archived/书籍/<book-id>/text"
```

输出默认在终端；需要持久保存校验结果时，通过 `--report` 指向该书在 Vault 内的验证目录。工具仅做结构/文字检查，不证明摘要语义完全正确。

## Git 范围

采用白名单。现有 `.env`、技能链接、运行目录、旧自动化、备份及 `Obsidian-learn/` 均未纳入。PDF、知识正文、聊天/模型输出、日志、账号凭证不进入代码提交。旧文件保留原位，没有删除或重建。

`main` 作为维护分支，与 GitHub 的 `origin/main` 同步。公开范围仅限上述工程文件，知识正文仍留在本机 Vault。后续开发从此项目继续，以明确的源码提交、测试和数据验收分别记录完成状态。
