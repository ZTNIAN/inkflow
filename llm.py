"""LLM 抽象层 — 复用原项目设计，精简到只保留核心"""
from __future__ import annotations
import json, re, time
from dataclasses import dataclass
from typing import Callable, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


@dataclass
class Message:
    role: str   # system | user | assistant
    content: str
    def to_dict(self): return {"role": self.role, "content": self.content}


@dataclass
class Response:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLM:
    """通用 LLM 客户端，兼容 DeepSeek / Ollama / 任意 OpenAI 兼容接口"""

    def __init__(self, api_key: str, base_url: str, model: str,
                 temperature: float = 0.7, max_tokens: int = 8192):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, messages: list[Message], temperature: float | None = None,
                 max_tokens: int | None = None) -> Response:
        kwargs = dict(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature if temperature is not None else self.temperature,
        )
        mt = max_tokens or self.max_tokens
        if mt > 0:
            kwargs["max_tokens"] = mt
        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        return Response(
            content=content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


def parse_json(raw: str, schema: type[T] | None = None) -> dict | T:
    """从 LLM 输出中安全提取 JSON"""
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE).strip()
    # 修复截断
    data = json.loads(_repair(stripped))
    if schema:
        return schema.model_validate(data)
    return data


def parse_json_list(raw: str) -> list[dict]:
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE).strip()
    data = json.loads(_repair(stripped))
    return data if isinstance(data, list) else [data]


def _repair(text: str) -> str:
    """修复被截断的 JSON"""
    stack = []
    in_str, escape = False, False
    for ch in text:
        if escape: escape = False; continue
        if ch == '\\' and in_str: escape = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch in '{[': stack.append('}' if ch == '{' else ']')
        elif ch in '}]' and stack and stack[-1] == ch: stack.pop()
    text = re.sub(r',\s*$', '', text.strip())
    while stack:
        text += stack.pop()
    return text


def with_retry(fn: Callable[[], T], max_attempts: int = 3, delay: float = 2.0) -> T:
    last_err = None
    for i in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < max_attempts - 1:
                time.sleep(delay * (i + 1))
    raise last_err
