"""Ponto de encaixe do assistente (RAG).

A página `views/assistente.py` chama `responder(pergunta, contexto)`. A busca
nos dados e a chamada ao modelo de linguagem entram na Frente 3 do plano; até
lá, `disponivel()` devolve False e a página mostra um aviso no lugar da
resposta.

Contrato esperado da implementação:
    responder(pergunta: str, contexto: dict | None) -> dict com
        "texto":  resposta em Markdown, com marcadores [1], [2] citando fontes
        "fontes": lista de {"id": "1", "titulo": "...", "detalhe": "..."}
"""
from __future__ import annotations


def disponivel() -> bool:
    return False


def responder(pergunta: str, contexto: dict | None = None) -> dict:
    raise NotImplementedError("O assistente (RAG) ainda não foi implementado.")


SUGESTOES_COM_PARADA = [
    "Por que esta parada tem esse índice de risco?",
    "Quais paradas vizinhas têm índice parecido?",
    "Quais linhas passam por esta parada?",
]

SUGESTOES_GERAIS = [
    "Quais regiões concentram as paradas de nível alto?",
    "O que mais pesa no modelo de tiroteio?",
    "Quais são os limites destes dados?",
]
