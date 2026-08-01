#!/usr/bin/env python3
from neo4j import GraphDatabase
import config
import sys

class GraphAnalyzer:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )

    def create_graph_projection(self):
        print("Building graph projection...")

        with self.driver.session() as session:
            try:
                result = session.run("CALL gds.graph.exists('transportNetwork') YIELD exists RETURN exists")
                exists = result.single()["exists"]
                if exists:
                    session.run("CALL gds.graph.drop('transportNetwork')")
            except Exception as e:
                pass

            session.run("""
                CALL gds.graph.project(
                  'transportNetwork',
                  'Stop',
                  'CONNECTS_TO',
                  {
                    nodeProperties: ['risk_score', 'lat', 'lon'],
                    relationshipProperties: ['distance_meters', 'risk_adjusted_cost']
                  }
                )
            """)

    def calculate_betweenness_centrality(self):
        print("Calculating centrality...")

        with self.driver.session() as session:
            try:
                result = session.run("""
                    CALL gds.betweenness.write('transportNetwork', {
                      writeProperty: 'betweenness_centrality'
                    })
                    YIELD centralityDistribution

                    RETURN
                      centralityDistribution.min AS min_centrality,
                      centralityDistribution.max AS max_centrality,
                      centralityDistribution.mean AS avg_centrality
                """)

                record = result.single()
                print(f"Avg: {record['avg_centrality']:.6f}, Max: {record['max_centrality']:.6f}")
            except Exception as e:
                print(f"[warn] Betweenness centrality falhou (bug conhecido do GDS 5.14): {e}. Prosseguindo sem essa métrica.")
                return

            result = session.run("""
                MATCH (s:Stop)
                WHERE s.betweenness_centrality > 0
                RETURN
                  s.name AS parada,
                  s.betweenness_centrality AS centralidade,
                  s.risk_score AS risco,
                  CASE
                    WHEN s.betweenness_centrality > 0.05 AND s.risk_score > 0.6
                    THEN 'CRITICO'
                    WHEN s.betweenness_centrality > 0.05
                    THEN 'Estruturalmente Critico'
                    WHEN s.risk_score > 0.6
                    THEN 'Alto Risco'
                    ELSE 'Normal'
                  END AS classificacao
                ORDER BY s.betweenness_centrality DESC
                LIMIT 10
            """)

            print("Top 10 critical stops:")
            for i, record in enumerate(result, 1):
                print(f"  {i}. {record['parada'][:40]:40} | "
                      f"Cent: {record['centralidade']:.4f} | "
                      f"Risk: {record['risco']:.2f} | "
                      f"{record['classificacao']}")

    def detect_communities(self):
        print("Detecting communities...")

        with self.driver.session() as session:
            result = session.run("""
                CALL gds.louvain.write('transportNetwork', {
                  writeProperty: 'community_id',
                  relationshipWeightProperty: 'distance_meters'
                })
                YIELD communityCount, modularity

                RETURN communityCount, modularity
            """)

            record = result.single()
            print(f"{record['communityCount']} communities, Modularity: {record['modularity']:.4f}")

            result = session.run("""
                MATCH (s:Stop)
                WHERE s.community_id IS NOT NULL

                WITH s.community_id AS community,
                     collect(s.name) AS paradas,
                     count(s) AS tamanho,
                     avg(s.risk_score) AS risco_medio,
                     max(s.risk_score) AS risco_maximo

                RETURN
                  community,
                  tamanho,
                  round(risco_medio * 100) / 100 AS risco_medio,
                  round(risco_maximo * 100) / 100 AS risco_maximo,
                  paradas[..3] AS amostra_paradas

                ORDER BY risco_medio DESC
                LIMIT 10
            """)

            print("Top 10 by risk:")
            for i, record in enumerate(result, 1):
                print(f"  {i}. Community {record['community']} | "
                      f"Size: {record['tamanho']} | "
                      f"Risk: {record['risco_medio']:.2f}")

    def calculate_pagerank(self):
        print("Calculating PageRank...")

        with self.driver.session() as session:
            result = session.run("""
                CALL gds.pageRank.write('transportNetwork', {
                  writeProperty: 'pagerank',
                  dampingFactor: 0.85,
                  maxIterations: 20
                })
                YIELD nodePropertiesWritten, ranIterations

                RETURN nodePropertiesWritten, ranIterations
            """)

            record = result.single()
            print(f"{record['nodePropertiesWritten']} nodes, {record['ranIterations']} iterations")

            result = session.run("""
                MATCH (s:Stop)
                WHERE s.pagerank IS NOT NULL
                RETURN
                  s.name AS parada,
                  s.pagerank AS importancia,
                  s.risk_score AS risco
                ORDER BY s.pagerank DESC
                LIMIT 10
            """)

            print("Top 10 by importance:")
            for i, record in enumerate(result, 1):
                print(f"  {i}. {record['parada'][:40]:40} | "
                      f"PageRank: {record['importancia']:.6f} | "
                      f"Risk: {record['risco']:.2f}")

    def identify_reclamacao_clusters(self):
        print("Identifying clusters...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (r1:Reclamacao), (r2:Reclamacao)
                WHERE id(r1) < id(r2)
                  AND r1.servico = r2.servico
                  AND point.distance(
                    point({latitude: r1.lat, longitude: r1.lon}),
                    point({latitude: r2.lat, longitude: r2.lon})
                  ) <= 200
                  AND duration.between(r1.data_abertura, r2.data_abertura).days <= 7

                MERGE (r1)-[c:CLUSTERS_WITH]->(r2)
                SET c.spatial_proximity_meters = round(point.distance(
                      point({latitude: r1.lat, longitude: r1.lon}),
                      point({latitude: r2.lat, longitude: r2.lon})
                    )),
                    c.temporal_proximity_hours = duration.between(
                      r1.data_abertura, r2.data_abertura
                    ).hours

                RETURN count(c) AS clusters_criados
            """)

            record = result.single()
            print(f"{record['clusters_criados']} cluster links created")

    def generate_summary_report(self):
        print("\n" + "=" * 60)
        print("  SYSTEM SUMMARY")
        print("=" * 60)

        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Stop)
                WITH count(s) AS total_stops,
                     avg(s.risk_score) AS avg_risk,
                     count(CASE WHEN s.risk_score >= 0.6 THEN 1 END) AS high_risk_count

                MATCH (r:Route)
                WITH total_stops, avg_risk, high_risk_count, count(r) AS total_routes

                MATCH (rec:Reclamacao)
                WITH total_stops, avg_risk, high_risk_count, total_routes,
                     count(rec) AS total_reclamacoes,
                     count(CASE WHEN rec.status = 'Aberto' THEN 1 END) AS reclamacoes_abertas

                RETURN *
            """)

            stats = result.single()

            print(f"\nStops: {stats['total_stops']:,}")
            print(f"Routes: {stats['total_routes']:,}")
            print(f"Complaints: {stats['total_reclamacoes']:,} ({stats['reclamacoes_abertas']:,} open)")
            print(f"\nAvg Risk: {stats['avg_risk']:.3f}")
            print(f"High Risk Stops: {stats['high_risk_count']:,}")

            result = session.run("""
                MATCH (c:Categoria)<-[:HAS_TYPE]-(rec:Reclamacao)
                RETURN
                  c.nome AS categoria,
                  count(rec) AS total
                ORDER BY total DESC
                LIMIT 5
            """)

            print("\nTop Complaint Categories:")
            for i, record in enumerate(result, 1):
                print(f"  {i}. {record['categoria']:30} {record['total']:,}")

            print("=" * 60)

    def close(self):
        self.driver.close()

    def run(self):
        print("Graph Analyzer\n")

        try:
            self.create_graph_projection()
            self.calculate_betweenness_centrality()
            self.detect_communities()
            self.calculate_pagerank()
            self.identify_reclamacao_clusters()
            self.generate_summary_report()

            print("\nAnalysis completed successfully\n")
            return True

        except Exception as e:
            print(f"\nAnalysis failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    analyzer = GraphAnalyzer()
    success = analyzer.run()
    sys.exit(0 if success else 1)
