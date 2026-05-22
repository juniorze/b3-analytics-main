from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import streamlit as st

CONFIG_DIR  = Path.home() / ".b3analytics"
CONFIG_FILE = CONFIG_DIR / "config.json"
logger = logging.getLogger(__name__)

AI_PRESETS = {
    "econômico": {
        "label":       "Econômico",
        "description": "1 busca · resposta curta · menor custo",
        "max_uses":    1,
        "max_tokens":  800,
        "icon":        "💚",
    },
    "padrão": {
        "label":       "Padrão",
        "description": "3 buscas · resposta completa · custo moderado",
        "max_uses":    3,
        "max_tokens":  3000,
        "icon":        "🔵",
    },
    "completo": {
        "label":       "Completo",
        "description": "5 buscas · análise profunda · maior custo",
        "max_uses":    5,
        "max_tokens":  5000,
        "icon":        "🟣",
    },
}
DEFAULT_PRESET = "padrão"

AI_PROVIDERS = {
    "anthropic_api": {
        "label":        "Anthropic API",
        "requires_key": True,
        "storage_key":  "anthropic",
        "env_var":      "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-5",
    },
    "openai_api": {
        "label":        "OpenAI API",
        "requires_key": True,
        "storage_key":  "openai",
        "env_var":      "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "google_gemini": {
        "label":        "Google Gemini",
        "requires_key": True,
        "storage_key":  "google",
        "env_var":      "GOOGLE_API_KEY",
        "default_model": "gemini-1.5-flash",
    },
    "claude_code": {
        "label":        "Motor IA Local",
        "requires_key": False,
        "storage_key":  "claude_code",
    },
}

TTL_OPTIONS = {
    "30 minutos": 30 * 60,
    "1 hora":     60 * 60,
    "3 horas":    3 * 60 * 60,
    "6 horas":    6 * 60 * 60,
    "12 horas":   12 * 60 * 60,
    "24 horas":   24 * 60 * 60,
}
DEFAULT_TTL_LABEL = "3 horas"

_FALLBACK_MODELS = {
    "claude-opus-4-5":           "Opus 4.5",
    "claude-sonnet-4-5":         "Sonnet 4.5",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
}
_OPENAI_MODELS = {
    "gpt-5.4":      "GPT-5.4",
    "gpt-5.4-mini": "GPT-5.4 mini",
    "gpt-5-nano":   "GPT-5 nano",
    "gpt-5-mini":   "GPT-5 mini",
}
_GEMINI_MODELS = {
    "gemini-3.5-flash":      "Gemini 3.5 Flash",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite",
}
_DEFAULT_MODEL = "claude-sonnet-4-5"


def provider_storage_key(provider: str) -> str:
    if provider in AI_PROVIDERS:
        return AI_PROVIDERS[provider].get("storage_key", provider)
    return provider


def provider_env_var(provider: str) -> str | None:
    if provider in AI_PROVIDERS:
        return AI_PROVIDERS[provider].get("env_var")
    return None


def _load() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except Exception as e:
        logger.warning("Falha ao carregar configuração local de IA: arquivo=%s erro=%s", CONFIG_FILE, e)
    return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR)
    os.chmod(tmp, 0o600)
    os.write(fd, json.dumps(data, indent=2).encode())
    os.close(fd)
    try:
        os.replace(tmp, CONFIG_FILE)
    except PermissionError:
        if os.name != "nt":
            raise
        logger.warning("Falha de permissão ao substituir config local; tentando fallback Windows: arquivo=%s", CONFIG_FILE)
        if CONFIG_FILE.exists():
            os.chmod(CONFIG_FILE, 0o600)
            CONFIG_FILE.unlink()
        os.replace(tmp, CONFIG_FILE)


def get_api_key(provider: str = "anthropic") -> str | None:
    storage_key = provider_storage_key(provider)
    saved = _load().get("providers", {}).get(storage_key, {}).get("api_key")
    if saved:
        return saved
    env_var = provider_env_var(provider)
    return os.environ.get(env_var) if env_var else None


def save_api_key(api_key: str, provider: str = "anthropic") -> None:
    provider = provider_storage_key(provider)
    data = _load()
    data.setdefault("providers", {})
    data["providers"].setdefault(provider, {})
    data["providers"][provider]["api_key"] = api_key
    _save(data)


def delete_api_key(provider: str = "anthropic") -> None:
    provider = provider_storage_key(provider)
    data = _load()
    data.get("providers", {}).pop(provider, None)
    _save(data)


def is_configured(provider: str = "anthropic") -> bool:
    key = get_api_key(provider)
    return bool(key and len(key) > 10)


def get_config_path() -> str:
    return str(CONFIG_FILE)


def get_model(provider: str = "anthropic") -> str:
    storage_key = provider_storage_key(provider)
    model = _load().get("providers", {}).get(storage_key, {}).get("model")
    if provider in AI_PROVIDERS:
        return model or AI_PROVIDERS[provider].get("default_model", _DEFAULT_MODEL)
    return model or _DEFAULT_MODEL


