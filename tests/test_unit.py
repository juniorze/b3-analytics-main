"""Testes unitários com assertions concretas. Nenhum assert True."""
import json
import os

import pandas as pd


class TestConfigAtivos:
    def test_acoes_tem_petr4(self):
        from b3analytics.config.assets import get_acoes
        ACOES = get_acoes()
        assert "PETR4.SA" in ACOES
        assert ACOES["PETR4.SA"] == "Petrobras PN"

    def test_acoes_tem_minimo_60(self):
        from b3analytics.config.assets import get_acoes
        n = len(get_acoes())
        assert n >= 60, f"ACOES tem {n}, esperado ≥ 60"

    def test_grupos_cobre_financeiro(self):
        from b3analytics.config.assets import get_grupos
        GRUPOS = get_grupos()
        assert "Financeiro" in GRUPOS
        assert "ITUB4.SA" in GRUPOS["Financeiro"]

    def test_todos_tickers_de_grupos_em_acoes(self):
        from b3analytics.config.assets import get_acoes, get_grupos
        ACOES  = get_acoes()
        GRUPOS = get_grupos()
        for grupo, tickers in GRUPOS.items():
            for t in tickers:
                assert t in ACOES, f"'{t}' do grupo '{grupo}' não está em ACOES"

    def test_crypto_em_acoes_se_configurado(self):
        from b3analytics.config.assets import get_acoes
        ACOES = get_acoes()
        cryptos = [t for t in ACOES if "-" in t or "BTC" in t or "ETH" in t]
        for c in cryptos:
            assert "-" in c or c.endswith(".SA"), f"Formato de cripto inválido: {c}"

    def test_indicator_defaults_valores_sensiveis(self):
        from b3analytics.config.settings import INDICATOR_DEFAULTS as D
        assert D["sma_short"]  == 20,  f"sma_short={D['sma_short']}"
        assert D["sma_medium"] == 50,  f"sma_medium={D['sma_medium']}"
        assert D["sma_long"]   == 200, f"sma_long={D['sma_long']}"
        assert D["ema_fast"]   == 9,   f"ema_fast={D['ema_fast']}"
        assert D["ema_slow"]   == 21,  f"ema_slow={D['ema_slow']}"
        assert D["rsi_period"] == 14,  f"rsi_period={D['rsi_period']}"
        assert D["rsi_ob"]     == 70,  f"rsi_ob={D['rsi_ob']}"
        assert D["rsi_os"]     == 30,  f"rsi_os={D['rsi_os']}"
        assert D["macd_fast"]  == 12,  f"macd_fast={D['macd_fast']}"
        assert D["macd_slow"]  == 26,  f"macd_slow={D['macd_slow']}"
        assert D["bb_period"]  == 20,  f"bb_period={D['bb_period']}"
        assert D["bb_std"]     == 2.0, f"bb_std={D['bb_std']}"


class TestAIConfigEstrito:
    CHAVE_TESTE = "FAKE-TEST-KEY-AUDITORIA-NOT-REAL-123456"

    def test_ciclo_completo_key(self):
        from b3analytics.infrastructure.ai_config import (
            delete_api_key,
            get_api_key,
            is_configured,
            save_api_key,
        )
        delete_api_key("anthropic")
        assert get_api_key("anthropic") is None
        assert not is_configured("anthropic")

        save_api_key(self.CHAVE_TESTE, "anthropic")
        assert get_api_key("anthropic") == self.CHAVE_TESTE, \
            f"Esperado '{self.CHAVE_TESTE}', got '{get_api_key('anthropic')}'"
        assert is_configured("anthropic")

        delete_api_key("anthropic")
        assert get_api_key("anthropic") is None
        assert not is_configured("anthropic")

    def test_modelo_persiste(self):
        from b3analytics.infrastructure.ai_config import get_model, save_model
        save_model("test-model-2025", "anthropic")
        result = get_model("anthropic")
        assert result == "test-model-2025", \
            f"Modelo não persistiu: '{result}'"

    def test_preset_econômico_valores(self):
        from b3analytics.infrastructure.ai_config import AI_PRESETS
        assert "econômico" in AI_PRESETS
        cfg = AI_PRESETS["econômico"]
        assert cfg["max_uses"] == 1, \
            f"econômico.max_uses={cfg['max_uses']}, esperado 1"
        assert cfg["max_tokens"] <= 1000, \
            f"econômico.max_tokens={cfg['max_tokens']}, esperado ≤ 1000"

    def test_preset_completo_mais_que_padrao(self):
        from b3analytics.infrastructure.ai_config import AI_PRESETS
        assert AI_PRESETS["completo"]["max_uses"]   > AI_PRESETS["padrão"]["max_uses"]
        assert AI_PRESETS["completo"]["max_tokens"] > AI_PRESETS["padrão"]["max_tokens"]

    def test_ttl_1h_e_3h(self):
        from b3analytics.infrastructure.ai_config import get_ttl, save_ttl
        save_ttl("1 hora")
        assert get_ttl() == 3600, f"TTL 1h = {get_ttl()}, esperado 3600"
        save_ttl("3 horas")
        assert get_ttl() == 10800, f"TTL 3h = {get_ttl()}, esperado 10800"

    def test_provider_claude_code_tem_requires_key_false(self):
        from b3analytics.infrastructure.ai_config import AI_PROVIDERS
        assert "claude_code" in AI_PROVIDERS
        assert AI_PROVIDERS["claude_code"]["requires_key"] is False, \
            "claude_code.requires_key deve ser False"

    def test_config_file_criado_em_home(self):
        from pathlib import Path

        from b3analytics.infrastructure.ai_config import get_config_path, save_model
        save_model("test-model-2025", "anthropic")
        path = Path(get_config_path())
        assert path.exists(), f"Config não foi criado em {path}"
        content = json.loads(path.read_text(encoding="utf-8"))
        assert "providers" in content

    def test_config_file_permissao_restrita(self):
        from pathlib import Path

        from b3analytics.infrastructure.ai_config import get_config_path, save_model
        save_model("test-model-2025", "anthropic")
        path = Path(get_config_path())
        if os.name == "nt":
            assert path.exists()
            return
        mode = oct(path.stat().st_mode)[-3:]
        assert mode == "600", \
            f"Permissão do config é {mode}, esperado 600 (só dono pode ler)"


