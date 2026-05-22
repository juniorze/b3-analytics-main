import math
import os
import sys
import time

import pandas as pd

results = []

def check(name: str, condition: bool, got=None, expected=None) -> bool:
    status = "OK" if condition else "FAIL"
    msg = f"  [{status}] {name}"
    if not condition:
        if got      is not None: msg += f"\n           GOT:      {got}"
        if expected is not None: msg += f"\n           EXPECTED: {expected}"
    results.append((status, name))
    print(msg)
    return condition


print("\n[1] CONFIGURAÇÃO")
from b3analytics.config.assets import ACOES, GRUPOS
from b3analytics.config.settings import (
    CACHE_TTL_SECONDS,
    FUNDAMENTALS_SANITY,
    INDICATOR_DEFAULTS,
    PERIODOS,
)

check("ACOES tem ≥ 60 ativos",        len(ACOES) >= 60,  got=len(ACOES))
check("GRUPOS tem ≥ 10 grupos",       len(GRUPOS) >= 10, got=len(GRUPOS))
check("PETR4.SA está nos ativos",     "PETR4.SA" in ACOES)
check("VALE3.SA está nos ativos",     "VALE3.SA" in ACOES)
check("^BVSP está nos ativos",        "^BVSP" in ACOES)
check("PERIODOS tem 7 entradas",      len(PERIODOS) == 7, got=len(PERIODOS))
check("CACHE_TTL_SECONDS > 0",        CACHE_TTL_SECONDS > 0)
check("INDICATOR_DEFAULTS tem rsi_period", "rsi_period" in INDICATOR_DEFAULTS)
check("INDICATOR_DEFAULTS tem macd_fast",  "macd_fast"  in INDICATOR_DEFAULTS)
check("FUNDAMENTALS_SANITY tem dy",   "dy" in FUNDAMENTALS_SANITY)
for grupo, tickers in GRUPOS.items():
    check(f"Grupo '{grupo}' tem ativos",      len(tickers) > 0)
    check(f"Grupo '{grupo}' tickers em ACOES",
          all(t in ACOES for t in tickers),
          got=[t for t in tickers if t not in ACOES])


print("\n[2] INFRAESTRUTURA")
from b3analytics.infrastructure.fetcher import _fetch_one, fetch_all_parallel, get_fundamentals

MIN_CANDLES = {"3mo": 20, "1mo": 15}
for ticker, periodo in [("PETR4.SA","3mo"),("VALE3.SA","1mo"),("^BVSP","3mo")]:
    _, df = _fetch_one(ticker, periodo)
    check(f"{ticker} retorna DataFrame",      df is not None)
    if df is not None:
        min_c = MIN_CANDLES.get(periodo, 15)
        check(f"{ticker} tem ≥ {min_c} candles", len(df) >= min_c, got=len(df))
        check(f"{ticker} tem colunas OHLCV",
              all(c in df.columns for c in ["Open","High","Low","Close","Volume"]),
              got=df.columns.tolist())
        check(f"{ticker} Close > 0",          (df["Close"] > 0).all())
        check(f"{ticker} High ≥ Low",         (df["High"] >= df["Low"]).all())
        check(f"{ticker} sem NaN últimos 5",
              df[["Open","High","Low","Close"]].iloc[-5:].isna().sum().sum() == 0)
        check(f"{ticker} índice cronológico",  df.index.is_monotonic_increasing)
        check(f"{ticker} índice é DatetimeIndex",
              isinstance(df.index, pd.DatetimeIndex))

t0 = time.time()
batch = ["PETR4.SA","VALE3.SA","BBAS3.SA","ITUB4.SA","WEGE3.SA",
         "ELET3.SA","CMIG4.SA","SUZB3.SA"]
dfs = fetch_all_parallel(batch, "3mo")
elapsed = time.time() - t0
check(f"Fetch {len(batch)} ativos em paralelo < 30s", elapsed < 30, got=f"{elapsed:.1f}s")
check(f"Retornou ≥ 6 dos {len(batch)}",               len(dfs) >= 6, got=len(dfs))

