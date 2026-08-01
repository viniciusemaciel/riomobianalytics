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
    "Como o risco de cada parada e cada rota é calculado, ponta a ponta",
    icon="∫",
)

st.divider()
section_title("1. Peso semântico por categoria")

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
section_title("2. Vinculação reclamação ↔ parada")

st.markdown(
    "Cada reclamação é atribuída à **parada de ônibus mais próxima** — o CSV "
    "`chamados_v2_com_stops_filtrado.csv` já traz esse vínculo pré-calculado no "
    "campo `stop_id_mais_proximo`. No banco de grafos, isso vira uma aresta "
    "`(Reclamacao)-[:AFFECTS]->(Stop)`, cuja propriedade `risk_contribution` é "
    "**exatamente o peso da categoria** da reclamação."
)

st.divider()
section_title("3. Risk score bruto da parada")

st.markdown("Para cada parada, somamos as contribuições de todas as reclamações que a afetam:")
st.latex(r"\text{risk\_sum} = \sum_{r \in \text{reclamações da parada}} \text{peso}(r)")

st.markdown("E depois aplicamos uma **função de saturação** para mapear esse valor para o intervalo [0, 1):")
st.latex(r"\text{risk\_score} = \frac{\text{risk\_sum}}{\text{risk\_sum} + 10}")

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

st.warning(
    "Custo dessa saturação: paradas com muitas reclamações **saturam** perto de 1.0. "
    "A diferença entre uma parada com 50 e outra com 500 reclamações fica pequena "
    "no score bruto. Por isso a etapa 4 é importante."
)

st.divider()
section_title("4. Normalização (0-100)")

st.markdown(
    "Aplicamos **normalização min-max** sobre o `risk_score` bruto de todas as "
    "paradas, produzindo o `risk_score_normalized`:"
)
st.latex(
    r"\text{risk\_score\_normalized} = "
    r"\frac{\text{risk\_score} - \text{min}}{\text{max} - \text{min}} \times 100"
)
st.markdown(
    "Isso rescala o score para o intervalo **[0, 100]**, tornando comparações entre "
    "paradas mais legíveis. **É a escala usada em todo o app.** Note que essa "
    "normalização é **relativa à rodada atual** — o mesmo `risk_sum` pode gerar "
    "`risk_score_normalized` diferente se o max/min mudar."
)

st.divider()
section_title("5. Classificação Alto / Médio / Baixo")

st.markdown(
    "Cada parada é classificada por **ranking**, não por threshold fixo, sobre "
    "`risk_score_normalized`:"
)
st.markdown("""
- **Alto** — top 33% das paradas que têm risco > 0
- **Médio** — 33% intermediário
- **Baixo** — 33% inferior (inclui paradas sem reclamação, com score 0)
""")
st.info(
    "Consequência: em uma cidade com pouquíssimas reclamações, uma parada com "
    "`risk_score_normalized = 20` ainda pode ser classificada **Alto** se estiver "
    "no top 33%. **Não é um valor absoluto, é uma posição relativa.**"
)

st.divider()
section_title("6. Métricas de rota")

st.markdown(
    "Para cada rota de ônibus, olhamos as paradas que ela atende (`:SERVES`) e "
    "agregamos:"
)
st.markdown("""
- **`avg_risk_score`** = média aritmética do `risk_score_normalized` (0-100) de todas as paradas da rota
- **`high_risk_stops`** = quantidade de paradas classificadas como `Alto` que a rota atende
""")
st.info(
    "Uma rota como a 584 com `avg_risk_score = 31.5` e 52 de 69 paradas em nível "
    "Alto significa que ela **passa em zonas de alta densidade de reclamações**, "
    "mesmo que sua média absoluta pareça modesta (lembre: a normalização é relativa)."
)

st.divider()
section_title("7. Custo ajustado por risco (arestas)")

st.markdown(
    "Cada conexão entre paradas (`:CONNECTS_TO`) recebe um custo que combina "
    "distância física com o risco médio das duas paradas:"
)
st.latex(r"\text{combined\_risk} = \frac{\text{risk\_score}(A) + \text{risk\_score}(B)}{2}")
st.latex(r"\text{risk\_adjusted\_cost} = \text{distance\_meters} \times (1 + \text{combined\_risk})")
st.markdown(
    "Usado quando se quer calcular rotas **mais seguras** entre duas paradas — "
    "o algoritmo de menor caminho penaliza trechos com risco alto. Atualmente "
    "essa métrica é populada mas ainda não é usada pelo webapp."
)

st.divider()
section_title("Resumo visual do pipeline")

st.markdown("""
```
[CSV 1746 curado] ─┐
                   │ peso da categoria (config.py)
                   ▼
       ┌─── Reclamação ───┐
       │  risk_contribution │
       └────────┬──────────┘
                │  AFFECTS
                ▼
        ┌──── Parada ────┐
        │ risk_sum       │  ← soma dos pesos
        │ risk_score     │  ← risk_sum / (risk_sum + 10)   [0, 1)
        │ risk_score_normalized │  ← (score − min) / (max − min) × 100   [0, 100]
        │ risk_level     │  ← Alto / Médio / Baixo (ranking top-33/mid-33/bot-33)
        └────────┬───────┘
                 │  SERVES
                 ▼
        ┌──── Rota ────┐
        │ avg_risk_score = média(risk_score_normalized das paradas)
        │ high_risk_stops = count(paradas com risk_level = 'Alto')
        └───────────────┘
```
""")

st.divider()
st.caption(
    "Implementação: `scripts/05_calculate_metrics.py` (cálculo), "
    "`scripts/04_sync_1746_to_neo4j.py` (atribuição reclamação↔parada), "
    "`config.py` (pesos)."
)

render_query_console()
