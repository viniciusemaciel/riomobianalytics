.PHONY: help setup load-gtfs load-1746 sync metrics analysis run-all query reset-sync clean

# Project settings
PYTHON := python3
PYTHONPATH := $(shell pwd)
SCRIPTS_DIR := scripts

# Default target
help:
	@echo "RioMobiAnalytics - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Setup & Data Loading:"
	@echo "  make setup         - Initialize databases (MongoDB & Neo4j)"
	@echo "  make load-gtfs     - Load GTFS transit data into Neo4j"
	@echo "  make load-1746     - Load 1746 complaint data into MongoDB"
	@echo "  make sync          - Sync complaints from MongoDB to Neo4j"
	@echo "  make metrics       - Calculate risk scores from complaints (reativo)"
	@echo "  make analysis      - Run graph analytics (centrality, communities)"
	@echo "  make predict       - Run ML model and compute combined risk score"
	@echo "  make run-all       - Run complete ETL pipeline (all steps)"
	@echo ""
	@echo "Queries & Analysis:"
	@echo "  make query              - Run all example queries and show insights"
	@echo "  make query-list         - List all available queries"
	@echo "  make query-high-risk    - Find top 10 high-risk stops"
	@echo "  make query-routes       - Find top 10 risky routes"
	@echo "  make query-complaints   - Find stops with most complaints"
	@echo "  make query-connections  - Find critical transit connections"
	@echo "  make query-stats        - Show network statistics"
	@echo "  make query-risk-dist    - Show risk distribution"
	@echo "  make query-custom       - Run custom Cypher query"
	@echo "  make neo4j              - Open Neo4j Browser"
	@echo ""
	@echo "Utilities:"
	@echo "  make reset-sync    - Reset sync flags to re-sync complaints"
	@echo "  make clean         - Clean Python cache files"
	@echo "  make install       - Install Python dependencies"
	@echo ""

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

# Setup databases
setup:
	@echo "🚀 Setting up databases..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/01_setup_databases.py

# Load GTFS data
load-gtfs:
	@echo "🚌 Loading GTFS data..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/02_load_gtfs_to_neo4j.py

# Load 1746 data
load-1746:
	@echo "📋 Loading 1746 complaint data..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/03_load_1746_to_mongodb.py

# Sync complaints to Neo4j
sync:
	@echo "🔄 Syncing complaints to Neo4j..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/04_sync_1746_to_neo4j.py

# Calculate metrics (reativo)
metrics:
	@echo "📊 Calculating metrics (reativo)..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/05_calculate_metrics.py

# Run graph analytics
analysis:
	@echo "🕸️  Running graph analytics..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/06_run_analyses.py

# Predict risk with ML model + combine scores
predict:
	@echo "🤖 Running ML risk prediction + combined score..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/07_predict_risk.py

# Run complete pipeline
run-all:
	@echo "🚀 Running complete ETL pipeline..."
	./run_all.sh

# Run query examples
query:
	@echo "🔍 Running query examples..."
	@echo ""
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/query_examples.py

# Run specific Neo4j query
query-high-risk:
	@echo "🚨 Finding high-risk stops..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py high_risk_stops

query-routes:
	@echo "🚌 Finding risky routes..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py risky_routes

query-complaints:
	@echo "📍 Finding stops with most complaints..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py stops_with_complaints

query-connections:
	@echo "🔗 Finding critical connections..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py critical_connections

query-stats:
	@echo "📊 Network statistics..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py network_stats

query-risk-dist:
	@echo "📈 Risk distribution..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py risk_distribution

query-list:
	@echo "📋 Available queries..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py list

query-custom:
	@echo "✍️  Enter custom query..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/run_neo4j_query.py custom

# Reset sync flags
reset-sync:
	@echo "🔄 Resetting sync flags..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPTS_DIR)/reset_sync.py

# Open Neo4j Browser
neo4j:
	@echo "🌐 Opening Neo4j Browser..."
	@open http://localhost:7474 || xdg-open http://localhost:7474 || echo "Please open http://localhost:7474 in your browser"

# Clean Python cache
clean:
	@echo "🧹 Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "✅ Cleaned!"

# Full reset (use with caution)
reset: clean
	@echo "⚠️  This will reset the sync flags. Continue? [y/N] " && read ans && [ $${ans:-N} = y ]
	$(MAKE) reset-sync

# Quick sync and query (common workflow)
sync-query: sync metrics predict query

# Reload all data
reload: setup load-gtfs load-1746 sync metrics analysis predict

# Development targets
dev-setup: install setup
	@echo "✅ Development environment ready!"

# Check database connections
check:
	@echo "🔍 Checking database connections..."
	@echo ""
	@echo "MongoDB:"
	@mongosh --quiet --eval "db.adminCommand('ping')" || echo "❌ MongoDB not accessible"
	@echo ""
	@echo "Neo4j:"
	@curl -s http://localhost:7474 > /dev/null && echo "✅ Neo4j is running" || echo "❌ Neo4j not accessible"
