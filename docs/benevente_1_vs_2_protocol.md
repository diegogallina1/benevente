# Benevente 1 e Benevente 2 — protocolo experimental

## Contrato de versões

- **Benevente 1** é a série publicada: seleção fundamentalista multifatorial em janeiro, pesos anuais e manutenção até a revisão seguinte.
- **Benevente 2** preserva exatamente essa cesta anual e acrescenta uma camada intranual de risco. Ela pode deslocar parte do patrimônio para CDI, mas não troca os ativos selecionados.

Este experimento não altera os artefatos publicados nem o site.

## Informação permitida

A camada observa somente o Ibovespa até o fechamento anterior. Calcula queda em relação ao maior nível das últimas 126 sessões e volatilidade realizada de 20 sessões. O sinal é deslocado em um pregão: uma informação do fechamento de hoje só pode alterar a exposição amanhã.

A configuração central, declarada antes da primeira execução, é:

- alerta: queda de 10% ou volatilidade anualizada de 30%;
- grave: queda de 20% ou volatilidade anualizada de 50%;
- teto de ações no alerta: 55%;
- teto de ações no estado grave: 25%;
- retorno gradual após 10 sessões mais calmas;
- custo adicional: 10 pontos-base por unidade de patrimônio movimentada.

O retorno diário do Benevente 2 é o CDI mais a fração mantida do excesso diário do Benevente 1, descontado o custo da mudança de exposição. Assim, o experimento mede apenas a proteção e não atribui à camada uma seleção de ativos que ela não realizou.

## Papel da LLM

Nenhum. Ainda não existe um arquivo histórico de notícias com URL, horário de publicação e conteúdo congelado. Inventar retrospectivamente que a LLM teria reconhecido a Covid produziria viés de antecipação. Um braço futuro poderá transformar notícias arquivadas em nível de risco, mas a alteração de peso continuará sujeita a uma regra quantitativa.

## Sensibilidade e limitações

Além da configuração central, uma grade de 432 combinações varia os limiares, os tetos e o prazo de recuperação. A grade mede sensibilidade; não escolhe a melhor configuração depois de observar 2020.

Como candidato separado, o motor pode escolher uma configuração usando exclusivamente 2015–2018 e então mantê-la congelada em 2019–2025. Esse recorte permite perguntar o que teria acontecido na Covid sem calibrar os números na própria crise. Quatro anos de treino continuam sendo uma amostra pequena e a escolha não deve ser tratada como definitiva.

A separação 2019–2025 é retrospectiva e contém apenas sete anos. A própria família de proteção foi concebida depois da Covid, portanto existe viés conceitual mesmo sem calibrar os parâmetros nela. Custos são aproximados e o imposto decorrente de trocas intranuais ainda não está modelado.

## Execução

```powershell
.\.venv-benevente\Scripts\python.exe benevente2_event_risk.py
```

Os resultados são gravados em `artifacts/benevente2_event_risk/`.
