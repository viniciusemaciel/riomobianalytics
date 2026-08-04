import sys
from pathlib import Path

import folium
from folium.plugins import MarkerCluster
import streamlit as st
from streamlit_folium import st_folium

sys.path.append(str(Path(__file__).parent.parent.parent))

from webapp.utils.data_fetchers import (
    get_stops_with_risk, get_complaints_by_location, get_stop_details,
    get_stop_complaints, get_complaint_details, get_nearby_complaints,
    get_connected_stops,
)
from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_page_header, render_risk_legend, render_risk_badge,
    render_empty_state, section_title, get_risk_color, CATEGORY_COLORS,
    PAGE_ICON,
)

st.set_page_config(page_title="Mapa Interativo · RioMobiAnalytics",
                   page_icon=PAGE_ICON, layout="wide")

apply_theme()

render_page_header(
    "Mapa interativo",
    "Paradas coloridas por nível de risco total e distribuição geográfica das reclamações",
    icon="◉",
)

tab1, tab2 = st.tabs(["Mapa de risco de paradas", "Mapa de reclamações"])

with tab1:
    section_title("Paradas de trânsito por nível de risco total")

    try:
        stops_df = get_stops_with_risk()
        stops_df = stops_df[stops_df["risk_level"].notna()]
        stops_df["total_complaints"] = stops_df["total_complaints"].fillna(0).astype(int)

        if stops_df.empty:
            render_empty_state(
                "Sem dados de paradas",
                "Execute o pipeline ETL na aba Gerenciamento de dados para popular o banco.",
            )
        else:
            col1, col2 = st.columns([3, 1])

            with col2:
                st.markdown("**Filtros**")

                risk_filter = st.selectbox(
                    "Nível de risco total",
                    ["Todos", "Alto", "Médio-Alto", "Médio-Baixo", "Baixo"],
                    index=0,
                )

                # Filtro de foco em tiroteios (ML)
                tiroteio_filter = st.checkbox(
                    "Foco em tiroteios (ML)",
                    value=False,
                    help="Exibe apenas paradas com probabilidade de tiroteio ≥ 50% "
                         "(modelo XGBoost). Use para identificar zonas de alerta "
                         "mesmo quando não há chamados abertos.",
                )

                min_complaints = st.slider(
                    "Mín. de reclamações",
                    0,
                    int(stops_df["total_complaints"].max()) if "total_complaints" in stops_df else 10,
                    0,
                )

                if risk_filter != "Todos":
                    stops_df = stops_df[stops_df["risk_level"] == risk_filter]
                if tiroteio_filter:
                    stops_df = stops_df[stops_df["risk_score_tiroteio"] >= 0.5]
                stops_df = stops_df[stops_df["total_complaints"] >= min_complaints]

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                m_left, m_right = st.columns(2)
                m_left.metric("Paradas exibidas", len(stops_df))
                m_right.metric(
                    "Risco total médio",
                    f"{stops_df['risk_score_normalized'].mean():.1f}"
                    if not stops_df.empty else "—",
                    help="Média da pontuação de risco total (0-100) das paradas exibidas após filtros.",
                )

                if not stops_df.empty and tiroteio_filter:
                    st.caption(
                        f"Destas, {(stops_df['risk_score_tiroteio'] >= 0.7).sum()} "
                        f"têm probabilidade de tiroteio ≥ 70%"
                    )

                st.markdown("**Legenda**")
                render_risk_legend()

            with col1:
                rio_center = [-22.9068, -43.1729]
                m = folium.Map(location=rio_center, zoom_start=11,
                               tiles="CartoDB positron")

                for _, stop in stops_df.iterrows():
                    color = get_risk_color(stop["risk_level"])
                    tiroteio_pct = stop.get("risk_score_tiroteio", 0) * 100
                    atual_pct = stop.get("risk_score_atual", 0) * 100

                    popup_html = f"""
                        <b>{stop['name']}</b><br>
                        <hr style='margin:4px 0'>
                        <b>Risco Total:</b> {stop['risk_score_normalized']:.1f}/100
                        ({stop['risk_level']})<br>
                        <span style='color:#888;font-size:0.85em'>
                          └ Chamados: {atual_pct:.0f}/100
                          &nbsp;|&nbsp; Tiroteio (ML): {tiroteio_pct:.0f}%
                        </span><br>
                        Reclamações: {int(stop['total_complaints'])}
                    """

                    folium.CircleMarker(
                        location=[stop["lat"], stop["lon"]],
                        radius=6,
                        popup=folium.Popup(popup_html, max_width=260),
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.75,
                        weight=1.5,
                    ).add_to(m)

                folium.LayerControl().add_to(m)
                st_folium(m, width=None, height=600)

            st.divider()
            section_title("Top 10 paradas com maior risco total")

            top_stops = stops_df.nlargest(10, "risk_score_normalized")[
                ["name", "risk_score_normalized", "risk_level",
                 "risk_score_atual", "risk_score_tiroteio",
                 "total_complaints", "id"]
            ]

            hcols = st.columns([2.5, 1, 1, 1, 1, 1, 1])
            hcols[0].markdown("**Parada**")
            hcols[1].markdown("**Total**")
            hcols[2].markdown("**Nível**")
            hcols[3].markdown("**Chamados**")
            hcols[4].markdown("**Tiroteio**")
            hcols[5].markdown("**Recl.**")
            hcols[6].markdown("**Ação**")

            for _, stop in top_stops.iterrows():
                cols = st.columns([2.5, 1, 1, 1, 1, 1, 1])
                cols[0].write(stop["name"])
                cols[1].write(f"{stop['risk_score_normalized']:.1f}")
                cols[2].markdown(render_risk_badge(stop["risk_level"]),
                                 unsafe_allow_html=True)
                cols[3].write(f"{(stop.get('risk_score_atual', 0) or 0) * 100:.0f}")
                cols[4].write(f"{(stop.get('risk_score_tiroteio', 0) or 0) * 100:.0f}%")
                cols[5].write(f"{int(stop['total_complaints'] or 0)}")
                if cols[6].button("Ver", key=f"btn_{stop['id']}",
                                  use_container_width=True):
                    st.session_state.selected_stop_id = stop["id"]
                    st.rerun()

            if "selected_stop_id" in st.session_state:
                st.divider()
                section_title("Detalhes da parada")

                stop_id = st.session_state.selected_stop_id
                try:
                    stop_details = get_stop_details(stop_id)
                    if stop_details:
                        # --- Card de decomposição dos 3 scores ---
                        st.markdown("#### Composição do risco")

                        total_score = (stop_details.get("risk_score_normalized") or 0)
                        atual_score = (stop_details.get("risk_score_atual") or 0) * 100
                        tiroteio_score = (stop_details.get("risk_score_tiroteio") or 0) * 100

                        dc1, dc2, dc3 = st.columns(3)
                        with dc1:
                            st.metric(
                                "Risco Total",
                                f"{total_score:.1f} / 100",
                            )
                            st.markdown(
                                render_risk_badge(stop_details.get("risk_level")),
                                unsafe_allow_html=True,
                            )
                        with dc2:
                            st.metric(
                                "Risco por Chamados",
                                f"{atual_score:.0f} / 100",
                                help="Agregação dos chamados 1746 abertos próximos à parada.",
                            )
                        with dc3:
                            st.metric(
                                "Risco de Tiroteio (ML)",
                                f"{tiroteio_score:.0f}%",
                                help="Probabilidade de tiroteio num raio de 500m — modelo XGBoost.",
                            )
                            shootout_level = (
                                "Alto" if tiroteio_score >= 70
                                else "Médio-Alto" if tiroteio_score >= 40
                                else "Baixo"
                            )
                            st.markdown(
                                render_risk_badge(shootout_level),
                                unsafe_allow_html=True,
                            )

                        # Barra visual de proporção
                        bar_atual = atual_score / 100
                        bar_tiroteio = tiroteio_score / 100
                        bar_total = total_score / 100
                        st.caption(
                            f"Fórmula: (0.6 × {atual_score:.0f} + 1.4 × {tiroteio_score:.0f}%) / 2 = {total_score:.1f}"
                        )

                        st.divider()

                        c1, c2 = st.columns(2)
                        with c1:
                            st.metric(
                                "Nível de risco",
                                stop_details.get("risk_level") or "Sem risco",
                            )
                        with c2:
                            st.metric("Reclamações totais",
                                      stop_details.get("total_complaints") or 0)

                        routes = stop_details.get("routes", [])
                        if routes:
                            st.write(f"**Rotas que servem**: {', '.join(filter(None, routes))}")

                        st.markdown("#### Reclamações afetando esta parada")
                        complaints_df = get_stop_complaints(stop_id)
                        if not complaints_df.empty:
                            by_category = complaints_df["servico"].value_counts()
                            st.write("**Por categoria**")
                            for category, count in by_category.items():
                                st.write(f"  • {category}: {count}")
                            st.write("**Reclamações recentes**")
                            for _, comp in complaints_df.head(5).iterrows():
                                st.write(f"• **{comp['protocolo']}** — {comp['servico']} · {comp['bairro']}")
                                if comp["descricao"]:
                                    st.caption(comp["descricao"][:100] + "...")
                        else:
                            st.info("Nenhuma reclamação afetando esta parada.")

                        st.markdown("#### Paradas conectadas (próximo nó)")
                        connected = get_connected_stops(stop_id, hops=1)
                        if not connected.empty:
                            st.dataframe(
                                connected[["name", "risk_level", "total_complaints"]],
                                use_container_width=True, hide_index=True,
                            )
                        else:
                            st.info("Nenhuma parada conectada encontrada.")

                        if st.button("Fechar detalhes"):
                            del st.session_state.selected_stop_id
                            st.rerun()
                    else:
                        st.warning("Parada não encontrada.")
                except Exception as e:
                    st.error(f"Erro ao carregar detalhes: {e}")

    except Exception as e:
        st.error(f"Erro ao carregar dados de paradas: {e}")

