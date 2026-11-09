"""Início — apresenta o projeto e leva às três formas de explorar os dados."""
import streamlit as st

from webapp.utils.data_fetchers import get_stops_with_risk, get_system_stats
from webapp.utils.insights import model_metrics, network_art_svg
from webapp.utils.state import go as go_page
from webapp.utils.theme import ORANGE, fmt_dec, fmt_int, normalize_level, stat_band


@st.cache_data(ttl=600, show_spinner=False)
def hero_art() -> str:
    try:
        df = get_stops_with_risk()
        hi = df[df["risk_level"].map(normalize_level) == "Alto"][["lat", "lon"]]
    except Exception:
        hi = None
    return network_art_svg(hi)


@st.cache_data(show_spinner=False)
def map_card_art() -> str:
    try:
        df = get_stops_with_risk()
        hi = df[df["risk_level"].map(normalize_level) == "Alto"][["lat", "lon"]]
    except Exception:
        hi = None
    return network_art_svg(hi, w=360, h=150, lon0=-43.36, lon1=-43.17, latc=-22.89)


RINGS_SVG = """<svg viewBox="0 0 360 150" xmlns="http://www.w3.org/2000/svg">
<g fill="none" stroke="#DCE1E7" stroke-dasharray="2 4"><circle cx="180" cy="75" r="28"/><circle cx="180" cy="75" r="52"/><circle cx="180" cy="75" r="76"/></g>
<g stroke="#C3CBD5" stroke-width="1.3"><line x1="180" y1="75" x2="160" y2="56"/><line x1="180" y1="75" x2="205" y2="88"/><line x1="160" y1="56" x2="140" y2="30"/>
<line x1="160" y1="56" x2="130" y2="80"/><line x1="205" y1="88" x2="228" y2="60"/><line x1="205" y1="88" x2="215" y2="124"/><line x1="140" y1="30" x2="118" y2="10"/>
<line x1="228" y1="60" x2="252" y2="40"/><line x1="130" y1="80" x2="108" y2="112"/><line x1="215" y1="124" x2="250" y2="118"/></g>
<g stroke="#fff" stroke-width="1.5"><circle cx="160" cy="56" r="5.5" fill="#D9542F"/><circle cx="205" cy="88" r="5.5" fill="#F08463"/><circle cx="140" cy="30" r="5" fill="#F08463"/>
<circle cx="130" cy="80" r="5" fill="#F2B19C"/><circle cx="228" cy="60" r="5" fill="#D9542F"/><circle cx="215" cy="124" r="5" fill="#F2B19C"/><circle cx="118" cy="10" r="4.5" fill="#F2DDD5"/>
<circle cx="252" cy="40" r="4.5" fill="#F08463"/><circle cx="108" cy="112" r="4.5" fill="#F2DDD5"/><circle cx="250" cy="118" r="4.5" fill="#F2B19C"/></g>
<circle cx="180" cy="75" r="9" fill="#0B1F3A" stroke="rgba(11,31,58,.2)" stroke-width="6"/></svg>"""

CHAT_SVG = """<svg viewBox="0 0 360 150" xmlns="http://www.w3.org/2000/svg">
<rect x="150" y="22" width="180" height="30" rx="12" fill="#0B1F3A"/><rect x="166" y="34" width="120" height="6" rx="3" fill="#fff" fill-opacity=".85"/>
<rect x="30" y="66" width="230" height="8" rx="4" fill="#B9C2CD"/><rect x="30" y="82" width="270" height="8" rx="4" fill="#CDD4DC"/><rect x="30" y="98" width="190" height="8" rx="4" fill="#CDD4DC"/>
<g font-family="Geist Mono, monospace" font-size="9" fill="#566579"><rect x="30" y="116" width="58" height="20" rx="6" fill="#fff" stroke="#E2E6EB"/><text x="40" y="129">1 modelo</text>
<rect x="94" y="116" width="58" height="20" rx="6" fill="#fff" stroke="#E2E6EB"/><text x="104" y="129">2 gtfs</text></g>
<circle cx="296" cy="102" r="5" fill="#F26A4B"/></svg>"""

