#!/usr/bin/env python3
from neo4j import GraphDatabase
import config
import sys

class MetricsCalculator:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )

    def calculate_risk_scores(self):
        print("Calculating risk scores...")

        with self.driver.session() as session:
            # Step 1: Calculate raw risk scores
            # Considera todo o histórico de reclamações — o dataset atual
            # (chamados_v2_com_stops_filtrado) já foi curado por relevância
            # e cobre 2020-2025, então limitar por janela zeraria o score.
            result = session.run("""
                MATCH (s:Stop)<-[a:AFFECTS]-(rec:Reclamacao)
                WHERE rec.status IN ['Aberto', 'Em Atendimento']

                WITH s,
                     count(rec) AS total_reclamacoes,
                     count(CASE WHEN rec.status = 'Aberto' THEN 1 END) AS abertas,
                     sum(a.risk_contribution) AS risk_sum

                SET s.total_reclamacoes = total_reclamacoes,
                    s.reclamacoes_abertas = abertas,
                    s.risk_score = risk_sum / (risk_sum + 10.0),
                    s.last_risk_update = datetime()

                RETURN count(s) AS paradas_atualizadas,
                       avg(s.risk_score) AS avg_risk,
                       max(s.risk_score) AS max_risk,
                       min(s.risk_score) AS min_risk
            """)

            record = result.single()
            if record:
                print(f"{record['paradas_atualizadas']} stops updated")
                if record['avg_risk'] is not None:
                    print(f"Avg: {record['avg_risk']:.3f}, Max: {record['max_risk']:.3f}")

            # Step 2: Calculate percentiles and normalize
            result = session.run("""
                MATCH (s:Stop)
                WHERE s.risk_score IS NOT NULL
                WITH min(s.risk_score) as min_score,
                     max(s.risk_score) as max_score
                RETURN min_score, max_score
            """)

            bounds = result.single()
            if not bounds:
                return False

            min_score = bounds['min_score']
            max_score = bounds['max_score']

            # Normalize all scores
            result = session.run("""
                MATCH (s:Stop)
                WHERE s.risk_score IS NOT NULL
                SET s.risk_score_normalized =
                  CASE
                    WHEN $max_score = $min_score THEN 50.0
                    ELSE (s.risk_score - $min_score) / ($max_score - $min_score) * 100.0
                  END
                RETURN count(s) as stops_normalized
            """, max_score=max_score, min_score=min_score)

            record = result.single()
            if record:
                print(f"{record['stops_normalized']} stops normalized to 0-100 scale")

            # Get count of stops with risk
            result = session.run("""
                MATCH (s:Stop)
                WHERE s.risk_score_normalized > 0
                RETURN count(s) as total_with_risk
            """)

            total_with_risk = result.single()['total_with_risk']
            third = total_with_risk // 3

            # Set risk levels using ordered queries
            # Top 1/3: Alto
            session.run(f"""
                MATCH (s:Stop)
                WHERE s.risk_score_normalized > 0
                WITH s
                ORDER BY s.risk_score_normalized DESC
                LIMIT {third}
                SET s.risk_level = 'Alto'
            """)

            # Middle 1/3: Médio
            session.run(f"""
                MATCH (s:Stop)
                WHERE s.risk_score_normalized > 0
                WITH s
                ORDER BY s.risk_score_normalized DESC
                SKIP {third}
                LIMIT {third}
                SET s.risk_level = 'Medio'
            """)

            # Bottom 1/3: Baixo
            session.run(f"""
                MATCH (s:Stop)
                WHERE s.risk_score_normalized > 0
                WITH s
                ORDER BY s.risk_score_normalized DESC
                SKIP {third * 2}
                SET s.risk_level = 'Baixo'
            """)

            # Set all zero-score stops to Baixo
            session.run("""
                MATCH (s:Stop)
                WHERE s.risk_score_normalized = 0
                SET s.risk_level = 'Baixo'
            """)

            # Verify distribution
            result = session.run("""
                MATCH (s:Stop)
                RETURN count(CASE WHEN s.risk_level = 'Alto' THEN 1 END) as alto,
                       count(CASE WHEN s.risk_level = 'Medio' THEN 1 END) as medio,
                       count(CASE WHEN s.risk_level = 'Baixo' THEN 1 END) as baixo
            """)

            record = result.single()
            if record:
                print(f"Final distribution - Alto:{record['alto']}, Médio:{record['medio']}, Baixo:{record['baixo']}")

            return True

    def update_connection_costs(self):
        print("Updating connections...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (s1:Stop)-[c:CONNECTS_TO]->(s2:Stop)
                SET c.combined_risk = (s1.risk_score + s2.risk_score) / 2,
                    c.risk_adjusted_cost = c.distance_meters *
                        (1 + (s1.risk_score + s2.risk_score) / 2)

                RETURN count(c) AS conexoes_atualizadas
            """)

            record = result.single()
            print(f"{record['conexoes_atualizadas']} connections updated")

            return True

    def update_route_metrics(self):
        print("Updating routes...")

        with self.driver.session() as session:
            # avg_risk_score da rota é a média do risk_score_normalized (0-100)
            # das paradas que ela atende — mesma escala usada no resto do app.
            # high_risk_stops conta paradas classificadas 'Alto' (top 33% do ranking)
            # em vez de threshold hardcoded, para bater com a classificação de paradas.
            result = session.run("""
                MATCH (r:Route)-[:SERVES]->(s:Stop)
                WITH r,
                     count(s) AS total_stops,
                     avg(coalesce(s.risk_score_normalized, 0)) AS avg_risk,
                     count(CASE WHEN s.risk_level = 'Alto' THEN 1 END) AS high_risk

                SET r.total_stops = total_stops,
                    r.avg_risk_score = avg_risk,
                    r.high_risk_stops = high_risk

                RETURN count(r) AS rotas_atualizadas
            """)

            record = result.single()
            print(f"{record['rotas_atualizadas']} routes updated")

            return True

    def close(self):
        self.driver.close()

    def run(self):
        print("Metrics Calculator\n")

        try:
            self.calculate_risk_scores()
            self.update_connection_costs()
            self.update_route_metrics()

            print("\nMetrics updated successfully")
            return True

        except Exception as e:
            print(f"\nCalculation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    calc = MetricsCalculator()
    success = calc.run()
    sys.exit(0 if success else 1)
