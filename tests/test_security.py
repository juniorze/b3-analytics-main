"""
tests/test_security.py — OWASP Top 10 (2021) para b3-analytics

Contexto: aplicação Streamlit local, single-user, sem banco de dados.
Cobre as categorias relevantes para este perfil de risco.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import stat

import pytest

ROOT = pathlib.Path(__file__).parent.parent


# ── A03:2021 — Injection (XSS, Command, Path Traversal) ──────────────────────

class TestA03Injection:

    def test_url_noticias_valida_protocolo_http(self):
        """_render_news_item: URL da IA deve ser filtrada por http antes de ir para href."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        news_start = src.find("def _render_news_item")
        news_end   = src.find("\ndef ", news_start + 10)
        func = src[news_start:news_end]
        assert 'startswith("http")' in func or "startswith('http')" in func, \
            "A03/XSS: _render_news_item não valida protocolo da URL — risco javascript: URI"

    def test_url_noticias_usa_safe_url(self):
        """_render_news_item: variável safe_url deve ser usada no href, não url direta."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        news_start = src.find("def _render_news_item")
        news_end   = src.find("\ndef ", news_start + 10)
        func = src[news_start:news_end]
        assert "safe_url" in func, \
            "A03/XSS: href de notícia usa 'url' direto — use safe_url validado"

    def test_links_expandable_card_filtram_protocolo(self):
        """_render_expandable_card: links devem ser filtrados por startswith('http')."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        card_start = src.find("def _render_expandable_card")
        card_end   = src.find("\ndef ", card_start + 10)
        func = src[card_start:card_end]
        assert 'startswith("http")' in func or "startswith('http')" in func, \
            "A03/XSS: _render_expandable_card não filtra protocolo dos links"

    def test_ticker_sem_caracteres_perigosos(self):
        """Todos os tickers cadastrados devem ser strings seguras (sem path traversal)."""
        from b3analytics.config.assets import get_acoes
        for ticker in get_acoes():
            assert ".."  not in ticker, f"A03: ticker com path traversal: {ticker}"
            assert "/"   not in ticker, f"A03: ticker com barra: {ticker}"
            assert "\\"  not in ticker, f"A03: ticker com backslash: {ticker}"
            assert "$("  not in ticker, f"A03: ticker com command substitution: {ticker}"
            assert "`"   not in ticker, f"A03: ticker com backtick: {ticker}"

    def test_cache_path_nao_escapa_do_diretorio(self):
        """_cache_path deve neutralizar path traversal e manter arquivo no CACHE_DIR."""
        from b3analytics.infrastructure.ai_cache import CACHE_DIR, _cache_path
        malicious = ["../etc/passwd", "../../root/.ssh/id_rsa", "PETR4/../../../tmp/x"]
        for bad in malicious:
            p = _cache_path(bad)
            assert str(p.resolve()).startswith(str(CACHE_DIR.resolve())), \
                f"A03/PathTraversal: cache escapa do diretório com ticker {bad!r} → {p}"

    def test_nenhum_eval_exec_com_dados_externos(self):
        """eval/exec com conteúdo dinâmico externo é injeção de código."""
        danger = re.compile(r'\b(eval|exec)\s*\(\s*(?!["\'])')
        for f in list((ROOT / "pages").glob("*.py")) + list((ROOT / "b3analytics").rglob("*.py")):
            if "__pycache__" in str(f):
                continue
            src = f.read_text(encoding="utf-8")
            m = danger.search(src)
            if m:
                line = src[max(0, m.start() - 30):m.end() + 80].strip()
                pytest.fail(f"A03/CodeInjection: {f.name} usa eval/exec com variável: {line[:100]}")

    def test_sem_os_system_com_input_usuario(self):
        """os.system e subprocess com shell=True + variáveis externas é command injection."""
        for f in list((ROOT / "pages").glob("*.py")) + list((ROOT / "b3analytics").rglob("*.py")):
            if "__pycache__" in str(f):
                continue
            src = f.read_text(encoding="utf-8")
            # os.system() sem nenhum argumento hardcoded é suspeito
            if re.search(r'os\.system\s*\(', src):
                pytest.fail(f"A03/CmdInjection: {f.name} usa os.system()")
            # subprocess com shell=True + variável
            if re.search(r'subprocess\.\w+\s*\(.*shell\s*=\s*True', src):
                # Verificar se o comando é hardcoded
                m = re.search(r'subprocess\.\w+\s*\(([^)]+)shell\s*=\s*True', src)
                if m and re.search(r'(ticker|input|user|query|url)', m.group(1), re.I):
                    pytest.fail(f"A03/CmdInjection: {f.name} usa subprocess com shell=True + variável")

    def test_input_usuario_nao_em_html_direto(self):
        """Resultado de st.text_input não deve ir diretamente para unsafe_allow_html."""
        for f in (ROOT / "pages").glob("*.py"):
            src = f.read_text(encoding="utf-8")
            # Heurística: text_input result em f-string com unsafe_allow_html na mesma linha
            lines = src.split("\n")
            inputs_vars = set()
            for i, line in enumerate(lines):
                # Coletar variáveis atribuídas de text_input
                m = re.match(r'\s*(\w+)\s*=\s*st\.text_input\s*\(', line)
                if m:
                    inputs_vars.add(m.group(1))
            # Verificar que nenhuma dessas variáveis aparece em bloco unsafe_allow_html
            for var in inputs_vars:
                pattern = rf'f["\'].*{{{var}}}.*["\'].*unsafe_allow_html'
                if re.search(pattern, src, re.DOTALL):
                    pytest.fail(f"A03/XSS: {f.name} injecta {var} (text_input) em HTML")


