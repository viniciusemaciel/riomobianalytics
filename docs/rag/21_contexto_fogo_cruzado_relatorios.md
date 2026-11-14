---
id: 21_contexto_fogo_cruzado_relatorios
titulo: Contexto externo — Fogo Cruzado: metodologia, relatórios anuais e conferência com a base
tipo: externo
origem: relatórios do Instituto Fogo Cruzado conforme reportagens (paráfrase) e conferência com a base do projeto
url: https://fogocruzado.org.br/
periodo_coberto: 2016–2025 (relatórios sobre 2022, 2024 e 2025)
atualizado_em: 2026-11-14
acessado_em: 2026-11-14
tags: [Fogo Cruzado, relatório anual, tiroteios, baleados, chacina policial, bala perdida, disputas, transporte público, metodologia]
---

## Quem é o Fogo Cruzado e como produz os dados

O Fogo Cruzado começou como um aplicativo criado com a Anistia Internacional e lançado em 2016 para monitorar tiroteios no Rio. Hoje é uma organização da sociedade civil de produção cidadã de dados, que atua em quatro regiões metropolitanas (Rio de Janeiro, Recife, Salvador e Belém). Segundo reportagens, o instituto colhe por aplicativo de celular informações sobre trocas de tiros em tempo real, e analistas verificam esses registros.

Não é um órgão oficial. O governo do estado do Rio já declarou que o ISP é a fonte oficial e que não comenta dados não oficiais. O projeto usa a exportação da API do instituto, e o texto sobre a base está no arquivo 04.

Fontes: [Jornal Contábil (relatório 2022)](https://www.jornalcontabil.com.br/noticia/duas-mil-pessoas-foram-baleadas-na-regiao-metropolitana-do-rio-de-janeiro-em-2022/); [IHU/Unisinos](https://ihu.unisinos.br/categorias/635116-rio-de-janeiro-tem-tres-chacinas-por-mes-revelam-dados-de-plataforma-inedita); [Folha de Pernambuco](https://www.folhape.com.br/noticias/numero-de-vitimas-de-bala-perdida-no-rio-aumenta-58-em-2025/398173/). Acesso em 14/11/2026.

## Definições do instituto

Nos relatórios, **baleados** são as pessoas feridas ou mortas por arma de fogo. **Chacina policial** é o episódio em que três ou mais civis são mortos em uma ação policial. **Vítima de bala perdida** é a pessoa sem ligação com o evento em que houve disparo e que foi atingida por projétil. Essas definições são do instituto e não coincidem com categorias penais oficiais.

No arquivo de dados do projeto, a coluna de chacina (`massacre`) aparece em ocorrências com mortes múltiplas, e a de ação policial (`police_action`) marca quando houve ação ou operação policial; a definição exata de cada coluna deve ser conferida na documentação da API.

Fontes: [Jornal de Brasília](https://jornaldebrasilia.com.br/noticias/brasil/letalidade-policial-cresce-133-e-disputa-territorial-bate-recorde-no-rj/); [Folha de Pernambuco](https://www.folhape.com.br/noticias/numero-de-vitimas-de-bala-perdida-no-rio-aumenta-58-em-2025/398173/). Acesso em 14/11/2026.

## Relatório anual de 2025 para o Grande Rio

Segundo reportagens sobre o relatório anual divulgado no fim de fevereiro de 2026, o Grande Rio registrou **2.315 tiroteios em 2025**, contra 5.444 em 2017, no início da série. O número de tiroteios caiu, mas a letalidade subiu: **1.722 pessoas baleadas** (10% a mais que em 2024) e **944 mortos** (23% a mais). O instituto contou 31 chacinas policiais, com 231 mortos (em 2024, foram 28 episódios e 99 mortos), e **275 tiroteios motivados por disputas entre facções e milícias**, o maior número da série e 26% acima de 2024.

Leitura para o projeto: o número de **ocorrências** e o de **vítimas** contam histórias diferentes. Em 2025 houve menos tiroteios e mais pessoas baleadas.

Fontes: [ISTOÉ](https://istoe.com.br/inseguranca-no-rio-de-janeiro-e-agravada-por-paralisia-na-gestao-estadual); [Jornal de Brasília](https://jornaldebrasilia.com.br/noticias/brasil/letalidade-policial-cresce-133-e-disputa-territorial-bate-recorde-no-rj/); [Alma Preta](https://almapreta.com.br/?p=68824). Acesso em 14/11/2026.

## Relatórios de 2024 e do primeiro semestre de 2025

Para 2024, o relatório anual apontou **2.532 tiroteios** na região metropolitana do Rio, o menor valor da série até então (média de sete por dia). A participação de forças de segurança foi de cerca de 36% dos tiroteios, e houve recorde de crianças baleadas (26 até 11 anos).

No primeiro semestre de 2025, o instituto contou 1.233 tiroteios, menos que nos mesmos períodos de 2024 (1.346) e de 2023 (1.778), mas 154 confrontos entre grupos armados, o maior valor da série (104 no primeiro semestre de 2024). Para 2022, o relatório indicou cerca de 2 mil baleados (984 mortos e 1.016 feridos).

Fontes: [Movimento Econômico](https://movimentoeconomico.com.br/seguranca/2025/02/19/rio-recife-belem-e-salvador-tiveram-mais-de-6-mil-tiroteios-em-2024/); [Alma Preta](https://almapreta.com.br/sessao/cotidiano/em-2024-maioria-dos-tiroteios-no-rio-e-em-belem-ocorreu-em-acoes-policiais/); [Brasil de Fato](https://www.brasildefato.com.br/2025/07/01/numero-de-vitimas-de-tiroteios-cresce-na-regiao-metropolitana-do-rio/); [Jornal Contábil](https://www.jornalcontabil.com.br/noticia/duas-mil-pessoas-foram-baleadas-na-regiao-metropolitana-do-rio-de-janeiro-em-2022/). Acesso em 14/11/2026.

## Baleados no transporte público

Um levantamento do instituto, de 2024, contou ao menos **156 pessoas baleadas no transporte público** da região metropolitana do Rio em cerca de oito anos (56 mortas e 100 feridas), das quais 14 em 2024 até aquela data. É um recorte de **dentro** do transporte, bem menor que o total de baleados, e diferente do que o projeto mede (tiroteio a até 500 m de uma parada).

Fonte: [CartaCapital](https://www.cartacapital.com.br/?p=469025). Acesso em 14/11/2026.

## Limites ao usar os números do Fogo Cruzado

São registros de eventos verificados por uma organização independente, não estatística oficial; dependem da capacidade do instituto de captar e verificar cada evento e das suas definições, e podem ser revisados. Contagens de "tiroteios" e de "disparos" nas reportagens usam a mesma ideia de ocorrência, mas as séries variam conforme a região (cidade, Grande Rio, quatro regiões metropolitanas). O assistente deve sempre dizer qual recorte e qual período está citando.
