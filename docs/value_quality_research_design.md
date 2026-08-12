# Benevente Quant AI — desenho de pesquisa valor e qualidade

## Hipótese

O Benevente testa se um filtro de valor e qualidade, complementado por uma revisão estruturada de LLM, gera retorno ajustado a risco superior ao CDI em horizontes de dois e cinco anos, depois de custos de negociação. Esta é uma hipótese testável, não uma promessa de performance.

## Ordem de decisão

1. Carregar snapshots fundamentais com `available_date <= T-1`.
2. Eliminar empresas ilíquidas, endividadas, sem geração de caixa ou com rentabilidade insuficiente.
3. Ranquear elegíveis por valor (FCF yield, earnings yield, book yield) e qualidade (ROE/ROIC, margem, dívida).
4. Solicitar ao LLM uma crítica factual da tese e dos riscos. A LLM não gera pesos, preços-alvo ou garantias.
5. Otimizador matemático constrói a carteira dentro de limites e com CDI como manga residual.
6. Toda recomendação requer aprovação humana e é registrada em carteira-sombra antes de qualquer execução.

## Dados fundamentais

Use o contrato `data/fundamentals_point_in_time_template.csv`. Cada dado precisa de uma data contábil (`as_of_date`) e uma data em que se tornou público (`available_date`). Dados atuais baixados de APIs públicas não podem ser reutilizados retroativamente em backtests.

Para propostas correntes, `cvm_fundamentals.py` baixa o DFP oficial da CVM e guarda a data de recebimento do documento. O preço, market cap e volume vêm de `yfinance` somente como cotação ao vivo e precisam ficar arquivados junto à proposta. O DFP não substitui uma base histórica de fundamentos para testes de performance.

## Custos Clear/B3

O modelo padrão para swing trade na B3 considera corretagem Clear de 0% e tarifas B3 de 0,0300% por lado para a faixa-base (0,0050% de negociação e 0,0250% de liquidação), além de slippage que cresce com a participação no volume diário. A tabela é versionada e deve ser conciliada com a nota de corretagem em cada execução.

## Protocolo de validação

- Universo histórico datado, incluindo exclusões e deslistagens.
- Treino, validação e teste final congelado; *walk-forward* mensal.
- Comparar quant puro, LLM sugestor e híbrido com as mesmas restrições.
- Reportar CDI, Ibovespa, carteira global B3 e MVO clássico.
- Dobrar custos e executar testes de subperíodos antes de alegar robustez.
- Publicar snapshots de dados, versões de modelo e notas de corretagem conciliadas.

## Escopo comercial

Enquanto não houver a estrutura regulatória apropriada, o Benevente Wealth System deve atuar como ferramenta de pesquisa e apoio à decisão, com aprovação humana obrigatória; não como execução autônoma ou garantia de retorno.
