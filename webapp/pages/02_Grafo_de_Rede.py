import sys
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from webapp.utils.data_fetchers import (
    get_network_graph_data, get_network_around_stop, get_stops_with_risk,
)
from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_page_header, render_empty_state, section_title,
    render_risk_badge, BRAND, PAGE_ICON,
)

st.set_page_config(page_title="Grafo de Rede · RioMobiAnalytics",
                   page_icon=PAGE_ICON, layout="wide")

apply_theme()

render_page_header(
    "Grafo de rede de trânsito",
    "Topologia da rede — cada nó é uma parada, cada aresta é uma conexão CONNECTS_TO no Neo4j",
    icon="◈",
)

with st.expander("O que este grafo mostra?", expanded=False):
    st.markdown(
        """
        Cada **nó** é uma parada de ônibus do GTFS. Cada **aresta** é uma
        relação `CONNECTS_TO` no Neo4j — ou seja, duas paradas que aparecem
        em sequência dentro de pelo menos uma viagem de alguma rota.

        A **cor do nó** é o `risk_level` (Alto / Médio / Baixo) atribuído por
        ranking, o mesmo mostrado no Mapa Interativo e na tabela abaixo:

        - 🔴 **Alto** — top 33% do ranking de risco entre paradas com reclamação
        - 🟡 **Médio** — 33% intermediário
        - 🟢 **Baixo** — 33% inferior, incluindo paradas sem reclamação

        **Duas formas de gerar o subgrafo:**

        1. **Amostra geral** — pega as primeiras _N_ arestas do banco. Ordem
           definida pelo Neo4j, boa para uma visão panorâmica.
        2. **A partir de uma parada** — BFS (busca em largura) começando na
           parada escolhida, coletando até _N_ arestas. Sempre gera um
           subgrafo **conectado**, útil para explorar vizinhança.

        A distribuição de níveis no cabeçalho do grafo mostra o viés da
        amostra atual — se aparecer muito verde, aumente o slider ou troque
        a parada de origem.
        """
    )

