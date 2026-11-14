---
id: 13_faq
titulo: Perguntas frequentes sobre o projeto
tipo: interno
origem: síntese dos arquivos 01 a 12
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: 2020–2025
atualizado_em: 2026-11-14
tags: [FAQ, perguntas, respostas, índice, dados, modelo, assistente]
---

## Perguntas sobre o projeto e o índice

**O que o índice de risco mede?** O quanto o entorno de uma parada se destaca, em relação às outras paradas, por reclamações do 1746 e pela previsão de tiroteio a até 500 m. É uma nota de 0 a 100.

**O índice é uma probabilidade ou um "% de risco"?** Não. É relativo: a parada de maior valor sempre recebe 100. Serve para comparar paradas e nunca deve ser lido como "x% de chance".

**O que significa o nível Alto?** A parada está na faixa mais alta do intervalo do índice (cerca de 75 a 100 da escala). Não quer dizer que algo vá acontecer, só que ela se destaca entre as paradas do projeto.

**Por que uma parada tem índice alto?** O modelo pesa muito a localização (latitude e longitude somam cerca de 45% da importância) e a época; as reclamações pesam menos. Sem inventar causas, a resposta honesta é que a região teve tiroteios registrados e que paradas vizinhas costumam ter valores parecidos.

**Posso usar o índice para escolher meu trajeto?** O projeto não foi feito para isso e o assistente não dá conselho de segurança pessoal. Para decisões do dia a dia, consulte fontes oficiais e o contexto local.

## Perguntas sobre os dados

**De onde vêm os dados?** Da rede de ônibus (GTFS), das reclamações da Central 1746 e dos registros de tiroteio do Fogo Cruzado.

**Que período os dados cobrem?** Tiroteios de 2020 a 2025 (a base termina em 31/12/2025); reclamações de 02/01/2020 a 12/12/2025. Os dados não chegam até hoje, e o assistente deve citar o período.

**Quantas paradas e linhas há?** 6.426 paradas e 510 linhas no feed filtrado.

**Os dados incluem crimes como roubo?** Não. O projeto não usa dados do ISP-RJ. As reclamações de "Segurança Pública" do 1746 são sobretudo fiscalização e guarda municipal, não registro de crimes.

**Por que há tiroteios de fora da cidade do Rio?** A base do Fogo Cruzado cobre 21 municípios do Grande Rio. O alvo do modelo usa só a cidade do Rio, mas as contagens por parada e o gráfico mensal usam toda a base.

**Em que horário acontecem mais tiroteios?** Na cidade do Rio, de 2020 a 2025, há picos na madrugada (3h e 4h) e no começo da noite (18h às 20h). Os da madrugada estão muito ligados a operações policiais. As ferramentas não filtram por horário; o resumo está no arquivo 16.

**Qual região da cidade tem mais tiroteios?** A Zona Norte (AP 3) reúne metade dos tiroteios registrados na cidade de 2020 a 2025 e também a maior parte das paradas. Todas as áreas tiveram menos tiroteios em 2025 do que em 2020 (arquivo 15).

**Por que não há paradas em Santa Cruz?** O feed de ônibus foi recortado num raio de 40 km do Centro, o que deixa de fora a região de Santa Cruz e quase toda Guaratiba (arquivos 02 e 15).

**Os tiroteios estão diminuindo?** Sim, em número: a cidade passou de 7,4 por dia em 2020 para 4,3 em 2025. Mas a parcela com ação policial subiu e o número de mortos em 2025 foi o maior da base (arquivos 04 e 16).

## Perguntas sobre contagens

**Por que a soma dos tiroteios das paradas de um bairro passa do total do bairro?** Porque o mesmo tiroteio conta para todas as paradas a até 500 m (exposição), enquanto no bairro cada tiroteio conta uma vez (ocorrência). Nunca some paradas para obter o bairro.

**O que é "exposição" de uma parada?** O número de tiroteios registrados a até 500 m dela no período.

**O número de tiroteios é o de vítimas?** Não. Conta ocorrências. A base original tem dados de vítimas, mas o app não os mostra.

**Por que a contagem de tiroteios e o índice podem divergir?** A contagem é histórico; o índice mistura previsão do modelo e reclamações e é relativo.

## Perguntas sobre o modelo

