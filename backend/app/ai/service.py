"""User-isolated encrypted settings, prompts and usage accounting."""
from __future__ import annotations
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends
from pydantic import Field, SecretStr
from .. import core
from .common import StrictModel, connection, dumps, fail, rows
from .providers import ProviderConfig, ProviderError, Usage, build_provider, validate_url, DEFAULT_URLS

router = APIRouter()
MODES = {
 'general': '你是准确、简洁的通用助手。区分事实和推测，不知道就说明。',
 'tutor': '你是大学学习导师。使用苏格拉底式提问定位误区，再解释概念和例子，最后提供一个检验理解的小练习。不要只给答案。',
 'code': '你是编程导师。先说明算法和复杂度，再提供可运行代码、边界条件及测试用例。不声称已执行代码，除非确有工具结果。',
 'paper': '你是学术写作导师。帮助梳理论点、证据、方法和文章结构。区分引用与自己的建议，绝不编造文献、DOI、实验或数据。',
 'english': '你是英语老师。先给自然英文表达或纠错版本，再用中文解释语法和用词差异，并给一个短练习。',
 'math': '你是数学导师。明确条件与定义，给出可检查的解题步骤和结论，检查边界条件，并指出相关知识点；信息不足先说明。',
}
Mode = Literal['general', 'tutor', 'code', 'paper', 'english', 'math']


class SettingsIn(StrictModel):
    provider: Literal['openai', 'deepseek', 'qwen', 'openai-compatible', 'gemini']
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(default='', max_length=500)
    api_key: SecretStr | None = None
    embedding_model: str = Field(default='', max_length=200)
    embedding_base_url: str = Field(default='', max_length=500)
    embedding_mode: Literal['keyword', 'local', 'api'] = 'local'
    input_budget: int = Field(default=24000, ge=4000, le=64000)


def cipher() -> Fernet:
    key = os.getenv('AI_SETTINGS_KEY')
    if key:
        try:
            return Fernet(key.encode())
        except ValueError:
            fail(503, 'SETTINGS_KEY_INVALID', '服务器加密配置无效，请联系管理员')
    path = Path(core.DATA_DIR) / '.ai-settings.key'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # O_EXCL prevents concurrent workers from replacing the encryption key.
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(Fernet.generate_key())
    try:
        return Fernet(path.read_bytes())
    except (OSError, ValueError):
        fail(503, 'SETTINGS_KEY_UNAVAILABLE', '服务器加密密钥不可用，请联系管理员')


def get_config(user_id: str) -> ProviderConfig:
    with connection() as conn:
        found = conn.execute('SELECT config_json,secret_encrypted FROM ai_settings WHERE user_id=?', (user_id,)).fetchone()
    private = os.getenv('AI_ALLOW_PRIVATE_ENDPOINTS', '').lower() in {'1', 'true'}
    if found:
        try:
            config = json.loads(found['config_json'])
            key = cipher().decrypt(found['secret_encrypted'].encode()).decode()
        except (InvalidToken, ValueError, TypeError):
            fail(503, 'SETTINGS_DECRYPT_FAILED', '个人 AI 配置无法解密，请重新保存')
        return ProviderConfig(**config, api_key=key, allow_private=private)
    # Never combine one user's configuration with another user's or admin key.
    return ProviderConfig(provider=os.getenv('MODEL_PROVIDER', '').lower(),
        model=os.getenv('MODEL_NAME', ''), api_key=os.getenv('API_KEY', ''),
        base_url=os.getenv('BASE_URL', ''), embedding_mode=os.getenv('EMBEDDING_MODE', 'local'),
        embedding_model=os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5'),
        embedding_base_url=os.getenv('EMBEDDING_BASE_URL', ''), allow_private=private)


def provider_for(user_id):
    try:
        return build_provider(get_config(user_id))
    except ProviderError as exc:
        fail(exc.status, exc.code, exc.message)


def public_config(user_id):
    config = get_config(user_id)
    with connection() as conn:
        personal = bool(conn.execute('SELECT 1 FROM ai_settings WHERE user_id=?', (user_id,)).fetchone())
    return {'provider': config.provider, 'model': config.model, 'base_url': config.base_url,
        'configured': bool(config.provider and config.model and config.api_key),
        'has_api_key': bool(config.api_key), 'source': 'personal' if personal else 'server_default',
        'embedding_mode': config.embedding_mode, 'embedding_model': config.embedding_model,
        'embedding_base_url': config.embedding_base_url, 'input_budget': config.input_budget}


@router.get('/settings/ai')
@router.get('/ai/settings', include_in_schema=False)
def settings_get(user=Depends(core.current_user)):
    return public_config(user['id'])


