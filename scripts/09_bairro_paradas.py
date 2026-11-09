#!/usr/bin/env python3
"""Bairro oficial de cada parada (ponto em polígono com Limite_de_Bairros.geojson).

Por padrão só calcula e grava data/processed/stops_bairro.csv (não toca em banco).
Com --gravar, também faz `SET s.bairro, s.codbnum` nos nós Stop do Neo4j, em lotes.
É um SET sobre propriedades novas: não apaga nem recria nada, e pode ser repetido.

Uso:
  python scripts/09_bairro_paradas.py             # só calcula e confere
  python scripts/09_bairro_paradas.py --gravar    # grava no Neo4j
"""
import json
import sys
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

GEOJSON = ROOT / "data" / "gtfs" / "Limite_de_Bairros.geojson"
STOPS = Path(config.GTFS_DIR) / "stops.txt"
OUT = ROOT / "data" / "processed" / "stops_bairro.csv"
BATCH = 1000


def calcular() -> pd.DataFrame:
    feats = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    polys = [shape(f["geometry"]) for f in feats]
    nomes = [f["properties"]["nome"].strip() for f in feats]
    codigos = [int(f["properties"]["codbnum"]) for f in feats]
    tree = STRtree(polys)

    stops = pd.read_csv(STOPS, dtype={"stop_id": str}, usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"])
    bairro, cod = [], []
    for lat, lon in zip(stops["stop_lat"], stops["stop_lon"]):
        idx = tree.query(Point(lon, lat), predicate="within") if pd.notna(lat) and pd.notna(lon) else []
        bairro.append(nomes[idx[0]] if len(idx) else None)
        cod.append(codigos[idx[0]] if len(idx) else None)
    stops["bairro"] = bairro
    stops["codbnum"] = pd.array(cod, dtype="Int64")
    return stops


def gravar_neo4j(stops: pd.DataFrame):
    from neo4j import GraphDatabase

    com = stops[stops["bairro"].notna()]
    rows = [{"id": r.stop_id, "bairro": r.bairro, "cod": int(r.codbnum)} for r in com.itertuples()]
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            for i in range(0, len(rows), BATCH):
                session.run(
                    "UNWIND $rows AS row MATCH (s:Stop {id: row.id}) SET s.bairro = row.bairro, s.codbnum = row.cod",
                    rows=rows[i:i + BATCH],
                )
            n = session.run("MATCH (s:Stop) WHERE s.bairro IS NOT NULL RETURN count(s) AS n").single()["n"]
        print(f"Neo4j: {n} paradas com bairro")
    finally:
        driver.close()


def main():
    stops = calcular()
    OUT.parent.mkdir(exist_ok=True)
    stops.to_csv(OUT, index=False)
    sem = stops["bairro"].isna().sum()
    print(f"{len(stops)} paradas | com bairro: {len(stops) - sem} | sem bairro: {sem}")
    print(stops["bairro"].value_counts().head(5).to_string())
    print(f"Gravado em {OUT}")
    if "--gravar" in sys.argv:
        gravar_neo4j(stops)
    else:
        print("Neo4j não alterado (use --gravar para gravar).")


if __name__ == "__main__":
    main()
