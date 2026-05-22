from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

_CACHE_FILE = Path.home() / ".b3analytics" / "macro_cache.json"
_CACHE_TTL  = 3600  # 1 hora
logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def _cache_load() -> dict | None:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            if datetime.now().timestamp() - data.get("_ts", 0) < _CACHE_TTL:
                return {k: v for k, v in data.items() if k != "_ts"}
    except Exception:
        logger.warning("Falha ao carregar cache macro local: arquivo=%s", _CACHE_FILE)
        pass
    return None


def _cache_save(data: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({**data, "_ts": datetime.now().timestamp()}))
    except Exception:
        logger.warning("Falha ao salvar cache macro local: arquivo=%s", _CACHE_FILE)
        pass


def _get_url(url: str, timeout: int = 8) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        logger.warning("Falha ao consultar URL macro: url=%s", url)
        return None


def _bcb(serie: int) -> float | None:
    raw = _get_url(
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json"
    )
    if raw:
        try:
            data = json.loads(raw)
            return float(data[-1]["valor"].replace(",", "."))
        except Exception:
            logger.warning("Falha ao parsear série BCB: serie=%s", serie)
            pass
    return None


def _yf_last(ticker: str) -> float | None:
    try:
        df = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
        if df is not None and len(df) > 0:
            return float(df["Close"].iloc[-1])
    except Exception:
        logger.warning("Falha ao buscar cotação macro no yfinance: ticker=%s", ticker)
        pass
    return None


def get_macro_context() -> dict:
    cached = _cache_load()
    if cached:
        return cached

    selic = _bcb(432)    # SELIC meta
    ipca  = _bcb(13522)  # IPCA acumulado 12m

    usd_brl = _yf_last("USDBRL=X")
    sp500   = _yf_last("^GSPC")
    vix     = _yf_last("^VIX")
    dxy     = _yf_last("DX-Y.NYB")
    brent   = _yf_last("BZ=F")
    ibov    = _yf_last("^BVSP")

    fed_funds = None
    raw = _get_url("https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS")
    if raw:
        try:
            lines = raw.decode().strip().split("\n")
            fed_funds = float(lines[-1].split(",")[1])
        except Exception:
            logger.warning("Falha ao parsear Fed Funds: fonte=FRED")
            pass

    BRT = timezone(timedelta(hours=-3))
    macro = {
        "selic_pct":    round(selic, 2)   if selic   is not None else None,
        "ipca_12m_pct": round(ipca, 2)    if ipca    is not None else None,
        "usd_brl":      round(usd_brl, 4) if usd_brl is not None else None,
        "juros_eua":    {"fed_funds": round(fed_funds, 2) if fed_funds is not None else None},
        "commodities":  {
            "petroleo_brent": round(brent, 2) if brent is not None else None,
            "minerio_ferro":  None,
            "sp500":          round(sp500, 2) if sp500 is not None else None,
            "vix":            round(vix, 2)   if vix   is not None else None,
            "dxy":            round(dxy, 2)   if dxy   is not None else None,
            "ibov":           round(ibov, 2)  if ibov  is not None else None,
        },
        "data_coleta": datetime.now(BRT).strftime("%Y-%m-%d %H:%M BRT"),
    }

    _cache_save(macro)
    return macro
