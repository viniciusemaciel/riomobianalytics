"""Validação dos visuais que o assistente pede (Fase 4). Não depende do Streamlit.

O modelo não desenha nada: ele chama `mostrar_grafico`, `mostrar_tabela` ou
`mostrar_mapa` com uma especificação. Este módulo confere e normaliza essa
especificação; `webapp/rag/render.py` a desenha na página.

Regras de segurança:
  - gráfico e tabela trazem os valores que o modelo copiou de um resultado de
    ferramenta e precisam de `fonte_id` desse resultado (o agente confere que o
    id existe na conversa); sem isso o visual é recusado;
  - o mapa não recebe coordenadas do modelo: recebe stop_ids e a posição e o
    índice são lidos do banco (ver `tools.mostrar_mapa`);
  - tamanhos limitados para não pesar na página nem no histórico da sessão.

Especificações devolvidas (dicts serializáveis, guardadas no histórico do chat):
  {"tipo": "grafico", "formato": "barra"|"barra_horizontal"|"linha", "titulo", "rotulos": [str],
   "series": [{"nome", "valores": [float|None]}], "eixo_y", "fonte_id"}
  {"tipo": "tabela", "titulo", "colunas": [str], "linhas": [[str|float|None]], "fonte_id"}
  {"tipo": "mapa", "titulo", "pontos": [{"stop_id", "nome", "lat", "lon", "indice", "nivel"}], "destaque"}
"""
from __future__ import annotations

import math
import re

MAX_ROTULOS = 50
MAX_SERIES = 4
MAX_COLUNAS = 8
MAX_LINHAS_TABELA = 50
MAX_PONTOS_MAPA = 50
MAX_TEXTO = 80
MAX_VISUAIS_POR_RESPOSTA = 3
FORMATOS = ("barra", "barra_horizontal", "linha")

_NUM = re.compile(r"^-?\d+(?:[.,]\d+)?$")


class VisualInvalido(ValueError):
    """Volta ao modelo como erro de ferramenta, com o motivo."""


def _texto(v, campo: str, obrigatorio: bool = True) -> str:
    s = "" if v is None else str(v).strip()
    if obrigatorio and not s:
        raise VisualInvalido(f"'{campo}' está vazio")
    return s[:MAX_TEXTO]


def _lista(v, campo: str, maximo: int) -> list:
    if not isinstance(v, list) or not v:
        raise VisualInvalido(f"'{campo}' deve ser uma lista não vazia")
    if len(v) > maximo:
        raise VisualInvalido(f"'{campo}' tem {len(v)} itens; o máximo é {maximo}")
    return v


def _numero(v, campo: str):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise VisualInvalido(f"'{campo}' tem valor não numérico: {v!r}")
    if isinstance(v, str):
        s = v.strip().replace(" ", "")
        if not _NUM.match(s):
            raise VisualInvalido(f"'{campo}' tem valor não numérico: {v!r}")
        v = s.replace(",", ".")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise VisualInvalido(f"'{campo}' tem valor não numérico: {v!r}") from None
    if not math.isfinite(x):
        raise VisualInvalido(f"'{campo}' tem valor infinito ou NaN")
    return x


def _celula(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    s = str(v).strip()
    if _NUM.match(s.replace(" ", "")):
        return float(s.replace(" ", "").replace(",", "."))
    return s[:MAX_TEXTO]


def _fonte_id(v) -> str:
    s = "" if v is None else str(v).strip().strip("[]")
    if not s:
        raise VisualInvalido("falta 'fonte_id': use o fonte_id do resultado de ferramenta de onde os valores saíram")
    return s


def grafico(formato=None, titulo=None, rotulos=None, series=None, eixo_y=None, fonte_id=None) -> dict:
    formato = (formato or "barra").strip()
    if formato not in FORMATOS:
        raise VisualInvalido(f"formato '{formato}' inválido; use um de {', '.join(FORMATOS)}")
    rot = [_texto(r, "rotulos") for r in _lista(rotulos, "rotulos", MAX_ROTULOS)]
    sers = []
    for i, s in enumerate(_lista(series, "series", MAX_SERIES)):
        if not isinstance(s, dict):
            raise VisualInvalido("cada série deve ser um objeto com 'nome' e 'valores'")
        vals = _lista(s.get("valores"), f"series[{i}].valores", MAX_ROTULOS)
        if len(vals) != len(rot):
            raise VisualInvalido(f"series[{i}] tem {len(vals)} valores para {len(rot)} rótulos; precisam ser iguais")
        nums = [_numero(v, f"series[{i}].valores") for v in vals]
        if all(n is None for n in nums):
            raise VisualInvalido(f"series[{i}] não tem nenhum valor")
        sers.append({"nome": _texto(s.get("nome"), "nome", obrigatorio=False) or f"Série {i + 1}", "valores": nums})
    return {"tipo": "grafico", "formato": formato, "titulo": _texto(titulo, "titulo"), "rotulos": rot,
            "series": sers, "eixo_y": _texto(eixo_y, "eixo_y", obrigatorio=False), "fonte_id": _fonte_id(fonte_id)}


def tabela(titulo=None, colunas=None, linhas=None, fonte_id=None) -> dict:
    cols = [_texto(c, "colunas") for c in _lista(colunas, "colunas", MAX_COLUNAS)]
    if len(set(cols)) != len(cols):
        raise VisualInvalido("'colunas' tem nomes repetidos")
    rows = []
    for i, linha in enumerate(_lista(linhas, "linhas", MAX_LINHAS_TABELA)):
        if not isinstance(linha, list) or len(linha) != len(cols):
            raise VisualInvalido(f"linhas[{i}] deve ser uma lista com {len(cols)} valores, um por coluna")
        rows.append([_celula(v) for v in linha])
    return {"tipo": "tabela", "titulo": _texto(titulo, "titulo"), "colunas": cols, "linhas": rows,
            "fonte_id": _fonte_id(fonte_id)}


def ids_do_mapa(stop_ids, destaque=None) -> tuple[list[str], str | None]:
    """Confere a lista de paradas pedida para o mapa (sem duplicatas, na ordem dada)."""
    ids, vistos = [], set()
    for v in _lista(stop_ids, "stop_ids", MAX_PONTOS_MAPA):
        s = str(v or "").strip()
        if s and s not in vistos:
            vistos.add(s)
            ids.append(s)
    if not ids:
        raise VisualInvalido("'stop_ids' não tem nenhum id")
    d = str(destaque).strip() if destaque else None
    if d and d not in vistos:
        ids.insert(0, d)
        ids = ids[:MAX_PONTOS_MAPA]
    return ids, d or None


def mapa(titulo, pontos: list[dict], destaque: str | None = None) -> dict:
    return {"tipo": "mapa", "titulo": _texto(titulo, "titulo"), "pontos": pontos, "destaque": destaque}
