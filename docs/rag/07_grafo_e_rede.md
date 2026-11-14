---
id: 07_grafo_e_rede
titulo: O grafo no Neo4j e a rede de ônibus
tipo: interno
origem: scripts 02, 04, 05, 06 e 10; webapp/rag/prompts.py; webapp/views/rede.py
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: rede GTFS filtrada; reclamações e tiroteios 2020–2025
atualizado_em: 2026-11-14
tags: [Neo4j, grafo, Stop, Route, CONNECTS_TO, SERVES, AFFECTS, PageRank, rede]
---

## Por que um grafo e o que há nele

A rede de ônibus é naturalmente um grafo: paradas são pontos e as linhas ligam um ponto ao outro. O projeto guarda isso no **Neo4j** (Aura Free), o que permite perguntar "quais paradas estão a 2 saltos desta?" ou "quais linhas passam por mais paradas de nível Alto?" sem montar junções complicadas. Os dados brutos das reclamações ficam à parte, no **MongoDB**.

**Nós**: `Stop` (parada, com bairro oficial, índice, nível, PageRank e contagens), `Route` (linha, com índice médio), `Trip` (a viagem representativa), `Reclamacao`, `Categoria` e `Tiroteio`.

## Relações principais

- `(Route)-[:SERVES]->(Stop)`: a linha atende a parada.
- `(Stop)-[:CONNECTS_TO]->(Stop)`: duas paradas seguidas numa viagem. Tem distância em metros, `combined_risk` e `risk_adjusted_cost`. São 6.974 pares dirigidos distintos.
- `(Reclamacao)-[:AFFECTS]->(Stop)`: a reclamação mais próxima da parada, com a distância.
- `(Reclamacao)-[:HAS_TYPE]->(Categoria)`: categoria do chamado.
- `Trip` liga-se à linha (`BELONGS_TO`) e às paradas (`HAS_STOP`); o assistente não consulta esses horários.
- Os nós `Tiroteio` **não têm relações**: a proximidade é calculada na hora por distância geográfica (arquivo 08).

## PageRank: o que é aqui

O PageRank mede **quão central uma parada é na rede**: paradas para onde muitos caminhos convergem, vindos de paradas também importantes, recebem valor maior. Foi calculado fora do Neo4j com a biblioteca `networkx` (o plugin de grafos não existe no Aura Free), sobre o grafo dirigido das ligações `CONNECTS_TO`, com fator de amortecimento 0,85. O valor é uma variável do modelo. Alto PageRank não significa perigo: significa posição central na rede.

## Métricas por linha e custo por risco

Cada linha agrega as paradas que atende: `avg_risk_score` (média do índice) e `high_risk_stops` (quantas são de nível Alto). Uma linha longa que cruza muitas áreas de nível Alto terá muitas paradas de risco alto mesmo com média modesta, porque a média é relativa. O `risk_adjusted_cost` das ligações é a distância multiplicada por (1 + risco combinado) e existe para permitir, no futuro, caminhos mais curtos que evitem trechos de maior risco.

## A página Rede

A página **Rede** parte de uma parada de origem e distribui as paradas ligadas em **anéis**, cada anel sendo a distância em número de paradas na rede (busca em largura). A cor de cada parada é o nível do índice. Serve para ver até onde a rede leva a partir de um ponto e como o risco se distribui em volta, e não para calcular tempo de viagem.
