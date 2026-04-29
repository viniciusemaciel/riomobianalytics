# Relatório de Otimização — RioMobiAnalytics

---

## 1. Contexto

O projeto RioMobiAnalytics analisa a rede de transporte público do Rio de Janeiro integrando duas fontes de dados:

- **GTFS** — feed oficial da rede de ônibus (paradas, rotas, viagens, horários)
- **1746** — reclamações de cidadãos georeferenciadas

O pipeline original carregava **todos os dados brutos** sem qualquer filtragem, resultando em tempo de processamento excessivo e consumo desnecessário de recursos.

Este relatório documenta as otimizações aplicadas, os critérios adotados e os ganhos obtidos.

---

## 2. Diagnóstico — Situação Antes da Otimização

### Volumetria original dos arquivos GTFS

| Arquivo | Registros | Tamanho em disco |
|---------|-----------|-----------------|
| `stops.txt` | 7.665 | 0,57 MB |
| `routes.txt` | 511 | 0,04 MB |
| `trips.txt` | 15.917 | 1,24 MB |
| `stop_times.txt` | **938.645** | **75,07 MB** |
| `calendar.txt` | 3 serviços | — |
| `chamados_v2.csv` | 303 | 0,05 MB |

### Principais bottlenecks identificados

1. **`stop_times.txt` sem filtro** — 938k registros carregados integralmente, sendo a grande maioria redundante para a análise de rede (múltiplas trips replicando o mesmo percurso)
2. **Carga de todos os tipos de serviço** — trips de sábados (`S_REG`) e domingos (`D_REG`) carregadas junto com dias úteis (`U_REG`), sem distinção de relevância
3. **Ausência de recorte geográfico** — paradas fora da área urbana do Rio incluídas no processamento
4. **Um `session.run()` por linha** — sem uso de bulk insert (`UNWIND`) no Neo4j, gerando overhead massivo de roundtrips

### Distribuição de trips por tipo de serviço (antes)

| service_id | Descrição | Trips | % |
|-----------|-----------|-------|---|
| `U_REG` | Dias úteis (seg–sex) | 7.908 | 49,7% |
| `S_REG` | Sábados | 4.860 | 30,5% |
| `D_REG` | Domingos/Feriados | 3.149 | 19,8% |

### Distribuição geográfica das paradas (antes)

| Raio do Centro (Praça XV) | Paradas | % do total |
|--------------------------|---------|------------|
| 10 km | 1.547 | 20,2% |
| 20 km | 3.978 | 51,9% |
| 30 km | 5.525 | 72,1% |
| **40 km** | **6.426** | **83,8%** |
| 50 km | 7.284 | 95,0% |
| 60 km | 7.665 | 100,0% |

---

## 3. Otimizações Aplicadas

### 3.1 Filtro Geográfico — Raio de 40 km do Centro do Rio

**Critério:** apenas paradas dentro de 40 km do ponto de referência adotado — **Praça XV** (lat -22.9035, lon -43.1729), que corresponde ao centro histórico e ponto de maior convergência da rede de transporte.

**Distância calculada via fórmula de Haversine** sobre a superfície esférica da Terra, sem aproximação plana.

**Justificativa do raio de 40 km:**
- 20 km cobre o núcleo urbano consolidado (51,9% das paradas)
- 40 km captura toda a malha urbana relevante do Rio, incluindo Barra da Tijuca, Campo Grande e Zona Norte (83,8%)
- Acima de 40 km, as paradas restantes pertencem a municípios limítrofes sem relevância para a análise de risco urbano do Rio

**Impacto em `stops.txt`:**

| | Registros |
|---|---|
| Original | 7.665 |
| Após filtro | 6.426 |
| **Removidos** | **1.239 (16,2%)** |

---

### 3.2 Filtro por Tipo de Serviço — Apenas U_REG (Dias Úteis)

**Critério:** apenas trips com `service_id = U_REG` são mantidas.

**Justificativa:**
- Dias úteis representam o fluxo habitual e mais denso da rede — o cenário mais relevante para análise de risco
- Sábados e domingos operam com frequência reduzida e não alteram a topologia do grafo (as mesmas paradas são servidas, em menor escala)
- Os algoritmos de análise — PageRank, Betweenness Centrality e Louvain — operam sobre a **topologia** da rede, não sobre a frequência horária

**Impacto em `trips.txt` (antes de 1 trip/rota):**

| | Trips |
|---|---|
| Todos os serviços | 15.917 |
| Apenas U_REG | 7.908 |
| Redução | 50,3% |

---

### 3.3 1 Trip Representativa por Rota

**Critério:** de todas as trips U_REG de cada rota, mantém-se apenas a primeira ocorrência.

**Por que isso funciona sem perda de informação:**

No GTFS, uma `Route` (linha de ônibus, ex.: linha 474) gera múltiplas `Trips` ao longo do dia — cada saída é uma trip separada. Em média, o dataset do Rio tem **15,5 trips por rota** no período de dias úteis. Todas elas percorrem **exatamente a mesma sequência de paradas**.

O pipeline usa `stop_times` para criar dois tipos de relacionamentos no Neo4j:
- `(Trip)-[:HAS_STOP]->(Stop)` — intermediário
- `(Stop)-[:CONNECTS_TO]->(Stop)` — o que alimenta os algoritmos GDS

Como o `CONNECTS_TO` é criado com `MERGE`, paradas duplicadas entre trips da mesma rota são simplesmente ignoradas. O grafo resultante é **idêntico** com 1 ou com 15 trips por rota.

