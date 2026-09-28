"""Async provider registry: actual HTTP only; test fakes never ship here."""
from __future__ import annotations
import asyncio
import ipaddress
import json
import os
import socket
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol
from urllib.parse import quote, urlsplit
import httpx


class ProviderError(Exception):
    """Public messages are constants, never upstream response text/URLs."""
    def __init__(self, code='AI_PROVIDER_ERROR', message='模型服务暂不可用，请检查配置或稍后重试', status=502):
        self.code, self.message, self.status = code, message, status
        super().__init__(code)


@dataclass
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    @classmethod
    def parse(cls, data):
        data = data if isinstance(data, dict) else {}
        def integer(key):
            value = data.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        return cls(integer('prompt_tokens'), integer('completion_tokens'), integer('total_tokens'))


@dataclass
class Completion:
    text: str
    usage: Usage = field(default_factory=Usage)


@dataclass
class Delta:
    text: str = ''
    usage: Usage | None = None


@dataclass
class ProviderConfig:
    provider: str
    model: str
    api_key: str = field(repr=False)
    base_url: str = ''
    embedding_model: str = ''
    embedding_base_url: str = ''
    embedding_mode: str = 'local'
    input_budget: int = 24000  # Conservative UTF-8 byte budget, not fabricated tokens.
    allow_private: bool = False  # Server policy only; never user-controlled.


class AIProvider(Protocol):
    config: ProviderConfig
    async def complete(self, messages: list[dict], *, json_mode=False, max_tokens=4096) -> Completion: ...
    def stream(self, messages: list[dict], *, max_tokens=4096) -> AsyncIterator[Delta]: ...


