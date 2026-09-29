# StudyMind AI 2.0

面向大学生日常学习的 Windows 本地优先桌面应用，Vue 3 + FastAPI + pywebview/WebView2；不是外部浏览器演示。

- 保留 StudyMind 图书星芒 logo、中文界面、所有已有真实数据与用户配置。
- 核心闭环：任务、课程、考试、学习记录、人工学习计划、资料/OCR、知识库、手工题库、客观题评分与数据报告。
- 可选 AI：个人密钥加密保存、真实固定问候连接测试、六种对话模式与流式输出；保存配置不代表服务在线。
- AI 出题、AI 计划生成、主观题模型评阅未开放。内置资料明确标注来源；每日练习是已有题池轮换，不是每日新增。
- 默认 SQLite + 关键词检索。用户数据位于本机用户目录；包内不带 .env、账户数据库或密钥。
- 使用场景：白天课堂与夜间宿舍交替；浅色、深色、跟随系统，优先清晰、紧凑与长期阅读。
- Windows 2.0.0 已发布至 [GitHub Release](https://github.com/123qingyuan/StudyMindAI/releases/tag/v2.0.0)。新增 Linux Docker Compose 部署位于 main，使用独立数据卷与 Python 3.12；不是 Linux 桌面包，也不自动迁移 Windows 数据，见 [Linux 文档](docs/LINUX.md)。
- Agent 自动执行、知识图谱、Learning Twin 不属于当前已交付承诺；个人中转站尚未验证成功，AI 配置保存不代表模型可用。