try:
    stops_df = get_stops_with_risk()

    if stops_df.empty:
        render_empty_state(
            "Sem dados de rede",
            "Execute o pipeline ETL para popular a rede de conexões entre paradas.",
        )
    else:
        col1, col2 = st.columns([3, 1])

        with col2:
            st.markdown("**Configurações**")

            mode = st.radio(
                "Fonte do subgrafo",
                ["Amostra geral", "A partir de uma parada"],
                index=0,
                help=(
                    "Amostra geral = primeiras N arestas do banco. "
                    "A partir de uma parada = BFS conectada a partir da origem."
                ),
            )

            selected_stop_id = None
            if mode == "A partir de uma parada":
                nameful_stops = stops_df[stops_df["name"].notna()].copy()
                nameful_stops = nameful_stops.sort_values("name")
                labels = nameful_stops.apply(
                    lambda r: f"{r['name']} · {(r['risk_level'] or 'Sem risco')}",
                    axis=1,
                ).tolist()
                ids = nameful_stops["id"].tolist()

                default_idx = 0
                for i, lvl in enumerate(nameful_stops["risk_level"].tolist()):
                    if lvl == "Alto":
                        default_idx = i
                        break

                idx = st.selectbox(
                    "Parada de origem",
                    options=range(len(ids)),
                    index=default_idx,
                    format_func=lambda i: labels[i],
                    help="A BFS começa aqui e expande pelas conexões CONNECTS_TO.",
                )
                selected_stop_id = ids[idx]

            max_edges = st.slider(
                "Máximo de arestas",
                min_value=100, max_value=2000, value=500, step=100,
                help=(
                    "Quantas conexões carregar do Neo4j. "
                    "Mais arestas = mais nós visíveis, mas render mais lento."
                ),
            )
            show_labels = st.checkbox(
                "Mostrar rótulos de nós", value=False,
                help="Nomes das paradas ao lado dos círculos (útil com poucos nós).",
            )
            layout_algo = st.selectbox(
                "Algoritmo de layout",
                ["Spring", "Kamada-Kawai", "Circular"], index=0,
                help=(
                    "Spring = força elástica (padrão). "
                    "Kamada-Kawai = distâncias respeitam caminhos. "
                    "Circular = tudo em torno de um círculo."
                ),
            )

        # Fetch edges according to the chosen mode
        with st.spinner("Carregando grafo..."):
            if mode == "A partir de uma parada" and selected_stop_id:
                network_df = get_network_around_stop(selected_stop_id, max_edges)
            else:
                network_df = get_network_graph_data(max_edges)

        if network_df.empty:
            render_empty_state(
                "Nenhuma aresta encontrada",
                "A parada escolhida pode não ter conexões CONNECTS_TO no banco.",
            )
        else:
            G = nx.Graph()
            for _, row in network_df.iterrows():
                G.add_edge(row["source"], row["target"],
                           distance=row["distance"], cost=row["cost"])

            stop_dict = stops_df.set_index("id").to_dict("index")
            for node in G.nodes():
                if node in stop_dict:
                    G.nodes[node].update(stop_dict[node])

            if layout_algo == "Spring":
                pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
            elif layout_algo == "Kamada-Kawai":
                pos = nx.kamada_kawai_layout(G)
            else:
                pos = nx.circular_layout(G)

            edge_x, edge_y = [], []
            for edge in G.edges():
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

            edge_trace = go.Scatter(
                x=edge_x, y=edge_y, mode="lines",
                line=dict(width=0.7, color="rgba(255,255,255,0.20)"),
                hoverinfo="none", showlegend=False,
            )

            # Cor do nó vem do risk_level (categórico), NÃO do risk_score.
            # Isso garante consistência com o Mapa Interativo e a tabela abaixo.
            LEVEL_COLOR = {
                "Alto":      BRAND["high"],
                "Médio":     BRAND["med"],
                "Medio":     BRAND["med"],
                "Baixo":     BRAND["low"],
                "Sem risco": "#8A93A3",
            }

            node_x, node_y, node_text, node_marker_color, node_size = [], [], [], [], []
            level_count = {"Alto": 0, "Médio": 0, "Baixo": 0, "Sem risco": 0}
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                info = stop_dict.get(node, {})
                risk_norm = info.get("risk_score_normalized") or 0
                raw_level = info.get("risk_level")
                level = raw_level or "Sem risco"
                if level == "Medio":
                    level = "Médio"
                level_count[level] = level_count.get(level, 0) + 1
                is_origin = (node == selected_stop_id)
                node_text.append(
                    (f"<b>★ ORIGEM</b><br>" if is_origin else "") +
                    f"<b>{info.get('name') or 'Desconhecido'}</b><br>"
                    f"Risco: {risk_norm:.1f}/100 · <b>{level}</b><br>"
                    f"Reclamações: {int(info.get('total_complaints') or 0)}"
                )
                node_marker_color.append(LEVEL_COLOR.get(level, "#8A93A3"))
                node_size.append(20 if is_origin else 12)

            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode="markers+text" if show_labels else "markers",
                hoverinfo="text",
                text=[stop_dict.get(node, {}).get("name", "")[:10]
                      for node in G.nodes()] if show_labels else None,
                textposition="top center",
                textfont=dict(size=10, color="#E4E7EE"),
                hovertext=node_text,
                marker=dict(
                    color=node_marker_color,
                    size=node_size,
                    line=dict(width=1.4, color=BRAND["navy"]),
                ),
                showlegend=False,
            )

            # Legend traces (invisible points, apenas pra popular a legenda)
            legend_traces = [
                go.Scatter(
                    x=[None], y=[None], mode="markers",
                    marker=dict(size=12, color=LEVEL_COLOR[lvl],
                                line=dict(width=1.4, color=BRAND["navy"])),
                    name=lvl, showlegend=True,
                )
                for lvl in ["Alto", "Médio", "Baixo"]
            ]

            fig = go.Figure(
                data=[edge_trace, node_trace] + legend_traces,
                layout=go.Layout(
                    title=dict(
                        text=(
                            f"<b>{len(G.nodes())}</b> nós · <b>{len(G.edges())}</b> arestas · "
                            f"<span style='color:{BRAND['high']}'>{level_count['Alto']} Alto</span> · "
                            f"<span style='color:{BRAND['med']}'>{level_count['Médio']} Médio</span> · "
                            f"<span style='color:{BRAND['low']}'>{level_count['Baixo']} Baixo</span>"
                        ),
                        font=dict(size=13, color="#E4E7EE"),
                        x=0.01,
                    ),
                    showlegend=True,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom", y=1.02,
                        xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#E4E7EE", size=11),
                    ),
                    hovermode="closest",
                    margin=dict(b=0, l=0, r=0, t=48),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=680,
                    paper_bgcolor=BRAND["navy"],
                    plot_bgcolor=BRAND["navy"],
                ),
            )

            with col1:
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False})

            st.divider()
            section_title("Estatísticas do subgrafo")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nós", len(G.nodes()))
            c2.metric("Arestas", len(G.edges()))
            avg_degree = sum(dict(G.degree()).values()) / max(len(G.nodes()), 1)
            c3.metric(
                "Grau médio", f"{avg_degree:.2f}",
                help="Quantas conexões cada parada tem em média neste subgrafo.",
            )
            c4.metric(
                "Densidade", f"{nx.density(G):.4f}",
                help=(
                    "Razão entre arestas existentes e o total possível. "
                    "Redes de transporte reais são esparsas (densidade baixa)."
                ),
            )

            st.divider()
            section_title("Paradas com maior risco no subgrafo")

            top_stops_by_risk = sorted(
                [(node_id, stop_dict.get(node_id, {}).get("risk_score_normalized") or 0)
                 for node_id in G.nodes() if node_id in stop_dict],
                key=lambda x: x[1], reverse=True,
            )[:10]

            hcols = st.columns([4, 1, 1, 1])
            hcols[0].markdown("**Parada**")
            hcols[1].markdown("**Risco**")
            hcols[2].markdown("**Nível**")
            hcols[3].markdown("**Reclamações**")

            for node_id, risk_norm in top_stops_by_risk:
                info = stop_dict[node_id]
                cols = st.columns([4, 1, 1, 1])
                cols[0].write(info.get("name") or "Desconhecido")
                cols[1].write(f"{risk_norm:.1f}")
                cols[2].markdown(render_risk_badge(info.get("risk_level")),
                                 unsafe_allow_html=True)
                cols[3].write(int(info.get("total_complaints") or 0))

except Exception as e:
    st.error(f"Erro ao carregar grafo de rede: {e}")

st.info(
    "Passe o mouse sobre os nós para detalhes. "
    "A parada de origem (quando escolhida) aparece com um marcador maior. "
    "A distribuição de níveis no cabeçalho do grafo mostra o viés da amostra atual."
)

render_query_console()
