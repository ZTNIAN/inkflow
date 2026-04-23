"""LLM 抽象层 — 支持普通调用 + 流式输出（v2: 鲁棒 JSON 解析）"""
from __future__ import annotations
import json, re, time
from dataclasses import dataclass
from typing import Callable, Generator, TypeVar
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

    def stream(self, messages: list[Message], temperature: float | None = None,
               max_tokens: int | None = None) -> Generator[str, None, None]:
        """流式输出，逐 token yield"""
        kwargs = dict(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature if temperature is not None else self.temperature,
            stream=True,
        )
        mt = max_tokens or self.max_tokens
        if mt > 0:
            kwargs["max_tokens"] = mt
        stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ═══════════════════════════════════════════════════════════════════════════════
# JSON 解析（v2 — 多层修复 + 重试）
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_json_text(raw: str) -> str:
    """从 LLM 输出中提取 JSON 文本，去掉 markdown 包裹和前后废话"""
    text = raw.strip()
    # 去掉 markdown 代码块
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE).strip()

    # 找到第一个 { 或 [ 到最后一个 } 或 ]
    first_obj = text.find('{')
    first_arr = text.find('[')
    if first_obj == -1 and first_arr == -1:
        return text  # 没找到，原样返回

    if first_obj == -1:
        start = first_arr
    elif first_arr == -1:
        start = first_obj
    else:
        start = min(first_obj, first_arr)

    last_obj = text.rfind('}')
    last_arr = text.rfind(']')
    end = max(last_obj, last_arr)

    if end > start:
        return text[start:end + 1]
    return text


def _fix_smart_quotes(text: str) -> str:
    """修复 JSON 字符串值内的弯引号，避免破坏 JSON 结构"""
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]

        if not in_string:
            if ch == '"':
                in_string = True
                result.append(ch)
            else:
                result.append(ch)
        else:
            if ch == '\\':
                result.append(ch)
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif ch == '"':
                in_string = False
                result.append(ch)
            elif ch in '\u201c\u201d':
                # 中文弯引号 → 转义为直引号
                result.append('\\"')
            elif ch in '\u2018\u2019':
                result.append("\\'")
            elif ch == '\u300a' or ch == '\u300b':
                # 书名号《》 → 转义
                result.append('\\' + ch)
            else:
                result.append(ch)
        i += 1
    return ''.join(result)


def _fix_trailing_commas(text: str) -> str:
    """去掉 JSON 中的尾逗号"""
    # ,} → }  和  ,] → ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _fix_single_quotes(text: str) -> str:
    """尝试将单引号 JSON 转为双引号（简单场景）"""
    if '"' in text:
        return text  # 已经有双引号了，不动
    if "'" not in text:
        return text
    # 简单替换：外层单引号变双引号
    return text.replace("'", '"')


def _fix_object_as_array(text: str) -> str:
    """修复 LLM 把数组元素输出成对象 key-value 的问题
    
    例如 DeepSeek 有时输出:
      "title_candidates": {
        "标题方案1（爆款型）": "实际标题内容",
        "标题方案2（共鸣型）": "实际标题内容"
      }
    而期望的是:
      "title_candidates": ["实际标题1", "实际标题2"]
    
    检测到这种模式后，提取 value 部分组成数组。
    """
    # 匹配 "key": { "中文key": "value", ... } 模式
    # 找到 "some_key": { 开始，到匹配的 } 结束
    pattern = r'"(\w+)":\s*\{([^{}]+)\}'
    
    def fix_obj(match):
        key = match.group(1)
        body = match.group(2)
        # 检查是否所有 key 都包含中文或看起来像描述性文本
        pairs = re.findall(r'"([^"]+)":\s*"([^"]*)"', body)
        if not pairs:
            return match.group(0)
        
        # 检查 key 是否包含中文字符（表明这是被错误格式化的数组）
        chinese_count = sum(1 for k, v in pairs if re.search(r'[\u4e00-\u9fff]', k))
        if chinese_count >= len(pairs) * 0.5:
            # 提取所有 value 组成数组
            values = [v for k, v in pairs]
            return f'"{key}": {json.dumps(values, ensure_ascii=False)}'
        return match.group(0)
    
    return re.sub(pattern, fix_obj, text)


def _repair(text: str) -> str:
    """修复被截断的 JSON（补全未闭合的括号）"""
    stack = []
    in_str, escape = False, False
    for ch in text:
        if escape: escape = False; continue
        if ch == '\\' and in_str: escape = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch in '{[': stack.append('}' if ch == '{' else ']')
        elif ch in '}]' and stack and stack[-1] == ch: stack.pop()
    # 去掉末尾多余逗号
    text = re.sub(r',\s*$', '', text.strip())
    while stack:
        text += stack.pop()
    return text


def parse_json(raw: str, schema: type[T] | None = None) -> dict | T:
    """从 LLM 输出中安全提取 JSON（v2 — 多层修复 + 重试）
    
    修复策略（按顺序尝试）：
    1. 提取 JSON 文本 → 直接解析
    2. 修复弯引号 → 解析
    3. 去尾逗号 → 解析
    4. 修复对象当数组 → 解析
    5. 修复截断 → 解析
    6. 组合修复 → 解析
    """
    text = _extract_json_text(raw)

    strategies = [
        lambda t: json.loads(t),                              # 直接解析
        lambda t: json.loads(_fix_smart_quotes(t)),            # 修弯引号
        lambda t: json.loads(_fix_trailing_commas(t)),         # 去尾逗号
        lambda t: json.loads(_fix_trailing_commas(_fix_smart_quotes(t))),  # 弯引号+尾逗号
        lambda t: json.loads(_fix_object_as_array(t)),         # 对象当数组
        lambda t: json.loads(_fix_object_as_array(_fix_smart_quotes(t))),  # 弯引号+对象当数组
        lambda t: json.loads(_repair(t)),                      # 修截断
        lambda t: json.loads(_repair(_fix_smart_quotes(t))),   # 弯引号+截断
        lambda t: json.loads(_repair(_fix_trailing_commas(_fix_smart_quotes(t)))),  # 全组合
        lambda t: json.loads(_repair(_fix_object_as_array(_fix_trailing_commas(_fix_smart_quotes(t))))),  # 最后手段
    ]

    last_err = None
    for strategy in strategies:
        try:
            data = strategy(text)
            if schema:
                return schema.model_validate(data)
            return data
        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            last_err = e
            continue

    # 所有策略都失败了
    raise last_err


def parse_json_list(raw: str) -> list[dict]:
    """解析 JSON 数组，兼容 LLM 返回对象的情况"""
    text = _extract_json_text(raw)

    strategies = [
        lambda t: json.loads(t),
        lambda t: json.loads(_fix_smart_quotes(t)),
        lambda t: json.loads(_fix_trailing_commas(t)),
        lambda t: json.loads(_fix_trailing_commas(_fix_smart_quotes(t))),
        lambda t: json.loads(_repair(_fix_trailing_commas(_fix_smart_quotes(t)))),
    ]

    for strategy in strategies:
        try:
            data = strategy(text)
            return data if isinstance(data, list) else [data]
        except (json.JSONDecodeError, ValueError):
            continue

    # 最后尝试修复后解析
    fixed = _fix_trailing_commas(_fix_smart_quotes(text))
    data = json.loads(_repair(fixed))
    return data if isinstance(data, list) else [data]


def with_retry(fn: Callable[[], T], max_attempts: int = 3, delay: float = 2.0) -> T:
    """重试包装器，带递增延迟"""
    last_err = None
    for i in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < max_attempts - 1:
                time.sleep(delay * (i + 1))
    raise last_err
