"""Rede — paradas ligadas a uma origem, em anéis pela distância na rede de linhas."""
import html
import math

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

from webapp.utils.data_fetchers import get_stop_neighborhood, get_stops_with_risk
from webapp.utils.state import get_selected, go as go_page, set_selected
from webapp.utils.theme import (
    LINE, MUTED, NAVY, ORANGE, empty_state, fmt_int, get_risk_color, level_legend,
    normalize_level, note, page_header, plotly_layout,
)

RING = 1.0


def radial_layout(G: nx.Graph, origin: str, dist: dict) -> dict:
    """Coloca cada parada no anel da sua distância; o ângulo segue a árvore BFS."""
    T = nx.bfs_tree(G, origin)
    leaves = {}

    def count(u):
        children = list(T.successors(u))
        leaves[u] = 1 if not children else sum(count(c) for c in children)
        return leaves[u]

    count(origin)
    span = {origin: (0.0, 2 * math.pi)}
    for u in nx.topological_sort(T):
        a0, a1 = span[u]
        cur = a0
        for c in sorted(T.successors(u), key=lambda c: -leaves[c]):
            width = (a1 - a0) * leaves[c] / leaves[u]
            span[c] = (cur, cur + width)
            cur += width
    pos = {}
    for n, (a0, a1) in span.items():
        a = (a0 + a1) / 2 - math.pi / 2
        r = dist.get(n, 0) * RING
        pos[n] = (r * math.cos(a), -r * math.sin(a))
    return pos


try:
    stops_all = get_stops_with_risk()
except Exception as e:
    st.error(f"Não foi possível carregar as paradas: {e}")
    st.stop()
stops_all = stops_all[stops_all["name"].notna()].copy()
stops_all["risk_level"] = stops_all["risk_level"].map(normalize_level)
info = stops_all.set_index("id").to_dict("index")

origin = get_selected()
if origin not in info:
    origin = stops_all.sort_values("risk_score_normalized", ascending=False)["id"].iloc[0]

page_header("Rede de ônibus", f"Vizinhança de {info[origin]['name']}",
            "Cada ponto é uma parada. Duas paradas estão ligadas quando uma linha passa por elas em sequência.")

# ---------- Controles ----------
c1, c2, c3 = st.columns([2.4, 1.6, 1], vertical_alignment="bottom")
with c1:
    named = stops_all.sort_values("name")
    ids = named["id"].tolist()
    labels = dict(zip(named["id"], named["name"] + " · " + named["risk_score_normalized"].round(0).astype(int).astype(str)))
    picked = st.selectbox("Origem", ids, index=ids.index(origin), format_func=lambda i: labels.get(i, i), key=f"origem_{origin}")
    if picked != origin:
        set_selected(picked)
        st.rerun()
with c2:
    hops = st.select_slider("Distância (paradas)", options=[1, 2, 3, 4], value=3, key="rede_hops")
with c3:
    show_names = st.toggle("Mostrar nomes", value=True)

try:
    edges = get_stop_neighborhood(origin, hops)
except Exception as e:
    st.error(f"Não foi possível carregar a rede: {e}")
    st.stop()

if edges.empty:
    empty_state("Sem conexões", "Esta parada não tem ligações registradas na rede. Escolha outra origem.")
    st.stop()

G = nx.Graph()
G.add_edges_from(zip(edges["source"], edges["target"]))
dist = nx.single_source_shortest_path_length(G, origin, cutoff=hops)
G = G.subgraph(dist.keys()).copy()
pos = radial_layout(G, origin, dist)

neighbors = [n for n in G.nodes if n != origin and n in info]
seen, top = set(), []
for n in sorted(neighbors, key=lambda n: -(info[n]["risk_score_normalized"] or 0)):
    name = info[n]["name"].split(" :: ")[0]
    if name not in seen:
        seen.add(name)
        top.append(n)
top = top[:5]

# ---------- Gráfico ----------
fig = go.Figure()
for h in range(1, hops + 1):
    fig.add_shape(type="circle", x0=-h, y0=-h, x1=h, y1=h, line=dict(color="#E3E7EC", width=1, dash="dot"))
    fig.add_annotation(x=0, y=h, text=f"{h} parada{'s' if h > 1 else ''}", showarrow=False,
                       yshift=8, font=dict(size=10, color=MUTED))
ex, ey = [], []
for a, b in G.edges():
    ex += [pos[a][0], pos[b][0], None]
    ey += [pos[a][1], pos[b][1], None]
fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="#C9D1DB", width=1.2), hoverinfo="skip"))

