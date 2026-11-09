"""Mapa — tela principal: índice de risco de cada parada, filtros e painel da parada."""
import html

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import config
from webapp.utils.data_fetchers import (
    get_complaint_details, get_complaints_by_location, get_connected_stops,
    get_route_stop_ids, get_routes_with_metrics, get_stop_complaints, get_stop_details,
    get_stops_with_risk, get_system_stats,
)
from webapp.utils.insights import MESES_ABREV, shootings_by_month
from webapp.utils.state import get_selected, go as go_page, set_selected
from webapp.utils.theme import (
    CATEGORY_COLORS, LEVEL_COLORS, LEVELS, LINE, MUTED, NAVY, NO_LEVEL_COLOR,
    ORANGE, empty_state, fmt_int, get_risk_color, legend_html, level_legend,
    normalize_level, note, plotly_layout, risk_badge, selection_chip, stat_band,
)

RIO_CENTER = [-22.905, -43.33]
LAYERS = ["Índice de risco", "Tiroteio", "Reclamações"]
TIRO_BINS = [(0.70, "≥ 70"), (0.50, "50 a 69"), (0.25, "25 a 49"), (0.0, "< 25")]


def tiro_color(score: float) -> str:
    score = score or 0
    colors = [LEVEL_COLORS["Alto"], LEVEL_COLORS["Médio-Alto"], LEVEL_COLORS["Médio-Baixo"], LEVEL_COLORS["Baixo"]]
    for (cut, _), color in zip(TIRO_BINS, colors):
        if score >= cut:
            return color
    return colors[-1]


def tiles_layer(m: folium.Map) -> None:
    key = config._secret("MAPTILER_API_KEY")
    if key:
        folium.TileLayer(
            tiles=f"https://api.maptiler.com/maps/dataviz-light/256/{{z}}/{{x}}/{{y}}{{r}}.png?key={key}",
            attr='<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> '
                 '<a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap</a>',
            name="MapTiler Dataviz", max_zoom=19,
        ).add_to(m)
    else:
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            name="CartoDB Positron", subdomains="abcd", max_zoom=19,
        ).add_to(m)


def stops_geojson(df: pd.DataFrame, layer: str) -> dict:
    feats = []
    for row in df.itertuples(index=False):
        idx = float(row.risk_score_normalized or 0)
        tiro = float(row.risk_score_tiroteio or 0)
        if layer == "Tiroteio":
            color = tiro_color(tiro)
            order = tiro
        else:
            color = get_risk_color(row.risk_level)
            order = idx / 100
        radius = 1.8 + 3.0 * max(0.0, min(order, 1.0)) ** 1.5
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(row.lon), float(row.lat)]},
            "properties": {
                "id": row.id, "name": row.name or "Parada sem nome",
                "indice": f"Índice {idx:.0f} · {normalize_level(row.risk_level) or 'sem nível'}",
                "color": color, "r": round(radius, 1), "o": order,
            },
        })
    feats.sort(key=lambda f: f["properties"]["o"])
    return {"type": "FeatureCollection", "features": feats}


def complaints_geojson(df: pd.DataFrame) -> dict:
    feats = []
    for row in df.itertuples(index=False):
        if pd.isna(row.lat) or pd.isna(row.lon):
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(row.lon), float(row.lat)]},
            "properties": {
                "id": str(row.protocolo), "name": f"Protocolo {row.protocolo}",
                "indice": f"{row.servico} · {getattr(row, 'bairro', '') or ''}",
                "color": CATEGORY_COLORS.get(row.servico, CATEGORY_COLORS["Outros"]), "r": 3.5,
            },
        })
    return {"type": "FeatureCollection", "features": feats}


def build_map(fc: dict) -> folium.Map:
    m = folium.Map(location=RIO_CENTER, zoom_start=11, tiles=None, prefer_canvas=True, control_scale=False)
    tiles_layer(m)
    folium.GeoJson(
        fc,
        name="dados",
        marker=folium.CircleMarker(radius=4, weight=0.6, fill=True, fill_opacity=0.9),
        style_function=lambda f: {
            "fillColor": f["properties"]["color"], "color": "#ffffff",
            "weight": 0.6, "fillOpacity": 0.9, "radius": f["properties"]["r"],
        },
        highlight_function=lambda f: {"weight": 2, "color": NAVY},
        tooltip=folium.GeoJsonTooltip(fields=["name", "indice"], aliases=["", ""], labels=False),
        zoom_on_click=False,
    ).add_to(m)
    return m


