"""Testes da busca na documentação (sem chave, sem rede, sem banco).

Cobrem: chunking dos arquivos reais de docs/rag, gravação e leitura do índice,
ranking por cosseno, limiar, exclusão de chunks e a ferramenta buscar_conhecimento.
Os embeddings são trocados por um embutidor falso (palavras em "saco" com hash).

Rode da raiz:  python tests/test_conhecimento.py      (ou: pytest tests/)
"""
import contextlib
import hashlib
import re
import sys
import tempfile
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# a ferramenta importa módulos que puxam streamlit/neo4j: troca por vazios, como em test_consulta_cypher.py
_db = types.ModuleType("webapp.utils.db_connections")
_db.query_neo4j = lambda *a, **k: []
_db.somente_leitura = contextlib.nullcontext
sys.modules["webapp.utils.db_connections"] = _db
for _nome in ("webapp.utils.data_fetchers", "webapp.utils.insights"):
    sys.modules[_nome] = types.ModuleType(_nome)

from webapp.rag import conhecimento as kb  # noqa: E402
from webapp.rag import tools  # noqa: E402

DIM = 64


def embutidor_falso(textos, tarefa):
    """Cada palavra soma 1 numa posição fixa (hash); depois normaliza. Texto parecido = cosseno alto."""
    m = np.zeros((len(textos), DIM), dtype=np.float32)
    for i, t in enumerate(textos):
        for palavra in re.findall(r"\w+", t.lower()):
            m[i, int(hashlib.md5(palavra.encode()).hexdigest(), 16) % DIM] += 1
    return kb._normalizar(m)


def _chunk(i, titulo, secao, texto, tipo="interno"):
    return {"id": f"doc{i}#01", "arquivo": f"doc{i}.md", "titulo": titulo, "secao": secao, "tipo": tipo,
            "origem": "origem teste", "url": "", "periodo_coberto": "", "acessado_em": "", "palavras": 50,
            "texto": texto, "texto_embutido": f"{titulo} > {secao}\n\n{texto}", "hash": f"h{i}"}


CHUNKS = [
    _chunk(1, "Metodologia", "Como o índice de risco é calculado",
           "O índice combina reclamações do 1746 e a previsão de tiroteio a 500 metros da parada, normalizado de 0 a 100."),
    _chunk(2, "Modelo", "Qualidade do modelo XGBoost",
           "O modelo XGBoost foi validado em 2024 com AUC de 0,71 e usa dezesseis variáveis."),
    _chunk(3, "Linha do tempo", "Operação Contenção em 2025",
           "Segundo relatórios públicos, a Operação Contenção ocorreu em outubro de 2025 no Rio.", tipo="externo"),
]


def _indice():
    return kb.Indice(embutidor_falso([c["texto_embutido"] for c in CHUNKS], kb.TAREFA_DOCUMENTO),
                     [dict(c) for c in CHUNKS], "falso", DIM)


# ------------------------------------------------------------------ chunking
def test_chunks_dos_arquivos_reais():
    chunks = kb.montar_chunks()
    assert len(chunks) > 50, f"só {len(chunks)} chunks em {kb.DOCS_DIR}"
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids)), "ids de chunk repetidos"
    assert not [c for c in chunks if c["arquivo"].startswith("_") or c["arquivo"].lower() == "readme.md"]
    assert kb.avisos_de_tamanho(chunks) == [], kb.avisos_de_tamanho(chunks)
    externos = [c for c in chunks if c["tipo"] == "externo"]
    assert externos and all(c["acessado_em"] and c["url"] for c in externos), "externo sem url ou acessado_em"
    c = chunks[0]
    assert c["texto_embutido"].startswith(f"{c['titulo']} > {c['secao']}\n\n"), "cabeçalho do chunk ausente"


def test_front_matter_e_secoes():
    meta, corpo = kb._front_matter("---\nid: x\ntitulo: Um título\nurl: https://a.b/c\ntags: [a, b]\n---\n\n## Um\nTexto um.\n")
    assert meta["id"] == "x" and meta["url"] == "https://a.b/c" and meta["tags"] == ["a", "b"]
    assert kb._secoes(corpo) == [("Um", "Texto um.")]
    # `##` dentro de bloco de código não abre seção; seção vazia some
    texto = "## A\nlinha\n```\n## falso\n```\n## B\n"
    assert [t for t, _ in kb._secoes(texto)] == ["A"]


