"""Camada de modelos: um formato comum para o agente e um adaptador por provedor.

O agente conversa sempre no formato de mensagens da Anthropic (role + blocos
text / tool_use / tool_result). Cada provedor converte esse formato para a
sua API e devolve uma `Resposta` normalizada. Provedores:

    anthropic  Claude (Haiku por padrão)       -> provedor_anthropic.py
    gemini     Google Gemini (Flash por padrão) -> provedor_gemini.py

Os SDKs só são importados na primeira chamada, então o pacote pode ser
testado sem eles. Chaves ausentes não quebram nada: o provedor só não aparece
em `disponiveis()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config


class ErroLLM(Exception):
    """Falha ao falar com o modelo, com mensagem curta e segura para a tela."""


@dataclass
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: dict


@dataclass
class Resposta:
    texto: str
    chamadas: list[ChamadaFerramenta] = field(default_factory=list)
    parou_por: str = ""
    conteudo: list[dict] = field(default_factory=list)  # blocos para reenviar como mensagem do assistente
    uso: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Provedor:
    id: str
    nome: str               # rótulo na tela
    modelo: str
    preco_entrada: float    # US$ por 1M tokens (estimativa)
    preco_saida: float

    def configurado(self) -> bool:
        return bool(config.ANTHROPIC_API_KEY if self.id == "anthropic" else config.GEMINI_API_KEY)


def _nome_modelo(m: str) -> str:
    return m.replace("claude-", "Claude ").replace("gemini-", "Gemini ").replace("-", " ").title().replace(" 5 5", " 5.5").replace(" Lite", "-Lite")


PROVEDORES: dict[str, Provedor] = {
    "anthropic": Provedor("anthropic", _nome_modelo(config.RAG_MODEL), config.RAG_MODEL,
                          config.RAG_PRECO_ENTRADA_MTOK, config.RAG_PRECO_SAIDA_MTOK),
    "gemini": Provedor("gemini", _nome_modelo(config.RAG_MODEL_GEMINI), config.RAG_MODEL_GEMINI,
                       config.RAG_PRECO_GEMINI_ENTRADA_MTOK, config.RAG_PRECO_GEMINI_SAIDA_MTOK),
}


def disponiveis() -> list[Provedor]:
    """Provedores com chave configurada, o padrão primeiro."""
    ps = [p for p in PROVEDORES.values() if p.configurado()]
    return sorted(ps, key=lambda p: p.id != config.RAG_PROVEDOR_PADRAO)


def chave_configurada() -> bool:
    return bool(disponiveis())


def provedor_padrao() -> str | None:
    ps = disponiveis()
    return ps[0].id if ps else None


def alternativo(provedor: str) -> str | None:
    """O outro provedor configurado, para o fallback."""
    for p in disponiveis():
        if p.id != provedor:
            return p.id
    return None


def chamar(
    system: str,
    mensagens: list[dict],
    ferramentas: list[dict] | None = None,
    *,
    provedor: str | None = None,
    permitir_ferramentas: bool = True,
    max_tokens: int = 1200,
) -> Resposta:
    """Uma chamada ao modelo do `provedor` (padrão: o primeiro disponível)."""
    pid = provedor or provedor_padrao()
    if pid is None:
        raise ErroLLM("Nenhuma chave de modelo configurada.")
    p = PROVEDORES.get(pid)
    if p is None or not p.configurado():
        raise ErroLLM(f"O provedor {pid} não está configurado.")
    if pid == "anthropic":
        from . import provedor_anthropic as mod
    else:
        from . import provedor_gemini as mod
    return mod.chamar(system, mensagens, ferramentas or [], modelo=p.modelo,
                      permitir_ferramentas=permitir_ferramentas, max_tokens=max_tokens)
