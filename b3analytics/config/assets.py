"""
Ativos e grupos. Suporta customizações persistidas em ~/.b3analytics/custom_assets.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

# ── Padrão B3 ─────────────────────────────────────────────────────────────────
_ACOES_DEFAULT: dict[str, str] = {
    "ITUB4.SA": "Itaú Unibanco PN",
    "BBDC4.SA": "Bradesco PN",
    "BBAS3.SA": "Banco do Brasil ON",
    "SANB11.SA": "Santander Units",
    "BPAC11.SA": "BTG Pactual Units",
    "ITSA4.SA": "Itaúsa PN",
    "BBSE3.SA": "BB Seguridade ON",
    "PETR4.SA": "Petrobras PN",
    "PETR3.SA": "Petrobras ON",
    "PRIO3.SA": "PetroRio ON",
    "RECV3.SA": "Petroreconcavo ON",
    "CSAN3.SA": "Cosan ON",
    "VBBR3.SA": "Vibra Energia ON",
    "ELET3.SA": "Eletrobras ON",
    "ELET6.SA": "Eletrobras PNB",
    "ENEV3.SA": "Eneva ON",
    "EGIE3.SA": "Engie Brasil ON",
    "CMIG4.SA": "Cemig PN",
    "CPFE3.SA": "CPFL Energia ON",
    "EQTL3.SA": "Equatorial ON",
    "SBSP3.SA": "Sabesp ON",
    "TAEE11.SA": "Taesa Units",
    "ENGI11.SA": "Energisa Units",
    "AURE3.SA": "Auren Energia ON",
    "VALE3.SA": "Vale ON",
    "CSNA3.SA": "CSN ON",
    "GGBR4.SA": "Gerdau PN",
    "GOAU4.SA": "Metalúrgica Gerdau PN",
    "USIM5.SA": "Usiminas PNA",
    "CMIN3.SA": "CSN Mineração ON",
    "AGRO3.SA": "BrasilAgro ON",
    "SLCE3.SA": "SLC Agrícola ON",
    "SMTO3.SA": "São Martinho ON",
    "JBSS3.SA": "JBS ON",
    "BEEF3.SA": "Minerva ON",
    "BRFS3.SA": "BRF ON",
    "MRFG3.SA": "Marfrig ON",
    "MDIA3.SA": "M. Dias Branco ON",
    "SUZB3.SA": "Suzano ON",
    "KLBN11.SA": "Klabin Units",
    "RANI3.SA": "Irani Papel ON",
    "CYRE3.SA": "Cyrela ON",
    "MRVE3.SA": "MRV ON",
    "EZTC3.SA": "EZTEC ON",
    "TEND3.SA": "Tenda ON",
    "DIRR3.SA": "Direcional ON",
    "JHSF3.SA": "JHSF ON",
    "MGLU3.SA": "Magazine Luiza ON",
    "LREN3.SA": "Lojas Renner ON",
    "ARZZ3.SA": "Arezzo ON",
    "SOMA3.SA": "Grupo Soma ON",
    "PETZ3.SA": "Petz ON",
    "NTCO3.SA": "Natura &Co ON",
    "ALPA4.SA": "Alpargatas PN",
    "RADL3.SA": "Raia Drogasil ON",
    "HAPV3.SA": "Hapvida ON",
    "RDOR3.SA": "Rede D'Or ON",
    "FLRY3.SA": "Fleury ON",
    "HYPE3.SA": "Hypera ON",
    "QUAL3.SA": "Qualicorp ON",
    "RENT3.SA": "Localiza ON",
    "MOVI3.SA": "Movida ON",
    "RAIL3.SA": "Rumo ON",
    "CCRO3.SA": "CCR ON",
    "ECOR3.SA": "EcoRodovias ON",
    "STBP3.SA": "Santos Brasil ON",
    "VIVT3.SA": "Vivo ON",
    "TIMS3.SA": "TIM ON",
    "TOTVS3.SA": "TOTVS ON",
    "INTB3.SA": "Intelbras ON",
    "LWSA3.SA": "Locaweb ON",
    "MULT3.SA": "Multiplan ON",
    "IGTI11.SA": "Iguatemi Units",
    "COGN3.SA": "Cogna ON",
    "YDUQ3.SA": "Yduqs ON",
    "PSSA3.SA": "Porto Seguro ON",
    "SULA11.SA": "SulAmérica Units",
    "AZUL4.SA": "Azul PN",
    "GOLL4.SA": "Gol PN",
    "WEGE3.SA": "WEG ON",
    "EMBR3.SA": "Embraer ON",
    "ABEV3.SA": "Ambev ON",
    "^BVSP": "Ibovespa",
}

_GRUPOS_DEFAULT: dict[str, list[str]] = {
    "Financeiro":  ["ITUB4.SA","BBDC4.SA","BBAS3.SA","SANB11.SA","BPAC11.SA","ITSA4.SA","BBSE3.SA"],
    "Petróleo":    ["PETR4.SA","PETR3.SA","PRIO3.SA","RECV3.SA","CSAN3.SA","VBBR3.SA"],
    "Energia":     ["ELET3.SA","ENEV3.SA","EGIE3.SA","CMIG4.SA","EQTL3.SA","SBSP3.SA","TAEE11.SA","ENGI11.SA","AURE3.SA"],
    "Mineração":   ["VALE3.SA","CSNA3.SA","GGBR4.SA","USIM5.SA","CMIN3.SA"],
    "Agro":        ["AGRO3.SA","SLCE3.SA","SMTO3.SA","JBSS3.SA","BEEF3.SA","BRFS3.SA","MRFG3.SA"],
    "Celulose":    ["SUZB3.SA","KLBN11.SA","RANI3.SA"],
    "Construção":  ["CYRE3.SA","MRVE3.SA","EZTC3.SA","TEND3.SA","DIRR3.SA"],
    "Varejo":      ["MGLU3.SA","LREN3.SA","ARZZ3.SA","SOMA3.SA","PETZ3.SA"],
    "Saúde":       ["RADL3.SA","HAPV3.SA","RDOR3.SA","FLRY3.SA","HYPE3.SA"],
    "Logística":   ["RENT3.SA","MOVI3.SA","RAIL3.SA","CCRO3.SA"],
    "Telecom":     ["VIVT3.SA","TIMS3.SA"],
    "Tecnologia":  ["TOTVS3.SA","INTB3.SA","LWSA3.SA"],
    "Indústria":   ["WEGE3.SA","EMBR3.SA","ABEV3.SA"],
}

_CRYPTO_DEFAULT: dict[str, str] = {
    "BTC-USD":   "Bitcoin",
    "ETH-USD":   "Ethereum",
    "SOL-USD":   "Solana",
    "BNB-USD":   "BNB",
    "ADA-USD":   "Cardano",
    "MATIC-USD": "Polygon",
    "DOT-USD":   "Polkadot",
    "AVAX-USD":  "Avalanche",
}

CUSTOM_FILE = Path.home() / ".b3analytics" / "custom_assets.json"
logger = logging.getLogger(__name__)


def _load_custom() -> dict:
    try:
        if CUSTOM_FILE.exists():
            return json.loads(CUSTOM_FILE.read_text())
    except Exception:
        logger.warning("Falha ao carregar customizações de ativos: arquivo=%s", CUSTOM_FILE)
        pass
    return {"acoes": {}, "grupos": {}, "crypto_enabled": False, "removed": []}


def _save_custom(data: dict) -> None:
    CUSTOM_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_acoes() -> dict[str, str]:
    custom  = _load_custom()
    removed = set(custom.get("removed", []))
    acoes   = {k: v for k, v in _ACOES_DEFAULT.items() if k not in removed}
    acoes.update(custom.get("acoes", {}))
    if custom.get("crypto_enabled", False):
        acoes.update(_CRYPTO_DEFAULT)
        acoes.update(custom.get("crypto_custom", {}))
    return acoes


def get_grupos() -> dict[str, list[str]]:
    custom  = _load_custom()
    removed = set(custom.get("removed", []))
    grupos: dict[str, list[str]] = {}
    for nome, tickers in _GRUPOS_DEFAULT.items():
        filtrados = [t for t in tickers if t not in removed]
        if filtrados:
            grupos[nome] = filtrados
    for nome, tickers in custom.get("grupos", {}).items():
        if nome in grupos:
            grupos[nome] = list(dict.fromkeys(grupos[nome] + tickers))
        else:
            grupos[nome] = tickers
    if custom.get("crypto_enabled", False):
        grupos["Cripto"] = (
            list(_CRYPTO_DEFAULT.keys())
            + list(custom.get("crypto_custom", {}).keys())
        )
    return grupos


def add_ativo(ticker: str, nome: str) -> None:
    data = _load_custom()
    data.setdefault("acoes", {})[ticker] = nome
    removed = data.get("removed", [])
    if ticker in removed:
        removed.remove(ticker)
        data["removed"] = removed
    _save_custom(data)


def remove_ativo(ticker: str) -> None:
    data = _load_custom()
    data.setdefault("removed", [])
    if ticker not in data["removed"]:
        data["removed"].append(ticker)
    data.get("acoes", {}).pop(ticker, None)
    _save_custom(data)


def add_grupo(nome: str, tickers: list[str]) -> None:
    data = _load_custom()
    data.setdefault("grupos", {})[nome] = tickers
    _save_custom(data)


def remove_grupo(nome: str) -> None:
    data = _load_custom()
    data.get("grupos", {}).pop(nome, None)
    _save_custom(data)


def set_crypto_enabled(enabled: bool) -> None:
    data = _load_custom()
    data["crypto_enabled"] = enabled
    _save_custom(data)


def add_crypto_custom(ticker: str, nome: str) -> None:
    data = _load_custom()
    data.setdefault("crypto_custom", {})[ticker] = nome
    data["crypto_enabled"] = True
    _save_custom(data)


def reset_to_defaults() -> None:
    if CUSTOM_FILE.exists():
        CUSTOM_FILE.unlink()


def is_crypto_enabled() -> bool:
    return _load_custom().get("crypto_enabled", False)


def get_custom_summary() -> dict:
    data = _load_custom()
    return {
        "adicionados":   len(data.get("acoes", {})),
        "removidos":     len(data.get("removed", [])),
        "grupos_custom": len(data.get("grupos", {})),
        "crypto_enabled": data.get("crypto_enabled", False),
        "crypto_custom": len(data.get("crypto_custom", {})),
    }


# Backward-compatible module-level aliases
ACOES  = get_acoes()
GRUPOS = get_grupos()
