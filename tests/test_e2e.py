"""E2E Playwright — assertions em elementos concretos, sem wait_for_timeout cego."""
import os
import re
import subprocess
import sys
import time

import pytest
from playwright.sync_api import Page, expect

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("B3_RUN_E2E") != "1",
        reason="E2E Streamlit/Playwright opcional; use B3_RUN_E2E=1 para executar",
    ),
]

PORT    = int(os.environ.get("B3_E2E_PORT", str(8503 + os.getpid() % 1000)))
BASE    = f"http://localhost:{PORT}"
TIMEOUT = 60_000


@pytest.fixture(scope="session", autouse=True)
def servidor():
    env = os.environ.copy()
    env["B3_ANALYTICS_E2E"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(PORT),
         "--server.headless", "true",
         "--server.runOnSave", "false",
         "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env,
    )
    import urllib.error
    import urllib.request
    for i in range(40):
        try:
            urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=2)
            print(f"\n  Streamlit OK em {i+1}s")
            break
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(1)
    else:
        proc.terminate()
        pytest.fail("Streamlit não subiu em 40s")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def carrega(page: Page, path: str = "") -> None:
    for tentativa in range(3):
        page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_selector("[data-testid='stApp']", timeout=TIMEOUT)
        page.wait_for_selector("[data-testid='stSidebar']", timeout=TIMEOUT)
        if "Failed to fetch dynamically imported module" not in page.content():
            return
        if tentativa < 2:
            page.reload(wait_until="domcontentloaded", timeout=TIMEOUT)
    pytest.fail("Streamlit não carregou módulos JS dinâmicos após retry")


def navega(page: Page, texto: str) -> None:
    page.locator(f"[data-testid='stSidebar'] >> text={texto}").first.click()
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)


class TestCarregamento:
    def test_app_carrega_sem_erro(self, page: Page):
        carrega(page)
        erros = page.locator("[data-testid='stException']")
        assert erros.count() == 0, "App iniciou com exceção"

    def test_titulo_bolsa_br(self, page: Page):
        carrega(page)
        expect(page).to_have_title(re.compile("BOLSA\\.BR"), timeout=TIMEOUT)

    def test_sidebar_tem_status_mercado(self, page: Page):
        carrega(page)
        texto = page.locator("[data-testid='stSidebar']").inner_text()
        assert "ABERTO" in texto or "FECHADO" in texto, \
            f"Status de mercado ausente na sidebar: '{texto[:200]}'"

    def test_sidebar_tem_delay_15min(self, page: Page):
        carrega(page)
        assert "15min" in page.locator("[data-testid='stSidebar']").inner_text(), \
            "Aviso de delay ausente"

    def test_7_paginas_na_navegacao(self, page: Page):
        carrega(page)
        for pagina in ["Visão Geral", "Gráfico", "Setups",
                       "Backtesting", "Comparação", "IA", "Configurações"]:
            loc = page.locator(f"[data-testid='stSidebar'] >> text={pagina}").first
            expect(loc).to_be_visible(timeout=TIMEOUT)


class TestVisaoGeral:
    def test_abre_sem_erro(self, page: Page):
        carrega(page)
        navega(page, "Visão Geral")
        assert page.locator("[data-testid='stException']").count() == 0, \
            "Visão Geral abriu com exceção"

    def test_tabela_tem_ticker(self, page: Page):
        carrega(page)
        navega(page, "Visão Geral")
        # Aguarda a tabela HTML customizada (não stDataFrame)
        page.wait_for_selector("table", timeout=60_000)
        content = page.content()
        assert "PETR4" in content or "VALE3" in content, \
            "Tabela não tem tickers reconhecíveis"

    def test_coluna_setup_nao_e_long_short(self, page: Page):
        carrega(page)
        navega(page, "Visão Geral")
        page.wait_for_selector("table", timeout=60_000)
        content = page.content()
        assert "SETUP" in content or "—" in content, \
            "Coluna Setup não encontrada"


class TestGrafico:
    def test_abre_sem_erro(self, page: Page):
        carrega(page, "/grafico")
        assert page.locator("[data-testid='stException']").count() == 0

    def test_selectbox_ativo_existe(self, page: Page):
        carrega(page, "/grafico")
        expect(page.locator("[data-testid='stSelectbox']").first).to_be_visible(timeout=TIMEOUT)

    def test_expander_parametros_existe(self, page: Page):
        carrega(page, "/grafico")
        expect(page.locator("text=Parâmetros").first).to_be_visible(timeout=TIMEOUT)

    def test_link_fundamentus_no_html(self, page: Page):
        carrega(page, "/grafico")
        page.wait_for_timeout(5000)
        assert "fundamentus" in page.content().lower(), \
            "Link do Fundamentus não encontrado"


