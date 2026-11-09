"""Verificação manual (precisa do Neo4j): o modo de leitura do assistente recusa escrita?

Rode da raiz:  python tests/check_somente_leitura.py

Tenta um SET que não altera nada (LIMIT 0), dentro e fora do modo de leitura.
Esperado: fora do modo, passa; dentro, o Neo4j recusa com erro de modo de acesso.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.utils.db_connections import query_neo4j, somente_leitura  # noqa: E402

ESCRITA = "MATCH (s:Stop) WITH s LIMIT 0 SET s.__teste = 1 RETURN count(s) AS n"

query_neo4j(ESCRITA)
print("fora do modo de leitura: escrita aceita (esperado, sem alterar dados)")

try:
    with somente_leitura():
        query_neo4j(ESCRITA)
    print("ATENÇÃO: a escrita passou no modo de leitura. O Neo4j não está recusando.")
    sys.exit(1)
except Exception as e:
    print(f"modo de leitura: escrita recusada, como esperado -> {str(e)[:120]}")
