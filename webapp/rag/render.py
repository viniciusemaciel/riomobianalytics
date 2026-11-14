"""Desenha na página os visuais pedidos pelo assistente (Fase 4).

Recebe as especificações já validadas por `webapp/rag/visuais.py` (guardadas no
histórico do chat) e desenha com Plotly, `st.dataframe` e Folium, na paleta do app:
laranja só para dado, níveis de risco no degradê de laranja.
Um visual com problema vira um aviso discreto, nunca derruba a página.
"""
from __future__ import annotations

import html

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from webapp.utils.mapa_base import RIO_CENTER, tiles_layer
from webapp.utils.theme import (
    LEVEL_COLORS, MUTED, NAVY, NO_LEVEL_COLOR, ORANGE, legend_html, normalize_level, plotly_layout,
)

CORES_SERIES = [ORANGE, NAVY, "#7D90AB", "#C9D1DB"]
_PLOTLY_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False,
                  "showAxisDragHandles": False, "responsive": True}


def _cabecalho(spec: dict) -> None:
    st.markdown(f"<div class='rm-eyebrow' style='margin:14px 0 4px'>{html.escape(spec.get('titulo') or '')}</div>",
                unsafe_allow_html=True)


def _rodape(spec: dict) -> None:
    if spec.get("fonte_id"):
        st.caption(f"Fonte [{spec['fonte_id']}]")


def _grafico(spec: dict, key: str) -> None:
    rot, series, formato = spec["rotulos"], spec["series"], spec.get("formato", "barra")
    fig = go.Figure()
    for i, s in enumerate(series):
        cor = CORES_SERIES[i % len(CORES_SERIES)]
        if formato == "linha":
            fig.add_trace(go.Scatter(x=rot, y=s["valores"], name=s["nome"], mode="lines+markers",
                                     line=dict(color=cor, width=2), marker=dict(size=5)))
        elif formato == "barra_horizontal":
            fig.add_trace(go.Bar(y=rot, x=s["valores"], name=s["nome"], orientation="h", marker_color=cor,
                                 text=s["valores"] if len(series) == 1 else None, texttemplate="%{text:.1~f}",
                                 textposition="outside", cliponaxis=False))
        else:
            fig.add_trace(go.Bar(x=rot, y=s["valores"], name=s["nome"], marker_color=cor,
                                 text=s["valores"] if len(series) == 1 and len(rot) <= 15 else None,
                                 texttemplate="%{text:.1~f}", textposition="outside", cliponaxis=False))
    horizontal = formato == "barra_horizontal"
    altura = max(240, min(28 * len(rot) + 60, 640)) if horizontal else 300
    plotly_layout(fig, height=altura, margin=dict(l=8, r=24, t=8, b=8))
    eixo_valor = dict(title=dict(text=spec.get("eixo_y") or "", font=dict(size=11, color=MUTED)),
                      gridcolor="#EEF1F4", zeroline=False, fixedrange=True)
    eixo_cat = dict(fixedrange=True, showgrid=False, automargin=True)
    if horizontal:
        fig.update_layout(xaxis=eixo_valor, yaxis={**eixo_cat, "autorange": "reversed"})
    else:
        fig.update_layout(yaxis=eixo_valor, xaxis=eixo_cat)
    if len(series) > 1:
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=11)),
                          barmode="group")
    st.plotly_chart(fig, width="stretch", key=key, config=_PLOTLY_CONFIG)


def _tabela(spec: dict, key: str) -> None:
    df = pd.DataFrame(spec["linhas"], columns=spec["colunas"])
    for c in df.columns:  # coluna só de números (ou vazios) vira numérica, para ordenar direito
        if df[c].map(lambda v: v is None or isinstance(v, float)).all():
            df[c] = pd.to_numeric(df[c], errors="coerce")
    cfg = {}
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            inteiro = df[c].dropna().map(float.is_integer).all()
            cfg[c] = st.column_config.NumberColumn(format="%d" if inteiro else "%.1f")
    st.dataframe(df, hide_index=True, width="stretch", key=key, column_config=cfg,
                 height=min(38 + 35 * len(df), 420))


def _mapa(spec: dict, key: str) -> None:
    pontos = spec.get("pontos") or []
    if not pontos:
        st.caption("Nenhuma parada para mostrar no mapa.")
        return
    m = folium.Map(location=RIO_CENTER, zoom_start=11, tiles=None, control_scale=False)
    tiles_layer(m)
    destaque = spec.get("destaque")
    for p in sorted(pontos, key=lambda p: p["stop_id"] == destaque):  # destaque desenhado por último, por cima
        nivel = normalize_level(p.get("nivel"))
        cor = LEVEL_COLORS.get(nivel, NO_LEVEL_COLOR)
        indice = p.get("indice")
        dica = html.escape(f"{p.get('nome') or p['stop_id']} · índice {indice:.0f}" if indice is not None
                           else (p.get("nome") or p["stop_id"]))
        loc = [p["lat"], p["lon"]]
        if p["stop_id"] == destaque:
            folium.CircleMarker(loc, radius=12, color=NAVY, weight=2.5, fill=False).add_to(m)
        folium.CircleMarker(loc, radius=7 if p["stop_id"] == destaque else 6, color="#ffffff", weight=1,
                            fill=True, fill_color=NAVY if p["stop_id"] == destaque else cor, fill_opacity=0.95,
                            tooltip=dica).add_to(m)
    lats, lons = [p["lat"] for p in pontos], [p["lon"] for p in pontos]
    if len(pontos) == 1:
        m.location, m.options["zoom"] = [lats[0], lons[0]], 15
    else:
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(24, 24), max_zoom=16)
    st_folium(m, height=360, width=None, key=key, returned_objects=[])
    niveis = [n for n in LEVEL_COLORS if any(normalize_level(p.get("nivel")) == n for p in pontos)]
    if niveis:
        st.markdown(legend_html([(LEVEL_COLORS[n], n) for n in niveis]), unsafe_allow_html=True)


_DESENHOS = {"grafico": _grafico, "tabela": _tabela, "mapa": _mapa}


def desenhar(visuais: list[dict] | None, prefixo: str) -> None:
    """Desenha os visuais de uma mensagem. `prefixo` deixa as chaves únicas por mensagem."""
    for j, spec in enumerate(visuais or []):
        fn = _DESENHOS.get(spec.get("tipo"))
        if fn is None:
            continue
        try:
            _cabecalho(spec)
            fn(spec, f"{prefixo}_{j}")
            _rodape(spec)
        except Exception:
            st.caption("Não consegui desenhar este visual.")
