"""Cliente do modelo de linguagem (Anthropic).

Uma única função, `chamar`, devolve a resposta já normalizada para o agente,
sem expor tipos do SDK. O SDK é importado só na primeira chamada, então o
resto do pacote pode ser testado sem a dependência instalada.

Prompt caching: o prompt de sistema e a última definição de ferramenta levam
`cache_control`, então as rodadas seguintes da mesma pergunta (e perguntas
seguidas) reaproveitam esse prefixo.
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


_client = None


def chave_configurada() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def _get_client():
    global _client
    if _client is None:
        if not chave_configurada():
            raise ErroLLM("ANTHROPIC_API_KEY não configurada.")
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=2, timeout=60.0)
    return _client


def _com_cache(ferramentas: list[dict]) -> list[dict]:
    if not ferramentas:
        return []
    copia = [dict(f) for f in ferramentas]
    copia[-1]["cache_control"] = {"type": "ephemeral"}
    return copia


def chamar(
    system: str,
    mensagens: list[dict],
    ferramentas: list[dict] | None = None,
    *,
    permitir_ferramentas: bool = True,
    max_tokens: int = 1200,
    modelo: str | None = None,
) -> Resposta:
    """Uma chamada ao modelo. `mensagens` segue o formato da API (role + content)."""
    import anthropic

    client = _get_client()
    kwargs = dict(
        model=modelo or config.RAG_MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=mensagens,
    )
    if ferramentas:
        kwargs["tools"] = _com_cache(ferramentas)
        if not permitir_ferramentas:
            # Mantém as definições (a API exige quando há tool_use no histórico), mas proíbe novas chamadas.
            kwargs["tool_choice"] = {"type": "none"}

    try:
        r = client.messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise ErroLLM("A chave da API foi recusada.") from e
    except anthropic.RateLimitError as e:
        raise ErroLLM("Limite de uso da API atingido. Tente de novo em instantes.") from e
    except anthropic.APIConnectionError as e:
        raise ErroLLM("Sem conexão com a API do modelo.") from e
    except anthropic.APIStatusError as e:
        raise ErroLLM(f"A API do modelo devolveu erro {e.status_code}.") from e

    texto, chamadas, conteudo = [], [], []
    for b in r.content:
        if b.type == "text":
            texto.append(b.text)
            conteudo.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            chamadas.append(ChamadaFerramenta(id=b.id, nome=b.name, argumentos=dict(b.input or {})))
            conteudo.append({"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input or {})})

    u = r.usage
    uso = {
        "entrada": getattr(u, "input_tokens", 0) or 0,
        "saida": getattr(u, "output_tokens", 0) or 0,
        "cache_leitura": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_escrita": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }
    return Resposta(texto="".join(texto).strip(), chamadas=chamadas, parou_por=r.stop_reason or "",
                    conteudo=conteudo, uso=uso)
