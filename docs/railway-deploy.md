# Railway 部署清单

Hiro2 的生产部署拆成 Web、API、PostgreSQL 三个 Railway 服务；Neo4j 使用 Neo4j Aura 或带持久化卷的独立服务。`docker-compose.yml` 继续用于本地联调，不作为生产服务编排文件。

## API 服务

- Dockerfile：`Dockerfile.api`
- 必填变量：`DATABASE_URL`、`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`
- LLM 变量：`HIRO2_LLM_PROVIDER`、`HIRO2_LLM_BASE_URL`、`HIRO2_LLM_MODEL`、`HIRO2_LLM_API_KEY`
- `CORS_ORIGINS`：填写 Web 服务公网 URL，多个值用逗号分隔
- 健康检查：`/health/ready`
- 如使用 Railway Volume，挂载到 `/data`，设置 `RESUME_OBJECTS_DIR=/data/resumes`、`RESUME_ARCHIVE_PATH=/data/resume-archive.jsonl`

API 启动时只执行幂等数据库迁移，不执行数据导入。首次部署后，在 API 服务环境中单独运行一次 `make db-import`，避免每次重启重复导入。

## Web 服务

- Dockerfile：`Dockerfile.web`
- `NEXT_PUBLIC_USE_MOCK=false`
- 构建参数 `API_BASE_URL`：填写 API 公网 URL，通常为 `https://<api-domain>/api/v1`

`NEXT_PUBLIC_API_BASE_URL` 是 Next.js 构建期变量，不能填 API 服务的 Railway 私有域名，否则用户浏览器无法访问。

## 发布顺序

1. 用 `railway link` 绑定目标 Project、Environment 和 Service。
2. 创建 PostgreSQL，确认 API 的 `DATABASE_URL` 可用。
3. 创建 API，配置变量并检查 `/health/ready`。
4. 执行一次 `db-import`，确认岗位、评测和候选人数据可读。
5. 创建 Web，注入 API 公网 URL 后构建。
6. 将 Web 公网 URL 加入 API 的 `CORS_ORIGINS`，再做浏览器验收。
7. 将 outbox/Neo4j 同步配置为独立任务，不依赖 API 进程常驻执行。

不要把本地 `.env`、LLM Key、简历原文件或 `data/raw` 上传到仓库；密钥应在 Railway Variables 中保存并按需封存。
