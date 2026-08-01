import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from webapp.utils.data_fetchers import (
    get_stops_with_risk, get_stop_details, get_stop_complaints,
    get_stop_routes, get_connected_stops, get_complaint_details,
    get_nearby_complaints, get_complaints_by_location,
)
from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_page_header, render_empty_state, section_title,
    render_risk_badge, PAGE_ICON,
)

st.set_page_config(page_title="Explorar Detalhes · RioMobiAnalytics",
                   page_icon=PAGE_ICON, layout="wide")

apply_theme()

render_page_header(
    "Explorador de detalhes",
    "Busca dirigida por parada ou protocolo com visão detalhada de vínculos",
    icon="⌕",
)

tab1, tab2 = st.tabs(["Explorar parada", "Explorar reclamação"])

with tab1:
    section_title("Pesquisar parada")

    stops_df = get_stops_with_risk()

    if stops_df.empty:
        render_empty_state(
            "Sem dados de paradas",
            "Execute o pipeline ETL para popular o banco.",
        )
    else:
        selected_stop_name = st.selectbox(
            "Selecione uma parada",
            options=sorted(stops_df[stops_df["name"].notna()]["name"].unique()),
            key="stop_search",
        )

        selected_stop = stops_df[stops_df["name"] == selected_stop_name].iloc[0] \
            if selected_stop_name else None

        if selected_stop is not None:
            stop_id = selected_stop["id"]
            try:
                stop_details = get_stop_details(stop_id)
                if stop_details:
                    st.divider()
                    section_title("Visão geral")

                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Nível de risco**")
                        st.markdown(
                            render_risk_badge(stop_details.get("risk_level")),
                            unsafe_allow_html=True,
                        )
                    with c2:
                        risk_norm = stop_details.get("risk_score_normalized") or 0
                        st.metric("Pontuação de risco", f"{risk_norm:.1f} / 100")

                    with st.expander("Como esses valores são calculados?"):
                        st.markdown(
                            """
                            1. Cada reclamação recebe um **peso** conforme sua categoria (Segurança=1.5, Iluminação=0.6, etc.).
                            2. A parada acumula a soma dos pesos das reclamações que a afetam (`risk_sum`).
                            3. O `risk_score` bruto é `risk_sum / (risk_sum + 10)` — saturação para [0, 1).
                            4. O `risk_score_normalized` reescala para [0, 100] via min-max sobre todas as paradas.
                            5. O `Nível de risco` classifica por ranking: top 33% = Alto, meio 33% = Médio, resto = Baixo.

                            Detalhes completos na página **Metodologia**.
                            """
                        )

                    st.divider()
                    section_title("Informações de reclamações")
                    st.metric(
                        "Total de reclamações",
                        int(stop_details.get("total_complaints") or 0),
                    )

                    st.divider()
                    section_title("Rotas que servem esta parada")
                    routes_df = get_stop_routes(stop_id)
                    if not routes_df.empty:
                        hcols = st.columns([1, 3, 1, 1])
                        hcols[0].markdown("**Rota**")
                        hcols[1].markdown("**Nome**")
                        hcols[2].markdown("**Tipo**")
                        hcols[3].markdown("**Risco médio**")
                        for _, route in routes_df.iterrows():
                            cols = st.columns([1, 3, 1, 1])
                            cols[0].write(route["short_name"])
                            cols[1].write(route["long_name"] if route["long_name"] else "—")
                            cols[2].write(route["type"] if route["type"] else "—")
                            avg = route.get("avg_risk")
                            cols[3].write(f"{avg:.1f}" if avg is not None else "—")
                    else:
                        st.info("Nenhuma rota encontrada para esta parada.")

                    st.divider()
                    section_title("Reclamações afetando esta parada")
                    complaints_df = get_stop_complaints(stop_id)
                    if not complaints_df.empty:
                        st.markdown("**Distribuição por categoria**")
                        by_category = complaints_df["servico"].value_counts()
                        for category, count in by_category.items():
                            st.write(f"  • {category}: {count}")

                        st.markdown("**Lista detalhada**")
                        for _, comp in complaints_df.iterrows():
                            with st.expander(f"{comp['protocolo']} — {comp['servico']}"):
                                st.write(f"**Data**: {comp['data_abertura']}")
                                if comp["bairro"]:
                                    st.write(f"**Bairro**: {comp['bairro']}")
                                if comp["descricao"]:
                                    st.write(f"**Descrição**: {comp['descricao']}")
                    else:
                        st.info("Nenhuma reclamação afetando esta parada.")

                    st.divider()
                    section_title("Paradas conectadas")
                    connected_df = get_connected_stops(stop_id, hops=1)
                    if not connected_df.empty:
                        st.dataframe(
                            connected_df[["name", "risk_level", "total_complaints"]],
                            use_container_width=True, hide_index=True,
                        )
                    else:
                        st.info("Nenhuma parada diretamente conectada.")
                else:
                    st.error("Parada não encontrada.")
            except Exception as e:
                st.error(f"Erro ao carregar detalhes da parada: {e}")

