#!/usr/bin/env python3
from pymongo import MongoClient
from neo4j import GraphDatabase
from datetime import datetime
from tqdm import tqdm
import config
import sys

class Neo4jSync:
    def __init__(self):
        self.mongo_client = MongoClient(config.MONGO_URI)
        self.mongo_db = self.mongo_client[config.MONGO_DB]

        self.neo4j_driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )

    def sync_reclamacoes(self):
        reclamacoes = list(self.mongo_db.reclamacoes_1746_raw.find({
            'synced_to_neo4j': False
        }))

        print(f"Syncing {len(reclamacoes)} complaints...")

        if len(reclamacoes) == 0:
            print("Nothing to sync")
            return True

        synced_count = 0
        error_count = 0

        # Query com stop_id pré-calculado (CSV chamados_v2_com_stops_filtrado):
        # o join espacial já foi feito no ETL upstream, então só amarramos por id.
        query_with_stop_id = """
            MERGE (rec:Reclamacao {id: $rec_id})
            SET rec.protocolo = $protocolo,
                rec.data_abertura = datetime($data_abertura),
                rec.servico = $servico,
                rec.descricao = $descricao,
                rec.status = $status,
                rec.lat = $lat,
                rec.lon = $lon,
                rec.peso = $peso,
                rec.criticidade = $criticidade,
                rec.bairro = $bairro

            MERGE (cat:Categoria {nome: $servico})
            ON CREATE SET
                cat.peso_base = $peso,
                cat.total_ocorrencias = 0
            ON MATCH SET
                cat.total_ocorrencias = cat.total_ocorrencias + 1

            MERGE (rec)-[:HAS_TYPE]->(cat)

            WITH rec
            MATCH (s:Stop {id: $stop_id})
            MERGE (rec)-[a:AFFECTS]->(s)
            SET a.distance_meters = $distance_meters,
                a.impact_level = rec.criticidade,
                a.risk_contribution = rec.peso,
                a.started_affecting = rec.data_abertura

            WITH s
            SET s.total_reclamacoes = coalesce(s.total_reclamacoes, 0) + 1

            RETURN count(s) AS paradas_afetadas
        """

        # Fallback: se a reclamação vier sem stop_id pré-calculado (dataset antigo),
        # cai no spatial join original limitado por MAX_DISTANCE_AFFECTS_METERS.
        query_spatial_fallback = """
            MERGE (rec:Reclamacao {id: $rec_id})
            SET rec.protocolo = $protocolo,
                rec.data_abertura = datetime($data_abertura),
                rec.servico = $servico,
                rec.descricao = $descricao,
                rec.status = $status,
                rec.lat = $lat,
                rec.lon = $lon,
                rec.peso = $peso,
                rec.criticidade = $criticidade,
                rec.bairro = $bairro

            MERGE (cat:Categoria {nome: $servico})
            ON CREATE SET
                cat.peso_base = $peso,
                cat.total_ocorrencias = 0
            ON MATCH SET
                cat.total_ocorrencias = cat.total_ocorrencias + 1

            MERGE (rec)-[:HAS_TYPE]->(cat)

            WITH rec
            MATCH (s:Stop)
            WHERE point.distance(
              point({latitude: rec.lat, longitude: rec.lon}),
              point({latitude: s.lat, longitude: s.lon})
            ) <= $max_distance

            MERGE (rec)-[a:AFFECTS]->(s)
            SET a.distance_meters = round(point.distance(
                  point({latitude: rec.lat, longitude: rec.lon}),
                  point({latitude: s.lat, longitude: s.lon})
                )),
                a.impact_level = rec.criticidade,
                a.risk_contribution = rec.peso,
                a.started_affecting = rec.data_abertura

            WITH s
            SET s.total_reclamacoes = coalesce(s.total_reclamacoes, 0) + 1

            RETURN count(s) AS paradas_afetadas
        """

        with self.neo4j_driver.session() as session:
            for rec in tqdm(reclamacoes, desc="Complaints"):
                try:
                    common_params = dict(
                        rec_id=f"REC_{rec['protocolo']}",
                        protocolo=rec['protocolo'],
                        data_abertura=rec['data_abertura'].isoformat(),
                        servico=rec['servico'],
                        descricao=rec.get('descricao', ''),
                        status=rec['status'],
                        lat=rec['lat'],
                        lon=rec['lon'],
                        peso=rec['peso'],
                        criticidade=rec['criticidade'],
                        bairro=rec.get('bairro', ''),
                    )

                    if rec.get('stop_id_mais_proximo'):
                        result = session.run(
                            query_with_stop_id,
                            stop_id=rec['stop_id_mais_proximo'],
                            distance_meters=round(rec.get('distancia_metros', 0)),
                            **common_params,
                        )
                    else:
                        result = session.run(
                            query_spatial_fallback,
                            max_distance=config.MAX_DISTANCE_AFFECTS_METERS,
                            **common_params,
                        )

                    self.mongo_db.reclamacoes_1746_raw.update_one(
                        {'_id': rec['_id']},
                        {'$set': {
                            'synced_to_neo4j': True,
                            'sync_timestamp': datetime.now()
                        }}
                    )

                    synced_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"\nError syncing {rec['protocolo']}: {e}")
                    continue

        print(f"\nSynced: {synced_count}")
        print(f"Errors: {error_count}")

        return True

    def close(self):
        self.mongo_client.close()
        self.neo4j_driver.close()

    def run(self):
        print("Neo4j Sync\n")

        try:
            self.sync_reclamacoes()
            print("\nSync completed successfully")
            return True

        except Exception as e:
            print(f"\nSync failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    sync = Neo4jSync()
    success = sync.run()
    sys.exit(0 if success else 1)
