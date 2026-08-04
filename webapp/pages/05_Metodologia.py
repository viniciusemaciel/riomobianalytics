import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_page_header, section_title, PAGE_ICON,
)

st.set_page_config(page_title="Metodologia · RioMobiAnalytics",
                   page_icon=PAGE_ICON, layout="wide")

apply_theme()

render_page_header(
    "Metodologia de cálculo de risco",
    "Como o risco total de cada parada é calculado — chamados 1746, modelo preditivo e fórmula combinada",
    icon="∫",
)

# =============================================================================
# 1. PESO SEMÂNTICO (REATIVO)
# =============================================================================
st.divider()
section_title("1. Risco por Chamados (reativo)")

section_title("1.1. Peso semântico por categoria")

st.markdown(
    "Cada reclamação do 1746 pertence a uma **categoria** derivada do campo `tipo` "
    "do CSV. Cada categoria tem um peso fixo que reflete o quanto ela contribui "
    "para o risco de uma parada de ônibus:"
)

pesos_df = pd.DataFrame([
    {"Categoria": "Segurança Pública",     "Peso": 1.5, "Motivação": "Impacto direto na segurança de quem espera na parada"},
    {"Categoria": "Trânsito e Transporte", "Peso": 0.8, "Motivação": "Sinaliza falha de infraestrutura de ponto de ônibus"},
    {"Categoria": "Iluminação Pública",    "Peso": 0.6, "Motivação": "Escuridão facilita crimes e atropelamentos"},
    {"Categoria": "Conservação de Vias",   "Peso": 0.5, "Motivação": "Afeta embarque/desembarque (buracos, mobiliário quebrado)"},
    {"Categoria": "Limpeza Urbana",        "Peso": 0.4, "Motivação": "Degradação do entorno correlaciona com sensação de insegurança"},
    {"Categoria": "Outros",                "Peso": 0.3, "Motivação": "Fallback para tipos residuais"},
])
st.dataframe(pesos_df, use_container_width=True, hide_index=True)

st.info(
    "Uma reclamação de **Segurança Pública** pesa 3.75× mais que uma de **Limpeza "
    "Urbana** no cálculo de risco. Esses pesos são definidos em `config.py` e "
    "podem ser ajustados."
)

st.divider()
section_title("1.2. Vinculação reclamação ↔ parada")

st.markdown(
    "Cada reclamação é atribuída à **parada de ônibus mais próxima** — o CSV "
    "`chamados_v2_com_stops_filtrado.csv` já traz esse vínculo pré-calculado no "
    "campo `stop_id_mais_proximo`. No banco de grafos, isso vira uma aresta "
    "`(Reclamacao)-[:AFFECTS]->(Stop)`, cuja propriedade `risk_contribution` é "
    "**exatamente o peso da categoria** da reclamação."
)

st.divider()
section_title("1.3. Risk score bruto (risk_score_atual)")

st.markdown("Para cada parada, somamos as contribuições de todas as reclamações que a afetam:")
st.latex(r"\text{risk\_sum} = \sum_{r \in \text{reclamações da parada}} \text{peso}(r)")

st.markdown("E depois aplicamos uma **função de saturação** para mapear esse valor para o intervalo [0, 1):")
st.latex(r"\text{risk\_score\_atual} = \frac{\text{risk\_sum}}{\text{risk\_sum} + 10}")

st.markdown(
    "A constante `10` é uma **suavização Bayesiana** — evita que uma única reclamação "
    "de peso alto já dispare score 1.0, e faz o crescimento ser mais rápido em valores "
    "baixos e desacelerar nos altos. Comportamento numérico:"
)

sat_df = pd.DataFrame([
    {"risk_sum": 0,   "risk_score": 0.000, "Interpretação": "Nenhuma reclamação"},
    {"risk_sum": 1,   "risk_score": 0.091, "Interpretação": "1 reclamação leve"},
    {"risk_sum": 5,   "risk_score": 0.333, "Interpretação": "Poucas reclamações"},
    {"risk_sum": 10,  "risk_score": 0.500, "Interpretação": "Ponto de inflexão"},
    {"risk_sum": 20,  "risk_score": 0.667, "Interpretação": "Muitas reclamações"},
    {"risk_sum": 50,  "risk_score": 0.833, "Interpretação": "Concentração alta"},
    {"risk_sum": 100, "risk_score": 0.909, "Interpretação": "Saturando"},
    {"risk_sum": 500, "risk_score": 0.980, "Interpretação": "Teto"},
])
st.dataframe(sat_df, use_container_width=True, hide_index=True)