def highlight_group(stop: dict | None) -> folium.FeatureGroup:
    fg = folium.FeatureGroup(name="selecao")
    if stop and stop.get("lat") is not None:
        loc = [stop["lat"], stop["lon"]]
        folium.CircleMarker(loc, radius=12, color=NAVY, weight=2.5, fill=False).add_to(fg)
        folium.CircleMarker(loc, radius=4.5, color=NAVY, fill=True, fill_color=NAVY, fill_opacity=1, weight=0).add_to(fg)
        label = html.escape(f"{stop.get('name') or 'Parada'} · {stop.get('risk_score_normalized', 0):.0f}")
        folium.Marker(
            loc,
            icon=folium.DivIcon(
                icon_size=(1, 1), icon_anchor=(-16, 34),
                html=f"<div style='background:{NAVY};color:#fff;font:600 12px Geist,Inter,sans-serif;"
                     f"padding:5px 10px;border-radius:6px;white-space:nowrap;display:inline-block'>{label}</div>",
            ),
        ).add_to(fg)
    return fg


def shootings_chart(ser: pd.DataFrame):
    """Barras de tiroteios por mês com o número em cima. Sem zoom nem arrasto."""
    n = ser["n"].tolist()
    top = max(n) if max(n) > 0 else 1
    fig = go.Figure(go.Bar(
        x=ser["rotulo"], y=n,
        marker=dict(color=[ORANGE if v > 0 else "#E6EAEF" for v in n], line=dict(width=0)),
        text=[str(v) for v in n], textposition="outside", cliponaxis=False,
        textfont=dict(size=11, color=[NAVY if v > 0 else MUTED for v in n]),
        customdata=[f"{p.month:02d}/{p.year}" for p in ser["mes"]],
        hovertemplate="%{customdata}: %{y} tiroteio(s)<extra></extra>",
    ))
    plotly_layout(fig, height=150, margin=dict(l=2, r=2, t=18, b=2))
    fig.update_layout(dragmode=False, bargap=0.28)
    fig.update_xaxes(fixedrange=True, showgrid=False, tickfont=dict(size=10, color=MUTED), ticks="")
    fig.update_yaxes(fixedrange=True, visible=False, range=[0, top * 1.3])
    return fig


def bar(label: str, value: float, color: str) -> str:
    v = max(0.0, min(value, 100.0))
    return (f"<div class='rm-bar'><span class='rm-bar__label'>{label}</span>"
            f"<div class='rm-bar__track'><div class='rm-bar__fill' style='width:{v:.0f}%;background:{color}'></div></div>"
            f"<span class='rm-bar__v'>{v:.0f}</span></div>")