nodes = [n for n in G.nodes if n != origin]
fig.add_trace(go.Scatter(
    x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes], mode="markers",
    marker=dict(size=[13 if n in top else 10 for n in nodes],
                color=[get_risk_color(info.get(n, {}).get("risk_level")) for n in nodes],
                line=dict(color="#fff", width=1.5)),
    customdata=[[info.get(n, {}).get("name", n), info.get(n, {}).get("risk_score_normalized") or 0,
                 info.get(n, {}).get("risk_level") or "sem nível", dist.get(n)] for n in nodes],
    hovertemplate="<b>%{customdata[0]}</b><br>Índice %{customdata[1]:.0f} · %{customdata[2]}"
                  "<br>a %{customdata[3]} parada(s) da origem<extra></extra>",
))
if show_names and top:
    fig.add_trace(go.Scatter(
        x=[pos[n][0] for n in top], y=[pos[n][1] for n in top], mode="text",
        text=[("   " + info[n]["name"].split(" :: ")[0]) if pos[n][0] >= 0 else (info[n]["name"].split(" :: ")[0] + "   ") for n in top],
        textposition=["middle right" if pos[n][0] >= 0 else "middle left" for n in top],
        textfont=dict(size=12, color=NAVY), hoverinfo="skip",
    ))
fig.add_trace(go.Scatter(
    x=[0], y=[0], mode="markers+text" if show_names else "markers",
    marker=dict(size=22, color=NAVY, line=dict(color="rgba(11,31,58,.25)", width=8)),
    text=[info[origin]["name"].split(" :: ")[0]], textposition="top center",
    textfont=dict(size=13, color=NAVY), hovertemplate=f"<b>{html.escape(info[origin]['name'])}</b> · origem<extra></extra>",
))
lim = hops + 0.45
plotly_layout(fig, height=560, margin=dict(l=4, r=4, t=4, b=4))
fig.update_xaxes(visible=False, range=[-lim - (0.9 if show_names else 0), lim + (0.9 if show_names else 0)])
fig.update_yaxes(visible=False, range=[-lim, lim], scaleanchor="x", scaleratio=1)
fig.update_layout(dragmode="pan")

col_g, col_p = st.columns([2.3, 1], gap="medium")
with col_g:
    with st.container(border=True):
        st.markdown(level_legend(), unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "scrollZoom": True}, key="grafo")
    note("Arraste para mover e use a rolagem para aproximar. A cor de cada parada é o nível do índice de risco.")

with col_p:
    with st.container(border=True):
        vals = [info[n]["risk_score_normalized"] or 0 for n in G.nodes if n in info]
        hood = sum(vals) / len(vals) if vals else 0
        city = float(stops_all["risk_score_normalized"].mean())
        st.markdown(
            f"<div class='rm-eyebrow'>Vizinhança de</div>"
            f"<div class='rm-panel-name'>{html.escape(info[origin]['name'])}</div>"
            f"<div class='rm-tiles' style='grid-template-columns:1fr 1fr'>"
            f"<div class='rm-tile'><div class='rm-tile__v'>{fmt_int(G.number_of_nodes())}</div><div class='rm-tile__l'>paradas</div></div>"
            f"<div class='rm-tile'><div class='rm-tile__v'>{fmt_int(G.number_of_edges())}</div><div class='rm-tile__l'>ligações</div></div></div>"
            f"<div class='rm-eyebrow' style='margin-top:14px'>Índice médio</div><div class='rm-bars'>"
            f"<div class='rm-bar'><span class='rm-bar__label'>Vizinhança</span><div class='rm-bar__track'><div class='rm-bar__fill' style='width:{hood:.0f}%;background:{ORANGE}'></div></div><span class='rm-bar__v'>{hood:.0f}</span></div>"
            f"<div class='rm-bar'><span class='rm-bar__label'>Cidade</span><div class='rm-bar__track'><div class='rm-bar__fill' style='width:{city:.0f}%;background:#B8C2CE'></div></div><span class='rm-bar__v'>{city:.0f}</span></div></div>"
            f"<div class='rm-eyebrow' style='margin:14px 0 4px'>Vizinhas com maior índice</div>",
            unsafe_allow_html=True,
        )
        for n in top:
            d = dist[n]
            a, b = st.columns([6, 1], vertical_alignment="center")
            a.markdown(
                f"<div class='rm-list-row'><span class='rm-dot' style='background:{get_risk_color(info[n]['risk_level'])}'></span>"
                f"<span class='rm-list-row__name'>{html.escape(info[n]['name'].split(' :: ')[0])}"
                f"<br><span class='rm-list-row__sub'>a {d} parada{'s' if d > 1 else ''} de distância</span></span>"
                f"<span class='rm-list-row__v'>{(info[n]['risk_score_normalized'] or 0):.0f}</span></div>",
                unsafe_allow_html=True,
            )
            if b.button("→", key=f"orig_{n}", type="tertiary", help="Usar como origem"):
                set_selected(n)
                st.rerun()
        st.write("")
        if st.button("Ver no mapa", width="stretch", key="rede_mapa"):
            set_selected(origin)
            st.session_state["map_center"] = origin
            go_page("mapa")
        if st.button("Perguntar ao assistente", width="stretch", key="rede_assist"):
            set_selected(origin)
            go_page("assistente")
