"""mitmjd: mitmproxy 插件 —— 网络层被动捕获 zhipin/51job 接口响应。

启动（由 jdserve boss 模式调用）：
    ~/.local/bin/mitmdump -s scripts/mitmjd.py -p 8888 --set block_global=false

浏览器经 --proxy-server=127.0.0.1:8888 走本代理；页面 JS 无法感知，
__zp_stoken__ 等签名正常计算。命中接口的响应体追加写入
data/raw/jd/boss/mitm-capture.jsonl。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from mitmproxy import http

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "jd" / "boss" / "mitm-capture.jsonl"
WATCH = ("zhipin.com/wapi/", "51job.com/api/job/search-pc")


class JdCapture:
    def __init__(self) -> None:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        self._fh = OUT.open("a", encoding="utf-8")

    def response(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url
        is_detail_html = "zhipin.com/job_detail/" in url
        if not is_detail_html and not any(k in url for k in WATCH):
            return
        if flow.response is None:
            return
        if is_detail_html:
            body: object = flow.response.text  # 详情页 SSR HTML 原文
        else:
            ct = flow.response.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = json.loads(flow.response.text)
            except Exception:  # noqa: BLE001 - 非 JSON 跳过
                return
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "url": url,
            "status": flow.response.status_code,
            "body": body,
        }
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()

    def done(self) -> None:
        self._fh.close()


addons = [JdCapture()]
