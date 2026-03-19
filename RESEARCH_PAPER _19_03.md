# RioMobiAnalytics: Sistema de Análise de Risco em Rede de Transporte Público Integrado com Dados de Reclamações Cidadãs

## RESUMO

Este trabalho apresenta RioMobiAnalytics, um sistema de análise que integra dados de GTFS (General Transit Feed Specification) da rede de transporte público do Rio de Janeiro com dados de reclamações cidadãs (1746) para identificar paradas de trânsito de alto risco. O sistema utiliza uma arquitetura híbrida de bancos de dados (MongoDB para dados não-estruturados e Neo4j para relacionamentos em grafo) para modelar a topologia da rede de transporte e calcular métricas de risco baseadas na proximidade geográfica de reclamações. Os resultados demonstram a viabilidade de integração de múltiplas fontes de dados para análise de vulnerabilidades em infraestrutura de transportes.

**Palavras-chave:** Análise de Transportes, Bancos de Dados em Grafo, GTFS, Análise de Risco, Reclamações Cidadãs, Neo4j, MongoDB.

---

## 1. INTRODUÇÃO

### 1.1 Contextualização

O Rio de Janeiro é uma metrópole com aproximadamente 6,7 milhões de habitantes que dependem significativamente de sistemas de transporte público para mobilidade urbana. A rede de transporte da cidade compreende aproximadamente 7.665 paradas de ônibus, 511 linhas de transporte e mais de 15 mil viagens diárias. Este sistema complexo de transportes é essencial para a conectividade urbana, mas enfrenta desafios significativos relacionados à segurança, qualidade do serviço e vulnerabilidades operacionais.

Paralelamente, a prefeitura do Rio de Janeiro mantém um sistema de ouvidoria cidadã (1746) que registra reclamações sobre diversos serviços públicos, incluindo problemas relacionados a transporte. Estes dados representam uma fonte valiosa de informação sobre os pontos críticos da rede de transporte, refletindo experiências reais de usuários.

A análise integrada destes dois conjuntos de dados (GTFS e reclamações 1746) pode fornecer insights sobre quais paradas e linhas de transporte apresentam maiores riscos e vulnerabilidades, informando decisões de planejamento urbano e alocação de recursos.

### 1.2 Descrição do Problema

Os sistemas de transportes urbanos enfrentam desafios na identificação de pontos críticos de vulnerabilidade. Embora dados estruturados de rotas (GTFS) e feedback de cidadãos (reclamações) estejam disponíveis, estes dados raramente são integrados para análise conjunta. Especificamente:

- **Falta de Integração**: Os dados de GTFS descrevem a topologia da rede, enquanto reclamações identificam problemas operacionais, mas não há integração sistemática destas perspectivas.

- **Análise Limitada de Relacionamentos**: Identificar quais paradas são afetadas por problemas requer análise de proximidade geográfica combinada com topologia de rede.

- **Ausência de Análise de Impacto em Rede**: Não há consideração dos efeitos cascata - como problemas em uma parada central afetam toda a rede de transporte.

- **Falta de Métricas de Vulnerabilidade Integradas**: Não existe uma metodologia unificada que combine risco local (reclamações) com importância estrutural (centralidade na rede).

### 1.3 Objetivos

**Objetivo Geral:**
Desenvolver um sistema integrado que combine dados de GTFS do Rio de Janeiro com dados de reclamações cidadãs (1746) para identificar e analisar paradas de transporte de alto risco.

**Objetivos Específicos:**

1. Modelar a rede de transporte público do Rio de Janeiro como um grafo, representando paradas, rotas e relacionamentos topológicos.

2. Integrar dados de reclamações cidadãs com a rede de transporte através de análise de proximidade geográfica (raio de 100 metros).

3. Desenvolver uma metodologia de cálculo de risco que considere: tipo de reclamação, criticidade e status.

4. Criar uma plataforma interativa de visualização que permita exploração dos dados e análise de vulnerabilidades.

### 1.4 Justificativa

Este trabalho é justificado por várias razões:

- **Relevância Prática**: O Rio de Janeiro enfrenta desafios contínuos em mobilidade urbana. Ferramentas analíticas que identifiquem pontos de vulnerabilidade podem orientar investimentos em segurança, manutenção e qualidade do serviço.

- **Inovação Metodológica**: A integração de dados de GTFS com feedback cidadão através de análise geoespacial e de grafo representa uma abordagem inovadora para análise de transportes.

