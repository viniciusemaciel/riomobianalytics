---
id: 20_contexto_isp
titulo: Contexto externo — ISP-RJ e as estatísticas oficiais de criminalidade
tipo: externo
origem: documentos do ISP-RJ e reportagens (paráfrase); o projeto NÃO usa dados do ISP
url: https://www.rj.gov.br/isp/sites/default/files/2025-10/Guia%20Pratico%2003.pdf
periodo_coberto: conceitos e indicadores vigentes até 2025
atualizado_em: 2026-11-14
acessado_em: 2026-11-14
tags: [ISP, ISP-RJ, CISP, AISP, RISP, registro de ocorrência, indicadores estratégicos, roubo em coletivo, estatística oficial]
---

## O que é o ISP-RJ e de onde vêm seus dados

O Instituto de Segurança Pública (ISP) é o órgão do governo do estado do Rio de Janeiro que consolida, analisa e divulga as estatísticas oficiais de segurança pública. Foi criado por lei estadual em 1999. O ISP parte principalmente dos **registros de ocorrência (RO)** feitos nas delegacias da Polícia Civil: ele extrai os dados todo mês, consolida e publica. Os dados também são abertos em formatos como CSV e XLSX no portal de dados abertos do estado e podem ser consultados em plataformas do instituto, como o ISPGeo e o ISP Conecta.

Este arquivo é **contexto externo**: o RioMobiAnalytics não usa números do ISP. Para valores oficiais de crimes, o caminho é o próprio ISP.

Fontes: [ISP, Relatório de Atividades 2024](https://www.isp.rj.gov.br/sites/default/files/2024-01/Relat%C3%B3rio%20de%20Atividades%202024.pdf); [ISP, Guia Prático 03](https://www.rj.gov.br/isp/sites/default/files/2025-10/Guia%20Pratico%2003.pdf); [ISP, Plano de Dados Abertos](https://www.rj.gov.br/isp/sites/default/files/2025-12/Plano%20de%20Dados%20Abertos%20ISP.pdf). Acesso em 14/11/2026.

## CISP, AISP e RISP: a divisão territorial usada pelo ISP

O ISP organiza os dados por áreas da segurança pública. Cada registro de ocorrência traz, entre outros campos, a CISP em que foi registrado, a AISP e a RISP onde o fato ocorreu, data e hora da comunicação e do fato, local, bairro e município.

- **CISP** (Circunscrição Integrada de Segurança Pública): em geral, a área de atuação de uma delegacia da Polícia Civil.
- **AISP** (Área Integrada de Segurança Pública): em geral, a área de um batalhão da Polícia Militar, e a unidade para a qual o sistema de metas distribui objetivos.
- **RISP** (Região Integrada de Segurança Pública): agrupamento regional de AISPs.

O ISP disponibiliza tabelas de correspondência entre CISP, AISP, RISP e municípios. O projeto usa o **bairro oficial** (polígonos da Prefeitura), e não essas divisões; ligar paradas a CISPs exigiria essas tabelas.

Fontes: [ISP, Guia Prático 03](https://www.rj.gov.br/isp/sites/default/files/2025-10/Guia%20Pratico%2003.pdf); [relatório sobre registros de ocorrência (Fiocruz/DSS)](https://dssbr.ensp.fiocruz.br/wp-content/uploads/2021/12/Relatorio_inqueritos_crimes_homicidio_contra_criancas_adolescentes_SEPOL_e_ISP.pdf); [ISP, Plano de Dados Abertos](https://www.rj.gov.br/isp/sites/default/files/2025-12/Plano%20de%20Dados%20Abertos%20ISP.pdf). Acesso em 14/11/2026.

## Os quatro indicadores estratégicos de criminalidade

O sistema de metas do ISP acompanha quatro indicadores estratégicos: **Letalidade Violenta** (homicídio doloso, feminicídio, lesão corporal seguida de morte, morte por intervenção de agente do Estado e latrocínio), **Roubo de Veículo**, **Roubo de Rua** (que inclui roubo a transeunte, **roubo em coletivo** e roubo de celular) e **Roubo de Carga**.

O roubo em coletivo é o indicador oficial mais próximo da experiência de quem usa ônibus, mas o projeto não o utiliza. O índice do RioMobiAnalytics mede o entorno de paradas por reclamações do 1746 e por tiroteios do Fogo Cruzado, e não crimes registrados em delegacia.

Fonte: [ISP, Guia Prático 03](https://www.rj.gov.br/isp/sites/default/files/2025-10/Guia%20Pratico%2003.pdf). Acesso em 14/11/2026.

## ISP e Fogo Cruzado medem coisas diferentes

O **ISP** conta crimes registrados em delegacia, por tipo penal e local do fato, e é a fonte oficial. O **Fogo Cruzado** conta tiroteios e disparos de arma de fogo registrados e verificados pelo instituto, sem ser fonte oficial. A Secretaria de Segurança do estado afirmou, em reportagem de 2026 sobre o relatório de 2025, que os registros de ocorrência seguem o ordenamento jurídico, que não inclui a categoria "tiroteio". Em outra ocasião, o governo disse não conhecer a metodologia do Fogo Cruzado e indicou o ISP como fonte oficial.

Consequência prática: um tiroteio sem vítimas pode não gerar registro de crime, e um homicídio pode não ser um tiroteio. **Os números do ISP e do Fogo Cruzado não são comparáveis diretamente**, e nenhum deve ser usado para "validar" o outro.

Fontes: [Jornal de Brasília](https://jornaldebrasilia.com.br/noticias/brasil/letalidade-policial-cresce-133-e-disputa-territorial-bate-recorde-no-rj/); [Agência Brasil (via Acessa)](https://www.acessa.com/noticias/2025/02/amp/232923-relatorio-indica-que-rj-vive-escalada-da-violencia-neste-inicio-de-ano.html). Acesso em 14/11/2026.

## Como o assistente deve usar este contexto

Ao explicar a diferença entre fontes, o assistente deve atribuir cada afirmação ("segundo o ISP", "segundo o governo do estado"), não citar números do ISP (o projeto não os tem) e remeter o usuário ao site do ISP para valores oficiais. Não deve comparar o índice do projeto com estatísticas do ISP nem sugerir que um bairro "tem mais crime" com base neste projeto.
