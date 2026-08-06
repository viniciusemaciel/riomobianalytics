#!/bin/bash
set -e

echo "==> Aguardando bancos…"
until python3 -c "
from neo4j import GraphDatabase
try:
    d = GraphDatabase.driver('${NEO4J_URI}', auth=('${NEO4J_USER}','${NEO4J_PASSWORD}'))
    d.verify_connectivity()
    print('Neo4j OK')
except Exception as e:
    exit(1)
" 2>/dev/null; do
    echo "   …Neo4j ainda não pronto, aguardando…"
    sleep 3
done

# Só roda o pipeline se o Neo4j estiver vazio (primeiro boot)
NEEDS_INIT=$(python3 -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('${NEO4J_URI}', auth=('${NEO4J_USER}','${NEO4J_PASSWORD}'))
with d.session() as s:
    r = s.run('MATCH (s:Stop) RETURN count(s) as c')
    c = r.single()['c']
    print('1' if c == 0 else '0')
d.close()
")

if [ "$NEEDS_INIT" = "1" ]; then
    echo "==> Primeiro boot: rodando pipeline ETL completo…"
    python3 scripts/01_setup_databases.py
    python3 scripts/02_load_gtfs_to_neo4j.py
    python3 scripts/03_load_1746_to_mongodb.py
    python3 scripts/04_sync_1746_to_neo4j.py
    python3 scripts/05_calculate_metrics.py
    python3 scripts/06_run_analyses.py
    python3 scripts/07_predict_risk.py
else
    echo "==> Dados já existentes, pulando pipeline…"
fi

echo "==> Subindo Streamlit…"
exec streamlit run webapp/Home.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.serverAddress=0.0.0.0
