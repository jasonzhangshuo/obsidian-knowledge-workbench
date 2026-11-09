# YouTube 字幕接入

Codex 和 Claudian 共用 `skills/youtube-transcript`。本地 CLI 启动一次性回环服务，打开 Chrome 任务页。扩展打开视频，从现有字幕缓存回传 JSON。返回内容包含视频 ID、字幕语言、时间范围和片段。浏览器会话负责访问 YouTube。

## 在 Mac 上安装

在普通「终端」进入本项目并准备扩展与 Skill 入口。

```bash
cd "$HOME/Projects/我的重启人生技能学习仓库"
python3 tools/youtube_transcript.py prepare \
  "$HOME/Developer/youtube-chinese/dist/extension" \
  .runtime/youtube-transcript-extension
python3 tools/youtube_transcript.py register
```

`prepare` 从现有扩展生成独立的构建副本，并打印完整路径。若 `.runtime/youtube-transcript-extension` 已生成，可直接使用该目录。到 Chrome 的 `chrome://extensions`，暂时关闭旧的 `YouTube Chinese`，再用「加载未打包的扩展程序」选择该目录。两份扩展并行开启时都会处理同一视频页。旧版的设置和安装可保留，需要恢复时关闭新版并重新开启旧版。

`register` 将同一个项目 Skill 安装为实体文件，分别放到项目的 `.agents/skills/` 和 Vault 的 `.agents/skills/`、`.claude/skills/`。Claudian 的 Skill 读取器会拒绝符号链接。若之前注册过链接，重新运行 `register` 就能迁移，项目 Skill 更新后也用同一命令同步。Vault 路径优先取 `--vault`，其次取项目 `.env` 的 `OBSIDIAN_VAULT_PATH`。安装后刷新 Skill 列表或新开会话。

多个 Chrome 个人资料时，可以把安装了字幕扩展的资料目录名写入 `.runtime/youtube-transcript-profile`，一行即可。目录名以该资料的 `chrome://version` 中「个人资料路径」的最后一级为准。CLI 会使用该资料打开任务页。这个配置只用于字幕工具，不进入 Git。

## 实测

```bash
transcript_file=$(mktemp -t youtube-transcript)
python3 tools/youtube_transcript.py fetch 'https://www.youtube.com/watch?v=8dHEG7WxR4c' > "$transcript_file" && \
  python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(r["video_id"], r["language"], r["cue_count"], r["first_start"], r["last_end"])' "$transcript_file"
```

终端验证成功后，在 Codex 和 Claudian 各新开一个会话，分别发送「用 YouTube 字幕 Skill 获取这条视频的字幕，告诉我片段数和首尾时间」及同一链接。比对两次的来源、视频 ID 和覆盖区间。

- `LOCAL_BRIDGE_DENIED` 表示当前执行器不允许监听本机回环端口。Skill 会报告错误，用户接受其他来源时可读取浏览器转写面板。
- `EXTENSION_TIMEOUT` 表示 Chrome 没有回传。检查 CLI 扩展是否已加载，以及 Chrome 打开的是否为安装该扩展的用户资料。
- `CAPTIONS_UNAVAILABLE` 表示扩展已经接单，但未在时限内取到字幕轨。可在对应的 Chrome 视频页查看是否有字幕、登录或验证提示。

构建副本会保留原有翻译和配音功能。字幕回传使用临时回环端口和每次生成的随机地址，CLI 结束后服务关闭。命令输出字幕，后续是否写入 Vault 由既有 YouTube 学习流程决定。
