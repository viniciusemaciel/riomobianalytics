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
    "tiroteios_parada": "Consultando os tiroteios perto da parada...",
    "tiroteios_bairros": "Contando tiroteios por bairro...",
    "resumo_reclamacoes": "Contando reclamações por categoria...",
    "metricas_linhas": "Consultando as linhas...",
    "rede_em_volta": "Consultando as paradas ligadas...",
    "consulta_cypher": "Rodando uma consulta no grafo...",
}


def disponivel() -> bool:
    from webapp.rag import llm
    return llm.chave_configurada()


def modelos() -> list[tuple[str, str]]:
    """(id do provedor, nome do modelo) dos provedores com chave, o padrão primeiro."""
    from webapp.rag import llm
    return [(p.id, p.nome) for p in llm.disponiveis()]


def nome_provedor(pid: str | None) -> str:
    from webapp.rag import llm
    p = llm.PROVEDORES.get(pid or "")
    return p.nome if p else (pid or "")


def responder(pergunta: str, contexto: dict | None = None, historico: list[dict] | None = None,
              ao_chamar=None, provedor: str | None = None, ao_trocar=None) -> dict:
    """`ao_chamar(rotulo)` recebe o texto do status; `ao_trocar(rotulo)` avisa quando o fallback entra."""
    from webapp.rag import agent, prompts, tools
    from webapp.rag.llm import ErroLLM

    try:
        res = agent.responder(
            pergunta,
            system_prompt=prompts.SYSTEM_PROMPT,
            ferramentas=tools,
            historico=historico,
            contexto=contexto,
            provedor=provedor,
            ao_chamar=(lambda nome, args: ao_chamar(ROTULOS_FERRAMENTA.get(nome, "Consultando os dados..."))) if ao_chamar else None,
            ao_trocar=(lambda de, para, motivo: ao_trocar(
                f"{nome_provedor(de)} indisponível; tentando com {nome_provedor(para)}...")) if ao_trocar else None,
        )
    except ErroLLM as e:
        raise RuntimeError(str(e)) from e
    return res.como_dict()


def custo_estimado(uso: dict, provedor: str | None = None) -> float:
    """US$ estimados, sem desconto de cache (por isso tende a ficar acima do real)."""
    from webapp.rag import llm
    p = llm.PROVEDORES.get(provedor or "") or llm.PROVEDORES["anthropic"]
    entrada = uso.get("entrada", 0) + uso.get("cache_leitura", 0) + uso.get("cache_escrita", 0)
    return (entrada * p.preco_entrada + uso.get("saida", 0) * p.preco_saida) / 1_000_000


def resumo_uso(uso: dict, rodadas: int, duracao_ms: int, provedor: str | None = None) -> str:
    entrada = uso.get("entrada", 0) + uso.get("cache_leitura", 0) + uso.get("cache_escrita", 0)
    modelo = f"{nome_provedor(provedor)} · " if provedor else ""
    return (f"{modelo}{rodadas} rodada(s) · {duracao_ms / 1000:.1f} s · {entrada:,} tokens de entrada "
            f"({uso.get('cache_leitura', 0):,} do cache) · {uso.get('saida', 0):,} de saída · "
            + (f"~US$ {custo_estimado(uso, provedor):.4f}" if custo_estimado(uso, provedor) else "plano gratuito")
            ).replace(",", ".")


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
