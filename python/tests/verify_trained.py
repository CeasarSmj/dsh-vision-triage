"""daemon 全链路验证：新训练的 L1/L2 权重经 RPC 是否 degraded=false。"""

import json
import os
import subprocess
import sys


def main() -> None:
    p = subprocess.Popen(
        [sys.executable, "-m", "dsh_visit", "daemon"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    nid = 0

    def call(method, params=None):
        nonlocal nid
        nid += 1
        p.stdin.write(json.dumps({"id": nid, "method": method, "params": params or {}}) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())

    r1 = call("classify_image", {"input": r"C:\Users\Administrator\Pictures\Screenshots\屏幕截图 2026-08-20 104954.png"})
    r2 = call("classify_structure", {"input": r"C:\Users\Administrator\Pictures\Screenshots\屏幕截图 2026-08-20 233712.png"})
    r3 = call("classify_image", {"input": r"D:\temple\dsh-vision-triage\data\raw\l1\content\picsum_00001.jpg"})
    r4 = call("ping")
    print(f"Blender L1: {r1['result']['category']} conf={r1['result']['confidence']:.3f} degraded={r1['result']['degraded']}")
    print(f"深色资源管理器 L2: {r2['result']['category']} conf={r2['result']['confidence']:.3f}")
    print(f"照片 L1: {r3['result']['category']} conf={r3['result']['confidence']:.3f} degraded={r3['result']['degraded']}")
    print(f"models_loaded: {r4['result']['models_loaded']}")
    call("shutdown")


if __name__ == "__main__":
    main()
