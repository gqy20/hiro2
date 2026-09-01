"""Embedding 适配层：网关 /v1/embeddings（qwen3-embedding:8b，4096 维）。

供判例检索（RAG）使用：JD 判例库构建与查询共用同一模型。
离线测试不触发网络——测试直接构造向量。
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from .settings import LLMSettings


def embed_texts(texts: list[str], *, batch: int = 32) -> list[list[float]]:
    """批量文本 -> 向量（网关 OpenAI 兼容 /v1/embeddings）。"""
    settings = LLMSettings()
    base = (settings.hiro2_llm_base_url or "").rstrip("/")
    key = settings.hiro2_llm_api_key or ""
    model = settings.hiro2_llm_model_embedding or "qwen3-embedding:8b"
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        payload = json.dumps({"model": model, "input": texts[i : i + batch]}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/embeddings",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        out.extend(item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"]))
    return out


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度（判例库 <= 千级，暴力计算足够）。"""
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


def save_embeddings(path: Path, records: list[dict]) -> None:
    """判例向量库落盘（JSONL：每行 jd_id/expect/text/embedding）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )


def load_embeddings(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
