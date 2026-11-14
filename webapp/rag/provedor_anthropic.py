"""Adaptador Anthropic (Claude). O formato interno do agente já é o desta API."""
from __future__ import annotations

import config

from .llm import ChamadaFerramenta, ErroLLM, Resposta

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=2, timeout=60.0)
    return _client


def _limpar(mensagens: list[dict]) -> list[dict]:
    """Remove chaves privadas (prefixo "_") que outros adaptadores guardam nos blocos."""
    saida = []
    for m in mensagens:
        c = m["content"]
        if isinstance(c, list):
            c = [{k: v for k, v in b.items() if not k.startswith("_")} for b in c]
        saida.append({"role": m["role"], "content": c})
    return saida


def chamar(system, mensagens, ferramentas, *, modelo, permitir_ferramentas, max_tokens) -> Resposta:
    import anthropic

    kwargs = dict(
        model=modelo,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=_limpar(mensagens),
    )
    if ferramentas:
        tools = [dict(f) for f in ferramentas]
        tools[-1]["cache_control"] = {"type": "ephemeral"}  # cacheia prompt + definições
        kwargs["tools"] = tools
        if not permitir_ferramentas:
            kwargs["tool_choice"] = {"type": "none"}

    try:
        r = _get_client().messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise ErroLLM("a chave da Anthropic foi recusada") from e
    except anthropic.RateLimitError as e:
        raise ErroLLM("limite de uso da Anthropic atingido") from e
    except anthropic.APIConnectionError as e:
        raise ErroLLM("sem conexão com a Anthropic") from e
    except anthropic.APIStatusError as e:
        raise ErroLLM(f"a Anthropic devolveu erro {e.status_code}") from e

    texto, chamadas, conteudo = [], [], []
    for b in r.content:
        if b.type == "text":
            texto.append(b.text)
            conteudo.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            args = dict(b.input or {})
            chamadas.append(ChamadaFerramenta(id=b.id, nome=b.name, argumentos=args))
            conteudo.append({"type": "tool_use", "id": b.id, "name": b.name, "input": args})

    u = r.usage
    uso = {
        "entrada": getattr(u, "input_tokens", 0) or 0,
        "saida": getattr(u, "output_tokens", 0) or 0,
        "cache_leitura": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_escrita": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }
    return Resposta(texto="".join(texto).strip(), chamadas=chamadas, parou_por=r.stop_reason or "",
                    conteudo=conteudo, uso=uso)
