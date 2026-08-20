#!/usr/bin/env python
"""daemon 常驻后端冒烟测试：验证 RPC 协议、模型懒加载与常驻缓存加速。

用法：python tests/smoke_daemon.py
断言：
  1. ping：进程存活、GPU 信息、初始零模型加载
  2. classify_image：RPC 返回规范 JSON
  3. parse_ui 首次加载（15-25s）vs 常驻二次调用（应明显更快）
  4. ping：omniparser 已加载
  5. shutdown：进程退出
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent
TEST_IMG = Path(__file__).resolve().parent / ".smoke-tmp" / "ui_screenshot.png"


def start_daemon() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "dsh_visit", "daemon"],
        cwd=PKG_DIR,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
    )


class RPC:
    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self.nid = 0

    def call(self, method: str, params=None, timeout: float = 360) -> dict:
        self.nid += 1
        req = {"id": self.nid, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("daemon 无响应（进程退出？）")
        resp = json.loads(line)
        assert resp.get("id") == self.nid, f"id 不匹配: {resp}"
        if not resp.get("ok"):
            raise RuntimeError(f"{method} 失败: {resp.get('error')}")
        return resp["result"]


def main() -> int:
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            failures += 1

    assert TEST_IMG.exists(), f"测试图缺失: {TEST_IMG}"
    proc = start_daemon()
    try:
        rpc = RPC(proc)

        print("== ping（初始状态）==")
        p = rpc.call("ping")
        check("进程存活", p.get("pong") is True)
        check("GPU 信息", isinstance(p.get("gpu"), dict) and "used_mb" in p.get("gpu", {}), str(p.get("gpu"))[:80])
        loaded = p.get("models_loaded", {})
        check("初始零模型加载", not any(v for v in loaded.values()), str(loaded))

        print("== classify_image ==")
        r = rpc.call("classify_image", {"input": str(TEST_IMG)})
        check("分类返回", r.get("category") in ("content", "structure") and "confidence" in r, str(r)[:80])

        print("== parse_ui 首次加载 vs 常驻二次 ==")
        t0 = time.time()
        r1 = rpc.call("parse_ui", {"input": str(TEST_IMG)})
        t_first = time.time() - t0
        check("首次解析成功", r1.get("status") == "ok" and r1.get("element_count", 0) > 0, f"元素 {r1.get('element_count')}")
        print(f"    首次加载+解析: {t_first:.1f}s")

        t0 = time.time()
        r2 = rpc.call("parse_ui", {"input": str(TEST_IMG)})
        t_second = time.time() - t0
        check("常驻二次解析成功", r2.get("status") == "ok" and r2.get("element_count", 0) > 0)
        print(f"    常驻二次解析: {t_second:.1f}s")
        check("常驻加速生效（二次 < 首次的 1/3）", t_second < max(t_first / 3, 2.0), f"首次 {t_first:.1f}s / 二次 {t_second:.1f}s")

        print("== ping（模型已加载）==")
        p2 = rpc.call("ping")
        check("omniparser 已常驻", p2.get("models_loaded", {}).get("omniparser") is True, str(p2.get("models_loaded")))
        check("GPU 显存占用已上报", p2.get("gpu", {}).get("used_mb", 0) > 0, f"{p2.get('gpu', {}).get('used_mb')}MB")

        print("== shutdown ==")
        rpc.call("shutdown", timeout=10)
        time.sleep(1.0)
        check("进程已退出", proc.poll() is not None, f"exit={proc.poll()}")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    print(f"\n结果: {'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
