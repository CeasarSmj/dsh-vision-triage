"""L1 content 类数据下载：真实照片（Lorem Picsum / Unsplash 摄影作品）。

ADR-3：用网络真实数据，不用合成数据。picsum.photos 提供 Unsplash 的真实摄影照片
（风景/建筑/人像/静物等），URL 带随机种子，适合批量下载。

用法：
  python -m dsh_visit.train.fetch_content --count 1000 [--out <data>/raw/l1/content]
"""

import argparse
import sys
from pathlib import Path

from .._paths import DATA_DIR

DEFAULT_OUT = DATA_DIR / "raw" / "l1" / "content"


def fetch_content(count: int, out: Path, workers: int = 8) -> None:
    import concurrent.futures
    import urllib.request

    out.mkdir(parents=True, exist_ok=True)

    def download_one(i: int) -> tuple[int, bool]:
        # 800x600 随机真实照片；随机种子避免与训练 epoch 冲突的重复
        url = f"https://picsum.photos/800/600?random={10000 + i}"
        dest = out / f"picsum_{i:05d}.jpg"
        if dest.exists():
            return i, True
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dsh-vision-triage/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            return i, dest.stat().st_size > 10_000  # 有效照片应 >10KB
        except Exception:
            return i, False

    ok = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(download_one, i): i for i in range(count)}
        for fut in concurrent.futures.as_completed(futures):
            i, success = fut.result()
            if success:
                ok += 1
            if ok % 200 == 0:
                print(f"  进度: {ok}/{count}")
    print(f"完成: {ok}/{count} 张照片 → {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 L1 content 类真实照片")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    fetch_content(args.count, Path(args.out), args.workers)


if __name__ == "__main__":
    sys.exit(main())