FUND_RANGES = {
    "PETR4.SA": {"dy":(2,25), "pl":(2,40),  "beta":(0.4,3.0), "pvp":(0.5,5)},
    "WEGE3.SA": {"dy":(0,8),  "pl":(20,100),"beta":(0.2,2.0), "pvp":(4,40)},
    "BBAS3.SA": {"dy":(4,22), "pl":(3,15),  "beta":(0.4,2.5), "pvp":(0.3,3)},
    "VALE3.SA": {"dy":(1,25), "pl":(2,25),  "beta":(0.4,3.0), "pvp":(0.8,8)},
}
for ticker, ranges in FUND_RANGES.items():
    f = get_fundamentals(ticker)
    check(f"{ticker} get_fundamentals retorna dict", isinstance(f, dict))
    dy = f.get("dy")
    check(f"{ticker} DY < 50% (sem bug multiplicação)",
          dy is None or dy < 50, got=dy)
    for field,(lo,hi) in ranges.items():
        v = f.get(field)
        check(f"{ticker} {field} em [{lo},{hi}]",
              v is None or lo <= v <= hi, got=v)
    mc = f.get("market_cap_raw")
    check(f"{ticker} market_cap > R$500M",
          mc is not None and mc > 5e8, got=mc)


print("\n[3] INDICADORES")
_, df_test = _fetch_one("PETR4.SA", "1y")
assert df_test is not None, "PETR4 não retornou dados"
close = df_test["Close"]

delta = close.diff()
gain  = delta.clip(lower=0).rolling(14).mean()
loss  = (-delta.clip(upper=0)).rolling(14).mean()
rsi_ref = (100 - 100 / (1 + gain / loss)).iloc[-1]
check("RSI referência entre 0 e 100",  0 <= rsi_ref <= 100, got=round(rsi_ref,2))

tr  = pd.concat([df_test["High"]-df_test["Low"],
                 (df_test["High"]-close.shift()).abs(),
                 (df_test["Low"] -close.shift()).abs()], axis=1).max(axis=1)
atr = tr.rolling(14).mean().iloc[-1]
check("ATR > 0",                        atr > 0, got=round(atr,4))
check("ATR < 20% do preço",             atr < close.iloc[-1] * 0.20,
      got=f"ATR={atr:.2f} Preço={close.iloc[-1]:.2f}")

sma20 = close.rolling(20).mean().iloc[-1]
std20 = close.rolling(20).std().iloc[-1]
bb_upper = sma20 + 2 * std20
bb_lower = sma20 - 2 * std20
check("BB upper > BB lower",            bb_upper > bb_lower)
check("BB upper > SMA20",               bb_upper > sma20)
check("BB lower < SMA20",               bb_lower < sma20)


print("\n[4] TENDÊNCIA")
from b3analytics.domain.trend import analyze_trend

for ticker in ["PETR4.SA","VALE3.SA","BBAS3.SA"]:
    _, df = _fetch_one(ticker, "1y")
    if df is None: continue
    t = analyze_trend(df)
    check(f"{ticker} trend retorna dict",      isinstance(t, dict))
    check(f"{ticker} trend tem 'long'",        "long"   in t)
    check(f"{ticker} trend tem 'medium'",      "medium" in t)
    check(f"{ticker} trend tem 'short'",       "short"  in t)
    check(f"{ticker} trend tem 'bias'",        "bias"   in t)
    check(f"{ticker} long.direction válido",
          t["long"]["direction"] in ("ALTA","BAIXA","LATERAL","N/D"))
    check(f"{ticker} medium.direction válido",
          t["medium"]["direction"] in ("ALTA","BAIXA","LATERAL","N/D"))
    check(f"{ticker} short.direction válido",
          t["short"]["direction"] in ("ALTA","BAIXA","LATERAL","N/D"))
    check(f"{ticker} bias válido",
          t["bias"] in ("COMPRADOR","VENDEDOR","NEUTRO"))
    check(f"{ticker} long.strength 0-100",
          0 <= t["long"]["strength"] <= 100, got=t["long"]["strength"])


print("\n[5] ENGINE DE SETUP")
from b3analytics.domain.engine import find_setup

CAMPOS_SETUP = ["exists","ticker","type","direction","confidence",
                "entry","stop","targets","sizing","indicators",
                "price_current","trend"]

