import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from webapp.utils.data_fetchers import get_stops_with_risk, get_system_stats
from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_hero, render_kpi, section_title, BRAND, PAGE_ICON,
)

st.set_page_config(
    page_title="RioMobiAnalytics",
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

render_hero(
    title_html="<em>Rio</em>MobiAnalytics",
    subtitle=(
        "Plataforma de análise de risco de trânsito no Rio de Janeiro — "
        "integra a rede GTFS de ônibus com reclamações do 1746 e um modelo "
        "preditivo de tiroteios para identificar paradas críticas."
    ),
    eyebrow="Pós-graduação em Ciência de Dados",
)

try:
    stats = get_system_stats()

    section_title("Visão geral do sistema")

    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi(
            "Paradas de ônibus",
            f"{stats.get('total_stops', 0):,}".replace(",", "."),
            "nós na rede GTFS",
        )
    with c2:
        render_kpi(
            "Rotas de trânsito",
            f"{stats.get('total_routes', 0):,}".replace(",", "."),
            "linhas ativas",
        )
    with c3:
        render_kpi(
            "Reclamações 1746",
            f"{stats.get('total_complaints', 0):,}".replace(",", "."),
            "chamados vinculados a paradas",
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    avg_risk = stats.get("avg_risk") or 0
    high_risk = stats.get("high_risk_stops", 0)
    high_tiroteio = stats.get("high_tiroteio_stops", 0)

    c4, c5, c6 = st.columns(3)
    with c4:
        render_kpi(
            "Pontuação média do sistema",
            f"{avg_risk:.1f} / 100",
            "média do risco total normalizado (0–100)",
        )
    with c5:
        render_kpi(
            "Paradas de alto risco total",
            f"{high_risk:,}".replace(",", "."),
            "tercil superior do ranking combinado",
        )
    with c6:
        render_kpi(
            "Alto risco de tiroteio (ML)",
            f"{high_tiroteio:,}".replace(",", "."),
            "prob. de tiroteio ≥ 50% — modelo XGBoost",
        )

    with st.expander("Como esses números são calculados?"):
        st.markdown(
            """
            **Risco Total** (métrica principal) combina duas fontes:

            1. **Risco por Chamados** — agregação dos chamados 1746 abertos
               próximos à parada (Segurança, Iluminação, etc.), com peso por
               categoria e fórmula de saturação: `risk_sum / (risk_sum + 10)`.

            2. **Risco de Tiroteio** — probabilidade prevista por um modelo
               XGBoost treinado com histórico de tiroteios (Fogo Cruzado) e
               chamados 1746. AUC 0.71, 16 features (geografia, rede, lags).

            **Fórmula final**: `(0,6 × atual + 1,4 × tiroteio) / 2`

            O resultado é normalizado 0–100 e classificado por **quartis do
            range de valores**: divide-se o intervalo [min, max] em 4 faixas
            e cada parada recebe o nível conforme a faixa em que cai
            (Baixo / Médio-Baixo / Médio-Alto / Alto). Detalhes na
            página **Metodologia**.
            """
        )

    # ---------------- Distribuição de risco ----------------
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    section_title(
        "Distribuição de risco total",
        "quantas paradas em cada nível — classificação por quartis do range",
    )

    try:
        stops_df = get_stops_with_risk()
        if not stops_df.empty and stops_df["risk_level"].notna().any():
            level_order = ["Baixo", "Médio-Baixo", "Médio-Alto", "Alto"]
            # Inverte a ordem pra que Alto fique no topo do gráfico horizontal
            level_counts = (
                stops_df["risk_level"]
                .dropna()
                .value_counts()
                .reindex(level_order, fill_value=0)
            )
            color_map = {
                "Alto":         BRAND["high"],
                "Médio-Alto":   BRAND["med_high"],
                "Médio-Baixo":  BRAND["med_low"],
                "Baixo":        BRAND["low"],
            }

            chart_col, legend_col = st.columns([3, 1])

            with chart_col:
                fig = go.Figure(
                    go.Bar(
                        x=level_counts.values,
                        y=level_counts.index,
                        orientation="h",
                        marker=dict(color=[color_map[l] for l in level_counts.index]),
                        text=[f"{v:,}".replace(",", ".") for v in level_counts.values],
                        textposition="outside",
                        textfont=dict(color=BRAND["navy"], size=12),
                        hovertemplate="<b>%{y}</b><br>%{x} paradas<extra></extra>",
                    )
                )
                fig.update_layout(
                    height=280,
                    margin=dict(l=10, r=40, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(
                        showgrid=True, gridcolor="#E4E7EE", zeroline=False,
                        tickfont=dict(color=BRAND["navy"], size=11),
                    ),
                    yaxis=dict(
                        tickfont=dict(color=BRAND["navy"], size=12,
                                      family="Inter, sans-serif"),
                        automargin=True,
                    ),
                    bargap=0.35,
                )
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False})

            with legend_col:
                total = int(level_counts.sum())
                pcts = {l: (level_counts[l] / total * 100) if total else 0 for l in level_order}

                def _block(label: str, pct: float, color: str) -> str:
                    return (
                        f"<div style='margin-bottom:10px;'>"
                        f"  <div style='font-size:0.72rem;text-transform:uppercase;"
                        f"              letter-spacing:0.08em;color:#8A93A3;"
                        f"              font-weight:600;margin-bottom:2px;'>{label}</div>"
                        f"  <div style='font-size:1.25rem;font-weight:700;"
                        f"              color:{color};line-height:1.1;'>{pct:.1f}%</div>"
                        f"</div>"
                    )

                st.markdown(
                    f"""
                    <div style='padding:8px 4px;'>
                      <div style='font-size:0.72rem;text-transform:uppercase;
                                  letter-spacing:0.08em;color:#8A93A3;
                                  font-weight:600;margin-bottom:2px;'>Paradas classificadas</div>
                      <div style='font-size:1.35rem;font-weight:700;
                                  color:{BRAND["navy"]};line-height:1.1;
                                  margin-bottom:14px;'>{total:,}</div>
                      {_block("% em Alto",         pcts["Alto"],         BRAND["high"])}
                      {_block("% em Médio-Alto",   pcts["Médio-Alto"],   BRAND["med_high"])}
                      {_block("% em Médio-Baixo",  pcts["Médio-Baixo"],  BRAND["med_low"])}
                      {_block("% em Baixo",        pcts["Baixo"],        BRAND["low"])}
                    </div>
                    """.replace(",", "."),
                    unsafe_allow_html=True,
                )
        else:
            st.info("Sem dados de nível de risco — rode o pipeline ETL primeiro.")
    except Exception as e:
        st.caption(f"Distribuição indisponível: {e}")

    # ---------------- Nav cards ----------------
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    section_title("Explorar", "seis visões sobre o mesmo dataset")

    nav_items = [
        ("◉", "Mapa interativo",       "Paradas coloridas por nível de risco total e distribuição geográfica das reclamações do 1746.", "pages/01_Mapa_Interativo.py"),
        ("◈", "Grafo de rede",         "Topologia da rede de trânsito com nós coloridos pelo risco total de cada parada.",              "pages/02_Grafo_de_Rede.py"),
        ("↑", "Gerenciamento de dados", "Upload de arquivos GTFS/CSV e execução do pipeline ETL passo a passo.",                   "pages/03_Gerenciamento_de_Dados.py"),
        ("⌕", "Explorar detalhes",     "Busca dirigida por parada ou protocolo com visão detalhada de vínculos.",                  "pages/04_Explorar_Detalhes.py"),
        ("∫", "Metodologia",           "Como o risco total de cada parada é calculado — chamados, modelo preditivo e fórmula combinada.", "pages/05_Metodologia.py"),
        ("⟐", "Modelo preditivo",      "Playground interativo do XGBoost — inspecione features, simule cenários e entenda as predições.", "pages/06_Modelo_Preditivo.py"),
    ]

    top_row = st.columns(3)
    bottom_row = st.columns(3)
    cell_containers = list(top_row) + list(bottom_row)

    for (icon, title, desc, page), cell in zip(nav_items, cell_containers):
        with cell:
            st.markdown(
                f"""
                <div class='rm-nav-card'>
                    <div class='rm-nav-card__icon'>{icon}</div>
                    <div class='rm-nav-card__title'>{title}</div>
                    <div class='rm-nav-card__desc'>{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link(page, label=f"Abrir {title} →")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    with st.expander("Detalhes técnicos"):
        st.markdown(
            """
            **Stack**

            - **MongoDB** — dados brutos das reclamações do 1746 com indexação geoespacial.
            - **Neo4j** — banco de grafo para a rede de trânsito e o relacionamento parada ↔ reclamação.
            - **XGBoost** — modelo preditivo de tiroteios (AUC 0.71), artefatos em `artifacts/`.
            - **Streamlit + Folium + Plotly** — camada de visualização.

            **Cache**

            Dados de leitura são cacheados por 5 minutos no processo do Streamlit
            (`@st.cache_data(ttl=300)`). Após executar o pipeline ETL, use o botão
            *Atualizar* do console de queries no rodapé ou recarregue a página.
            """
        )

except Exception as e:
    st.error(f"Erro ao carregar dados do sistema: {e}")
    st.info("Certifique-se de que MongoDB e Neo4j estão em execução e acessíveis.")

render_query_console()
