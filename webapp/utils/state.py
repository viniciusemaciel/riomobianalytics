"""Estado compartilhado entre páginas: a parada selecionada no mapa.

Mapa, Rede e Assistente leem a mesma chave do `st.session_state`, então
escolher uma parada numa página vale para as outras.
"""
from __future__ import annotations

import streamlit as st

KEY = "selected_stop_id"
# Parada com que o usuário abriu o Assistente pelo botão do mapa ("Perguntar sobre esta parada").
ASSISTENTE_PARADA = "assistente_parada_pedida"

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


def ask_about(stop_id: str) -> None:
    """Seleciona a parada e abre o Assistente com ela como contexto e as sugestões dela à vista."""
    set_selected(stop_id)
    st.session_state[ASSISTENTE_PARADA] = stop_id
    go("assistente")
