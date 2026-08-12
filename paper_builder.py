from pathlib import Path


def build_paper_files() -> None:
    Path("paper").mkdir(exist_ok=True)
    Path("docs").mkdir(exist_ok=True)
    Path("paper/ieee_cifer_2027.tex").write_text(r'''\documentclass[10pt,conference]{IEEEtran}
\usepackage{booktabs,graphicx}
\title{Benevente Quant AI: A Reproducible Multi-Agent Framework for Portfolio Optimization}
\author{Anonymous Authors}
\begin{document}\maketitle
\begin{abstract}We present Benevente Quant AI, a reproducible research framework for Brazilian equity and CDI portfolio allocation. The architecture separates structured confidence signals from deterministic constrained mean--variance optimization and models turnover-based transaction costs. Using an archived real-data run from January 2023 to June 2026, the strategy produced lower volatility and drawdown than a classic mean--variance portfolio and the Ibovespa, but underperformed CDI. These results do not support a claim of alpha; rather, they establish an auditable baseline and identify the conditions required for further validation.\end{abstract}
\section{Method}At each monthly rebalance, the decision uses returns and macro observations through $t-1$. A typed signal layer produces bounded confidence scores; a convex optimizer enforces full investment, non-negative weights, 15\% equity position limits, an equity cap, and a CDI residual sleeve. The backtest deducts 10 basis points of transaction cost plus 5 basis points of slippage per executed turnover.
\section{Empirical evaluation}The archived run covers 2 January 2023--30 June 2026, using adjusted B3 prices from Yahoo Finance and CDI, Selic and IPCA series from Banco Central do Brasil. Benevente Quant AI returned 22.98\% cumulatively (CAGR 8.93\%), with 9.95\% annualized volatility and a maximum drawdown of -4.87\%. It did not exceed CDI (34.23\% cumulative; CAGR 12.95\%); its Sharpe ratio relative to realized CDI was -0.32. Classic MVO had 20.00\% cumulative return, 13.74\% volatility and -7.30\% maximum drawdown; Ibovespa had 27.21\%, 19.92\%, and -14.81\%, respectively.
\section{Limitations and reproducibility}The fixed present-day ticker universe introduces survivorship bias, market prices come from a secondary source, and execution costs are modeled rather than observed. Every input series and result table is archived under \texttt{artifacts/real\_data}. Execute \texttt{python research\_runner.py} followed by \texttt{python validate\_research.py}; the offline mode is solely a deterministic software test.
\end{document}
''', encoding="utf-8")
    Path("docs/fucape_btech_2026.md").write_text("""# Benevente Wealth System\n\n## Resumo executivo\nSolução comercial B2B para apoio analítico à alocação de carteiras B3/CDI. A base acadêmica e experimental do produto é denominada Benevente Quant AI. Métricas devem ser preenchidas somente a partir dos artefatos executados do backtest.\n\n## Limitações\nBacktests não são garantia de desempenho futuro. O sistema não é recomendação de investimento.\n""", encoding="utf-8")


if __name__ == "__main__":
    build_paper_files()
