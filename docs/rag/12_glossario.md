---
id: 12_glossario
titulo: Glossário de termos do projeto
tipo: interno
origem: repositório riomobianalytics e fontes públicas citadas nos arquivos 20 a 22
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: não se aplica
atualizado_em: 2026-11-14
tags: [glossário, índice, nível, exposição, ocorrência, GTFS, PageRank, CISP, AISP, AUC]
---

## Termos do índice de risco

**Índice de risco (`risk_score_normalized`)**: nota de 0 a 100 de cada parada, relativa às demais. **Nível**: faixa do índice em quatro partes iguais do intervalo (Baixo, Médio-Baixo, Médio-Alto, Alto). **Risco reativo (`risk_score_atual`)**: parte do índice vinda das reclamações do 1746, de 0 a 1. **Risco de tiroteio (`risk_score_tiroteio`)**: saída do modelo, de 0 a 1 no banco (o app às vezes mostra de 0 a 100), sem calibração. **Risco total (`risk_score_total`)**: combinação dos dois, `(0,6 × reativo + 1,4 × tiroteio) / 2`. **Normalização mínimo-máximo**: reescala o total para que o menor valor vire 0 e o maior, 100. **Peso da categoria**: importância fixa dada a cada tipo de reclamação (Segurança Pública 1,5 até Outros 0,3). **Saturação**: transformação `soma / (soma + 10)` que limita a influência de muitas reclamações.

## Termos dos dados

**Parada (Stop)**: ponto de ônibus do GTFS. **Linha (Route)**: linha de ônibus. **Viagem (Trip)**: percurso de uma linha; o projeto usa uma por linha. **GTFS**: formato aberto de dados de transporte público. **1746**: Central de atendimento da Prefeitura do Rio; seus chamados viram "reclamações". **Reclamação**: chamado do 1746 de um dos 14 tipos mantidos, ligado à parada mais próxima. **Fogo Cruzado**: instituto que registra tiroteios; fonte da base de ocorrências. **Ocorrência (ou tiroteio)**: um registro de tiroteio do Fogo Cruzado, não uma vítima. **Baleados**: feridos mais mortos, civis e agentes. **Bairro oficial**: bairro pelo polígono do Limite de Bairros da Prefeitura.

**Área de planejamento (AP)**: uma das 5 grandes divisões da cidade usadas pela Prefeitura (AP 1 Centro; AP 2 Zona Sul e Grande Tijuca; AP 3 Zona Norte; AP 4 Barra e Jacarepaguá; AP 5 Zona Oeste). **Região de planejamento (RP)**: subdivisão das AP que agrupa bairros vizinhos, como Madureira, Bangu ou Jacarepaguá (arquivo 15).

## Termos de contagem

**Exposição**: número de tiroteios a até 500 m de uma parada; o mesmo tiroteio conta para todas as paradas no raio. **Ocorrência por bairro**: cada tiroteio contado uma vez, no bairro onde ocorreu. **Raio de 500 m**: distância usada para associar tiroteios a uma parada. **Janelas de 3, 6 e 12 meses**: períodos anteriores ao mês-alvo usados para somar reclamações no modelo. **Período da base**: 2020 a 2025.

## Termos de rede e grafo

**Grafo**: conjunto de nós (paradas, linhas, reclamações) e relações. **Neo4j**: banco de grafos usado. **MongoDB**: banco de documentos, onde ficam as reclamações brutas. **`CONNECTS_TO`**: ligação entre duas paradas seguidas numa viagem. **`SERVES`**: a linha atende a parada. **`AFFECTS`**: a reclamação aponta para a parada mais próxima. **PageRank**: medida de centralidade de uma parada na rede. **Salto**: um passo de uma parada para a seguinte na rede. **Custo ajustado por risco**: distância × (1 + risco combinado).

## Termos do modelo

**XGBoost**: algoritmo de árvores de decisão em conjunto, usado como classificador binário. **AUC-ROC**: mede quão bem o modelo ordena; 0,5 é sorteio e 1,0 é perfeito (o modelo tem 0,71 na validação de 2024). **Precisão**: dos meses marcados pelo modelo, quantos tiveram tiroteio. **Revocação**: dos meses com tiroteio, quantos o modelo marcou. **F1**: média harmônica entre precisão e revocação. **Limiar**: corte de classificação (0,488). **Validação**: ano usado para avaliar (2024). **Teste**: ano reservado (2025), não avaliado. **Vazamento temporal**: usar informação do futuro; o projeto evita ao usar só meses anteriores. **`scale_pos_weight`**: peso extra da classe rara no treino.

## Termos de segurança pública (fontes externas)

**ISP-RJ**: Instituto de Segurança Pública do estado do Rio, que publica estatísticas oficiais de criminalidade. **CISP**: Circunscrição Integrada de Segurança Pública, área de uma delegacia de polícia civil. **AISP**: Área Integrada de Segurança Pública, área de um batalhão da PM. **RISP**: Região Integrada de Segurança Pública, que reúne AISPs. **ADPF 635**: ação no STF sobre operações policiais em favelas do Rio. **Chacina**: no Fogo Cruzado, situação com tiros em que três ou mais civis são mortos; **chacina policial** é a que ocorre em ação ou operação policial. Na base do projeto, a coluna `massacre` marca chacinas (arquivos 04 e 21). **Operação Contenção**: operação das polícias Civil e Militar de 28/10/2025 nos complexos do Alemão e da Penha; na base é um único registro (arquivos 04 e 22).
