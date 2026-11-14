#!/usr/bin/env python3
"""Gera o índice de vetores da documentação do assistente (docs/rag -> artifacts/rag_index).

Cada seção `##` dos arquivos de docs/rag vira um chunk; o texto embutido leva o
título do arquivo e o da seção na frente. Os vetores vêm do Gemini
(config.RAG_MODEL_EMBEDDING, RAG_EMBED_DIM dimensões, tarefa RETRIEVAL_DOCUMENT).

O índice é versionado no git: o app só lê `vetores.npy` e `chunks.json`. Rode de
novo quando editar algum arquivo de docs/rag, e commite `artifacts/rag_index/`.
Só os chunks cujo texto mudou são reenviados ao Gemini (o resto reaproveita o
vetor do índice atual, se modelo e dimensão forem os mesmos).

Uso (da raiz do repo):
  python scripts/11_indexar_rag.py              mostra o plano (chunks novos/alterados) e não grava nada
  python scripts/11_indexar_rag.py --gravar     gera/atualiza o índice
  python scripts/11_indexar_rag.py --gravar --tudo    reembute todos os chunks
  python scripts/11_indexar_rag.py --testar "como o índice é calculado?"
                                                mostra os 5 trechos mais próximos e as similaridades
                                                (sem limiar; serve para calibrar RAG_LIMIAR_SIMILARIDADE)
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from webapp.rag import conhecimento as kb  # noqa: E402


def _indice_atual():
    try:
        ind = kb.carregar_indice(recarregar=True)
    except (FileNotFoundError, ValueError):
        return None
    if ind.modelo != config.RAG_MODEL_EMBEDDING or ind.dimensao != config.RAG_EMBED_DIM:
        print(f"Índice atual usa {ind.modelo}/{ind.dimensao}; a configuração pede "
              f"{config.RAG_MODEL_EMBEDDING}/{config.RAG_EMBED_DIM}. Vai reembutir tudo.")
        return None
    return ind


def indexar(gravar: bool, tudo: bool) -> int:
    chunks = kb.montar_chunks()
    if not chunks:
        print(f"Nenhum chunk em {kb.DOCS_DIR}.")
        return 1
    avisos = kb.avisos_de_tamanho(chunks)
    arquivos = len({c["arquivo"] for c in chunks})
    print(f"{len(chunks)} chunks em {arquivos} arquivos de {kb.DOCS_DIR.name}/")
    for a in avisos:
        print(f"  aviso: {a}")

    atual = None if tudo else _indice_atual()
    reaproveitaveis = {}
    if atual is not None:
        reaproveitaveis = {c["hash"]: atual.vetores[i] for i, c in enumerate(atual.chunks)}
    pendentes = [i for i, c in enumerate(chunks) if c["hash"] not in reaproveitaveis]
    print(f"{len(chunks) - len(pendentes)} chunks reaproveitados, {len(pendentes)} para embutir.")
    removidos = 0 if atual is None else len({c["hash"] for c in atual.chunks} - {c["hash"] for c in chunks})
    if removidos:
        print(f"{removidos} chunk(s) do índice atual saem (texto mudou ou seção removida).")

    if not gravar:
        print("\nNada foi gravado. Use --gravar para gerar o índice.")
        return 0

    vetores = np.zeros((len(chunks), config.RAG_EMBED_DIM), dtype=np.float32)
    for i, c in enumerate(chunks):
        if c["hash"] in reaproveitaveis:
            vetores[i] = reaproveitaveis[c["hash"]]
    if pendentes:
        novos = kb.embutir_gemini([chunks[i]["texto_embutido"] for i in pendentes], kb.TAREFA_DOCUMENTO)
        if novos.shape[1] != config.RAG_EMBED_DIM:
            print(f"O modelo devolveu {novos.shape[1]} dimensões; esperado {config.RAG_EMBED_DIM}.")
            return 1
        vetores[pendentes] = novos
    kb.gravar_indice(chunks, vetores)
    print(f"Índice gravado em {kb.INDICE_DIR.relative_to(config.BASE_DIR)}/ "
          f"({vetores.shape[0]} x {vetores.shape[1]}, {vetores.nbytes / 1024:.0f} KB). "
          "Commite essa pasta para o app usar.")
    return 0


def testar(pergunta: str) -> int:
    try:
        ind = kb.carregar_indice(recarregar=True)
    except FileNotFoundError:
        print("Ainda não há índice. Rode primeiro:  python scripts/11_indexar_rag.py --gravar")
        return 1
    achados = kb.buscar(pergunta, k=5, limiar=-1.0, indice=ind)
    print(f'Pergunta: "{pergunta}"   (limiar atual: {config.RAG_LIMIAR_SIMILARIDADE}, trechos por busca: {config.RAG_BUSCA_TOP_K})\n')
    for a in achados:
        marca = "passa " if a["similaridade"] >= config.RAG_LIMIAR_SIMILARIDADE else "abaixo"
        print(f"  {a['similaridade']:.3f} {marca}  [{a['tipo']}] {a['titulo']} > {a['secao']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gravar", action="store_true", help="gera/atualiza o índice (sem isso, só mostra o plano)")
    ap.add_argument("--tudo", action="store_true", help="reembute todos os chunks, ignorando o índice atual")
    ap.add_argument("--testar", metavar="PERGUNTA", help="mostra os 5 trechos mais próximos da pergunta")
    args = ap.parse_args()
    sys.exit(testar(args.testar) if args.testar else indexar(args.gravar, args.tudo))
