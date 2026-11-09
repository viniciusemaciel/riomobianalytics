"""Ponto de entrada do RioMobiAnalytics (Streamlit Community Cloud: webapp/Home.py).

Define a navegação no topo e carrega o tema uma vez por execução. As páginas
ficam em `webapp/views/`.
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from webapp.utils.theme import ASSETS_DIR, PAGE_ICON, apply_theme  # noqa: E402

st.set_page_config(
    page_title="RioMobiAnalytics",
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.logo(
    str(ASSETS_DIR / "logo_full.png"),
    icon_image=str(ASSETS_DIR / "logo_mark.png"),
    size="large",
)

apply_theme()

pages = [
    st.Page("views/inicio.py", title="Início", default=True),
    st.Page("views/mapa.py", title="Mapa", url_path="mapa"),
    st.Page("views/rede.py", title="Rede", url_path="rede"),
    st.Page("views/assistente.py", title="Assistente", url_path="assistente"),
    st.Page("views/risco.py", title="Risco", url_path="risco"),
    st.Page("views/metodologia.py", title="Metodologia", url_path="metodologia"),
]

st.navigation(pages, position="top").run()
