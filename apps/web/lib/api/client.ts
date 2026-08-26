// 通用 fetch wrapper。
//
// 设计要点：
// - 服务端专用：所有当前页面都是 RSC，数据获取在服务端完成。
// - Mock / Real 二选一：mock 模式下不允许调用 apiFetch，必须走 queries.ts 的 mock 分支。
// - 错误归一：非 2xx、超时、网络错误统一抛 ApiError，让 Next.js error.tsx 边界统一处理。
// - 默认 10s 超时，使用 AbortController；调用方可用 options.signal 提前取消。

export class ApiError extends Error {
  status?: number;
  cause?: unknown;

  constructor(
    message: string,
    options: { status?: number; cause?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.cause = options.cause;
  }
}

export type ApiOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
  headers?: Record<string, string>;
};

const DEFAULT_TIMEOUT_MS = 10_000;

// ponytail: mock 是当前默认（本地无后端），env 未设置或为 "true"/"1" 都视为 mock。
export function isMockMode(): boolean {
  const raw = process.env.NEXT_PUBLIC_USE_MOCK;
  if (raw === undefined || raw === "") return true;
  return raw === "true" || raw === "1";
}

export async function apiFetch<T>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  if (isMockMode()) {
    throw new Error(
      "Mock mode: apiFetch is disabled while NEXT_PUBLIC_USE_MOCK=true. Use a query function in queries.ts instead.",
    );
  }

  const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
  if (!baseUrl) {
    throw new ApiError("NEXT_PUBLIC_API_BASE_URL is not set");
  }

  const controller = new AbortController();
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (opts.signal) {
    if (opts.signal.aborted) controller.abort();
    else
      opts.signal.addEventListener("abort", () => controller.abort(), {
        once: true,
      });
  }

  try {
    const method = opts.method ?? "GET";
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(opts.headers ?? {}),
    };
    const init: RequestInit = {
      method,
      headers,
      signal: controller.signal,
    };
    if (method === "POST" || method === "PUT" || method === "PATCH") {
      headers["Content-Type"] = "application/json";
      if (opts.body !== undefined) {
        init.body = JSON.stringify(opts.body);
      }
    }
    const res = await fetch(`${baseUrl}${path}`, init);
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new ApiError(
        `API ${res.status} ${res.statusText}: ${body.slice(0, 200)}`,
        { status: res.status },
      );
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(`Request timed out after ${timeoutMs}ms`, {
        cause: err,
      });
    }
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError(`Request timed out after ${timeoutMs}ms`, {
        cause: err,
      });
    }
    throw new ApiError(
      err instanceof Error ? err.message : "Unknown fetch error",
      { cause: err },
    );
  } finally {
    clearTimeout(timer);
  }
}