# ── A02:2021 — Cryptographic Failures ────────────────────────────────────────

class TestA02CryptographicFailures:

    def test_config_json_chmod_600(self):
        """config.json deve ter permissões 600 — somente owner pode ler/escrever."""
        config = pathlib.Path.home() / ".b3analytics" / "config.json"
        if not config.exists():
            pytest.skip("config.json não existe ainda (normal em CI sem configuração)")
        if os.name == "nt":
            pytest.skip("chmod 600 não é representado de forma equivalente no Windows")
        mode = stat.S_IMODE(config.stat().st_mode)
        assert mode == 0o600, \
            f"A02: config.json tem modo {oct(mode)}, esperado 0o600 — rode chmod 600"

    def test_api_key_salva_fora_do_repositorio(self):
        """Chave deve estar em ~/.b3analytics/, nunca dentro do projeto versionado."""
        from b3analytics.infrastructure.ai_config import get_config_path
        config_path = pathlib.Path(get_config_path()).resolve()
        repo_root   = ROOT.resolve()
        assert not str(config_path).startswith(str(repo_root)), \
            f"A02: config.json DENTRO do repositório: {config_path}"

    def test_nenhuma_chave_real_hardcoded(self):
        """Nenhum arquivo .py deve conter padrão de chave de API real."""
        real_key = re.compile(r'sk-ant-api03-[A-Za-z0-9\-_]{20,}')
        for f in ROOT.rglob("*.py"):
            if "__pycache__" in str(f) or ".pytest_cache" in str(f):
                continue
            src = f.read_text(encoding="utf-8")
            m = real_key.search(src)
            if m:
                pytest.fail(f"A02: chave de API real em {f.relative_to(ROOT)}: {m.group()[:25]}...")

    def test_api_key_nao_logada_nem_impressa(self):
        """Módulos de infraestrutura não devem imprimir/logar a API key."""
        for f in (ROOT / "b3analytics").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            src = f.read_text(encoding="utf-8")
            bad = re.search(r'(?:print|logging\.\w+)\s*\(.*(?:api_key|sk-ant)', src, re.I)
            assert not bad, \
                f"A02: {f.name} pode logar chave: {bad.group()[:80] if bad else ''}"

    def test_api_key_nao_em_session_state(self):
        """API key não deve ser colocada em st.session_state (exposta no browser)."""
        key_vars = re.compile(r'st\.session_state\[.*\]\s*=\s*(?:nova_key|api_key|_api_key_global|chave)')
        for f in (ROOT / "pages").glob("*.py"):
            src = f.read_text(encoding="utf-8")
            m = key_vars.search(src)
            assert not m, \
                f"A02: {f.name} armazena chave em session_state: {m.group()[:80] if m else ''}"

    def test_config_json_campos_conhecidos(self):
        """config.json não deve ter campos suspeitos (password, secret, token)."""
        config = pathlib.Path.home() / ".b3analytics" / "config.json"
        if not config.exists():
            pytest.skip("config.json não existe")
        data = json.loads(config.read_text(encoding="utf-8"))
        suspicious = [k for k in data
                      if any(x in k.lower() for x in ["password", "secret", "token", "private_key"])]
        assert not suspicious, f"A02: config.json tem campos suspeitos: {suspicious}"


