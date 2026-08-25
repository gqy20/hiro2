"""jdserve: 远程浏览器抓取服务的启停（Xvfb + Chrome/CDP + x11vnc + noVNC）。

这是 jdauto/jdlisten 的运行前提。完整流程：

    uv run scripts/jdserve.py start          # 启动虚拟显示 + Chrome + VNC/noVNC
    用户浏览器打开 http://<本机IP>:6080/vnc.html  # noVNC 操作远程 Chrome
    用户在远程 Chrome 里登录 51job 并手动搜索一次   # "焐热" WAF 信誉（关键！）
    uv run scripts/jdauto.py run --keywords ...     # 自动抓搜索层
    uv run scripts/jdauto.py detail                 # 自动抓详情
    uv run scripts/jdserve.py stop

原理：51job 的 WAF 对冷浏览器/纯 cookie 的程序化导航返回空结果（软封锁）；
真人手动操作一次后，同一浏览器内的 CDP 导航即可正常返回。
"""

from __future__ import annotations

import argparse
import subprocess
import time
import urllib.request
from pathlib import Path

XVFB = ["Xvfb", ":99", "-screen", "0", "1600x900x24"]
CHROME = [
    "google-chrome-stable",
    "--user-data-dir=/tmp/remote-chrome",
    "--remote-debugging-port=9222",
    "--no-first-run",
    "--window-position=0,0",
    "--window-size=1580,860",
    "about:blank",
]
X11VNC = ["x11vnc", "-display", ":99", "-localhost", "-forever", "-shared", "-nopw", "-quiet"]
WEBSOCKIFY = ["websockify", "--web=/usr/share/novnc", "-d", "6080", "localhost:5900"]


def _spawn(cmd: list[str], env_display: str | None = None) -> subprocess.Popen:
    import os

    env = dict(os.environ)
    if env_display:
        env["DISPLAY"] = env_display
    log = "/tmp/" + Path(cmd[0]).name + ".log"
    fh = open(log, "ab")
    return subprocess.Popen(cmd, env=env, stdout=fh, stderr=fh, start_new_session=True)


def _alive(pattern: str) -> bool:
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True)
    return r.returncode == 0


def _cdp_ok() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2)
        return True
    except Exception:  # noqa: BLE001 - 任何失败都视为未就绪
        return False


def cmd_start() -> int:
    if _cdp_ok():
        print("已在运行（CDP 9222 可用），noVNC: http://<本机IP>:6080/vnc.html")
        return 0
    _spawn(XVFB)
    time.sleep(1)
    _spawn(CHROME, env_display=":99")
    time.sleep(3)
    _spawn(X11VNC)
    time.sleep(1)
    _spawn(WEBSOCKIFY)
    time.sleep(2)
    for _ in range(10):
        if _cdp_ok():
            break
        time.sleep(1)
    status = cmd_status()
    print("下一步：noVNC 打开远程浏览器 -> 登录 51job -> 手动搜索一次（焐热）-> 跑 jdauto")
    return 0 if status == 0 else 1


def cmd_stop() -> int:
    for pattern in ("remote-chrome", "Xvfb :99", "x11vnc", "websockify.*6080"):
        subprocess.run(["pkill", "-f", pattern], capture_output=True)
    time.sleep(1)
    print("已停止全部服务")
    return 0


def cmd_status() -> int:
    ok = {
        "Xvfb": _alive("Xvfb :99"),
        "Chrome/CDP": _cdp_ok(),
        "x11vnc": _alive("x11vnc"),
        "noVNC": _alive("websockify"),
    }
    for name, alive in ok.items():
        print(f"  {name}: {'✓' if alive else '✗'}")
    print("  noVNC 地址: http://<本机IP>:6080/vnc.html")
    return 0 if all(ok.values()) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdserve")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    return {"start": cmd_start, "stop": cmd_stop, "status": cmd_status}[args.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