@router.put('/settings/ai')
@router.post('/settings/ai', include_in_schema=False)
@router.put('/ai/settings', include_in_schema=False)
async def settings_put(payload: SettingsIn, user=Depends(core.current_user)):
    value = payload.model_dump(exclude={'api_key'})
    value['base_url'] = value['base_url'] or DEFAULT_URLS.get(payload.provider, '')
    private = os.getenv('AI_ALLOW_PRIVATE_ENDPOINTS', '').lower() in {'1', 'true'}
    try:
        await validate_url(value['base_url'], private)
        if payload.embedding_base_url:
            await validate_url(payload.embedding_base_url, private)
    except ProviderError as exc:
        fail(exc.status, exc.code, exc.message)
    with connection() as conn:
        old = conn.execute('SELECT secret_encrypted,config_json FROM ai_settings WHERE user_id=?', (user['id'],)).fetchone()
        if payload.api_key is not None:
            secret = payload.api_key.get_secret_value()
            if not 1 <= len(secret) <= 4096 or any(ord(c) < 32 for c in secret):
                fail(422, 'INVALID_API_KEY', 'API Key 长度或格式不正确')
            encrypted = cipher().encrypt(secret.encode()).decode()
        elif old:
            previous = json.loads(old['config_json'])
            if (previous['provider'], previous['base_url']) != (value['provider'], value['base_url']):
                fail(422, 'API_KEY_REQUIRED', '更改服务商或地址时必须重新提供 API Key')
            encrypted = old['secret_encrypted']
        else:
            fail(422, 'API_KEY_REQUIRED', '首次保存个人配置必须提供 API Key')
        if old:
            conn.execute('UPDATE ai_settings SET config_json=?,secret_encrypted=?,updated_at=? WHERE user_id=?',
                         (dumps(value), encrypted, core.now_iso(), user['id']))
        else:
            conn.execute('INSERT INTO ai_settings(user_id,config_json,secret_encrypted,updated_at) VALUES(?,?,?,?)',
                         (user['id'], dumps(value), encrypted, core.now_iso()))
    return public_config(user['id'])


@router.delete('/settings/ai')
def settings_delete(user=Depends(core.current_user)):
    with connection() as conn:
        conn.execute('DELETE FROM ai_settings WHERE user_id=?', (user['id'],))
    return public_config(user['id'])


@router.get('/ai/modes')
def list_modes(user=Depends(core.current_user)):
    return [{'id': name, 'description': prompt} for name, prompt in MODES.items()]


@router.get('/ai/usage')
def list_usage(user=Depends(core.current_user)):
    with connection() as conn:
        return rows(conn.execute('SELECT * FROM ai_usage WHERE user_id=? ORDER BY created_at DESC LIMIT 200', (user['id'],)).fetchall())


def record_usage(user_id, purpose, provider, usage: Usage | None, status):
    usage = usage or Usage()
    with connection() as conn:
        conn.execute('INSERT INTO ai_usage(id,user_id,purpose,provider,model,prompt_tokens,completion_tokens,total_tokens,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (core.uid(), user_id, purpose, provider.config.provider, provider.config.model,
             usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, status, core.now_iso()))


def bounded_messages(messages, budget=24000):
    """UTF-8 bytes are a conservative input bound, not a token usage estimate.

    Keep the system message and whole newest turns; never truncate the latest
    user request or pair an old assistant answer with a missing user request.
    """
    if not messages:
        fail(422, 'EMPTY_PROMPT', '提示词不能为空')
    systems = [m for m in messages if m['role'] == 'system']
    history = [m for m in messages if m['role'] != 'system']
    size = sum(len(m['content'].encode()) + 32 for m in systems)
    if size > budget:
        fail(413, 'INPUT_BUDGET_EXCEEDED', '输入超出模型预算，请缩短内容')
    chosen = []
    for message in reversed(history):
        length = len(message['content'].encode()) + 32
        if size + length > budget:
            if not chosen:
                fail(413, 'INPUT_BUDGET_EXCEEDED', '输入超出模型预算，请缩短内容或分段处理')
            break
        chosen.append({'role': message['role'], 'content': message['content']})
        size += length
    chosen.reverse()
    while chosen and chosen[0]['role'] == 'assistant':
        chosen.pop(0)
    return systems + chosen


async def complete_for(user_id, purpose, messages, *, json_mode=False, max_tokens=4096):
    provider = provider_for(user_id)
    prompts = bounded_messages(messages, provider.config.input_budget)
    usage, status = None, 'failed'
    try:
        result = await provider.complete(prompts, json_mode=json_mode, max_tokens=max_tokens)
        usage, status = result.usage, 'completed'
        return result.text
    except ProviderError as exc:
        fail(exc.status, exc.code, exc.message)
    except Exception:
        fail(502, 'AI_PROVIDER_ERROR', '模型服务暂不可用，请稍后重试')
    finally:
        record_usage(user_id, purpose, provider, usage, status)


def parse_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        fail(502, 'INVALID_AI_JSON', '模型未返回严格 JSON；未保存不完整结果')