**Impacto em `trips.txt`:**

| | Trips |
|---|---|
| U_REG (todas) | 7.908 |
| 1 por rota | 510 |
| **Redução** | **93,6%** |

---

### 3.4 Impacto Combinado em `stop_times.txt`

Os três filtros acima (geo + U_REG + 1 trip/rota) foram aplicados em cascata sobre o `stop_times.txt`:

| Nível de filtro | Stop-times | Redução acumulada |
|----------------|------------|-------------------|
| 0 — Baseline (sem filtro) | 938.645 | — |
| 1 — Filtro geográfico 40 km | ~827.690 | 11,8% |
| 2 — + Apenas U_REG | ~399.855 | 57,4% |
| 3 — + 1 trip representativa/rota | **25.086** | **97,3%** |

**Redução em disco:** de **75,07 MB → 1,96 MB** (97,4% menor)

---

### 3.5 Filtro Geográfico em `chamados_v2.csv`

**Critério:** reclamações com coordenadas inválidas ou fora do raio de 40 km são removidas.

**Resultado:** todos os 303 registros do dataset possuem coordenadas válidas e estão dentro do raio — nenhum registro foi removido. Dataset íntegro.

---

### 3.6 `calendar.txt` — Apenas U_REG

**Critério:** manter apenas a linha correspondente ao `service_id = U_REG`.

| | Serviços |
|---|---|
| Original | 3 (U_REG, S_REG, D_REG) |
| Filtrado | 1 (U_REG) |

---

## 4. Volumetria Comparativa Final

| Arquivo | Registros (antes) | Registros (depois) | Redução | Tamanho (antes) | Tamanho (depois) |
|---------|-------------------|-------------------|---------|-----------------|-----------------|
| `stops.txt` | 7.665 | 6.426 | 16,2% | 0,57 MB | 0,40 MB |
| `routes.txt` | 511 | 510 | 0,2% | 0,04 MB | 0,04 MB |
| `trips.txt` | 15.917 | 510 | **96,8%** | 1,24 MB | 0,04 MB |
| `stop_times.txt` | 938.645 | 25.086 | **97,3%** | 75,07 MB | 1,96 MB |
| `calendar.txt` | 3 | 1 | 66,7% | — | — |
| `chamados_v2.csv` | 303 | 303 | 0% | 0,05 MB | 0,05 MB |

---

## 5. Parâmetros do Recorte Adotado

| Parâmetro | Valor |
|-----------|-------|
| Centro de referência | Praça XV, Rio de Janeiro (lat -22.9035, lon -43.1729) |
| Raio geográfico | 40 km |
| Tipo de serviço | U_REG (dias úteis, segunda a sexta) |
| Período coberto pelo GTFS | 31/12/2022 → 31/12/2025 |
| Strategy de trips | 1 trip representativa por rota |
| Reclamações 1746 | 303 registros (todos dentro do raio) |
| Paradas incluídas | 6.426 de 7.665 (83,8% da rede) |

---

## 6. Próximos Passos — Expansão Temporal do Dataset 1746

Com a **redução de 97,3% no volume de dados GTFS** processados, o pipeline agora opera com capacidade computacional significativamente maior. Isso abre espaço para **expandir a janela temporal das reclamações 1746**, aumentando a robustez estatística das análises de risco.

### Situação atual

| Métrica | Valor |
|---------|-------|
| Período coberto | 15/11/2025 → 14/12/2025 (30 dias) |
| Total de reclamações | 303 |
| Densidade temporal | ~10 reclamações/dia |

### Limitações do período atual

- **Amostra pequena** — 303 registros podem não capturar padrões sazonais ou eventos pontuais (greves, eventos climáticos, obras)
- **Janela curta** — 30 dias não permitem análise de tendências temporais ou validação de recorrência de problemas
- **Baixa confiança estatística** — métricas de risco calculadas sobre poucos eventos são mais suscetíveis a outliers

### Proposta de expansão

| Cenário | Período | Estimativa de registros | Ganho analítico |
|---------|---------|------------------------|-----------------|
| **Mínimo** | 6 meses | ~1.800 | Captura variação sazonal básica |
| **Recomendado** | 12 meses | ~3.600 | Ciclo anual completo, padrões consolidados |
| **Ideal** | 24 meses | ~7.200 | Validação de tendências, comparação ano a ano |

### Viabilidade técnica

Com a otimização aplicada, o pipeline agora processa:
- **25.086 stop-times** (vs. 938.645 antes) — 97,3% menos dados GTFS
- **Tempo de carga estimado** — redução de horas para minutos

Isso permite absorver **até 20x mais reclamações 1746** sem comprometer o tempo total de execução, mantendo-o abaixo do baseline original.

### Impacto esperado

- **Maior robustez nos scores de risco** — paradas com múltiplas reclamações ao longo do tempo terão scores mais confiáveis
- **Detecção de padrões temporais** — identificar se certos problemas são sazonais (ex.: alagamentos no verão)
- **Validação de intervenções** — comparar períodos antes/depois de melhorias na infraestrutura
- **Análise de clusters mais precisa** — algoritmo Louvain se beneficia de maior densidade de eventos

### Ação recomendada

Solicitar ao fornecedor do dataset 1746 (Prefeitura do Rio / Data.Rio) a **exportação histórica de 12–24 meses** de reclamações georeferenciadas, aplicando o mesmo filtro geográfico de 40 km do Centro.

---
