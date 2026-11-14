---
id: 14_guia_do_app
titulo: Guia de uso do aplicativo — mapa, painel da parada, rede e página de risco
tipo: interno
origem: páginas do aplicativo (webapp/views)
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: versão atual do aplicativo
atualizado_em: 2026-11-14
tags: [como usar, mapa, camadas, filtros, busca, painel da parada, rede, simulador, página risco, assistente, protocolo 1746]
---

## Como usar o mapa

O **Mapa** é a tela principal. No topo há três controles:

- **Buscar parada:** digite o nome; a lista mostra o nome e o índice de cada parada. Ao escolher, o mapa centraliza nela e abre o painel.
- **Camada:** muda o que a cor dos pontos representa. **Índice de risco** pinta pelos quatro níveis. **Tiroteio** pinta só pelo score do modelo de tiroteio, em quatro faixas (abaixo de 25, 25 a 49, 50 a 69 e 70 ou mais). **Reclamações** mostra as reclamações do 1746 coloridas por categoria.
- **Filtros:** nível de risco (um ou mais), uma linha de ônibus específica e um mínimo de reclamações vinculadas. O número ao lado de "Filtros" indica quantos estão ativos, e "Limpar filtros" volta ao padrão.

Abaixo do mapa, "Tabela das paradas exibidas" lista as paradas que passaram pelos filtros, e "Reclamação da Central 1746 por protocolo" busca um chamado pelo número e mostra bairro, descrição e paradas afetadas.

## O painel da parada selecionada

Ao clicar numa parada, o painel mostra:

- o **índice de 0 a 100**, o nível e a posição relativa ("entre os 10% mais altos" ou "maior que 60% das paradas");
- três números: reclamações vinculadas, linhas que passam na parada e paradas ligadas diretamente na rede;
- a **composição do índice**, com duas barras de 0 a 100: a parte de reclamações e o score de tiroteio do modelo;
- um gráfico com os **tiroteios a até 500 m mês a mês** e o total no período (fonte: Fogo Cruzado);
- a lista das reclamações vinculadas, por categoria.

Os botões levam à página Rede a partir dessa parada ("Ver rede da parada"), abrem o assistente já com a parada como contexto ("Perguntar ao assistente") ou limpam a seleção.

## A página Rede

A página **Rede** escolhe uma parada de origem e desenha as paradas alcançáveis em **anéis**: o primeiro anel são as paradas a um passo na rede, o segundo a dois passos, e assim por diante. A cor de cada parada é o nível do índice, e é possível mostrar ou esconder os nomes. Serve para ver como o risco se distribui ao longo das linhas que saem de um ponto. Não calcula tempo de viagem nem horários.

## A página Risco

A página **Risco** mostra como o modelo foi avaliado e permite explorá-lo:

- **Períodos:** treino (2021 a 2023), validação (2024) e teste (2025).
- **Métricas da validação:** AUC, recall (dos meses com tiroteio, quantos o modelo marcou), precisão (dos meses marcados, quantos tiveram tiroteio) e a taxa real de meses com tiroteio.
- **Gráfico por decil:** a taxa real de tiroteio em cada décimo das paradas ordenadas pelo score. É a melhor forma de ver que o modelo ordena bem (arquivo 06).

Há três abas. **Consultar parada** mostra o índice, as duas partes, o nível e o valor das 16 variáveis do modelo para uma parada. **Simulador** permite mudar as contagens de reclamações (total, Segurança Pública e Iluminação em 3, 6 e 12 meses) e ver como o score do modelo, o índice e o nível mudariam, mantendo fixas localização, linhas e PageRank. **Detalhes técnicos** traz os hiperparâmetros do modelo.

## Como o simulador ajuda a entender o índice

O simulador responde perguntas do tipo "se esta parada tivesse o dobro de reclamações de iluminação, o índice subiria muito?". Em geral, mudar as reclamações move o índice menos do que se espera, porque a localização e o tempo pesam mais no modelo do que as reclamações (arquivo 06). Ele mostra também a fórmula usada, com os números da simulação: (0,6 × reclamações + 1,4 × tiroteio) / 2, normalizado de 0 a 100 pelas paradas atuais. O resultado é um exercício, não uma previsão para uma situação real.

## As páginas Início, Metodologia e Assistente

**Início** apresenta o projeto, alguns números gerais e atalhos para as outras páginas. **Metodologia** explica o cálculo do índice, os níveis, os limites e um glossário. **Assistente** é o chat: aceita perguntas em português sobre paradas, linhas, bairros, reclamações, tiroteios e sobre o próprio projeto, e cita a fonte de cada número. Quando se chega a ele pelo botão do painel, "esta parada" se refere à parada selecionada no mapa (arquivo 10).
