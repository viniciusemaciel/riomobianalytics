#!/usr/bin/env python3
"""
Calcula o risco preditivo (XGBoost) e o risco total combinado.

Fluxo:
1. Carrega modelo XGBoost, scaler e metadata de artifacts/
2. Obtém features estáticas do Neo4j (lat, lon, num_rotas_servindo, pagerank)
3. Calcula features de lag (3m/6m/12m) dos chamados por stop via Neo4j
4. Gera features temporais (ano, mes_sin, mes_cos) para o mês corrente
5. Prediz risk_score_tiroteio com XGBoost
6. Calcula risk_score_total = (0.6 * atual + 1.4 * tiroteio) / 2
7. Normaliza 0–100, classifica em tercis (Alto / Médio / Baixo)
8. Escreve no Neo4j + atualiza conexões e rotas
"""

import json
import math
import sys
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

import joblib
import numpy as np
import pandas as pd
from neo4j import GraphDatabase

import config

# ---------------------------------------------------------------------------
# Pesos da fórmula de risco combinado
# ---------------------------------------------------------------------------
PESO_ATUAL = 0.6
PESO_TIROTEIO = 1.4


class RiskPredictor:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )

    # ------------------------------------------------------------------
    # Carregamento de artefatos
    # ------------------------------------------------------------------

    def load_artifacts(self):
        """Carrega modelo XGBoost, StandardScaler e metadata."""
        print("Carregando artefatos do modelo…")
        self.model = joblib.load("artifacts/xgb_model.joblib")
        self.scaler = joblib.load("artifacts/scaler.joblib")

        with open("artifacts/metadata.json", "r") as f:
            self.metadata = json.load(f)

        self.feature_names = self.metadata["features"]
        print(f"  {len(self.feature_names)} features: {', '.join(self.feature_names[:6])}…")
        print(f"  Período de treino: {self.metadata['train_period']}")

    # ------------------------------------------------------------------
    # Determinação da janela de features
    # ------------------------------------------------------------------

    def _compute_date_windows(self):
        """
        Define as janelas de lag com base no mês corrente.

        Para o mês M (ex: agosto/2026), as janelas usam dados dos meses
        anteriores COMPLETOS (sem incluir M):
          - 3m: [M-3, M)  →  2026-05-01 a 2026-07-31
          - 6m: [M-6, M)  →  2026-02-01 a 2026-07-31
          - 12m: [M-12, M) → 2025-08-01 a 2026-07-31

        ⚠️  A lógica replica o .rolling(window=k).sum().shift(1)
            do notebook de preprocessamento — sem vazamento temporal.
        """
        hoje = date.today()
        # Primeiro dia do mês corrente (ex: 2026-08-01)
        self.mes_corrente_start = date(hoje.year, hoje.month, 1)

        self.ano = hoje.year
        self.mes = hoje.month
        self.mes_sin = math.sin(2 * math.pi * self.mes / 12)
        self.mes_cos = math.cos(2 * math.pi * self.mes / 12)

        # Início de cada janela (usa dateutil para subtração correta de meses)
        self.date_3m_start = self.mes_corrente_start - relativedelta(months=3)
        self.date_6m_start = self.mes_corrente_start - relativedelta(months=6)
        self.date_12m_start = self.mes_corrente_start - relativedelta(months=12)

        print(
            f"\nJanela de features para {self.ano}-{self.mes:02d}:"
            f"\n  3m : [{self.date_3m_start}, {self.mes_corrente_start})"
            f"\n  6m : [{self.date_6m_start}, {self.mes_corrente_start})"
            f"\n  12m: [{self.date_12m_start}, {self.mes_corrente_start})"
        )

    # ------------------------------------------------------------------
    # Extração de features do Neo4j
    # ------------------------------------------------------------------

    def _fetch_features(self):
        """
        Executa UMA query Cypher que retorna todas as features para todos os stops.

        Features extraídas do Neo4j:
          - Estáticas: lat, lon, num_rotas_servindo, pagerank
          - Lags (contagens de chamados nas janelas 3m/6m/12m):
              total, segurança pública, iluminação pública

        Cada contagem aplica: data_abertura >= start AND data_abertura < mes_corrente_start
        """
        query = """
            MATCH (s:Stop)
            OPTIONAL MATCH (rec:Reclamacao)-[:AFFECTS]->(s)
            WHERE date(rec.data_abertura) >= date($date_12m_start)
              AND date(rec.data_abertura) <  date($mes_corrente_start)

            // Counts by service category within each lag window
            WITH s,
                 count(rec) AS total_12m,
                 count(CASE WHEN date(rec.data_abertura) >= date($date_6m_start)  THEN rec END) AS total_6m,
                 count(CASE WHEN date(rec.data_abertura) >= date($date_3m_start)  THEN rec END) AS total_3m,

                 count(CASE WHEN rec.servico = 'Segurança Pública' THEN rec END) AS seg_12m,
                 count(CASE WHEN rec.servico = 'Segurança Pública'
                            AND date(rec.data_abertura) >= date($date_6m_start) THEN rec END) AS seg_6m,
                 count(CASE WHEN rec.servico = 'Segurança Pública'
                            AND date(rec.data_abertura) >= date($date_3m_start) THEN rec END) AS seg_3m,

                 count(CASE WHEN rec.servico = 'Iluminação Pública' THEN rec END) AS ilum_12m,
                 count(CASE WHEN rec.servico = 'Iluminação Pública'
                            AND date(rec.data_abertura) >= date($date_6m_start) THEN rec END) AS ilum_6m,
                 count(CASE WHEN rec.servico = 'Iluminação Pública'
                            AND date(rec.data_abertura) >= date($date_3m_start) THEN rec END) AS ilum_3m

            // Static features + route count + pagerank
            OPTIONAL MATCH (r:Route)-[:SERVES]->(s)
            WITH s, total_3m, total_6m, total_12m,
                 seg_3m, seg_6m, seg_12m,
                 ilum_3m, ilum_6m, ilum_12m,
                 count(DISTINCT r) AS num_rotas

            RETURN s.id                          AS stop_id,
                   s.name                        AS name,
                   s.lat                         AS lat,
                   s.lon                         AS lon,
                   num_rotas                     AS num_rotas_servindo,
                   COALESCE(s.pagerank, 0.0)     AS pagerank,
                   COALESCE(s.risk_score_atual, 0.0) AS risk_score_atual,
                   total_3m,  total_6m,  total_12m,
                   seg_3m,   seg_6m,   seg_12m,
                   ilum_3m,  ilum_6m,  ilum_12m
            ORDER BY s.id
        """

        params = {
            "mes_corrente_start": str(self.mes_corrente_start),
            "date_3m_start": str(self.date_3m_start),
            "date_6m_start": str(self.date_6m_start),
            "date_12m_start": str(self.date_12m_start),
        }

        with self.driver.session() as session:
            result = session.run(query, params)
            records = list(result)

        if not records:
            raise RuntimeError("Nenhum stop encontrado no Neo4j. Rode o pipeline ETL primeiro.")

        self.df = pd.DataFrame([dict(r) for r in records])

        # Alinha os nomes das colunas de lag com os feature_names do modelo
        self.df = self.df.rename(columns={
            "total_3m": "num_reclamacoes_3m",
            "total_6m": "num_reclamacoes_6m",
            "total_12m": "num_reclamacoes_12m",
            "seg_3m": "num_reclamacoes_seguranca_3m",
            "seg_6m": "num_reclamacoes_seguranca_6m",
            "seg_12m": "num_reclamacoes_seguranca_12m",
            "ilum_3m": "num_reclamacoes_iluminacao_3m",
            "ilum_6m": "num_reclamacoes_iluminacao_6m",
            "ilum_12m": "num_reclamacoes_iluminacao_12m",
        })

        print(f"  {len(self.df)} stops carregados do Neo4j")
        print(f"  Chamados nas janelas — total 3m: {self.df['num_reclamacoes_3m'].sum()}, "
              f"6m: {self.df['num_reclamacoes_6m'].sum()}, 12m: {self.df['num_reclamacoes_12m'].sum()}")

    # ------------------------------------------------------------------
    # Montagem da matriz de features e predição
    # ------------------------------------------------------------------

    def _build_feature_matrix(self):
        """
        Constrói a matriz X com as 16 features na ordem exata esperada pelo modelo.

        Transformações (iguais às do notebook de treinamento):
          1. Log1p nas 9 colunas de contagem de chamados
          2. StandardScaler (pré-ajustado) em todas as 16 colunas
        """
        # Colunas de contagem que recebem log1p (índices 4 a 12 do metadata)
        count_cols = [c for c in self.feature_names if c.startswith("num_reclamacoes_")]

        X = self.df.copy()

        # Features temporais
        X["ano"] = self.ano
        X["mes_sin"] = self.mes_sin
        X["mes_cos"] = self.mes_cos

        # Log1p nos contadores (mesma transformação do treino)
        for col in count_cols:
            X[col] = np.log1p(X[col])

        # Garante ordem exata das features
        X = X[self.feature_names]

        # Verifica consistência
        assert X.shape[1] == 16, f"Esperadas 16 features, obtidas {X.shape[1]}"
        assert not X.isna().any().any(), "NaN encontrado na matriz de features"

        self.X_raw = X.copy()

        # StandardScaler (já ajustado no treino)
        X_scaled = self.scaler.transform(X)
        self.X_scaled = X_scaled

        print(f"  Matriz de features: {X_scaled.shape}")

    def _predict(self):
        """Executa o XGBoost e guarda as probabilidades preditas."""
        probas = self.model.predict_proba(self.X_scaled)[:, 1]
        self.df["risk_score_tiroteio"] = probas

        acima_50 = (probas >= 0.5).sum()
        print(f"  Predições concluídas — {acima_50} stops com prob ≥ 0.50")
        print(f"  Prob tiroteio — min: {probas.min():.4f}, "
              f"média: {probas.mean():.4f}, max: {probas.max():.4f}")

    # ------------------------------------------------------------------
    # Risco combinado, normalização e classificação
    # ------------------------------------------------------------------

    def _compute_combined_risk(self):
        """
        Fórmula:
            risk_score_total = (PESO_ATUAL * atual + PESO_TIROTEIO * tiroteio) / 2
        """
        df = self.df

        atual = df["risk_score_atual"].fillna(0.0)
        tiroteio = df["risk_score_tiroteio"]

        df["risk_score_total"] = (PESO_ATUAL * atual + PESO_TIROTEIO * tiroteio) / 2.0

        # Normalização 0–100 (min-max sobre o total combinado)
        tmin = df["risk_score_total"].min()
        tmax = df["risk_score_total"].max()

        if tmax == tmin:
            df["risk_score_normalized"] = 50.0
        else:
            df["risk_score_normalized"] = (
                (df["risk_score_total"] - tmin) / (tmax - tmin) * 100.0
            )

        # Classificação por QUARTIS DOS VALORES (4 faixas do range 0-100).
        # Divide-se o intervalo [min, max] em 4 e cada parada recebe
        # o nível conforme a faixa em que cai. Usamos np.select em vez
        # de df.loc para evitar bugs de copy-on-write.
        scores = df["risk_score_normalized"].values
        lo = scores.min()
        hi = scores.max()

        if hi == lo:
            df["risk_level"] = "Baixo"
        else:
            step = (hi - lo) / 4.0
            # Baixo:       [lo,          lo + step)
            # Médio-Baixo: [lo + step,   lo + 2*step)
            # Médio-Alto:  [lo + 2*step, lo + 3*step)
            # Alto:        [lo + 3*step, hi]
            df["risk_level"] = np.select(
                [
                    scores == 0,                               # zero → sempre Baixo
                    scores >= lo + 3 * step,                   # topo do range → Alto
                    scores >= lo + 2 * step,                   # Médio-Alto
                    scores >= lo + step,                       # Médio-Baixo
                ],
                ["Baixo", "Alto", "Médio-Alto", "Médio-Baixo"],
                default="Baixo",
            )

        dist = df["risk_level"].value_counts()
        print(f"\nRisco Total combinado:")
        print(f"  risk_score_total — min: {tmin:.4f}, média: {df['risk_score_total'].mean():.4f}, max: {tmax:.4f}")
        print(f"  Distribuição — Alto: {dist.get('Alto', 0)}, "
              f"Médio-Alto: {dist.get('Médio-Alto', 0)}, "
              f"Médio-Baixo: {dist.get('Médio-Baixo', 0)}, "
              f"Baixo: {dist.get('Baixo', 0)}")

    # ------------------------------------------------------------------
    # Escrita no Neo4j
    # ------------------------------------------------------------------

    def _write_to_neo4j(self):
        """
        Atualiza cada nó Stop com:
          - risk_score_tiroteio
          - risk_score_total
          - risk_score_normalized (0–100)
          - risk_level (Alto / Médio / Baixo)
          - last_prediction_date
        """
        print("\nEscrevendo scores no Neo4j…")

        with self.driver.session() as session:
            batch = []
            for _, row in self.df.iterrows():
                batch.append({
                    "stop_id": row["stop_id"],
                    "risk_score_tiroteio": float(row["risk_score_tiroteio"]),
                    "risk_score_total": float(row["risk_score_total"]),
                    "risk_score_normalized": float(row["risk_score_normalized"]),
                    "risk_level": row["risk_level"],
                })

            result = session.run(
                """
                UNWIND $batch AS item
                MATCH (s:Stop {id: item.stop_id})
                SET s.risk_score_tiroteio   = item.risk_score_tiroteio,
                    s.risk_score_total      = item.risk_score_total,
                    s.risk_score_normalized = item.risk_score_normalized,
                    s.risk_level            = item.risk_level,
                    s.last_prediction_date  = datetime()
                RETURN count(s) AS updated
                """,
                batch=batch,
            )
            record = result.single()
            print(f"  {record['updated']} stops atualizados no Neo4j")

    def _update_connections(self):
        """Atualiza custos das conexões usando o risco total combinado."""
        print("Atualizando conexões (CONNECTS_TO)…")
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s1:Stop)-[c:CONNECTS_TO]->(s2:Stop)
                WHERE s1.risk_score_total IS NOT NULL
                  AND s2.risk_score_total IS NOT NULL
                SET c.combined_risk = (s1.risk_score_total + s2.risk_score_total) / 2,
                    c.risk_adjusted_cost = c.distance_meters *
                        (1 + (s1.risk_score_total + s2.risk_score_total) / 2)
                RETURN count(c) AS conexoes_atualizadas
            """)
            record = result.single()
            print(f"  {record['conexoes_atualizadas']} conexões atualizadas")

    def _update_routes(self):
        """Atualiza métricas das rotas usando o risco total combinado."""
        print("Atualizando rotas (Route)…")
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:Route)-[:SERVES]->(s:Stop)
                WITH r,
                     count(s) AS total_stops,
                     avg(COALESCE(s.risk_score_normalized, 0)) AS avg_risk,
                     count(CASE WHEN s.risk_level = 'Alto' THEN 1 END) AS high_risk

                SET r.total_stops    = total_stops,
                    r.avg_risk_score = avg_risk,
                    r.high_risk_stops = high_risk

                RETURN count(r) AS rotas_atualizadas
            """)
            record = result.single()
            print(f"  {record['rotas_atualizadas']} rotas atualizadas")

    # ------------------------------------------------------------------
    # Orquestração
    # ------------------------------------------------------------------

    def close(self):
        self.driver.close()

    def run(self):
        print("=" * 60)
        print("Risk Predictor — XGBoost + Risco Combinado")
        print("=" * 60)

        try:
            self.load_artifacts()
            self._compute_date_windows()
            self._fetch_features()
            self._build_feature_matrix()
            self._predict()
            self._compute_combined_risk()
            self._write_to_neo4j()
            self._update_connections()
            self._update_routes()

            print("\n✅ Risco preditivo e combinado calculados com sucesso.")
            return True

        except Exception as e:
            print(f"\n❌ Falha na predição: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    pred = RiskPredictor()
    success = pred.run()
    sys.exit(0 if success else 1)
