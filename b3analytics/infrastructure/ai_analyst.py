from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from b3analytics.infrastructure.macro import get_macro_context

_AI_API_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
logger = logging.getLogger(__name__)

_EMPTY_RESULT: dict = {
    "macro_score":          0,
    "macro_label":          "NEUTRO",
    "setup_alinhamento":    "SEM_SETUP",
    "alinhamento_explicacao": "",
    "catalistas":           [],
    "riscos":               [],
    "noticias":             [],
    "parecer_macro":        "",
    "parecer_integrado":    "",
    "confianca_analise":    0,
}


def _parse_response(text: str) -> dict:
    if not text.strip():
        return dict(_EMPTY_RESULT)

    # Strip markdown code fences
    for fence in ("```json", "```"):
        if fence in text:
            text = text.split(fence)[-1].split("```")[0].strip()
            break

    # Extract outermost JSON object
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    # First attempt: parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Falha ao parsear resposta de IA como JSON bruto")
        pass

    # Second attempt: sanitize literal control characters inside strings
    sanitized = re.sub(r'(?<!\\)[\n\r\t]', ' ', text)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        logger.warning("Falha ao parsear resposta de IA após sanitização")
        pass

    return dict(_EMPTY_RESULT)


def _system_prompt(max_searches: int) -> str:
    return (
        "Você é um analista financeiro especializado no mercado brasileiro (B3). "
        f"Você pode fazer no máximo {max_searches} busca(s) na web. "
        "Use-as com critério — priorize notícias recentes e fontes confiáveis. "
        "REGRAS DE FORMATO: responda SOMENTE com JSON puro, sem texto antes ou depois, "
        "strings em uma linha, sem quebras de linha internas. "
        "Use português brasileiro. Seja direto e objetivo."
    )


def _user_prompt(
    ticker:       str,
    nome:         str,
    setor:        str,
    setup:        dict | None,
    macro:        dict,
    max_searches: int = 3,
    sources:      list | None = None,
    analyst_data: dict | None = None,
) -> str:
    setup_ctx = "Nenhum setup técnico identificado."
    if setup:
        setup_ctx = json.dumps({
            "tipo":      setup.get("type"),
            "direcao":   setup.get("direction"),
            "confianca": setup.get("confidence"),
            "entrada":   setup.get("entry", {}).get("price"),
            "stop":      setup.get("stop", {}).get("price"),
            "rr_a1":     setup.get("targets", [{}])[0].get("rr") if setup.get("targets") else None,
            "rsi":       setup.get("indicators", {}).get("rsi"),
        }, ensure_ascii=False)

    comods = macro.get("commodities", {})

    analyst_ctx = ""
    if analyst_data:
        rec   = analyst_data.get("recommendation_key", "")
        mean  = analyst_data.get("recommendation_mean")
        n     = analyst_data.get("n_analysts")
        tgt   = analyst_data.get("target_mean")
        earn  = analyst_data.get("earnings_date", "")
        ex_d  = analyst_data.get("ex_dividend_date", "")
        dr    = analyst_data.get("dividend_rate")
        parts = []
        if rec:   parts.append(f"Recomendação yfinance: {rec} (média: {mean}, {n} analistas)")
        if tgt:   parts.append(f"Preço-alvo médio yfinance: R$ {tgt:.2f}")
        if earn:  parts.append(f"Próximo resultado: {earn}")
        if ex_d:  parts.append(f"Próxima data ex-dividendo: {ex_d}")
        if dr:    parts.append(f"Dividendo anual/ação (yfinance): R$ {dr:.4f}")
        if parts:
            analyst_ctx = "\n## DADOS DE ANALISTAS (yfinance)\n" + "\n".join(parts) + "\n"

    if max_searches == 1:
        instrucao = "Faça 1 busca sobre notícias recentes do ativo (últimos 7 dias)."
        campos    = "catalistas máx 2, riscos máx 2, noticias máx 3"
    elif max_searches <= 3:
        instrucao = "Faça até 3 buscas: 1) notícias do ativo, 2) setor no Brasil, 3) macro Brasil."
        campos    = "catalistas máx 4, riscos máx 4, noticias máx 5"
    else:
        instrucao = "Faça até 5 buscas: ativo, setor, macro Brasil, cenário global, e recomendações de analistas."
        campos    = "catalistas máx 6, riscos máx 6, noticias máx 8"

    fontes_str = ""
    if sources:
        lista = "\n".join(f"   - {s}" for s in sources[:12])
        fontes_str = f"\nFONTES PRIORITÁRIAS:\n{lista}\n"

    return f"""Analise o ativo {ticker} ({nome}) — Setor: {setor}.

## ANÁLISE TÉCNICA
{setup_ctx}

## CENÁRIO MACRO
SELIC: {macro.get('selic_pct','N/D')}% | IPCA 12m: {macro.get('ipca_12m_pct','N/D')}% | USD/BRL: {macro.get('usd_brl','N/D')} | Fed: {(macro.get('juros_eua') or {}).get('fed_funds','N/D')}% | Brent: {comods.get('petroleo_brent','N/D')} | S&P500: {comods.get('sp500','N/D')} | VIX: {comods.get('vix','N/D')} | Ibov: {comods.get('ibov','N/D')}
{analyst_ctx}
## TAREFA
{instrucao}
{fontes_str}
Campos: {campos}

Retorne APENAS JSON puro (strings sem quebra de linha, sem texto fora do JSON):
{{"ticker":"{ticker}","macro_score":<-100 a +100>,"macro_label":"FAVORÁVEL|NEUTRO|DESFAVORÁVEL","setup_alinhamento":"ALINHADO|CONFLITO|NEUTRO|SEM_SETUP","alinhamento_explicacao":"<1 frase>","catalistas":[{{"fator":"<texto>","impacto":"ALTO|MÉDIO|BAIXO","fonte":"<site>","detalhe":"<1-2 frases>","links":["<URL ou vazio>"]}}],"riscos":[{{"fator":"<texto>","impacto":"ALTO|MÉDIO|BAIXO","fonte":"<site>","detalhe":"<contexto>","links":["<URL ou vazio>"]}}],"noticias":[{{"titulo":"<título>","sentimento":"POSITIVO|NEGATIVO|NEUTRO","fonte":"<site>","url":"<URL completa ou vazio>","resumo":"<1 frase>"}}],"consenso_analistas":{{"visao_geral":"<parágrafo>","casas_favoraveis":["<XP>"],"casas_contrarias":["<casa>"],"preco_alvo_estimado":<número R$ ou null>,"perspectiva_ano":"<perspectiva 12 meses>","fonte":"<onde encontrou>"}},"perspectiva_longo_prazo":"<2-3 frases>","proximos_dividendos":{{"previsao":"<estimativa>","base":"<como chegou>"}},"proximos_resultados":{{"data_estimada":"<data dd/mm/aaaa ou trimestre>","expectativa":"<o que o mercado espera>","fonte":"<fonte>"}},"ativos_correlacionados":[{{"ticker":"<TICKER.SA>","relacao":"<como se correlaciona>","correlacao_tipo":"POSITIVA|NEGATIVA|NEUTRA"}}],"parecer_macro":"<2-3 frases>","parecer_integrado":"<2-3 frases>","confianca_analise":<0-100>}}"""