with tab2:
    section_title("Distribuição de reclamações")

    try:
        complaints_df = get_complaints_by_location()

        if complaints_df.empty:
            render_empty_state(
                "Sem reclamações",
                "Nenhuma reclamação disponível — verifique o carregamento do CSV do 1746.",
            )
        else:
            col1, col2 = st.columns([3, 1])

            with col2:
                st.markdown("**Filtros**")
                category_filter = st.multiselect(
                    "Categorias",
                    options=complaints_df["servico"].unique(),
                    default=None,
                )
                if category_filter:
                    complaints_df = complaints_df[complaints_df["servico"].isin(category_filter)]

                st.metric("Reclamações exibidas", len(complaints_df))
                st.caption("Exibindo até 1000 reclamações — use os filtros de categoria para refinar.")

                st.markdown("**Legenda por categoria**")
                for cat, color in CATEGORY_COLORS.items():
                    st.markdown(
                        f"""<div class='rm-legend__row'>
                            <span class='rm-legend__dot' style='background:{color}'></span>
                            <span>{cat}</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )

            with col1:
                rio_center = [-22.9068, -43.1729]
                m = folium.Map(location=rio_center, zoom_start=11,
                               tiles="CartoDB positron")
                cluster = MarkerCluster().add_to(m)
                for _, complaint in complaints_df.iterrows():
                    color = CATEGORY_COLORS.get(complaint["servico"], "#8A93A3")
                    folium.CircleMarker(
                        location=[complaint["lat"], complaint["lon"]],
                        radius=4,
                        popup=folium.Popup(f"""
                            <b>Reclamação {complaint['protocolo']}</b><br>
                            Categoria: {complaint['servico']}
                        """, max_width=200),
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.65,
                        weight=1,
                    ).add_to(cluster)
                st_folium(m, width=None, height=600)

            st.divider()
            section_title("Detalhes de reclamações")

            if "selected_complaint_protocolo" in st.session_state:
                st.subheader(f"Reclamação: {st.session_state.selected_complaint_protocolo}")
                protocolo = st.session_state.selected_complaint_protocolo
                try:
                    complaint_details = get_complaint_details(protocolo)
                    if complaint_details:
                        c1, c2 = st.columns(2)
                        c1.metric("Categoria", complaint_details.get("servico", "N/A"))
                        c2.metric("Paradas afetadas",
                                  int(complaint_details.get("stop_count", 0)))
                        st.write(f"**Bairro**: {complaint_details.get('bairro', 'N/A')}")

                        data_abertura = complaint_details.get("data_abertura")
                        if data_abertura:
                            st.write(f"**Data de abertura**: {data_abertura}")

                        descricao = complaint_details.get("descricao")
                        if descricao:
                            st.write(f"**Descrição**: {descricao}")

                        affected_stops = complaint_details.get("affected_stops", [])
                        if affected_stops:
                            st.write("**Paradas afetadas**")
                            for stop_name in filter(None, affected_stops):
                                st.write(f"  • {stop_name}")

                        st.markdown("#### Reclamações próximas")
                        lat = complaint_details.get("lat")
                        lon = complaint_details.get("lon")
                        if lat and lon:
                            nearby = get_nearby_complaints(lat, lon, radius_meters=500)
                            if not nearby.empty:
                                nearby_filtered = nearby[nearby["protocolo"] != protocolo].head(10)
                                if not nearby_filtered.empty:
                                    st.dataframe(
                                        nearby_filtered[["protocolo", "servico", "bairro"]],
                                        use_container_width=True, hide_index=True,
                                    )
                                else:
                                    st.info("Nenhuma reclamação próxima.")
                            else:
                                st.info("Nenhuma reclamação próxima.")

                        if st.button("Fechar detalhes"):
                            del st.session_state.selected_complaint_protocolo
                            st.rerun()
                    else:
                        st.warning("Reclamação não encontrada.")
                except Exception as e:
                    st.error(f"Erro ao carregar detalhes da reclamação: {e}")
            else:
                st.write(f"**Total de reclamações**: {len(complaints_df)}")
                if not complaints_df.empty:
                    st.write("**Por categoria**")
                    by_category = complaints_df["servico"].value_counts()
                    for category, count in by_category.items():
                        st.write(f"  • {category}: {count}")

                    st.write("**Amostra**")
                    for _, comp in complaints_df.head(10).iterrows():
                        if st.button(
                            f"⌕ {comp['protocolo']} — {comp['servico']}",
                            key=f"comp_{comp['protocolo']}",
                        ):
                            st.session_state.selected_complaint_protocolo = comp["protocolo"]
                            st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar dados de reclamações: {e}")

st.info("Clique em **Ver** na tabela de paradas ou em um protocolo para abrir o detalhamento completo.")

render_query_console()
