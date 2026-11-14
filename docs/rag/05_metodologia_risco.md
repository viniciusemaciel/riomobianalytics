---
id: 05_metodologia_risco
titulo: Metodologia — como o índice de risco é calculado
tipo: interno
origem: scripts 05 e 07, config.py, webapp/views/metodologia.py
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: 2020–2025
atualizado_em: 2026-11-14
tags: [índice de risco, risk_score_normalized, níveis, normalização, reclamações, tiroteio, fórmula]
---

## Visão geral: duas partes combinadas em um índice de 0 a 100

O índice de risco de cada parada (`risk_score_normalized`) vem de duas partes. A **parte reativa** (`risk_score_atual`) resume as reclamações do 1746 ligadas à parada. A **parte preditiva** (`risk_score_tiroteio`) é a saída de um modelo XGBoost que estima a chance de haver tiroteio a até 500 m da parada no mês. As duas se combinam, e o resultado é reescalado de 0 a 100 entre todas as paradas.

Os dados de entrada são o GTFS (paradas e rede), o 1746 e o Fogo Cruzado. O índice é **relativo**: compara as paradas atuais entre si. Não é probabilidade e nunca deve ser escrito com "%".

## Parte reativa: peso das reclamações

Cada reclamação tem o peso da sua categoria (Segurança Pública 1,5; Trânsito e Transporte 0,8; Iluminação 0,6; Conservação de Vias 0,5; Limpeza Urbana 0,4; Outros 0,3). Para cada parada, soma-se o peso de todas as reclamações ligadas a ela (`risk_sum`) e aplica-se uma saturação:

`risk_score_atual = risk_sum / (risk_sum + 10)`

O 10 evita que uma única reclamação dispare o valor e faz o crescimento desacelerar: `risk_sum` 1,5 dá cerca de 0,13; 10 dá 0,50; 40 dá 0,80. O resultado fica sempre entre 0 e 1, e é 0 para quem não tem reclamação.

## Parte preditiva: modelo de tiroteio a 500 m

O `risk_score_tiroteio` (guardado entre 0 e 1; o app às vezes mostra de 0 a 100) é a probabilidade bruta que o XGBoost devolve para "haverá pelo menos um tiroteio a até 500 m desta parada neste mês". Não é calibrada: o modelo foi treinado dando mais peso à classe rara, o que desloca os valores para cima. Serve para ordenar paradas, não para dizer "a chance é de tanto". O arquivo 06 detalha o modelo.

## Combinação e normalização

`risk_score_total = (0,6 × risk_score_atual + 1,4 × risk_score_tiroteio) / 2`

O peso maior no tiroteio (1,4 contra 0,6) reflete a escolha de dar mais importância à informação preditiva do que ao registro de reclamações; o divisor 2 mantém o resultado entre 0 e 1. Depois aplica-se a normalização mínimo-máximo sobre todas as paradas:

`risk_score_normalized = (total − mínimo) / (máximo − mínimo) × 100`

Por isso a parada de maior risco sempre tem 100 e a de menor tem 0, mesmo que o risco geral da cidade mude. Compare índices dentro do mesmo cálculo, nunca entre cálculos de datas diferentes.

## Os quatro níveis

O intervalo entre o menor e o maior valor é dividido em **4 faixas de mesma largura** (aproximadamente 0–25, 25–50, 50–75 e 75–100 do índice): Baixo, Médio-Baixo, Médio-Alto e Alto. A parada cai na faixa do seu valor. Como as faixas têm a mesma largura (e não o mesmo número de paradas), cada nível pode ter quantidades bem diferentes de paradas; a ferramenta de estatísticas mostra a distribuição atual. Mudanças em pesos ou no modelo mudam os níveis.

## A que data o índice se refere

O índice guardado no banco é o da última execução do script de previsão, e a data dela fica em `Stop.last_prediction_date`. As variáveis do modelo usam as reclamações dos 3, 6 e 12 meses anteriores a essa data e o mês do ano (sazonalidade). Como os dados de reclamações e tiroteios vão até dezembro de 2025, o índice descreve o entorno das paradas com base no histórico de 2020 a 2025, não em ocorrências de hoje.

## Métricas de rota e custo ajustado por risco

Para cada linha, `avg_risk_score` é a média do índice das paradas que ela atende e `high_risk_stops` conta as paradas de nível Alto. Cada ligação entre paradas recebe `combined_risk` (média dos totais das duas) e o custo `risk_adjusted_cost = distância em metros × (1 + combined_risk)`, previsto para buscar caminhos que evitem trechos de maior risco. O arquivo 07 explica o grafo.
