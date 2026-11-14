---
id: 01_projeto
titulo: O que é o RioMobiAnalytics
tipo: interno
origem: repositório riomobianalytics (README, config.py, webapp/)
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: dados de 2020 a 2025
atualizado_em: 2026-11-14
tags: [projeto, objetivo, escopo, páginas, app, paradas de ônibus, Rio de Janeiro]
---

## O que é o RioMobiAnalytics

O RioMobiAnalytics é um projeto de ciência de dados (trabalho de pós-graduação) que compara o risco de tiroteio no entorno das paradas de ônibus do Rio de Janeiro. Ele liga três fontes públicas: a rede de ônibus (GTFS), as reclamações de serviços públicos da Central 1746 da Prefeitura e os registros de tiroteio do Instituto Fogo Cruzado.

O resultado é um **índice de risco de 0 a 100 para cada parada**, dividido em quatro níveis (Baixo, Médio-Baixo, Médio-Alto e Alto). O índice combina duas partes: o peso das reclamações próximas (a parte "reativa") e a previsão de um modelo de aprendizado de máquina (XGBoost) para tiroteio a até 500 m da parada (a parte "preditiva"). A rede de ônibus é modelada como um grafo no Neo4j, o que permite medir a importância de cada parada na rede e calcular métricas por linha.

O app é público, feito em Streamlit, e só **lê** os dados: toda a carga e o cálculo acontecem antes, em scripts.

## Para que serve e para quem

O índice serve para **comparar paradas entre si** e apontar onde reclamações e histórico de tiroteio indicam maior atenção. Usos pensados: exploração por quem estuda mobilidade e segurança urbana, apoio a discussões de planejamento, comunicação de dados e ensino.

O índice não foi pensado para orientar a decisão individual de "posso passar por aqui". Ele é relativo (compara as paradas atuais), não é probabilidade e não prevê um evento específico. O arquivo de uso responsável (11) detalha isso.

## O que o projeto não é

- Não é uma estatística oficial de criminalidade. Os registros oficiais de crime no estado vêm do Instituto de Segurança Pública (ISP-RJ); o projeto não usa dados do ISP.
- Não mede crimes contra quem está no ônibus. Tiroteio no entorno de uma parada não é um evento na parada.
- Não prevê quando ou onde um tiroteio específico vai acontecer.
- Não aponta culpados nem atribui violência a comunidades, bairros ou grupos.
- Não usa dados pessoais: as reclamações do 1746 entram só com categoria, data e localização; os tiroteios entram como ocorrências georreferenciadas.

## Páginas do aplicativo

A navegação fica no topo, nesta ordem:

- **Início**: apresenta o projeto, números gerais (paradas, reclamações ligadas, AUC do modelo na validação de 2024) e leva às formas de explorar.
- **Mapa**: tela principal. Mostra as paradas coloridas pelo índice, com três camadas (Índice de risco, Tiroteio, Reclamações), busca por nome de parada, filtros (nível de risco, linha, mínimo de reclamações) e painel da parada selecionada.
- **Rede**: a partir de uma parada de origem, mostra as paradas ligadas em anéis, ordenadas pela distância na rede (em número de paradas).
- **Assistente**: chat em português que responde perguntas com dados do projeto, citando a fonte de cada número.
- **Risco**: métricas do modelo na validação, consulta técnica de uma parada e um simulador de cenários.
- **Metodologia**: explicação do cálculo, limites e glossário.

O arquivo 14 explica como usar cada página (camadas, filtros, painel da parada, simulador).

## Período e fontes dos dados

Os dados de tiroteio e de reclamações cobrem **2020 a 2025**: os registros do Fogo Cruzado vão de 31/12/2019 (noite, horário local) a 31/12/2025, e as reclamações do 1746 vão de 02/01/2020 a 12/12/2025. O modelo usa meses de janeiro de 2021 a dezembro de 2025.

Isso significa que "o último ano" nos dados é 2025. O assistente deve sempre citar o período, porque a base não chega até hoje.
