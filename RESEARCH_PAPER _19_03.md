# RioMobiAnalytics: Sistema de Análise de Risco em Rede de Transporte Público Integrado com Dados de Reclamações Cidadãs e Modelo Preditivo de Tiroteios

## RESUMO

Este trabalho apresenta RioMobiAnalytics, um sistema de análise que integra dados de GTFS (General Transit Feed Specification) da rede de transporte público do Rio de Janeiro com dados de reclamações cidadãs (1746) e ocorrências de tiroteios (Fogo Cruzado) para identificar paradas de trânsito de alto risco. O sistema utiliza uma arquitetura híbrida de bancos de dados (MongoDB para dados geoespaciais e Neo4j para relacionamentos em grafo) para modelar a topologia da rede de transporte e calcular métricas de risco que combinam uma componente reativa (chamados 1746) com uma componente preditiva (modelo XGBoost de probabilidade de tiroteio). Um webapp interativo em Streamlit disponibiliza dashboards, mapas e um playground do modelo para exploração dos resultados. Os resultados demonstram a viabilidade de integração de múltiplas fontes de dados para análise de vulnerabilidades em infraestrutura de transportes.

**Palavras-chave:** Análise de Transportes, Bancos de Dados em Grafo, GTFS, Análise de Risco, Reclamações Cidadãs, Neo4j, MongoDB, XGBoost, Modelo Preditivo.

---

## 1. INTRODUÇÃO

### 1.1 Contextualização

O Rio de Janeiro é uma metrópole com aproximadamente 6,7 milhões de habitantes que dependem significativamente de sistemas de transporte público para mobilidade urbana. A rede de transporte da cidade compreende aproximadamente 7.665 paradas de ônibus, 511 linhas de transporte e mais de 15 mil viagens diárias. Este sistema complexo de transportes é essencial para a conectividade urbana, mas enfrenta desafios significativos relacionados à segurança, qualidade do serviço e vulnerabilidades operacionais.

Paralelamente, a prefeitura do Rio de Janeiro mantém um sistema de ouvidoria cidadã (1746) que registra reclamações sobre diversos serviços públicos, incluindo problemas relacionados a transporte. Estes dados representam uma fonte valiosa de informação sobre os pontos críticos da rede de transporte, refletindo experiências reais de usuários.

Adicionalmente, o Rio de Janeiro enfrenta desafios de violência armada que afetam diretamente a mobilidade urbana. Dados da plataforma Fogo Cruzado registram ocorrências de tiroteios com vítimas georreferenciadas, permitindo correlacionar incidentes de violência com a infraestrutura de transporte.

A análise integrada destes três conjuntos de dados (GTFS, reclamações 1746 e Fogo Cruzado) pode fornecer insights sobre quais paradas e linhas de transporte apresentam maiores riscos, tanto reativos (baseados em chamados já abertos) quanto preditivos (baseados em padrões históricos de violência), informando decisões de planejamento urbano e alocação de recursos.

### 1.2 Descrição do Problema

Os sistemas de transportes urbanos enfrentam desafios na identificação de pontos críticos de vulnerabilidade. Embora dados estruturados de rotas (GTFS), feedback de cidadãos (reclamações) e registros de violência (Fogo Cruzado) estejam disponíveis, estes dados raramente são integrados para análise conjunta. Especificamente:

- **Falta de Integração**: Os dados de GTFS descrevem a topologia da rede, reclamações identificam problemas operacionais, e dados de tiroteios sinalizam risco de violência — mas não há integração sistemática destas três perspectivas.

- **Análise Limitada de Relacionamentos**: Identificar quais paradas são afetadas por problemas requer análise de proximidade geográfica combinada com topologia de rede.

- **Ausência de Análise de Impacto em Rede**: Não há consideração dos efeitos cascata — como problemas em uma parada central afetam toda a rede de transporte.

- **Caráter Reativo das Métricas Tradicionais**: Métricas baseadas apenas em chamados já abertos são intrinsecamente reativas — o problema já aconteceu. A incorporação de modelos preditivos permite antecipar riscos antes que se materializem em chamados.

### 1.3 Objetivos

**Objetivo Geral:**
Desenvolver um sistema integrado que combine dados de GTFS do Rio de Janeiro com dados de reclamações cidadãs (1746) e ocorrências de tiroteios (Fogo Cruzado) para identificar, analisar e prever paradas de transporte de alto risco.

**Objetivos Específicos:**

1. Modelar a rede de transporte público do Rio de Janeiro como um grafo, representando paradas, rotas e relacionamentos topológicos.

