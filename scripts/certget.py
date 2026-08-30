"""certget: 学练赛证"证"段数据采集（osta 标准库 + 1+X 证书 + 华为认证）。

用法：
    uv run scripts/certget.py osta          # 人社部国家职业标准目录（702 条，含 PDF 路径）
    uv run scripts/certget.py onex          # 教育部 1+X 职业技能等级证书与标准
    uv run scripts/certget.py huawei        # 华为职业认证全景（HCIA/HCIP/HCIE 树）
    uv run scripts/certget.py pdf <编码>    # 下载指定职业编码的标准 PDF（raw 快照）
    uv run scripts/certget.py all           # 三个目录源全跑（不含 PDF）

数据源（2026-08-30 实测，全部公开 JSON 无鉴权，详见 docs/research/xlzsz-channels.md）：
  osta    https://www.osta.org.cn/api/public/skillStandardList（技能人才评价工作网）
  onex    https://www.ncb.edu.cn/portal/exam/api/open/{certificate/pubQuery,standard/open/query}
  huawei  https://apigw-04.huawei.com/api/services/lras/ecms/v1/getProfessionalCertification

产物：
  data/raw/certs/osta-standards.jsonl        原始标准目录快照
  data/raw/certs/onex-certificates.jsonl     1+X 证书目录快照
  data/raw/certs/onex-standards.jsonl        1+X 等级标准目录快照
  data/raw/certs/huawei-certs.jsonl          华为认证树快照
  data/raw/certs/osta-pdf/<职业编码>.pdf     标准 PDF 原文（按需下载）
  data/processed/certs/cert-catalog.jsonl    三源归一证书目录（norm 层）

幂等：目录快照全量重写（响应即事实），PDF 按 code 判存在跳过。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "certs"
PROC = ROOT / "data" / "processed" / "certs"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126", "Accept": "application/json"}
SLEEP = 0.6

# 数字技术相关关键词（osta nameCode 搜索 + onex 关键词，两组共用）
RELATED_KEYS = (
    "人工智能",
    "大数据",
    "云计算",
    "数据",
    "智能",
    "信息",
    "软件",
    "网络",
    "安全",
)

# osta 标准库：一次 pageSize 拉全量目录（702 条），本地再按关键词筛
OSTA_LIST = "https://www.osta.org.cn/api/public/skillStandardList"
OSTA_PDF = "https://www.osta.org.cn/api/sys/downloadFile/decrypt?fileName="
ONEX_CERT = "https://www.ncb.edu.cn/portal/exam/api/open/certificate/pubQuery"
ONEX_STD = "https://www.ncb.edu.cn/portal/exam/api/open/standard/open/query"
HW_API = (
    "https://apigw-04.huawei.com/api/services/lras/ecms/v1/getProfessionalCertification"
    "?a2Flag=N&X-HW-ID=com.huawei.prm.talent&env=&language=zh_CN"
)


def _get(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={**UA, "Content-Type": "application/json", "Origin": "https://vslc.ncb.edu.cn"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- osta 标准库


def fetch_osta_list() -> list[dict]:
    """拉 osta 标准库全量目录（702 条，pageSize=800 一次取完）。"""
    data = _get(f"{OSTA_LIST}?pageSize=800&pageNum=1&total=0&nameCode=&status=1")
    body = data.get("body") or {}
    return body.get("list") or []


def cmd_osta(run: RunContext) -> dict:
    items = fetch_osta_list()
    run.log("osta", "fetched", "progress", count={"standards": len(items)})
    _write_jsonl(RAW / "osta-standards.jsonl", items)
    related = [x for x in items if any(k in x.get("name", "") for k in RELATED_KEYS)]
    run.log("osta", "filtered", "progress", count={"related": len(related)})
    return {
        "source": "osta",
        "total": len(items),
        "related": len(related),
        "out": str((RAW / "osta-standards.jsonl").relative_to(ROOT)),
    }


def cmd_pdf(run: RunContext, code: str) -> dict:
    """下载指定职业编码的标准 PDF 到 raw/certs/osta-pdf/。"""
    items = fetch_osta_list()
    target = next((x for x in items if (x.get("code") or "").strip() == code), None)
    if not target:
        raise SystemExit(f"职业编码 {code} 不在标准库中（可用关键词先查 osta 命令产物）")
    info = target.get("standardInfo") or ""
    if not info:
        raise SystemExit(f"{code} 无标准 PDF 路径")
    url = OSTA_PDF + urllib.parse.quote(info, safe="")
    dest = RAW / "osta-pdf" / f"{code}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        run.log("pdf", code, "SKIPPED", detail="已存在")
        return {"code": code, "out": str(dest.relative_to(ROOT)), "skipped": True}
    req = urllib.request.Request(
        url, headers={**UA, "Referer": "https://www.osta.org.cn/skillStandard"}
    )
    with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as fh:
        fh.write(r.read())
    if dest.read_bytes()[:4] != b"%PDF":
        dest.unlink()
        run.log("pdf", code, "ERROR", error_type="not_pdf", error_message="响应非 PDF")
        raise SystemExit(f"{code} 下载失败：响应不是 PDF")
    run.log("pdf", code, "SUCCEEDED", count={"bytes": dest.stat().st_size})
    return {"code": code, "name": target["name"], "out": str(dest.relative_to(ROOT))}


# ---------------------------------------------------------------- 1+X


# 1+X API 的 pageNum/pageSize 实测被服务端忽略（任何页返回同一首页，2026-08-30），
# 无法翻页拉全量 1237 条；改为数字技术域关键词词典遍历 + 唯一 id 去重聚合。
ONEX_KEYS = (
    "人工智能",
    "智能",
    "数据",
    "信息",
    "软件",
    "网络",
    "大模型",
    "机器学习",
    "云计算",
    "机器人",
    "互联网",
    "数字",
    "物联网",
    "区块链",
)


def _onex_pages(run: RunContext, api: str, key: str, label: str, kw: str | None) -> list[dict]:
    """1+X 采集：关键词遍历 + 唯一 id 去重。

    服务端固定每查询返回 10 条且忽略分页参数，逐关键词请求后按唯一 id 聚合。
    口径：数字技术域相关子集（非全量 1237 条），局限已记录于 SOURCES.yml。
    """
    seen: dict[str, dict] = {}
    for k in [kw] if kw else ONEX_KEYS:
        payload: dict = {"pageNum": 1, "pageSize": 10, key: k}
        data = _post_json(api, payload).get("data") or {}
        batch = data.get("records") or []
        for r in batch:
            rid = str(r.get("certificateId") or r.get("standardId") or "")
            if rid and rid not in seen:
                seen[rid] = r
        run.log(
            label,
            f"kw:{k}",
            "progress",
            count={"unique": len(seen), "server_total": data.get("total")},
        )
        time.sleep(SLEEP)
    return list(seen.values())


def cmd_onex(run: RunContext, kw: str | None) -> dict:
    # 口径修正：API 的 pageNum/pageSize 实测被忽略（任何页返回同一首页），无法翻页拉全量；
    # 改为数字技术域关键词遍历 + 唯一 id 去重聚合（局限记录于 xlzsz-known-limits.md）。
    keys = (
        [kw]
        if kw
        else [
            "人工智能",
            "智能",
            "数据",
            "信息",
            "软件",
            "网络",
            "大模型",
            "机器学习",
            "云计算",
            "机器人",
            "互联网",
            "数字",
            "编程",
            "算法",
        ]
    )
    cert_map: dict[str, dict] = {}
    std_map: dict[str, dict] = {}
    endpoints = (
        (ONEX_CERT, cert_map, "certificateName", "certificateId"),
        (ONEX_STD, std_map, "standardName", "standardId"),
    )
    for k in keys:
        for api, m, fld, idkey in endpoints:
            payload = {"pageNum": 1, "pageSize": 10, fld: k}
            data = _post_json(api, payload).get("data") or {}
            for r in data.get("records") or []:
                rid = str(r.get(idkey) or "")
                if rid and rid not in m:
                    m[rid] = r
            run.log(
                "onex",
                f"kw:{k}",
                "progress",
                count={"certs": len(cert_map), "stds": len(std_map)},
            )
        time.sleep(SLEEP)
    certs = list(cert_map.values())
    stds = list(std_map.values())
    _write_jsonl(RAW / "onex-certificates.jsonl", certs)
    _write_jsonl(RAW / "onex-standards.jsonl", stds)
    return {
        "source": "onex",
        "keywords": len(keys),
        "certificates": len(certs),
        "standards": len(stds),
        "out": [
            str((RAW / "onex-certificates.jsonl").relative_to(ROOT)),
            str((RAW / "onex-standards.jsonl").relative_to(ROOT)),
        ],
    }


# ---------------------------------------------------------------- 华为认证


def cmd_huawei(run: RunContext) -> dict:
    data = _get(HW_API).get("data") or []
    run.log("huawei", "fetched", "progress", count={"categories": len(data)})
    flat: list[dict] = []
    for cat in data:
        for child in cat.get("childItemList") or []:
            for level_key in ("hciaList", "hcipList", "hcieList"):
                for cert in child.get(level_key) or []:
                    flat.append(
                        {
                            "category": cat.get("itemName"),
                            "direction": child.get("itemName"),
                            "level": level_key.replace("List", ""),
                            "name": cert.get("certifiedProductName"),
                            "fullname": cert.get("certifiedProductFullname"),
                            "introduction": cert.get("introduction"),
                            "prerequisites": cert.get("prerequisites"),
                            "amount": cert.get("amount"),
                            "exam_code": cert.get("associatedExamCode") or cert.get("examCode"),
                            "version": cert.get("version"),
                        }
                    )
    _write_jsonl(RAW / "huawei-certs.jsonl", flat)
    ai = [c for c in flat if "AI" in (c["name"] or "")]
    run.log("huawei", "flattened", "progress", count={"certs": len(flat), "ai": len(ai)})
    return {
        "source": "huawei",
        "total": len(flat),
        "ai_related": len(ai),
        "out": str((RAW / "huawei-certs.jsonl").relative_to(ROOT)),
    }


# ---------------------------------------------------------------- 归一层


def _norm_onex_grade(code: str | None) -> str:
    return {"1": "初级", "2": "中级", "3": "高级"}.get(str(code or ""), "")


def cmd_normalize(run: RunContext) -> dict:
    """三源归一为 cert-catalog.jsonl：统一 cert_id/name/issuer/level/effective_from/fields。"""
    records: list[dict] = []

    osta_path = RAW / "osta-standards.jsonl"
    if osta_path.is_file():
        for line in osta_path.open(encoding="utf-8"):
            r = json.loads(line)
            records.append(
                {
                    "cert_id": f"osta-std-{r.get('id', r['code'])}",
                    "name": r["name"],
                    "type": "national_standard",
                    "issuer": "人力资源和社会保障部",
                    "level": "",
                    "career_code": r["code"],
                    "effective_from": (r.get("issueTime") or "")[:10],
                    "doc_number": r.get("issueNumber"),
                    "pdf": bool(r.get("standardInfo")),
                    "source": "osta",
                    "source_url": "https://www.osta.org.cn/skillStandard",
                }
            )

    onex_path = RAW / "onex-certificates.jsonl"
    if onex_path.is_file():
        for line in onex_path.open(encoding="utf-8"):
            r = json.loads(line)
            grade = _norm_onex_grade((r.get("certificateGrade") or {}).get("code"))
            records.append(
                {
                    "cert_id": f"onex-{r.get('certificateId')}",
                    "name": r.get("certificateName"),
                    "type": "onex_certificate",
                    "issuer": r.get("xzhOrgName"),
                    "level": grade,
                    "career_code": "",
                    "effective_from": r.get("stateDt"),
                    "description": (r.get("certificateDesc") or "")[:500],
                    "source": "onex",
                    "source_url": "https://vslc.ncb.edu.cn/gateway/Certificate",
                }
            )

    hw_path = RAW / "huawei-certs.jsonl"
    if hw_path.is_file():
        for line in hw_path.open(encoding="utf-8"):
            r = json.loads(line)
            records.append(
                {
                    "cert_id": f"hw-{(r['name'] or '').lower().replace(' ', '-')}",
                    "name": r["name"],
                    "type": "vendor_cert",
                    "issuer": "华为",
                    "level": {"hcia": "工程师", "hcip": "高级工程师", "hcie": "专家"}.get(
                        r["level"], ""
                    ),
                    "direction": r.get("direction"),
                    "introduction": (r.get("introduction") or "")[:500],
                    "amount": r.get("amount"),
                    "source": "huawei",
                    "source_url": "https://e.huawei.com/cn/talent/cert/",
                }
            )

    _write_jsonl(PROC / "cert-catalog.jsonl", records)
    by_source: dict[str, int] = {}
    for rec in records:
        by_source[rec["source"]] = by_source.get(rec["source"], 0) + 1
    run.log("normalize", "merged", "SUCCEEDED", count={"total": len(records), **by_source})
    return {
        "total": len(records),
        "by_source": by_source,
        "out": str((PROC / "cert-catalog.jsonl").relative_to(ROOT)),
    }


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="certget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("osta")
    p_kw = sub.add_parser("onex")
    p_kw.add_argument("--kw", default=None, help="按证书/标准名过滤（默认全量）")
    sub.add_parser("huawei")
    p_pdf = sub.add_parser("pdf")
    p_pdf.add_argument("code", help="职业编码，如 2-02-10-09")
    sub.add_parser("all")
    sub.add_parser("norm", help="三源归一为 cert-catalog.jsonl")
    args = parser.parse_args(argv)

    if args.cmd == "osta":
        run = RunContext("certget", {"cmd": "osta"})
        result = cmd_osta(run)
    elif args.cmd == "onex":
        run = RunContext("certget", {"cmd": "onex", "kw": args.kw})
        result = cmd_onex(run, args.kw)
    elif args.cmd == "huawei":
        run = RunContext("certget", {"cmd": "huawei"})
        result = cmd_huawei(run)
    elif args.cmd == "pdf":
        run = RunContext("certget", {"cmd": "pdf", "code": args.code})
        result = cmd_pdf(run, args.code)
    elif args.cmd == "all":
        run = RunContext("certget", {"cmd": "all"})
        result = {
            "osta": cmd_osta(run),
            "onex": cmd_onex(run, None),
            "huawei": cmd_huawei(run),
            "norm": cmd_normalize(run),
        }
    else:  # norm
        run = RunContext("certget", {"cmd": "norm"})
        result = cmd_normalize(run)

    run.finish(result)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
