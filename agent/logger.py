"""执行日志与工具调用 trace。"""

import logging
import time
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent")


class Trace:
    """记录 Agent 每轮的思考、工具调用与结果，便于调试与回放。"""

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def log(self, **kwargs: Any) -> None:
        entry = {"ts": time.time(), **kwargs}
        self.entries.append(entry)
        logger.info(" | ".join(f"{k}={v}" for k, v in kwargs.items()))

    def reset(self) -> None:
        self.entries.clear()
