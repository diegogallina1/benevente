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
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py --offline
python paper_builder.py
python research_runner.py --output artifacts/real_data
python validate_research.py --input artifacts/real_data
python tune_hyperparameters.py --input artifacts/real_data --split 2025-01-01
```

Os resultados ficam em `artifacts/`. A execução normal requer dados reais do `yfinance` e falha de forma explícita se não os obtiver; `--offline` é a única forma de usar dados sintéticos determinísticos.

`research_runner.py` é a execução empírica: salva os preços de entrada, séries macro, curvas, métricas, comparativos CDI/Ibovespa/MVO clássico e sensibilidade de custos. Não preencha artigos com os resultados de `--offline`.

`validate_research.py` faz as verificações independentes de integridade de séries, datas, valores nulos, recomposição da curva de patrimônio e conjunto de benchmarks.

`tune_hyperparameters.py` seleciona gamma e influência dos sinais antes de 2025 e mede o modelo selecionado somente a partir de 2025. O resultado fora da amostra deve ser apresentado separadamente.

## LLM opcional

O backtest usa `MockLLMAgents` determinístico por padrão, para manter reprodutibilidade e evitar chamadas pagas. `OpenAIStructuredAgents` é um adaptador opcional que requer `OPENAI_API_KEY` e valida a resposta contra JSON Schema/Pydantic antes de qualquer influência no otimizador. A API jamais gera pesos de carteira.

> Aviso: material educacional e de pesquisa. Não é recomendação de investimento nem validação de desempenho futuro.
