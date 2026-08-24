"""Validate Conventional Commit messages for Hiro2."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADER = re.compile(
    r"^(feat|fix|docs|refactor|test|chore|build|ci|perf|style)"
    r"(?:\(([a-z0-9][a-z0-9._/-]*)\))?!?:\s+\S.+$"
)
MAX_HEADER_LENGTH = 72


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: cmcheck.py <commit-message-file>", file=sys.stderr)
        return 2

    message_file = Path(sys.argv[1])
    lines = message_file.read_text(encoding="utf-8").splitlines()
    header = next((line.strip() for line in lines if line.strip() and not line.startswith("#")), "")

    if len(header) > MAX_HEADER_LENGTH:
        print(f"提交标题不能超过 {MAX_HEADER_LENGTH} 个字符: {header}", file=sys.stderr)
        return 1
    if HEADER.fullmatch(header):
        return 0

    print("提交信息必须遵循 Conventional Commits 格式。", file=sys.stderr)
    print("格式: type(scope): 摘要", file=sys.stderr)
    print(
        "type: feat | fix | docs | refactor | test | chore | build | ci | perf | style",
        file=sys.stderr,
    )
    print("示例: feat(temporal): 增加日报导入", file=sys.stderr)
    print("示例: docs: 更新数据路线图", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