def _call_local_agent(
    prompt:     str,
    system:     str = "",
    max_tokens: int = 1500,
) -> str:
    import shutil
    import subprocess
    if not shutil.which("claude"):
        raise RuntimeError("Motor IA local não encontrado")

    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    r = subprocess.run(
        ["claude", "--print"],
        input=full_prompt,
        capture_output=True, text=True, timeout=240,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"Motor IA local falhou (código {r.returncode}): {r.stderr[:300]}"
        )
    return r.stdout.strip()


def _prompt_without_web(prompt: str) -> str:
    return (
        prompt
        .replace(
            "Faça até 3 buscas: 1) notícias do ativo, 2) setor no Brasil, 3) macro Brasil.",
            "Use seu conhecimento e os dados fornecidos sobre: 1) o ativo, 2) o setor no Brasil, 3) macro Brasil.",
        )
        .replace(
            "Faça 1 busca sobre notícias recentes do ativo (últimos 7 dias).",
            "Use seu conhecimento e os dados fornecidos sobre o ativo.",
        )
        .replace(
            "Faça até 5 buscas: ativo, setor, macro Brasil, cenário global, e recomendações de analistas.",
            "Use seu conhecimento e os dados fornecidos sobre: ativo, setor, macro Brasil, cenário global e recomendações de analistas.",
        )
    )


def test_local_agent_connection() -> tuple[bool, str]:
    try:
        resposta = _call_local_agent(
            prompt="Responda apenas: CONECTADO",
            system="Assistente de teste.",
            max_tokens=20,
        )
        if resposta.strip():
            return True, f"Motor IA local respondeu: {resposta.strip()[:50]}"
        return False, "Resposta vazia"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        logger.warning("Erro inesperado ao testar conexão do motor IA local")
        return False, f"Erro inesperado: {e}"


def _analyze_via_local_agent(
    ticker:       str,
    nome:         str,
    setor:        str,
    setup:        dict | None,
    macro:        dict | None = None,
    sources:      list | None = None,
    analyst_data: dict | None = None,
) -> dict:
    if macro is None:
        macro = get_macro_context()
    system = _system_prompt(3)
    prompt = _user_prompt(
        ticker, nome, setor, setup, macro or {},
        max_searches=3, sources=sources, analyst_data=analyst_data,
    )
    prompt = _prompt_without_web(prompt)
    text = _call_local_agent(prompt, system=system, max_tokens=1500)
    return _parse_response(text)


