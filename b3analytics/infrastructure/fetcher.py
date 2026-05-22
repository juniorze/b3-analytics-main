from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st
import yfinance as yf

from b3analytics.config.assets import ACOES
from b3analytics.config.settings import CACHE_TTL_SECONDS, FUNDAMENTALS_SANITY, PERIODOS

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def _sanity(field: str, value):
    bounds = FUNDAMENTALS_SANITY
    if field not in bounds or value is None:
        return value
    lo, hi = bounds[field]
    return value if lo <= value <= hi else None


def _mock_history(ticker: str) -> pd.DataFrame:
    base = 20 + (sum(ord(ch) for ch in ticker) % 80)
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=45, freq="B")
    step = pd.Series(range(len(idx)), index=idx, dtype="float64")
    close = base + step * 0.15
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.4,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=idx,
    )


def _fetch_one(ticker: str, periodo: str = "3mo") -> tuple[str, pd.DataFrame | None]:
    if os.environ.get("B3_ANALYTICS_E2E") == "1":
        return ticker, _mock_history(ticker)
    try:
        df = yf.Ticker(ticker).history(period=periodo, auto_adjust=True)
        if df is None or len(df) < 2:
            return ticker, None
        df.index = pd.to_datetime(df.index).tz_localize(None)
        rename = {}
        for c in df.columns:
            lc = c.lower()
            if lc == "open":              rename[c] = "Open"
            elif lc == "high":            rename[c] = "High"
            elif lc == "low":             rename[c] = "Low"
            elif lc in ("close", "adj close"): rename[c] = "Close"
            elif lc == "volume":          rename[c] = "Volume"
        if rename:
            df = df.rename(columns=rename)
        return ticker, df
    except Exception:
        logger.warning("Falha ao buscar histórico no yfinance: ticker=%s periodo=%s", ticker, periodo)
        return ticker, None


def fetch_all_parallel(
    tickers: list[str],
    periodo: str = "3mo",
    max_workers: int = 8,
) -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, t, periodo): t for t in tickers}
        for future in as_completed(futures):
            ticker, df = future.result()
            if df is not None:
                results[ticker] = df
    return results


