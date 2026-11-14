"""Base de conhecimento do assistente: chunking, índice de vetores e busca.

Os textos ficam em `docs/rag/*.md`. Cada seção `##` vira um chunk, e o texto que
vai para o embedding leva na frente o título do arquivo e o da seção
("Título > Seção"), no lugar de sobreposição entre chunks. Arquivos que começam
com `_` e o README não são indexados.

O índice é gerado offline por `scripts/11_indexar_rag.py` e versionado em
`artifacts/rag_index/`:
    vetores.npy   float32, uma linha por chunk, já normalizada (norma 1)
    chunks.json   {"modelo", "dimensao", "chunks": [...]} na mesma ordem dos vetores

Em tempo de execução o app só lê esses arquivos. A única chamada ao Gemini é a
da pergunta (`RETRIEVAL_QUERY`), uma por busca. Como os vetores têm norma 1, o
cosseno é um produto escalar em numpy.

Este módulo não depende do Streamlit nem de banco. O SDK do Gemini só é
importado na primeira chamada de embedding, então o resto roda sem ele.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

import config

DOCS_DIR = config.BASE_DIR / "docs" / "rag"
INDICE_DIR = config.ARTIFACTS_DIR / "rag_index"
ARQ_VETORES = "vetores.npy"
ARQ_CHUNKS = "chunks.json"

PALAVRAS_MIN, PALAVRAS_MAX = 40, 400   # tamanho combinado para as seções de docs/rag

TAREFA_DOCUMENTO = "RETRIEVAL_DOCUMENT"
TAREFA_PERGUNTA = "RETRIEVAL_QUERY"


# ---------------------------------------------------------------- chunking
_RE_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def _front_matter(texto: str) -> tuple[dict, str]:
    """Lê o cabeçalho `chave: valor` (sem YAML; `[a, b]` vira lista) e devolve (meta, corpo)."""
    m = _RE_FRONT_MATTER.match(texto)
    if not m:
        return {}, texto
    meta: dict = {}
    for linha in m.group(1).splitlines():
        if ":" not in linha:
            continue
        chave, valor = linha.split(":", 1)
        valor = valor.strip()
        if valor.startswith("[") and valor.endswith("]"):
            meta[chave.strip()] = [t.strip() for t in valor[1:-1].split(",") if t.strip()]
        else:
            meta[chave.strip()] = valor
    return meta, texto[m.end():]


def _secoes(corpo: str) -> list[tuple[str, str]]:
    """Divide em seções `## Título` (ignora `##` dentro de bloco de código e o que vem antes da primeira)."""
    secoes: list[tuple[str, str]] = []
    titulo, linhas, em_codigo = None, [], False
    for linha in corpo.splitlines():
        if linha.lstrip().startswith("```"):
            em_codigo = not em_codigo
        if not em_codigo and linha.startswith("## "):
            if titulo is not None:
                secoes.append((titulo, "\n".join(linhas).strip()))
            titulo, linhas = linha[3:].strip(), []
        elif titulo is not None:
            linhas.append(linha)
    if titulo is not None:
        secoes.append((titulo, "\n".join(linhas).strip()))
    return [(t, c) for t, c in secoes if c]


def _indexavel(caminho: Path) -> bool:
    return caminho.suffix == ".md" and not caminho.name.startswith("_") and caminho.name.lower() != "readme.md"


def montar_chunks(docs_dir: Path | str = DOCS_DIR) -> list[dict]:
    """Um dict por seção `##` de cada arquivo indexável, em ordem de arquivo e de seção."""
    chunks: list[dict] = []
    for caminho in sorted(Path(docs_dir).glob("*.md")):
        if not _indexavel(caminho):
            continue
        meta, corpo = _front_matter(caminho.read_text(encoding="utf-8"))
        doc_id = meta.get("id") or caminho.stem
        titulo = meta.get("titulo") or doc_id
        for i, (secao, texto) in enumerate(_secoes(corpo), 1):
            embutido = f"{titulo} > {secao}\n\n{texto}"
            chunks.append({
                "id": f"{doc_id}#{i:02d}",
                "arquivo": caminho.name,
                "titulo": titulo,
                "secao": secao,
                "tipo": meta.get("tipo", "interno"),
                "origem": meta.get("origem", ""),
                "url": meta.get("url", ""),
                "periodo_coberto": meta.get("periodo_coberto", ""),
                "acessado_em": meta.get("acessado_em", ""),
                "palavras": len(texto.split()),
                "texto": texto,
                "texto_embutido": embutido,
                "hash": hashlib.sha256(embutido.encode("utf-8")).hexdigest()[:16],
            })
    return chunks


def avisos_de_tamanho(chunks: list[dict]) -> list[str]:
    return [f"{c['id']} ({c['secao']}): {c['palavras']} palavras, fora de {PALAVRAS_MIN} a {PALAVRAS_MAX}"
            for c in chunks if not PALAVRAS_MIN <= c["palavras"] <= PALAVRAS_MAX]


# -------------------------------------------------------------- embeddings
def _normalizar(m: np.ndarray) -> np.ndarray:
    normas = np.linalg.norm(m, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return (m / normas).astype(np.float32)


def _erro_passageiro(e: Exception) -> bool:
    """Limite de requisições, indisponibilidade e queda de conexão valem nova tentativa; chave ou modelo errados não."""
    msg = str(e)
    if any(s in msg for s in ("429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE")):
        return True
    if any(s in msg.lower() for s in ("disconnected", "timed out", "timeout", "connection reset", "connection error")):
        return True
    return any(s in type(e).__name__ for s in ("Protocol", "Connect", "Timeout", "ReadError"))


def _espera_pedida(e: Exception) -> float | None:
    """Segundos que o Gemini pede para esperar ('Please retry in 44.1s'), se o erro disser."""
    m = re.search(r"retry in ([\d.]+)\s*s", str(e), re.I) or re.search(r"retryDelay'?\"?:\s*'?\"?(\d+)s", str(e))
    return float(m.group(1)) if m else None


def embutir_gemini(textos: list[str], tarefa: str, *, lote: int = 10) -> np.ndarray:
    """Embeddings do Gemini, normalizados (float32, uma linha por texto).

    `tarefa`: TAREFA_DOCUMENTO para os chunks, TAREFA_PERGUNTA para a pergunta.
    Envia em lotes pequenos. O plano gratuito conta cada texto como uma requisição
    (100 por minuto), então entre lotes espera o bastante para ficar em ~80 por minuto
    e, num erro passageiro (limite, indisponibilidade, queda de conexão), espera o tempo
    que o Gemini pedir e tenta de novo, até 6 vezes.
    """
    if not config.GEMINI_API_KEY:
        raise ValueError("falta GEMINI_API_KEY para gerar embeddings")
    from google.genai import types

    from .provedor_gemini import _get_client

    cliente = _get_client()
    cfg = types.EmbedContentConfig(task_type=tarefa, output_dimensionality=config.RAG_EMBED_DIM)
    vetores: list[list[float]] = []
    for ini in range(0, len(textos), lote):
        parte = textos[ini:ini + lote]
        t0 = time.time()
        for tentativa in range(6):
            try:
                r = cliente.models.embed_content(model=config.RAG_MODEL_EMBEDDING, contents=parte, config=cfg)
                break
            except Exception as e:
                if tentativa == 5 or not _erro_passageiro(e):
                    raise
                espera = _espera_pedida(e)
                time.sleep(espera + 2 if espera else 2 * 2 ** tentativa)
        vetores.extend(list(x.values) for x in r.embeddings)
        if ini + lote < len(textos):  # só entre lotes; uma pergunta isolada não espera
            time.sleep(max(0.0, len(parte) / 80 * 60 - (time.time() - t0)))
        if len(textos) > lote:
            print(f"  {min(ini + lote, len(textos))}/{len(textos)} embutidos", flush=True)
    return _normalizar(np.asarray(vetores, dtype=np.float32))


# ------------------------------------------------------------------ índice
@dataclass
class Indice:
    vetores: np.ndarray       # (n_chunks, dimensao), norma 1
    chunks: list[dict]
    modelo: str
    dimensao: int


def gravar_indice(chunks: list[dict], vetores: np.ndarray, pasta: Path | str = INDICE_DIR) -> None:
    if len(chunks) != len(vetores):
        raise ValueError(f"{len(chunks)} chunks para {len(vetores)} vetores")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    np.save(pasta / ARQ_VETORES, vetores.astype(np.float32))
    guardados = [{k: v for k, v in c.items() if k != "texto_embutido"} for c in chunks]
    meta = {"modelo": config.RAG_MODEL_EMBEDDING, "dimensao": int(vetores.shape[1]), "chunks": guardados}
    (pasta / ARQ_CHUNKS).write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _ler_indice(pasta: Path) -> Indice:
    arq_chunks, arq_vetores = pasta / ARQ_CHUNKS, pasta / ARQ_VETORES
    if not arq_chunks.exists() or not arq_vetores.exists():
        raise FileNotFoundError(f"índice da documentação não encontrado em {pasta} (rode scripts/11_indexar_rag.py)")
    meta = json.loads(arq_chunks.read_text(encoding="utf-8"))
    vetores = np.load(arq_vetores)
    if len(meta["chunks"]) != len(vetores):
        raise ValueError("índice corrompido: número de chunks diferente do de vetores (rode scripts/11_indexar_rag.py)")
    return Indice(vetores, meta["chunks"], meta.get("modelo", ""), int(meta.get("dimensao", vetores.shape[1])))


@lru_cache(maxsize=4)
def _carregar_cache(pasta: str) -> Indice:
    return _ler_indice(Path(pasta))


def carregar_indice(pasta: Path | str = INDICE_DIR, *, recarregar: bool = False) -> Indice:
    if recarregar:
        _carregar_cache.cache_clear()
    return _carregar_cache(str(pasta))


# ------------------------------------------------------------------- busca
def buscar(pergunta: str, *, k: int | None = None, limiar: float | None = None, excluir=(),
           indice: Indice | None = None, embutidor=None) -> list[dict]:
    """Trechos mais parecidos com a pergunta, do mais ao menos similar.

    `k`: máximo de trechos (padrão config.RAG_BUSCA_TOP_K). `limiar`: cosseno mínimo
    (padrão config.RAG_LIMIAR_SIMILARIDADE); abaixo dele nada volta. `excluir`: ids de
    chunk a pular (aplicado antes do top-k, então o próximo da fila entra no lugar).
    `embutidor(textos, tarefa)` é trocável em testes. Cada trecho traz `similaridade`.
    """
    pergunta = (pergunta or "").strip()
    if not pergunta:
        raise ValueError("a pergunta da busca está vazia")
    k = config.RAG_BUSCA_TOP_K if k is None else k
    limiar = config.RAG_LIMIAR_SIMILARIDADE if limiar is None else limiar
    indice = indice or carregar_indice()
    q = (embutidor or embutir_gemini)([pergunta], TAREFA_PERGUNTA)
    if q.shape[1] != indice.vetores.shape[1]:
        raise ValueError(f"a pergunta tem {q.shape[1]} dimensões e o índice {indice.vetores.shape[1]}: "
                         "gere o índice de novo com o mesmo modelo (scripts/11_indexar_rag.py)")
    scores = indice.vetores @ q[0]
    achados: list[dict] = []
    for i in np.argsort(-scores):
        chunk = indice.chunks[i]
        if chunk["id"] in excluir:
            continue
        if scores[i] < limiar:
            break
        achados.append({**chunk, "similaridade": round(float(scores[i]), 3)})
        if len(achados) >= k:
            break
    return achados