- **Relevância Acadêmica**: Demonstra aplicação prática de conceitos de bancos de dados em grafo, análise de redes, mineração de dados e sistemas distribuídos.

- **Disponibilidade de Dados**: Ambos os conjuntos de dados (GTFS e 1746) estão disponíveis publicamente, facilitando reprodutibilidade e validação.

- **Escalabilidade**: A arquitetura desenvolvida pode ser aplicada a outras cidades com dados GTFS e sistemas de ouvidoria análogos.

### 1.5 Escopo Negativo

Este trabalho **não** cobre:

- Previsão de demanda de transporte ou otimização de rotas.
- Implementação de sistemas de controle ou atuação automática baseada em análise de risco.
- Análise comparativa com outras cidades (foco exclusivo no Rio de Janeiro).
- Desenvolvimento de aplicativos mobile para usuários finais.
- Validação em campo de resultados (trabalho é exploratório e analítico).

---

## 2. FUNDAMENTAÇÃO TEÓRICA

### 2.1 Área do Negócio - Transporte Urbano e Análise de Vulnerabilidade

#### Contexto de Transportes Públicos Urbanos

Transportes públicos são infraestruturas críticas para cidades modernas, afetando mobilidade, economia e qualidade de vida. Segundo dados do IPEA (Instituto de Pesquisa Econômica Aplicada), aproximadamente 63% dos deslocamentos no Rio de Janeiro são realizados via transporte público.

#### GTFS - General Transit Feed Specification

GTFS é um formato aberto de dados desenvolvido pelo Google em parceria com agências de trânsito. Define estrutura padronizada para descrever:
- **Stops**: Paradas com coordenadas geográficas
- **Routes**: Linhas de transporte com características (ônibus, metrô, BRT)
- **Trips**: Instâncias individuais de viagens em rotas específicas
- **Stop Times**: Sequências de paradas em cada viagem

GTFS permite modelagem de topologia de transporte e análise de conectividade de rede.

#### Sistema 1746 de Ouvidoria

O 1746 é o sistema de ouvidoria cidadã do Rio de Janeiro que permite registrar reclamações sobre serviços públicos. Dados disponíveis incluem:
- Data de abertura e encerramento
- Categoria do serviço (transporte, segurança, iluminação, etc.)
- Localização geográfica (latitude/longitude)
- Status (Aberto, Em Atendimento, Fechado)
- Criticidade (Alta, Média, Baixa)

### 2.2 Mineração de Dados e Análise Integrada

#### Integração de Dados Heterogêneos

Sistemas modernos frequentemente combinam dados estruturados (GTFS) com dados não-estruturados (reclamações). Técnicas de integração incluem:
- **Matching Geoespacial**: Usar coordenadas para vincular dados de diferentes fontes
- **Deduplicação**: Identificar registros duplicados através de chaves únicas
- **Sincronização**: Manter consistência entre múltiplos repositórios

#### Análise Geoespacial

Análise geoespacial permite consultas baseadas em localização:
- **Índices 2D-Sphere**: MongoDB oferece índices geoespaciais nativos
- **Queries de Proximidade**: Encontrar pontos dentro de raio especificado

#### Cálculo de Risco Integrado

Metodologias de risco integram múltiplas dimensões:
- **Frequência**: Quantas reclamações ocorreram
- **Tipo**: Categorias de reclamação têm pesos diferentes
- **Criticidade**: Problemas graves recebem multiplicadores maiores
- **Temporal**: Considerar apenas reclamações recentes (últimos 30 dias)

### 2.3 Trabalhos Relacionados - TODO 

---

## 3. MATERIAIS E MÉTODOS

### 3.1 Descrição dos Stakeholders

O sistema foi desenvolvido com foco em potenciais usuários:

- **Planejadores Urbanos**: Utilizarão análise de risco para priorizar investimentos em infraestrutura de transporte e segurança.
- **Operadores de Transporte**: Identificarão paradas com problemas operacionais recorrentes para alocação de recursos de manutenção.
- **Pesquisadores Acadêmicos**: Utilizarão dados e visualizações para pesquisa em redes de transporte e análise de vulnerabilidade.
- **Gestores de Ouvidoria**: Compreenderão correlação entre reclamações e vulnerabilidades estruturais de rede.
- **Cidadãos**: Acessarão informações sobre qualidade e segurança de paradas de transporte.

### 3.2 Descrição da Base de Dados

#### 3.2.1 Fonte de Dados - GTFS Rio de Janeiro

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

#### 3.2.2 Fonte de Dados - Reclamações 1746

