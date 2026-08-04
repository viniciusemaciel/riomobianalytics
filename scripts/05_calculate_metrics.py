#!/usr/bin/env python3
"""
Calcula o risco reativo (por chamados) de cada parada de ônibus.

Este script agrega os chamados abertos vinculados a cada Stop no Neo4j
e salva a propriedade `risk_score_atual` (0–1). A normalização final,
classificação em tercis e o risco combinado com o modelo preditivo ficam
no script `07_predict_risk.py`.
"""

from neo4j import GraphDatabase
import config
import sys


class MetricsCalculator:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )

    def calculate_risk_scores(self):
        print("Calculating risk scores (reativo → risk_score_atual)…")

        with self.driver.session() as session:
            # Agrega chamados com status Aberto / Em Atendimento e calcula
            # o score bruto com a mesma fórmula de suavização original:
            #   risk_score_atual = risk_sum / (risk_sum + 10.0)
            result = session.run("""
                MATCH (s:Stop)<-[a:AFFECTS]-(rec:Reclamacao)
                WHERE rec.status IN ['Aberto', 'Em Atendimento']

                WITH s,
                     count(rec) AS total_reclamacoes,
                     count(CASE WHEN rec.status = 'Aberto' THEN 1 END) AS abertas,
                     sum(a.risk_contribution) AS risk_sum

                SET s.total_reclamacoes = total_reclamacoes,
                    s.reclamacoes_abertas = abertas,
                    s.risk_score_atual = risk_sum / (risk_sum + 10.0),
                    s.last_risk_update = datetime()

                RETURN count(s) AS paradas_atualizadas,
                       avg(s.risk_score_atual) AS avg_risk,
                       max(s.risk_score_atual) AS max_risk,
                       min(s.risk_score_atual) AS min_risk
            """)

            record = result.single()
            if record:
                print(f"  {record['paradas_atualizadas']} stops atualizados")
                if record["avg_risk"] is not None:
                    print(
                        f"  risk_score_atual — avg: {record['avg_risk']:.3f}, "
                        f"max: {record['max_risk']:.3f}, "
                        f"min: {record['min_risk']:.3f}"
                    )
            else:
                print("  Nenhum stop atualizado (sem chamados abertos?).")

        return True

    def close(self):
        self.driver.close()

    def run(self):
        print("Metrics Calculator (risco reativo)\n")

        try:
            self.calculate_risk_scores()
            print("\nRisco reativo atualizado com sucesso.")
            print("⚠️  Lembre-se de rodar 07_predict_risk.py para gerar o risco combinado.")
            return True

        except Exception as e:
            print(f"\nFalha no cálculo: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    calc = MetricsCalculator()
    success = calc.run()
    sys.exit(0 if success else 1)