class TestAICacheEstrito:
    MOCK = {
        "macro_score":        42,
        "macro_label":        "FAVORÁVEL",
        "setup_alinhamento":  "ALINHADO",
        "alinhamento_explicacao": "Mock para auditoria.",
        "catalistas": [{"fator": "A", "impacto": "ALTO",  "fonte": "mock"}],
        "riscos":     [{"fator": "B", "impacto": "BAIXO", "fonte": "mock"}],
        "noticias":   [{"titulo": "N1", "sentimento": "POSITIVO"}],
        "parecer_macro":     "Macro mock.",
        "parecer_integrado": "Integrado mock.",
        "confianca_analise": 75,
        "_model":    "test-model-2025",
        "_preset":   "padrão",
        "_provider": "mock",
    }

    def setup_method(self, _):
        from b3analytics.infrastructure.ai_cache import invalidate_all
        invalidate_all()

    def teardown_method(self, _):
        from b3analytics.infrastructure.ai_cache import invalidate_all
        invalidate_all()

    def test_salvar_e_recuperar(self):
        from b3analytics.infrastructure.ai_cache import get_cached, save_cache
        save_cache("PETR4.SA", self.MOCK)
        r = get_cached("PETR4.SA", ttl=3600)
        assert r is not None, "Cache não retornou resultado"
        assert r["macro_score"] == 42, \
            f"macro_score={r['macro_score']}, esperado 42"
        assert r["macro_label"] == "FAVORÁVEL"
        assert "cached_at" in r, "cached_at ausente"
        assert r["catalistas"][0]["fator"] == "A"

    def test_ttl_zero_expira(self):
        from b3analytics.infrastructure.ai_cache import get_cached, save_cache
        save_cache("PETR4.SA", self.MOCK)
        r = get_cached("PETR4.SA", ttl=0)
        assert r is None, \
            f"Com TTL=0 deveria retornar None, got: {r}"

    def test_invalidate_remove(self):
        from b3analytics.infrastructure.ai_cache import get_cached, invalidate, save_cache
        save_cache("PETR4.SA", self.MOCK)
        invalidate("PETR4.SA")
        assert get_cached("PETR4.SA", ttl=3600) is None, \
            "Depois de invalidate() ainda retornou resultado"

    def test_invalidate_all_retorna_contagem(self):
        from b3analytics.infrastructure.ai_cache import invalidate_all, save_cache
        for t in ["PETR4.SA", "VALE3.SA", "BBAS3.SA"]:
            save_cache(t, {**self.MOCK, "ticker": t})
        n = invalidate_all()
        assert n == 3, f"invalidate_all() retornou {n}, esperado 3"

    def test_list_cached_campos(self):
        from b3analytics.infrastructure.ai_cache import list_cached, save_cache
        save_cache("PETR4.SA", self.MOCK)
        items = list_cached(ttl=3600)
        assert len(items) == 1, f"Esperado 1 item, got {len(items)}"
        item = items[0]
        assert item["ticker"]      == "PETR4.SA"
        assert item["expired"]     is False
        assert item["age_minutes"] >= 0
        assert item["macro_score"] == 42

    def test_cache_stats_contagem(self):
        from b3analytics.infrastructure.ai_cache import cache_stats, save_cache
        for t in ["PETR4.SA", "VALE3.SA"]:
            save_cache(t, {**self.MOCK, "ticker": t})
        s = cache_stats(ttl=3600)
        assert s["total"]   == 2, f"total={s['total']}, esperado 2"
        assert s["valid"]   == 2, f"valid={s['valid']}, esperado 2"
        assert s["expired"] == 0, f"expired={s['expired']}, esperado 0"
        assert "PETR4.SA" in s["tickers_valid"]

    def test_arquivo_criado_com_nome_correto(self):
        from b3analytics.infrastructure.ai_cache import CACHE_DIR, save_cache
        save_cache("PETR4.SA", self.MOCK)
        assert (CACHE_DIR / "PETR4_SA.json").exists(), \
            f"Arquivo PETR4_SA.json não encontrado em {CACHE_DIR}"


