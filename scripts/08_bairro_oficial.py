#!/usr/bin/env python3
"""Acrescenta o bairro oficial (Limite de Bairros da Prefeitura) às ocorrências do Fogo Cruzado.

Para cada ocorrência faz ponto em polígono com data/gtfs/Limite_de_Bairros.geojson.
Não altera o CSV original: grava uma cópia em data/processed/ (fora de
data/fogocruzado/, que o app lê inteira) com as colunas novas:
  bairro_oficial  nome do bairro pelo polígono (vazio fora do município do Rio)
  codbnum         código do bairro oficial (liga com o id_bairro do 1746)
  bairro_final    bairro_oficial, ou o `neighborhood` da API quando não há oficial
  bairro_fonte    'oficial' ou 'api'

Uso: python scripts/08_bairro_oficial.py [csv_de_entrada]
"""
import json
import sys
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "data" / "gtfs" / "Limite_de_Bairros.geojson"
FOGO_DIR = ROOT / "data" / "fogocruzado"
OUT_DIR = ROOT / "data" / "processed"


def carregar_bairros():
    feats = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    polys = [shape(f["geometry"]) for f in feats]
    nomes = [f["properties"]["nome"].strip() for f in feats]
    codigos = [int(f["properties"]["codbnum"]) for f in feats]
    return polys, nomes, codigos


def main():
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(FOGO_DIR.glob("*.csv"))[-1]
    saida = OUT_DIR / (entrada.stem + "_bairro_oficial.csv")
    OUT_DIR.mkdir(exist_ok=True)

    df = pd.read_csv(entrada)
    polys, nomes, codigos = carregar_bairros()
    tree = STRtree(polys)

    oficial, cod = [], []
    for lon, lat in zip(df["longitude"], df["latitude"]):
        idx = tree.query(Point(lon, lat), predicate="within") if pd.notna(lon) and pd.notna(lat) else []
        if len(idx):
            oficial.append(nomes[idx[0]])
            cod.append(codigos[idx[0]])
        else:
            oficial.append(None)
            cod.append(None)

    df["bairro_oficial"] = oficial
    df["codbnum"] = pd.array(cod, dtype="Int64")
    tem = df["bairro_oficial"].notna()
    df["bairro_final"] = df["bairro_oficial"].where(tem, df["neighborhood"])
    df["bairro_fonte"] = tem.map({True: "oficial", False: "api"})
    df.to_csv(saida, index=False)

    rio = df["city"] == "Rio de Janeiro"
    print(f"{len(df)} ocorrências | com bairro oficial: {int(tem.sum())} | fallback da API: {int((~tem).sum())}")
    print(f"Rio sem polígono: {int((rio & ~tem).sum())} (pontos na baía ou na divisa)")
    print(f"Fora do município do Rio (sem oficial, esperado): {int((~rio & ~tem).sum())}")
    print(f"Gravado em {saida}")


if __name__ == "__main__":
    main()
