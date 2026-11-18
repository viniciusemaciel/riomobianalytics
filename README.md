# RioMobiAnalytics

**Índice de risco do entorno das paradas de ônibus do Rio de Janeiro, construído sobre um grafo da rede de transporte.** O projeto liga cada uma das 6.426 paradas às reclamações da Central 1746 e a um modelo de aprendizado de máquina que estima a chance de tiroteio por perto. O resultado é um índice de 0 a 100 por parada, explicável e explorável num app Streamlit com banco de grafos (Neo4j), banco de documentos (MongoDB) e um assistente que responde perguntas em português.

> Projeto de conclusão da pós-graduação em Ciência de Dados e Analytics (Universidade de Pernambuco).
> Autores: **Vinicius Maciel** e **Clauberto Jr**.
> App no ar: <https://riomobianalytics.streamlit.app/>

## O que o projeto faz

- **Modela a rede de ônibus como um grafo.** Paradas, linhas e viagens do GTFS da cidade ficam no Neo4j. Duas paradas seguidas numa viagem são ligadas (`CONNECTS_TO`), e a posição de cada parada na rede (PageRank, número de linhas) vira variável do modelo.
- **Liga as reclamações às paradas.** Os chamados do 1746 de 14 tipos (iluminação, segurança pública, conservação etc.) ficam no MongoDB e são ligados no grafo à parada mais próxima, até 300 m (mediana de 97 m).
- **Prevê o risco de tiroteio.** Um classificador XGBoost, treinado com as ocorrências do [Fogo Cruzado](https://fogocruzado.org.br/), estima a probabilidade de pelo menos um tiroteio a até 500 m da parada no mês.
- **Combina os dois sinais.** A parte reativa (reclamações, com peso por categoria) e a parte preditiva (probabilidade do modelo) viram um índice de 0 a 100, dividido em 4 níveis de mesma largura: Baixo, Médio-Baixo, Médio-Alto e Alto.

```
risco_total = (0,6 × risco_reclamações + 1,4 × probabilidade_tiroteio) / 2   → normalizado de 0 a 100
```

O índice usa as bases até dezembro de 2025 (data de referência 31/12/2025). Ele compara o entorno das paradas; não é uma garantia de segurança nem uma previsão de ocorrências de hoje.

## O app

| Página | O que dá para fazer |
| --- | --- |
| **Início** | Explicação do projeto, números gerais e atalhos para as outras páginas |
| **Mapa** | Paradas coloridas pelo índice, pela parte de tiroteio ou pelas reclamações, com filtros, busca e o painel de cada parada |
| **Rede** | As paradas ligadas a uma origem, em anéis pela distância na rede de linhas |
| **Assistente** | "Pergunte ao RioMobi": perguntas em português sobre os dados, a metodologia e o contexto da cidade, com fontes, gráficos, tabelas e mapas |
| **Risco** | Como o modelo se comporta (importância das variáveis, desempenho) e um simulador de cenários |
| **Metodologia** | O caminho completo, das bases ao índice |

## O assistente (RAG)

O assistente é um agente com chamada de ferramentas. O modelo de linguagem nunca acessa o banco diretamente: ele pede uma ferramenta, o app executa e devolve o resultado, por até 6 rodadas por pergunta.

- **Modelos:** Claude Haiku 5.5 como principal e Gemini 3.5 Flash-Lite como reserva automática (fallback) quando o principal falha.
- **17 ferramentas:** consultas fixas ao Neo4j (paradas, bairros, linhas, reclamações, tiroteios), uma consulta Cypher livre e só de leitura (`consulta_cypher`, protegida por três camadas: validação do texto, sessão de leitura e tempo limite), a busca na documentação (`buscar_conhecimento`) e as ferramentas de visual (gráfico, tabela, mapa).
- **Documentação indexada:** 19 arquivos de `docs/rag/`, um trecho por seção `##` (113 trechos), com vetores de 768 dimensões do `gemini-embedding-001`. O índice fica versionado em `artifacts/rag_index/`.
- **Busca:** até 3 trechos por pergunta, com similaridade mínima de 0,65 (valores escolhidos no benchmark de 17/11/2026, em `notebooks/05_benchmark_rag.ipynb`).
- **Regra:** números (índice, contagens, rankings) vêm sempre das ferramentas que consultam o banco; a documentação explica o como e o porquê.

## Arquitetura

```
GTFS + 1746 + Fogo Cruzado ──► scripts/ (carga, uma vez) ──► Neo4j Aura   (grafo + índice)
                                                         └─► MongoDB Atlas (chamados brutos)
                                                                    ▲
           artifacts/ (modelo, índice do RAG) ─────────────► app Streamlit (webapp/)
                                                                    │
                                               Claude / Gemini ◄────┘ (assistente)
```

O app só **lê** os bancos. Toda carga e todo cálculo do índice acontecem fora dele, nos `scripts/`.

## Dados

| Base | Uso |
| --- | --- |
| GTFS do Rio (`stops`, `routes`, `trips`, `stop_times`) | Paradas, linhas e o grafo de ligações |
| Central 1746 (`data/1746/`) | Parte reativa do índice e variáveis do modelo (22.916 chamados de 14 tipos, 2020 a 2025) |
| Fogo Cruzado (`data/fogocruzado/`) | Alvo do modelo (12.637 tiroteios na cidade, dez/2019 a dez/2025) |
| Limite de Bairros da Prefeitura (`data/gtfs/Limite_de_Bairros.*`) | Bairro oficial das paradas e dos tiroteios (164 bairros) |

## Modelo

Classificador XGBoost na granularidade parada × mês, com 16 variáveis: localização, número de linhas, PageRank, mês do ano e contagens de reclamações em 3, 6 e 12 meses (total, segurança e iluminação). Divisão por tempo: treino de 2021 a 2023, validação em 2024 e teste em 2025. AUC de validação de 0,71. As páginas Risco e Metodologia trazem a importância das variáveis e os detalhes.

## Estrutura do repositório

```
├── webapp/                    App Streamlit (entrada: webapp/Home.py)
│   ├── views/                 Início, Mapa, Rede, Assistente, Risco, Metodologia
│   ├── rag/                   Assistente: agente, provedores (Claude e Gemini), ferramentas,
│   │                          guarda do Cypher, busca na documentação, visuais
│   ├── utils/                 Conexões, consultas em cache, tema, estado
│   ├── assets/ e static/      Logo, ícones, CSS e fontes
├── scripts/                   Carga dos bancos e cálculo do índice
│   ├── 01_setup_databases.py       APAGA os dados dos dois bancos e recria índices
│   ├── 02_load_gtfs_to_neo4j.py    paradas, linhas, viagens, ligações
│   ├── 03_load_1746_to_mongodb.py  chamados → MongoDB
│   ├── 04_sync_1746_to_neo4j.py    chamados → grafo (AFFECTS)
│   ├── 05_calculate_metrics.py     parte reativa do índice
│   ├── 06_pagerank.py              PageRank (networkx, igual ao do treino)
│   ├── 07_predict_risk.py          previsão do modelo e índice final (--data-ref)
│   ├── 08_bairro_oficial.py        bairro oficial dos tiroteios (à parte)
│   ├── 09_bairro_paradas.py        bairro oficial das paradas (à parte)
│   ├── 10_tiroteios_neo4j.py       tiroteios no Neo4j (à parte)
│   ├── 11_indexar_rag.py           índice de vetores de docs/rag (à parte)
│   └── run_all.sh                  roda de 01 a 07
├── avaliacao/                 Benchmark do assistente (perguntas, cenários, métricas)
├── notebooks/                 Preparação, análise, variáveis, treino e benchmark do RAG
├── artifacts/                 Modelo, scaler, metadados, índice do RAG e resultados do benchmark
├── data/                      GTFS, 1746, Fogo Cruzado e arquivos processados
├── docs/                      Artigo (research_paper.md) e a documentação do assistente (rag/)
├── apresentacao/              Slides da apresentação final e do RAG (HTML)
├── tests/                     Testes (pytest) e verificações contra o banco
├── config.py                  Credenciais, caminhos e parâmetros
└── requirements.txt
```

## Como rodar

**Requisitos:** Python 3.12, uma instância do [Neo4j AuraDB](https://neo4j.com/cloud/aura/) e um cluster do [MongoDB Atlas](https://www.mongodb.com/atlas) (os dois têm plano gratuito). Para o assistente, chaves da Anthropic e do Gemini; para o mapa, uma chave da MapTiler.

```bash
git clone https://github.com/viniciusemaciel/riomobianalytics.git
cd riomobianalytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # preencha as credenciais
```

### Carregar os bancos

Rode uma vez, ou quando quiser reconstruir do zero. **O passo 01 apaga os dados dos dois bancos.**

```bash
FORCE_RESET=true ./scripts/run_all.sh
```

Os scripts 08 a 11 não entram no `run_all.sh` e rodam à parte, depois da carga:

```bash
python scripts/08_bairro_oficial.py
python scripts/09_bairro_paradas.py --gravar
python scripts/10_tiroteios_neo4j.py --gravar
python scripts/11_indexar_rag.py --gravar      # só quando editar docs/rag/
```

O script 07 usa por padrão a data de referência 31/12/2025 (fim das bases). Para outra data: `python scripts/07_predict_risk.py --data-ref AAAA-MM-DD`.

### Rodar o app

```bash
streamlit run webapp/Home.py
```

### Testes

```bash
pytest tests/                              # sem banco e sem API
python tests/test_benchmark.py             # benchmark com modelo falso
python tests/check_somente_leitura.py      # contra o Aura: o assistente não escreve no banco
python tests/check_armadilhas.py           # contra o Aura e as APIs: perguntas-armadilha
```

## Configuração

O `config.py` lê primeiro as variáveis de ambiente e o `.env`, e depois os Secrets do Streamlit.

| Variável | Descrição |
| --- | --- |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Conexão com o Neo4j (`neo4j+s://<id>.databases.neo4j.io`) |
| `MONGO_URI`, `MONGO_DB` | Conexão com o MongoDB (banco padrão `riomobianalytics`) |
| `MAPTILER_API_KEY` | Mapa base do app |
| `ANTHROPIC_API_KEY`, `RAG_MODEL` | Modelo principal do assistente (padrão `claude-haiku-5-5`) |
| `GEMINI_API_KEY`, `RAG_MODEL_GEMINI` | Reserva do assistente e embeddings (padrão `gemini-3.5-flash-lite`) |
| `RAG_PROVEDOR_PADRAO`, `RAG_FALLBACK` | Provedor principal (`anthropic`) e reserva automática (`true`) |
| `RAG_BUSCA_TOP_K`, `RAG_LIMIAR_SIMILARIDADE` | Trechos por busca (3) e similaridade mínima (0,65) |
| `RAG_MAX_PERGUNTAS_SESSAO` | Limite de perguntas por sessão (30) |

Os modelos de arquivo estão em `.env.example` e `.streamlit/secrets.toml.example`. O `.env` e o `.streamlit/secrets.toml` não vão para o git.

## Publicar no Streamlit Community Cloud

1. Crie o app em [share.streamlit.io](https://share.streamlit.io) apontando para este repositório, branch `main`, arquivo `webapp/Home.py`.
2. Em **Settings → Secrets**, cole as chaves de `.streamlit/secrets.toml.example` (valores entre aspas, formato TOML).
3. No MongoDB Atlas, libere `0.0.0.0/0` em **Network Access** (o Streamlit Cloud não tem IP fixo).

Antes de uma demonstração: o AuraDB Free pausa depois de alguns dias parado (retome no console) e o app do Streamlit dorme depois de cerca de 12 horas sem acesso, então abra o app alguns minutos antes.

## Retreinar o modelo

Rode os notebooks em ordem:

1. `01_filtragem_gtfs_1746.ipynb`: filtra o GTFS e o 1746 brutos (rodado originalmente no Databricks).
2. `02_eda_fogo_cruzado.ipynb`: análise exploratória dos tiroteios.
3. `03_feature_engineering.ipynb`: monta a base do modelo, incluindo o PageRank.
4. `04_treino_modelo.ipynb`: treina e compara modelos e salva o vencedor em `artifacts/`.

O `05_benchmark_rag.ipynb` roda o benchmark do assistente (busca e respostas, Claude × Gemini).

## Limitações

- O Neo4j AuraDB Free não tem o plugin Graph Data Science, então o PageRank é calculado em Python com os mesmos parâmetros do treino.
- A ligação reclamação → parada é por proximidade (parada mais próxima, até 300 m), não por causalidade. O índice compara a exposição relativa entre paradas; não é garantia de segurança.
- Os dados do Fogo Cruzado são uma exportação de um momento; o índice deve ser recalculado quando a base for atualizada.

## Tecnologias

Python · Streamlit · Neo4j · MongoDB · XGBoost · scikit-learn · NetworkX · Plotly · Folium · Claude · Gemini · pandas