# =============================================================================
# 2. RISCO DE TIROTEIO (PREDITIVO — ML)
# =============================================================================
st.divider()
section_title("2. Risco de Tiroteio (preditivo — ML)")

st.markdown(
    "Esta é a componente **preditiva** do risco: um modelo de machine learning "
    "que estima a probabilidade de ocorrer um tiroteio num raio de 500 metros "
    "da parada, usando dados históricos do **Fogo Cruzado** e dos chamados 1746."
)

st.divider()
section_title("2.1. Dados de treinamento")

st.markdown(
    "O modelo foi treinado com **385.560 amostras**, cada uma representando uma "
    "combinação (parada, mês) entre janeiro/2021 e dezembro/2025. "
    "A fonte de tiroteios é a API do Fogo Cruzado (ocorrências com vítimas "
    "georreferenciadas). O target é binário: 1 se houve pelo menos um tiroteio "
    "num raio de 500 m da parada naquele mês, 0 caso contrário. "
    "A taxa base é de ~13% dos meses com tiroteio próximo à parada."
)

st.divider()
section_title("2.2. Features do modelo (16 variáveis)")

features_df = pd.DataFrame([
    {"Categoria": "Geográficas",       "Features": "lat, lon"},
    {"Categoria": "Rede",              "Features": "num_rotas_servindo (quantas linhas passam), pagerank (centralidade no grafo)"},
    {"Categoria": "Temporais",         "Features": "ano, mes_sin, mes_cos (codificação cíclica do mês)"},
    {"Categoria": "Chamados — lag 3m", "Features": "Total, Segurança Pública, Iluminação Pública"},
    {"Categoria": "Chamados — lag 6m", "Features": "Total, Segurança Pública, Iluminação Pública"},
    {"Categoria": "Chamados — lag 12m","Features": "Total, Segurança Pública, Iluminação Pública"},
])
st.dataframe(features_df, use_container_width=True, hide_index=True)

st.markdown(
    "As contagens de chamados recebem `log1p` para comprimir a cauda longa "
    "(a diferença entre 0 e 1 reclamação importa mais que entre 100 e 101). "
    "Todas as features são padronizadas com `StandardScaler` ajustado nos "
    "dados de treino (2021–2023)."
)

st.info(
    "As janelas de lag usam apenas meses **anteriores** ao mês-alvo "
    "(`.rolling(k).sum().shift(1)`). Não há vazamento temporal — o modelo "
    "nunca vê dados do futuro."
)

st.divider()
section_title("2.3. Arquitetura e hiperparâmetros")

hiper_df = pd.DataFrame([
    {"Parâmetro": "Algoritmo",               "Valor": "XGBoost (classificador binário)"},
    {"Parâmetro": "Árvores",                 "Valor": "300 (n_estimators)"},
    {"Parâmetro": "Profundidade máxima",     "Valor": "5 (max_depth)"},
    {"Parâmetro": "Taxa de aprendizado",     "Valor": "0.05 (learning_rate)"},
    {"Parâmetro": "Subamostragem",           "Valor": "80% (subsample)"},
    {"Parâmetro": "Balanceamento",           "Valor": "scale_pos_weight = 5.01"},
    {"Parâmetro": "Métrica de otimização",   "Valor": "AUC-ROC"},
])
st.dataframe(hiper_df, use_container_width=True, hide_index=True)

st.divider()
section_title("2.4. Performance")

perf_df = pd.DataFrame([
    {"Métrica": "AUC-ROC",              "Valor": "0.71"},
    {"Métrica": "Acurácia",             "Valor": "0.68"},
    {"Métrica": "Precisão (classe 1)",  "Valor": "0.23"},
    {"Métrica": "Recall (classe 1)",    "Valor": "0.58"},
    {"Métrica": "F1-score",             "Valor": "0.32"},
])
st.dataframe(perf_df, use_container_width=True, hide_index=True)

st.markdown(
    "O AUC-ROC de 0.71 está significativamente acima do aleatório (0.50). "
    "O modelo é adequado para **priorização e scoring**, não para alarmes "
    "de alta precisão. Artefatos em `artifacts/`: `xgb_model.joblib` (768 KB), "
    "`scaler.joblib`, `metadata.json`."
)

st.divider()
section_title("2.5. Importância das features")

st.markdown(
    "O gráfico abaixo mostra quanto cada feature contribuiu para as decisões "
    "do modelo (importância por *gain* — redução média de impureza nas "
    "árvores do XGBoost):"
)

