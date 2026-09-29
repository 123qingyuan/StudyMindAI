# Linux 一键部署（Docker Compose）

> 当前交付的本机是 Windows，未安装 Docker、WSL 没有 Linux 发行版。因此 **Linux 镜像构建/启动尚未在本机验证**。已有真实 Linux 集成测试 `.github/workflows/linux-deploy.yml`，须在推送后由 Actions 或 Linux 主机执行并检查结果；不能把语法检查或 Windows API 测试当作 Linux 部署成功。

## 前提与一条命令

面向 Linux x86_64/amd64，建议至少 2 核、4 GB RAM，并留出镜像和用户上传所需磁盘空间。ARM64 暂不承诺原生支持。先由管理员按 [Docker 官方文档](https://docs.docker.com/engine/install/) 安装 Docker Engine 和支持 `up --wait --wait-timeout` 的 Compose v2，确保当前用户有权限运行 `docker info`。Docker 组近似 root 权限；不要把 socket 改为 666。

完整源码必须包含 `data/question_bank_manifest.json` 及 `data/builtin/legacy-expansion-v1/{manifest.json,01.md…07.md}`。这些是受控内置资料，不是用户数据库；旧版仅克隆代码而缺少此目录会导致注册失败。本次已添加精确 Git 白名单，交付/提交时必须包含它们。

在项目根目录执行：

```bash
bash deploy.sh
# 若已保留可执行位，也可 ./deploy.sh
```

脚本会检测依赖、创建仅 Linux 使用的 `.env.linux`（只在不存在时创建）、构建前后端并等待健康检查，最后请求真实首页。构建失败不会先停掉已有服务，启动失败返回非零并输出容器状态和近期日志。不会自动安装 Docker、修改防火墙、执行远程 shell、写入已有 `.env`、清理卷或停止其他服务。

默认浏览器访问 **http://127.0.0.1:8765**，自行注册，没有默认账户或密码。首次构建需要联网下载官方基础镜像、Debian 包、npm/pip 依赖；构建完成后常规离线功能不再依赖这些下载。

## 配置、隔离与数据

`.env.linux.example` 是不含密钥的示例。修改生成的 `.env.linux` 后再次执行 `bash deploy.sh` 即可：

```dotenv
STUDYMIND_BIND=127.0.0.1
STUDYMIND_PORT=8765
```

也可单次 `STUDYMIND_PORT=18765 bash deploy.sh`；shell 环境优先于文件。配置文件不会被脚本 source 执行。不要在文件中放未知命令。Compose 项目默认 `studymind`，多套部署必须使用不同且固定的 `COMPOSE_PROJECT_NAME` 和端口，避免访问错卷。

- Vue 静态文件和 `/api` 由同一个 FastAPI 服务提供，无需额外 Nginx。
- SQLite、关键词检索、单 Uvicorn worker；不连接现有 Windows/MySQL 数据。
- 运行 UID/GID 为 `10001:10001`，根文件系统只读，无额外 capabilities，`/tmp` 临时内存文件系统。
- Compose 管理的 `app-data` 命名卷挂载 `/var/lib/studymind`。包括 `studymind.sqlite3`、`uploads/`、随机生成的 `.jwt-key` 和 `.ai-settings.key`。密钥权限 600；重建镜像/容器不会更换它们。不能只备份 SQLite 而漏掉密钥和上传文件。
- 内置资料位于镜像只读的 `/app/data`，不会被用户卷遮住。不会复制用户上传、数据库、账号验收报告或 `.env` 到镜像。
- 重启策略 `unless-stopped`；健康检查每 15 秒请求 SQLite-backed `/api/health`。Docker 标记 unhealthy 本身不会自动重启仍存活的进程；此时需检查日志，部署脚本会失败。
- 新建命名卷继承镜像目录权限。自行改成宿主 bind mount 时需管理员明确准备 UID/GID 10001 的目录；脚本不会递归 chown 用户数据。

## 离线 AI 边界

Linux 默认依赖包不含 WebView/PyInstaller、Qdrant、FastEmbed，也不会下载向量模型。关键词检索、资料解析（PDF/DOCX/图片 OCR）、内置题库、手工题目、客观题确定性评分、笔记与统计可本地使用。受控题库 28 类、每类 100 题；旧版扩展资料明确标记“含重复待整理”，不代表新增优质长课程。

AI 对话/知识库问答需要用户在设置中填写自己的有效提供商配置和真实可用模型，且能连通提供商。不要把 `configured` 当作供应商可用证据。本 Linux 镜像请将设置里的检索方式保持 **keyword**；切换 local/api 向量并不会自动安装依赖，语义检索不在默认支持范围。AI 出题等尚未开放的路线仍不承诺可用。服务器没有预置 API Key。

Python 使用 **3.12** 而非照搬 Windows 的 3.13：实际下载发现 `rapidocr-onnxruntime==1.4.4` 的元数据要求 `<3.13`。`requirements-linux.txt` 锁定所有解析依赖和 SHA256，构建用 `--only-binary=:all: --require-hashes`；镜像构建会实际初始化 ONNX OCR、识别文本并检查 PDF、DOCX、关键词及内置清单。`libgl1`、`libglib2.0-0`、`libgomp1` 用于 Linux OpenCV/ONNX 运行。

## 远程访问：保留回环绑定，配置 HTTPS

不要直接把 8765 暴露到公网，注册入口没有邀请/管理员审批。公网开放前评估注册滥用、存储配额、备份、外层限流和访问控制。最简单的私人使用方式是 SSH 隧道：

```bash
ssh -L 8765:127.0.0.1:8765 your-user@your-server
```

需正式远程访问时，在**同一宿主机**部署管理员维护的 HTTPS 反向代理。例如 Caddy（自行准备 DNS/TLS/访问策略；脚本不安装）：

```caddyfile
study.example.com {
    request_body {
        max_size 22MB
    }
    reverse_proxy 127.0.0.1:8765 {
        flush_interval -1
    }
}
```

通过 `https://study.example.com` 同源访问前后端，不需要通配 CORS。不要把宿主回环地址直接用于另一个隔离容器中的代理。Uvicorn 默认不信任转发头，避免伪造客户 IP；反代后的应用限流可能聚合为代理 IP，应在代理层补充身份/来源限流。若必须局域网直连，可显式设置 `STUDYMIND_BIND=0.0.0.0`，但 HTTP 不加密，不能用于公网登录。

## 日常维护

以下命令均在项目根目录运行，使用与部署相同的项目名/环境变量：

```bash
docker compose --env-file .env.linux ps
docker compose --env-file .env.linux logs --tail=100 app
docker compose --env-file .env.linux restart app
docker compose --env-file .env.linux stop app
# 重新启动并等待健康；无需重新构建
docker compose --env-file .env.linux up -d --wait --wait-timeout 180
```

### 一致性备份（短暂停机）

先停 app，确保 SQLite、上传和密钥是一致的。备份包含隐私和密钥，应加密离线保存，不上传到 Git/公开 CI。

```bash
mkdir -p backups
chmod 700 backups
backup="backups/studymind-$(date +%Y%m%d-%H%M%S).tar.gz"
docker compose --env-file .env.linux stop app
# run 会使用同一数据卷；覆盖 entrypoint，仍以 UID 10001 读取
(umask 077; docker compose --env-file .env.linux run --rm --no-deps --entrypoint tar app -C /var/lib/studymind -czf - . > "$backup")
# 检查上条命令成功，并验证归档后再视为备份完成
tar -tzf "$backup"
docker compose --env-file .env.linux up -d --wait --wait-timeout 180
```

恢复应先保留故障卷快照、停止应用，在**新建空卷/独立项目**验证可信备份，避免直接覆盖含新数据的现有卷。可在新项目中 `docker compose --env-file .env.linux run --rm --no-deps -T --entrypoint tar app -C /var/lib/studymind -xzf - < "$backup"`，然后启动并验证注册/旧账号登录、文件和个人设置。不要从不可信 tar 恢复。

### 升级与回退

1. 先完成上面的备份，记录当前 Git revision 和镜像 ID。
2. 审阅新版本，`git pull --ff-only`（工作区应干净），再 `bash deploy.sh`。
3. 检查健康、首页、已有账户、资料、AI 个人配置。脚本不会覆盖 `.env.linux` 或删除卷。
4. 回退数据库不保证向后兼容；使用旧源码重建，并在独立项目恢复升级前完整备份验证后再切换。

**不要执行 `docker compose down -v` / `docker volume prune`：会删除数据。** 不要随意改变 Compose 项目名后误以为数据丢失。

## 可重复验收

`.github/workflows/linux-deploy.yml` 在 Ubuntu 24.04 上执行完整镜像构建、非 root OCR、首页静态资源、201 注册、409 重复、401 错误密码、200 登录、2800 题/31 文档读回、重复部署、配置文件不变、强制重建后的旧 token/密钥/加密样本及上传持久化。失败保留日志 artifact，不包含临时账号密码/令牌。

手动运行同样测试时应使用独立测试项目与空卷，不能指向现有生产数据：

```bash
export COMPOSE_PROJECT_NAME=studymind-linux-test STUDYMIND_PORT=18765
bash deploy.sh
mkdir -p .linux-test
python3 deploy/linux/http_check.py create --state .linux-test/state.json
docker compose --env-file .env.linux exec -T app python < deploy/linux/persistence_check.py
docker compose --env-file .env.linux up -d --force-recreate --wait --wait-timeout 180
python3 deploy/linux/http_check.py verify --state .linux-test/state.json
docker compose --env-file .env.linux exec -T app python < deploy/linux/persistence_check.py
docker compose --env-file .env.linux down
```

测试会创建随机临时账户，密码/token 只保存在忽略的 `.linux-test/state.json`，不要上传。命名卷保留，重复新一轮测试用新的项目名，不要在生产卷执行测试。
