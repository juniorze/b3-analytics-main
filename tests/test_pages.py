import ast
import importlib
import sys
from pathlib import Path

results = []

def check(name, ok, detail="", got=None):
    if got is not None and not ok:
        detail = str(got)
    results.append(("OK" if ok else "FAIL", name))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f" → {detail}" if detail else ""))


print("\n[1] Sintaxe de todas as páginas")
for page in sorted(Path("pages").glob("*.py")):
    try:
        ast.parse(page.read_text(encoding="utf-8"))
        check(f"Sintaxe {page.name}", True)
    except SyntaxError as e:
        check(f"Sintaxe {page.name}", False, str(e))


print("\n[2] Sintaxe de todos os módulos do pacote")
for py in sorted(Path("b3analytics").rglob("*.py")):
    try:
        ast.parse(py.read_text(encoding="utf-8"))
        check(f"Sintaxe {py}", True)
    except SyntaxError as e:
        check(f"Sintaxe {py}", False, str(e))


print("\n[3] Imports do pacote principal")
modules = [
    "b3analytics.config.settings",
    "b3analytics.config.assets",
    "b3analytics.infrastructure.fetcher",
    "b3analytics.infrastructure.cache",
    "b3analytics.domain.indicators",
    "b3analytics.domain.trend",
    "b3analytics.domain.levels",
    "b3analytics.domain.engine",
    "b3analytics.domain.backtesting",
    "b3analytics.presentation.theme",
    "b3analytics.presentation.components",
    "b3analytics.presentation.sidebar",
]
for m in modules:
    try:
        importlib.import_module(m)
        check(f"Import {m}", True)
    except Exception as e:
        check(f"Import {m}", False, str(e))


print("\n[4] Verificações estruturais do app.py")
app_src = Path("app.py").read_text(encoding="utf-8")
check('app.py não usa page_link("app.py")', 'page_link("app.py")' not in app_src)
check('app.py usa st.navigation',            'st.navigation' in app_src)
check('app.py define default=True em uma página', 'default=True' in app_src)
check('app.py usa position="sidebar"',       'position="sidebar"' in app_src)
check('app.py importa render_sidebar_extras', 'render_sidebar_extras' in app_src)
check('app.py NÃO usa position="hidden"',    'position="hidden"' not in app_src)
check('app.py registra configuracoes.py',    'configuracoes.py' in app_src)


print("\n[5] Verificações estruturais da sidebar")
sb_src = Path("b3analytics/presentation/sidebar.py").read_text(encoding="utf-8")
check('sidebar.py não usa st.page_link',        'st.page_link' not in sb_src)
check('sidebar.py tem render_sidebar_extras',   'render_sidebar_extras' in sb_src)
check('sidebar.py tem render_sidebar (alias)',  'render_sidebar' in sb_src)


print("\n[6] Chaves de período corretas nas páginas")
from b3analytics.config.settings import PERIODOS

valid_keys = set(PERIODOS.keys())
old_keys = {"1A", "2A", "5A", "3M", "6M", "1M", "15d"}
for page in sorted(Path("pages").glob("*.py")):
    src = page.read_text(encoding="utf-8")
    stale = [k for k in old_keys if f'"{k}"' in src and "PERIODO_MAP" not in src]
    check(f"{page.name} sem chaves de período obsoletas", len(stale) == 0, got=stale)


print("\n[7] Imports de render_sidebar nas páginas (devem ser zero ou alias)")
for page in sorted(Path("pages").glob("*.py")):
    src = page.read_text(encoding="utf-8")
    has_import = "from b3analytics.presentation.sidebar import render_sidebar" in src
    if has_import:
        calls_it = "render_sidebar()" in src
        check(f"{page.name} não chama render_sidebar()", not calls_it, got="chama render_sidebar() na página")
    else:
        check(f"{page.name} não importa render_sidebar", True)


print("\n[8] PERIODOS: valor padrão correto no select_slider")
for page in ["grafico.py", "comparacao.py"]:
    src = (Path("pages") / page).read_text(encoding="utf-8")
    check(f"{page} usa value='1 ano'", "value=\"1 ano\"" in src or "value='1 ano'" in src)
for page in ["backtesting.py"]:
    src = (Path("pages") / page).read_text(encoding="utf-8")
    check(f"{page} usa value='2 anos'", "value=\"2 anos\"" in src or "value='2 anos'" in src)


print("\n[9] Página Configurações")
cfg_src = Path("pages/configuracoes.py").read_text(encoding="utf-8")
check('configuracoes.py existe',                  Path("pages/configuracoes.py").exists())
check('configuracoes.py importa INDICATOR_DEFAULTS', 'INDICATOR_DEFAULTS' in cfg_src)
check('configuracoes.py tem session_state indicator_params', 'indicator_params' in cfg_src)
check('configuracoes.py tem botão restaurar',     'Restaurar' in cfg_src)
check('grafico.py não tem expander de parâmetros', 'st.expander' not in Path("pages/grafico.py").read_text(encoding="utf-8"))
check('grafico.py tem get_params()',               'get_params' in Path("pages/grafico.py").read_text(encoding="utf-8"))
check('setups.py tem get_params()',                'get_params' in Path("pages/setups.py").read_text(encoding="utf-8"))
check('backtesting.py tem get_params()',           'get_params' in Path("pages/backtesting.py").read_text(encoding="utf-8"))


passed = sum(1 for s, _ in results if s == "OK")
failed = len(results) - passed
print(f"\nTotal: {len(results)} | Passou: {passed} | Falhou: {failed}")
if failed:
    sys.exit(1)
else:
    print("✅ Todas as páginas OK\n")
