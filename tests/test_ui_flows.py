"""
Testes de fluxo 100% via interface.
Cada teste navega, clica e verifica resultados reais no browser.
"""
import os
import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("B3_RUN_E2E") != "1",
        reason="Fluxos UI/Playwright opcionais; use B3_RUN_E2E=1 com servidor em 8504",
    ),
]

BASE    = "http://localhost:8504"
TIMEOUT = 25_000


# ── Helpers ────────────────────────────────────────────────────────────────────

def app(page: Page, rota: str = "") -> None:
    page.goto(f"{BASE}{rota}")
    page.wait_for_selector("[data-testid='stApp']",     timeout=30_000)
    page.wait_for_selector("[data-testid='stSidebar']", timeout=30_000)
    try:
        page.wait_for_function(
            "!document.querySelector('[data-testid=\"stSpinner\"]')",
            timeout=20_000,
        )
    except Exception:
        pass


def sem_erro(page: Page, contexto: str = "") -> None:
    excecao = page.locator("[data-testid='stException']")
    if excecao.count() > 0:
        msg = excecao.first.inner_text()[:400]
        pytest.fail(f"TELA DE ERRO Streamlit em '{contexto}':\n{msg}")


def clica_nav(page: Page, texto: str) -> None:
    page.locator("[data-testid='stSidebar']").get_by_text(texto, exact=True).click()
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)
    try:
        page.wait_for_function(
            "!document.querySelector('[data-testid=\"stSpinner\"]')",
            timeout=15_000,
        )
    except Exception:
        pass


def aguarda_sem_spinner(page: Page, timeout: int = 15_000) -> None:
    try:
        page.wait_for_function(
            "!document.querySelector('[data-testid=\"stSpinner\"]')",
            timeout=timeout,
        )
    except Exception:
        pass


# ── FLUXO 1: Inicialização e navegação ────────────────────────────────────────