# ------------------------------------------------------------- índice em disco
def test_gravar_e_carregar_indice():
    ind = _indice()
    with tempfile.TemporaryDirectory() as d:
        kb.gravar_indice(CHUNKS, ind.vetores, d)
        lido = kb.carregar_indice(d, recarregar=True)
        assert lido.vetores.shape == (3, DIM) and lido.vetores.dtype == np.float32
        assert np.allclose(lido.vetores, ind.vetores)
        assert [c["id"] for c in lido.chunks] == [c["id"] for c in CHUNKS]
        assert "texto_embutido" not in lido.chunks[0]
        try:
            kb.gravar_indice(CHUNKS[:2], ind.vetores, d)
        except ValueError:
            pass
        else:
            raise AssertionError("chunks e vetores com tamanhos diferentes deviam falhar")


def test_indice_ausente_orienta():
    try:
        kb.carregar_indice("/tmp/nao_existe_rag_index", recarregar=True)
    except FileNotFoundError as e:
        assert "11_indexar_rag" in str(e)
    else:
        raise AssertionError("devia falhar sem índice")


# --------------------------------------------------------------------- busca
def test_ranking_acha_o_trecho_certo():
    ind = _indice()
    r = kb.buscar("como o índice de risco é calculado?", indice=ind, embutidor=embutidor_falso, limiar=0.0, k=3)
    assert r[0]["id"] == "doc1#01"
    assert [x["similaridade"] for x in r] == sorted((x["similaridade"] for x in r), reverse=True)
    assert kb.buscar("AUC do modelo XGBoost", indice=ind, embutidor=embutidor_falso, limiar=0.0)[0]["id"] == "doc2#01"


def test_k_limiar_e_exclusao():
    ind = _indice()
    kw = dict(indice=ind, embutidor=embutidor_falso)
    assert len(kb.buscar("índice de risco modelo Operação", k=2, limiar=0.0, **kw)) == 2
    assert kb.buscar("banana abacaxi laranja", limiar=0.5, **kw) == []          # nada parecido: nada volta
    com = kb.buscar("como o índice de risco é calculado?", limiar=0.0, k=1, **kw)
    sem = kb.buscar("como o índice de risco é calculado?", limiar=0.0, k=1, excluir={com[0]["id"]}, **kw)
    assert sem and sem[0]["id"] != com[0]["id"], "o chunk excluído devia dar lugar ao próximo"


def test_pergunta_vazia_e_dimensao_errada():
    ind = _indice()
    try:
        kb.buscar("   ", indice=ind, embutidor=embutidor_falso)
    except ValueError:
        pass
    else:
        raise AssertionError("pergunta vazia devia falhar")
    curto = lambda textos, tarefa: np.ones((len(textos), 8), dtype=np.float32) / np.sqrt(8)  # noqa: E731
    try:
        kb.buscar("qualquer", indice=ind, embutidor=curto)
    except ValueError as e:
        assert "dimensões" in str(e)
    else:
        raise AssertionError("dimensão diferente devia falhar")


# ---------------------------------------------------------------- ferramenta
def _com_busca(fn):
    original = kb.buscar
    kb.buscar = fn
    try:
        return tools.buscar_conhecimento("pergunta")
    finally:
        kb.buscar = original


def test_ferramenta_registrada():
    assert "buscar_conhecimento" in tools._FUNCOES
    d = next(x for x in tools.DEFINICOES if x["name"] == "buscar_conhecimento")
    assert d["input_schema"]["required"] == ["pergunta"]


def test_ferramenta_interna_e_externa():
    achados = [{**CHUNKS[0], "similaridade": 0.8}, {**CHUNKS[2], "similaridade": 0.7}]
    out = _com_busca(lambda *a, **k: achados)
    assert out["fonte"].startswith("Documentação do projeto: Metodologia > Como o índice")
    assert len(out["dados"]["trechos"]) == 2 and out["dados"]["trechos"][0]["tipo"] == "interno"
    assert "segundo [origem]" in out["dados"]["observacao"]          # há trecho externo
    so_interno = _com_busca(lambda *a, **k: achados[:1])
    assert "segundo [origem]" not in so_interno["dados"]["observacao"]


def test_ferramenta_sem_trecho_nao_gera_fonte():
    out = _com_busca(lambda *a, **k: [])
    assert out["fonte"] == "" and out["dados"]["trechos"] == []
    assert "não complete de memória" in out["dados"]["observacao"]


def test_ferramenta_erro_vira_mensagem_curta():
    def sem_indice(*a, **k):
        raise FileNotFoundError("índice não encontrado")

    def rede(*a, **k):
        raise ConnectionError("sem rede")

    for falha, trecho in ((sem_indice, "indexada"), (rede, "indisponível")):
        try:
            _com_busca(falha)
        except ValueError as e:
            assert trecho in str(e)
        else:
            raise AssertionError("devia virar ValueError")


if __name__ == "__main__":
    falhas = 0
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok    {nome}")
            except AssertionError as e:
                falhas += 1
                print(f"FALHA {nome}: {e}")
    sys.exit(1 if falhas else 0)