with tab2:
    section_title("Pesquisar reclamação")

    complaints_df = get_complaints_by_location()

    if complaints_df.empty:
        render_empty_state("Sem reclamações", "Nenhum dado de reclamação disponível.")
    else:
        protocolo = st.text_input(
            "Número do protocolo",
            placeholder="Ex.: 2024001234",
        )

        if protocolo:
            try:
                complaint_details = get_complaint_details(protocolo)
                if complaint_details:
                    st.divider()
                    section_title("Detalhes da reclamação")

                    c1, c2 = st.columns(2)
                    c1.metric("Categoria", complaint_details.get("servico", "N/A"))
                    c2.metric("Paradas afetadas",
                              int(complaint_details.get("stop_count", 0)))

                    st.divider()
                    section_title("Informações")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Data de abertura**: {complaint_details.get('data_abertura', 'N/A')}")
                        st.write(f"**Bairro**: {complaint_details.get('bairro', 'N/A')}")
                    with c2:
                        st.write(f"**Latitude**: {complaint_details.get('lat', 'N/A')}")
                        st.write(f"**Longitude**: {complaint_details.get('lon', 'N/A')}")

                    descricao = complaint_details.get("descricao")
                    if descricao:
                        st.divider()
                        section_title("Descrição")
                        st.write(descricao)

                    affected_stops = complaint_details.get("affected_stops", [])
                    if affected_stops:
                        st.divider()
                        section_title("Paradas afetadas")
                        for stop_name in filter(None, affected_stops):
                            st.write(f"  • {stop_name}")

                    st.divider()
                    section_title("Reclamações próximas", "raio de 500 m")
                    lat = complaint_details.get("lat")
                    lon = complaint_details.get("lon")
                    if lat and lon:
                        try:
                            nearby = get_nearby_complaints(lat, lon, radius_meters=500)
                            if not nearby.empty:
                                nearby_filtered = nearby[nearby["protocolo"] != protocolo]
                                if not nearby_filtered.empty:
                                    st.dataframe(
                                        nearby_filtered[["protocolo", "servico", "bairro"]],
                                        use_container_width=True, hide_index=True,
                                    )
                                else:
                                    st.info("Nenhuma reclamação próxima.")
                            else:
                                st.info("Nenhuma reclamação próxima.")
                        except Exception as e:
                            st.warning(f"Erro ao buscar reclamações próximas: {e}")
                    else:
                        st.warning("Coordenadas da reclamação não disponíveis.")
                else:
                    st.warning(f"Reclamação {protocolo} não encontrada.")
            except Exception as e:
                st.error(f"Erro ao carregar detalhes da reclamação: {e}")
        else:
            st.info("Digite um protocolo para buscar detalhes.")

st.divider()
st.info("Visão completa de paradas e reclamações — inclui distribuição por categoria e vínculos.")

render_query_console()
