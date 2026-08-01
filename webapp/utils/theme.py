"""RioMobiAnalytics — design system helpers.

Uso mínimo em cada página:

    from webapp.utils.theme import apply_theme, render_page_header, PAGE_ICON

    st.set_page_config(page_title="...", page_icon=PAGE_ICON, layout="wide")
    apply_theme()
    render_page_header("Título", "Subtítulo", icon="MAP")
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
import html

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_MARK = ASSETS_DIR / "logo_mark.png"
LOGO_FULL = ASSETS_DIR / "logo_full.png"
FAVICON = ASSETS_DIR / "favicon.png"
STYLE_CSS = ASSETS_DIR / "style.css"

PAGE_ICON = str(FAVICON) if FAVICON.exists() else "🚌"


@lru_cache(maxsize=8)
def _asset_data_uri(path_str: str) -> str:
    """Return a base64 data URI for a PNG asset (cached per process)."""
    path = Path(path_str)
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"

BRAND = {
    "navy": "#0B1F3A",
    "navy_soft": "#1B3457",
    "coral": "#F26A4B",
    "cream": "#FAF7F2",
    "high": "#D14B3A",
    "med": "#E9A23B",
    "low": "#3F9E6E",
}

CATEGORY_COLORS = {
    "Segurança Pública":      "#D14B3A",
    "Iluminação Pública":     "#E9A23B",
    "Trânsito e Transporte":  "#3B78C7",
    "Conservação de Vias":    "#8A5CB6",
    "Limpeza Urbana":         "#3F9E6E",
    "Outros":                 "#8A93A3",
}


def apply_theme() -> None:
    """Inject the shared stylesheet + brand the sidebar. Idempotent per rerun."""
    if STYLE_CSS.exists():
        css = STYLE_CSS.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    if LOGO_FULL.exists():
        with st.sidebar:
            st.image(str(LOGO_FULL), use_container_width=True)
            st.markdown(
                "<div style='height:1px;background:rgba(255,255,255,0.12);"
                "margin:12px 0 8px 0;'></div>",
                unsafe_allow_html=True,
            )


def render_page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Hero header for internal pages (not Home)."""
    icon_html = ""
    if icon:
        icon_html = (
            f"<div class='rm-page-header__icon'>{html.escape(icon)}</div>"
        )
    st.markdown(
        f"""
        <div class='rm-page-header'>
            {icon_html}
            <div>
                <div class='rm-page-header__title'>{html.escape(title)}</div>
                <div class='rm-page-header__subtitle'>{html.escape(subtitle)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title_html: str, subtitle: str, eyebrow: str = "",
                logo: bool = True) -> None:
    """Home hero with gradient. `title_html` may contain <em> for coral highlight.

    When ``logo`` is True and ``logo_mark.png`` exists, renders the icon-only
    mark on the right side of the hero.
    """
    eyebrow_html = (
        f"<div class='rm-hero__eyebrow'>{html.escape(eyebrow)}</div>"
        if eyebrow else ""
    )
    logo_html = ""
    if logo:
        uri = _asset_data_uri(str(LOGO_MARK))
        if uri:
            logo_html = (
                f"<div class='rm-hero__logo'>"
                f"<img src='{uri}' alt='RioMobiAnalytics'/></div>"
            )
    st.markdown(
        f"""
        <div class='rm-hero'>
            <div class='rm-hero__text'>
                {eyebrow_html}
                <div class='rm-hero__title'>{title_html}</div>
                <div class='rm-hero__subtitle'>{html.escape(subtitle)}</div>
            </div>
            {logo_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(label: str, value: str, hint: str = "") -> None:
    """Custom KPI card (drop-in for st.metric with the same layout)."""
    hint_html = (
        f"<div class='rm-kpi__hint'>{html.escape(hint)}</div>" if hint else ""
    )
    st.markdown(
        f"""
        <div class='rm-kpi'>
            <div class='rm-kpi__accent'></div>
            <div class='rm-kpi__label'>{html.escape(label)}</div>
            <div class='rm-kpi__value'>{html.escape(value)}</div>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_risk_badge(level: str | None) -> str:
    """Return the HTML string for a risk badge — call inside st.markdown(..., unsafe_allow_html=True)."""
    if not level:
        return "<span class='rm-badge rm-badge--none'>Sem risco</span>"
    mapping = {
        "Alto":  "rm-badge--high",
        "Medio": "rm-badge--med",
        "Médio": "rm-badge--med",
        "Baixo": "rm-badge--low",
    }
    cls = mapping.get(level, "rm-badge--none")
    return f"<span class='rm-badge {cls}'>{html.escape(str(level))}</span>"


def render_risk_legend() -> None:
    """Vertical legend for the risk map (colored dots + labels)."""
    st.markdown(
        f"""
        <div class='rm-legend'>
            <div class='rm-legend__row'>
                <span class='rm-legend__dot' style='background:{BRAND["high"]}'></span>
                <span><strong>Alto</strong> — top 33%</span>
            </div>
            <div class='rm-legend__row'>
                <span class='rm-legend__dot' style='background:{BRAND["med"]}'></span>
                <span><strong>Médio</strong> — 33% intermediário</span>
            </div>
            <div class='rm-legend__row'>
                <span class='rm-legend__dot' style='background:{BRAND["low"]}'></span>
                <span><strong>Baixo</strong> — 33% inferior</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, message: str, icon: str = "○") -> None:
    st.markdown(
        f"""
        <div class='rm-empty'>
            <div class='rm-empty__icon'>{html.escape(icon)}</div>
            <div class='rm-empty__title'>{html.escape(title)}</div>
            <div>{html.escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav_card(icon: str, title: str, description: str, page_path: str) -> None:
    """Nav card that behaves like a page link. Uses st.page_link inside a styled container."""
    with st.container(border=False):
        st.markdown(
            f"""
            <div class='rm-nav-card'>
                <div class='rm-nav-card__icon'>{html.escape(icon)}</div>
                <div class='rm-nav-card__title'>{html.escape(title)}</div>
                <div class='rm-nav-card__desc'>{html.escape(description)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link(page_path, label=f"Abrir {title} →")


def section_title(title: str, hint: str = "") -> None:
    hint_html = (
        f"<span class='rm-section-title__hint'>{html.escape(hint)}</span>"
        if hint else ""
    )
    st.markdown(
        f"""
        <div class='rm-section-title'>
            <h2>{html.escape(title)}</h2>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_risk_color(risk_level: str | None) -> str:
    """Cor derivada do risk_level (Alto/Médio/Baixo).

    Usar risk_level em vez do score bruto garante que a cor no mapa bata
    com o filtro de nível e com a legenda: como o nível é atribuído por
    ranking (top 33% = Alto), duas paradas com o mesmo score podem ter
    níveis diferentes, e o mapa deve refletir o nível, não o número.
    """
    if not risk_level:
        return "#8A93A3"
    mapping = {
        "Alto":  BRAND["high"],
        "Medio": BRAND["med"],
        "Médio": BRAND["med"],
        "Baixo": BRAND["low"],
    }
    return mapping.get(risk_level, "#8A93A3")
