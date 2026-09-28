# StudyMind AI｜智学助手

一个可本地运行的大学生 AI 学习与效率助手。当前版本优先保证真实可运行：认证、任务、课程、考试、学习记录、学习计划、对话、文档上传/解析、中文 OCR、笔记、知识库向量检索、题目接口、Agent 计划确认、学习统计均走真实后端数据流。

## 当前运行策略

本项目已配置为本机真实 **MySQL 8.4**，监听 `127.0.0.1:3306`；本地向量检索使用 Qdrant local，中文嵌入模型为 `BAAI/bge-small-zh-v1.5`。SQLite 仅用于隔离测试。服务器默认真实模型连接已配置并实测通过；密钥只保存在后端且不返回浏览器。若模型配置被移除，AI 入口会明确报错，不伪造输出。

## 启动

```powershell
cd E:\StudyMindAI\frontend
npm ci
npm run build
cd ..
backend\.venv\Scripts\python.exe scripts\launch.py
```

浏览器打开 <http://127.0.0.1:8765>。

Windows 也可双击根目录 `start.bat`。首次安装依赖并构建前端：`cd /d E:\StudyMindAI\frontend && npm ci && npm run build`。

## Windows EXE

执行 `scripts\\build_exe.bat` 可生成 `dist\\StudyMindAI.exe`。EXE 已内置前端、后端、OCR 运行组件和内置学习资料；双击后会打开独立的 StudyMind AI 应用窗口，界面由系统 WebView2 内嵌渲染，不会跳转到外部浏览器。用户数据保存在 `%LOCALAPPDATA%\\StudyMindAI\\data`。

桌面版默认使用 SQLite 和关键词检索，因此干净的 Windows 电脑无需另装 Python、Node.js、MySQL 或 Qdrant。AI 模型可在应用设置中配置；语义嵌入仍建议使用源码部署版。

## 配置 AI

复制 `.env.example` 为 `backend/.env`，填写兼容 OpenAI API 的 `MODEL_NAME`、`API_KEY`、`BASE_URL`。启动前在 PowerShell 中加载变量，或直接设置系统环境变量。API Key 只在后端使用，不会发送到浏览器。

## 已实现模块

- 邮箱密码注册/登录/退出、Argon2 密码哈希、签名令牌与会话撤销
- Dashboard：真实任务、学习时长、考试、文档、会话统计
- 任务：新增、完成、编辑状态、删除、优先级、截止日期、分类
- 课程、考试、学习记录
- 学习计划：按日期范围生成草案，用户可看到每日条目
- AI 对话：模式 Prompt、会话历史、SSE 流式输出、失败状态持久化
- 文档：TXT/Markdown/DOCX/PDF 文本提取、扫描 PDF OCR、图片 OCR；上传受限且按用户隔离
- 笔记与知识检索
- AI 出题接口与答题评分（需模型配置）
- Agent：读取学习上下文、生成待确认任务计划，确认后真实写入任务；无任意命令执行
- 学习趋势与学科统计

## 本次完善

- **AI 学习助手**：6 种学习模式、连续上下文、SSE 流式输出、停止与重新生成、Markdown、代码高亮、LaTeX、复制回答，以及可选的知识库严格约束问答。
- **个人知识库**：聚合知识空间、真实文档数、索引数与分块数；支持文档/OCR 入库、本地中文向量检索、语义低分时关键词复核、带原文引用问答、知识点和学习笔记。
- **智能练习题库**：支持自定义学科、6 种题型、3 档难度和 5/10/20/50 题；可限定知识库来源。模型结果严格校验后才落库，客观题确定性评分，主观题按 AI 量规评阅，并汇总作答次数、正确率与平均分。
- **统一界面**：全部页面共享现代 SaaS 视觉系统；AI、知识库和题库新增专用状态、指标与工作区，桌面端和 390px 移动端均已验收。

本轮证据：`data/verification/feature-completion.json`（12 项真实模型/知识库/题库端到端检查）、`data/verification/completed-browser.json`（6 项真实浏览器检查）和 `data/verification/*-polished.png`（最终页面截图）。

### AI 暂时不可用时

知识库的上传、OCR、分块、来源查看、笔记和本地检索数据仍可使用；题库支持手工添加题目、客观题确定性评分、删除与统计。界面不会用固定文本冒充 AI。两个实际使用账户已加入明确带 `[示例]` 标记、可自行删除的大学计算机基础知识库、复习笔记和 8 道客观练习题。需要重新补充时可执行：

```powershell
backend\.venv\Scripts\python.exe scripts\seed_starter_content.py
```

## 重要边界

Redis/Celery 异步队列和生产多 worker 部署不在当前本地版本范围内；本地 Qdrant 必须保持单 Uvicorn worker。AI 生成能力必须由用户配置模型供应商后使用，应用不会用假数据填充 AI 回答。

## 验证

```powershell
cd E:\StudyMindAI\backend
.venv\Scripts\python.exe -m pytest tests -q
cd ..
backend\.venv\Scripts\python.exe scripts\verify_documents.py
backend\.venv\Scripts\python.exe scripts\verify_api.py
backend\.venv\Scripts\python.exe scripts\verify_browser.py
backend\.venv\Scripts\python.exe scripts\verify_completed_features.py
backend\.venv\Scripts\python.exe scripts\verify_completed_browser.py
```

最后一个脚本使用本机 Edge、创建并清理一次性验收账户，覆盖登录、Dashboard、任务、课程、考试、学习记录、计划发布、笔记、文档预览、AI 未配置边界、所有路由和移动端导航。验收截图保存在 `data/verification/`。
