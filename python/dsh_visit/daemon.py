"""dsh_visit 常驻后端（daemon）：行式 JSON-RPC 服务。

背景：本地推理模型（尤其 OmniParser 的 Florence-2，约 1GB）每次以子进程方式调用
都要重新加载（15-25s）。本模块提供一个常驻进程：Node 插件 `spawn python -m dsh_visit daemon`
后通过 stdin/stdout 交换换行分隔的 JSON-RPC 消息，模型引擎在进程内缓存，
首次调用加载、之后秒级响应。

协议：
  请求（每行一个 JSON）：{id, method, params}
  响应（每行一个 JSON）：{id, ok: true, result} 或 {id, ok: false, error}
  控制：method="ping"（状态探活）/ "shutdown"（退出，归还 GPU 显存）

方法（复用 cli 层同一套实现，进程内引擎缓存）：
  classify_image / classify_structure / detect_image / ocr / parse_ui / ping / shutdown

注意：
  - 模型的进度输出（ultralytics / tqdm / easyocr）会被重定向到 stderr，
    避免污染 stdout 协议；响应经保留的真实 stdout fd 输出。
  - 引擎均为模块级单例（懒加载）：进程拉起时零 GPU 占用，首次调用相应方法才加载。
"""

import json
import os
import sys
import time

# ---- stdout 保护：模型库的 print/tqdm 一律改道 stderr，协议行走真实 fd ----
_real_stdout = os.fdopen(os.dup(1), "w", encoding="utf-8")


def _emit(payload: dict) -> None:
    _real_stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _real_stdout.flush()


class _StdoutRedirect:
    """吞掉模型库对 sys.stdout 的写入（转交 stderr，便于排查）。"""

    def write(self, data: str):
        try:
            sys.__stderr__.write(data)
        except Exception:
            pass

    def flush(self):
        try:
            sys.__stderr__.flush()
        except Exception:
            pass


sys.stdout = _StdoutRedirect()

# ---- 方法实现（复用 cli / 各模块，引擎懒加载单例）----

_METHODS: dict[str, callable] = {}


def _register(fn):
    _METHODS[fn.__name__] = fn
    return fn


@_register
def ping(params):
    gpu = {}
    try:
        import torch

        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            gpu = {
                "name": torch.cuda.get_device_name(0),
                "free_mb": round(free / 1048576),
                "total_mb": round(total / 1048576),
                "used_mb": round((total - free) / 1048576),
            }
    except Exception as exc:
        gpu = {"error": str(exc)}
    return {
        "pong": True,
        "uptime_s": round(time.time() - _START_TIME, 1),
        "gpu": gpu,
        "models_loaded": {
            "omniparser": _is_loaded("_engine", "dsh_visit.ui_parse.parser"),
            "ocr": _is_loaded("_engine", "dsh_visit.ocr.ocr"),
            "table": _is_loaded("_table_engine", "dsh_visit.ocr.ocr"),
            "classifier": _is_loaded("_engine", "dsh_visit.classify.model") or None,
        },
    }


def _is_loaded(attr: str, module: str) -> bool:
    try:
        import importlib

        mod = importlib.import_module(module)
        return getattr(mod, attr, None) is not None
    except Exception:
        return False


@_register
def classify_image(params):
    from .classify import classify_l1

    return classify_l1(params["input"])


@_register
def classify_structure(params):
    from .classify import classify_l2

    return classify_l2(params["input"])


@_register
def detect_image(params):
    from .detect import detect_natural_image

    return detect_natural_image(
        params["input"],
        text_prompts=params.get("text_prompts"),
        conf=params.get("conf", 0.25),
        max_detections=params.get("max_detections", 100),
    )


@_register
def ocr(params):
    from .ocr import ocr_image

    return ocr_image(params["input"], with_table=bool(params.get("with_table")))


@_register
def parse_ui(params):
    from .ui_parse import parse_ui_screenshot

    return parse_ui_screenshot(params["input"])


@_register
def shutdown(params):
    # 响应先回，随后进程退出
    _emit({"id": params.get("__id__"), "ok": True, "result": {"bye": True}})
    os._exit(0)


# ---- 主循环 ----

_START_TIME = time.time()


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:  # stdin EOF（父进程退出/关闭）→ 释放资源退出
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            params = req.get("params") or {}
            fn = _METHODS.get(method)
            if fn is None:
                raise ValueError(f"未知方法: {method}")
            if method == "shutdown":
                params["__id__"] = req.get("id")
            result = fn(params)
            _emit({"id": req.get("id"), "ok": True, "result": result})
        except Exception as exc:
            _emit({"id": req.get("id"), "ok": False, "error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
