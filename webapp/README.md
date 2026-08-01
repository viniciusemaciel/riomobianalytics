# RioMobiAnalytics — Web Application

Streamlit multi-page app for visualising and managing transit-risk data from
the RioMobiAnalytics pipeline.

## Pages

| # | Nome                    | Arquivo                                | O que faz |
|---|-------------------------|----------------------------------------|-----------|
| — | Home                    | `Home.py`                              | Hero, KPIs do sistema, distribuição de risco, navegação. |
| 1 | Mapa interativo         | `pages/01_Mapa_Interativo.py`          | Folium com paradas coloridas por risco + reclamações por categoria. |
| 2 | Grafo de rede           | `pages/02_Grafo_de_Rede.py`            | Plotly + NetworkX; nós coloridos pelo `risk_score_normalized`. |
| 3 | Gerenciamento de dados  | `pages/03_Gerenciamento_de_Dados.py`   | Upload GTFS/CSV, execução do pipeline ETL, status do sistema. |
| 4 | Explorar detalhes       | `pages/04_Explorar_Detalhes.py`        | Busca dirigida por parada ou protocolo com view detalhada. |
| 5 | Metodologia             | `pages/05_Metodologia.py`              | Como o risco é calculado, ponta a ponta. |

## Estrutura

```
webapp/
├── Home.py                     # Entry point (aparece como "Home" no menu lateral)
├── pages/                      # Multi-page (numeração define a ordem no menu)
│   ├── 01_Mapa_Interativo.py
│   ├── 02_Grafo_de_Rede.py
│   ├── 03_Gerenciamento_de_Dados.py
│   ├── 04_Explorar_Detalhes.py
│   └── 05_Metodologia.py
├── assets/
│   ├── logo_mark.png           # Marca isolada (favicon é derivado dela)
│   ├── logo_full.png           # Marca + wordmark (usado no sidebar)
│   ├── favicon.png             # 64×64 gerado do logo_mark
│   └── style.css               # Design system (Inter + paleta navy/coral/off-white)
└── utils/
    ├── theme.py                # apply_theme, render_hero, render_page_header, badges…
    ├── db_connections.py       # Neo4j driver + Mongo client (cacheados)
    ├── data_fetchers.py        # Queries Cypher/Mongo cacheadas (@st.cache_data ttl=300)
    ├── footer_console.py       # Console de queries no rodapé (colapsada por padrão)
    └── query_logger.py         # Logger em memória por sessão
```

## Design system (`utils/theme.py`)

Helpers reutilizáveis — chamar **`apply_theme()`** em toda página logo após
`st.set_page_config`. Ele injeta o CSS e renderiza a logo no sidebar.

| Helper                | Uso                                                     |
|-----------------------|---------------------------------------------------------|
| `apply_theme()`       | Injeta o CSS global e renderiza a logo no sidebar.      |
| `render_hero(...)`    | Hero navy com gradiente (só na Home).                   |
| `render_page_header(title, subtitle, icon)` | Header padrão das páginas internas. |
| `render_kpi(label, value, hint)`            | Card de métrica com barra coral.    |
| `render_risk_badge(level)`                  | Pill "Alto/Médio/Baixo" (retorna HTML). |
| `render_risk_legend()`                      | Legenda vertical com bolinhas coloridas. |
| `render_empty_state(title, msg)`            | Bloco vazio com borda tracejada.    |
| `section_title(title, hint)`                | Subtítulo com hint em cinza claro.  |
| `get_risk_color(level)`                     | Cor consistente com a legenda.      |
| Constantes            | `BRAND`, `CATEGORY_COLORS`, `PAGE_ICON`.                |

Paleta:
- **Navy** `#0B1F3A` — texto e sidebar
- **Coral** `#F26A4B` — ações primárias e destaque
- **Off-white** `#FAF7F2` — background
- **Alto/Médio/Baixo** — `#D14B3A` / `#E9A23B` / `#3F9E6E`

Tipografia: **Inter** carregada do Google Fonts em `assets/style.css`.

O tema também é declarado em `.streamlit/config.toml` — assim widgets padrão do
Streamlit (`st.metric`, sliders, botões, tabs) já saem coerentes.

## Rodar

Pré-requisito: MongoDB e Neo4j rodando (via `docker-compose up -d` na raiz) e
`.env` configurado com as credenciais.

```bash
# a partir da raiz do repositório
./run_webapp.sh
# ou
streamlit run webapp/Home.py --server.port=8501
```

App em `http://localhost:8501`.

## Cache

- `@st.cache_data(ttl=300)` nas funções de `data_fetchers.py` — resultados
  ficam em cache por 5 minutos.
- `@st.cache_resource` nos drivers de banco em `db_connections.py`.
- Para forçar refresh: pressione **C** no app, ou hamburger menu → *Clear cache*.

## Console de queries (rodapé)

Cada página renderiza `render_query_console()` no fim — expander recolhido com
todas as queries Cypher/Mongo executadas na sessão + latências. Útil pra debug
sem poluir a página.

## Troubleshooting

**`Neo.ClientError.Security.Unauthorized`** — o `NEO4J_PASSWORD` do `.env` não
bate com a senha do container. Verifique em `docker-compose.yml` (variável
`NEO4J_AUTH`).

**`AuthenticationRateLimit`** — o Neo4j baniu temporariamente após várias
tentativas com senha errada. Reinicie o container: `docker-compose restart neo4j`.

**Página em branco / sidebar sem logo** — confira se `webapp/assets/logo_mark.png`
e `logo_full.png` existem.

**Import errors** — rode a partir da raiz do repo, ou:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Adicionando páginas novas

1. Crie `pages/NN_Nome_Da_Pagina.py` (`NN` = ordem no menu; **sem emojis** no
   nome do arquivo — usamos ícones do design system).
2. No topo:
   ```python
   from webapp.utils.theme import apply_theme, render_page_header, PAGE_ICON
   from webapp.utils.footer_console import render_query_console

   st.set_page_config(page_title="...", page_icon=PAGE_ICON, layout="wide")
   apply_theme()
   render_page_header("Título", "Subtítulo", icon="◉")
   ```
3. No fim: `render_query_console()`.

## Adicionando visualizações

1. Adicione a função em `utils/data_fetchers.py` com `@st.cache_data(ttl=300)`.
2. Retorne `pandas.DataFrame` sempre que possível.
3. Para plots use **Plotly** — passe `paper_bgcolor="rgba(0,0,0,0)"` e cores
   de `BRAND` pra manter consistência com o resto do app.

## Stack

- **Streamlit** — framework
- **Plotly** — gráficos interativos
- **Folium** + **streamlit-folium** — mapas
- **NetworkX** — algoritmos de grafo
- **Pandas** — manipulação
- **PyMongo** + **neo4j** — drivers de banco
