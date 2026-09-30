"""真实 LLM API 封装（OpenAI 兼容接口，支持 OpenAI / DeepSeek 等）。"""

import os
import time
from typing import Any, cast, Dict, List, Optional

from .logger import logger

DEFAULT_MODEL = "gpt-4o-mini"


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


class LLMClient:
    def __init__(self, api_key=None, base_url=None, model=None, timeout: float = 60.0, retries: int = 2) -> None:
        self.api_key = api_key or _first_env("OPENAI_API_KEY", "LLM_API_KEY", "DEEPSEEK_API_KEY", "API_KEY")
        self.base_url = base_url or _first_env("OPENAI_BASE_URL", "LLM_BASE_URL", "DEEPSEEK_BASE_URL", "BASE_URL")
        self.model = model or _first_env("LLM_MODEL", "OPENAI_MODEL", "DEEPSEEK_MODEL", "MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.retries = retries
        self._client = None
        logger.info("LLMClient 配置: base_url=%s model=%s", self.base_url or "（OpenAI 默认地址）", self.model)

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("未安装 openai，请先执行: pip install openai") from exc
            kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("未配置 API Key，请设置 OPENAI_API_KEY / LLM_API_KEY / DEEPSEEK_API_KEY / API_KEY 环境变量")
        last_error: Any = None
        for attempt in range(self.retries + 1):
            try:
                client = self._ensure_client()
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:  # 网络/超时等，退避后重试
                last_error = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM 调用失败: {last_error}")
