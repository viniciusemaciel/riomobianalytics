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
import streamlit.components.v1 as components

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

    logo_uri = _asset_data_uri(str(LOGO_FULL))
    if logo_uri:
        # Injeta a logo no topo do sidebar + botão custom "abrir sidebar".
        # Roda dentro de um iframe (components.html) mas manipula o
        # window.parent.document. O clique é sintetizado com pointerdown+
        # mouseup+click porque botões React do Streamlit não respondem a
        # HTMLElement.click() puro em algumas versões.
        components.html(
            f"""
            <script>
            (function() {{
                const LOGO_ID = 'rm-sidebar-logo-node';
                const TOGGLE_ID = 'rm-sidebar-toggle';
                const LOGO_URI = "{logo_uri}";
                const doc = window.parent.document;
                const win = window.parent;

                function findNativeToggle() {{
                    // Streamlit 1.60 usa dois botões distintos:
                    //   • stExpandSidebarButton — no toolbar do topo, aparece
                    //     APENAS quando o sidebar está colapsado.
                    //   • stSidebarCollapseButton — dentro do sidebar, aparece
                    //     apenas quando o sidebar está aberto.
                    // Como o nosso botão custom só é visível na condição
                    // "sidebar colapsado", queremos sempre o Expand.
                    const selectors = [
                        'button[data-testid="stExpandSidebarButton"]',
                        '[data-testid="stExpandSidebarButton"]',
                        '[data-testid="stExpandSidebarButton"] button',
                        // Fallbacks pra outras versões:
                        '[data-testid="stSidebarCollapsedControl"] button',
                        '[data-testid="collapsedControl"] button',
                    ];
                    for (const sel of selectors) {{
                        const nodes = doc.querySelectorAll(sel);
                        for (const n of nodes) {{
                            if (n && n.id !== TOGGLE_ID) return n;
                        }}
                    }}
                    return null;
                }}

                function fireRealClick(el) {{
                    // Botões React do Streamlit escutam pointerdown+mouseup, e
                    // ignoram HTMLElement.click() em alguns casos. Disparamos
                    // uma sequência realista de eventos usando as classes
                    // Event do window.parent (mesma origem que o alvo).
                    const rect = el.getBoundingClientRect();
                    const opts = {{
                        bubbles: true, cancelable: true, view: win,
                        clientX: rect.left + rect.width / 2,
                        clientY: rect.top + rect.height / 2,
                        button: 0,
                    }};
                    try {{ el.dispatchEvent(new win.PointerEvent('pointerdown', opts)); }} catch(e) {{}}
                    el.dispatchEvent(new win.MouseEvent('mousedown', opts));
                    try {{ el.dispatchEvent(new win.PointerEvent('pointerup', opts)); }} catch(e) {{}}
                    el.dispatchEvent(new win.MouseEvent('mouseup', opts));
                    el.dispatchEvent(new win.MouseEvent('click', opts));
                    el.click();
                }}

                function openSidebar() {{
                    const native = findNativeToggle();
                    if (native) {{ fireRealClick(native); return true; }}
                    return false;
                }}

                function ensureToggleButton() {{
                    let btn = doc.getElementById(TOGGLE_ID);
                    if (!btn) {{
                        btn = doc.createElement('button');
                        btn.id = TOGGLE_ID;
                        btn.type = 'button';
                        btn.setAttribute('aria-label', 'Abrir menu lateral');
                        btn.innerHTML = '&raquo;';
                        btn.addEventListener('click', (e) => {{
                            e.preventDefault();
                            e.stopPropagation();
                            openSidebar();
                        }});
                        doc.body.appendChild(btn);
                    }}
                    return btn;
                }}

                function updateToggleVisibility() {{
                    const btn = ensureToggleButton();
                    const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
                    let collapsed = true;
                    if (sidebar) {{
                        const rect = sidebar.getBoundingClientRect();
                        collapsed = rect.width < 40;
                    }}
                    btn.classList.toggle('rm-visible', collapsed);
                }}

                function injectLogo() {{
                    const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
                    if (!sidebar) return;
                    ['transform', 'visibility', 'width'].forEach(k => {{
                        if (sidebar.style[k]) sidebar.style[k] = '';
                    }});
                    const existing = doc.getElementById(LOGO_ID);
                    if (existing && existing.parentElement !== sidebar) {{
                        existing.remove();
                    }}
                    let card = doc.getElementById(LOGO_ID);
                    if (!card) {{
                        card = doc.createElement('div');
                        card.id = LOGO_ID;
                        card.className = 'rm-sidebar-logo';
                        const img = doc.createElement('img');
                        img.src = LOGO_URI;
                        img.alt = 'RioMobiAnalytics';
                        card.appendChild(img);
                    }}
                    if (sidebar.firstChild !== card) {{
                        sidebar.insertBefore(card, sidebar.firstChild);
                    }}
                }}

                function tick() {{
                    injectLogo();
                    updateToggleVisibility();
                }}

                if (!win.__rmSidebarObserver) {{
                    const obs = new win.MutationObserver(tick);
                    obs.observe(doc.body, {{childList: true, subtree: true}});
                    win.__rmSidebarObserver = obs;
                }}
                if (!win.__rmSidebarInterval) {{
                    win.__rmSidebarInterval = win.setInterval(updateToggleVisibility, 500);
                }}
                tick();
            }})();
            </script>
            """,
            height=0,
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
