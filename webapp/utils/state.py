"""Estado compartilhado entre páginas: a parada selecionada no mapa.

Mapa, Rede e Assistente leem a mesma chave do `st.session_state`, então
escolher uma parada numa página vale para as outras.
"""
from __future__ import annotations

import streamlit as st

KEY = "selected_stop_id"

PAGES = {
    "inicio": "views/inicio.py",
    "mapa": "views/mapa.py",
    "rede": "views/rede.py",
    "assistente": "views/assistente.py",
    "risco": "views/risco.py",
    "metodologia": "views/metodologia.py",
}


def get_selected() -> str | None:
    return st.session_state.get(KEY)


def set_selected(stop_id: str | None) -> None:
    if stop_id:
        st.session_state[KEY] = stop_id
    else:
        st.session_state.pop(KEY, None)


def go(page: str) -> None:
    st.switch_page(PAGES[page])
