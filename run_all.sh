#!/bin/bash

echo "RioMobiAnalytics - Full Data Load"
echo "=============================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

run_script() {
    script_name=$1
    echo "Running: $script_name"
    PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 scripts/$script_name

    if [ $? -eq 0 ]; then
        echo "${GREEN}$script_name complete${NC}"
        echo ""
        return 0
    else
        echo "${RED}$script_name failed${NC}"
        echo ""
        return 1
    fi
}

run_script "01_setup_databases.py" || exit 1
run_script "02_load_gtfs_to_neo4j.py" || exit 1
run_script "03_load_1746_to_mongodb.py" || exit 1
run_script "04_sync_1746_to_neo4j.py" || exit 1
run_script "05_calculate_metrics.py" || exit 1
run_script "06_run_analyses.py" || exit 1
run_script "07_predict_risk.py" || exit 1

echo "=============================================="
echo "${GREEN}Full load complete${NC}"
echo "=============================================="