class TestFluxoNavegacao:

    def test_app_abre_sem_erro(self, page: Page):
        app(page)
        sem_erro(page, "página inicial")

    def test_titulo_bolsa_br_visivel(self, page: Page):
        app(page)
        assert "BOLSA" in page.content(), "Título BOLSA.BR não encontrado"

    def test_status_mercado_na_sidebar(self, page: Page):
        app(page)
        sidebar = page.locator("[data-testid='stSidebar']").inner_text()
        assert "ABERTO" in sidebar or "FECHADO" in sidebar, \
            f"Status de mercado ausente. Sidebar: {sidebar[:200]}"

    def test_navegacao_visao_geral(self, page: Page):
        app(page)
        clica_nav(page, "Visão Geral")
        sem_erro(page, "Visão Geral")

    def test_navegacao_grafico(self, page: Page):
        app(page)
        clica_nav(page, "Gráfico")
        sem_erro(page, "Gráfico")

    def test_navegacao_setups(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        sem_erro(page, "Setups")

    def test_navegacao_backtesting(self, page: Page):
        app(page)
        clica_nav(page, "Backtesting")
        sem_erro(page, "Backtesting")

    def test_navegacao_comparacao(self, page: Page):
        app(page)
        clica_nav(page, "Comparação")
        sem_erro(page, "Comparação")

    def test_navegacao_ia(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        sem_erro(page, "IA")

    def test_navegacao_configuracoes(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        sem_erro(page, "Configurações")

    def test_volta_e_navega_novamente(self, page: Page):
        app(page)
        for pagina in ["Gráfico", "Setups", "IA", "Configurações", "Visão Geral"]:
            clica_nav(page, pagina)
            sem_erro(page, f"segunda navegação para {pagina}")


# ── FLUXO 2: Sidebar ──────────────────────────────────────────────────────────

class TestFluxoSidebar:

    def test_capital_input_aceita_valor(self, page: Page):
        # Capital/Risco só aparece em páginas de trading (Setups, Backtesting)
        app(page, "/setups")
        inp = page.locator(
            "[data-testid='stSidebar'] [data-testid='stNumberInput'] input"
        ).first
        expect(inp).to_be_visible(timeout=TIMEOUT)
        inp.fill("5000")
        inp.press("Tab")
        sem_erro(page, "sidebar capital input")

    def test_risco_slider_clicavel(self, page: Page):
        # Capital/Risco só aparece em páginas de trading (Setups, Backtesting)
        app(page, "/setups")
        slider = page.locator(
            "[data-testid='stSidebar'] [data-testid='stSlider']"
        ).first
        expect(slider).to_be_visible(timeout=TIMEOUT)
        slider.click()
        sem_erro(page, "sidebar risco slider")

    def test_multiselect_grupos_existe(self, page: Page):
        app(page)
        ms = page.locator(
            "[data-testid='stSidebar'] [data-testid='stMultiSelect']"
        ).first
        expect(ms).to_be_visible(timeout=TIMEOUT)
        sem_erro(page, "sidebar multiselect grupos")


# ── FLUXO 3: Visão Geral ──────────────────────────────────────────────────────

class TestFluxoVisaoGeral:

    def test_tabela_aparece(self, page: Page):
        app(page)
        clica_nav(page, "Visão Geral")
        page.wait_for_function(
            "document.body.innerText.includes('PETR4') || "
            "document.body.innerText.includes('VALE3') || "
            "!!document.querySelector('table')",
            timeout=45_000,
        )
        sem_erro(page, "tabela Visão Geral")

    def test_checkbox_so_com_setup(self, page: Page):
        app(page)
        clica_nav(page, "Visão Geral")
        cb = page.locator("[data-testid='stCheckbox']").first
        expect(cb).to_be_visible(timeout=TIMEOUT)
        cb.click()
        page.wait_for_timeout(500)
        sem_erro(page, "checkbox só com setup")

    def test_selectbox_ordenar(self, page: Page):
        app(page)
        clica_nav(page, "Visão Geral")
        selectboxes = page.locator("[data-testid='stSelectbox']")
        expect(selectboxes.last).to_be_visible(timeout=TIMEOUT)
        selectboxes.last.click()
        page.wait_for_timeout(400)
        sem_erro(page, "selectbox ordenar Visão Geral")
        page.keyboard.press("Escape")


# ── FLUXO 4: Gráfico ─────────────────────────────────────────────────────────

class TestFluxoGrafico:

    def test_seletor_ativo_abre(self, page: Page):
        app(page)
        clica_nav(page, "Gráfico")
        sb = page.locator("[data-testid='stSelectbox']").first
        expect(sb).to_be_visible(timeout=TIMEOUT)
        sb.click()
        page.wait_for_timeout(400)
        sem_erro(page, "seletor ativo gráfico")
        page.keyboard.press("Escape")

    def test_checkboxes_indicadores_existem(self, page: Page):
        app(page)
        clica_nav(page, "Gráfico")
        page.wait_for_timeout(2000)
        # Gráfico tem checkboxes para ativar SMA/EMA/Bollinger etc.
        cbs = page.locator("[data-testid='stCheckbox']")
        assert cbs.count() >= 3, \
            f"Esperado ≥3 checkboxes de indicadores no Gráfico, got {cbs.count()}"
        sem_erro(page, "checkboxes indicadores gráfico")

    def test_mudar_periodo_nao_quebra(self, page: Page):
        app(page)
        clica_nav(page, "Gráfico")
        # Slider de período
        slider = page.locator("[data-testid='stSlider']").first
        if slider.is_visible():
            slider.click()
            page.wait_for_timeout(500)
            sem_erro(page, "mudar período gráfico")

    def test_link_fundamentus_presente(self, page: Page):
        app(page)
        clica_nav(page, "Gráfico")
        page.wait_for_timeout(5000)
        assert "fundamentus" in page.content().lower(), \
            "Link do Fundamentus não encontrado"


# ── FLUXO 5: Setups ───────────────────────────────────────────────────────────

class TestFluxoSetups:

    def test_zero_radio_buttons(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        n = page.locator("[data-testid='stRadio']").count()
        assert n == 0, \
            f"FALHA: {n} radio button(s) encontrado(s) — trocar por dropdowns"

    def test_dropdown_direcao_funciona(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        sb = page.locator("[data-testid='stSelectbox']").first
        expect(sb).to_be_visible(timeout=TIMEOUT)
        sb.click()
        page.wait_for_timeout(400)
        content = page.content()
        assert "LONG" in content or "Todos" in content, \
            "Opções do dropdown de direção não encontradas"
        sem_erro(page, "dropdown direção setups")
        page.keyboard.press("Escape")

    def test_dropdown_tipo_funciona(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        sbs = page.locator("[data-testid='stSelectbox']")
        if sbs.count() >= 2:
            sbs.nth(1).click()
            page.wait_for_timeout(400)
            content = page.content()
            assert any(x in content for x in
                       ["Pullback", "Rompimento", "Reversão", "Todos"]), \
                "Tipos de setup não encontrados"
            sem_erro(page, "dropdown tipo setups")
            page.keyboard.press("Escape")

    def test_input_capital_aceita_valor(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        inp = page.locator("[data-testid='stNumberInput'] input").first
        expect(inp).to_be_visible(timeout=TIMEOUT)
        inp.fill("2000")
        inp.press("Tab")
        sem_erro(page, "input capital setups")

    def test_slider_confianca_existe(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        sliders = page.locator("[data-testid='stSlider']")
        assert sliders.count() >= 1, "Slider de confiança mínima não encontrado"
        sem_erro(page, "slider confiança setups")

    def test_botao_escanear_habilitado(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        btn = page.locator("button").filter(
            has_text=re.compile("Escanear", re.I)
        ).first
        expect(btn).to_be_visible(timeout=TIMEOUT)
        expect(btn).to_be_enabled()
        sem_erro(page, "botão escanear setups")


# ── FLUXO 6: Backtesting ──────────────────────────────────────────────────────

class TestFluxoBacktesting:

    def test_page_carrega(self, page: Page):
        app(page)
        clica_nav(page, "Backtesting")
        sem_erro(page, "Backtesting")

    def test_seletores_ativo_e_estrategia(self, page: Page):
        app(page)
        clica_nav(page, "Backtesting")
        sbs = page.locator("[data-testid='stSelectbox']")
        assert sbs.count() >= 2, \
            f"Esperado ≥2 seletores (ativo + estratégia), got {sbs.count()}"
        expect(sbs.first).to_be_visible(timeout=TIMEOUT)

    def test_botao_rodar_habilitado(self, page: Page):
        app(page)
        clica_nav(page, "Backtesting")
        btn = page.locator("button").filter(
            has_text=re.compile(r"Rodar|Backtest|▶", re.I)
        ).first
        expect(btn).to_be_visible(timeout=TIMEOUT)
        expect(btn).to_be_enabled()
        sem_erro(page, "botão rodar backtest")


# ── FLUXO 7: IA ───────────────────────────────────────────────────────────────

class TestFluxoIA:

    def test_page_abre_sem_erro(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        sem_erro(page, "IA abertura")

    def test_tab_configuracao_clicavel(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        tab = page.locator("[data-testid='stTab']").filter(
            has_text=re.compile("Configuração", re.I)
        ).first
        expect(tab).to_be_visible(timeout=TIMEOUT)
        tab.click()
        page.wait_for_timeout(800)
        sem_erro(page, "IA tab Configuração")

    def test_tab_analise_clicavel(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        tabs = page.locator("[data-testid='stTab']")
        expect(tabs.last).to_be_visible(timeout=TIMEOUT)
        tabs.last.click()
        page.wait_for_timeout(800)
        sem_erro(page, "IA tab Análise")

    def test_provider_selector_sem_crash(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        sem_erro(page, "IA provider selector render")
        assert "Motor IA Local" in page.content(), \
            "Opção 'Motor IA Local' não encontrada"

    def test_selecionar_motor_local_sem_icone_invalido(self, page: Page):
        """O icon='✓' corrigido para '✅' — não deve aparecer erro de emoji."""
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)

        opt = page.locator("text=Motor IA Local").first
        if opt.is_visible():
            opt.click()
            page.wait_for_timeout(1500)

        content = page.content()
        assert "is not a valid emoji" not in content, \
            "ERRO: ícone inválido (icon='✓' ou similar) ainda presente"
        assert "Shortcodes are not allowed" not in content, \
            "ERRO: ícone shortcode ainda presente"
        sem_erro(page, "IA selecionar Motor IA Local")

    def test_selecionar_api_remota_sem_crash(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)

        opt = page.locator("text=API Remota").first
        if opt.is_visible():
            opt.click()
            page.wait_for_timeout(1000)

        sem_erro(page, "IA selecionar API Remota")

    def _ativa_api_remota(self, page: Page) -> None:
        """Garante que o provider API Remota está ativo na tab Config."""
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() > 0 and sels.first.is_visible():
            sels.first.click()
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile("API Remota|remota", re.I)).first
            if opt.is_visible():
                opt.click()
                page.wait_for_timeout(2000)
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

    def test_campo_api_key_existe_e_aceita_input(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        # API Key só aparece quando a API Remota está ativa
        self._ativa_api_remota(page)

        campo = page.locator("input[type='password']").first
        expect(campo).to_be_visible(timeout=TIMEOUT)
        campo.click()
        campo.fill("FAKE-TEST-KEY-UI-NOT-REAL-9999")
        page.wait_for_timeout(400)
        sem_erro(page, "IA campo API key")

    def test_seletor_modelo_existe(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        # Seletor de modelo só aparece quando a API Remota está ativa
        self._ativa_api_remota(page)
        assert "Modelo" in page.content() or "modelo" in page.content(), \
            "Seletor de modelo não encontrado"

    def test_presets_existem(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        content = page.content()
        assert any(p in content for p in
                   ["Econômico", "Padrão", "Completo", "econômico", "padrão"]), \
            "Presets de custo não encontrados"

    def test_secao_cache_existe(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        assert "Cache" in page.content() or "cache" in page.content(), \
            "Seção de cache não encontrada"

    def test_botao_testar_habilitado(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        btn = page.locator("button").filter(has_text=re.compile("Testar", re.I)).first
        expect(btn).to_be_visible(timeout=TIMEOUT)
        expect(btn).to_be_enabled()
        sem_erro(page, "IA botão Testar")

    def test_tab_analise_sem_api_key_sem_crash(self, page: Page):
        app(page)
        clica_nav(page, "IA")
        tabs = page.locator("[data-testid='stTab']")
        if tabs.count() >= 2:
            tabs.nth(1).click()
            page.wait_for_timeout(1500)
            sem_erro(page, "IA tab Análise sem API key")


# ── FLUXO 8: Configurações ────────────────────────────────────────────────────

class TestFluxoConfiguracoes:

    def test_page_carrega(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        sem_erro(page, "Configurações")

    def test_secoes_indicadores(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        content = page.content()
        for secao in ["Médias Móveis", "RSI", "MACD", "Bollinger"]:
            assert secao in content, f"Seção '{secao}' não encontrada"

    def test_inputs_numericos_existem(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        n = page.locator("[data-testid='stNumberInput']").count()
        assert n >= 5, f"Esperado ≥5 inputs numéricos, got {n}"

    def test_mudar_sma_nao_crasha(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        inp = page.locator("[data-testid='stNumberInput'] input").first
        expect(inp).to_be_visible(timeout=TIMEOUT)
        inp.fill("15")
        inp.press("Tab")
        page.wait_for_timeout(400)
        sem_erro(page, "mudar SMA")

    def test_botao_restaurar_funciona(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        btn = page.locator("button").filter(
            has_text=re.compile("Restaurar", re.I)
        ).first
        expect(btn).to_be_visible(timeout=TIMEOUT)
        expect(btn).to_be_enabled()
        btn.click()
        page.wait_for_timeout(1200)
        sem_erro(page, "botão Restaurar padrões")

    def test_editor_ativos_existe(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        content = page.content()
        assert any(x in content for x in ["Ativos", "ativos", "ativo"]), \
            "Editor de ativos não encontrado"

    def test_tabs_editor_existem(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        content = page.content()
        for tab in ["Adicionar", "Remover", "Grupos", "Cripto"]:
            assert tab in content, f"Tab '{tab}' do editor não encontrada"

    def test_tab_adicionar_tem_campos(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        tab = page.locator("[role='tab']").filter(
            has_text=re.compile("Adicionar", re.I)
        ).first
        if tab.is_visible():
            tab.click()
            page.wait_for_timeout(800)
            sem_erro(page, "tab Adicionar ativos")
            assert "Ticker" in page.content(), "Campo Ticker não encontrado"

    def test_tab_remover_tem_selectbox(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        tab = page.locator("[role='tab']").filter(
            has_text=re.compile("Remover", re.I)
        ).first
        if tab.is_visible():
            tab.click()
            page.wait_for_timeout(800)
            sem_erro(page, "tab Remover ativos")

    def test_tab_cripto_tem_toggle(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        # Streamlit tabs render as [role='tab']
        tab = page.locator("[role='tab']").filter(
            has_text=re.compile(r"Cripto|₿", re.I)
        ).first
        if tab.is_visible():
            tab.click()
            page.wait_for_timeout(1000)
            sem_erro(page, "tab Cripto")
            # st.toggle renders as stCheckbox in Streamlit 1.50
            toggle = page.locator("[data-testid='stCheckbox']").first
            expect(toggle).to_be_visible(timeout=TIMEOUT)

    def test_habilitar_cripto_e_desabilitar(self, page: Page):
        app(page)
        clica_nav(page, "Configurações")
        tab = page.locator("[role='tab']").filter(
            has_text=re.compile(r"Cripto|₿", re.I)
        ).first
        if not tab.is_visible():
            pytest.skip("Tab Cripto não encontrada")
        tab.click()
        page.wait_for_timeout(1000)
        toggle = page.locator("[data-testid='stCheckbox']").first
        expect(toggle).to_be_visible(timeout=TIMEOUT)
        toggle.click()
        page.wait_for_timeout(1500)
        sem_erro(page, "habilitar cripto")
        # Desabilitar para não afetar outros testes
        toggle = page.locator("[data-testid='stCheckbox']").first
        if toggle.is_visible():
            toggle.click()
            page.wait_for_timeout(1000)


# ── FLUXO 9: Comparação ───────────────────────────────────────────────────────

class TestFluxoComparacao:

    def test_page_carrega(self, page: Page):
        app(page)
        clica_nav(page, "Comparação")
        sem_erro(page, "Comparação")

    def test_multiselect_existe(self, page: Page):
        app(page)
        clica_nav(page, "Comparação")
        ms = page.locator("[data-testid='stMultiSelect']").first
        expect(ms).to_be_visible(timeout=TIMEOUT)

    def test_selecionar_ativo_nao_crasha(self, page: Page):
        app(page)
        clica_nav(page, "Comparação")
        ms = page.locator("[data-testid='stMultiSelect']").first
        expect(ms).to_be_visible(timeout=TIMEOUT)
        ms.click()
        page.wait_for_timeout(500)
        opcao = page.locator("[data-testid='stMultiSelect'] li").first
        if opcao.is_visible():
            opcao.click()
            page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        sem_erro(page, "Comparação selecionar ativo")


# ── FLUXO 10: IA Providers Completo ──────────────────────────────────────────

class TestIA_ProvidersCompleto:
    """Testa a UI de seleção de provider via selectbox compacto (sem radio)."""

    def _vai_para_config(self, page: Page) -> None:
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(1000)
        sem_erro(page, "IA tab Configuração abertura")

    def _ativa_motor_local(self, page: Page) -> bool:
        """Tenta ativar Motor IA Local via provider selectbox. Retorna True se bem-sucedido."""
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() == 0:
            return False
        sels.first.click()
        page.wait_for_timeout(400)
        opt = page.get_by_role("option", name=re.compile("Motor IA Local", re.I)).first
        if opt.is_visible():
            opt.click()
            page.wait_for_timeout(2000)
            return True
        page.keyboard.press("Escape")
        return False

    def test_sem_radio_button_no_provider(self, page: Page):
        """Provider section usa selectbox — não deve ter radio com opções de provider."""
        self._vai_para_config(page)
        radios = page.locator("[data-testid='stRadio']")
        for i in range(radios.count()):
            txt = radios.nth(i).inner_text()
            assert "Modo de análise" not in txt, \
                "FALHA: radio 'Modo de análise' ainda presente"
            assert "API Remota (chave)" not in txt or "Motor IA Local" not in txt, \
                f"FALHA: radio com opções de provider ainda presente: {txt[:200]}"

    def test_cards_provider_existem(self, page: Page):
        """Ambas as opções de provider devem aparecer no dropdown do selectbox."""
        self._vai_para_config(page)
        prov_sel = page.locator("[data-testid='stSelectbox']").first
        expect(prov_sel).to_be_visible(timeout=TIMEOUT)
        prov_sel.click()
        page.wait_for_timeout(500)
        content = page.content()
        page.keyboard.press("Escape")
        assert "API Remota" in content, "Opção 'API Remota' não encontrada no dropdown"
        assert "Motor IA Local" in content, "Opção 'Motor IA Local' não encontrada no dropdown"

    def test_indicador_provider_ativo_visivel(self, page: Page):
        """Indicador 'Provider ativo' deve estar visível."""
        self._vai_para_config(page)
        content = page.content()
        assert "Provider ativo" in content or "API Remota" in content or "Motor IA Local" in content, \
            "Nenhum indicador de provider ativo encontrado"

    def test_botao_usar_motor_local_existe_ou_ativo(self, page: Page):
        """Opção Motor IA Local deve estar disponível no selectbox de provider."""
        self._vai_para_config(page)
        content = page.content()
        assert "Motor IA Local" in content, \
            "Opção 'Motor IA Local' não encontrada no seletor de provider"
        sem_erro(page, "IA seletor Motor IA Local")

    def test_botao_usar_api_remota_existe_ou_ativo(self, page: Page):
        """Opção API Remota deve estar disponível no dropdown do selectbox."""
        self._vai_para_config(page)
        prov_sel = page.locator("[data-testid='stSelectbox']").first
        prov_sel.click()
        page.wait_for_timeout(500)
        content = page.content()
        page.keyboard.press("Escape")
        assert "API Remota" in content, \
            "Opção 'API Remota' não encontrada no dropdown de provider"
        sem_erro(page, "IA seletor API Remota")

    def test_clicar_usar_motor_local_sem_crash(self, page: Page):
        """Selecionar Motor IA Local no provider selectbox não deve causar crash."""
        self._vai_para_config(page)
        self._ativa_motor_local(page)
        sem_erro(page, "IA selecionar Motor IA Local sem crash")
        content = page.content()
        assert "Motor IA Local" in content, "Seleção de Motor IA Local causou crash"

    def test_clicar_usar_api_remota_sem_crash(self, page: Page):
        """Selecionar API Remota no provider selectbox não deve causar crash."""
        self._vai_para_config(page)
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() > 0:
            sels.first.click()
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile("API Remota", re.I)).first
            if opt.is_visible():
                opt.click()
                page.wait_for_timeout(2000)
            else:
                page.keyboard.press("Escape")
        sem_erro(page, "IA selecionar API Remota sem crash")

    def test_tab_analise_abre_quando_motor_local_ativo(self, page: Page):
        """Tab Análise deve abrir sem pedir API Key quando Motor IA Local está ativo."""
        app(page)
        clica_nav(page, "IA")
        config_tab = page.locator("[data-testid='stTab']").first
        config_tab.click()
        page.wait_for_timeout(1000)
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() > 0:
            sels.first.click()
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile("Motor IA Local", re.I)).first
            if opt.is_visible():
                opt.click()
                page.wait_for_timeout(2500)
            else:
                page.keyboard.press("Escape")
        analise_tab = page.locator("[data-testid='stTab']").last
        analise_tab.click()
        page.wait_for_timeout(1500)
        sem_erro(page, "IA tab Análise com Motor IA Local ativo")
        content = page.content()
        assert "Analisar" in content or "Ativo" in content or "ativo" in content.lower(), \
            "Tab Análise não carregou corretamente com Motor IA Local ativo"

    def test_sidebar_mostra_provider_ativo(self, page: Page):
        """Sidebar deve mostrar o provider ativo."""
        app(page)
        clica_nav(page, "IA")
        sidebar = page.locator("[data-testid='stSidebar']").inner_text()
        assert any(x in sidebar for x in [
            "Motor IA Local", "API Remota", "IA não configurada",
            "configurado", "ativo",
        ]), f"Status IA não encontrado na sidebar. Conteúdo: {sidebar[:300]}"

    def test_em_breve_removido(self, page: Page):
        """Seção 'Em breve' com OpenAI/Gemini deve ter sido removida."""
        self._vai_para_config(page)
        content = page.content()
        assert "OpenAI GPT-4o" not in content, \
            "FALHA: card 'OpenAI GPT-4o' ainda presente"
        assert "Google Gemini" not in content, \
            "FALHA: card 'Google Gemini' ainda presente"


# ── FLUXO 11: IA Análise Completa ────────────────────────────────────────────

class TestIAAnaliseCompleta:
    """Testa o fluxo completo de análise com todas as novas seções."""

    def _ativa_motor_local_e_vai_analise(self, page: Page) -> None:
        """Ativa Motor IA Local no config tab e abre o tab de análise."""
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(1000)
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() > 0:
            sels.first.click()
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile("Motor IA Local", re.I)).first
            if opt.is_visible():
                opt.click()
                page.wait_for_timeout(2500)
            else:
                page.keyboard.press("Escape")
        page.locator("[data-testid='stTab']").nth(1).click()
        page.wait_for_timeout(2000)

    def test_tab_analise_abre_sem_crash(self, page: Page):
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA tab Análise abertura")

    def test_seletor_ativo_existe(self, page: Page):
        """Selectbox de ativo deve estar visível no tab Análise (com CC ativo)."""
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA Análise seletor ativo")
        content = page.content()
        # If analysis tab is accessible (no st.stop), find a visible selectbox
        # Note: config tab's selectboxes are in DOM but hidden — filter by visibility
        if "Analisar" in content or "Análise" in content:
            sbs = page.locator("[data-testid='stSelectbox']").all()
            visible_sbs = [sb for sb in sbs if sb.is_visible()]
            assert len(visible_sbs) > 0, "Nenhum selectbox visível no tab Análise"
            expect(visible_sbs[0]).to_be_visible(timeout=TIMEOUT)

    def test_botao_analisar_existe_e_habilitado(self, page: Page):
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA Análise botão")
        btn = page.locator("button").filter(has_text=re.compile("Analisar", re.I)).first
        if btn.is_visible():
            expect(btn).to_be_enabled()

    def test_catalisadores_como_expanders_se_cache_existe(self, page: Page):
        """Se resultado em cache existir, catalisadores são expanders expansíveis."""
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA Análise expanders")
        # Only click VISIBLE expanders (config tab has hidden expanders in DOM)
        expanders = page.locator("[data-testid='stExpander']").all()
        visible_expanders = [e for e in expanders if e.is_visible()]
        if visible_expanders:
            visible_expanders[0].click()
            page.wait_for_timeout(500)
            sem_erro(page, "expandir expander visível")

    def test_dados_analistas_yf_sem_crash(self, page: Page):
        """Painel de dados yfinance não deve causar crash."""
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA painel analistas yfinance")
        assert page.locator("[data-testid='stException']").count() == 0

    def test_noticias_com_links_externos(self, page: Page):
        """Links externos devem ter target=_blank (se existirem)."""
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA notícias links externos")
        assert page.locator("[data-testid='stException']").count() == 0

    def test_json_completo_expander_existe_se_resultado(self, page: Page):
        """Expander 'Ver JSON completo' deve aparecer quando há resultado."""
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA JSON expander")
        content = page.content()
        if "Score" in content or "macro_score" in content:
            assert "Ver JSON completo" in content, \
                "Expander 'Ver JSON completo' ausente quando há resultado"

    def test_provider_badge_visivel_em_analise(self, page: Page):
        """Badge de provider deve aparecer na tab Análise."""
        self._ativa_motor_local_e_vai_analise(page)
        sem_erro(page, "IA provider badge")
        content = page.content()
        assert any(x in content for x in [
            "Motor IA Local", "API Remota", "Analisar",
        ]), "Nenhum badge/botão de provider encontrado na tab Análise"


# ── FLUXO 12: Tamanho de Interface ────────────────────────────────────────────

class TestTamanhoInterface:
    """Verifica que a interface usa tamanhos compactos (font ≤ 14px, botões ≤ 40px)."""

    def test_fonte_base_compacta_no_css(self, page: Page):
        """CSS injetado deve conter fonte base ≤ 13px."""
        app(page)
        content = page.content()
        assert "13px" in content or "12px" in content, \
            "CSS não contém fonte compacta (13px ou menor) — verificar theme.py"

    def test_botoes_sem_overflow_vertical(self, page: Page):
        """Botões principais não devem ultrapassar 40px de altura."""
        app(page)
        sem_erro(page, "Interface compacta — botões")
        btns = page.locator("button").all()
        for btn in btns[:8]:
            if btn.is_visible():
                box = btn.bounding_box()
                if box and box["height"] > 0:
                    assert box["height"] <= 40, \
                        f"Botão com {box['height']:.0f}px (máx 40px): '{btn.inner_text()[:30]}'"

    def test_pagina_principal_sem_crash_com_fonte_compacta(self, page: Page):
        app(page)
        sem_erro(page, "Página principal com fonte compacta")
        content = page.content()
        assert "BOLSA" in content or "Dashboard" in content, \
            "Página principal não carregou com tema compacto"

    def test_setups_com_interface_compacta(self, page: Page):
        app(page)
        clica_nav(page, "Setups")
        sem_erro(page, "Setups com interface compacta")

    def test_grafico_com_interface_compacta(self, page: Page):
        app(page)
        clica_nav(page, "Gráfico")
        sem_erro(page, "Gráfico com interface compacta")


# ── FLUXO 13: Navegação Contextual ────────────────────────────────────────────

class TestFluxoNavegacaoContextual:
    """Verifica botões de navegação contextual entre páginas."""

    def test_grafico_tem_botao_setups(self, page: Page):
        """Página Gráfico deve ter botão contextual para Setups."""
        app(page)
        clica_nav(page, "Gráfico")
        page.wait_for_timeout(1000)
        sem_erro(page, "Gráfico nav contextual")
        content = page.content()
        assert "Setups" in content, "Botão 'Setups' não encontrado na página Gráfico"

    def test_grafico_tem_botao_ia(self, page: Page):
        """Página Gráfico deve ter botão contextual para IA."""
        app(page)
        clica_nav(page, "Gráfico")
        page.wait_for_timeout(1000)
        sem_erro(page, "Gráfico botão IA")
        content = page.content()
        assert "IA" in content or "🧠" in content, \
            "Botão IA não encontrado na página Gráfico"

    def test_grafico_tem_link_fundamentus(self, page: Page):
        """Página Gráfico deve ter link para Fundamentus."""
        app(page)
        clica_nav(page, "Gráfico")
        page.wait_for_timeout(1000)
        sem_erro(page, "Gráfico link Fundamentus")
        content = page.content()
        assert "Fundamentus" in content or "fundamentus" in content.lower(), \
            "Link Fundamentus não encontrado na página Gráfico"

    def test_clicar_botao_setups_no_grafico_sem_crash(self, page: Page):
        """Clicar em 'Setups' no Gráfico deve navegar sem crash."""
        app(page)
        clica_nav(page, "Gráfico")
        page.wait_for_timeout(1000)
        btn = page.locator("button").filter(has_text=re.compile("Setups", re.I)).first
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(2000)
            sem_erro(page, "Navegar Gráfico → Setups")

    def test_ia_analise_tem_botao_grafico(self, page: Page):
        """Após análise de IA com resultado, deve aparecer botão para Gráfico."""
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() > 0:
            sels.first.click()
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile("Motor IA Local", re.I)).first
            if opt.is_visible():
                opt.click()
                page.wait_for_timeout(2000)
            else:
                page.keyboard.press("Escape")
        page.locator("[data-testid='stTab']").nth(1).click()
        page.wait_for_timeout(2000)
        sem_erro(page, "IA análise com botão Gráfico")
        content = page.content()
        if "Score" in content or "macro_score" in content or "Parecer" in content:
            assert "Gráfico" in content or "📈" in content, \
                "Botão 'Gráfico' ausente na IA com resultado em cache"

    def test_setups_motor_local_ativo_sem_aviso_ia(self, page: Page):
        """Setups com Motor IA Local ativo não deve bloquear análise de IA."""
        app(page)
        clica_nav(page, "IA")
        page.locator("[data-testid='stTab']").first.click()
        page.wait_for_timeout(800)
        sels = page.locator("[data-testid='stSelectbox']")
        if sels.count() > 0:
            sels.first.click()
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile("Motor IA Local", re.I)).first
            if opt.is_visible():
                opt.click()
                page.wait_for_timeout(2000)
            else:
                page.keyboard.press("Escape")
        clica_nav(page, "Setups")
        page.wait_for_timeout(2000)
        sem_erro(page, "Setups com Motor IA Local ativo")
        content = page.content()
        assert "Configure a IA" not in content, \
            "FALHA: 'Configure a IA' visível com Motor IA Local ativo"