def fetch_fundamentals_parallel(
    tickers: list[str],
    max_workers: int = 8,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_fundamentals, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                logger.warning("Falha ao buscar fundamentos em paralelo: ticker=%s fonte=yfinance", ticker)
                results[ticker] = {}
    return results


def _col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _preco_atual_from_df(ticker: str, df_raw: pd.DataFrame) -> dict:
    if df_raw.empty:
        return {}
    close_col = _col(df_raw, ["close", "Close"])
    if close_col is None:
        return {}
    prices = df_raw[close_col].dropna()
    if len(prices) < 2:
        return {}
    atual = float(prices.iloc[-1])
    anterior = float(prices.iloc[-2])
    semana_atras = float(prices.iloc[-5]) if len(prices) >= 5 else anterior
    mes_atras = float(prices.iloc[0])
    vol_col = _col(df_raw, ["volume", "Volume"])
    vol_total = float(df_raw[vol_col].sum()) if vol_col else None
    return {
        "ticker": ticker,
        "nome": ACOES.get(ticker, ticker),
        "preco": atual,
        "variacao_dia": (atual - anterior) / anterior * 100,
        "variacao_semana": (atual - semana_atras) / semana_atras * 100,
        "variacao_mes": (atual - mes_atras) / mes_atras * 100,
        "sparkline": prices.tail(30).tolist(),
        "volume": vol_total,
    }

@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_historico(ticker: str, periodo_label: str = "1A") -> pd.DataFrame:
    period = PERIODOS.get(periodo_label, "1y")
    _, df = _fetch_one(ticker, period)
    if df is None:
        return pd.DataFrame()
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_historico_titled(ticker: str, periodo_label: str = "1A") -> pd.DataFrame:
    period = PERIODOS.get(periodo_label, "1y")
    _, df = _fetch_one(ticker, period)
    return df if df is not None else pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_preco_atual(ticker: str) -> dict:
    try:
        df_raw = get_historico(ticker, "1M")
        return _preco_atual_from_df(ticker, df_raw)
    except Exception:
        logger.warning("Falha ao calcular preço atual: ticker=%s fonte=yfinance", ticker)
        return {}


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_precos_atuais(tickers: tuple[str, ...]) -> dict[str, dict]:
    try:
        period = PERIODOS.get("1M", "1y")
        historicos = fetch_all_parallel(list(tickers), period)
        dados = {}
        for ticker, df_raw in historicos.items():
            data = _preco_atual_from_df(ticker, df_raw)
            if data:
                dados[ticker] = data
        return dados
    except Exception:
        logger.warning(
            "Falha ao buscar preços atuais em lote: quantidade=%s fonte=yfinance",
            len(tickers),
        )
        return {}


@st.cache_data(ttl=600)
def get_fundamentals(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        logger.warning("Falha ao buscar info fundamentalista no yfinance: ticker=%s", ticker)
        return {}

    def safe(key, default=None):
        val = info.get(key, default)
        return val if val not in (None, "N/A", "", 0) else default

    preco_atual    = safe("currentPrice") or safe("regularMarketPrice")
    preco_anterior = safe("previousClose") or safe("regularMarketPreviousClose")
    abertura       = safe("open") or safe("regularMarketOpen")
    max_dia        = safe("dayHigh") or safe("regularMarketDayHigh")
    min_dia        = safe("dayLow")  or safe("regularMarketDayLow")
    max_52s        = safe("fiftyTwoWeekHigh")
    min_52s        = safe("fiftyTwoWeekLow")
    variacao_dia   = (
        (preco_atual - preco_anterior) / preco_anterior * 100
        if preco_atual and preco_anterior else None
    )
    volume       = safe("volume") or safe("regularMarketVolume")
    volume_medio = safe("averageVolume") or safe("averageDailyVolume10Day")

    mc_raw = safe("marketCap")
    if mc_raw:
        if mc_raw >= 1e12:   mc_fmt = f"R$ {mc_raw/1e12:.1f}T"
        elif mc_raw >= 1e9:  mc_fmt = f"R$ {mc_raw/1e9:.1f}B"
        elif mc_raw >= 1e6:  mc_fmt = f"R$ {mc_raw/1e6:.1f}M"
        else:                mc_fmt = f"R$ {mc_raw:,.0f}"
    else:
        mc_fmt = None

    dy_raw    = safe("dividendYield")
    div_anual = safe("trailingAnnualDividendRate")
    dy_pct    = None

    dy_primary = None
    if dy_raw is not None and dy_raw > 0:
        raw_as_pct = dy_raw * 100 if dy_raw < 0.10 else dy_raw
        dy_primary = _sanity("dy", raw_as_pct)

    dy_trail = None
    if div_anual and preco_atual and div_anual > 0:
        dy_trail = _sanity("dy", div_anual / preco_atual * 100)

    dy_hist = None
    try:
        tk_obj    = yf.Ticker(ticker)
        divs_hist = tk_obj.dividends
        if divs_hist is not None and len(divs_hist) > 0:
            divs_hist.index = pd.to_datetime(divs_hist.index).tz_localize(None)
            cutoff      = pd.Timestamp.now() - pd.DateOffset(months=18)
            hist_total  = float(divs_hist[divs_hist.index >= cutoff].sum())
            annual_hist = hist_total * 12 / 18
            if annual_hist > 0 and preco_atual:
                dy_hist = _sanity("dy", annual_hist / preco_atual * 100)
    except Exception:
        logger.warning("Falha ao buscar histórico de dividendos: ticker=%s fonte=yfinance", ticker)
        pass

    if (dy_primary and dy_trail and dy_trail / dy_primary > 5.0):
        dy_pct = dy_primary
    else:
        candidates = [v for v in [dy_primary, dy_trail, dy_hist] if v is not None and v > 0]
        dy_pct = max(candidates) if candidates else None

    beta_raw = _sanity("beta", safe("beta"))
    beta = beta_raw
    if beta is None or abs(beta) < 0.50:
        try:
            tk_obj2 = yf.Ticker(ticker) if 'tk_obj' not in dir() else tk_obj
            df_stk  = tk_obj2.history(period="2y", auto_adjust=True)
            df_ibov = yf.Ticker("^BVSP").history(period="2y", auto_adjust=True)
            if df_stk is not None and df_ibov is not None and len(df_stk) > 100 and len(df_ibov) > 100:
                r_stk  = df_stk["Close"].pct_change().dropna()
                r_ibov = df_ibov["Close"].pct_change().dropna()
                comb   = pd.concat([r_stk, r_ibov], axis=1).dropna()
                if len(comb) > 50:
                    cov  = float(comb.iloc[:, 0].cov(comb.iloc[:, 1]))
                    var  = float(comb.iloc[:, 1].var())
                    beta = _sanity("beta", round(cov / var, 2)) if var != 0 else None
        except Exception:
            logger.warning("Falha ao calcular beta por histórico: ticker=%s benchmark=^BVSP", ticker)
            beta = beta_raw

    trailing_pe = _sanity("pl", safe("trailingPE"))
    forward_pe  = safe("forwardPE")
    if (trailing_pe and forward_pe and forward_pe > 0 and trailing_pe / forward_pe > 3.0):
        pl = _sanity("pl", forward_pe)
    else:
        pl = trailing_pe
    pvp         = _sanity("pvp",   safe("priceToBook"))
    ev_ebitda   = _sanity("ev_ebitda", safe("enterpriseToEbitda"))
    margem_raw  = safe("profitMargins")
    margem_pct  = _sanity("margem_liquida", margem_raw * 100 if margem_raw is not None else None)
    roe_raw     = safe("returnOnEquity")
    roe_pct     = _sanity("roe", roe_raw * 100 if roe_raw is not None else None)

    return {
        "preco": preco_atual, "preco_anterior": preco_anterior,
        "variacao_dia": variacao_dia, "abertura": abertura,
        "max_dia": max_dia, "min_dia": min_dia,
        "max_52s": max_52s, "min_52s": min_52s,
        "volume": volume, "volume_medio": volume_medio,
        "market_cap": mc_fmt, "market_cap_raw": mc_raw,
        "pl":       round(pl, 1)         if pl         is not None else None,
        "pvp":      round(pvp, 2)        if pvp        is not None else None,
        "ev_ebitda": round(ev_ebitda, 1) if ev_ebitda  is not None else None,
        "dy":       round(dy_pct, 2)     if dy_pct     is not None else None,
        "div_anual": div_anual,
        "margem_liquida": round(margem_pct, 1) if margem_pct is not None else None,
        "roe":      round(roe_pct, 1)    if roe_pct    is not None else None,
        "beta":     round(beta, 2)       if beta       is not None else None,
        "nome":     safe("longName") or safe("shortName"),
        "setor":    safe("sector"),
        "industria": safe("industry"),
        "pais":     safe("country"),
    }


def get_analyst_data(ticker: str) -> dict:
    """
    Busca dados de analistas, dividendos e resultados via yfinance.
    Todos os campos são opcionais — retorna None quando indisponível.
    """
    import datetime as _dt
    result: dict = {
        "recommendation_key":  None,
        "recommendation_mean": None,
        "n_analysts":          None,
        "target_mean":         None,
        "target_high":         None,
        "target_low":          None,
        "target_median":       None,
        "dividend_rate":       None,
        "ex_dividend_date":    None,
        "dividend_history":    [],
        "earnings_date":       None,
        "recent_actions":      [],
    }
    try:
        t    = yf.Ticker(ticker)
        info = t.info or {}

        result["recommendation_key"]  = info.get("recommendationKey")
        result["recommendation_mean"] = info.get("recommendationMean")
        result["n_analysts"]          = info.get("numberOfAnalystOpinions")

        for field, key in [
            ("target_mean",   "targetMeanPrice"),
            ("target_high",   "targetHighPrice"),
            ("target_low",    "targetLowPrice"),
            ("target_median", "targetMedianPrice"),
        ]:
            v = info.get(key)
            if v and v > 0:
                result[field] = round(float(v), 2)

        dr = info.get("trailingAnnualDividendRate") or info.get("dividendRate")
        if dr and dr > 0:
            result["dividend_rate"] = round(float(dr), 4)

        ex_div = info.get("exDividendDate")
        if ex_div:
            try:
                result["ex_dividend_date"] = _dt.datetime.fromtimestamp(
                    int(ex_div)
                ).strftime("%d/%m/%Y")
            except Exception:
                logger.warning("Falha ao converter data ex-dividendo: ticker=%s fonte=yfinance", ticker)
                pass

        try:
            divs = t.dividends
            if divs is not None and not divs.empty:
                result["dividend_history"] = [
                    {
                        "date":  str(idx.date()) if hasattr(idx, "date") else str(idx),
                        "value": round(float(v), 4),
                    }
                    for idx, v in divs.tail(8).items()
                ]
        except Exception:
            logger.warning("Falha ao buscar dividendos de analistas: ticker=%s fonte=yfinance", ticker)
            pass

        try:
            cal = t.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date") or cal.get("earnings_date")
                if ed is not None:
                    items = list(ed) if hasattr(ed, "__iter__") and not isinstance(ed, str) else [ed]
                    if items:
                        dt = items[0]
                        result["earnings_date"] = (
                            dt.strftime("%d/%m/%Y")
                            if hasattr(dt, "strftime")
                            else str(dt)[:10]
                        )
        except Exception:
            logger.warning("Falha ao buscar calendário de resultados: ticker=%s fonte=yfinance", ticker)
            pass

        try:
            up = t.upgrades_downgrades
            if up is not None and not up.empty:
                result["recent_actions"] = [
                    {
                        "firm":       str(row.get("Firm", "")),
                        "to_grade":   str(row.get("ToGrade", "")),
                        "from_grade": str(row.get("FromGrade", "")),
                        "action":     str(row.get("Action", "")),
                        "date":       str(idx.date()) if hasattr(idx, "date") else str(idx),
                    }
                    for idx, row in up.head(5).iterrows()
                ]
        except Exception:
            logger.warning("Falha ao buscar upgrades/downgrades: ticker=%s fonte=yfinance", ticker)
            pass

    except Exception:
        logger.warning("Falha ao buscar dados de analistas: ticker=%s fonte=yfinance", ticker)
        pass

    return result


_CORRELACOES_FIXAS: dict = {
    "PETR4.SA":  ["PETR3.SA","PRIO3.SA","RECV3.SA","VBBR3.SA","BZ=F"],
    "PETR3.SA":  ["PETR4.SA","PRIO3.SA","BZ=F"],
    "VALE3.SA":  ["CMIN3.SA","CSNA3.SA","GGBR4.SA","TIO=F"],
    "ITUB4.SA":  ["BBAS3.SA","BBDC4.SA","ITSA4.SA","SANB11.SA"],
    "BBAS3.SA":  ["ITUB4.SA","BBDC4.SA","SANB11.SA","BPAC11.SA"],
    "BBDC4.SA":  ["ITUB4.SA","BBAS3.SA","SANB11.SA"],
    "WEGE3.SA":  ["EMBR3.SA","INTB3.SA"],
    "SUZB3.SA":  ["KLBN11.SA","RANI3.SA"],
    "ELET3.SA":  ["ENEV3.SA","EGIE3.SA","CMIG4.SA","CPFE3.SA"],
    "RENT3.SA":  ["MOVI3.SA","LCAM3.SA"],
    "RADL3.SA":  ["HYPE3.SA","FLRY3.SA","HAPV3.SA"],
    "PRIO3.SA":  ["PETR4.SA","RECV3.SA","BZ=F"],
    "MGLU3.SA":  ["ARZZ3.SA","LREN3.SA","SOMA3.SA"],
}


def get_correlated_assets(ticker: str, grupos: dict | None = None) -> list:
    """Retorna até 5 tickers correlacionados ao ativo dado."""
    fixas = _CORRELACOES_FIXAS.get(ticker, [])
    setor_tickers: list = []
    if grupos:
        for grupo, tickers in grupos.items():
            if ticker in tickers:
                setor_tickers = [t for t in tickers if t != ticker][:4]
                break
    combined = list(dict.fromkeys(fixas + setor_tickers))
    return combined[:5]


get_info_fundamentalista = get_fundamentals
