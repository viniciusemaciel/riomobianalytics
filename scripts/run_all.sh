#!/bin/bash
# Carga completa dos bancos (Neo4j + MongoDB) a partir de data/.
# Usa as credenciais do .env. ATENÇÃO: o passo 01 APAGA os dados existentes.
#   ./scripts/run_all.sh            pede confirmação no passo 01
#   FORCE_RESET=true ./scripts/run_all.sh   sem confirmação
set -e
cd "$(dirname "$0")/.."

STEPS=(
  01_setup_databases.py
  02_load_gtfs_to_neo4j.py
  03_load_1746_to_mongodb.py
  04_sync_1746_to_neo4j.py
  05_calculate_metrics.py
  06_pagerank.py
  07_predict_risk.py
)

for step in "${STEPS[@]}"; do
  echo "==> $step"
  python3 "scripts/$step"
done
echo "==> Carga completa."
