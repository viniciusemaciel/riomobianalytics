"""Assistente — perguntas em português sobre os dados, com a parada selecionada como contexto.

A interface está pronta; a resposta vem de `webapp.utils.assistente.responder`,
que a Frente 3 (RAG) implementa.
"""
import html

import streamlit as st

from webapp.utils import assistente
from webapp.utils.data_fetchers import get_stop_details
from webapp.utils.state import get_selected, go as go_page, set_selected
from webapp.utils.theme import ASSETS_DIR, CREAM, fmt_int, normalize_level, page_header

st.markdown(
    f"<style>[data-testid='stAppViewContainer'], [data-testid='stHeader'] {{ background: {CREAM} !important; }}"
    f"[data-testid='stBottomBlockContainer'], [data-testid='stBottom'] > div {{ background: {CREAM} !important; }}</style>",
    unsafe_allow_html=True,
)

if "chat" not in st.session_state:
    st.session_state.chat = []

sel = get_selected()
ctx = None
if sel:
    try:
        det = get_stop_details(sel)
    except Exception:
        det = None
    if det:
        ctx = {
            "stop_id": sel,
            "nome": det.get("name"),
            "indice": round(float(det.get("risk_score_normalized") or 0)),
            "nivel": normalize_level(det.get("risk_level")),
            "reclamacoes": int(det.get("total_complaints") or 0),
            "score_tiroteio": round(float(det.get("risk_score_tiroteio") or 0) * 100),
            "linhas": sorted({r for r in (det.get("routes") or []) if r}),
        }

_, center, _ = st.columns([1, 3, 1])
with center:
    page_header("Assistente", "Pergunte sobre os dados",
                "As respostas usam só os dados do projeto e mostram a fonte de cada afirmação.")

    if ctx:
        a, b = st.columns([5, 1.2], vertical_alignment="center")
        a.markdown(
            f"<span class='rm-chip'><span class='rm-eyebrow' style='font-size:10px'>Contexto</span>"
            f"<span class='rm-chip__dot'></span><b>{html.escape(ctx['nome'] or '')}</b>"
            f"<span style='color:#8C97A6'>índice {ctx['indice']} · {fmt_int(len(ctx['linhas']))} linhas</span></span>",
            unsafe_allow_html=True,
        )
        if b.button("Remover", type="tertiary", key="ctx_off"):
            set_selected(None)
            st.rerun()
    else:
        a, b = st.columns([5, 1.6], vertical_alignment="center")
        a.markdown("<span class='rm-muted'>Sem parada selecionada. As perguntas valem para a cidade toda.</span>",
                   unsafe_allow_html=True)
        if b.button("Escolher no mapa", type="tertiary", key="ctx_pick"):
            go_page("mapa")

    st.write("")
    pending = None
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"], avatar=str(ASSETS_DIR / "logo_mark.png") if msg["role"] == "assistant" else None):
            st.markdown(msg["text"])
            if msg.get("fontes"):
                st.markdown(
                    "<div class='rm-eyebrow' style='margin-top:8px'>Fontes</div>"
                    + "".join(
                        f"<span class='rm-route' style='margin:6px 6px 0 0;display:inline-block'>{html.escape(f['id'])} · "
                        f"{html.escape(f['titulo'])}</span>" for f in msg["fontes"]),
                    unsafe_allow_html=True,
                )

    if not st.session_state.chat:
        st.markdown("<div class='rm-eyebrow' style='margin:6px 0 10px'>Sugestões</div>", unsafe_allow_html=True)
        sugs = assistente.SUGESTOES_COM_PARADA if ctx else assistente.SUGESTOES_GERAIS
        for i, s in enumerate(sugs):
            if st.button(s, key=f"sug_{i}"):
                pending = s

    if not assistente.disponivel():
        st.markdown(
            "<div style='background:#fff;border:1px solid #E2E6EB;border-left:3px solid #0B1F3A;border-radius:0;"
            "padding:12px 16px;margin-top:14px' class='rm-muted'>O assistente ainda não está conectado. "
            "A busca nos dados (RAG) é a próxima etapa do projeto; a interface e o contexto da parada já estão prontos.</div>",
            unsafe_allow_html=True,
        )

question = st.chat_input("Pergunte sobre paradas, linhas ou segurança no entorno") or pending
if question:
    st.session_state.chat.append({"role": "user", "text": question})
    if assistente.disponivel():
        try:
            ans = assistente.responder(question, ctx)
            st.session_state.chat.append({"role": "assistant", "text": ans.get("texto", ""), "fontes": ans.get("fontes", [])})
        except Exception as e:
            st.session_state.chat.append({"role": "assistant", "text": f"Não consegui responder agora ({e})."})
    else:
        st.session_state.chat.append({
            "role": "assistant",
            "text": "Ainda não consigo responder: o assistente será conectado aos dados na próxima etapa do projeto.",
        })
    st.rerun()

with center:
    st.markdown(
        "<p class='rm-muted' style='text-align:center;margin-top:1.5rem'>Responde só com os dados do projeto. "
        "Não prevê ocorrências individuais nem recomenda rotas.</p>",
        unsafe_allow_html=True,
    )
