"""Confere, com o índice real, que cada pergunta de exemplo do catálogo encontra a documentação certa.

Precisa da GEMINI_API_KEY (embute as perguntas) e de artifacts/rag_index. Não chama o modelo de chat.
Rode da raiz:  python tests/check_catalogo.py

Para cada pergunta de documentação: a busca (top-k e limiar do config) tem de trazer pelo menos um
dos arquivos esperados. Perguntas de dados ao vivo (sem `docs`) são puladas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.rag import catalogo, conhecimento  # noqa: E402


def main():
    falhas = 0
    for t in catalogo.TEMAS:
        for p in t.perguntas:
            if not p.docs:
                continue
            achados = conhecimento.buscar(p.texto)
            ids = [a["id"].split("#")[0] for a in achados]
            ok = any(i in p.docs for i in ids)
            falhas += not ok
            sims = ", ".join(f"{a['id']} {a['similaridade']:.3f}" for a in achados) or "nada acima do limiar"
            print(f"{'ok   ' if ok else 'FALHA'} [{t.nome}] {p.texto}\n       {sims}")
    print("\nTodas as perguntas encontram a documentação." if not falhas else f"\n{falhas} pergunta(s) sem o trecho esperado.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
