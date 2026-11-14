#!/usr/bin/env python3
"""Leva os tiroteios do Fogo Cruzado para o Neo4j (opção A: sem relações).

Duas regras de contagem, cada uma para uma pergunta:

  Parada = EXPOSIÇÃO. `Stop.tiroteios_500m_total` e `Stop.tiroteios_500m_12m`
  contam as ocorrências a até 500 m da parada (o mesmo raio do alvo do modelo).
  Um tiroteio conta para TODAS as paradas no raio, de propósito. Por isso somar
  paradas de um bairro não dá o total do bairro: conta o mesmo tiroteio várias vezes.

  Bairro = OCORRÊNCIA. Um nó `(:Tiroteio)` por ocorrência, com `bairro` oficial
  (ponto em polígono, script 08). Contar por bairro é `count(t)` agrupado por
  `t.bairro`: cada tiroteio entra uma vez só. Fora do município do Rio, `bairro`
  fica vazio e `cidade` diz onde foi.

Os nós Tiroteio não têm relação com as paradas (cabe no limite do Aura Free); a
distância, quando preciso, sai de `point.distance(t.local, ...)`, com índice de ponto.

"12m" são os 12 últimos meses DA BASE (que termina em `tiroteios_base_fim`), não
os 12 meses antes de hoje.

Por padrão só calcula e grava data/processed/stops_tiroteios.csv (não toca em banco).
Com --gravar: cria restrição e índices, faz MERGE dos nós Tiroteio e SET das
propriedades das paradas, em lotes. Pode ser repetido; não apaga nada.

Precisa de data/processed/<csv do Fogo Cruzado>_bairro_oficial.csv (rode o script 08 antes).

Uso:
  python scripts/10_tiroteios_neo4j.py            # só calcula e confere
  python scripts/10_tiroteios_neo4j.py --gravar   # grava no Neo4j
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

PROC = ROOT / "data" / "processed"
STOPS = Path(config.GTFS_DIR) / "stops.txt"
OUT = PROC / "stops_tiroteios.csv"
RAIO_M = 500
BATCH = 2000
FMT_DATA = "%d/%m/%Y, %H:%M:%S"


def carregar_tiroteios() -> pd.DataFrame:
    arquivos = sorted(PROC.glob("*_bairro_oficial.csv"))
    if not arquivos:
        sys.exit("Não achei data/processed/*_bairro_oficial.csv. Rode antes: python scripts/08_bairro_oficial.py")
    df = pd.read_csv(arquivos[-1], usecols=["id", "latitude", "longitude", "data", "city", "neighborhood",
                                            "bairro_oficial", "codbnum"])
    df = df.drop_duplicates(subset="id")
    df["dt"] = pd.to_datetime(df["data"], format=FMT_DATA, errors="coerce")
    df = df.dropna(subset=["latitude", "longitude", "dt"]).reset_index(drop=True)
    df["mes"] = df["dt"].dt.to_period("M")
    print(f"{arquivos[-1].name}: {len(df)} ocorrências válidas, de {df['mes'].min()} a {df['mes'].max()}")
    return df


def contar_por_parada(tiros: pd.DataFrame) -> pd.DataFrame:
    stops = pd.read_csv(STOPS, dtype={"stop_id": str}, usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"])
    stops = stops.dropna(subset=["stop_lat", "stop_lon"]).reset_index(drop=True)
    fim = tiros["mes"].max()
    recente = (tiros["mes"] > fim - 12).values  # 12 meses: fim-11 .. fim

    la2, lo2 = np.radians(tiros["latitude"].values), np.radians(tiros["longitude"].values)
    total, ult12 = np.zeros(len(stops), int), np.zeros(len(stops), int)
    for i in range(0, len(stops), 300):  # em blocos, para não montar uma matriz de 6 mil x 20 mil de uma vez
        bloco = stops.iloc[i:i + 300]
        la1 = np.radians(bloco["stop_lat"].values)[:, None]
        lo1 = np.radians(bloco["stop_lon"].values)[:, None]
        a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
        perto = 2 * 6_371_000 * np.arcsin(np.sqrt(a)) <= RAIO_M
        total[i:i + 300] = perto.sum(axis=1)
        ult12[i:i + 300] = (perto & recente).sum(axis=1)
    stops["tiroteios_500m_total"] = total
    stops["tiroteios_500m_12m"] = ult12
    stops["tiroteios_base_inicio"] = str(tiros["mes"].min())
    stops["tiroteios_base_fim"] = str(fim)
    return stops


def gravar_neo4j(tiros: pd.DataFrame, stops: pd.DataFrame):
    from neo4j import GraphDatabase

    def _txt(v):
        return None if pd.isna(v) else str(v).strip()

    nos = [{
        "id": str(r.id),
        "data": r.dt.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00",
        "mes": str(r.mes), "ano": int(r.dt.year),
        "lat": float(r.latitude), "lon": float(r.longitude),
        "cidade": _txt(r.city), "bairro": _txt(r.bairro_oficial), "bairro_api": _txt(r.neighborhood),
        "codbnum": None if pd.isna(r.codbnum) else int(r.codbnum),
    } for r in tiros.itertuples()]
    props = [{"id": r.stop_id, "total": int(r.tiroteios_500m_total), "ult12": int(r.tiroteios_500m_12m),
              "ini": r.tiroteios_base_inicio, "fim": r.tiroteios_base_fim} for r in stops.itertuples()]

    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    try:
        with driver.session() as s:
            s.run("CREATE CONSTRAINT tiroteio_id_unique IF NOT EXISTS FOR (t:Tiroteio) REQUIRE t.id IS UNIQUE")
            s.run("CREATE POINT INDEX tiroteio_local IF NOT EXISTS FOR (t:Tiroteio) ON (t.local)")
            s.run("CREATE INDEX tiroteio_bairro IF NOT EXISTS FOR (t:Tiroteio) ON (t.bairro)")
            for i in range(0, len(nos), BATCH):
                s.run("""
                    UNWIND $rows AS row
                    MERGE (t:Tiroteio {id: row.id})
                    SET t.data = datetime(row.data), t.mes = row.mes, t.ano = row.ano,
                        t.lat = row.lat, t.lon = row.lon,
                        t.local = point({latitude: row.lat, longitude: row.lon}),
                        t.cidade = row.cidade, t.bairro = row.bairro, t.bairro_api = row.bairro_api,
                        t.codbnum = row.codbnum
                """, rows=nos[i:i + BATCH])
                print(f"  Tiroteio: {min(i + BATCH, len(nos))}/{len(nos)}")
            for i in range(0, len(props), BATCH):
                s.run("""
                    UNWIND $rows AS row
                    MATCH (st:Stop {id: row.id})
                    SET st.tiroteios_500m_total = row.total, st.tiroteios_500m_12m = row.ult12,
                        st.tiroteios_base_inicio = row.ini, st.tiroteios_base_fim = row.fim
                """, rows=props[i:i + BATCH])
            n_t = s.run("MATCH (t:Tiroteio) RETURN count(t) AS n").single()["n"]
            n_s = s.run("MATCH (s:Stop) WHERE s.tiroteios_500m_total IS NOT NULL RETURN count(s) AS n").single()["n"]
            n_n = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
            n_r = s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
        print(f"Neo4j: {n_t} nós Tiroteio, {n_s} paradas com contagem | grafo: {n_n} nós, {n_r} relações")
    finally:
        driver.close()


def main():
    tiros = carregar_tiroteios()
    stops = contar_por_parada(tiros)
    PROC.mkdir(exist_ok=True)
    stops.to_csv(OUT, index=False)

    rio = tiros["bairro_oficial"].notna()
    print(f"{len(stops)} paradas | com ao menos 1 tiroteio a 500 m na base toda: {(stops['tiroteios_500m_total'] > 0).sum()} "
          f"| nos 12 últimos meses da base: {(stops['tiroteios_500m_12m'] > 0).sum()}")
    print(f"Ocorrências no município do Rio (com bairro oficial): {rio.sum()} de {len(tiros)}")
    print("\nParadas com mais tiroteios a 500 m (base toda):")
    print(stops.nlargest(5, "tiroteios_500m_total")[["stop_name", "tiroteios_500m_total", "tiroteios_500m_12m"]].to_string(index=False))
    print("\nBairros com mais ocorrências (cada tiroteio conta uma vez):")
    print(tiros.loc[rio, "bairro_oficial"].value_counts().head(5).to_string())
    print(f"\nSoma das contagens das paradas: {stops['tiroteios_500m_total'].sum()} "
          f"(maior que as {len(tiros)} ocorrências porque um tiroteio conta para várias paradas; é esperado)")
    print(f"Gravado em {OUT}")
    if "--gravar" in sys.argv:
        gravar_neo4j(tiros, stops)
    else:
        print("Neo4j não alterado (use --gravar para gravar).")


if __name__ == "__main__":
    main()
