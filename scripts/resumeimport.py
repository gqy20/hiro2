"""resumeimport: 既有简历文件批量登记入档（不解析，source=imported）。

用法：
    uv run scripts/resumeimport.py run [目录]      # 默认 data/fixtures/resumes-div/out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.candidates.archive import import_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "data" / "fixtures" / "resumes-div" / "out"


def cmd_run(directory: Path) -> dict:
    files = (
        sorted(
            p
            for p in directory.iterdir()
            if p.suffix.lower() in (".pdf", ".docx", ".txt", ".md")
            # -2col 是同内容的版式变体，仅用于解析回归，不重复入档
            and "-2col" not in p.stem
        )
        if directory.is_dir()
        else []
    )
    imported, skipped = 0, 0
    for p in files:
        try:
            import_file(p)
            imported += 1
        except ValueError:
            skipped += 1  # 已入档
    return {"imported": imported, "skipped": skipped, "dir": str(directory)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resumeimport")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("directory", nargs="?", default=str(DEFAULT_DIR))
    args = parser.parse_args(argv)
    print(json.dumps(cmd_run(Path(args.directory)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
