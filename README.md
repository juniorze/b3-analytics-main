# BOLSA.BR

App local em Python 3.12+ com Streamlit para analise tecnica educacional de ativos da B3.

O projeto consolida cotacoes, indicadores tecnicos, scanner de setups, backtesting, comparacao de ativos, carteira local e analises auxiliares para estudo. As informacoes exibidas tem carater educacional e nao constituem recomendacao de investimento.

## Instalacao

```bash
git clone https://github.com/seu-usuario/b3-analytics.git
cd b3-analytics
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,test]"
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev,test]"
```

## Execucao local

```bash
py -m streamlit run app.py
```

Se `py` nao estiver disponivel no ambiente, use:

```bash
python -m streamlit run app.py
```

## Validacao

```bash
py -m pytest
py -m ruff check .
py -m streamlit run app.py
```

## Estado atual

- Fase 4B.1 implementada na Carteira.
- Semaforo tecnico da carteira executado somente por botao manual.
- Resultado da analise tecnica mantido em `st.session_state`.
- Tela da carteira exibe ultima analise, limpeza manual, mensagem para carteira sem posicao e aviso educacional.
- Teste sistemico usa OHLCV sintetico deterministico na validacao de setups, mantendo `find_setup` real.

## Funcionalidades

- Visao geral de ativos da B3 com cotacoes, variacoes e leitura tecnica.
- Graficos com indicadores tecnicos.
- Scanner educacional de setups.
- Backtesting local.
- Comparacao de ativos.
- Carteira local com posicoes, risco e semaforo tecnico educacional.
- Integracao opcional com IA para analises auxiliares.

## Limitacoes

- `yfinance` pode falhar, atrasar ou retornar dados incompletos.
- O app e local e depende do ambiente da maquina do usuario.
- Nao envia ordens.
- Nao possui login B3.
- Nao executa recomendacao automatica.
- Nao constitui recomendacao de investimento.

## Aviso educacional

Este projeto e uma ferramenta educacional. Nenhuma informacao exibida deve ser interpretada como recomendacao de compra, venda, manutencao de posicao ou alocacao ideal de carteira. Analise tecnica nao garante resultados futuros.

## Qualidade

O CI basico no GitHub Actions instala `.[dev,test]`, executa `pytest` e `ruff check .` em Python 3.12 para `push` e `pull_request` na branch `main`.

## Licenca

MIT
