"""Assistente — perguntas em português sobre os dados, com a parada selecionada como contexto.

A resposta vem de `webapp.utils.assistente.responder` (agente em `webapp/rag/`);
gráficos, tabelas e mapas das respostas são desenhados por `webapp/rag/render.py`.
Os temas e perguntas de exemplo vêm de `webapp/rag/catalogo.py`.

Layout: uma coluna estreita e centrada, no fundo cinza do app.
- Sem conversa: título, um cartão com a parada em contexto e a caixa de pergunta,
  os temas como abas com três perguntas num único cartão, e o link "O que o
  assistente sabe". Modelo e uso da sessão ficam no popover "Ajustes".
- Com conversa: barra compacta (contexto, "Nova conversa", "Ajustes"), pergunta do
  usuário num balão azul-marinho à direita, resposta num cartão branco, e a caixa
  de pergunta fixa embaixo.

Vindo do botão "Perguntar sobre esta parada" do mapa, a página recebe a parada em
`selected_stop_id` e a marca em `state.ASSISTENTE_PARADA`: as sugestões da parada
aparecem mesmo com conversa em andamento, até a próxima pergunta.
"""
import html
import json

import streamlit as st

import config
from webapp.rag import catalogo, render
from webapp.utils import assistente
from webapp.utils.data_fetchers import get_stop_details
from webapp.utils.state import ASSISTENTE_PARADA, get_selected, go as go_page, set_selected
from webapp.utils.theme import ASSETS_DIR, fmt_int, normalize_level, page_header

st.markdown("<style>[data-testid='stBottomBlockContainer'] { max-width: 960px !important; }</style>",
            unsafe_allow_html=True)

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


# ------------------------------------------------------------------ peças
def _sugestoes(prefixo: str) -> str | None:
    """Temas como abas e as três perguntas do tema num cartão. Devolve a pergunta clicada."""
    temas = catalogo.temas(com_parada=bool(ctx))
    ids = [t.id for t in temas]
    chave = f"{prefixo}_tema"
    if st.session_state.get(chave) not in ids:
        st.session_state[chave] = ids[0]
    with st.container(key=f"{prefixo}_temas"):
        st.segmented_control("Tema", ids, format_func={t.id: t.nome for t in temas}.get, key=chave,
                             label_visibility="collapsed")
    tema = next((t for t in temas if t.id == st.session_state.get(chave)), temas[0])
    escolhida = None
    with st.container(key=f"card_{prefixo}_perguntas"):
        st.markdown(f"<p class='rm-tema-desc'>{html.escape(tema.descricao)}</p>", unsafe_allow_html=True)
        for i, p in enumerate(tema.perguntas):
            if st.button(p.texto, key=f"{prefixo}_{tema.id}_{i}", width="stretch"):
                escolhida = p.texto
    return escolhida


def _contexto(chave: str) -> None:
    """Parada em contexto (com botão para tirar) ou o convite para escolher uma no mapa."""
    a, b = st.columns([5, 1.4], vertical_alignment="center", gap="small")
    if ctx:
        a.markdown(
            f"<span class='rm-chip'><span class='rm-chip__dot'></span><b>{html.escape(ctx['nome'] or '')}</b>"
            f"<span class='rm-muted'>índice {ctx['indice']} · {fmt_int(len(ctx['linhas']))} linhas</span></span>",
            unsafe_allow_html=True,
        )
        if b.button("Remover", type="tertiary", key=f"{chave}_off", help="Perguntar sobre a cidade toda"):
            set_selected(None)
            st.rerun()
    else:
        a.markdown("<span class='rm-muted'>Perguntas sobre a cidade toda.</span>", unsafe_allow_html=True)
        if b.button("Escolher parada", type="tertiary", key=f"{chave}_pick", help="Abre o mapa para escolher uma parada"):
            go_page("mapa")


def _ajustes() -> None:
    with st.popover("Ajustes", icon=":material/tune:"):
        opcoes = assistente.modelos()
        if len(opcoes) > 1:
            ids = [o[0] for o in opcoes]
            if st.session_state.get("rag_provedor") not in ids:
                st.session_state.rag_provedor = ids[0]
            st.segmented_control("Modelo", ids, format_func=dict(opcoes).get, key="rag_provedor")
            st.caption("Se o modelo escolhido falhar, a pergunta é refeita no outro automaticamente.")
        elif opcoes:
            st.session_state.rag_provedor = opcoes[0][0]
            st.caption(f"Modelo: {opcoes[0][1]}")
        else:
            st.caption("Nenhum modelo configurado.")
        n = st.session_state.get("n_perguntas", 0)
        st.caption(f"Nesta sessão: {n} de {config.RAG_MAX_PERGUNTAS_SESSAO} perguntas"
                   + (f" · ~US$ {st.session_state.get('custo_sessao', 0.0):.4f}" if n else ""))


