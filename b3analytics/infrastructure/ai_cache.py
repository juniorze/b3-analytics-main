from __future__ import annotations

import json
import logging
import time
from pathlib import Path

CACHE_DIR   = Path.home() / ".b3analytics" / "ai_cache"
DEFAULT_TTL = 3 * 60 * 60  # 3 horas
logger = logging.getLogger(__name__)


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace("\\", "_").replace("^", "").replace(".", "_")
    return CACHE_DIR / f"{safe}.json"


def get_cached(ticker: str, ttl: int = DEFAULT_TTL) -> dict | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("cached_at", 0) > ttl:
            return None
        return data
    except Exception:
        logger.warning("Falha ao ler cache de IA: ticker=%s arquivo=%s", ticker, path)
        return None


def save_cache(ticker: str, resultado: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(ticker)
    path.write_text(json.dumps({
        **resultado,
        "cached_at": time.time(),
        "ticker":    ticker,
    }, ensure_ascii=False, indent=2))


def invalidate(ticker: str) -> None:
    path = _cache_path(ticker)
    if path.exists():
        path.unlink()


def invalidate_all() -> int:
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


def list_cached(ttl: int = DEFAULT_TTL) -> list[dict]:
    if not CACHE_DIR.exists():
        return []
    result = []
    for f in sorted(CACHE_DIR.glob("*.json")):
        try:
            data      = json.loads(f.read_text())
            cached_at = data.get("cached_at", 0)
            age       = time.time() - cached_at
            result.append({
                "ticker":      data.get("ticker", f.stem),
                "cached_at":   cached_at,
                "age_minutes": int(age / 60),
                "expired":     age > ttl,
                "macro_score": data.get("macro_score"),
                "macro_label": data.get("macro_label"),
                "model":       data.get("_model"),
                "preset":      data.get("_preset"),
            })
        except Exception:
            logger.warning("Falha ao listar item de cache de IA: arquivo=%s", f)
            pass
    return result


def cache_stats(ttl: int = DEFAULT_TTL) -> dict:
    items   = list_cached(ttl)
    valid   = [i for i in items if not i["expired"]]
    expired = [i for i in items if i["expired"]]
    return {
        "total":         len(items),
        "valid":         len(valid),
        "expired":       len(expired),
        "tickers_valid": [i["ticker"] for i in valid],
    }
