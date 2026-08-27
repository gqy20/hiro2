"""jdcorp: 企业官方招聘站采集（Playwright 拦截同源 XHR，无需登录/WAF 对抗）。

已支持站点：
    bytedance  jobs.bytedance.com（社招搜索；列表页自带职责/要求正文与发布时间）
    alibaba    talent-holding.alibaba.com（集团社招；POST /position/search）

用法：
    uv run scripts/jdcorp.py run --site bytedance --keywords "大模型" "RAG" [--pages 3]
    uv run scripts/jdcorp.py run --site alibaba  --keywords "大模型" [--pages 3]

原理：拦截页面自身发出的搜索 XHR（浏览器内完成 csrf/签名）；字节分页走 URL
current 参数，阿里分页点击页面「下一页」按钮。
产物：data/raw/jd/corp/<site>.jsonl，jd_id 幂等去重；限速页间 2~4s。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "jd" / "corp"
CACHE = OUT_DIR / ".cache.json"
MIN_DESC = 120  # 职责+要求合并后过短的多为挂名岗，采集层即丢弃
CACHE_TTL = 7 * 86400  # 关键词级缓存 7 天：期内首屏无新岗位则跳过整词


def load_cache() -> dict:
    if CACHE.is_file():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - 缓存损坏即重建
            return {}
    return {}


_CACHE_LOCK = threading.Lock()


def save_cache(cache: dict) -> None:
    # ponytail: 线程锁防同进程并发写坏 JSON；多进程并发下最坏丢一次 mark，缓存可重建
    with _CACHE_LOCK:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def cached_keyword(cache: dict, site: str, keyword: str) -> bool:
    """增量判断：该词 7 天内跑过。首屏仍会实抓（新岗位总在第一页出现），
    命中缓存且首屏 0 新增时跳过剩余页，避免整词重扫。"""
    ts = (cache.get(site) or {}).get(keyword, {}).get("ts", 0)
    return bool(ts) and time.time() - ts < CACHE_TTL


def mark_keyword(cache: dict, site: str, keyword: str) -> None:
    cache.setdefault(site, {})[keyword] = {"ts": int(time.time())}


def _ms_to_date(ms: int | float | str | None) -> str | None:
    if not ms:
        return None
    if isinstance(ms, str):
        # 字符串日期直接取前 10 位；字符串时间戳转数值
        if "-" in ms:
            return ms[:10]
        try:
            ms = int(ms)
        except ValueError:
            return None
    return time.strftime("%Y-%m-%d", time.localtime(ms / 1000))


def _normalize_gh(job: dict, board: str) -> dict | None:
    """Greenhouse job -> 统一 JD 记录（board 泛化：anthropic/togetherai/...）。"""
    import re

    pid = job.get("id")
    html = job.get("content") or ""
    body = re.sub(r"<[^>]+>", "\n", html)
    body = re.sub(r"\n{2,}|\s{2,}", "\n", body).strip()
    if not pid or len(body) < MIN_DESC:
        return None
    loc = job.get("location") or {}
    # anthropic 历史前缀 anthropic.jsonl 用 anth:，保持幂等兼容
    tag = "anth" if board == "anthropic" else f"gh-{board}"
    return {
        "jd_id": f"{tag}:{pid}",
        "platform": "anthropic" if board == "anthropic" else tag,
        "title": job.get("title") or "",
        "description": body[:4000],
        "publish_date": _ms_to_date(job.get("updated_at")),
        "city": loc.get("name") or None,
        "work_year": "",
        "salary": "",
        "keyword": "ALL",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_greenhouse(boards: list[str], _pages: int) -> dict:
    """Greenhouse 公开 boards：--keywords 传 board 名单，每个一次 API 全量。"""
    import urllib.request

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "greenhouse.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "greenhouse",
                                "boards": boards})
    per_board: dict[str, int] = {}
    for board in boards:
        fresh = 0
        try:
            req = urllib.request.Request(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126"})
            with urllib.request.urlopen(req, timeout=30) as r:
                jobs = json.loads(r.read()).get("jobs") or []
        except Exception as exc:  # noqa: BLE001 - 单 board 失败不阻塞
            run.log("jdcorp", board, "WARN", detail=str(exc)[:120])
            jobs = []
        for job in jobs:
            rec = _normalize_gh(job, board)
            if rec and rec["jd_id"] not in seen:
                seen.add(rec["jd_id"])
                with out.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fresh += 1
        run.log("jdcorp", board, "succeeded", count={"new": fresh})
        per_board[board] = fresh
        time.sleep(random.uniform(1.5, 3.0))
    metrics = {"new": sum(per_board.values()), "per_board": per_board,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def run_anthropic(_keywords: list[str], _pages: int) -> dict:
    """boards.greenhouse.io：一次 API 返回全量岗位（含 JD 正文 HTML），无翻页无关键词。"""
    import urllib.request

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "anthropic.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "anthropic"})
    req = urllib.request.Request(
        "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true",
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126"})
    with urllib.request.urlopen(req, timeout=30) as r:
        jobs = json.loads(r.read()).get("jobs") or []
    fresh = 0
    for job in jobs:
        rec = _normalize_gh(job, "anthropic")
        if rec and rec["jd_id"] not in seen:
            seen.add(rec["jd_id"])
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fresh += 1
    metrics = {"new": fresh, "total": len(jobs), "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def _normalize_tx(post: dict, keyword: str) -> dict | None:
    """腾讯 Query 帖 -> 统一 JD 记录（列表页只有职责正文，无要求段）。"""
    pid = post.get("PostId") or post.get("Id")
    body = (post.get("Responsibility") or "").strip()
    if not pid or len(body) < MIN_DESC:
        return None
    return {
        "jd_id": f"tx:{pid}",
        "platform": "tencent",
        "title": post.get("RecruitPostName") or "",
        "description": body,
        "publish_date": _ms_to_date(post.get("LastUpdateTime")),
        "city": post.get("LocationName") or None,
        "work_year": (post.get("RequireWorkYearsName") or "").replace("工作经验", ""),
        "salary": "",
        "keyword": keyword,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_tencent(keywords: list[str], pages: int) -> dict:
    """careers.tencent.com：GET /tencentcareer/api/post/Query，纯 HTTP 无需浏览器。"""
    import urllib.parse
    import urllib.request

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "tencent.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001 - 脏行跳过
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "tencent",
                                "keywords": keywords, "pages": pages})
    cache = load_cache()
    per_keyword: dict[str, int] = {}
    for kw in keywords:
        warm = cached_keyword(cache, "tencent", kw)
        fresh = 0
        for page in range(1, pages + 1):
            q = urllib.parse.urlencode({
                "timestamp": str(int(time.time() * 1000)), "countryId": "", "cityId": "",
                "bgIds": "", "productId": "", "categoryId": "", "parentCategoryId": "",
                "attrId": "", "keyword": "" if kw == "ALL" else kw,
                "pageIndex": page, "pageSize": 10,
                "language": "zh-cn", "pt": "1",
            })
            req = urllib.request.Request(
                f"https://careers.tencent.com/tencentcareer/api/post/Query?{q}",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126",
                         "Referer": "https://careers.tencent.com/zh-cn/search.html"})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    posts = (json.loads(r.read()).get("Data") or {}).get("Posts") or []
            except Exception as exc:  # noqa: BLE001 - 单页失败不阻塞
                run.log("jdcorp", f"{kw}#p{page}", "WARN", detail=str(exc)[:120])
                break
            got = 0
            for post in posts:
                rec = _normalize_tx(post, kw)
                if rec and rec["jd_id"] not in seen:
                    seen.add(rec["jd_id"])
                    with out.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fresh += 1
                    got += 1
            run.log("jdcorp", f"{kw}#p{page}", "succeeded", count={"new": got})
            if page == 1:
                mark_keyword(cache, "tencent", kw)
                if warm and got == 0:
                    break
            if got == 0:
                break
            time.sleep(random.uniform(2.0, 4.0))
        save_cache(cache)
        per_keyword[kw] = fresh

    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def _normalize_mt(post: dict, keyword: str) -> dict | None:
    """美团 getJobList -> 统一 JD 记录。"""
    pid = post.get("jobUnionId") or post.get("projectId")
    body = ((post.get("jobDuty") or "").strip() + "\n"
            + (post.get("jobRequirement") or "").strip()).strip()
    if not pid or len(body) < MIN_DESC:
        return None
    cities = [c.get("name") for c in post.get("cityList") or [] if c.get("name")]
    return {
        "jd_id": f"mt:{pid}",
        "platform": "meituan",
        "title": post.get("name") or "",
        "description": body,
        "publish_date": _ms_to_date(post.get("refreshTime")),
        "city": "/".join(cities[:2]) or None,
        "work_year": post.get("workYear") or "",
        "salary": "",
        "keyword": keyword,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_meituan(keywords: list[str], pages: int) -> dict:
    """zhaopin.meituan.com：goto 搜索页拦截 POST getJobList，点「下一页」翻页。"""
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "meituan.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "meituan",
                                "keywords": keywords, "pages": pages})
    cache = load_cache()
    per_keyword: dict[str, int] = {}

    def _drain(captured: list[dict], kw: str) -> int:
        fresh = 0
        for body in captured:
            data = (body or {}).get("data") or {}
            for post in data.get("list") or []:
                rec = _normalize_mt(post, kw)
                if rec and rec["jd_id"] not in seen:
                    seen.add(rec["jd_id"])
                    with out.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fresh += 1
        return fresh

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for kw in keywords:
            warm = cached_keyword(cache, "alibaba", kw)
            fresh = 0
            captured: list[dict] = []

            def on_resp(resp):  # noqa: ANN001
                if "getJobList" in resp.url:
                    try:
                        captured.append(resp.json())
                    except Exception:  # noqa: BLE001
                        pass

            page.on("response", on_resp)
            try:
                mt_q = f"keyword={urllib.parse.quote(kw)}" if kw != "ALL" else ""
                page.goto(
                    "https://zhaopin.meituan.com/web/position?" + mt_q,
                    wait_until="networkidle", timeout=45_000,
                )
                page.wait_for_timeout(2_500)
                fresh += _drain(captured, kw)
                run.log("jdcorp", f"{kw}#p1", "succeeded", count={"new": fresh})
                mark_keyword(cache, "alibaba", kw)
                if warm and fresh == 0:
                    per_keyword[kw] = fresh
                    continue
                for cur in range(2, pages + 1):
                    captured.clear()
                    try:
                        # 分页控件形态不定：antd next / 文本按钮双兜底
                        nxt = page.locator(".ant-pagination-next button, .ant-pagination-next")
                        if nxt.count() == 0:
                            nxt = page.get_by_text("下一页", exact=False)
                        nxt.first.click(timeout=8_000)
                        page.wait_for_timeout(3_000)
                    except Exception:  # noqa: BLE001
                        break
                    got = _drain(captured, kw)
                    fresh += got
                    run.log("jdcorp", f"{kw}#p{cur}", "succeeded", count={"new": got})
                    if got == 0:
                        break
                    time.sleep(random.uniform(2.0, 4.0))
            except Exception as exc:  # noqa: BLE001
                run.log("jdcorp", kw, "WARN", detail=str(exc)[:120])
            finally:
                page.remove_listener("response", on_resp)
            save_cache(cache)
            per_keyword[kw] = fresh
        browser.close()

    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def _normalize_xhs(post: dict, keyword: str) -> dict | None:
    """小红书 pageQueryPosition -> 统一 JD 记录。"""
    pid = post.get("positionId")
    body = ((post.get("duty") or "").strip() + "\n"
            + (post.get("qualification") or "").strip()).strip()
    if not pid or len(body) < MIN_DESC:
        return None
    return {
        "jd_id": f"xhs:{pid}",
        "platform": "xiaohongshu",
        "title": post.get("positionName") or "",
        "description": body,
        "publish_date": _ms_to_date(post.get("publishTime")),
        "city": "/".join(post.get("workplace") or [])[:24] or None,
        "work_year": "",
        "salary": "",
        "keyword": keyword,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_xiaohongshu(keywords: list[str], pages: int) -> dict:
    """job.xiaohongshu.com：goto 搜索页拦截 POST pageQueryPosition，点「下一页」。"""
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "xiaohongshu.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "xiaohongshu",
                                "keywords": keywords, "pages": pages})
    cache = load_cache()
    per_keyword: dict[str, int] = {}

    def _drain(captured: list[dict], kw: str) -> int:
        fresh = 0
        for body in captured:
            data = (body or {}).get("data") or {}
            for post in data.get("list") or []:
                rec = _normalize_xhs(post, kw)
                if rec and rec["jd_id"] not in seen:
                    seen.add(rec["jd_id"])
                    with out.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fresh += 1
        return fresh

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for kw in keywords:
            warm = cached_keyword(cache, "meituan", kw)
            fresh = 0
            captured: list[dict] = []

            def on_resp(resp):  # noqa: ANN001
                if "pageQueryPosition" in resp.url:
                    try:
                        captured.append(resp.json())
                    except Exception:  # noqa: BLE001
                        pass

            page.on("response", on_resp)
            try:
                xhs_q = f"positionName={urllib.parse.quote(kw)}" if kw != "ALL" else ""
                page.goto(
                    "https://job.xiaohongshu.com/social/position?" + xhs_q,
                    wait_until="networkidle", timeout=45_000,
                )
                page.wait_for_timeout(2_500)
                fresh += _drain(captured, kw)
                run.log("jdcorp", f"{kw}#p1", "succeeded", count={"new": fresh})
                mark_keyword(cache, "meituan", kw)
                if warm and fresh == 0:
                    per_keyword[kw] = fresh
                    continue
                for cur in range(2, pages + 1):
                    captured.clear()
                    try:
                        nxt = page.locator(".ant-pagination-next button, .ant-pagination-next")
                        if nxt.count() == 0:
                            nxt = page.get_by_text("下一页", exact=False)
                        nxt.first.click(timeout=8_000)
                        page.wait_for_timeout(3_000)
                    except Exception:  # noqa: BLE001
                        break
                    got = _drain(captured, kw)
                    fresh += got
                    run.log("jdcorp", f"{kw}#p{cur}", "succeeded", count={"new": got})
                    if got == 0:
                        break
                    time.sleep(random.uniform(2.0, 4.0))
            except Exception as exc:  # noqa: BLE001
                run.log("jdcorp", kw, "WARN", detail=str(exc)[:120])
            finally:
                page.remove_listener("response", on_resp)
            save_cache(cache)
            per_keyword[kw] = fresh
        browser.close()

    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def _normalize_vivo(post: dict, keyword: str) -> dict | None:
    """vivo portal page 帖 -> 统一 JD 记录。"""
    pid = post.get("job_id") or post.get("job_code")
    body = (post.get("job_desc") or "").strip()
    if not pid or len(body) < MIN_DESC:
        return None
    cities = [c.get("city") for c in post.get("job_location_list") or [] if c.get("city")]
    yoe = f"{post['yoe_min']}-{post.get('yoe_max') or ''}" if post.get("yoe_min") else ""
    return {
        "jd_id": f"vivo:{pid}",
        "platform": "vivo",
        "title": post.get("job_title") or "",
        "description": body,
        "publish_date": _ms_to_date(post.get("publish_timestamp")),
        "city": "/".join(dict.fromkeys(cities)) or None,
        "work_year": yoe,
        "salary": "",
        "keyword": keyword,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_vivo(keywords: list[str], pages: int) -> dict:
    """hr.vivo.com：POST /api/social/webSite/portal/page，纯 HTTP。"""
    import urllib.request

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "vivo.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "vivo",
                                "keywords": keywords, "pages": pages})
    cache = load_cache()
    per_keyword: dict[str, int] = {}
    for kw in keywords:
        warm = cached_keyword(cache, "vivo", kw)
        fresh = 0
        for page in range(1, pages + 1):
            body = json.dumps({
                "city_code_list": [], "company_id": 1, "group_id": 1, "user_id": None,
                "job_category_id_list": [],
                "keyword": "" if kw == "ALL" else kw,
                "max_results": 10, "page": page, "yoe_list": [], "loading": True,
            }).encode()
            req = urllib.request.Request(
                "https://hr.vivo.com/api/social/webSite/portal/page",
                data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126",
                         "Referer": "https://hr.vivo.com/jobs"})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    posts = json.loads(r.read()).get("data") or []
            except Exception as exc:  # noqa: BLE001
                run.log("jdcorp", f"{kw}#p{page}", "WARN", detail=str(exc)[:120])
                break
            got = 0
            for post in posts:
                rec = _normalize_vivo(post, kw)
                if rec and rec["jd_id"] not in seen:
                    seen.add(rec["jd_id"])
                    with out.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fresh += 1
                    got += 1
            run.log("jdcorp", f"{kw}#p{page}", "succeeded", count={"new": got})
            if page == 1:
                mark_keyword(cache, "vivo", kw)
                if warm and got == 0:
                    break
            if got == 0:
                break
            time.sleep(random.uniform(2.0, 4.0))
        save_cache(cache)
        per_keyword[kw] = fresh

    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def _normalize_ali(post: dict, keyword: str) -> dict | None:
    """阿里 position -> 统一 JD 记录。"""
    pid = post.get("id") or post.get("code")
    desc = (post.get("description") or "").strip()
    req = (post.get("requirement") or "").strip()
    body = (desc + "\n" + req).strip()
    if not pid or len(body) < MIN_DESC:
        return None
    exp = post.get("experience") or {}
    work_year = (
        f"{exp['from']}-"
        + (str(exp["to"]) if exp.get("to") else "")
        if exp.get("from") is not None
        else ""
    )
    return {
        "jd_id": f"ali:{pid}",
        "platform": "alibaba",
        "title": post.get("name") or "",
        "description": body,
        "publish_date": _ms_to_date(post.get("publishTime") or post.get("modifyTime")),
        "city": "/".join((post.get("workLocations") or [])[:2]) or None,
        "work_year": work_year,
        "salary": "",
        "keyword": keyword,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_alibaba(keywords: list[str], pages: int) -> dict:
    """talent-holding：goto 搜索页拦截 POST /position/search，点「下一页」翻页。"""
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "alibaba.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001 - 脏行跳过
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "alibaba",
                                "keywords": keywords, "pages": pages})
    cache = load_cache()
    per_keyword: dict[str, int] = {}

    def _drain(captured: list[dict], out_path: Path, kw: str, seen_set: set) -> int:
        fresh = 0
        for body in captured:
            data = ((body or {}).get("content") or {}).get("datas") or []
            for post in data:
                rec = _normalize_ali(post, kw)
                if rec and rec["jd_id"] not in seen_set:
                    seen_set.add(rec["jd_id"])
                    with out_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fresh += 1
        return fresh

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for kw in keywords:
            warm = cached_keyword(cache, "xiaohongshu", kw)
            fresh = 0
            captured: list[dict] = []

            def on_resp(resp):  # noqa: ANN001
                if "/position/search" in resp.url:
                    try:
                        captured.append(resp.json())
                    except Exception:  # noqa: BLE001
                        pass

            page.on("response", on_resp)
            try:
                ali_q = f"search={urllib.parse.quote(kw)}&" if kw != "ALL" else ""
                page.goto(
                    "https://talent-holding.alibaba.com/off-campus/position-list"
                    f"?lang=zh&{ali_q}",
                    wait_until="networkidle", timeout=45_000,
                )
                page.wait_for_timeout(2_500)
                fresh += _drain(captured, out, kw, seen)
                run.log("jdcorp", f"{kw}#p1", "succeeded", count={"new": fresh})
                mark_keyword(cache, "xiaohongshu", kw)
                if warm and fresh == 0:
                    per_keyword[kw] = fresh
                    continue
                # 第 2 页起点「下一页」，等待新一批响应追加
                for cur in range(2, pages + 1):
                    captured.clear()
                    try:
                        page.get_by_role("button", name="下一页").or_(
                            page.get_by_text("下一页", exact=True)
                        ).first.click(timeout=8_000)
                        page.wait_for_timeout(3_000)
                    except Exception:  # noqa: BLE001 - 无下一页即止
                        break
                    got = _drain(captured, out, kw, seen)
                    fresh += got
                    run.log("jdcorp", f"{kw}#p{cur}", "succeeded", count={"new": got})
                    if got == 0:
                        break
                    time.sleep(random.uniform(2.0, 4.0))
            except Exception as exc:  # noqa: BLE001 - 导航失败记录继续
                run.log("jdcorp", kw, "WARN", detail=str(exc)[:120])
            finally:
                page.remove_listener("response", on_resp)
            save_cache(cache)
            per_keyword[kw] = fresh
        browser.close()

    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def _normalize(post: dict, keyword: str) -> dict | None:
    """字节 job_post -> 统一 JD 记录（jdxtract targets 形状）。"""
    pid = post.get("id") or post.get("code")
    desc = (post.get("description") or "").strip()
    req = (post.get("requirement") or "").strip()
    body = (desc + "\n" + req).strip()
    if not pid or len(body) < MIN_DESC:
        return None
    cities = [c.get("name") for c in post.get("city_list") or [] if c.get("name")]
    return {
        "jd_id": f"bd:{pid}",
        "platform": "bytedance",
        "title": post.get("title") or "",
        "description": body,
        "publish_date": _ms_to_date(post.get("publish_time")),
        "city": "/".join(cities[:2]) or None,
        "work_year": "",
        "salary": "",
        "keyword": keyword,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_bytedance(keywords: list[str], pages: int, limit: int = 10) -> dict:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "bytedance.jsonl"
    seen = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001 - 脏行跳过
                continue

    run = RunContext("jdcorp", {"cmd": "run", "site": "bytedance",
                                "keywords": keywords, "pages": pages})
    cache = load_cache()
    per_keyword: dict[str, int] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for kw in keywords:
            warm = cached_keyword(cache, "bytedance", kw)
            fresh = 0
            for cur in range(1, pages + 1):
                captured: list[dict] = []

                def on_resp(resp):  # noqa: ANN001 - playwright 回调
                    if "/api/v1/search/job/posts" in resp.url:
                        try:
                            captured.append(resp.json())
                        except Exception:  # noqa: BLE001 - 挑战页跳过
                            pass

                page.on("response", on_resp)
                kw_q = f"keywords={urllib.parse.quote(kw)}&" if kw != "ALL" else ""
                url = (
                    "https://jobs.bytedance.com/experienced/position?"
                    f"{kw_q}current={cur}&limit={limit}"
                )
                try:
                    page.goto(url, wait_until="networkidle", timeout=45_000)
                    page.wait_for_timeout(2_500)
                except Exception as exc:  # noqa: BLE001 - 导航失败记录继续
                    run.log("jdcorp", f"{kw}#p{cur}", "WARN", detail=str(exc)[:120])
                finally:
                    page.remove_listener("response", on_resp)

                got = 0
                for body in captured:
                    posts = ((body or {}).get("data") or {}).get("job_post_list") or []
                    for post in posts:
                        rec = _normalize(post, kw)
                        if rec and rec["jd_id"] not in seen:
                            seen.add(rec["jd_id"])
                            with out.open("a", encoding="utf-8") as fh:
                                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            fresh += 1
                            got += 1
                run.log("jdcorp", f"{kw}#p{cur}", "succeeded", count={"new": got})
                if got == 0 and (cur >= 2 or warm):
                    break  # 连续空页：关键词池耗尽
                time.sleep(random.uniform(2.0, 4.0))
            mark_keyword(cache, "bytedance", kw)
            save_cache(cache)
            per_keyword[kw] = fresh
        browser.close()

    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword,
               "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def runall(keywords: list[str], pages: int, workers: int) -> int:
    """全部站点并行采集（每线程独立浏览器实例；纯 HTTP 站无额外开销）。"""
    import concurrent.futures as cf

    runners = {
        "bytedance": run_bytedance, "alibaba": run_alibaba,
        "tencent": run_tencent, "meituan": run_meituan,
        "xiaohongshu": run_xiaohongshu, "anthropic": run_anthropic,
        "greenhouse": lambda kws, pgs: run_greenhouse(  # noqa: E731
            ["togetherai", "scaleai", "databricks", "pinterest",
             "figma", "discord", "stripe", "duolingo"], pgs),
        "vivo": run_vivo,
    }
    results: dict[str, object] = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, keywords, pages): name for name, fn in runners.items()}
        for f in cf.as_completed(futs):
            name = futs[f]
            try:
                results[name] = f.result()
            except Exception as exc:  # noqa: BLE001 - 单站失败不阻塞其余
                results[name] = {"error": str(exc)[:200]}
    print(json.dumps(results, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdcorp")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--site", default="bytedance",
                       choices=["bytedance", "alibaba", "tencent", "meituan",
                                "xiaohongshu", "anthropic", "greenhouse",
                                "vivo"])
    p_run.add_argument("--keywords", nargs="+", required=True,
                       help="关键词列表；传 all 全量抓取（greenhouse 站传 board 名单）")
    p_run.add_argument("--pages", type=int, default=3)
    p_run.add_argument("--force", action="store_true", help="忽略 7 天关键词缓存")
    p_all = sub.add_parser("runall", help="全部站点并行采集")
    p_all.add_argument("--keywords", nargs="+", default=["ALL"],
                       help="默认 ALL 全量；也可传关键词列表")
    p_all.add_argument("--pages", type=int, default=10)
    p_all.add_argument("--workers", type=int, default=3)
    args = parser.parse_args(argv)

    if args.cmd == "runall":
        return runall(args.keywords, args.pages, args.workers)
    if args.force:
        cache = load_cache()
        cache.pop(args.site, None)
        save_cache(cache)
    keywords = ["ALL"] if args.keywords == ["all"] else args.keywords
    runner = {"alibaba": run_alibaba, "tencent": run_tencent,
              "meituan": run_meituan, "xiaohongshu": run_xiaohongshu,
              "anthropic": run_anthropic, "greenhouse": run_greenhouse,
              "vivo": run_vivo}.get(args.site, run_bytedance)
    result = runner(keywords, args.pages)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
