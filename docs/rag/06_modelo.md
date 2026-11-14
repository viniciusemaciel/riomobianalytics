---
id: 06_modelo
titulo: O modelo XGBoost de risco de tiroteio
tipo: interno
origem: artifacts/metadata.json, notebooks 03 e 04, webapp/views/risco.py
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: treino 2021–2023, validação 2024, teste 2025
atualizado_em: 2026-11-14
tags: [XGBoost, modelo, AUC, validação, features, importância, limiar, limitações]
---

## O que o modelo prevê e como foi montado

O modelo é um classificador binário XGBoost. Para cada par (parada, mês), ele estima se haverá **pelo menos um tiroteio do Fogo Cruzado a até 500 m da parada naquele mês** (só município do Rio). A base tem 385.560 linhas: 6.426 paradas × 60 meses (janeiro de 2021 a dezembro de 2025). Em 14,96% dos pares houve tiroteio; na validação, 13,2%.

A divisão é temporal: **treino de 2021 a 2023** (231.336 linhas), **validação em 2024** (77.112) e **teste em 2025** (77.112). As métricas mostradas no app são as da **validação de 2024**. Hiperparâmetros do `metadata.json`: 300 árvores, profundidade 5, taxa de aprendizado 0,05, subamostra 0,8, `scale_pos_weight` 5,01 e métrica AUC.

## As 16 variáveis do modelo

- **Geografia**: latitude e longitude da parada.
- **Rede**: número de linhas que passam na parada e PageRank (importância na rede).
- **Reclamações do 1746** (9 variáveis): total, de Segurança Pública e de Iluminação, cada uma somada nos 3, 6 e 12 meses anteriores ao mês-alvo.
- **Tempo**: ano e o mês codificado em seno e cosseno (sazonalidade).

As contagens de reclamações passam por `log1p` e todas as variáveis são padronizadas (`StandardScaler` ajustado no treino). As janelas usam só meses **anteriores** ao mês-alvo, então o modelo não vê o futuro.

## Quão bom é o modelo (validação 2024)

| Modelo | AUC-ROC |
|---|---|
| XGBoost (usado) | 0,7105 |
| Rede neural simples (MLP) | 0,6190 |
| Regressão logística | 0,6093 |
| Sorteio (referência) | 0,50 |

No limiar de classificação 0,488, o XGBoost tem precisão de 0,22, revocação de 0,61 e F1 de 0,33. Em palavras: o modelo **ordena** bem melhor do que o acaso, e acerta mais de metade dos meses com tiroteio, mas, entre os meses que ele marca, só cerca de 1 em 5 de fato teve tiroteio. Serve para priorizar e comparar paradas, **não para alarme de alta precisão**.

## O que o modelo acerta na prática

Ordenando os pares parada e mês de 2024 pelo score do modelo e dividindo em dez grupos iguais (decis), a taxa real de meses com tiroteio a 500 m sobe quase sempre de um grupo para o outro: 2% no décimo mais baixo, 12% no meio e **33% no décimo mais alto**, contra 13% na média. Os 10% de maior score reúnem 25% de todos os meses com tiroteio; os 30% de maior score, 53%; e a metade de maior score, 76%. É esse ordenamento que o índice aproveita: paradas de índice alto concentram muito mais tiroteios no entorno, embora a maioria dos meses delas ainda passe sem nenhum.

## O que mais pesa e o que isso significa

Pelo ganho médio nas árvores, os grupos de variáveis pesam cerca de: **geografia 45%** (latitude 22,9% e longitude 22,5%), **tempo 27%**, **reclamações 17%** e **rede 10%** (valores do notebook). Ou seja, o modelo aprendeu sobretudo **onde** os tiroteios já aconteceram e em que épocas; as reclamações refinam, e mais as de 12 meses do que as de 3.

Consequências para quem lê o índice: paradas vizinhas tendem a ter valores parecidos; a explicação de um índice alto é, em grande parte, a localização histórica; e o modelo não "enxerga" causas locais.

## Limitações do modelo

- **Não é probabilidade calibrada** e o índice final é relativo (arquivo 05).
- **Viés de registro**: o alvo vem de ocorrências registradas pelo Fogo Cruzado, e as reclamações dependem de quem usa o 1746.
- **Efeito do tempo**: o `ano` pesa 10,9%; usar o modelo num ano que ele não viu é extrapolar.
- **Tiroteio a 500 m não é tiroteio na parada**, e o modelo não distingue o tipo de ocorrência (ação policial, disputa etc.).
- As métricas da página Risco são calculadas a partir das previsões da validação de 2024.
