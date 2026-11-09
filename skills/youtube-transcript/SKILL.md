---
name: youtube-transcript
description: 优先使用用户的 YouTube Chinese Chrome 扩展获取带时间戳字幕。用户说用 Chrome 插件、YouTube 字幕 Skill，或在学习仓库提交 YouTube 链接要求转写、拆解、学习、翻译或归档时，走本 Skill 的本机命令。
---

# YouTube 字幕与学习

1. 用以下命令调用 YouTube Chinese 扩展。此项目中获取字幕时先走这个入口，即使其他 Skill 提供了通用下载方式。传入用户给的纯网址，去掉 Markdown 外壳。

   ```bash
   transcript_file=$(mktemp -t youtube-transcript)
   python3 "$HOME/Projects/我的重启人生技能学习仓库/tools/youtube_transcript.py" fetch '<YouTube URL>' > "$transcript_file" && printf '%s\n' "$transcript_file"
   ```

   保留退出码和错误，成功后先检查 `title`、`video_id`、`language`、`kind`、`video_duration`、`cue_count`、`first_start`、`last_end`。以片段为单位读取 `cues`，避免一次输出长节目全文。需要安装或排查时读项目的 `docs/engineering/youtube-transcript.md`。

2. 命令失败时报告实际错误和执行位置。用户明确要求用插件时，停在这里。只有用户允许换来源时，再用可访问的浏览器「转写文稿」、发布者的正式转写，或对用户提供的可用音视频做本地 Whisper 转写。标明实际来源及覆盖范围。此 Skill 不调用 `yt-dlp`、`agent-reach`，也不提取浏览器 Cookie。

3. 按 Vault `90-系统/YouTube学习流程.md` 标明读取状态和实际覆盖范围。获得完整字幕轨与实际完整阅读是两个步骤。只有分段处理并核对覆盖后才标记完整。区分讲者观点、用户理解和 AI 推断。按用户意图输出学习结果或归档，归档沿用既有来源、时间戳、标签和关联规则。
