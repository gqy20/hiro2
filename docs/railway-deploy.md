# Railway 部署清单

Hiro2 生产环境固定为三个服务：`web`、`api`、一个 PostgreSQL。Neo4j 使用
Neo4j Aura 或带持久化卷的独立服务。`docker-compose.yml` 只用于本地联调，
不会创建或更新 Railway 资源。

## 当前拓扑

- Web：`web`，使用 `Dockerfile.web`
- API：`api`，使用 `Dockerfile.api`
- PostgreSQL：`Postgres-0sS8`，挂载路径 `/var/lib/postgresql/data`
- API 健康检查：`/health/ready`

服务名是生产运维事实。若将来迁移数据库，应先建立迁移方案、验证新库和切换
`DATABASE_URL`，不能在日常发布中临时新建 PostgreSQL。

## 日常发布

日常发布只更新已有的 API 和 Web 服务：

```bash
railway status
railway service status --all --environment production
railway up --service api --environment production --message "deploy api"
railway up --service web --environment production --message "deploy web"
```

禁止在日常发布中运行以下基础设施命令：

```text
railway add --database postgres
railway deploy <database-template>
```

`railway up` 必须显式指定 `--service` 和 `--environment`，不能依赖当前链接的默认
服务。`railway redeploy` 只重启最近一次部署，不会上传当前工作树的新代码。

### 发布前数据库守卫

执行发布前必须确认：

1. `railway service status --all --environment production` 只列出一个 PostgreSQL。
2. PostgreSQL 挂载一个 `/var/lib/postgresql/data` Volume。
3. API 的 `DATABASE_URL` 指向现有 PostgreSQL 私有域名。
4. 没有待处理的数据库或 Volume 创建变更。

发现重复 PostgreSQL 时停止发布。先确认 API 引用和数据归属，再处理冗余资源；
不得用“重新建库”解决应用部署失败。

## API 服务

- 必填变量：`DATABASE_URL`
- Neo4j 变量：`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`
- LLM 变量：`HIRO2_LLM_PROVIDER`、`HIRO2_LLM_BASE_URL`、
  `HIRO2_LLM_MODEL`、`HIRO2_LLM_API_KEY`
- `CORS_ORIGINS`：填写当前 Web Railway 域名和自定义域名，逗号分隔
- 健康检查：`/health/ready`
- 简历持久化：Volume 挂载到 `/data`，并设置
  `RESUME_OBJECTS_DIR=/data/resumes`、
  `RESUME_ARCHIVE_PATH=/data/resume-archive.jsonl`

API 容器启动时先幂等执行 migration。应用启动后还会在后台执行一次幂等
`dbimport`；它不阻塞健康检查，但日志中必须能看到导入完成或明确失败。不要再在
每次发布后手工重复导入。

生产使用 `HIRO2_LLM_PROVIDER=mock` 时，应同时设置
`HIRO2_SNAPSHOT_ANALYZE=false`，避免把待分析记录全部送入隔离队列。配置真实 LLM
后再开启分析。

## Web 服务

- `NEXT_PUBLIC_USE_MOCK=false`
- `API_BASE_URL=https://<api-domain>/api/v1`
- `NEXT_PUBLIC_API_BASE_URL` 与 `API_BASE_URL` 保持一致

`NEXT_PUBLIC_*` 会在 Next.js 构建期内联，必须使用 API 公网地址，不能使用 Railway
私有域名。Web 依赖 API 地址变化时必须重新构建，单纯重启旧镜像无效。

## 首次初始化

首次初始化与日常发布分开执行：

1. 只创建一个 PostgreSQL，并确认 Volume 已挂载。
2. 创建 API，配置 `DATABASE_URL` 后部署并检查 `/health/ready`。
3. 确认后台 `dbimport` 完成，岗位、评测和候选人数据可读。
4. 创建 Web，注入 API 公网 URL 后构建。
5. 将 Web Railway 域名和自定义域名加入 API 的 `CORS_ORIGINS`。
6. 将 outbox/Neo4j 同步配置为独立任务，不依赖 API 进程常驻执行。

数据库只在首次初始化或经过审核的迁移中创建。每次创建后立即核对服务和 Volume
数量，不能连续执行模板部署后再集中清理。

## 发布验收

```bash
curl -fsS https://<api-domain>/health/ready
curl -fsS -o /dev/null https://<web-domain>/
railway service status --all --environment production
```

同时检查最新 API/Web 部署状态和错误日志。最新部署失败但旧容器仍可访问时，不能
把 HTTP 200 当成发布成功；应使用 `railway deployment list --service <name>` 确认
新部署为 `SUCCESS`。

不要上传本地 `.env`、LLM Key、简历原文件或 `data/raw`。密钥只保存在 Railway
Variables 或 CI Secret 中，日志不得输出变量值。
