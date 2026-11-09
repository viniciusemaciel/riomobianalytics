"""Ponto de encaixe do assistente (RAG).

A página `views/assistente.py` chama `responder(...)`. A lógica fica em
`webapp/rag/` (agente, ferramentas, prompt); este módulo é só a fachada.

    responder(pergunta, contexto, historico, ao_chamar) -> dict com
        "texto":  resposta em Markdown, com marcadores [1], [2] citando fontes
        "fontes": lista de {"id": "1", "titulo": "...", "detalhe": "..."}
        "passos": ferramentas chamadas (para o expansor "Como cheguei nisso")
"""
from __future__ import annotations

ROTULOS_FERRAMENTA = {
    "estatisticas_gerais": "Consultando os totais do projeto...",
    "paradas_mais_criticas": "Consultando as paradas de maior índice...",
    "buscar_parada": "Buscando paradas...",
    "resumo_bairros": "Agrupando paradas por bairro...",
    "detalhes_parada": "Consultando os detalhes da parada...",
    "reclamacoes_parada": "Consultando as reclamações da parada...",
    "resumo_reclamacoes": "Contando reclamações por categoria...",
    "metricas_linhas": "Consultando as linhas...",
    "rede_em_volta": "Consultando as paradas ligadas...",
}


def disponivel() -> bool:
    from webapp.rag import llm
    return llm.chave_configurada()


def responder(pergunta: str, contexto: dict | None = None, historico: list[dict] | None = None,
              ao_chamar=None) -> dict:
    from webapp.rag import agent, prompts, tools
    from webapp.rag.llm import ErroLLM

    try:
        res = agent.responder(
            pergunta,
            system_prompt=prompts.SYSTEM_PROMPT,
            ferramentas=tools,
            historico=historico,
            contexto=contexto,
            ao_chamar=(lambda nome, args: ao_chamar(ROTULOS_FERRAMENTA.get(nome, "Consultando os dados..."))) if ao_chamar else None,
        )
    except ErroLLM as e:
        raise RuntimeError(str(e)) from e
    return res.como_dict()


SUGESTOES_COM_PARADA = [
    "Por que esta parada tem esse índice de risco?",
    "Quais paradas vizinhas têm índice parecido?",
    "Quais linhas passam por esta parada?",
]

SUGESTOES_GERAIS = [
    "Quais são as 10 paradas com maior índice de risco?",
    "Quais bairros têm mais paradas de nível alto?",
    "Quais linhas passam por mais paradas de nível alto?",
]
