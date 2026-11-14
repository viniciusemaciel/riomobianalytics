"""Teste do caminho da consulta livre com o banco simulado (sem Neo4j, sem chave).

Prova que: (1) consulta bloqueada nunca chega ao banco; (2) consulta válida roda
em modo de leitura, com timeout e com o LIMIT aplicado; (3) erros do banco viram
mensagens curtas para o modelo.

Rode da raiz:  python tests/test_consulta_cypher.py      (ou: pytest tests/)
"""
import contextlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- banco falso: substitui os módulos que importam streamlit/neo4j ------------
CHAMADAS = []          # (consulta, timeout, em_modo_leitura)
_estado = {"leitura": False, "resposta": [{"bairro": "Bangu", "n": 42}], "erro": None}


@contextlib.contextmanager
def _somente_leitura():
    _estado["leitura"] = True
    try:
        yield
    finally:
        _estado["leitura"] = False


def _query_neo4j(consulta, parameters=None, timeout=None):
    CHAMADAS.append((consulta, timeout, _estado["leitura"]))
    if _estado["erro"]:
        raise _estado["erro"]
    return _estado["resposta"]


db = types.ModuleType("webapp.utils.db_connections")
db.query_neo4j, db.somente_leitura = _query_neo4j, _somente_leitura
sys.modules["webapp.utils.db_connections"] = db
for nome in ("webapp.utils.data_fetchers", "webapp.utils.insights"):
    sys.modules[nome] = types.ModuleType(nome)

from webapp.rag import tools  # noqa: E402
from webapp.rag.cypher_guard import CypherBloqueado, TIMEOUT_S  # noqa: E402


def _reset(resposta=None, erro=None):
    CHAMADAS.clear()
    _estado.update(resposta=resposta if resposta is not None else [{"bairro": "Bangu", "n": 42}], erro=erro)


def test_escrita_nao_chega_ao_banco():
    _reset()
    for q in ("MATCH (s:Stop) DETACH DELETE s",
              "MATCH (s:Stop) SET s.risk_score_normalized = 0 RETURN s",
              "MATCH (s:Stop) RETURN s; MATCH (n) DELETE n",
              "CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DELETE n', {})"):
        try:
            tools.executar("consulta_cypher", {"consulta": q, "objetivo": "teste"})
        except CypherBloqueado:
            pass
        else:
            raise AssertionError(f"não bloqueou: {q}")
    assert CHAMADAS == [], f"o banco foi chamado: {CHAMADAS}"


def test_consulta_valida_roda_em_leitura_com_timeout_e_limit():
    _reset()
    out = tools.executar("consulta_cypher", {
        "consulta": "MATCH (s:Stop {risk_level: 'Alto'}) RETURN s.bairro AS bairro, count(*) AS n ORDER BY n DESC",
        "objetivo": "paradas de nível alto por bairro"})
    (consulta, timeout, leitura), = CHAMADAS
    assert leitura, "não rodou em modo de leitura"
    assert timeout == TIMEOUT_S
    assert consulta.endswith("LIMIT 50")
    assert out["dados"]["linhas"] == [{"bairro": "Bangu", "n": 42}]
    assert out["detalhe"] == consulta and "paradas de nível alto" in out["fonte"]


def test_texto_longo_e_cortado():
    _reset(resposta=[{"descricao": "x" * 5000}])
    out = tools.executar("consulta_cypher", {"consulta": "MATCH (r:Reclamacao) RETURN r.descricao AS descricao", "objetivo": "t"})
    assert len(out["dados"]["linhas"][0]["descricao"]) <= tools.MAX_CHARS_VALOR + 1


def test_aviso_de_lista_cortada():
    _reset(resposta=[{"i": i} for i in range(50)])
    out = tools.executar("consulta_cypher", {"consulta": "MATCH (s:Stop) RETURN s.id AS i", "objetivo": "t"})
    assert out["dados"]["pode_haver_mais"] is True


class TransactionTimedOut(Exception):
    pass


def test_timeout_vira_mensagem_curta():
    _reset(erro=TransactionTimedOut("Neo.ClientError.Transaction.TransactionTimedOut: blah"))
    try:
        tools.executar("consulta_cypher", {"consulta": "MATCH (a:Stop), (b:Stop) RETURN count(*)", "objetivo": "t"})
    except ValueError as e:
        assert f"{TIMEOUT_S} s" in str(e) and "Filtre" in str(e)
    else:
        raise AssertionError("devia falhar")


def test_recusa_de_escrita_do_banco_vira_mensagem():
    # terceira camada: se algo passasse pelo guard, o modo de leitura do Neo4j recusaria
    _reset(erro=Exception("Writing in read access mode not allowed"))
    try:
        tools.executar("consulta_cypher", {"consulta": "MATCH (s:Stop) RETURN s.id", "objetivo": "t"})
    except ValueError as e:
        assert "só lê" in str(e)
    else:
        raise AssertionError("devia falhar")


def test_ferramenta_declarada():
    nomes = [d["name"] for d in tools.DEFINICOES]
    assert "consulta_cypher" in nomes
    d = next(d for d in tools.DEFINICOES if d["name"] == "consulta_cypher")
    assert d["input_schema"]["required"] == ["consulta", "objetivo"]


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
