---
id: 09_arquitetura
titulo: Arquitetura, pipeline de dados e implantação
tipo: interno
origem: README, scripts de carga, notebooks e paper do projeto
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: estrutura do projeto, dados de 2020 a 2025
atualizado_em: 2026-11-14
tags: [arquitetura, pipeline, Neo4j, MongoDB, Streamlit, grafo, notebooks, como foi construído]
---

## Visão geral: de onde os dados vêm até o mapa

O projeto tem três etapas. Primeiro, as três fontes (rede de ônibus GTFS, reclamações da Central 1746 e tiroteios do Fogo Cruzado) são tratadas em notebooks e carregadas por scripts. Depois, o grafo da rede e as métricas ficam no **Neo4j** e as reclamações brutas no **MongoDB**. Por fim, o aplicativo **Streamlit** lê esses dados e os mostra no mapa, na rede, na página de risco e no assistente.

O aplicativo só **lê**: nunca escreve nos bancos. Isso o mantém rápido e evita que um uso altere dados. Em contrapartida, os números só mudam quando o processamento é refeito.

## As etapas do processamento

1. **Rede de ônibus:** paradas, linhas e viagens do GTFS entram no grafo, com as ligações entre paradas consecutivas (`CONNECTS_TO`) e entre linhas e paradas (`SERVES`).
2. **Reclamações:** os 14 tipos de chamado do 1746 escolhidos pelo projeto são guardados no MongoDB e ligados à parada mais próxima no grafo (`AFFECTS`).
3. **Risco reativo:** pesos por categoria resumem as reclamações de cada parada (arquivo 05).
4. **Importância na rede:** o PageRank de cada parada é calculado a partir das ligações do grafo.
5. **Risco preditivo e índice:** o modelo XGBoost estima a chance de tiroteio a 500 m, o resultado é combinado com o risco reativo, normalizado de 0 a 100 e classificado em quatro níveis (arquivos 05 e 06).
6. **Bairros e tiroteios:** cada parada e cada ocorrência do Fogo Cruzado recebe o bairro oficial, e os tiroteios entram no grafo (arquivo 08).

## Notebooks e modelo treinado

Os notebooks documentam a análise: filtragem do GTFS e do 1746, exploração do Fogo Cruzado, construção das variáveis e treino do modelo. O treino gera o modelo, o normalizador, os metadados e as previsões de validação, usados no cálculo do índice e na página Risco.

## Por que Neo4j e MongoDB

O Neo4j guarda o que é rede: paradas, linhas e ligações, o que facilita consultar vizinhanças e calcular PageRank. O MongoDB guarda as reclamações brutas, que são texto e campos variados. Os dois são serviços gratuitos de nuvem; o plano gratuito do Neo4j não inclui a biblioteca de ciência de grafos, por isso o PageRank foi calculado com a biblioteca `networkx`.
