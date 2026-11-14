"""Testes do guard de Cypher livre (não precisam de banco nem de chave).

Rode da raiz:  python tests/test_cypher_guard.py      (ou: pytest tests/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.rag.cypher_guard import CypherBloqueado, LIMITE_MAXIMO, validar  # noqa: E402

# ---------------------------------------------------------------- devem passar
PERMITIDAS = [
    "MATCH (s:Stop) WHERE s.bairro = 'Tijuca' RETURN count(s) AS paradas",
    "MATCH (s:Stop) RETURN s.bairro AS bairro, avg(s.risk_score_normalized) AS indice ORDER BY indice DESC LIMIT 10",
    "MATCH (r:Route)-[:SERVES]->(s:Stop {risk_level: 'Alto'}) RETURN r.short_name, count(s) AS n ORDER BY n DESC LIMIT 5",
    "MATCH (rec:Reclamacao)-[:AFFECTS]->(s:Stop) WHERE rec.data_abertura >= datetime('2024-01-01') RETURN s.name, count(rec) LIMIT 20",
    "MATCH (rec:Reclamacao)-[:HAS_TYPE]->(c:Categoria) RETURN c.nome, count(*) AS total",
    "MATCH (a:Stop {id: '123'})-[:CONNECTS_TO*1..3]->(b:Stop) RETURN DISTINCT b.name LIMIT 30",
    "MATCH (s:Stop) WHERE s.name CONTAINS 'CREATE' RETURN s.name LIMIT 5",          # palavra proibida só dentro de string
    "MATCH (s:Stop) RETURN {nome: s.name, total: count(s)} AS item LIMIT 3",        # mapa com função
    "MATCH (s:Stop) WITH s.bairro AS b, count(*) AS n RETURN b, n ORDER BY n DESC;", # ; final tolerado
    "MATCH (a:Stop {id:'1'}), (b:Stop) WHERE point.distance(point({latitude:a.lat, longitude:a.lon}), "
    "point({latitude:b.lat, longitude:b.lon})) < 500 RETURN b.name LIMIT 10",
    "MATCH (s:Stop)-[:SERVES|CONNECTS_TO]-(x) RETURN count(x)",
    "// comentário\nMATCH (s:Stop) RETURN count(s)",
    "UNWIND ['Alto', 'Médio-Alto'] AS nivel MATCH (s:Stop {risk_level: nivel}) RETURN nivel, count(s)",
    "MATCH (t:Tiroteio) WHERE t.ano = 2024 RETURN t.bairro, count(t) AS n ORDER BY n DESC LIMIT 10",
    "MATCH (s:Stop {id: '1'}), (t:Tiroteio) WHERE point.distance(t.local, point({latitude: s.lat, longitude: s.lon})) <= 500 "
    "RETURN t.mes, count(t) ORDER BY t.mes",
    "MATCH (s:Stop) WHERE s.risk_level = 'Alto' RETURN s.name, s.risk_score_normalized ORDER BY s.risk_score_normalized DESC LIMIT 10",
]

# ------------------------------------------------------- devem ser bloqueadas
BLOQUEADAS = {
    "escrita: DELETE": "MATCH (s:Stop) DETACH DELETE s",
    "escrita: SET": "MATCH (s:Stop {id: '1'}) SET s.risk_score_normalized = 0 RETURN s",
    "escrita: SET minúsculo": "match (s:Stop) set s.x = 1 return s",
    "escrita: CREATE": "CREATE (s:Stop {id: 'x'}) RETURN s",
    "escrita: MERGE": "MERGE (s:Stop {id: 'x'}) RETURN s",
    "escrita: REMOVE": "MATCH (s:Stop) REMOVE s.bairro RETURN s",
    "escrita escondida depois de RETURN": "MATCH (s:Stop) RETURN s LIMIT 1 // ok\n; MATCH (n) DETACH DELETE n",
    "duas instruções": "MATCH (s:Stop) RETURN s; MATCH (n) RETURN n",
    "comentário de bloco escondendo ;": "MATCH (s:Stop) RETURN s /* x */ ; DROP INDEX foo",
    "FOREACH": "MATCH (s:Stop) FOREACH (x IN [1] | SET s.a = x) RETURN s",
    "procedimento db": "CALL db.labels() YIELD label RETURN label",
    "procedimento apoc": "MATCH (s:Stop) CALL apoc.create.node(['X'], {}) YIELD node RETURN node",
    "subconsulta CALL": "MATCH (s:Stop) CALL { WITH s RETURN s.id AS i } RETURN i",
    "função apoc": "MATCH (s:Stop) RETURN apoc.text.join([s.name], ',') LIMIT 1",
    "apoc.load.json (sai para a rede)": "WITH apoc.load.json('http://x') AS j RETURN j",
    "LOAD CSV": "LOAD CSV FROM 'file:///etc/passwd' AS l RETURN l",
    "admin: SHOW": "SHOW DATABASES",
    "admin: DROP": "DROP CONSTRAINT stop_id_unique",
    "começa com algo estranho": "PROFILE MATCH (s:Stop) RETURN s",
    "USE outro banco": "USE system MATCH (n) RETURN n",
    "UNION": "MATCH (s:Stop) RETURN s.id AS x UNION MATCH (r:Route) RETURN r.id AS x",
    "sem RETURN": "MATCH (s:Stop)",
    "rótulo fora da lista (Trip)": "MATCH (t:Trip) RETURN count(t)",
    "relação fora da lista (HAS_STOP)": "MATCH (t)-[:HAS_STOP]->(s:Stop) RETURN count(s)",
    "rótulo fora da lista (Neighborhood)": "MATCH (n:Neighborhood) RETURN n",
    "alternativa fora da lista": "MATCH (a:Stop)-[:SERVES|HAS_STOP]-(b) RETURN count(b)",
    "crase": "MATCH (s:`Stop`) RETURN s",
    "caminho sem teto (*)": "MATCH (a:Stop)-[:CONNECTS_TO*]->(b:Stop) RETURN count(b)",
    "caminho sem teto (2..)": "MATCH (a:Stop)-[:CONNECTS_TO*2..]->(b:Stop) RETURN count(b)",
    "caminho longo (*1..10)": "MATCH (a:Stop)-[:CONNECTS_TO*1..10]->(b:Stop) RETURN count(b)",
    "caminho longo (*8)": "MATCH (a:Stop)-[*8]->(b:Stop) RETURN count(b)",
    "padrão quantificado": "MATCH (a:Stop) ((x)-[:CONNECTS_TO]->(y)){1,20} (b:Stop) RETURN count(b)",
    "LIMIT com parâmetro": "MATCH (s:Stop) RETURN s LIMIT $n",
    "string sem fechar": "MATCH (s:Stop) WHERE s.name = 'abc RETURN s",
    "vazia": "   ",
    "longa demais": "MATCH (s:Stop) RETURN s.name " + "+ s.name " * 300,
}


def test_permitidas_passam():
    for q in PERMITIDAS:
        v = validar(q)
        assert v.consulta.rstrip().upper().split()[-2] == "LIMIT", q
        assert v.limite <= LIMITE_MAXIMO


def test_bloqueadas_sao_recusadas():
    for nome, q in BLOQUEADAS.items():
        try:
            validar(q)
        except CypherBloqueado:
            continue
        raise AssertionError(f"passou e não devia: {nome}")


def test_limit_acrescentado():
    v = validar("MATCH (s:Stop) RETURN s.name")
    assert v.consulta.endswith("LIMIT 50") and v.limite == 50 and v.avisos


def test_limit_reduzido():
    v = validar("MATCH (s:Stop) RETURN s.name LIMIT 5000")
    assert v.consulta.endswith("LIMIT 50") and "5000" not in v.consulta


def test_limit_pequeno_mantido():
    v = validar("MATCH (s:Stop) RETURN s.name LIMIT 7")
    assert v.consulta.endswith("LIMIT 7") and v.limite == 7 and not v.avisos


def test_comentario_nao_esconde_limit():
    v = validar("MATCH (s:Stop) RETURN s.name LIMIT 500 // fim")
    assert v.consulta.endswith("LIMIT 50") and "//" not in v.consulta


def test_limit_no_meio_nao_conta():
    v = validar("MATCH (s:Stop) WITH s LIMIT 1000 RETURN s.name")
    assert v.consulta.endswith("LIMIT 50")


def test_string_preservada():
    v = validar("MATCH (s:Stop) WHERE s.name = 'Praça; SET' RETURN s.name")
    assert "'Praça; SET'" in v.consulta


def test_mensagem_orienta_o_modelo():
    try:
        validar("MATCH (t:Trip) RETURN t")
    except CypherBloqueado as e:
        assert "Stop" in str(e) and "SERVES" in str(e)
    else:
        raise AssertionError("Trip devia ser bloqueado")


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
    print(f"\n{len(PERMITIDAS)} consultas permitidas e {len(BLOQUEADAS)} bloqueadas verificadas.")
    sys.exit(1 if falhas else 0)