importance_df = pd.DataFrame([
    {"Feature": "lon",                          "Importância": "22.9%"},
    {"Feature": "lat",                          "Importância": "22.5%"},
    {"Feature": "ano",                          "Importância": "10.9%"},
    {"Feature": "mes_sin",                      "Importância":  "8.2%"},
    {"Feature": "mes_cos",                      "Importância":  "8.1%"},
    {"Feature": "num_rotas_servindo",           "Importância":  "5.6%"},
    {"Feature": "pagerank",                     "Importância":  "4.8%"},
    {"Feature": "num_reclamacoes_iluminacao_12m","Importância": "2.8%"},
    {"Feature": "num_reclamacoes_seguranca_12m", "Importância": "2.3%"},
    {"Feature": "num_reclamacoes_12m",          "Importância":  "2.2%"},
    {"Feature": "num_reclamacoes_6m",           "Importância":  "1.9%"},
    {"Feature": "num_reclamacoes_iluminacao_3m","Importância":  "1.9%"},
    {"Feature": "num_reclamacoes_iluminacao_6m","Importância":  "1.8%"},
    {"Feature": "num_reclamacoes_seguranca_6m", "Importância":  "1.7%"},
    {"Feature": "num_reclamacoes_seguranca_3m", "Importância":  "1.3%"},
    {"Feature": "num_reclamacoes_3m",           "Importância":  "1.1%"},
])
st.dataframe(importance_df, use_container_width=True, hide_index=True)

st.markdown(
    "**Leitura por grupo:**\n"
    "- **Geografia (lat + lon): ~45%** — o preditor mais forte. Onde a parada "
    "está é o principal determinante do risco de tiroteio.\n"
    "- **Tempo (ano + mês cíclico): ~27%** — a sazonalidade importa: há meses "
    "e épocas do ano consistentemente mais violentos.\n"
    "- **Chamados 1746 (9 lags): ~17%** — as reclamações adicionam sinal, "
    "especialmente as janelas mais longas (12 meses). Iluminação e Segurança "
    "são as categorias mais informativas.\n"
    "- **Rede (rotas + pagerank): ~10%** — paradas com mais linhas e mais "
    "centrais na rede têm perfil de risco diferente."
)

st.info(
    "Isso explica por que o modelo funciona mesmo com poucos chamados recentes: "
    "a geografia e a sazonalidade já carregam a maior parte do sinal preditivo. "
    "Os chamados refinam a previsão, especialmente quando há histórico de "
    "iluminação precária ou incidentes de segurança nos últimos 12 meses."
)

# =============================================================================
# 3. RISCO TOTAL (COMBINADO)
# =============================================================================
st.divider()
section_title("3. Risco Total (combinado)")

st.markdown(
    "As duas componentes anteriores são fundidas em uma **métrica única** "
    "que pondera o presente (chamados) e o futuro (predição de tiroteio):"
)

st.latex(
    r"\text{risk\_score\_total} = "
    r"\frac{0.6 \times \text{risk\_score\_atual} + "
    r"1.4 \times \text{risk\_score\_tiroteio}}{2}"
)

st.markdown(
    "- **Peso 0.6 no reativo**: os chamados são evidência concreta, mas "
    "reativa — o problema já aconteceu\n"
    "- **Peso 1.4 no preditivo**: maior porque é a informação nova, "
    "*forward-looking*, que antecipa onde o risco pode surgir antes "
    "dos chamados aparecerem\n"
    "- **Divisor 2**: mantém o score no intervalo [0, 1]"
)

st.divider()
section_title("3.1. Normalização (0–100)")

st.markdown(
    "Aplicamos **normalização min-max** sobre o `risk_score_total` de todas as "
    "paradas, produzindo o `risk_score_normalized`:"
)
st.latex(
    r"\text{risk\_score\_normalized} = "
    r"\frac{\text{risk\_score\_total} - \text{min}}{\text{max} - \text{min}} \times 100"
)
st.markdown(
    "Isso rescala o score para o intervalo **[0, 100]**, tornando comparações entre "
    "paradas mais legíveis. **É a escala usada em todo o app.**"
)

st.divider()
section_title("3.2. Classificação em 4 níveis (quartis do range)")