2. Integrar dados de reclamações cidadãs com a rede de transporte através de análise de proximidade geográfica (raio de 100 metros).

3. Desenvolver uma metodologia de cálculo de risco que combine uma componente reativa (chamados 1746) com uma componente preditiva (modelo XGBoost treinado com dados do Fogo Cruzado).

4. Treinar e validar um modelo de machine learning para predição de probabilidade de tiroteio nas proximidades de paradas de ônibus.

5. Criar uma plataforma interativa de visualização que permita exploração dos dados, simulação de cenários e análise de vulnerabilidades.

### 1.4 Justificativa

Este trabalho é justificado por várias razões:

- **Relevância Prática**: O Rio de Janeiro enfrenta desafios contínuos em mobilidade urbana e violência. Ferramentas analíticas que identifiquem pontos de vulnerabilidade — tanto reativos quanto preditivos — podem orientar investimentos em segurança, manutenção e qualidade do serviço.

- **Inovação Metodológica**: A fusão de risco reativo (chamados) com risco preditivo (machine learning sobre dados de violência) numa métrica unificada representa uma abordagem original para análise de vulnerabilidade em transportes.

- **Relevância Acadêmica**: Demonstra aplicação prática de conceitos de bancos de dados em grafo, análise de redes, aprendizado de máquina supervisionado e sistemas distribuídos.

- **Disponibilidade de Dados**: Os três conjuntos de dados utilizados (GTFS, 1746 e Fogo Cruzado) estão disponíveis publicamente, facilitando reprodutibilidade e validação.

- **Escalabilidade**: A arquitetura desenvolvida pode ser aplicada a outras cidades com dados GTFS, sistemas de ouvidoria e registros de violência análogos.

### 1.5 Escopo Negativo

Este trabalho **não** cobre:

- Previsão de demanda de transporte ou otimização de rotas.
- Implementação de sistemas de controle ou atuação automática baseada em análise de risco.
- Análise comparativa com outras cidades (foco exclusivo no Rio de Janeiro).
- Desenvolvimento de aplicativos mobile para usuários finais.
- Validação em campo de resultados (trabalho é exploratório e analítico).
- Previsão de novos chamados 1746 — o modelo preditivo foca exclusivamente em tiroteios.

---

## 2. FUNDAMENTAÇÃO TEÓRICA

### 2.1 Área do Negócio — Transporte Urbano e Análise de Vulnerabilidade

#### Contexto de Transportes Públicos Urbanos

Transportes públicos são infraestruturas críticas para cidades modernas, afetando mobilidade, economia e qualidade de vida. Segundo dados do IPEA (Instituto de Pesquisa Econômica Aplicada), aproximadamente 63% dos deslocamentos no Rio de Janeiro são realizados via transporte público.

#### GTFS — General Transit Feed Specification

GTFS é um formato aberto de dados desenvolvido pelo Google em parceria com agências de trânsito. Define estrutura padronizada para descrever:
- **Stops**: Paradas com coordenadas geográficas
- **Routes**: Linhas de transporte com características (ônibus, metrô, BRT)
- **Trips**: Instâncias individuais de viagens em rotas específicas
- **Stop Times**: Sequências de paradas em cada viagem

GTFS permite modelagem de topologia de transporte e análise de conectividade de rede.

#### Sistema 1746 de Ouvidoria

O 1746 é o sistema de ouvidoria cidadã do Rio de Janeiro que permite registrar reclamações sobre serviços públicos. Dados disponíveis incluem:
- Data de abertura
- Tipo do serviço (granularidade fina, ex: "Guarda Municipal / Fiscalização de trânsito")
- Localização geográfica (latitude/longitude)
- Parada de ônibus mais próxima pré-calculada (stop_id_mais_proximo)

#### Fogo Cruzado

O Fogo Cruzado é uma plataforma que registra ocorrências de tiroteios com vítimas no Rio de Janeiro, com dados georreferenciados e data precisa. Esses dados permitem construir um target binário para modelagem preditiva: ocorreu tiroteio num raio de 500m de uma parada em determinado mês?

### 2.2 Mineração de Dados e Análise Integrada

#### Integração de Dados Heterogêneos

Sistemas modernos frequentemente combinam dados estruturados (GTFS) com dados não-estruturados (reclamações, registros de violência). Técnicas de integração incluem:
- **Matching Geoespacial**: Usar coordenadas para vincular dados de diferentes fontes
- **Deduplicação**: Identificar registros duplicados através de chaves únicas
- **Sincronização**: Manter consistência entre múltiplos repositórios (MongoDB ↔ Neo4j)

