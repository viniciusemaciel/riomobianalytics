#!/usr/bin/env python3
import os
import sys
from pymongo import MongoClient
from neo4j import GraphDatabase
import config

def setup_mongodb():
    print("Configuring MongoDB...")

    try:
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DB]

        db.reclamacoes_1746_raw.create_index("protocolo", unique=True)
        db.reclamacoes_1746_raw.create_index("synced_to_neo4j")
        db.reclamacoes_1746_raw.create_index("data_abertura")
        db.reclamacoes_1746_raw.create_index([("localizacao", "2dsphere")])

        print("MongoDB ready")
        client.close()
        return True

    except Exception as e:
        print(f"MongoDB setup failed: {e}")
        return False


def setup_neo4j():
    print("\n[!] setup_neo4j vai APAGAR todos os dados do Neo4j.")
    if os.environ.get("FORCE_RESET") == "true":
        print("    FORCE_RESET=true → confirmado automaticamente.")
    else:
        try:
            confirm = input("    Digite RESET para confirmar: ").strip()
            if confirm != "RESET":
                print("    Cancelado.")
                return False
        except EOFError:
            print("    Sem terminal interativo. Defina FORCE_RESET=true no ambiente.")
            return False

    print("Configuring Neo4j...")

    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Clearing database...")
            deleted_total = 0
            while True:
                result = session.run("""
                    MATCH (n)
                    WITH n LIMIT 500
                    DETACH DELETE n
                    RETURN count(n) as deleted
                """)
                deleted = result.single()["deleted"]
                deleted_total += deleted
                if deleted == 0:
                    break
                if deleted_total % 5000 == 0:
                    print(f"{deleted_total} nodes removed...")
            print(f"Cleared {deleted_total} nodes")

            constraints = [
                "CREATE CONSTRAINT stop_id_unique IF NOT EXISTS FOR (s:Stop) REQUIRE s.id IS UNIQUE",
                "CREATE CONSTRAINT route_id_unique IF NOT EXISTS FOR (r:Route) REQUIRE r.id IS UNIQUE",
                "CREATE CONSTRAINT trip_id_unique IF NOT EXISTS FOR (t:Trip) REQUIRE t.id IS UNIQUE",
                "CREATE CONSTRAINT reclamacao_id_unique IF NOT EXISTS FOR (rec:Reclamacao) REQUIRE rec.id IS UNIQUE",
                "CREATE CONSTRAINT neighborhood_name_unique IF NOT EXISTS FOR (n:Neighborhood) REQUIRE n.name IS UNIQUE",
                "CREATE CONSTRAINT categoria_nome_unique IF NOT EXISTS FOR (c:Categoria) REQUIRE c.nome IS UNIQUE"
            ]

            for constraint in constraints:
                session.run(constraint)

            indices = [
                "CREATE INDEX stop_name IF NOT EXISTS FOR (s:Stop) ON (s.name)",
                "CREATE INDEX stop_risk IF NOT EXISTS FOR (s:Stop) ON (s.risk_score)",
                "CREATE INDEX stop_location IF NOT EXISTS FOR (s:Stop) ON (s.lat, s.lon)",
                "CREATE INDEX rec_data IF NOT EXISTS FOR (r:Reclamacao) ON (r.data_abertura)",
                "CREATE INDEX rec_status IF NOT EXISTS FOR (r:Reclamacao) ON (r.status)",
                "CREATE INDEX route_name IF NOT EXISTS FOR (r:Route) ON (r.short_name)"
            ]

            for index in indices:
                session.run(index)

            session.run(
                "CREATE FULLTEXT INDEX reclamacao_search IF NOT EXISTS "
                "FOR (r:Reclamacao) ON EACH [r.descricao, r.servico]"
            )

            print("Neo4j ready")

        driver.close()
        return True

    except Exception as e:
        print(f"Neo4j setup failed: {e}")
        return False


if __name__ == "__main__":
    print("Database Setup\n")

    mongo_ok = setup_mongodb()
    neo4j_ok = setup_neo4j()

    if mongo_ok and neo4j_ok:
        print("\nDatabases configured successfully")
        sys.exit(0)
    else:
        print("\nSetup failed")
        sys.exit(1)