**Que modelo é usado?** Um XGBoost com 16 variáveis (localização, rede, reclamações em 3, 6 e 12 meses e tempo), treinado com 2021 a 2023 e validado em 2024.

**Quão bom é o modelo?** AUC de 0,71 na validação de 2024 (0,5 seria sorteio). Ordena melhor que o acaso e acerta mais da metade dos meses com tiroteio, mas só cerca de 1 em 5 dos meses marcados tem tiroteio de fato. Serve para priorizar, não para alarme.

**Por que a localização pesa tanto?** Porque tiroteios se concentram em certas áreas ao longo do tempo; o modelo aprendeu onde já ocorreram. Por isso paradas vizinhas têm valores parecidos.

## Perguntas sobre o grafo e a rede

**O que é PageRank aqui?** Uma medida de quão central é a parada na rede de linhas. Não indica perigo.

**O que liga duas paradas no grafo?** Uma viagem que passa por elas em sequência.

**Por que Neo4j e MongoDB?** O Neo4j guarda a rede e os vínculos (consultas por proximidade na rede); o MongoDB guarda as reclamações brutas.

**O que é o custo ajustado por risco?** A distância entre paradas multiplicada por (1 + risco combinado das duas), pensada para caminhos que evitem trechos de maior risco.

**Como uso o simulador?** Na página Risco, aba Simulador, escolha uma parada e mude as contagens de reclamações; o app mostra como o score do modelo, o índice e o nível mudariam (arquivo 14).

**O que é a camada "Tiroteio" do mapa?** Ela pinta as paradas só pelo score do modelo de tiroteio, sem a parte de reclamações (arquivo 14).

## Perguntas sobre o assistente

**O que o assistente sabe responder?** Perguntas sobre paradas, linhas, bairros, reclamações e tiroteios do projeto, e sobre a metodologia e o contexto das fontes.

**Ele inventa números?** Não deve: todo número vem de uma ferramenta e traz uma fonte numerada. Se não achar, diz que não encontrou.

**Ele pode executar consultas livres no banco?** Sim, só de leitura, com limite de linhas e de tempo. Ele não escreve nem apaga nada.

**Por que ele às vezes recusa uma pergunta?** Porque está fora do escopo, pede conselho pessoal de segurança, ou tenta alterar dados.

## Perguntas sobre contexto externo

**Por que os tiroteios caíram desde 2021?** A base mostra queda ano a ano de 2021 (4.645 tiroteios) a 2025 (2.316) nos 21 municípios do Grande Rio que ela cobre. As causas são debatidas e o projeto não as afirma; o arquivo 22 reúne eventos do período citados por fontes públicas.

**O que o ISP-RJ mede de diferente?** Registros oficiais de crimes feitos pela polícia (por delegacia e batalhão); o Fogo Cruzado registra tiroteios, que não são uma categoria oficial. As duas medidas não são comparáveis diretamente (arquivos 20 e 21).

**O projeto diz qual grupo armado domina um bairro?** Não. O projeto não tem dados de grupos armados, e o assistente não deduz isso a partir de tiroteios. Ele pode mostrar os tiroteios do Fogo Cruzado e as reclamações do 1746 da parada ou do bairro.

## Perguntas sobre a Operação Contenção, chacinas e ônibus

**Como a Operação Contenção aparece nos dados?** Como uma única ocorrência no bairro da Penha em 28/10/2025, com 117 civis e 5 agentes mortos. Ela pesa muito nos totais de mortos de 2025 e de outubro (122 das 584 mortes do ano na cidade do Rio), mas conta como um tiroteio só. O assistente não tem ferramenta de mortos: esses números vêm do CSV do Fogo Cruzado (arquivo 04), e o contexto da operação está no arquivo 22.

**O que é uma "chacina" nos dados do Fogo Cruzado?** Uma situação com tiros em que três ou mais civis morrem; a chacina policial é a que acontece em ação policial. Na base há 294 ocorrências marcadas como chacina (152 na cidade do Rio). Esse indicador não está nas ferramentas prontas do assistente (arquivos 04 e 21).

**As operações policiais afetam os ônibus?** O arquivo 22 traz reportagens sobre ônibus usados como barricadas na Operação Contenção, mas o projeto não mede interrupções de linhas nem paradas fora de serviço.
