"""Testes do catálogo de temas e da ferramenta o_que_posso_perguntar (sem chave, sem rede, sem banco).

Rode da raiz:  python tests/test_catalogo.py      (ou: pytest tests/)
"""
import contextlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_db = types.ModuleType("webapp.utils.db_connections")
_db.query_neo4j = lambda *a, **k: []
_db.somente_leitura = contextlib.nullcontext
sys.modules["webapp.utils.db_connections"] = _db
for _nome in ("webapp.utils.data_fetchers", "webapp.utils.insights"):
    sys.modules[_nome] = types.ModuleType(_nome)

from webapp.rag import catalogo, conhecimento, tools  # noqa: E402

DOCS = {p.stem for p in conhecimento.DOCS_DIR.glob("*.md") if conhecimento._indexavel(p)}


def test_temas_curtos_e_com_tres_perguntas():
    for t in catalogo.temas(com_parada=True):
        assert len(t.perguntas) == 3, f"{t.nome}: {len(t.perguntas)} perguntas"
        assert len(t.nome) <= 18, f"nome longo demais para o seletor: {t.nome}"
        assert len(t.descricao) <= 110, f"descrição longa: {t.nome}"
        for p in t.perguntas:
            assert len(p.texto) <= 70, f"pergunta longa: {p.texto}"
    ids = [t.id for t in catalogo.temas(com_parada=True)]
    assert len(ids) == len(set(ids))
    assert catalogo.temas()[0].id != "parada" and catalogo.temas(True)[0].id == "parada"


def test_docs_esperados_existem():
    for t in catalogo.TEMAS:
        for p in t.perguntas:
            faltam = [d for d in p.docs if d not in DOCS]
            assert not faltam, f"{p.texto}: docs inexistentes {faltam}"


def test_documentos_e_titulo_curto():
    docs = catalogo.documentos(conhecimento.montar_chunks())
    assert {d["id"] for d in docs} == DOCS
    assert any(d["tipo"] == "externo" for d in docs)
    assert catalogo.titulo_curto("Contexto externo — linha do tempo") == "Linha do tempo"
    assert catalogo.titulo_curto("Fonte de dados — GTFS da rede") == "GTFS da rede"
    assert catalogo.titulo_curto("O modelo XGBoost") == "O modelo XGBoost"


def test_ferramenta_sem_fonte_e_registrada():
    assert "o_que_posso_perguntar" in tools._FUNCOES
    d = next(x for x in tools.DEFINICOES if x["name"] == "o_que_posso_perguntar")
    assert d["input_schema"]["properties"] == {}
    out = tools.o_que_posso_perguntar()
    assert out["fonte"] == ""
    dados = out["dados"]
    assert len(dados["temas"]) == len(catalogo.TEMAS) and dados["nao_responde"]
    assert dados["documentacao"]["do_projeto"] and dados["documentacao"]["fontes_externas"]


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