#### Análise Geoespacial

Análise geoespacial permite consultas baseadas em localização:
- **Índices 2D-Sphere**: MongoDB oferece índices geoespaciais nativos
- **Queries de Proximidade**: Encontrar pontos dentro de raio especificado
- **Spatial Join Pré-calculado**: O CSV de chamados já inclui a parada mais próxima, reduzindo o custo de O(N_stops) para O(1) por chamado no sync

#### Cálculo de Risco Integrado

O sistema implementa um framework de risco em duas camadas:

**Camada Reativa — Risco por Chamados (risk_score_atual)**:
- Agregação de chamados 1746 abertos próximos à parada (raio de 100m)
- Peso semântico por categoria: Segurança Pública (1.5), Trânsito (0.8), Iluminação (0.6), Conservação (0.5), Limpeza (0.4), Outros (0.3)
- Fórmula de saturação: `risk_sum / (risk_sum + 10)`, mapeando para [0, 1)
- Somente chamados com status "Aberto" ou "Em Atendimento"

**Camada Preditiva — Risco de Tiroteio (risk_score_tiroteio)**:
- Modelo XGBoost treinado com 385.560 amostras (parada × mês, 2021–2025)
- 16 features: geográficas (lat, lon), rede (num_rotas_servindo, pagerank), temporais (ano, mes_sin, mes_cos), e contagens de chamados com lags de 3, 6 e 12 meses (total, segurança pública, iluminação pública)
- Target binário: houve tiroteio num raio de 500m naquele mês?
- AUC-ROC: 0.71 (validação 2024)

**Risco Total Combinado**:
```
risk_score_total = (0.6 × risk_score_atual + 1.4 × risk_score_tiroteio) / 2
```
O peso maior no preditivo (1.4 vs 0.6) reflete seu caráter *forward-looking*.

O score total é normalizado via min-max para a escala 0–100 e classificado em 4 níveis por quartis do range de valores: Alto, Médio-Alto, Médio-Baixo, Baixo.

#### Aprendizado de Máquina Supervisionado

O XGBoost (Extreme Gradient Boosting) foi escolhido por sua robustez a dados tabulares com features heterogêneas e desbalanceamento de classes (~13% de positivos). O `scale_pos_weight = 5.01` compensa o desbalanceamento. Features de contagem de chamados recebem transformação `log1p` para comprimir a cauda longa, e todas as 16 features são padronizadas com `StandardScaler` antes da predição.

As janelas de lag (3, 6 e 12 meses) usam apenas meses anteriores ao mês-alvo (`.rolling(k).sum().shift(1)`), eliminando vazamento temporal.

### 2.3 Trabalhos Relacionados — TODO

---

## 3. MATERIAIS E MÉTODOS

### 3.1 Descrição dos Stakeholders

O sistema foi desenvolvido com foco em potenciais usuários:

- **Planejadores Urbanos**: Utilizarão análise de risco para priorizar investimentos em infraestrutura de transporte e segurança.
- **Operadores de Transporte**: Identificarão paradas com problemas operacionais recorrentes e zonas de risco preditivo de violência para alocação de recursos e ajuste de rotas.
- **Pesquisadores Acadêmicos**: Utilizarão dados e visualizações para pesquisa em redes de transporte e análise de vulnerabilidade.
- **Gestores de Ouvidoria**: Compreenderão correlação entre reclamações e vulnerabilidades estruturais de rede.
- **Cidadãos**: Acessarão informações sobre qualidade e segurança de paradas de transporte.

### 3.2 Descrição da Base de Dados

#### 3.2.1 Fonte de Dados — GTFS Rio de Janeiro

