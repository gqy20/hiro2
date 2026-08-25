// 客户端可调用的查询函数。RSC 页面不通过本文件读取数据（避免把
// node:fs 路径拉进客户端 bundle）；RSC 直接调用 loadXxxFixture 或 apiFetch。
//
// 当前只有 publishJobVersion 是客户端操作（mutation），新增客户端 mutation
// 时按相同模式增量添加。

import { apiFetch, isMockMode } from "@/lib/api/client";

export type PublishResult = {
  versionId: string;
  publishedAt: string;
  reviewActionIds: string[];
};

// ponytail: mock 模式无副作用 + 1.4s 模拟延迟，real 模式 POST。
export async function publishJobVersion(
  jobId: string,
  version: string,
): Promise<PublishResult> {
  if (isMockMode()) {
    await new Promise((resolve) => setTimeout(resolve, 1400));
    return {
      versionId: `${jobId}:${version}`,
      publishedAt: new Date().toISOString().slice(0, 10),
      reviewActionIds: [],
    };
  }
  return apiFetch<PublishResult>(
    `/jobs/${encodeURIComponent(jobId)}/versions/${encodeURIComponent(version)}/publish`,
    { method: "POST", body: { jobId, version } },
  );
}