#!/usr/bin/env python3
"""
PageRank das paradas SEM depender do plugin GDS (indisponível no Aura Free).

Replica o cálculo usado no treino do modelo
(notebooks/03_feature_engineering.ipynb, célula do pagerank):
  - grafo dirigido; aresta (A, B) quando B vem logo após A numa viagem
    (= relações CONNECTS_TO do Neo4j, deduplicadas entre rotas)
  - nx.pagerank(G, alpha=0.85, max_iter=100)
  - paradas sem dado ficam com 0.0

Grava Stop.pagerank, usado por 07_predict_risk.py e pelas páginas do app.
Substitui o antigo 06_run_analyses.py (GDS). Rodar entre o 05 e o 07.
"""
import sys

import networkx as nx
from neo4j import GraphDatabase

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # raiz do repo (config.py)
import config

BATCH = 1000


def main():
    driver = GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )
    try:
        with driver.session() as session:
            stop_ids = [r["id"] for r in session.run("MATCH (s:Stop) RETURN s.id AS id")]
            edges = [
                (r["a"], r["b"])
                for r in session.run(
                    "MATCH (a:Stop)-[:CONNECTS_TO]->(b:Stop) "
                    "WHERE a <> b RETURN DISTINCT a.id AS a, b.id AS b"
                )
            ]
        if not stop_ids or not edges:
            print("Sem paradas ou conexões no Neo4j. Rode 02_load_gtfs_to_neo4j.py antes.")
            return 1

        G = nx.DiGraph()
        G.add_nodes_from(stop_ids)
        G.add_edges_from(edges)
        print(f"Nós: {G.number_of_nodes():,}, arestas: {G.number_of_edges():,}")

        pr = nx.pagerank(G, alpha=0.85, max_iter=100)
        rows = [{"id": sid, "pr": float(pr.get(sid, 0.0))} for sid in stop_ids]
        print(f"PageRank — min: {min(r['pr'] for r in rows):.2e}, "
              f"max: {max(r['pr'] for r in rows):.2e}, "
              f"média: {sum(r['pr'] for r in rows) / len(rows):.2e}")

        with driver.session() as session:
            for i in range(0, len(rows), BATCH):
                session.run(
                    "UNWIND $rows AS row MATCH (s:Stop {id: row.id}) SET s.pagerank = row.pr",
                    rows=rows[i:i + BATCH],
                )
        print(f"pagerank gravado em {len(rows):,} paradas.")
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
