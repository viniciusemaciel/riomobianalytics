#!/usr/bin/env python3
import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from tqdm import tqdm
import config
import sys
import zipfile
import os

class GTFSLoader:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self.gtfs_dir = config.GTFS_DIR

    def extract_gtfs_zip(self):
        zip_path = os.path.join(self.gtfs_dir, "gtfs_rio-de-janeiro.zip")
        required_files = ['stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt']

        all_exist = all(
            os.path.exists(os.path.join(self.gtfs_dir, f))
            for f in required_files
        )

        if all_exist:
            return True

        if not os.path.exists(zip_path):
            print(f"Zip file not found: {zip_path}")
            return False

        print("Extracting GTFS archive...")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.gtfs_dir)
                extracted_files = zip_ref.namelist()

                missing = [f for f in required_files
                          if not os.path.exists(os.path.join(self.gtfs_dir, f))]

                if missing:
                    print(f"Missing required files: {missing}")
                    return False

                for f in required_files:
                    file_path = os.path.join(self.gtfs_dir, f)
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    print(f"  {f}: {size_mb:.1f}MB")

                return True

        except Exception as e:
            print(f"Extraction failed: {e}")
            return False

    def load_stops(self):
        df = pd.read_csv(f"{self.gtfs_dir}/stops.txt")
        print(f"Loading {len(df)} stops...")

        with self.driver.session() as session:
            for _, row in tqdm(df.iterrows(), total=len(df), desc="Stops"):
                session.run("""
                    MERGE (s:Stop {id: $id})
                    ON CREATE SET
                        s.name = $name,
                        s.lat = $lat,
                        s.lon = $lon,
                        s.wheelchair_accessible = $wheelchair,
                        s.risk_score = 0.0,
                        s.total_reclamacoes = 0,
                        s.reclamacoes_abertas = 0,
                        s.betweenness_centrality = 0.0,
                        s.pagerank = 0.0,
                        s.community_id = 0,
                        s.created_at = datetime()
                    ON MATCH SET
                        s.name = $name,
                        s.lat = $lat,
                        s.lon = $lon,
                        s.wheelchair_accessible = $wheelchair
                """,
                    id=str(row['stop_id']),
                    name=str(row['stop_name']),
                    lat=float(row['stop_lat']),
                    lon=float(row['stop_lon']),
                    wheelchair=bool(row.get('wheelchair_boarding', 0) == 1)
                )

    def load_routes(self):
        df = pd.read_csv(f"{self.gtfs_dir}/routes.txt")
        print(f"Loading {len(df)} routes...")

        with self.driver.session() as session:
            for _, row in tqdm(df.iterrows(), total=len(df), desc="Routes"):
                session.run("""
                    MERGE (r:Route {id: $id})
                    ON CREATE SET
                        r.short_name = $short_name,
                        r.long_name = $long_name,
                        r.type = $type,
                        r.color = $color,
                        r.avg_risk_score = 0.0,
                        r.total_stops = 0,
                        r.high_risk_stops = 0
                    ON MATCH SET
                        r.short_name = $short_name,
                        r.long_name = $long_name,
                        r.type = $type,
                        r.color = $color
                """,
                    id=str(row['route_id']),
                    short_name=str(row['route_short_name']),
                    long_name=str(row['route_long_name']),
                    type=str(row.get('route_type', 'Bus')),
                    color=str(row.get('route_color', 'FFFFFF'))
                )

    def load_trips(self):
        df = pd.read_csv(f"{self.gtfs_dir}/trips.txt")
        print(f"Loading {len(df)} trips...")

        with self.driver.session() as session:
            for _, row in tqdm(df.iterrows(), total=len(df), desc="Trips"):
                session.run("""
                    MERGE (t:Trip {id: $id})
                    ON CREATE SET
                        t.route_id = $route_id,
                        t.headsign = $headsign,
                        t.direction = $direction,
                        t.service_type = $service_type
                    ON MATCH SET
                        t.route_id = $route_id,
                        t.headsign = $headsign,
                        t.direction = $direction,
                        t.service_type = $service_type
                """,
                    id=str(row['trip_id']),
                    route_id=str(row['route_id']),
                    headsign=str(row.get('trip_headsign', '')),
                    direction=int(row.get('direction_id', 0)),
                    service_type=str(row.get('service_id', 'weekday'))
                )

    def create_trip_route_relationships(self):
        print("Linking trips to routes...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:Trip), (r:Route)
                WHERE t.route_id = r.id
                MERGE (t)-[:BELONGS_TO]->(r)
                RETURN count(*) as total
            """)

            record = result.single()
            print(f"Created {record['total']} links")

    def load_stop_times_and_connections(self):
        df = pd.read_csv(f"{self.gtfs_dir}/stop_times.txt")
        print(f"Loading {len(df)} stop times...")

        df = df.sort_values(['trip_id', 'stop_sequence'])

        batch_size = config.BATCH_SIZE
        total_batches = len(df) // batch_size + 1

        with self.driver.session() as session:
            for i in tqdm(range(0, len(df), batch_size), desc="Stop times", total=total_batches):
                batch = df.iloc[i:i+batch_size]

                for _, row in batch.iterrows():
                    session.run("""
                        MATCH (t:Trip {id: $trip_id})
                        MATCH (s:Stop {id: $stop_id})
                        MERGE (t)-[:HAS_STOP {
                            stop_sequence: $sequence,
                            arrival_time: $arrival,
                            departure_time: $departure
                        }]->(s)
                    """,
                        trip_id=str(row['trip_id']),
                        stop_id=str(row['stop_id']),
                        sequence=int(row['stop_sequence']),
                        arrival=str(row['arrival_time']),
                        departure=str(row['departure_time'])
                    )

        print("Building stop connections...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:Trip)-[hs1:HAS_STOP]->(s1:Stop)
                MATCH (t)-[hs2:HAS_STOP]->(s2:Stop)
                WHERE hs2.stop_sequence = hs1.stop_sequence + 1

                WITH s1, s2, t, hs1.stop_sequence AS sequence,
                     point({latitude: s1.lat, longitude: s1.lon}) AS p1,
                     point({latitude: s2.lat, longitude: s2.lon}) AS p2

                MERGE (s1)-[c:CONNECTS_TO {route_id: t.route_id}]->(s2)
                ON CREATE SET
                    c.distance_meters = round(point.distance(p1, p2)),
                    c.sequence = sequence,
                    c.travel_time_seconds = 120,
                    c.risk_adjusted_cost = round(point.distance(p1, p2))

                RETURN count(c) as total
            """)

            record = result.single()
            print(f"Created {record['total']} connections")

    def create_route_serves_relationships(self):
        print("Linking routes to stops...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:Route)<-[:BELONGS_TO]-(t:Trip)-[:HAS_STOP]->(s:Stop)
                WITH r, s, count(DISTINCT t) AS trips_count
                MERGE (r)-[:SERVES {
                    total_trips_daily: trips_count,
                    avg_frequency_minutes: 15
                }]->(s)
                RETURN count(*) as total
            """)

            record = result.single()
            print(f"Created {record['total']} links")

    def create_neighborhoods(self):
        print("Setting up neighborhoods...")

        neighborhoods = [
            {"name": "Copacabana", "regiao": "Zona Sul", "populacao": 146392},
            {"name": "Ipanema", "regiao": "Zona Sul", "populacao": 42080},
            {"name": "Centro", "regiao": "Centro", "populacao": 41142},
            {"name": "Botafogo", "regiao": "Zona Sul", "populacao": 82890},
            {"name": "Tijuca", "regiao": "Zona Norte", "populacao": 181839},
            {"name": "Barra da Tijuca", "regiao": "Zona Oeste", "populacao": 300823},
        ]

        with self.driver.session() as session:
            for n in neighborhoods:
                session.run("""
                    MERGE (nb:Neighborhood {name: $name})
                    ON CREATE SET
                        nb.regiao = $regiao,
                        nb.populacao = $populacao,
                        nb.total_stops = 0,
                        nb.total_reclamacoes = 0,
                        nb.avg_risk_score = 0.0
                    ON MATCH SET
                        nb.regiao = $regiao,
                        nb.populacao = $populacao
                """, **n)

    def close(self):
        self.driver.close()

    def run(self):
        print("GTFS Loader\n")

        try:
            if not self.extract_gtfs_zip():
                print("Extraction failed")
                return False

            self.load_stops()
            self.load_routes()
            self.load_trips()
            self.create_trip_route_relationships()
            self.load_stop_times_and_connections()
            self.create_route_serves_relationships()
            self.create_neighborhoods()

            print("\nGTFS data loaded successfully")
            return True

        except Exception as e:
            print(f"\nLoad failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    loader = GTFSLoader()
    success = loader.run()
    sys.exit(0 if success else 1)
