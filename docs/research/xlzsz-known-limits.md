# 学练赛证数据采集已知局限（2026-08-30 实测）

## 1+X 证书平台（vslc.ncb.edu.cn）

- **pageNum/pageSize 参数实测被服务端忽略**：任何页码都返回同一首页（10 条），
  无法翻页拉取全量 1237 条证书。
- 采集口径因此为"数字技术域关键词遍历 + 唯一 id 去重聚合"（14 个关键词），
  覆盖 AI/数据/网络/软件相关子集，非全量目录。
- total 字段可信（服务端报告全量数），但 records 无法完整取回。

## DataFountain（datafountain.cn）

- 分页参数名是 `page`（不是 `pageNum`）；`pageNum` 被忽略会导致每页重复。
- pageSize 固定 10（请求更大值无效）。
- 已按 race_id 去重，产物无重复。

## 天池（tianchi.aliyun.com）

- pageNum 正常生效，无重复；`isActive` 参数语义未深究（取空串为当前列表）。

## 讯飞大赛（challenge.xfyun.cn）

- contests-list 接口 curPage 正常，含往届全届次；无重复。
