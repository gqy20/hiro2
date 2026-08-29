"""smoke: 真实服务渲染冒烟——各路由主内容与页面标题存在性检查。

用法：
    make dev && uv run scripts/smoke.py          # 检查本机 3000 端口
    uv run scripts/smoke.py --base http://localhost:3000

动机：e2e 全跑 mock 模式，real（DB/文件）模式的契约错位只能由真实服务发现。
每页断言：HTTP 200 + 恰好一个 h1 + 主内容关键文本存在 + 无错误标记。
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request

# 路由 -> 首屏必须出现的关键文本（任一命中即可）
ROUTES: list[tuple[str, list[str]]] = [
    ("/", ["工作台", "优先事项", "我的岗位"]),
    ("/new-jobs", ["岗位发现", "候选"]),
    ("/positions", ["我的岗位"]),
    ("/jobs", ["岗位更新", "新增", "删除", "修改"]),
    ("/skills", ["能力全景", "capability"]),
    ("/diagnosis", ["诊断", "候选人", "画像"]),
    ("/resumes", ["简历"]),
    ("/career", ["目标岗位", "下一步", "开始你的成长诊断"]),
    ("/career/jobs", ["目标岗位", "必备能力"]),
    ("/profile", ["画像"]),
    ("/career/path", ["学习路径"]),
    ("/data", ["数据总览", "数据集", "来源"]),
    ("/data/sources", ["数据来源", "来源"]),
    ("/data/pipeline", ["流水线", "运行"]),
    ("/tasks", ["我的任务", "审核"]),
    ("/evaluation", ["评测与质量", "准确率", "命中率"]),
    ("/temporal", ["时间情报"]),
    ("/temporal/signals", ["信号"]),
    ("/temporal/forecasts", ["趋势回测", "预测"]),
    ("/temporal/retrospect", ["预测复盘", "命中率"]),
    ("/temporal/suggestions", ["影响建议", "JobImpactSuggestion"]),
    ("/temporal/timeline", ["时间轴", "四层"]),
]

ERROR_MARKERS = ["Application error", "Internal Server Error", "__NEXT_ERROR__"]


def check_route(base: str, route: str, keywords: list[str]) -> dict:
    url = f"{base}{route}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except Exception as exc:  # noqa: BLE001
        return {"route": route, "ok": False, "reason": f"请求失败: {exc}"}

    if status != 200:
        return {"route": route, "ok": False, "reason": f"HTTP {status}"}
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if len(h1s) != 1:
        return {"route": route, "ok": False, "reason": f"h1 数量 {len(h1s)}"}
    if not any(k in html for k in keywords):
        return {"route": route, "ok": False, "reason": f"主内容缺失（期望关键词 {keywords}）"}
    if any(m in html for m in ERROR_MARKERS):
        return {"route": route, "ok": False, "reason": "页面含错误标记"}
    return {"route": route, "ok": True, "h1": re.sub(r"<[^>]+>", "", h1s[0]).strip()[:40]}


def main() -> int:
    parser = argparse.ArgumentParser(prog="smoke")
    parser.add_argument("--base", default="http://localhost:3000")
    args = parser.parse_args()

    results = [check_route(args.base, route, kw) for route, kw in ROUTES]
    failed = [r for r in results if not r["ok"]]
    for r in results:
        mark = "✓" if r["ok"] else "✗"
        detail = r.get("h1") or r.get("reason", "")
        print(f"{mark} {r['route']:<24} {detail}")
    print(json.dumps({"total": len(results), "failed": len(failed)}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
