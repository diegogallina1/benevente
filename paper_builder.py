from pathlib import Path


def build_paper_files() -> None:
    Path("paper").mkdir(exist_ok=True)
    Path("docs").mkdir(exist_ok=True)
    Path("paper/ieee_cifer_2027.tex").write_text(r'''\documentclass[10pt,conference]{IEEEtran}
\usepackage{booktabs,graphicx}
\title{AlphaNet-B3: A Reproducible Multi-Agent Framework for Portfolio Optimization}
\author{Anonymous Authors}
\begin{document}\maketitle
\begin{abstract}This manuscript accompanies a reproducible B3/CDI portfolio-backtesting framework. Reported outcomes must be generated from the committed experiment artifacts, not pre-filled claims.\end{abstract}
\section{Method}The pipeline uses information available through $t-1$, typed confidence signals, and constrained mean--variance optimization with transaction costs and slippage.
\section{Reproducibility}Run \texttt{python main.py --offline}; use \texttt{artifacts/metrics.json} to populate results.
\end{document}
''', encoding="utf-8")
    Path("docs/fucape_btech_2026.md").write_text("""# CapInvest AI\n\n## Resumo executivo\nProtótipo reprodutível para apoio analítico à alocação de carteiras B3/CDI. Métricas devem ser preenchidas somente a partir dos artefatos executados do backtest.\n\n## Limitações\nBacktests não são garantia de desempenho futuro. O sistema não é recomendação de investimento.\n""", encoding="utf-8")


if __name__ == "__main__":
    build_paper_files()