def _call_openai(model: str, api_key: str, system: str, prompt: str, max_tokens: int) -> dict:
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _prompt_without_web(prompt)},
        ],
    }).encode()
    req = urllib.request.Request(
        _OPENAI_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.reason}") from e

    text = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return _parse_response(text)


def _call_google_gemini(model: str, api_key: str, system: str, prompt: str, max_tokens: int) -> dict:
    payload = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": _prompt_without_web(prompt)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }).encode()
    url_model = urllib.parse.quote(model, safe="")
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{url_model}:generateContent?key={api_key}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.reason}") from e

    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts).strip()
    return _parse_response(text)


def analyze(
    ticker:          str,
    nome:            str,
    setor:           str,
    setup:           dict | None,
    api_key:         str,
    model:           str | None = None,
    macro_preloaded: dict | None = None,
    preset:          str | None = None,
    sources:         list | None = None,
    analyst_data:    dict | None = None,
    provider:        str = "anthropic_api",
) -> dict:
    from b3analytics.infrastructure.ai_config import AI_PRESETS, get_model, get_preset
    _model  = model  or get_model(provider)
    _preset = preset or get_preset(provider)
    cfg     = AI_PRESETS.get(_preset, AI_PRESETS["padrão"])
    macro   = macro_preloaded or get_macro_context()
    system  = _system_prompt(cfg["max_uses"])
    prompt  = _user_prompt(
        ticker, nome, setor, setup, macro,
        max_searches=cfg["max_uses"],
        sources=sources,
        analyst_data=analyst_data,
    )

    if provider == "openai_api":
        return _call_openai(_model, api_key, system, prompt, cfg["max_tokens"])

    if provider == "google_gemini":
        return _call_google_gemini(_model, api_key, system, prompt, cfg["max_tokens"])

    payload = json.dumps({
        "model":      _model,
        "max_tokens": cfg["max_tokens"],
        "system":     system,
        "tools": [{
            "type":     "web_search_20250305",
            "name":     "web_search",
            "max_uses": cfg["max_uses"],
        }],
        "messages": [{"role": "user",
                      "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        _AI_API_URL,
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "X-API-Key":         api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    "web-search-2025-03-05",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.reason}") from e

    content = body.get("content", [])
    text    = "\n".join(b["text"] for b in content if b.get("type") == "text").strip()
    return _parse_response(text)


def get_or_analyze(
    ticker:  str,
    nome:    str,
    setor:   str,
    setup:   dict | None,
    api_key: str | None,
    model:   str | None = None,
    macro:   dict | None = None,
    preset:  str | None = None,
    ttl:     int | None = None,
    force:   bool = False,
) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    from b3analytics.infrastructure.ai_cache import get_cached, save_cache
    from b3analytics.infrastructure.ai_config import (
        get_active_provider,
        get_all_sources,
        get_sources_enabled,
        get_ttl,
        is_local_agent_available,
    )
    from b3analytics.infrastructure.fetcher import get_analyst_data

    _ttl      = ttl if ttl is not None else get_ttl()
    _provider = get_active_provider()
    sources   = get_all_sources() if get_sources_enabled() else None

    if not force:
        cached = get_cached(ticker, ttl=_ttl)
        if cached:
            return cached

    # Fetch macro and analyst data in parallel
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_macro   = ex.submit(get_macro_context) if macro is None else None
        f_analyst = ex.submit(get_analyst_data, ticker)
        _macro        = f_macro.result()   if f_macro   else macro
        _analyst_data = f_analyst.result()

    if api_key is not None and _provider in {"anthropic_api", "openai_api", "google_gemini"}:
        resultado = analyze(
            ticker, nome, setor, setup, api_key,
            model=model, macro_preloaded=_macro, preset=preset,
            sources=sources, analyst_data=_analyst_data,
            provider=_provider,
        )
        resultado["_provider"] = _provider
    elif _provider == "claude_code" or api_key is None:
        if not is_local_agent_available():
            return {
                **_EMPTY_RESULT,
                "parecer_macro":     "Motor IA local não disponível.",
                "parecer_integrado": "Configure o motor IA local para usar esta função.",
            }
        resultado = _analyze_via_local_agent(
            ticker, nome, setor, setup, _macro,
            sources=sources, analyst_data=_analyst_data,
        )
        resultado["_provider"] = "claude_code"
    else:
        return dict(_EMPTY_RESULT)

    resultado["_analyst_yf"] = _analyst_data
    save_cache(ticker, resultado)
    return resultado