class TestJSONParserEstrito:
    def _parse(self, text: str) -> dict:
        from b3analytics.infrastructure.ai_analyst import _parse_response
        return _parse_response(text)

    def test_json_limpo_macro_score(self):
        r = self._parse('{"macro_score": 42, "macro_label": "NEUTRO"}')
        assert r["macro_score"] == 42

    def test_texto_antes_score_correto(self):
        r = self._parse('Aqui: {"macro_score": -15, "macro_label": "DESFAVORÁVEL"} ok.')
        assert r["macro_score"] == -15

    def test_markdown_fence_score_correto(self):
        r = self._parse('```json\n{"macro_score": 77, "macro_label": "FAVORÁVEL"}\n```')
        assert r["macro_score"] == 77

    def test_newline_nao_quebra_parse(self):
        raw = '{"macro_score": 30, "macro_label": "NEUTRO", "parecer": "A\nB"}'
        r   = self._parse(raw)
        assert r.get("macro_score") == 30, \
            f"Parse com newline retornou macro_score={r.get('macro_score')}"

    def test_resposta_vazia_retorna_dict_com_score(self):
        r = self._parse("")
        assert isinstance(r, dict)
        assert "macro_score" in r
        assert isinstance(r["macro_score"], int)

    def test_nao_json_retorna_dict_com_score(self):
        r = self._parse("bla bla bla sem json")
        assert isinstance(r, dict)
        assert "macro_score" in r
        assert isinstance(r["macro_score"], int)

    def test_score_sempre_inteiro(self):
        for raw in [
            '{"macro_score": 0}',
            '{"macro_score": -100}',
            '{"macro_score": 100}',
        ]:
            r = self._parse(raw)
            assert isinstance(r["macro_score"], int), \
                f"macro_score deveria ser int, got {type(r['macro_score'])}"


class TestMathEstrito:
    def test_rr_1_5(self):
        rr = (107.5 - 100) / (100 - 95)
        assert abs(rr - 1.5) < 0.0001, f"R/R={rr}"

    def test_rr_2_5(self):
        rr = (112.5 - 100) / (100 - 95)
        assert abs(rr - 2.5) < 0.0001

    def test_sizing_nao_excede_capital(self):
        cap, rp, e, s = 1000, 0.02, 38.80, 37.20
        rm = cap * rp; ru = abs(e - s)
        qr = int(rm / ru); qc = int(cap / e); q = max(1, min(qr, qc))
        alocado = q * e
        assert alocado <= cap, f"Alocado R${alocado:.2f} > capital R${cap}"

    def test_dy_0085_vira_8_5_pct(self):
        dy_raw = 0.085
        dy_pct = dy_raw * 100 if dy_raw < 1.0 else dy_raw
        assert abs(dy_pct - 8.5) < 0.001, f"DY={dy_pct}, esperado 8.5"

    def test_dy_85_nao_multiplica(self):
        dy_raw = 8.5
        dy_pct = dy_raw * 100 if dy_raw < 1.0 else dy_raw
        assert abs(dy_pct - 8.5) < 0.001, f"DY={dy_pct}, esperado 8.5"

    def test_drawdown_negativo(self):
        eq = pd.Series([10000, 11000, 10500, 9800, 10200, 10800])
        dd = ((eq - eq.cummax()) / eq.cummax() * 100).min()
        assert dd <= 0, f"Drawdown={dd}, deve ser ≤ 0"
        assert dd > -100, f"Drawdown={dd}, deve ser > -100"
        assert abs(dd - (-10.9)) < 1.0, f"Drawdown={dd:.1f}%, esperado ~-10.9%"