DEFAULT_URLS = {'openai': 'https://api.openai.com/v1', 'deepseek': 'https://api.deepseek.com/v1',
                'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                'gemini': 'https://generativelanguage.googleapis.com/v1beta'}
TIMEOUT = httpx.Timeout(connect=10, read=60, write=20, pool=10)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


async def validate_url(url: str, allow_private=False):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError
        if not allow_private:
            if parsed.scheme != 'https':
                raise ValueError
            # Reject loopback, private, metadata and DNS aliases thereof.
            infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            if not infos or any(not ipaddress.ip_address(info[4][0]).is_global for info in infos):
                raise ValueError
    except (ValueError, OSError):
        raise ProviderError('INVALID_PROVIDER_URL', '模型地址必须是有效的公共 HTTPS 地址（私网仅管理员可显式启用）', 422) from None


def endpoint(base, suffix):
    base = base.rstrip('/')
    for known in ('/chat/completions', '/embeddings'):
        if base.endswith(known):
            base = base[:-len(known)]
    return base + suffix


async def read_json(response):
    if response.status_code >= 400:
        if response.status_code == 429:
            raise ProviderError('AI_RATE_LIMITED', '模型服务请求频率受限，请稍后重试', 429)
        raise ProviderError()
    data = bytearray()
    async for chunk in response.aiter_bytes():
        data.extend(chunk)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ProviderError('AI_RESPONSE_TOO_LARGE', '模型响应超过安全限制')
    try:
        return json.loads(data)
    except (ValueError, TypeError):
        raise ProviderError('INVALID_AI_RESPONSE', '模型返回的结构无效') from None


class OpenAICompatible:
    def __init__(self, config):
        self.config = config

    async def _url(self, suffix):
        base = self.config.base_url or DEFAULT_URLS.get(self.config.provider, '')
        await validate_url(base, self.config.allow_private)
        return endpoint(base, suffix)

    def headers(self):
        return {'Authorization': 'Bearer ' + self.config.api_key, 'Content-Type': 'application/json'}

    async def complete(self, messages, *, json_mode=False, max_tokens=4096):
        url = await self._url('/chat/completions')
        payload = {'model': self.config.model, 'messages': messages, 'stream': False,
                   'temperature': 0.3, 'max_tokens': max_tokens}
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
                async with client.stream('POST', url, headers=self.headers(), json=payload) as response:
                    data = await read_json(response)
            text = data['choices'][0]['message']['content']
            if not isinstance(text, str) or not text.strip():
                raise ValueError
            return Completion(text, Usage.parse(data.get('usage')))
        except httpx.TimeoutException:
            raise ProviderError('AI_TIMEOUT', '模型服务超时，请重试', 504) from None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            raise ProviderError() from None

    async def stream(self, messages, *, max_tokens=4096):
        url = await self._url('/chat/completions')
        payload = {'model': self.config.model, 'messages': messages, 'stream': True,
                   'stream_options': {'include_usage': True}, 'max_tokens': max_tokens}
        received, finished = 0, False
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
                async with client.stream('POST', url, headers=self.headers(), json=payload) as response:
                    if response.status_code >= 400:
                        raise ProviderError(status=429 if response.status_code == 429 else 502)
                    async for line in response.aiter_lines():
                        received += len(line.encode('utf-8'))
                        if received > MAX_RESPONSE_BYTES:
                            raise ProviderError('AI_RESPONSE_TOO_LARGE', '模型响应超过安全限制')
                        if not line.startswith('data:'):
                            continue
                        raw = line[5:].strip()
                        if raw == '[DONE]':
                            finished = True
                            break
                        item = json.loads(raw)
                        if 'error' in item:
                            raise ProviderError()
                        if item.get('usage'):
                            yield Delta(usage=Usage.parse(item['usage']))
                        for choice in item.get('choices', []):
                            if choice.get('finish_reason'):
                                if choice['finish_reason'] in {'length', 'content_filter'}:
                                    raise ProviderError('AI_INCOMPLETE', '模型输出未完整结束，可重新生成')
                                finished = True
                            text = choice.get('delta', {}).get('content')
                            if isinstance(text, str) and text:
                                yield Delta(text)
            if not finished:
                raise ProviderError('AI_STREAM_INTERRUPTED', '模型流意外中断，可重新生成')
        except httpx.TimeoutException:
            raise ProviderError('AI_TIMEOUT', '模型服务超时，请重试', 504) from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderError() from None


class GeminiNative:
    def __init__(self, config):
        self.config = config

    async def _request(self, messages, stream, json_mode=False, max_tokens=4096):
        base = self.config.base_url or DEFAULT_URLS['gemini']
        await validate_url(base, self.config.allow_private)
        action = 'streamGenerateContent?alt=sse' if stream else 'generateContent'
        url = base.rstrip('/') + '/models/' + quote(self.config.model, safe='') + ':' + action
        systems = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
        payload = {'contents': [{'role': 'model' if m['role'] == 'assistant' else 'user',
                    'parts': [{'text': m['content']}]} for m in messages if m['role'] != 'system'],
                   'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': 0.3}}
        if systems:
            payload['systemInstruction'] = {'parts': [{'text': systems}]}
        if json_mode:
            payload['generationConfig']['responseMimeType'] = 'application/json'
        return url, payload

    @staticmethod
    def parse(data):
        candidates = data.get('candidates', [])
        if data.get('error') or any(c.get('finishReason') in {'SAFETY', 'MAX_TOKENS', 'RECITATION'} for c in candidates):
            raise ProviderError('AI_INCOMPLETE', '模型输出未完整结束，可重新生成')
        text = ''.join(p.get('text', '') for c in candidates[:1] for p in c.get('content', {}).get('parts', []))
        u = data.get('usageMetadata', {})
        return text, Usage.parse({'prompt_tokens': u.get('promptTokenCount'), 'completion_tokens': u.get('candidatesTokenCount'), 'total_tokens': u.get('totalTokenCount')})

    async def complete(self, messages, *, json_mode=False, max_tokens=4096):
        url, payload = await self._request(messages, False, json_mode, max_tokens)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
                async with client.stream('POST', url, headers={'x-goog-api-key': self.config.api_key}, json=payload) as response:
                    data = await read_json(response)
            text, usage = self.parse(data)
            if not text.strip():
                raise ProviderError()
            return Completion(text, usage)
        except httpx.TimeoutException:
            raise ProviderError('AI_TIMEOUT', '模型服务超时，请重试', 504) from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderError() from None

    async def stream(self, messages, *, max_tokens=4096):
        url, payload = await self._request(messages, True, max_tokens=max_tokens)
        finished, size = False, 0
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
                async with client.stream('POST', url, headers={'x-goog-api-key': self.config.api_key}, json=payload) as response:
                    if response.status_code >= 400:
                        raise ProviderError()
                    async for line in response.aiter_lines():
                        size += len(line.encode('utf-8'))
                        if size > MAX_RESPONSE_BYTES:
                            raise ProviderError()
                        if line.startswith('data:'):
                            data = json.loads(line[5:])
                            text, usage = self.parse(data)
                            finished |= any(c.get('finishReason') == 'STOP' for c in data.get('candidates', []))
                            yield Delta(text, usage)
            if not finished:
                raise ProviderError('AI_STREAM_INTERRUPTED', '模型流意外中断，可重新生成')
        except httpx.TimeoutException:
            raise ProviderError('AI_TIMEOUT', '模型服务超时，请重试', 504) from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderError() from None


REGISTRY: dict[str, type] = {'openai': OpenAICompatible, 'deepseek': OpenAICompatible,
    'qwen': OpenAICompatible, 'openai-compatible': OpenAICompatible, 'gemini': GeminiNative}


def build_provider(config: ProviderConfig) -> AIProvider:
    if config.provider not in REGISTRY or not config.model or not config.api_key:
        raise ProviderError('AI_NOT_CONFIGURED', 'AI 尚未配置，请在个人 AI 设置中配置模型', 503)
    return REGISTRY[config.provider](config)