def _o_que_sabe() -> None:
    docs = catalogo.documentos()
    internos = [d for d in docs if d["tipo"] != "externo"]
    externos = [d for d in docs if d["tipo"] == "externo"]
    linhas = "".join(f"<li><b>{html.escape(a)}</b><span>{html.escape(b)}</span></li>" for a, b in catalogo.DADOS_AO_VIVO)
    ext = "".join(
        f"<li><b>{html.escape(catalogo.titulo_curto(d['titulo']))}</b>"
        f"<span>{html.escape(d['periodo_coberto'])}"
        f"{' · acessado em ' + html.escape(d['acessado_em']) if d['acessado_em'] else ''}</span></li>" for d in externos)
    nao = "".join(f"<li>{html.escape(t)}</li>" for t in catalogo.NAO_RESPONDE)
    titulos = ", ".join(html.escape(catalogo.titulo_curto(d["titulo"])) for d in internos)
    st.markdown(
        "<div class='rm-know'>"
        "<div class='rm-eyebrow'>Consulta ao vivo no banco</div>"
        f"<ul class='rm-know__list'>{linhas}</ul>"
        f"<div class='rm-eyebrow'>Documentação do projeto · {len(internos)} textos</div>"
        f"<p class='rm-know__p'>{titulos}.</p>"
        f"<div class='rm-eyebrow'>Fontes externas · {len(externos)} resumos</div>"
        f"<ul class='rm-know__list'>{ext}</ul>"
        "<p class='rm-know__p'>Sempre citadas como “segundo [fonte]”. Não são dados do projeto.</p>"
        "<div class='rm-eyebrow'>Não responde</div>"
        f"<ul class='rm-know__list rm-know__list--no'>{nao}</ul>"
        "</div>",
        unsafe_allow_html=True,
    )


def _fonte_curta(titulo: str) -> str:
    prefixo = "Documentação do projeto: "
    if titulo.startswith(prefixo):
        partes = [catalogo.titulo_curto(x.strip()).replace(" > ", " › ") for x in titulo[len(prefixo):].split(";")]
        return "Documentação · " + "; ".join(partes)
    return titulo


def _fontes(fontes: list[dict]) -> None:
    itens = "".join(
        f"<li title='{html.escape(f['titulo'])}'><span class='rm-fontes__n'>{html.escape(f['id'])}</span>"
        f"<span class='rm-fontes__t'>{html.escape(_fonte_curta(f['titulo']))}</span></li>" for f in fontes)
    st.markdown(f"<div class='rm-fontes'><div class='rm-eyebrow'>Fontes</div><ul>{itens}</ul></div>",
                unsafe_allow_html=True)


def _bastidores(msg: dict) -> None:
    with st.expander("Como cheguei nisso"):
        if msg.get("uso"):
            st.caption(assistente.resumo_uso(msg["uso"], msg.get("rodadas", 0), msg.get("duracao_ms", 0),
                                             msg.get("provedor")))
        if msg.get("fallback"):
            st.caption(f"Fallback: {assistente.nome_provedor(msg['fallback']['de'])} falhou "
                       f"({msg['fallback']['motivo']}); respondido por {assistente.nome_provedor(msg.get('provedor'))}.")
        for p in msg.get("passos", []):
            args = json.dumps(p["argumentos"], ensure_ascii=False)
            args = "" if args == "{}" else (args if len(args) <= 140 else args[:140] + "…")
            st.markdown(f"- `{p['ferramenta']}` {args}{'' if p['ok'] else ' (falhou)'} · {p['duracao_ms']} ms")


# ------------------------------------------------------------------ página
PLACEHOLDER = "Pergunte sobre paradas, bairros ou o índice"
wrap = st.container(key="rm_assist")
sugestao = None
inline = None  # pergunta digitada na caixa do topo (tela sem conversa)
tem_chat = bool(st.session_state.chat)

if ctx is None or st.session_state.get(ASSISTENTE_PARADA) != ctx["stop_id"]:
    st.session_state.pop(ASSISTENTE_PARADA, None)
veio_do_mapa = bool(ctx) and st.session_state.get(ASSISTENTE_PARADA) == ctx["stop_id"]