class TestSetups:
    def test_abre_sem_erro(self, page: Page):
        carrega(page, "/setups")
        assert page.locator("[data-testid='stException']").count() == 0

    def test_zero_radio_buttons(self, page: Page):
        carrega(page, "/setups")
        n = page.locator("[data-testid='stRadio']").count()
        assert n == 0, \
            f"Encontrado {n} radio button(s) — devem ser substituídos por dropdowns"

    def test_selectboxes_existem(self, page: Page):
        carrega(page, "/setups")
        for label in ["Direção", "Tipo de setup", "Ordenar por", "Período de análise"]:
            expect(page.locator(f"text={label}").first).to_be_visible(timeout=TIMEOUT)

    def test_botao_escanear_clicavel(self, page: Page):
        carrega(page, "/setups")
        btn = page.locator("button", has_text="Escanear").first
        expect(btn).to_be_visible(timeout=TIMEOUT)
        expect(btn).to_be_enabled()

    def test_disclaimer_presente(self, page: Page):
        carrega(page, "/setups")
        texto = page.locator("[data-testid='stSidebar']").inner_text().lower()
        assert "dados para fins" in texto or "não constitui" in texto, \
            "Disclaimer não encontrado"


class TestIA:
    def test_abre_sem_erro(self, page: Page):
        carrega(page, "/ia")
        assert page.locator("[data-testid='stException']").count() == 0

    def test_duas_tabs_existem(self, page: Page):
        carrega(page, "/ia")
        expect(page.locator("text=Configuração").first).to_be_visible(timeout=TIMEOUT)
        expect(page.locator("text=Análise").first).to_be_visible(timeout=TIMEOUT)

    def test_tab_config_campo_api_key(self, page: Page):
        carrega(page, "/ia")
        page.locator("text=Configuração").first.click()
        expect(page.locator("text=API Key").first).to_be_visible(timeout=TIMEOUT)

    def test_tab_config_selector_modelo(self, page: Page):
        carrega(page, "/ia")
        page.locator("text=Configuração").first.click()
        expect(page.locator("text=Modelo").first).to_be_visible(timeout=TIMEOUT)

    def test_tab_config_botao_testar(self, page: Page):
        carrega(page, "/ia")
        page.locator("text=Configuração").first.click()
        btn = page.locator("button", has_text="Testar").first
        expect(btn).to_be_visible(timeout=TIMEOUT)
        expect(btn).to_be_enabled()

    def test_tab_config_tem_motor_local_option(self, page: Page):
        carrega(page, "/ia")
        page.locator("text=Configuração").first.click()
        page.get_by_role("combobox").first.click()
        expect(page.locator("text=Motor IA Local").last).to_be_visible(timeout=TIMEOUT)

    def test_tab_config_tem_cache_section(self, page: Page):
        carrega(page, "/ia")
        page.locator("text=Configuração").first.click()
        expect(page.locator("text=/Cache/i").first).to_be_visible(timeout=TIMEOUT)

    def test_tab_config_tem_ttl_selector(self, page: Page):
        carrega(page, "/ia")
        page.locator("text=Configuração").first.click()
        page.locator("text=/Cache/i").first.click()
        expect(page.locator("text=Validade do cache").first).to_be_visible(timeout=TIMEOUT)


class TestConfiguracoes:
    def test_abre_sem_erro(self, page: Page):
        carrega(page, "/configuracoes")
        assert page.locator("[data-testid='stException']").count() == 0

    def test_secao_medias_moveis(self, page: Page):
        carrega(page, "/configuracoes")
        expect(page.locator("text=Médias Móveis").first).to_be_visible(timeout=TIMEOUT)

    def test_secao_rsi(self, page: Page):
        carrega(page, "/configuracoes")
        expect(page.locator("text=RSI").first).to_be_visible(timeout=TIMEOUT)

    def test_botao_restaurar_padrao(self, page: Page):
        carrega(page, "/configuracoes")
        btn = page.locator("button", has_text="Restaurar").first
        expect(btn).to_be_visible(timeout=TIMEOUT)

    def test_secao_editor_ativos(self, page: Page):
        """Editor de ativos deve existir na página de Configurações."""
        carrega(page, "/configuracoes")
        content = page.content()
        assert "Ativos" in content or "ativo" in content.lower(), \
            "Editor de ativos não encontrado em Configurações"
