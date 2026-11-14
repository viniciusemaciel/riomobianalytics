"""Assistente — perguntas em português sobre os dados, com a parada selecionada como contexto.

A interface está pronta; a resposta vem de `webapp.utils.assistente.responder`,
que a Frente 3 (RAG) implementa.
"""
import html
import json

import streamlit as st

import config
from webapp.utils import assistente
from webapp.utils.data_fetchers import get_stop_details
from webapp.utils.state import get_selected, go as go_page, set_selected
from webapp.utils.theme import ASSETS_DIR, CREAM, fmt_int, normalize_level, page_header

st.markdown(
    f"<style>[data-testid='stAppViewContainer'], [data-testid='stHeader'] {{ background: {CREAM} !important; }}"
    f"[data-testid='stBottomBlockContainer'], [data-testid='stBottom'] > div {{ background: {CREAM} !important; }}</style>",
    unsafe_allow_html=True,
)

AVATAR = str(ASSETS_DIR / "logo_mark.png")

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

    opcoes = assistente.modelos()
    if len(opcoes) > 1:
        ids = [o[0] for o in opcoes]
        if st.session_state.get("rag_provedor") not in ids:
            st.session_state.rag_provedor = ids[0]
        st.segmented_control("Modelo", ids, format_func=dict(opcoes).get, key="rag_provedor",
                             help="Se o modelo escolhido falhar, a pergunta é refeita no outro automaticamente.")
    elif opcoes:
        st.session_state.rag_provedor = opcoes[0][0]

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
    sugestao = None
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"], avatar=AVATAR if msg["role"] == "assistant" else None):
            st.markdown(msg["text"])
            if msg.get("passos") or msg.get("uso"):
                with st.expander("Como cheguei nisso"):
                    if msg.get("uso"):
                        st.caption(assistente.resumo_uso(msg["uso"], msg.get("rodadas", 0), msg.get("duracao_ms", 0),
                                                         msg.get("provedor")))
                    if msg.get("fallback"):
                        st.caption(f"Fallback: {assistente.nome_provedor(msg['fallback']['de'])} falhou "
                                   f"({msg['fallback']['motivo']}); respondido por {assistente.nome_provedor(msg.get('provedor'))}.")
                    for p in msg.get("passos", []):
                        st.markdown(f"- `{p['ferramenta']}` {json.dumps(p['argumentos'], ensure_ascii=False)}"
                                    f"{'' if p['ok'] else ' (falhou)'} · {p['duracao_ms']} ms")
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
                sugestao = s

    if not assistente.disponivel():
        st.markdown(
            "<div style='background:#fff;border:1px solid #E2E6EB;border-left:3px solid #0B1F3A;border-radius:0;"
            "padding:12px 16px;margin-top:14px' class='rm-muted'>O assistente está desligado: falta configurar a "
            "chave de um modelo (ANTHROPIC_API_KEY ou GEMINI_API_KEY). O restante do app funciona normalmente.</div>",
            unsafe_allow_html=True,
        )

# A pergunta entra no histórico e a página recarrega na hora (o usuário vê a mensagem).
# A resposta é gerada na execução seguinte, para qualquer pergunta que ainda esteja sem
# resposta: se uma execução for interrompida no meio, a próxima retoma a pergunta, em vez
# de deixá-la pendurada. Enquanto responde, a caixa de texto fica desativada.
aguardando = bool(st.session_state.chat) and st.session_state.chat[-1]["role"] == "user"
question = st.chat_input("Pergunte sobre paradas, linhas ou segurança no entorno", disabled=aguardando) or sugestao
if question and not aguardando:
    st.session_state.chat.append({"role": "user", "text": question})
    if not assistente.disponivel():
        st.session_state.chat.append({
            "role": "assistant",
            "text": "O assistente está desligado: falta configurar a chave do modelo.",
        })
    elif st.session_state.get("n_perguntas", 0) >= config.RAG_MAX_PERGUNTAS_SESSAO:
        st.session_state.chat.append({
            "role": "assistant",
            "text": f"Você chegou ao limite de {config.RAG_MAX_PERGUNTAS_SESSAO} perguntas desta sessão. Recarregue a página para continuar.",
        })
    else:
        st.session_state.n_perguntas = st.session_state.get("n_perguntas", 0) + 1
    st.rerun()

if aguardando:
    pergunta = st.session_state.chat[-1]["text"]
    historico = st.session_state.chat[:-1]
    with center, st.chat_message("assistant", avatar=AVATAR):
        with st.status("Pensando...", expanded=True) as status:
            def _andamento(rotulo):
                status.update(label=rotulo)
                status.caption(rotulo)

            _andamento("Lendo a pergunta...")
            try:
                ans = assistente.responder(pergunta, ctx, historico, ao_chamar=_andamento,
                                           provedor=st.session_state.get("rag_provedor"), ao_trocar=_andamento)
                st.session_state.chat.append({"role": "assistant", "text": ans.get("texto", ""),
                                              "fontes": ans.get("fontes", []), "passos": ans.get("passos", []),
                                              "uso": ans.get("uso"), "rodadas": ans.get("rodadas", 0),
                                              "duracao_ms": ans.get("duracao_ms", 0),
                                              "provedor": ans.get("provedor"), "fallback": ans.get("fallback")})
                st.session_state.custo_sessao = st.session_state.get("custo_sessao", 0.0) + assistente.custo_estimado(ans.get("uso") or {}, ans.get("provedor"))
            except Exception as e:
                status.update(label="Não consegui responder", state="error")
                st.session_state.chat.append({"role": "assistant", "text": f"Não consegui responder agora: {e}"})
    st.rerun()

with center:
    st.markdown(
        "<p class='rm-muted' style='text-align:center;margin-top:1.5rem'>Responde só com os dados do projeto. "
        "Não prevê ocorrências individuais nem recomenda rotas.</p>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("n_perguntas"):
        st.caption(f"Sessão: {st.session_state.n_perguntas} pergunta(s) · ~US$ {st.session_state.get('custo_sessao', 0.0):.4f} estimados")