**Origem**: Sistema de Ouvidoria Cidadã do Rio de Janeiro

**Características do Dataset**:
- **1.746 Reclamações** registradas entre período de coleta
- **Categorias**: Segurança Pública, Transporte, Iluminação, Conservação de Vias, Limpeza Urbana, Outros
- **Campos**: ID (protocolo), data de abertura/encerramento, categoria, criticidade (Alta/Média/Baixa), status (Aberto/Em Atendimento/Fechado), localização (lat/lon)

**Características Geoespaciais**:
- Coordenadas precisas permitindo análise de proximidade

#### 3.2.3 Esquema de Armazenamento

**MongoDB - Reclamações**:
```
Collections: reclamacoes_1746_raw
Documentos com:
  - protocolo (unique index)
  - data_abertura, data_encerramento
  - servico (categoria), criticidade, status
  - localizacao (GeoJSON, 2dsphere index)
  - synced_to_neo4j (flag booleana)
```

**Neo4j - Rede de Transporte**:
```
Nodes:
  - Stop: id, name, lat, lon, risk_score, risk_level, betweenness_centrality, pagerank, community_id
  - Route: short_name, long_name, type, avg_risk_score, total_stops
  - Trip: route_id, headsign, direction
  - Reclamacao: protocolo, data_abertura, servico, criticidade
  - Categoria: servico, peso_base

Relationships:
  - Stop -[CONNECTS_TO]-> Stop (sequential, distance_meters, risk_adjusted_cost)
  - Route -[SERVES]-> Stop
  - Trip -[HAS_STOP]-> Stop
  - Reclamacao -[AFFECTS]-> Stop (dentro 100m)
```

#### 3.2.4 Seleção de Atributos Relevantes

A partir do inventário completo de dados, foram selecionados os atributos essenciais para análise de risco:

**Atributos GTFS Selecionados**:
- **Stops**: `stop_id` (PK), `stop_name`, `stop_lat`, `stop_lon` - coordenadas críticas para análise geoespacial
- **Routes**: `route_id` (PK), `route_short_name`, `route_long_name`, `route_type` - tipo diferencia ônibus (700), BRT (702) e trem/metrô (200)
- **Trips**: `trip_id` (PK), `route_id` (FK), `trip_headsign` - relacionamento entre rotas e paradas
- **Stop_times**: `trip_id`, `stop_id`, `stop_sequence` - ordem sequencial para construir grafo de rede

**Atributos 1746 Selecionados**:
- `protocolo` (PK), `data_abertura`, `servico`, `latitude`, `longitude`, `status`, `criticidade`
- Filtro temporal: últimos 30 dias com status 'Aberto' ou 'Em Atendimento'

**Atributos Derivados Calculados**:
- **risk_score**: `risk_sum / (risk_sum + 10)` onde risk_sum = Σ(peso_categoria × mult_criticidade)
- **risk_level**: Baixo (<2.0), Médio (2.0-5.0), Alto (≥5.0)
- **complaint_count**: número de reclamações dentro de 100m
- **Métricas de grafo**: betweenness_centrality, pagerank, community_id

#### 3.2.5 Análise Descritiva dos Dados

**Estatísticas GTFS**:
- 7.665 paradas distribuídas em área de ~1.500 km² (-23.07° a -22.78° lat, -43.72° a -43.16° lon)
- 511 linhas: 88% ônibus regular (449), 6% BRT (32), 6% trem/metrô (30)
- 15.917 viagens: 54% sentido ida, 46% volta
- Média de 62 paradas por viagem (min: 7, max: 149)

**Estatísticas 1746**:
- 303 reclamações no período de 29 dias (média 10.1/dia)
- Distribuição por serviço: Segurança Pública (38.3%), Iluminação Pública (29.7%), Conservação de Vias (23.1%), Trânsito e Transporte (8.9%)
- Distribuição por criticidade: Alta (55.4%), Média (44.6%)
- Status: 100% Aberto (nenhuma resolvida no período)
- Concentração geográfica: Zona Sul (Copacabana, Ipanema), Centro (Saara, Lapa), Barra da Tijuca

**Análise de Proximidade Geoespacial**:
- Em amostra de 1.000 paradas: 8.4% apresentaram reclamações dentro de raio de 100m
- Média de 1.5 reclamações por parada afetada
- Máximo: 4 reclamações associadas a uma única parada
- Projeção: ~640 paradas afetadas em toda a rede (8.4% × 7.665)
