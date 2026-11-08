# 每日视频推荐第一版

推荐逻辑归属本仓库，入口 `skills/daily-video-recommendation/SKILL.md`，确定性工具 `tools/video_recommendation.py`。Codex heartbeat 执行语义提取、公开搜索、字幕评审并在原对话输出；没有另开模型服务。每日时间与唯一调度登记在 LifeOS `docs/engineering/schedule-ownership.md`，用户本次指定 Codex dot 为执行例外。

## 已实现

- 微信读书两自然周阅读量、最近30天个人划线与想法，最多5本。显式报告截断/未读分页；缺凭证、升级通知、错误不当成空数据。
- Wiki 原生 MCP 与浏览器限定历史由 skill 调用，原始证据日期、推断及缺失状态分开。访问不能当播放时长；精确播放时长采集尚未实现。
- 证据按14天半衰期，同主题同原始材料只保留最强信号，最多3个独立材料；机器生成、已归档、自动访问不能计入兴趣。
- 候选由字幕评审后按相关性/新信息/具体内容/观看成本排序，热度不进入质量分。陌生频道指可用记录未出现，非全账号证明。
- YouTube 官方 search/videos/commentThreads 适配器（环境变量 YOUTUBE_API_KEY）；无 key 时 skill 使用公开搜索及浏览器元数据。评论关闭/不可用不等于零评论。
- 既有字幕 CLI 复用。第一版推荐门槛检查视频ID、已知时长、字幕首尾覆盖、全部cue审阅范围。它能拒绝明显截断，不能数学证明字幕没有缺句，仍需语义检查。
- SQLite 每日唯一领取及跨天视频去重，准备状态不冒充送达。失败次日再试，不自动删除锁/补发。

## 本机安装与操作

将 SKILL.md 复制到 `~/.codex/skills/daily-video-recommendation/`，同目录放不入库的 runtime.json，字段为 `cli_path`（本仓库工具绝对路径）、`transcript_cli`（既有字幕工具绝对路径）、`state_dir`（私人运行目录）。不得将配置或证据复制到 Git。安装后新会话可发现；heartbeat 直接读绝对 Skill 路径。

```bash
python3 tools/video_recommendation.py --help
python3 -m unittest discover -s tests -p test_video_recommendation.py -v
```

状态路径是所有手动/定时运行共同的数据库。`begin` 先领取；源数据和候选卡保存到私人目录；`rank`、`select` 只做评分；`finish` 校验并标 prepared；当前线程随后输出卡片。中断的 running/failed 当天不会自动重跑，防止重复推送。停止在 Codex 自动任务面板暂停对应 heartbeat；保留证据与数据库，不启动替代任务。

## 首次现场验收（2026-11-08）

微信读书、Wiki read、浏览器限定近7天访问与视频公开元数据均实际读取成功。未发现已配置 YouTube API key，因此官方 API 适配器只有合成测试证据，现场走公开搜索/浏览器。精确播放时长缺失，不参与评分。

长候选的字幕只返回4段、末尾14.646秒，被覆盖检查排除；第二条短候选返回49段、末尾141.72秒，播放器约140秒，已逐段阅读。第二条评论关闭，记录 unavailable，不伪造评论分析。私人兴趣内容、视频卡与回包只保留在私人运行目录。

完整源码测试31项通过（包含新增11项）；Skill结构验证通过。既有 Pydantic 未解析前向引用警告不影响测试通过。自然定时触发和系统通知仍待首次运行验收；创建成功不证明未来准点送达。
