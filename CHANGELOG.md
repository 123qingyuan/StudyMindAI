# 更新记录

## main — Linux Docker Compose 部署（未单独发布安装包）
- 增加 `bash deploy.sh`、多阶段镜像、独立 Linux Python 3.12 哈希锁定依赖；修复 RapidOCR 不支持 Python 3.13 的 Linux 安装阻碍。
- 非 root、只读根目录、回环绑定、健康等待、日志轮转及命名卷持久化 SQLite/上传/JWT 和 AI 加密密钥；不会覆盖已有配置。
- 受控内置题库及旧版标记资料采用精确 Git/Docker 白名单；不打包用户数据。
- 新增中文 HTTPS/备份/升级文档和 Ubuntu 集成测试。提交 `040161e` 的 [Linux CI 36524138537](https://github.com/123qingyuan/StudyMindAI/actions/runs/36524138537) 已完成且结果 success，日志确认构建、健康启动、HTTP/OCR/内置内容与重建持久化。该次 artifact 上传缺失并有 Node.js 弃用警告；部分 tee 管道未显式启用 pipefail，不能只凭绿色状态作验收结论。未验证真实 AI 供应商、公网生产或 ARM64。

## 2.0.0 — 已发布 Windows 桌面版
- 全局语义设计系统、蓝灰工作台与完整深/浅/跟随系统主题，登录与弹窗共用外观。
- 主题持久化、首屏主题引导、运行中响应系统偏好；键盘焦点及 reduced-motion 支持。
- 保留已有 AI 恢复修改；增加 HTTP 400/402/403/408/422/429 等安全分类与精确模型 ID 提示，不泄露上游响应。
- 修正学习总览缺失题库数量、零值图表柱体表达。
- 版本号统一 2.0.0；独立数据目录验收开关 STUDYMIND_APP_DIR。
- 任务、课程、资料、知识库、题库与统计继续使用真实 API。
- AI 出题、AI 计划生成与主观题模型评分仍未开放；未声称用户当前个人 AI 供应商连接成功。
