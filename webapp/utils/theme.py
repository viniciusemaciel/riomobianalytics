"""RioMobiAnalytics — sistema visual compartilhado.

Uso em cada página (o roteador `webapp/Home.py` já chama `apply_theme`):

    from webapp.utils.theme import page_header, risk_badge, LEVEL_COLORS

Regras do redesign:
- Azul-marinho em texto, navegação e controles.
- Laranja reservado ao dado (índice de risco, tiroteio) e ao ponto do logo.
- Índice de risco = `risk_score_normalized` (0 a 100), nunca "% de chance".
"""
from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_MARK = ASSETS_DIR / "logo_mark.svg"
FAVICON = ASSETS_DIR / "favicon.png"
STYLE_CSS = ASSETS_DIR / "style.css"

PAGE_ICON = str(FAVICON) if FAVICON.exists() else None

NAVY = "#0B1F3A"
NAVY_SOFT = "#1B3457"
ORANGE = "#F26A4B"
CREAM = "#FAF7F2"
TEXT_2 = "#3C4A5D"
MUTED = "#647185"
LINE = "#D6DCE4"
SUNKEN = "#EEF1F5"
CANVAS = "#F2F4F7"   # fundo das páginas; cartões em branco por cima
ORANGE_INK = "#C24A2B"  # laranja para texto pequeno (contraste melhor que o ORANGE)

LEVELS = ["Baixo", "Médio-Baixo", "Médio-Alto", "Alto"]

# Degradê de laranja: quanto mais alto o nível, mais fechado o tom.
LEVEL_COLORS = {
    "Baixo": "#F2DDD5",
    "Médio-Baixo": "#F2B19C",
    "Médio-Alto": "#F08463",
    "Alto": "#D9542F",
}
NO_LEVEL_COLOR = "#C9D1DB"

# Texto legível sobre o fundo de cada nível (selos).
LEVEL_BADGE = {
    "Baixo": ("#F6ECE8", "#7A4A3C"),
    "Médio-Baixo": ("#FBE6DE", "#8E3F28"),
    "Médio-Alto": ("#FBDDD2", "#8E3220"),
    "Alto": ("#F8D3C6", "#7E2814"),
}

# Categorias de reclamação: tons de azul-marinho, laranja só em Segurança.
CATEGORY_COLORS = {
    "Segurança Pública": ORANGE,
    "Iluminação Pública": "#1B3457",
    "Trânsito e Transporte": "#4A6385",
    "Conservação de Vias": "#7D90AB",
    "Limpeza Urbana": "#A9B6C8",
    "Outros": "#C9D1DB",
}


PLOT_FONT = dict(family="Geist, Inter, sans-serif", color=NAVY, size=12)


def normalize_level(level: str | None) -> str | None:
    if not level:
        return None
    return {"Medio-Alto": "Médio-Alto", "Medio-Baixo": "Médio-Baixo"}.get(level, level)


def get_risk_color(level: str | None) -> str:
    return LEVEL_COLORS.get(normalize_level(level), NO_LEVEL_COLOR)


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def fmt_dec(value, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


@st.cache_data(show_spinner=False)
def _read_css(mtime: float) -> str:
    # `mtime` entra na chave do cache: um style.css novo (deploy) é relido sem precisar de reboot.
    return STYLE_CSS.read_text(encoding="utf-8") if STYLE_CSS.exists() else ""


def apply_theme() -> None:
    """Injeta o CSS compartilhado. Chamado uma vez por execução no roteador."""
    css = _read_css(STYLE_CSS.stat().st_mtime if STYLE_CSS.exists() else 0.0)
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    sub = f"<p class='rm-sub'>{html.escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"<div class='rm-header'><div class='rm-eyebrow'>{html.escape(eyebrow)}</div>"
        f"<h1 class='rm-title'>{html.escape(title)}</h1>{sub}</div>",
        unsafe_allow_html=True,
    )


def eyebrow(text: str) -> None:
    st.markdown(f"<div class='rm-eyebrow'>{html.escape(text)}</div>", unsafe_allow_html=True)


def section_title(title: str, hint: str = "", label: str = "") -> None:
    lab = f"<div class='rm-eyebrow'>{html.escape(label)}</div>" if label else ""
    hint_html = f"<p class='rm-section__hint'>{html.escape(hint)}</p>" if hint else ""
    st.markdown(
        f"<div class='rm-section'>{lab}<h2>{html.escape(title)}</h2>{hint_html}</div>",
        unsafe_allow_html=True,
    )


def stat_band(items: list[tuple[str, str]], compact: bool = False, slim: bool = False, accent: int | None = None) -> None:
    """Faixa de números separados por linhas finas, num cartão branco. Vira 2x2 no celular.

    `slim`: versão mais baixa (telas de trabalho, como o Mapa). `accent`: posição do número em laranja.
    """
    cells = "".join(
        f"<div class='rm-stat'><div class='rm-stat__value{' rm-stat__value--accent' if i == accent else ''}'>{html.escape(v)}</div>"
        f"<div class='rm-stat__label'>{html.escape(l)}</div></div>"
        for i, (v, l) in enumerate(items)
    )
    cls = "rm-band rm-band--compact" if compact else ("rm-band rm-band--slim" if slim else "rm-band")
    st.markdown(f"<div class='{cls}'>{cells}</div>", unsafe_allow_html=True)


def risk_badge(level: str | None) -> str:
    level = normalize_level(level)
    if level not in LEVEL_BADGE:
        return "<span class='rm-badge rm-badge--none'>Sem nível</span>"
    bg, fg = LEVEL_BADGE[level]
    return f"<span class='rm-badge' style='background:{bg};color:{fg}'>{html.escape(level)}</span>"


def legend_html(items: list[tuple[str, str]]) -> str:
    dots = "".join(
        f"<span class='rm-legend__item'><span class='rm-dot' style='background:{c}'></span>{html.escape(t)}</span>"
        for c, t in items
    )
    return f"<div class='rm-legend'>{dots}</div>"


def level_legend() -> str:
    return legend_html([(LEVEL_COLORS[l], l) for l in LEVELS])


def empty_state(title: str, message: str) -> None:
    st.markdown(
        f"<div class='rm-empty'><div class='rm-empty__title'>{html.escape(title)}</div>"
        f"<div>{html.escape(message)}</div></div>",
        unsafe_allow_html=True,
    )


def note(text: str) -> None:
    st.markdown(f"<div class='rm-note'>{html.escape(text)}</div>", unsafe_allow_html=True)


def plotly_layout(fig, height: int = 320, margin: dict | None = None):
    fig.update_layout(
        height=height,
        margin=margin or dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=PLOT_FONT,
        showlegend=False,
        hoverlabel=dict(bgcolor="#fff", bordercolor=LINE, font=PLOT_FONT),
    )
    return fig