st.markdown(
    "Divide-se o intervalo `[min_score, max_score]` em **4 faixas iguais**. "
    "Cada parada recebe o nível conforme a faixa em que seu score cai:"
)
st.latex(r"\text{faixa} = \frac{\text{max\_score} - \text{min\_score}}{4}")
st.markdown(
    "- **Alto** — 4º quartil: `[min + 3×faixa, max]`\n"
    "- **Médio-Alto** — 3º quartil: `[min + 2×faixa, min + 3×faixa)`\n"
    "- **Médio-Baixo** — 2º quartil: `[min + faixa, min + 2×faixa)`\n"
    "- **Baixo** — 1º quartil: `[min, min + faixa)`"
)
st.info(
    "O número de paradas em cada nível **varia** conforme a distribuição "
    "real dos scores. Se a cidade piora, mais paradas sobem para Alto e "
    "Médio-Alto. Se melhora, mais paradas descem. Diferente de um ranking "
    "que força sempre a mesma quantidade em cada nível."
)

# =============================================================================
# 4. MÉTRICAS DE ROTA E CONEXÕES
# =============================================================================
st.divider()
section_title("4. Métricas de rota")

st.markdown(
    "Para cada rota de ônibus, olhamos as paradas que ela atende (`:SERVES`) e "
    "agregamos:"
)
st.markdown(
    "- `avg_risk_score` = média aritmética do `risk_score_normalized` (0-100) "
    "de todas as paradas da rota\n"
    "- `high_risk_stops` = quantidade de paradas classificadas como `Alto` "
    "que a rota atende"
)
st.info(
    "Uma rota como a 584 com `avg_risk_score = 31.5` e 52 de 69 paradas em nível "
    "Alto significa que ela **passa em zonas de alta densidade de reclamações**, "
    "mesmo que sua média absoluta pareça modesta (lembre: a normalização é relativa)."
)

st.divider()
section_title("5. Custo ajustado por risco (arestas)")

st.markdown(
    "Cada conexão entre paradas (`:CONNECTS_TO`) recebe um custo que combina "
    "distância física com o risco total médio das duas paradas:"
)
st.latex(r"\text{combined\_risk} = \frac{\text{risk\_score\_total}(A) + \text{risk\_score\_total}(B)}{2}")
st.latex(r"\text{risk\_adjusted\_cost} = \text{distance\_meters} \times (1 + \text{combined\_risk})")
st.markdown(
    "Usado quando se quer calcular rotas **mais seguras** entre duas paradas — "
    "o algoritmo de menor caminho penaliza trechos com risco alto."
)

# =============================================================================
# 6. RESUMO VISUAL DO PIPELINE
# =============================================================================
st.divider()
section_title("6. Resumo visual do pipeline completo")

st.markdown("""
```
[CSV 1746 curado] ─┐                           [Fogo Cruzado API]
                   │ peso da categoria                │
                   ▼                                  │
       ┌─── Reclamação ───┐                          │
       │  risk_contribution │                         │
       └────────┬──────────┘                          │
                │  AFFECTS                            │
                ▼                                     ▼
        ┌────────────────── Parada ───────────────────┐
        │ risk_sum          ← soma dos pesos          │
        │ risk_score_atual  ← risk_sum/(risk_sum+10)  │  [0, 1)
        │                                                  │
        │ risk_score_tiroteio ← XGBoost(16 features)  │  [0, 1]
        │   features: lat, lon, rotas, pagerank,      │
        │   lags 3m/6m/12m de chamados,               │
        │   ano, mes_sin, mes_cos                     │
        │                                                  │
        │ risk_score_total ← (0.6×atual + 1.4×tiro)/2 │  [0, 1]
        │ risk_score_normalized ← min-max → [0, 100]  │
        │ risk_level ← 4 níveis por quartis do range  │
        └────────┬───────┬────────────────────────────┘
                 │       │
           SERVES│       │ CONNECTS_TO
                 ▼       ▼
        ┌──── Rota ──┐  ┌─── Conexão ───────────────┐
        │ avg_risk    │  │ combined_risk              │
        │ high_risk   │  │ risk_adjusted_cost         │
        └─────────────┘  └────────────────────────────┘
```
""")

st.divider()
st.caption(
    "Implementação: `scripts/05_calculate_metrics.py` (risco reativo), "
    "`scripts/07_predict_risk.py` (modelo ML + combinação), "
    "`scripts/04_sync_1746_to_neo4j.py` (atribuição reclamação↔parada), "
    "`config.py` (pesos). "
    "Modelo: `artifacts/xgb_model.joblib`, treinado em `modelo-treinamento.ipynb`."
)

render_query_console()
