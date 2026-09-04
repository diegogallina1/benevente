A automação preparou a decisão do ano e parou aqui, porque quem aprova é uma
pessoa: a política exige aprovação humana nomeada, e mesclar este pull request é
o registro dela.

O que conferir antes de aprovar:

- O `decision_date` dos livros é o do primeiro pregão do ano.
- O `status` diz `decisao_tomada_na_data`, e não `reconstrucao_sob_politica_congelada`.
  Se disser reconstrução, a automação rodou depois da data e a amostra
  confirmatória do ano não vale. Aí é caso de investigar, não de aprovar.
- O manifesto da captura traz os quatro insumos com hash, e o `--conferir` passou.
- A suíte reproduziu a decisão de 2026 com o mesmo maquinário que produziu esta.

O que este pull request **não** decide: nada sobre a política. Orçamento por
perfil, número de emissores, tetos e fatores continuam sendo os do registro
congelado. O que a automação fez foi aplicá-los à data, com os dados da data.