# ---------- Hero ----------
left, right = st.columns([1, 1.08], gap="large", vertical_alignment="center")
with left:
    st.markdown(
        "<div class='rm-eyebrow'>Pós-graduação em Ciência de Dados · Rio de Janeiro</div>"
        "<div class='rm-hero__title'>Risco no entorno das paradas de ônibus do Rio</div>"
        "<p class='rm-hero__lead'>Cruzamos a rede de ônibus com reclamações da Central 1746 e "
        "registros de tiroteio para comparar o risco no entorno de cada parada da cidade.</p>",
        unsafe_allow_html=True,
    )
    b1, b2, _ = st.columns([1.1, 1.1, 1.2])
    if b1.button("Abrir o mapa →", type="primary", width="stretch", key="home_mapa"):
        go_page("mapa")
    if b2.button("Como funciona", width="stretch", key="home_metodo"):
        go_page("metodologia")
with right:
    st.markdown(
        f"<div class='rm-hero__art'>{hero_art()}"
        f"<span class='rm-hero__caption'><span class='rm-dot' style='background:{ORANGE}'></span>"
        f"paradas de nível alto · Zona Norte e Centro</span></div>",
        unsafe_allow_html=True,
    )

st.write("")

# ---------- Números ----------
try:
    stats = get_system_stats()
except Exception:
    stats = {}
try:
    auc = model_metrics().get("auc")
except Exception:
    auc = None
stat_band([
    (fmt_int(stats.get("total_stops")), "paradas de ônibus"),
    (fmt_int(stats.get("total_routes")), "linhas"),
    (fmt_int(stats.get("total_complaints")), "reclamações 1746 vinculadas"),
    (fmt_dec(auc) if auc else "—", "AUC do modelo, validação 2024"),
])

# ---------- Como funciona ----------
steps = [
    ("01", "Fontes", "GTFS da rede de ônibus, Central 1746 e Fogo Cruzado", False),
    ("02", "Grafo", "Neo4j liga as paradas pelas linhas. MongoDB guarda as reclamações", False),
    ("03", "Modelo", "XGBoost estima o risco de tiroteio a até 500 m de cada parada", True),
    ("04", "Índice", "Reclamações e modelo viram um índice de 0 a 100 por parada", False),
]
flow = []
for i, (n, t, d, acc) in enumerate(steps):
    dot = f"<span class='rm-dot' style='background:{ORANGE}'></span>" if acc else ""
    flow.append(
        f"<div class='rm-flow__step{' rm-flow__step--accent' if acc else ''}'>"
        f"<div class='rm-flow__num'><span>{n}</span>{dot}</div>"
        f"<div class='rm-flow__title'>{t}</div><div class='rm-flow__desc'>{d}</div></div>"
    )
    if i < len(steps) - 1:
        flow.append("<div class='rm-flow__arrow'></div>")
st.markdown(
    "<div class='rm-section'><div class='rm-eyebrow'>Como funciona</div>"
    "<h2>Da rede de ônibus a um índice por parada</h2></div>"
    f"<div class='rm-flow'>{''.join(flow)}</div>",
    unsafe_allow_html=True,
)

# ---------- Por onde começar ----------
st.markdown(
    "<div class='rm-section'><div class='rm-eyebrow'>Por onde começar</div>"
    "<h2>Três formas de explorar os dados</h2></div>",
    unsafe_allow_html=True,
)
cards = [
    ("Mapa", "O índice de cada parada na cidade, com filtros por nível, linha e camada.", None, "mapa"),
    ("Rede", "As paradas ligadas a uma origem, organizadas pela distância na rede.", RINGS_SVG, "rede"),
    ("Assistente", "Perguntas em português sobre paradas e linhas, com a fonte de cada resposta.", CHAT_SVG, "assistente"),
]
cols = st.columns(3, gap="medium")
for col, (title, desc, art, page) in zip(cols, cards):
    with col:
        with st.container(border=True):
            art_html = art if art else map_card_art()
            st.markdown(
                f"<div class='rm-card-art'>{art_html}</div>"
                f"<div class='rm-card-title'>{title}</div><div class='rm-card-desc'>{desc}</div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Abrir {title.lower()} →", key=f"card_{page}", width="stretch"):
                go_page(page)

st.markdown(
    "<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-top:2.5rem;"
    "padding-top:1.25rem;border-top:1px solid #E2E6EB'>"
    "<span class='rm-muted'>O índice compara paradas. Não é previsão de ocorrência nem recomendação de rota.</span>"
    "<span class='rm-eyebrow'>Fontes: GTFS Rio · Central 1746 · Fogo Cruzado</span></div>",
    unsafe_allow_html=True,
)