def save_model(model_id: str, provider: str = "anthropic") -> None:
    provider = provider_storage_key(provider)
    data = _load()
    data.setdefault("providers", {})
    data["providers"].setdefault(provider, {})
    data["providers"][provider]["model"] = model_id
    _save(data)


def fetch_available_models(api_key: str, provider: str = "anthropic_api") -> list[dict]:
    if provider != "anthropic_api":
        return []
    key_id = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return _fetch_models_cached(key_id, api_key)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_models_cached(key_id: str, _api_key: str) -> list[dict]:
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/models",
            headers={
                "X-API-Key":         _api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        models = data.get("data", [])
        models.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return models
    except Exception:
        logger.warning("Falha ao buscar modelos Anthropic: key_id=%s", key_id)
        return []


def get_model_options(models: list[dict], provider: str = "anthropic_api") -> dict[str, str]:
    if provider == "openai_api":
        return dict(_OPENAI_MODELS)
    if provider == "google_gemini":
        return dict(_GEMINI_MODELS)
    if models:
        return {m["id"]: m.get("display_name", m["id"]) for m in models}
    return dict(_FALLBACK_MODELS)


def get_preset(provider: str = "anthropic") -> str:
    provider = provider_storage_key(provider)
    preset = _load().get("providers", {}).get(provider, {}).get("preset", DEFAULT_PRESET)
    return preset if preset in AI_PRESETS else DEFAULT_PRESET


def get_ttl_label() -> str:
    label = _load().get("ai_cache", {}).get("ttl_label", DEFAULT_TTL_LABEL)
    return label if label in TTL_OPTIONS else DEFAULT_TTL_LABEL


def get_ttl() -> int:
    return TTL_OPTIONS.get(get_ttl_label(), TTL_OPTIONS[DEFAULT_TTL_LABEL])


def save_ttl(label: str) -> None:
    data = _load()
    data.setdefault("ai_cache", {})
    data["ai_cache"]["ttl_label"] = label
    _save(data)


def save_preset(preset: str, provider: str = "anthropic") -> None:
    provider = provider_storage_key(provider)
    data = _load()
    data.setdefault("providers", {}).setdefault(provider, {})
    data["providers"][provider]["preset"] = preset
    _save(data)


def is_local_agent_available() -> bool:
    import shutil
    return shutil.which("claude") is not None


def get_active_provider() -> str:
    provider = _load().get("active_provider", "anthropic_api")
    return provider if provider in AI_PROVIDERS else "anthropic_api"


def save_active_provider(provider: str) -> None:
    data = _load()
    data["active_provider"] = provider
    _save(data)


def get_local_agent_info() -> dict:
    import re
    import shutil
    import subprocess
    info: dict = {"available": False}
    if not shutil.which("claude"):
        return info
    info["available"] = True
    try:
        r = subprocess.run(["claude", "--version"],
                           capture_output=True, text=True, timeout=5)
        raw = (r.stdout.strip() or r.stderr.strip())
        m   = re.search(r"(\d+\.\d+[\.\d]*)", raw)
        info["version"] = m.group(1) if m else raw
    except Exception:
        logger.warning("Falha ao consultar versão do motor IA local")
        pass
    for cmd in [["claude", "config", "list"], ["claude", "config", "get", "model"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                info["config_raw"] = r.stdout.strip()
                m = re.search(r"model[:\s]+([a-z0-9\-\.]+)", r.stdout, re.I)
                if m:
                    info["model"] = m.group(1)
                break
        except Exception:
            logger.warning("Falha ao consultar configuração do motor IA local: comando=%s", " ".join(cmd))
            pass
    return info


def get_sources_enabled() -> bool:
    return bool(_load().get("sources_enabled", False))


def get_all_sources() -> list:
    return _load().get("sources", [])


def save_sources_enabled(enabled: bool) -> None:
    data = _load()
    data["sources_enabled"] = bool(enabled)
    _save(data)


def save_sources(sources: list) -> None:
    data = _load()
    data["sources"] = [s for s in sources if s]
    _save(data)


def test_api_key(api_key: str, model: str, provider: str = "anthropic_api") -> tuple[bool, str]:
    try:
        if provider == "openai_api":
            payload = json.dumps({
                "model": model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "ping"}],
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15):
                return True, f"Chave OpenAI válida · modelo: {model}"

        if provider == "google_gemini":
            payload = json.dumps({
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 10},
            }).encode()
            url_model = urllib.parse.quote(model, safe="")
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{url_model}:generateContent?key={api_key}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15):
                return True, f"Chave Google Gemini válida · modelo: {model}"

        payload = json.dumps({
            "model":      model,
            "max_tokens": 10,
            "messages":   [{"role": "user", "content": "ping"}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "X-API-Key":         api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15):
            return True, f"Chave válida · modelo: {model}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Chave inválida ou sem permissão (401)"
        elif e.code == 429:
            return True, "Chave válida, limite de taxa atingido (429)"
        elif e.code == 529:
            return True, "Chave válida, API sobrecarregada (529)"
        else:
            return False, f"Erro HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, f"Erro de conexão: {e}"