**Origem**: Google GTFS Feeds (https://transitfeeds.com/)

**Características do Dataset**:
- **7.665 Paradas** (Stops) distribuídas geograficamente no Rio de Janeiro
- **511 Linhas de Transporte** (Routes) cobrindo ônibus, metrô e BRT
- **15.917 Viagens** (Trips) representando instâncias de rotas em diferentes períodos
- **938.645 Registros de Stop Times** descrevendo sequências de paradas

**Arquivos Utilizados**:
- `stops.txt`: ID, nome, latitude, longitude, acessibilidade
- `routes.txt`: ID, nome, tipo (ônibus/metrô/BRT), agência
- `trips.txt`: ID da viagem, ID da rota, sentido, destino
- `stop_times.txt`: ID viagem, ID parada, tempo de chegada, sequência

#### 3.2.2 Fonte de Dados — Reclamações 1746

**Origem**: Sistema de Ouvidoria Cidadã do Rio de Janeiro

**Características do Dataset**:
- **22.916 reclamações** registradas entre janeiro/2020 e dezembro/2025, após curadoria de tipos relevantes
- **Categorias canônicas**: Segurança Pública, Iluminação Pública, Conservação de Vias, Trânsito e Transporte, Limpeza Urbana, Outros
- **Pré-processamento**: 47.680 linhas no CSV bruto, filtradas para 22.916 via `TIPO_TO_SERVICO` (14 tipos mantidos, 10 descartados por irrelevância para segurança de paradas)
- **Spatial join pré-calculado**: o CSV já inclui `stop_id_mais_proximo` e `distancia_metros` para cada chamado
- **Campos**: protocolo (id_chamado), data_inicio, tipo (21 valores, mapeados para 6 categorias canônicas), latitude, longitude, stop_id_mais_proximo, distancia_metros

**Distribuição por categoria**:
- Limpeza Urbana: 9.027 (39%)
- Iluminação Pública: 6.167 (27%)
- Conservação de Vias: 3.511 (15%)
- Segurança Pública: 3.158 (14%)
- Trânsito e Transporte: 1.048 (5%)

#### 3.2.3 Fonte de Dados — Fogo Cruzado

**Origem**: API do Fogo Cruzado (https://fogocruzado.org.br/)

**Características**:
- Ocorrências de tiroteios com vítimas, georreferenciadas e com data precisa
- Utilizadas para construir o target binário do modelo preditivo: 1 se houve ≥1 tiroteio num raio de 500m da parada em determinado mês, 0 caso contrário
- Período utilizado: janeiro/2021 a dezembro/2025 (60 meses)
- Taxa base: ~13% dos meses-para possuem tiroteio próximo

#### 3.2.4 Esquema de Armazenamento

**MongoDB — Reclamações**:
```
Collection: reclamacoes_1746_raw
Documentos com:
  - protocolo (unique index)
  - data_abertura
  - servico (categoria canônica), tipo (categoria original)
  - localizacao (GeoJSON, 2dsphere index)
  - stop_id_mais_proximo, distancia_metros
  - sinced_to_neo4j (flag booleana)
```

**Neo4j — Rede de Transporte**:
```
Nodes:
  - Stop: id, name, lat, lon, num_rotas_servindo, pagerank,
          risk_score_atual, risk_score_tiroteio, risk_score_total,
          risk_score_normalized, risk_level, total_reclamacoes,
          reclamacoes_abertas, last_risk_update, last_prediction_date
  - Route: short_name, long_name, type, avg_risk_score, total_stops, high_risk_stops
  - Trip: route_id, headsign, direction
  - Reclamacao: protocolo, data_abertura, servico, status, criticidade, peso, bairro
  - Categoria: nome, peso_base, total_ocorrencias

Relationships:
  - Stop -[CONNECTS_TO]-> Stop (distance_meters, combined_risk, risk_adjusted_cost)
  - Route -[SERVES]-> Stop
  - Trip -[HAS_STOP]-> Stop
  - Reclamacao -[AFFECTS]-> Stop (distance_meters, risk_contribution)
  - Reclamacao -[HAS_TYPE]-> Categoria
```

#### 3.2.5 Análise Descritiva dos Dados

**Estatísticas GTFS**:
- 7.665 paradas distribuídas em área de ~1.500 km² (-23.07° a -22.78° lat, -43.72° a -43.16° lon)
- 511 linhas: 88% ônibus regular (449), 6% BRT (32), 6% trem/metrô (30)
- 15.917 viagens: 54% sentido ida, 46% volta
- Média de 62 paradas por viagem (min: 7, max: 149)

**Estatísticas 1746**:
- 22.916 reclamações no período de 2020–2025 (média ~318/mês)
- Distribuição por serviço: Limpeza Urbana (39.4%), Iluminação Pública (26.9%), Conservação de Vias (15.3%), Segurança Pública (13.8%), Trânsito e Transporte (4.6%)
- 4.908 paradas (64%) receberam pelo menos uma reclamação
- Top 5 paradas mais afetadas: Figueira de Melo (431 chamados), Alfredo Reis (251), Club Municipal (108), Pau-Ferro (87), Brás do Amaral (65)
- Período: a base não contém chamados de 2026 (dataset encerra em dezembro/2025)

**Estatísticas Fogo Cruzado**:
- 385.560 amostras (7.665 paradas × meses com dados)
- ~13% dos meses-para possuem registro de tiroteio num raio de 500m
- Concentração geográfica dos tiroteios segue padrão conhecido da violência no Rio (Zona Norte e Zona Oeste com maior incidência)

**Métricas de Rede (Neo4j GDS)**:
- PageRank médio: 0.00013 (escala logarítmica típica de redes de transporte)
- Betweenness centrality: não disponível (bug conhecido no plugin GDS 5.14 com overflow de histograma para este grafo)
- 223 comunidades detectadas (modularidade: 0.81)

### 3.3 Arquitetura do Sistema

#### 3.3.1 Pipeline ETL

O pipeline é composto por 7 scripts executados sequencialmente:

| Script | Função |
|---|---|
| `01_setup_databases.py` | Inicializa índices MongoDB e constraints Neo4j |
| `02_load_gtfs_to_neo4j.py` | Carrega GTFS: 7.665 Stops, 511 Routes, 15.917 Trips, 938K CONNECTS_TO |
| `03_load_1746_to_mongodb.py` | Filtra e carrega chamados 1746 no MongoDB (22.916 docs) |
| `04_sync_1746_to_neo4j.py` | Sincroniza chamados MongoDB → Neo4j (Reclamacao + AFFECTS) |
| `05_calculate_metrics.py` | Calcula risk_score_atual (reativo) para cada Stop |
| `06_run_analyses.py` | Executa algoritmos de grafo (PageRank, comunidades) |
| `07_predict_risk.py` | Carrega XGBoost, prediz risk_score_tiroteio, calcula risco combinado |

O orquestrador `run_all.sh` ou `make run-all` executa todos em sequência.

#### 3.3.2 Webapp

Plataforma interativa em Streamlit com 6 páginas:
- **Home**: Dashboard com 6 KPIs e distribuição de risco
- **Mapa Interativo**: Mapa Folium com paradas coloridas por risco, filtros e decomposição de scores
- **Grafo de Rede**: Visualização NetworkX + Plotly da topologia da rede
- **Gerenciamento de Dados**: Upload e execução do pipeline
- **Explorar Detalhes**: Busca por parada ou protocolo com visão completa
- **Metodologia**: Documentação da fórmula de risco, pesos e pipeline
- **Modelo Preditivo**: Playground interativo do XGBoost — consulta, simulação what-if e documentação da API

### 3.4 Metodologia de Cálculo de Risco

#### 3.4.1 Risco por Chamados (reativo)

Fórmula de saturação bayesiana:
```
risk_score_atual = risk_sum / (risk_sum + 10)
onde risk_sum = Σ peso(categoria) para chamados com status Aberto/Em Atendimento
```

A constante 10 evita que poucos chamados disparem o score, exigindo volume sustentado para atingir valores altos.

#### 3.4.2 Risco de Tiroteio (preditivo)

Modelo XGBoost com 16 features:
- **Geográficas (45% de importância)**: lat, lon
- **Temporais (27%)**: ano, mes_sin, mes_cos
- **Chamados — lags (17%)**: contagens de reclamações em janelas de 3, 6 e 12 meses (total, segurança pública, iluminação pública), com transformação log1p
- **Rede (10%)**: num_rotas_servindo, pagerank

Artefatos: `xgb_model.joblib` (787 KB), `scaler.joblib` (1.5 KB), `metadata.json`.

#### 3.4.3 Risco Total Combinado

```
risk_score_total = (0.6 × risk_score_atual + 1.4 × risk_score_tiroteio) / 2
risk_score_normalized = (risk_score_total − min) / (max − min) × 100   [0, 100]
```

Classificação por quartis do range de valores (não por quantidade de paradas):
- **Alto**: 4º quartil — [min + 3×step, max]
- **Médio-Alto**: 3º quartil — [min + 2×step, min + 3×step)
- **Médio-Baixo**: 2º quartil — [min + step, min + 2×step)
- **Baixo**: 1º quartil — [min, min + step)

Onde `step = (max − min) / 4`.

### 3.5 Métricas de Rede

**Métricas de Rota**: `avg_risk_score` = média do `risk_score_normalized` das paradas servidas; `high_risk_stops` = contagem de paradas classificadas como Alto.

**Custo Ajustado por Risco (arestas)**:
```
combined_risk = (risk_score_total(A) + risk_score_total(B)) / 2
risk_adjusted_cost = distance_meters × (1 + combined_risk)
```

Permite cálculo de rotas mais seguras: o algoritmo de menor caminho penaliza trechos com risco elevado.
