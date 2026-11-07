# 本机知识 MCP

Codex 和主 Hermes 按需通过 stdio 启动同一入口。程序从项目 .env 中读取 OBSIDIAN_VAULT_PATH，根据 config/knowledge-books.json 读取《入菩萨行论》济群法师讲记的总览、课程、概念和原文。返回结果带来源版本及 PDF 物理页。客户端负责理解问题、选择证据和组织回答。

## 安装和接入

在本项目目录内使用 Python 3.12 安装固定依赖。

~~~bash
uv venv --python 3.12 .runtime/knowledge-mcp/venv312
uv pip install --python .runtime/knowledge-mcp/venv312/bin/python \
  -r tools/requirements-knowledge-mcp.txt
.runtime/knowledge-mcp/venv312/bin/python -m unittest discover -s tests -v
~~~

客户端的服务名为 obsidian_knowledge。将 command 指向虚拟环境中 Python 的绝对路径，args 只含 tools/knowledge_mcp.py 的绝对路径。程序根据自身所在位置找项目配置，因此调用可以从不同目录发起。

| 客户端 | 配置和验证 |
|---|---|
| Codex | 在本机 config.toml 增加 mcp_servers.obsidian_knowledge，使用新会话检查工具发现及调用。 |
| 主 Hermes | 在本机 config.yaml 的 mcp_servers 下增加 obsidian_knowledge。CLI 验收会话使用 -t mcp-obsidian_knowledge 限定工具集。 |
| Hermes 微信 | 使用主 Hermes 对应的微信入口发送 /reload-mcp。若网关要求确认，选择仅本次。确认加载后提问，核对回复和同一会话的工具记录。 |

书籍清单和 MCP 依赖随项目维护。本机运行环境、客户端配置、测试问答及原书均保留在本机。停用时删除或禁用对应客户端配置中的 obsidian_knowledge 节点，再用新会话或 /reload-mcp 更新工具。

## 工具和来源

| 工具 | 输入与结果 |
|---|---|
| search_knowledge | 接收中文词组列表。返回标题、课程、命中词、片段、草稿状态和页面 ID。词组覆盖不足时补查逐页原文。 |
| read_knowledge | 用页面 ID 读取已获准的知识页。 |
| search_source | 用中文词组查逐页原文，返回片段和 PDF 物理页。 |
| read_source_page | 用 PDF 物理页码读取完整的逐页文本及来源信息。 |

检索范围为配置指定的总览、章节和概念目录，以及同版 PDF 的逐页文本。原书路径及哈希随证据返回，旧问答及验证记录单独保留。工具接受页面 ID 或物理页码，越界及符号链接返回错误。搜索结果区分知识页命中、原文回退、空结果和文件不可用。

四个工具均通过 MCP 声明只读和本地访问。客户端依照现有审批策略处理工具调用。

Obsidian 中的 PDF 引用使用 `[[相对路径/lecture-full.pdf#page=31]]` 格式。微信答复列出书名、课次和物理页，原件从 Mac 上的 Vault 查看。

## 验收方法

1. 搜索“忏悔”“出罪力”和问题改写，确认候选来自正确课程或概念。
2. 用知识页未收录的完整偈句触发原文回退。按物理页读取后与 PDF 原页对照。
3. 在 Codex 和主 Hermes 的新会话运行本书已有八题，重点检查跨课、拼接引文、逐字定位及缺失材料。检查实际 MCP 工具调用记录。
4. 使用 tools/book_wiki_audit.py 的 --answers 和 --pages 参数核对引用。输入 JSON 的 answers 数组中每项含 id 和 evidence。每条证据含 pdf_page 和 quote。检查解释是否与原文语境相符。
5. 在实际微信会话完成一次提问和回复，核对工具调用和 PDF 页码。记录能否打开相应出处。

首轮失败与复查分别记录。程序匹配验证引文与页码，抽样审阅验证回答与上下文的关系。

2026-11-07 的本机验收已核对原 PDF 及 457 页提取哈希。Codex CLI 和主 Hermes CLI 各运行原有八题及两道改写题，分别有 24 条和 27 条逐字引文通过页码核对。物理第 31 页在 macOS 预览中打开并核对。Codex CLI 使用当次账号模型目录提供的 gpt-5.6-sol。

2026-11-07，主 Hermes 微信端通过一次《入菩萨行论》跨课问答验收。用户确认收到回复。同一微信会话的记录显示，Hermes 在答复前调用 `obsidian_knowledge` 5 次，其中 `search_knowledge` 1 次、`read_knowledge` 2 次、`search_source` 2 次。在 Mac 上直接从原 PDF 提取物理第 85 页的文字，确认回复所引的 1 条逐字引文与该页一致。