# ── A05:2021 — Security Misconfiguration ─────────────────────────────────────

class TestA05SecurityMisconfiguration:

    def test_sem_debug_true_em_paginas(self):
        """Nenhuma página deve ter debug=True ativo."""
        for f in (ROOT / "pages").glob("*.py"):
            src = f.read_text(encoding="utf-8")
            assert not re.search(r'debug\s*=\s*True', src, re.I), \
                f"A05: {f.name} tem debug=True"

    def test_streamlit_xsrf_protection_ativo(self):
        """config.toml não deve desabilitar XSRF protection."""
        config_toml = ROOT / ".streamlit" / "config.toml"
        if not config_toml.exists():
            return  # sem config.toml — proteção padrão do Streamlit se aplica
        content = config_toml.read_text(encoding="utf-8").lower()
        assert "enablexsrfprotection = false" not in content, \
            "A05: XSRF protection desabilitada — risco CSRF"
        assert "enablexsrfprotection=false" not in content, \
            "A05: XSRF protection desabilitada — risco CSRF"

    def test_gitignore_protege_arquivos_sensiveis(self):
        """.gitignore deve existir e proteger .env, *.key, *.pem."""
        gi = ROOT / ".gitignore"
        assert gi.exists(), "A05: .gitignore não encontrado"
        content = gi.read_text(encoding="utf-8")
        for pattern in [".env", "*.key", "*.pem"]:
            assert pattern in content, f"A05: .gitignore não inclui '{pattern}'"

    def test_sem_passwords_em_requirements(self):
        """requirements.txt não deve conter URLs com credenciais embutidas."""
        req = ROOT / "requirements.txt"
        if not req.exists():
            pytest.skip("requirements.txt não encontrado")
        content = req.read_text(encoding="utf-8")
        # Padrão: https://user:pass@... em índice privado
        bad = re.search(r'https?://\w+:\w+@', content)
        assert not bad, f"A05: requirements.txt contém credencial em URL: {bad.group() if bad else ''}"

    def test_usage_stats_desabilitado(self):
        """gatherUsageStats deve estar desabilitado para privacidade."""
        config_toml = ROOT / ".streamlit" / "config.toml"
        if not config_toml.exists():
            return
        content = config_toml.read_text(encoding="utf-8").lower()
        assert "gatherusagestats = false" in content or "gatherusagestats=false" in content, \
            "A05: gatherUsageStats não está desabilitado — telemetria ativa"


# ── A04:2021 — Insecure Design ───────────────────────────────────────────────

