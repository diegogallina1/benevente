# Benevente Quant AI / Benevente Wealth System

**Benevente Quant AI** é o nome acadêmico do framework de pesquisa; **Benevente Wealth System** é sua apresentação comercial B2B. O repositório mantém o identificador técnico `alphanet-b3` por compatibilidade.

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
```

Os resultados ficam em `artifacts/`. A execução sem `--offline` tenta baixar dados com `yfinance`, mas mantém fallback explícito e determinístico.

> Aviso: material educacional e de pesquisa. Não é recomendação de investimento nem validação de desempenho futuro.