with wrap:
    if not tem_chat:
        h, aj = st.columns([5, 1], vertical_alignment="top")
        with h:
            page_header("Assistente", "Pergunte sobre os dados",
                        "Responde com os dados do projeto e a documentação dele, e mostra a fonte de cada afirmação.")
        with aj, st.container(key="rm_aj"):
            _ajustes()
        with st.container(border=True, key="card_pergunta"):
            _contexto("ctx")
            inline = st.chat_input(PLACEHOLDER, key="pergunta_inicial")
        if not assistente.disponivel():
            st.markdown("<div class='rm-off'>O assistente está desligado: falta configurar a chave de um modelo "
                        "(ANTHROPIC_API_KEY ou GEMINI_API_KEY). O restante do app funciona normalmente.</div>",
                        unsafe_allow_html=True)
        st.markdown("<div class='rm-eyebrow rm-gap'>Comece por um tema</div>", unsafe_allow_html=True)
        sugestao = _sugestoes("ini")
        with st.container(key="rm_sabe"):
            with st.popover("O que o assistente sabe e o que não responde", icon=":material/info:", type="tertiary"):
                _o_que_sabe()
    else:
        with st.container(key="rm_topo"):
            t, n, aj = st.columns([5, 1.5, 1.2], vertical_alignment="center", gap="small")
            t.markdown("<div class='rm-assist-titulo'>Assistente</div>", unsafe_allow_html=True)
            if n.button("Nova conversa", key="nova", width="stretch"):
                st.session_state.chat = []
                st.rerun()
            with aj:
                _ajustes()
            _contexto("ctx_chat")

        for i, msg in enumerate(st.session_state.chat):
            if msg["role"] == "user":
                extra = f"<div class='rm-bolha__sub'>sobre {html.escape(msg['parada'])}</div>" if msg.get("parada") else ""
                st.markdown(f"<div class='rm-bolha-linha'><div class='rm-bolha'>{html.escape(msg['text'])}{extra}</div></div>",
                            unsafe_allow_html=True)
                continue
            with st.chat_message("assistant", avatar=AVATAR):
                st.markdown(msg["text"])
                if msg.get("visuais"):
                    render.desenhar(msg["visuais"], f"vis_{i}")
                if msg.get("fontes"):
                    _fontes(msg["fontes"])
                if msg.get("passos") or msg.get("uso"):
                    _bastidores(msg)

        if veio_do_mapa:
            st.markdown(f"<div class='rm-eyebrow rm-gap'>Sobre {html.escape(ctx['nome'] or 'esta parada')}</div>",
                        unsafe_allow_html=True)
            with st.container(key="card_mapa_perguntas"):
                for i, p in enumerate(catalogo.TEMA_PARADA.perguntas):
                    if st.button(p.texto, key=f"mapa_{i}", width="stretch"):
                        sugestao = p.texto
        elif st.session_state.chat[-1]["role"] == "assistant":
            with st.container(key="rm_mais"):
                with st.popover("Ver temas e exemplos de perguntas", icon=":material/lightbulb:"):
                    sugestao = _sugestoes("pop")

# A pergunta entra no histórico e a página recarrega na hora (o usuário vê a mensagem).
# A resposta é gerada na execução seguinte, para qualquer pergunta que ainda esteja sem
# resposta: se uma execução for interrompida no meio, a próxima retoma a pergunta, em vez
# de deixá-la pendurada. Enquanto responde, a caixa de texto fica desativada.
aguardando = bool(st.session_state.chat) and st.session_state.chat[-1]["role"] == "user"
if tem_chat:
    question = st.chat_input(PLACEHOLDER, disabled=aguardando, key="pergunta") or sugestao
else:
    question = inline or sugestao
if question and not aguardando:
    st.session_state.chat.append({"role": "user", "text": question, "parada": ctx["nome"] if ctx else None})
    st.session_state.pop(ASSISTENTE_PARADA, None)
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
    with wrap, st.chat_message("assistant", avatar=AVATAR):
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
                                              "provedor": ans.get("provedor"), "fallback": ans.get("fallback"),
                                              "visuais": ans.get("visuais", [])})
                st.session_state.custo_sessao = st.session_state.get("custo_sessao", 0.0) + assistente.custo_estimado(ans.get("uso") or {}, ans.get("provedor"))
            except Exception as e:
                status.update(label="Não consegui responder", state="error")
                st.session_state.chat.append({"role": "assistant", "text": f"Não consegui responder agora: {e}"})
    st.rerun()

with wrap:
    if not tem_chat:
        st.markdown("<p class='rm-assist-foot'>O índice compara paradas. Não prevê ocorrências nem recomenda rotas.</p>",
                    unsafe_allow_html=True)