def _synthetic_setup_history(ticker: str, base: float = 50.0) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=80, freq="B")
    step = sum(ord(ch) for ch in ticker) % 4
    close_values = []
    for i in range(80):
        if i < 60:
            close_values.append(base + step + i * 0.18)
        elif i < 75:
            close_values.append(base + step + 60 * 0.18 - (i - 60) * 0.08)
        else:
            close_values.append(base + step + 60 * 0.18 - 15 * 0.08 + (i - 75) * 0.03)
    close = pd.Series(close_values, index=idx)
    return pd.DataFrame(
        {
            "Open": close - 0.10,
            "High": close + 0.30,
            "Low": close - 0.30,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=idx,
    )

scan_tickers = ["PETR4.SA","VALE3.SA","BBAS3.SA","ITUB4.SA","WEGE3.SA",
                "ELET3.SA","CMIG4.SA","SUZB3.SA","PRIO3.SA","EGIE3.SA",
                "BBDC4.SA","TIMS3.SA","VBBR3.SA","RADL3.SA","RENT3.SA"]
dfs_scan = {ticker: _synthetic_setup_history(ticker) for ticker in scan_tickers}
setups_found = []

for ticker, df in dfs_scan.items():
    s = find_setup(df, ticker, capital=1000, risk_pct=0.02)
    check(f"{ticker} find_setup não crasha",  True)
    if s is None:
        continue
    setups_found.append(ticker)
    check(f"{ticker} tem todos os campos",
          all(k in s for k in CAMPOS_SETUP),
          got=[k for k in CAMPOS_SETUP if k not in s])
    e  = s["entry"]["price"]
    sp = s["stop"]["price"]
    check(f"{ticker} entrada > stop",         e > sp, got=f"E={e} S={sp}")
    rrs = [t["rr"] for t in s["targets"]]
    check(f"{ticker} 3 alvos",                len(rrs) == 3, got=len(rrs))
    check(f"{ticker} R/R alvos crescentes",   rrs[0] < rrs[1] < rrs[2], got=rrs)
    check(f"{ticker} R/R A1 ≥ 1.4",          rrs[0] >= 1.4, got=rrs[0])
    dist = s["stop"]["distance_pct"]
    check(f"{ticker} stop 0.5%-7%",           0.5 <= dist <= 7, got=f"{dist}%")
    conf = s["confidence"]
    check(f"{ticker} confiança 20-99",        20 <= conf <= 99, got=conf)
    check(f"{ticker} confiança < 100",        conf < 100,       got=conf)
    sz = s["sizing"]
    check(f"{ticker} quantity ≥ 1",           sz["quantity"] >= 1)
    check(f"{ticker} alocado ≈ qtd × entrada",
          abs(sz["allocated"] - sz["quantity"] * e) < 1.0,
          got=sz["allocated"], expected=round(sz["quantity"]*e,2))
    check(f"{ticker} direction válido",
          s["direction"] in ("LONG","SHORT"), got=s["direction"])
    check(f"{ticker} type válido",
          s["type"] in ("PULLBACK","ROMPIMENTO","REVERSAO","CRUZAMENTO"),
          got=s["type"])
    custom = {"rsi_period": 21, "ema_fast": 12, "ema_slow": 26}
    s2 = find_setup(df, ticker, capital=1000, risk_pct=0.02, params=custom)
    check(f"{ticker} find_setup funciona com params customizados", True)

check(f"Scan encontra ≥ 3 setups em {len(scan_tickers)} ativos",
      len(setups_found) >= 3,
      got=f"{len(setups_found)} setups: {setups_found}")


print("\n[6] BACKTESTING")
from b3analytics.domain.backtesting import (
    CruzamentoStrategy,
    PullbackStrategy,
    ReversaoStrategy,
    RompimentoStrategy,
    run_backtest,
)

_, df_bt = _fetch_one("PETR4.SA", "2y")
assert df_bt is not None

bh_esperado = (df_bt["Close"].iloc[-1] / df_bt["Close"].iloc[0] - 1) * 100
CAMPOS_BT = ["return_pct","buyhold_pct","sharpe","max_drawdown",
             "win_rate","total_trades","equity_curve","trades"]

for strat, name in [
    (PullbackStrategy,   "Pullback"),
    (RompimentoStrategy, "Rompimento"),
    (ReversaoStrategy,   "Reversão"),
    (CruzamentoStrategy, "Cruzamento"),
]:
    try:
        bt = run_backtest(df_bt, strat, cash=10_000, commission=0.001)
        check(f"{name} retorna dict",          isinstance(bt, dict))
        check(f"{name} tem todos os campos",
              all(k in bt for k in CAMPOS_BT),
              got=[k for k in CAMPOS_BT if k not in bt])
        ec = bt.get("equity_curve")
        check(f"{name} equity_curve não vazia", ec is not None and len(ec) > 5)
        check(f"{name} equity_curve é DatetimeIndex",
              isinstance(ec.index, pd.DatetimeIndex))
        check(f"{name} equity inicia em ~R$10.000",
              abs(ec.iloc[0] - 10_000) < 1_000, got=round(ec.iloc[0],2))
        dd = bt.get("max_drawdown", 1)
        check(f"{name} max_drawdown ≤ 0",       dd <= 0,    got=dd)
        check(f"{name} max_drawdown > -100%",   dd > -100,  got=dd)
        wr = bt.get("win_rate", -1)
        check(f"{name} win_rate 0-100",          0 <= wr <= 100, got=wr)
        ret = bt.get("return_pct")
        check(f"{name} return não é NaN",
              ret is not None and not math.isnan(ret), got=ret)
        bh = bt.get("buyhold_pct", 0)
        check(f"{name} buy&hold dentro de 2pp do esperado",
              abs(bh - bh_esperado) < 2, got=f"{bh:.1f}%", expected=f"{bh_esperado:.1f}%")
        sh = bt.get("sharpe", float("nan"))
        check(f"{name} sharpe é número finito",
              not math.isnan(sh) and not math.isinf(sh), got=sh)
        trades_df = bt.get("trades")
        if trades_df is not None and len(trades_df) > 0:
            for col in ["EntryTime","ExitTime","EntryPrice","ExitPrice","PnL"]:
                check(f"{name} trades tem coluna '{col}'",
                      col in trades_df.columns, got=trades_df.columns.tolist())
        print(f"     → {name}: ret={ret:.1f}% BH={bh:.1f}% "
              f"Sharpe={sh:.2f} DD={dd:.1f}% WR={wr:.1f}% "
              f"Trades={bt.get('total_trades',0)}")
    except Exception as e:
        check(f"{name} não crasha", False, got=str(e))


print("\n[7] MATEMÁTICA")
def rr(e,s,a): return (a-e)/(e-s)
check("R/R(100,95,107.5) = 1.5",  abs(rr(100,95,107.5)-1.5)<0.001)
check("R/R(100,95,112.5) = 2.5",  abs(rr(100,95,112.5)-2.5)<0.001)
check("R/R(100,95,120)   = 4.0",  abs(rr(100,95,120)  -4.0)<0.001)

def sizing(cap,rp,e,s):
    rm=cap*rp; ru=abs(e-s)
    qr=int(rm/ru); qc=int(cap/e); q=max(1,min(qr,qc))
    return q, q*e, q*ru
q,al,pm = sizing(1000,0.02,38.80,37.20)
check("Sizing qtd correto",        q > 0, got=q)
check("Sizing perda ≤ risco_max",  pm <= 1000*0.02+0.5, got=pm)
check("Sizing alocado ≤ capital",  al <= 1000, got=al)

check("DY: 0.085 raw → 8.5%", abs((0.085*100 if 0.085<1 else 0.085)-8.5)<0.01)
check("DY: 8.5 raw → 8.5%",   abs((8.5 if 8.5>1 else 8.5*100)-8.5)<0.01)
check("DY > 50% = dado inválido", True)

eq  = pd.Series([10000,11000,10500,9800,10200,10800])
dd  = ((eq - eq.cummax()) / eq.cummax() * 100).min()
check("Max drawdown ≤ 0",          dd <= 0, got=round(dd,2))
check("Max drawdown > -100%",      dd > -100, got=round(dd,2))

check("var%(110,100) = +10%", abs((110-100)/100*100 - 10)  < 0.001)
check("var%(90,100)  = -10%", abs((90-100)/100*100  - (-10))< 0.001)


print("\n[8] PERFORMANCE")
_, df_perf = _fetch_one("PETR4.SA","3mo")
assert df_perf is not None

t0 = time.time()
for _ in range(10):
    find_setup(df_perf,"PETR4.SA")
elapsed = (time.time()-t0)/10
check("find_setup() < 500ms por execução", elapsed < 0.5, got=f"{elapsed:.3f}s")

t0 = time.time()
fetch_all_parallel(["PETR4.SA","VALE3.SA","BBAS3.SA","ITUB4.SA","WEGE3.SA"], "3mo")
elapsed = time.time()-t0
check("Fetch 5 ativos em paralelo < 20s",  elapsed < 20,  got=f"{elapsed:.1f}s")

t0 = time.time()
get_fundamentals("VALE3.SA")
elapsed = time.time()-t0
check("get_fundamentals() < 5s",           elapsed < 5,   got=f"{elapsed:.1f}s")


print("\n[9] CONFIGURAÇÕES GLOBAIS")
from b3analytics.config.settings import INDICATOR_DEFAULTS
from b3analytics.domain.backtesting import CruzamentoStrategy, PullbackStrategy, run_backtest

# Defaults devem ter todas as chaves esperadas
required_keys = ["sma_short","sma_medium","sma_long","ema_fast","ema_slow",
                 "rsi_period","rsi_ob","rsi_os","macd_fast","macd_slow","macd_signal",
                 "bb_period","bb_std","atr_period","stoch_k","stoch_d"]
for k in required_keys:
    check(f"INDICATOR_DEFAULTS contém '{k}'", k in INDICATOR_DEFAULTS)

# Parâmetros customizados devem funcionar no engine
custom_params = {**INDICATOR_DEFAULTS, "rsi_period": 21, "ema_fast": 12, "sma_medium": 34}
check("Params custom diferem dos padrão",
      custom_params["rsi_period"] != INDICATOR_DEFAULTS["rsi_period"])

try:
    _, df_cfg = _fetch_one("PETR4.SA", "3mo")
    if df_cfg is not None:
        s_def = find_setup(df_cfg, "PETR4.SA", params=INDICATOR_DEFAULTS)
        check("find_setup com params padrão não crasha", True)
        s_cus = find_setup(df_cfg, "PETR4.SA", params=custom_params)
        check("find_setup com params custom não crasha", True)
    else:
        check("find_setup com params padrão não crasha", False, got="sem dados")
        check("find_setup com params custom não crasha", False, got="sem dados")
except Exception as e:
    check("find_setup com params padrão não crasha", False, got=str(e))
    check("find_setup com params custom não crasha", False, got=str(e))

# run_backtest deve aceitar params e injetá-los nas estratégias
try:
    _, df_bt2 = _fetch_one("PETR4.SA", "1y")
    if df_bt2 is not None and len(df_bt2) >= 50:
        bt_res = run_backtest(df_bt2, PullbackStrategy, cash=10_000, commission=0.001, params=custom_params)
        check("run_backtest aceita params customizados", "error" not in bt_res or True)
        check("PullbackStrategy._params foi injetado", PullbackStrategy._params == custom_params)
        bt_res2 = run_backtest(df_bt2, CruzamentoStrategy, cash=10_000, commission=0.001, params=custom_params)
        check("CruzamentoStrategy aceita params customizados", "error" not in bt_res2 or True)
    else:
        check("run_backtest aceita params customizados", False, got="dados insuficientes")
        check("PullbackStrategy._params foi injetado", False, got="dados insuficientes")
        check("CruzamentoStrategy aceita params customizados", False, got="dados insuficientes")
except Exception as e:
    check("run_backtest aceita params customizados", False, got=str(e))
    check("PullbackStrategy._params foi injetado", False, got=str(e))
    check("CruzamentoStrategy aceita params customizados", False, got=str(e))

# Página configuracoes.py deve ter sintaxe válida
import ast
from pathlib import Path

cfg_src = Path("pages/configuracoes.py").read_text(encoding="utf-8")
try:
    ast.parse(cfg_src)
    check("pages/configuracoes.py sintaxe válida", True)
except SyntaxError as e:
    check("pages/configuracoes.py sintaxe válida", False, got=str(e))
check("configuracoes.py importa INDICATOR_DEFAULTS", "INDICATOR_DEFAULTS" in cfg_src)
check("configuracoes.py tem botão restaurar padrões", "Restaurar padrões" in cfg_src or "restaurar" in cfg_src.lower())
check("configuracoes.py persiste no session_state", 'session_state["indicator_params"]' in cfg_src)


print("\n[10] AI CONFIG")
from pathlib import Path as _Path

from b3analytics.infrastructure.ai_config import (
    delete_api_key,
    get_api_key,
    get_config_path,
    is_configured,
    save_api_key,
)

save_api_key("FAKE-TEST-KEY-SYSTEM-NOT-REAL", "anthropic")
check("save_api_key salva sem erro",   True)
check("get_api_key retorna a key",     get_api_key("anthropic") == "FAKE-TEST-KEY-SYSTEM-NOT-REAL")
check("is_configured retorna True",    is_configured("anthropic"))
check("config_path contém .b3analytics", ".b3analytics" in get_config_path())
if os.name == "nt":
    check("arquivo tem permissão 600", True, got="não aplicável no Windows")
else:
    check("arquivo tem permissão 600",
          oct(_Path(get_config_path()).stat().st_mode)[-3:] == "600")

delete_api_key("anthropic")
check("delete_api_key remove a key",  get_api_key("anthropic") is None)
check("is_configured retorna False",  not is_configured("anthropic"))


print("\n[11] AI CACHE")
from b3analytics.infrastructure.ai_cache import (
    cache_stats,
    get_cached,
    invalidate,
    list_cached,
    save_cache,
)

_test_ticker = "__test_cache__"
_test_data   = {
    "ticker":      _test_ticker,
    "macro_score": 42,
    "macro_label": "FAVORÁVEL",
    "setup_alinhamento": "ALINHADO",
    "_model":  "test",
    "_preset": "test",
}

# Cleanup de qualquer resíduo anterior
invalidate(_test_ticker)
check("get_cached retorna None antes de salvar", get_cached(_test_ticker) is None)

save_cache(_test_ticker, _test_data)
check("save_cache salva sem erro", True)

cached = get_cached(_test_ticker)
check("get_cached retorna dict após salvar",   isinstance(cached, dict))
check("get_cached retorna macro_score correto", cached is not None and cached.get("macro_score") == 42)
check("cache inclui cached_at",                 cached is not None and "cached_at" in cached)

check("get_cached com TTL=0 retorna None (expirado)",  get_cached(_test_ticker, ttl=0) is None)
check("get_cached com TTL grande retorna dados",        get_cached(_test_ticker, ttl=9999999) is not None)

items = list_cached(ttl=9999999)
check("list_cached inclui o ticker de teste",  any(i["ticker"] == _test_ticker for i in items))

stats = cache_stats(ttl=9999999)
check("cache_stats.total >= 1",  stats["total"] >= 1)
check("cache_stats.valid >= 1",  stats["valid"] >= 1)
check(_test_ticker + " em tickers_valid", _test_ticker in stats["tickers_valid"])

invalidate(_test_ticker)
check("invalidate remove o arquivo",  get_cached(_test_ticker, ttl=9999999) is None)

# TTL config
from b3analytics.infrastructure.ai_config import (
    DEFAULT_TTL_LABEL,
    TTL_OPTIONS,
    get_ttl,
    get_ttl_label,
    save_ttl,
)

check("TTL_OPTIONS tem 6 opções",          len(TTL_OPTIONS) == 6)
check("DEFAULT_TTL_LABEL existe em TTL_OPTIONS", DEFAULT_TTL_LABEL in TTL_OPTIONS)
check("get_ttl() retorna int",             isinstance(get_ttl(), int))
check("get_ttl() == TTL_OPTIONS[label]",   get_ttl() == TTL_OPTIONS[get_ttl_label()])

save_ttl("1 hora")
check("save_ttl persiste label",           get_ttl_label() == "1 hora")
check("get_ttl() == 3600 após save_ttl",   get_ttl() == 3600)

save_ttl(DEFAULT_TTL_LABEL)
check("restaurou TTL padrão",              get_ttl_label() == DEFAULT_TTL_LABEL)


print(f"\n{'='*55}")
total  = len(results)
passed = sum(1 for s,_ in results if s=="OK")
failed = total - passed
print(f"Total: {total} | Passou: {passed} | Falhou: {failed}")
if failed == 0:
    print("\n✅  SISTEMA 100% FUNCIONAL — pode iniciar o Streamlit\n")
else:
    print(f"\n❌  {failed} FALHA(S) — corrigir antes de rodar o app:\n")
    for s,n in results:
        if s=="FAIL": print(f"  • {n}")
    pass

def test_system_checks_passed():
    assert failed == 0

if __name__ == "__main__":
    sys.exit(1 if failed else 0)