def render_panel(sel_id: str, stops_df: pd.DataFrame) -> None:
    det = get_stop_details(sel_id)
    if not det:
        empty_state("Parada não encontrada", "Escolha outra parada no mapa.")
        return
    idx = float(det.get("risk_score_normalized") or 0)
    top_pct = float((stops_df["risk_score_normalized"] >= idx).mean() * 100) if not stops_df.empty else 100
    rank_txt = (f"entre os {max(1, round(top_pct))}% mais altos" if top_pct <= 50
                else f"maior que {100 - round(top_pct)}% das paradas")
    routes = sorted({r for r in (det.get("routes") or []) if r})
    try:
        n_conn = len(get_connected_stops(sel_id, hops=1))
    except Exception:
        n_conn = None

    st.markdown(
        f"<div class='rm-eyebrow'>Parada selecionada</div>"
        f"<div class='rm-panel-name'>{html.escape(det.get('name') or 'Parada sem nome')}</div>"
        f"<div class='rm-panel-id'>{html.escape(str(sel_id))}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div class='rm-index'><div class='rm-index__value'>{idx:.0f}</div>"
        f"<div class='rm-index__meta'>{risk_badge(det.get('risk_level'))}<br>"
        f"índice de risco · {rank_txt}</div></div>",
        unsafe_allow_html=True,
    )

    tiles = [
        (fmt_int(det.get("total_complaints") or 0), "reclamações vinculadas"),
        (fmt_int(len(routes)), "linhas passam aqui"),
        (fmt_int(n_conn) if n_conn is not None else "—", "paradas ligadas direto"),
    ]
    st.markdown(
        "<div class='rm-tiles'>" + "".join(
            f"<div class='rm-tile'><div class='rm-tile__v'>{v}</div><div class='rm-tile__l'>{l}</div></div>"
            for v, l in tiles) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='rm-eyebrow' style='margin-top:16px'>Composição do índice</div><div class='rm-bars'>"
        + bar("Reclamações", (det.get("risk_score_atual") or 0) * 100, "#7D90AB")
        + bar("Tiroteio", (det.get("risk_score_tiroteio") or 0) * 100, ORANGE)
        + "</div>",
        unsafe_allow_html=True,
    )

    row = stops_df.loc[stops_df["id"] == sel_id]
    lat = float(row["lat"].iloc[0]) if not row.empty else det.get("lat")
    lon = float(row["lon"].iloc[0]) if not row.empty else det.get("lon")
    ser = shootings_by_month(lat, lon) if lat is not None and lon is not None else pd.DataFrame()
    if not ser.empty:
        first, last = ser["mes"].iloc[0], ser["mes"].iloc[-1]
        periodo = (str(last.year) if first.year == last.year
                   else f"{MESES_ABREV[first.month - 1]}/{first.year} a {MESES_ABREV[last.month - 1]}/{last.year}")
        total = int(ser["n"].sum())
        st.markdown(
            f"<div class='rm-eyebrow' style='margin-top:10px'>Tiroteios a até 500 m, {periodo}</div>"
            f"<div class='rm-muted' style='margin-top:4px'>{total} tiroteio{'s' if total != 1 else ''} no período · fonte: Fogo Cruzado</div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            shootings_chart(ser), width="stretch", key="tiroteios_chart",
            config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False,
                    "showAxisDragHandles": False, "responsive": True},
        )

    if routes:
        shown = routes[:10]
        extra = f"<span class='rm-muted'>+{len(routes) - len(shown)}</span>" if len(routes) > len(shown) else ""
        st.markdown(
            "<div class='rm-eyebrow' style='margin-top:6px'>Linhas</div><div class='rm-routes'>"
            + "".join(f"<span class='rm-route'>{html.escape(str(r))}</span>" for r in shown) + extra + "</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    if st.button("Ver rede da parada →", type="primary", width="stretch", key="go_rede"):
        go_page("rede")
    if st.button("Perguntar ao assistente", width="stretch", key="go_assist"):
        go_page("assistente")
    if st.button("Limpar seleção", type="tertiary", key="clear_sel"):
        set_selected(None)
        st.rerun()


def render_top(stops_df: pd.DataFrame) -> None:
    st.markdown(
        "<div class='rm-eyebrow'>Para começar</div>"
        "<div class='rm-panel-name' style='font-size:1.2rem'>Clique numa parada no mapa</div>"
        "<p class='rm-muted' style='margin-top:6px'>Ou escolha uma das paradas com maior índice de risco:</p>",
        unsafe_allow_html=True,
    )
    top = stops_df.nlargest(6, "risk_score_normalized")
    for row in top.itertuples(index=False):
        c1, c2 = st.columns([6, 1])
        c1.markdown(
            f"<div class='rm-list-row'><span class='rm-dot' style='background:{get_risk_color(row.risk_level)}'></span>"
            f"<span class='rm-list-row__name'>{html.escape(row.name or 'Parada')}</span>"
            f"<span class='rm-list-row__v'>{row.risk_score_normalized:.0f}</span></div>",
            unsafe_allow_html=True,
        )
        if c2.button("→", key=f"top_{row.id}", type="tertiary", help="Selecionar"):
            set_selected(row.id)
            st.rerun()


# ----------------------------------------------------------------------------
try:
    stops_all = get_stops_with_risk()
except Exception as e:  # banco fora do ar
    st.error(f"Não foi possível carregar as paradas: {e}")
    st.stop()

if stops_all.empty:
    empty_state("Sem dados de paradas", "O banco não devolveu paradas.")
    st.stop()

stops_all = stops_all.copy()
stops_all["risk_level"] = stops_all["risk_level"].map(normalize_level)
stops_all["total_complaints"] = stops_all["total_complaints"].fillna(0).astype(int)
sel_id = get_selected()

try:
    stats = get_system_stats()
except Exception:
    stats = {}

selection_chip(stops_all.loc[stops_all["id"] == sel_id, "name"].iloc[0]
               if sel_id and (stops_all["id"] == sel_id).any() else None)
stat_band([
    (fmt_int(stats.get("total_stops", len(stops_all))), "paradas"),
    (fmt_int(stats.get("total_routes")), "linhas"),
    (fmt_int((stops_all["risk_level"] == "Alto").sum()), "nível alto"),
    (fmt_int(stats.get("total_complaints")), "reclamações 1746"),
], compact=True)

# ---------- Barra de ferramentas ----------
t1, t2, t3 = st.columns([2.2, 2.2, 1], vertical_alignment="bottom")
with t1:
    named = stops_all[stops_all["name"].notna()].sort_values("name")
    options = named["id"].tolist()
    labels = dict(zip(named["id"], named["name"] + " · " + named["risk_score_normalized"].round(0).astype(int).astype(str)))
    picked = st.selectbox(
        "Buscar parada", options, index=None, format_func=lambda i: labels.get(i, i),
        placeholder="Buscar parada pelo nome", label_visibility="collapsed", key="busca_parada",
    )
    if picked and picked != st.session_state.get("_last_pick"):
        st.session_state["_last_pick"] = picked
        set_selected(picked)
        st.session_state["map_center"] = picked
        sel_id = picked
with t2:
    layer = st.segmented_control("Camada", LAYERS, default=LAYERS[0], key="camada",
                                 label_visibility="collapsed") or LAYERS[0]

levels_sel = st.session_state.get("f_niveis", LEVELS)
route_sel = st.session_state.get("f_linha", "Todas")
min_rec = st.session_state.get("f_min_rec", 0)
try:
    routes_df = get_routes_with_metrics()
    _named = routes_df.dropna(subset=["name"]).assign(name=lambda d: d["name"].astype(str))
    route_opts = ["Todas"] + sorted(_named["name"].unique().tolist(), key=lambda s: (len(s), s))
    route_ids = _named.groupby("name")["id"].apply(list).to_dict()
except Exception:
    route_opts, route_ids = ["Todas"], {}
n_active = (len(levels_sel) < len(LEVELS)) + (route_sel != "Todas") + (min_rec > 0)
with t3:
    with st.popover(f"Filtros{f' · {n_active}' if n_active else ''}", width="stretch"):
        st.pills("Nível de risco", LEVELS, selection_mode="multi", default=LEVELS, key="f_niveis")
        st.selectbox("Linha", route_opts, key="f_linha")
        st.slider("Mínimo de reclamações vinculadas", 0, int(max(stops_all["total_complaints"].max(), 1)), 0, key="f_min_rec")
        if st.button("Limpar filtros", type="tertiary"):
            for k in ("f_niveis", "f_linha", "f_min_rec"):
                st.session_state.pop(k, None)
            st.rerun()

# ---------- Filtros ----------
stops_df = stops_all[stops_all["risk_level"].isin(levels_sel or LEVELS)]
if route_sel != "Todas":
    ids = set()
    for rid in route_ids.get(route_sel, []):
        try:
            ids.update(get_route_stop_ids(rid))
        except Exception:
            pass
    stops_df = stops_df[stops_df["id"].isin(ids)]
if min_rec:
    stops_df = stops_df[stops_df["total_complaints"] >= min_rec]

# ---------- Mapa + painel ----------
col_map, col_panel = st.columns([2.3, 1], gap="medium")

with col_map:
    if layer == "Reclamações":
        try:
            comp = get_complaints_by_location()
            fc = complaints_geojson(comp)
        except Exception as e:
            st.warning(f"Reclamações indisponíveis: {e}")
            fc = {"type": "FeatureCollection", "features": []}
    else:
        fc = stops_geojson(stops_df, layer)

    sel_row = stops_all[stops_all["id"] == sel_id].iloc[0].to_dict() if sel_id and (stops_all["id"] == sel_id).any() else None
    center = zoom = None
    if st.session_state.get("map_center") and sel_row:
        center, zoom = [sel_row["lat"], sel_row["lon"]], 14
        st.session_state["map_center"] = None

    out = st_folium(
        build_map(fc), key="mapa", height=520, use_container_width=True,
        feature_group_to_add=highlight_group(sel_row),
        center=center, zoom=zoom,
        returned_objects=["last_active_drawing"],
    )
    clicked = (out or {}).get("last_active_drawing") or {}
    cid = (clicked.get("properties") or {}).get("id")
    if cid and cid != st.session_state.get("_last_click"):
        st.session_state["_last_click"] = cid
        if layer == "Reclamações":
            st.session_state["protocolo_sel"] = cid
        else:
            set_selected(cid)
        st.rerun()

    if layer == "Tiroteio":
        cols = [LEVEL_COLORS["Baixo"], LEVEL_COLORS["Médio-Baixo"], LEVEL_COLORS["Médio-Alto"], LEVEL_COLORS["Alto"]]
        st.markdown(legend_html(list(zip(cols, [f"score {l}" for _, l in reversed(TIRO_BINS)]))), unsafe_allow_html=True)
        note("Score de tiroteio do modelo XGBoost (0 a 100) para o raio de 500 m de cada parada. Ordena paradas, não é probabilidade.")
    elif layer == "Reclamações":
        st.markdown(legend_html([(c, n) for n, c in CATEGORY_COLORS.items()]), unsafe_allow_html=True)
        note("Até 1.000 reclamações da Central 1746, coloridas por categoria. Clique num ponto para ver o protocolo abaixo.")
    else:
        st.markdown(level_legend(), unsafe_allow_html=True)
        note(f"{fmt_int(len(stops_df))} paradas exibidas. O índice vai de 0 a 100 e combina reclamações e o modelo de tiroteio.")

with col_panel:
    with st.container(border=True):
        if sel_id:
            render_panel(sel_id, stops_all)
        else:
            render_top(stops_all)

# ---------- Detalhes ----------
st.write("")
with st.expander("Tabela das paradas exibidas"):
    table = stops_df[["id", "name", "risk_score_normalized", "risk_level", "total_complaints", "risk_score_tiroteio"]].copy()
    table["risk_score_tiroteio"] = (table["risk_score_tiroteio"] * 100).round(0)
    table = table.sort_values("risk_score_normalized", ascending=False)
    ev = st.dataframe(
        table.drop(columns=["id"]).rename(columns={
            "name": "Parada", "risk_score_normalized": "Índice", "risk_level": "Nível",
            "total_complaints": "Reclamações", "risk_score_tiroteio": "Score de tiroteio",
        }),
        hide_index=True, width="stretch", height=360,
        column_config={"Índice": st.column_config.NumberColumn(format="%.0f")},
        on_select="rerun", selection_mode="single-row", key="tabela_paradas",
    )
    rows = (ev or {}).get("selection", {}).get("rows", []) if ev else []
    if rows:
        new_id = table.iloc[rows[0]]["id"]
        if new_id != sel_id:
            set_selected(new_id)
            st.session_state["map_center"] = new_id
            st.rerun()

if sel_id:
    with st.expander("Reclamações vinculadas à parada selecionada"):
        try:
            comp_sel = get_stop_complaints(sel_id)
        except Exception as e:
            comp_sel = pd.DataFrame()
            st.warning(f"Consulta indisponível: {e}")
        if comp_sel.empty:
            st.caption("Nenhuma reclamação vinculada a esta parada.")
        else:
            by_cat = comp_sel["servico"].value_counts()
            st.markdown(" · ".join(f"**{c}**: {n}" for c, n in by_cat.items()))
            st.dataframe(
                comp_sel[["protocolo", "data_abertura", "servico", "status", "bairro"]].rename(columns={
                    "protocolo": "Protocolo", "data_abertura": "Abertura", "servico": "Categoria",
                    "status": "Status", "bairro": "Bairro"}),
                hide_index=True, width="stretch", height=280,
            )

with st.expander("Reclamação da Central 1746 por protocolo"):
    proto = st.text_input("Protocolo", value=st.session_state.get("protocolo_sel", ""), placeholder="Número do protocolo")
    if proto:
        try:
            info = get_complaint_details(proto)
        except Exception as e:
            info = None
            st.warning(f"Consulta indisponível: {e}")
        if info:
            c1, c2, c3 = st.columns(3)
            c1.metric("Categoria", info.get("servico") or "—")
            c2.metric("Paradas afetadas", int(info.get("stop_count") or 0))
            c3.metric("Abertura", (info.get("data_abertura") or "—")[:10])
            if info.get("bairro"):
                st.markdown(f"**Bairro:** {info['bairro']}")
            if info.get("descricao"):
                st.markdown(f"**Descrição:** {info['descricao']}")
            stops_aff = [s for s in (info.get("affected_stops") or []) if s]
            if stops_aff:
                st.markdown("**Paradas afetadas:** " + ", ".join(stops_aff))
        elif info is None and proto:
            st.caption("Nenhuma reclamação com esse protocolo.")
