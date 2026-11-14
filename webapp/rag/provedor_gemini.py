"""Adaptador Google Gemini (SDK google-genai).

Converte o formato interno (mensagens no estilo Anthropic) para `contents` do
Gemini, e a resposta de volta:

  texto                  -> Part(text=...)
  tool_use               -> Part(function_call=FunctionCall(id, name, args))
  tool_result            -> Part(function_response=FunctionResponse(id, name, response))
  papel "assistant"      -> role "model"

Os modelos Gemini 3 devolvem uma `thought_signature` junto de cada chamada de
função e exigem recebê-la de volta na rodada seguinte. Ela fica guardada no
bloco tool_use, na chave privada "_gemini_sig" (o adaptador Anthropic remove
chaves com "_").
"""
from __future__ import annotations

import json
import uuid

import config

from .llm import ChamadaFerramenta, ErroLLM, Resposta

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _declaracoes(ferramentas: list[dict]):
    from google.genai import types

    decl = []
    for f in ferramentas:
        schema = f.get("input_schema") or {}
        kw = {"name": f["name"], "description": f.get("description", "")}
        if schema.get("properties"):  # ferramentas sem parâmetros vão sem schema
            kw["parameters_json_schema"] = schema
        decl.append(types.FunctionDeclaration(**kw))
    return [types.Tool(function_declarations=decl)]


def _contents(mensagens: list[dict]):
    from google.genai import types

    nomes = {}  # tool_use id -> nome da função (FunctionResponse exige o nome)
    contents = []
    for m in mensagens:
        papel = "model" if m["role"] == "assistant" else "user"
        blocos = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        parts = []
        for b in blocos:
            t = b.get("type")
            if t == "text" and b.get("text"):
                parts.append(types.Part(text=b["text"]))
            elif t == "tool_use":
                nomes[b["id"]] = b["name"]
                parte = types.Part(function_call=types.FunctionCall(id=b["id"], name=b["name"], args=b.get("input") or {}))
                if b.get("_gemini_sig"):
                    parte.thought_signature = b["_gemini_sig"]
                parts.append(parte)
            elif t == "tool_result":
                bruto = b.get("content")
                try:
                    valor = json.loads(bruto) if isinstance(bruto, str) else bruto
                except (TypeError, ValueError):
                    valor = bruto
                chave = "error" if b.get("is_error") else "result"
                parts.append(types.Part(function_response=types.FunctionResponse(
                    id=b["tool_use_id"], name=nomes.get(b["tool_use_id"], "ferramenta"), response={chave: valor})))
        if parts:
            contents.append(types.Content(role=papel, parts=parts))
    return contents


def _erro(e) -> ErroLLM:
    code = getattr(e, "code", None)
    if code in (401, 403):
        return ErroLLM("a chave do Gemini foi recusada")
    if code == 429:
        return ErroLLM("cota do Gemini esgotada (no plano gratuito, a cota diária volta à meia-noite do Pacífico)")
    if code:
        return ErroLLM(f"o Gemini devolveu erro {code}")
    return ErroLLM("sem conexão com o Gemini")


def chamar(system, mensagens, ferramentas, *, modelo, permitir_ferramentas, max_tokens) -> Resposta:
    from google.genai import errors, types

    cfg = dict(
        system_instruction=system,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),  # menos latência
    )
    if ferramentas:
        cfg["tools"] = _declaracoes(ferramentas)
        # O agente executa as ferramentas; o SDK não deve chamá-las sozinho.
        cfg["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        modo = types.FunctionCallingConfigMode.AUTO if permitir_ferramentas else types.FunctionCallingConfigMode.NONE
        cfg["tool_config"] = types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode=modo))

    try:
        r = _get_client().models.generate_content(
            model=modelo, contents=_contents(mensagens), config=types.GenerateContentConfig(**cfg))
    except errors.APIError as e:
        raise _erro(e) from e
    except Exception as e:  # rede, timeout
        raise ErroLLM("sem conexão com o Gemini") from e

    cand = (r.candidates or [None])[0]
    parts = (cand.content.parts if cand is not None and cand.content else None) or []
    texto, chamadas, conteudo = [], [], []
    for parte in parts:
        if parte.function_call:
            fc = parte.function_call
            cid = fc.id or f"gem_{uuid.uuid4().hex[:12]}"
            args = dict(fc.args or {})
            chamadas.append(ChamadaFerramenta(id=cid, nome=fc.name, argumentos=args))
            bloco = {"type": "tool_use", "id": cid, "name": fc.name, "input": args}
            if parte.thought_signature:
                bloco["_gemini_sig"] = parte.thought_signature
            conteudo.append(bloco)
        elif parte.text and not parte.thought:
            texto.append(parte.text)
            conteudo.append({"type": "text", "text": parte.text})

    if not parts and not chamadas:
        motivo = getattr(cand, "finish_reason", None) if cand is not None else None
        raise ErroLLM(f"o Gemini não devolveu resposta ({motivo or 'vazia'})")

    u = r.usage_metadata
    cache = (getattr(u, "cached_content_token_count", 0) or 0) if u else 0
    uso = {
        "entrada": max(0, ((getattr(u, "prompt_token_count", 0) or 0) if u else 0) - cache),
        "saida": ((getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0,
        "cache_leitura": cache,
        "cache_escrita": 0,
    }
    parou = str(getattr(cand, "finish_reason", "") or "") if cand is not None else ""
    return Resposta(texto="".join(texto).strip(), chamadas=chamadas,
                    parou_por="tool_use" if chamadas else parou, conteudo=conteudo, uso=uso)