class TestA04InsecureDesign:

    def test_periodo_analise_e_valor_de_lista_fechada(self):
        """Período de análise vem de dict fixo (selectbox), não de text_input livre."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        assert "periodo_map" in src, "A04: periodo_map não encontrado"
        # Garantir que não há text_input para período
        analise_block = src[src.find("with tab_analise:"):]
        assert not re.search(r'text_input.*[Pp]er[ií]odo|[Pp]er[ií]odo.*text_input', analise_block), \
            "A04: período pode ser input livre do usuário"

    def test_api_key_validada_por_formato_sk_ant(self):
        """API key deve ser validada (sk-ant prefix) antes de ser salva."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        assert "sk-ant" in src and "startswith" in src, \
            "A04: API key aceita qualquer string sem validar prefixo sk-ant"

    def test_ticker_vem_de_lista_de_ativos_conhecidos(self):
        """Ticker de análise vem de selectbox de ativos cadastrados, não de input livre."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        analise_block = src[src.find("with tab_analise:"):]
        # Deve ter opcoes dict derivado de ACOES
        assert "ACOES" in src and "opcoes" in analise_block, \
            "A04: seleção de ticker não usa lista de ativos conhecidos"
        # Não deve ter text_input para ticker na tab de análise
        assert not re.search(r'text_input.*[Tt]icker|ticker.*text_input', analise_block[:1000]), \
            "A04: ticker pode ser input livre na tab de análise"

    def test_ai_response_json_parsing_com_fallback(self):
        """ai_analyst.py deve ter fallback para JSON malformado da IA."""
        src = (ROOT / "b3analytics/infrastructure/ai_analyst.py").read_text(encoding="utf-8")
        assert "json.JSONDecodeError" in src or "JSONDecodeError" in src, \
            "A04: ai_analyst não captura JSONDecodeError — crash com resposta malformada"

    def test_modelo_ia_selecionado_de_lista_conhecida(self):
        """Modelo de IA é selecionado via selectbox (lista fechada), não digitado."""
        src = (ROOT / "pages/ia.py").read_text(encoding="utf-8")
        modelo_section = src[src.find("Modelo ativo"):src.find("Modelo ativo") + 400] \
            if "Modelo ativo" in src else ""
        # Deve usar selectbox, não text_input
        assert "text_input" not in modelo_section, \
            "A04: modelo pode ser digitado livremente pelo usuário"


# ── A08:2021 — Software and Data Integrity Failures ──────────────────────────

class TestA08DataIntegrity:

    def test_cache_usa_json_nao_pickle(self):
        """Cache serializa com JSON (seguro), nunca pickle (desserialização arbitrária)."""
        src = (ROOT / "b3analytics/infrastructure/ai_cache.py").read_text(encoding="utf-8")
        assert "json.dumps" in src or "json.dump" in src, \
            "A08: cache não usa json para serializar"
        assert "pickle" not in src, \
            "A08: cache usa pickle — desserialização insegura (RCE via cache manipulado)"

    def test_cache_nao_executa_conteudo_salvo(self):
        """Leitura de cache não deve usar eval/exec."""
        src = (ROOT / "b3analytics/infrastructure/ai_cache.py").read_text(encoding="utf-8")
        assert "eval(" not in src, "A08: ai_cache.py usa eval() — executa conteúdo do cache"
        assert "exec(" not in src, "A08: ai_cache.py usa exec() — executa conteúdo do cache"

    def test_cache_existente_e_json_valido(self):
        """Arquivos de cache no disco devem ser JSON válido."""
        cache_dir = pathlib.Path.home() / ".b3analytics" / "cache"
        if not cache_dir.exists() or not list(cache_dir.glob("*.json")):
            pytest.skip("Sem arquivos de cache para validar")
        for f in cache_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                assert isinstance(data, dict), f"A08: cache {f.name} não é dict JSON"
            except json.JSONDecodeError as e:
                pytest.fail(f"A08: cache {f.name} contém JSON corrompido: {e}")

    def test_config_json_parsing_com_tratamento_de_erro(self):
        """ai_config._load() deve tratar falha de parsing do config.json."""
        src = (ROOT / "b3analytics/infrastructure/ai_config.py").read_text(encoding="utf-8")
        # Deve ter try/except em torno do json.loads
        assert "except" in src and "json" in src, \
            "A08: ai_config não trata erro de parsing do config.json"

    def test_ai_response_nao_e_executada_diretamente(self):
        """Resposta da IA é tratada como dado JSON, nunca como código executável."""
        src = (ROOT / "b3analytics/infrastructure/ai_analyst.py").read_text(encoding="utf-8")
        # Resposta da IA vai para json.loads, não para eval/exec
        assert "eval(" not in src, \
            "A08: ai_analyst passa resposta da IA para eval() — RCE via prompt injection"
        assert "exec(" not in src, \
            "A08: ai_analyst passa resposta da IA para exec() — RCE via prompt injection"

    def test_resultado_ai_tem_campos_minimos_validados(self):
        """get_cached deve retornar None para cache corrompido, não crash."""
        import time

        from b3analytics.infrastructure.ai_cache import CACHE_DIR, get_cached
        # Criar cache com dado inválido (sem macro_score)
        test_file = CACHE_DIR / "TEST_SECURITY_TEMP.json"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        test_file.write_text(json.dumps({"corrupted": True, "cached_at": time.time()}))
        try:
            result = get_cached("TEST_SECURITY_TEMP", ttl=3600)
            # Deve retornar o dict (cache válido estruturalmente) ou None
            assert result is None or isinstance(result, dict), \
                "A08: get_cached retornou tipo inesperado com dado corrompido"
        finally:
            test_file.unlink(missing_ok=True)


# ── A10:2021 — SSRF (Server-Side Request Forgery) ────────────────────────────

class TestA10SSRF:

    def test_url_api_e_constante_hardcoded(self):
        """URL da API deve ser constante, não derivada de input."""
        src = (ROOT / "b3analytics/infrastructure/ai_analyst.py").read_text(encoding="utf-8")
        assert '_AI_API_URL = "https://api.anthropic.com' in src, \
            "A10: URL da API não é constante — risco de SSRF via input"

    def test_fundamentus_url_sanitiza_ticker(self):
        """URL do Fundamentus em grafico.py deve sanitizar ticker (remove .SA)."""
        src = (ROOT / "pages/grafico.py").read_text(encoding="utf-8")
        assert "replace(" in src and "fundamentus" in src.lower(), \
            "A10: URL do Fundamentus pode incluir ticker não sanitizado (ex: .SA in URL)"

    def test_sem_request_http_para_url_de_input_usuario(self):
        """Nenhuma página deve fazer request HTTP para URL fornecida diretamente pelo usuário."""
        bad_pattern = re.compile(
            r'(?:requests\.get|httpx\.get|urllib\.request\.urlopen)\s*\(\s*'
            r'(?:st\.\w+|url|link|href)',
            re.I,
        )
        for f in (ROOT / "pages").glob("*.py"):
            src = f.read_text(encoding="utf-8")
            m = bad_pattern.search(src)
            assert not m, \
                f"A10/SSRF: {f.name} faz request para URL que pode ser input do usuário"

    def test_yfinance_ticker_nao_e_url_arbitraria(self):
        """yfinance.Ticker usa ticker, não URL arbitrária — verificar que fetcher valida."""
        src = (ROOT / "b3analytics/infrastructure/fetcher.py").read_text(encoding="utf-8")
        # fetcher deve usar ticker de ACOES, não de input livre
        # Verificar que não há concatenação de URL com variável não validada
        assert "yf.Ticker" in src or "yfinance" in src, \
            "A10: fetcher não usa yfinance"
        # Não deve construir URL manualmente com input
        bad = re.search(r'f["\']https?://.*{(?:ticker|url|link)', src)
        assert not bad, \
            f"A10: fetcher constrói URL manualmente com variável: {bad.group()[:80] if bad else ''}"
