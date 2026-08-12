# Benevente Quant AI / Benevente Wealth System

**Benevente Quant AI** é o nome acadêmico do framework de pesquisa; **Benevente Wealth System** é sua apresentação comercial B2B.

Framework de pesquisa para backtest de alocação B3/CDI com sinais tipados, MVO determinístico e fricções operacionais modeladas.

## Princípios

- Decisão em cada rebalanceamento usa somente retornos até `T-1`.
- A camada de sinais não produz pesos: o otimizador convexo aplica os limites.
- Custos de transação (10 bps), slippage (5 bps) e limiar de turnover são contabilizados.
- O teto de 15% vale para ações; o CDI é a manga residual de liquidez. Aplicar 15% também ao CDI tornaria inviável a restrição de até 60% em ações.
- `--offline` produz dados sintéticos determinísticos para testes reprodutíveis; não representa mercado real.

## Executar

```powershell
python -m venv .venv-benevente
.\.venv-benevente\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py --offline
python paper_builder.py
python research_runner.py --output artifacts/real_data
python validate_research.py --input artifacts/real_data
python tune_hyperparameters.py --input artifacts/real_data --split 2025-01-01
python horizon_evaluation.py --output artifacts/horizons
python value_portfolio_runner.py --fundamentals data/my_point_in_time_fundamentals.csv --decision-date 2026-08-01 --horizon 5
python live_proposal_runner.py --policy data/my_production_policy.json --itr-year 2026 --market-snapshot data/my_market_snapshot.csv
python pilot_tracker.py --policy data/my_pilot_100k_policy.json --nav data/my_pilot_nav.csv
```

Os resultados ficam em `artifacts/`. A execução normal requer dados reais do `yfinance` e falha de forma explícita se não os obtiver; `--offline` é a única forma de usar dados sintéticos determinísticos.

`research_runner.py` é a execução empírica: salva os preços de entrada, séries macro, curvas, métricas, comparativos CDI/Ibovespa/MVO clássico e sensibilidade de custos. Não preencha artigos com os resultados de `--offline`.

`validate_research.py` faz as verificações independentes de integridade de séries, datas, valores nulos, recomposição da curva de patrimônio e conjunto de benchmarks.

`tune_hyperparameters.py` seleciona gamma e influência dos sinais antes de 2025 e mede o modelo selecionado somente a partir de 2025. O resultado fora da amostra deve ser apresentado separadamente.

`horizon_evaluation.py` executa janelas pré-definidas de 5, 10 e 15 anos, cada uma com um ano independente de lookback antes do início da avaliação. Não use os resultados dessas janelas para retroativamente escolher parâmetros.

## Seleção de valor e qualidade

O módulo de médio/longo prazo utiliza filtros determinísticos para evitar ações frágeis: capitalização e liquidez mínimas, geração positiva de caixa, ROIC/ROE mínimos, alavancagem e cobertura de juros. Só depois ele ranqueia valor e qualidade. O arquivo [fundamentals_point_in_time_template.csv](data/fundamentals_point_in_time_template.csv) define o contrato de dados: cada observação exige `available_date`, a data em que ficou pública. Sem esse arquivo preenchido por uma fonte histórica confiável, o sistema não produz uma recomendação — por desenho.

O custo padrão de swing trade é `ClearB3CostModel`: corretagem Clear de 0%, taxa B3 regular de 0,0300% por lado e slippage dependente da participação no volume. Ele gera uma carteira-sombra e um modelo de ordens para conciliação posterior com notas de corretagem.

## Proposta com dados reais — sem execução automática

`live_proposal_runner.py` baixa o ITR mais recente da CVM e o combina ao DFP anual anterior para calcular métricas TTM: DFP anual + ITR atual − ITR comparativo. A data de recebimento da CVM limita a disponibilidade da informação. Copie e complete [production_policy_template.json](data/production_policy_template.json) e forneça um [market_snapshot_template.csv](data/market_snapshot_template.csv) datado, atribuído à B3, corretora ou fornecedor licenciado. A rotina não consulta valores sem origem, não envia ordens e só pode ser seguida por entrada manual na corretora e reconciliação das notas.

Para o experimento prospectivo, [pilot_100k_policy.json](data/pilot_100k_policy.json) e [pilot_nav_template.csv](data/pilot_nav_template.csv) iniciam uma carteira-sombra de R$100 mil. `pilot_tracker.py` mede NAV, retorno líquido observado, drawdown, CDI e Ibovespa sem criar nem executar uma ordem.

## LLM opcional

O backtest usa `MockLLMAgents` determinístico por padrão, para manter reprodutibilidade e evitar chamadas pagas. `OpenAIStructuredAgents` é um adaptador opcional que requer `OPENAI_API_KEY` e valida a resposta contra JSON Schema/Pydantic antes de qualquer influência no otimizador. A API jamais gera pesos de carteira.

> Aviso: material educacional e de pesquisa. Não é recomendação de investimento nem validação de desempenho futuro.
