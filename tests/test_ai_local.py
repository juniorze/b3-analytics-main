"""
Testes do motor IA local — verificam que o agente REALMENTE responde e o dado é válido.
Skipa automaticamente se o motor não estiver no PATH (skip autorizado).
"""
import shutil
import subprocess
import time

import pytest

LOCAL_AGENT_OK = shutil.which("claude") is not None

pytestmark = pytest.mark.skipif(
    not LOCAL_AGENT_OK,
    reason="motor IA local não encontrado"
)


class TestAILocalReal:
    def test_version_tem_numero(self):
        r = subprocess.run(["claude", "--version"],
                           capture_output=True, text=True, timeout=10)
        assert r.returncode == 0, f"Saiu com {r.returncode}: {r.stderr}"
        saida = r.stdout.strip() + r.stderr.strip()
        import re
        assert re.search(r"\d+\.\d+", saida), \
            f"Versão sem número: '{saida}'"
        print(f"\n  versão: {saida}")

    def test_resposta_nao_e_vazia(self):
        """Motor IA local deve responder algo para um prompt simples."""
        r = subprocess.run(
            ["claude", "--print"],
            input="Diga apenas: TESTE_OK",
            capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, \
            f"Motor IA local retornou código {r.returncode}: {r.stderr[:300]}"
        resposta = r.stdout.strip()
        assert len(resposta) > 0, "Resposta do motor IA local está vazia"
        print(f"\n  Resposta: '{resposta[:80]}'")

    def test_resposta_json_valida(self):
        """Motor IA local deve conseguir retornar JSON válido quando pedido."""
        from b3analytics.infrastructure.ai_analyst import _call_local_agent, _parse_response

        resposta = _call_local_agent(
            prompt=(
                'Retorne APENAS este JSON sem nenhum texto: '
                '{"status": "ok", "numero": 99, "lista": [1, 2, 3]}'
            ),
            system=(
                "Você é um gerador de JSON. "
                "Retorne APENAS o JSON pedido, sem texto adicional, "
                "sem markdown, sem explicação."
            ),
            max_tokens=100,
        )
        assert resposta.strip(), "Resposta JSON vazia"

        parsed = _parse_response(resposta)
        assert isinstance(parsed, dict), \
            f"Resposta não parseou como dict: '{resposta[:200]}'"
        assert parsed.get("numero") == 99 or parsed.get("status") == "ok", \
            f"JSON não tem campos esperados: {parsed}"

    @pytest.mark.timeout(300)
    def test_analise_petr4_score_em_range(self):
        """Análise real de PETR4 deve retornar score entre -100 e 100."""
        from b3analytics.config.assets import get_acoes
        from b3analytics.infrastructure.ai_analyst import get_or_analyze
        from b3analytics.infrastructure.ai_cache import invalidate
        from b3analytics.infrastructure.ai_config import save_active_provider
        from b3analytics.infrastructure.fetcher import _fetch_one

        save_active_provider("claude_code")
        invalidate("PETR4.SA")

        _, df = _fetch_one("PETR4.SA", "3mo")
        assert df is not None, "Não conseguiu buscar dados de PETR4"

        t0 = time.time()
        resultado = get_or_analyze(
            ticker  = "PETR4.SA",
            nome    = get_acoes()["PETR4.SA"],
            setor   = "Petróleo",
            setup   = None,
            api_key = None,
            force   = True,
        )
        elapsed = time.time() - t0

        assert resultado is not None, \
            "get_or_analyze retornou None — motor IA local falhou silenciosamente"
        assert isinstance(resultado, dict), \
            f"Resultado não é dict: {type(resultado)}"
        assert "macro_score" in resultado, \
            f"'macro_score' ausente. Campos: {list(resultado.keys())}"

        score = resultado["macro_score"]
        assert isinstance(score, int), \
            f"macro_score deve ser int, got {type(score)}: {score}"
        assert -100 <= score <= 100, \
            f"macro_score={score} fora do range -100..100"
        assert resultado.get("macro_label") in ("FAVORÁVEL", "NEUTRO", "DESFAVORÁVEL"), \
            f"macro_label inválido: '{resultado.get('macro_label')}'"

        print(f"\n  PETR4: score={score:+d} label={resultado['macro_label']} "
              f"em {elapsed:.1f}s")

    def test_resultado_foi_cacheado(self):
        """Após análise, resultado deve estar no cache em disco."""
        from b3analytics.infrastructure.ai_cache import get_cached
        from b3analytics.infrastructure.ai_config import get_ttl

        cached = get_cached("PETR4.SA", ttl=get_ttl())
        assert cached is not None, \
            "Resultado não foi cacheado após análise — save_cache não chamado"
        assert cached.get("_provider") == "claude_code", \
            f"_provider='{cached.get('_provider')}', esperado 'claude_code'"
        assert "cached_at" in cached

    @pytest.mark.timeout(300)
    def test_segunda_chamada_usa_cache(self):
        """Segunda chamada deve ser < 1.5s (cache hit, sem acionar motor)."""
        from b3analytics.config.assets import get_acoes
        from b3analytics.infrastructure.ai_analyst import get_or_analyze

        t0 = time.time()
        r  = get_or_analyze("PETR4.SA", get_acoes()["PETR4.SA"],
                             "Petróleo", None, None, force=False)
        elapsed = time.time() - t0

        assert r is not None, "Cache hit retornou None"
        assert elapsed < 1.5, \
            f"Cache hit demorou {elapsed:.2f}s (esperado < 1.5s)"

    def test_connection_test_retorna_bool_e_msg(self):
        from b3analytics.infrastructure.ai_analyst import test_local_agent_connection
        ok, msg = test_local_agent_connection()
        assert isinstance(ok, bool),  f"ok deve ser bool, got {type(ok)}"
        assert isinstance(msg, str),  f"msg deve ser str, got {type(msg)}"
        assert len(msg) > 0,          "msg está vazia"
        assert ok is True,            f"Conexão falhou: {msg}"
        print(f"\n  Conexão: {msg}")

    def test_info_retorna_dict_com_available(self):
        from b3analytics.infrastructure.ai_config import get_local_agent_info
        info = get_local_agent_info()
        assert isinstance(info, dict)
        assert "available" in info
        assert info["available"] is True
        assert "version" in info, f"'version' ausente: {info}"
        print(f"\n  Info: {info}")
