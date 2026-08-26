# Declared Beats Searched: A Capacity Limit for Nested Configuration Selection in Annual Portfolio Rules

**Target venue:** IEEE CiFer (SSCI 2027). Companion to the governance paper; shares the evaluation infrastructure, claims nothing it does not measure.

**Draft status:** complete manuscript draft, English, all figures traceable to versioned artifacts. Author metadata, formatting to `IEEEtran`, and the final word budget are the authors' pass.

---

## Abstract

Nested (walk-forward) configuration selection is the standard defence against backtest overfitting: for each decision year, the configuration is ranked only on years already closed, so no year informs its own selection. We report a controlled experiment showing that this defence has a capacity limit in the number of candidates it can rank, and that exceeding it silently destroys the very property the procedure exists to protect. On identical inputs, code, and evaluation window (Brazilian equities, eleven annual decisions, 2015–2025 development sample), a nested search over 36 candidate configurations realises 15.31% a year with a deflated Sharpe probability of 0.957; the same procedure over 256 candidates — a grid containing the 36 as a strict subset — realises 12.68% with a deflated Sharpe of 0.777, below conventional significance, because the expected maximum Sharpe under the null rises from 0.375 to 0.746. The wider selector's trajectory shows the mechanism: with ten annual observations it ranks candidates on noise, at one point committing a full year to a configuration that returned −7.2% while cash returned 6.4%. We argue that when the observation count cannot support the candidate count, the honest alternative is to *declare* the configuration before the period and freeze it — registered with input hashes, a named approver, and a falsification criterion — rather than to search. We document the declared policy that replaced the search, the ancillary negative results that shaped it (inverse-volatility sizing lost to the incumbent weighting in 8 of 8 configurations; an annual volatility target cut exposure only after crises and never before one), and the two accepted risk layers whose combination was measured risk-matched rather than assumed additive. All results are development-sample diagnostics; prospective evaluation of the frozen policy begins with the first trading session of 2027.

**Keywords:** backtest overfitting; walk-forward analysis; deflated Sharpe ratio; model selection; preregistration; portfolio construction.

---

## 1. Introduction

A quantitative portfolio rule has free parameters — how many names, how much equity, which signal — and the standard temptation is to choose them by searching the historical sample. The standard rebuke is equally well known: the winner of a wide search is an order statistic, and the sample that ranked it can no longer test it (Bailey & López de Prado, 2014; White, 2000). The accepted middle path is *nested* selection: for decision year *t*, rank the candidates using only years that had closed before *t*, then evaluate year *t* once. The realised track is then, by construction, a sequence of choices each made without its own outcome.

This paper measures a failure mode of that middle path which, to our knowledge, is rarely quantified: the nested selector itself has a *capacity*, set by the number of out-of-sample observations available to its ranking step. An annual protocol accumulates one observation per year. Ranking 36 candidates on three-to-ten annual observations is already generous; ranking 256 is not a stronger version of the same procedure but a different and worse one, in which the ranking statistic's sampling error dominates the spread between candidates. Crucially, the failure is silent: the wider search runs without error, produces a plausible-looking track, and reports the same nested guarantee.

Our contribution is a controlled measurement of this effect and the design response it forced. We hold the data panel, the engine code, the evaluation window, and the selection statistic fixed, and vary only the candidate set — 36 configurations versus a superset of 256. We then document the replacement policy: one *declared* configuration per investor profile, frozen before the period with input hashes and a named human approver, plus the negative results that pruned its design space and the risk-matched measurement of its two accepted overlay layers.

The setting is deliberately unglamorous: annual selection of Brazilian equities from dated fundamentals, with survivorship-free prices reconstructed from the exchange's own archive. The infrastructure — receipt-date gating of filings, delisting-aware returns, liquidity-dependent costs, a Brazilian tax model — is shared with a companion governance paper and is not re-argued here.

## 2. Experimental design

### 2.1 Engine and data

The engine takes an annual decision at the first trading session of each year, using only prices and CVM filings whose *receipt dates* precede the decision. The price panel covers 514 issuers including 166 that stop trading, built from the B3 COTAHIST archive spliced with provider adjusted closes; delisting liquidates at the last observable price into cash. Execution cost is charged by participation in traded volume; Brazilian taxes follow the regressive fixed-income table and the 15% equity rate with realisation tied to actual turnover. A configuration is a tuple (equity budget, holding count or selectivity fraction, signal family, sector cap), with the per-issuer cap derived from budget and count so it never binds mechanically.

### 2.2 The controlled pair

Two runs differ *only* in the candidate grid:

- **G36:** equity budgets {55, 75, 95%} × counts {5, 8, 12} × four signal families (value/quality, triple-factor, 12-month momentum, low volatility). This is the historically published grid.
- **G256:** G36's axes extended with a 35% budget, counts up to 20, a proportional-selectivity family (hold a fixed *share* of the eligible universe, floored and capped), and an optional three-issuers-per-sector cap. G36 ⊂ G256.

Both use the same nested rule: rank by Sharpe of excess return over cash on all closed years (minimum three), charge a full-turnover rebalance on any configuration switch, evaluate the chosen configuration once. Identity of inputs was verified to the bit: the 36 shared configurations produce annual returns identical across the two runs to 5.6 × 10⁻¹⁷.

### 2.3 Why the wide grid is not a straw man

Every added axis was independently motivated. A fixed holding count is a moving target — twenty names were 74% of the 2016 eligible universe and 21% of 2025's, so the proportional family holds selectivity constant instead. The sector cap addresses a real governance gap (an undeclared five-name bet on one CVM sector in 2022). The 35% budget matches the conservative profile actually sold. G256 is, in other words, exactly the grid a diligent team would build next.

## 3. Results

### 3.1 The headline pair

| | G36 | G256 |
|---|---:|---:|
| Nested CAGR, 2016–2025 | **15.31%** | **12.68%** |
| After-tax CAGR | 13.89% | 11.64% |
| Excess Sharpe vs cash | 0.452 | 0.368 |
| Years beating the Ibovespa | 5 / 10 | 3 / 10 |
| Configuration switches | 3 | 4 |
| Observed Sharpe of the track | 0.958 | 1.047 |
| Expected max Sharpe under null | 0.375 | 0.746 |
| **Deflated Sharpe probability** | **0.957** | **0.777** |

Widening the search cost 2.63 percentage points a year of *realised* nested return — not of the hindsight winner, of the track an investor could actually have held — and moved the deflated Sharpe from significant to not. The null expectation nearly doubled because it grows with the log of the trial count while the observation count stayed at ten.

### 3.2 The mechanism, visible in the trajectory

The G256 selector's year-by-year choices show ranking noise directly. For 2018 it selected a low-volatility configuration (`eq55_n8_low_volatility`) on the strength of three training years; that configuration returned −7.2% in a year when cash returned 6.4% and the G36 selector's choice was mildly positive. For 2017 it chose a momentum configuration it abandoned a year later. Four switches in ten years, each charged as a full liquidation. With 256 candidates and at most ten ranking observations, the spread between the best candidates' true means is smaller than the sampling error of the ranking statistic; the argmax is then approximately a draw from the noise tail, and the switching cost is paid on top.

### 3.3 What the factorial itself says

Read as a *diagnostic* (marginal means across the full factorial over the same 2016–2025 window, never as a selection), the wide grid is informative. The triple-factor signal dominates every alternative (mean excess Sharpe 0.645 against 0.481, 0.424, 0.293). The equity budget is a pure risk dial: within a configuration family the excess Sharpe is invariant to it to four decimals. The holding count is U-shaped — five names have the highest raw return, twenty the best excess Sharpe (0.512) and the mildest worst year (−3.8%) — but the wider basket's annual returns are 0.93-correlated with the concentrated one's, so breadth buys idiosyncratic-risk reduction, not market protection. The sector cap binds in 20 of 128 paired configurations and improves the excess Sharpe in none of them; it survives as a governance constraint, not a performance claim.

None of this licenses picking the factorial's best cell. That is the same order statistic wearing a lab coat.

## 4. The declared alternative

### 4.1 Freezing instead of searching

The response to Section 3 was to stop selecting and start declaring: one configuration per investor profile, chosen from the diagnostic reading and from governance requirements, then frozen *before* the prospective period in a registration that records the SHA-256 of every input file and of the policy code, a named approver (the registration refuses to be created anonymously), the confirmatory start date (first trading session of 2027, minimum three annual decisions), and a falsification criterion (each profile must clear after-tax cash over the full window, and the realised risk ordering across profiles must not invert). The registration deliberately contains no performance statistic — a registration that reports a return is not a registration — and this is enforced by test.

The declared ladder:

| Profile | Equity | Names | Global sleeve | CAGR 2015–2025 | Max drawdown |
|---|---:|---:|---:|---:|---:|
| Conservative | 35% | 12 | 7% of portfolio | 12.51% | −9.16% |
| Balanced | 55% | 8 | 11% | 15.51% | −17.86% |
| Aggressive | 75% | 5 | 15% | 19.87% | −28.94% |
| Cash (CDI) | | | | 9.61% | 0% |
| Ibovespa (total return) | | | | 11.74% | −46.82% |

Each profile beat cash in 8 of 11 calendar years and the risk ordering is monotone. These are development-sample figures under the same caveat as everything else here.

### 4.2 The layers, and how their combination was measured

Two layers survived testing. A **declared global sleeve** — one fifth of the equity budget in a B3-listed S&P 500 fund, carved out of the budget rather than added — is the only tested axis that improved return and risk simultaneously: its daily correlation with the domestic sleeve is 0.064, and its annual correlation −0.52 — against the 0.93 annual correlation that more domestic names deliver. Roughly a third of its window return came from BRL depreciation, and the sleeve is described, on every surface that shows the number, as an unhedged long-dollar position. An **intra-year overlay** moves the domestic sleeve toward cash when Ibovespa drawdown and volatility, observed at the previous close, cross fixed thresholds; on the published stack it reduced maximum drawdown by 6.7–8.7 points per profile for under one point of annual return, and *raised* the excess Sharpe in all three profiles (0.512→0.561, 0.507→0.603, 0.537→0.617). Measured on the domestic book alone, however, the overlay lowers the conservative Sharpe (0.408 → 0.328) while halving its drawdown — the benefit lives in the tail, which Sharpe does not price, and a conservative profile judged by Sharpe alone would reject exactly the protection it most needs.

Because the sleeve is part of the equity the overlay would cut, their combination is not additive and was measured, not assumed. Two variants — fund inside the overlay's reach versus outside it — were compared *risk-matched*: the outside variant's domestic budget is solved so total equity lands exactly where the inside variant puts it, and the run asserts the match. Keeping the fund outside won in all three profiles (excess Sharpe 0.561/0.603/0.617 versus 0.482/0.511/0.546), consistent with the prior that cutting the uncorrelated asset on a domestic stress signal discards the reason for holding it. The registration discloses this as a selection over two candidates rather than presenting the winner as the only option considered.

### 4.3 Ancillary negative results

Three further hypotheses were rejected and are reported at equal detail, because a method whose failure inventory is hidden cannot be audited. **Inverse-volatility sizing** (and equal weighting, and a geometric blend) lost to the incumbent confidence weighting in 8 of 8 configurations, buying 0.95 points of drawdown for 2.11 points of annual return, and degraded *most* in the wide baskets where it was predicted to help. **An annual volatility target** cut exposure in 5 of 13 years, always after a visible stress and never before one — January 2020 was calm, so the year of the largest drawdown ran fully exposed and the maximum drawdown was unchanged to the day — while a post-crisis January (2016) was cut from 35% to 8.8% equity in a year the strategy returned +35%. **Faster reselection cadence** cost monotonically more the more concentrated the book (−2.90 points a year for quarterly reselection of the five-name profile; statistically indistinguishable from zero for the twelve-name profile), with no cell individually significant at eleven paired years.

## 5. Limitations

Eleven annual observations underpower every individual test; what supports each conclusion is consistency across configurations, not the magnitude of any cell. The whole 2015–2025 window is a development sample: factors, grids, constraints, and the decision to declare rather than search were all chosen while looking at it, and reproducing the computation demonstrates determinism, not out-of-sample validity. The overlay was designed after the crises it is evaluated on and reacts with a one-session lag. Distributions for issuers no provider still serves are imputed from the cross-section and flagged per ticker; primary-event reconciliation against exchange records is incomplete, which is why no institutional performance claim is made. The capacity argument is demonstrated in one market and one protocol; its quantitative boundary (how many candidates *n* years can rank) is left open, though the direction — degradation, not improvement, past the boundary — should generalise to any selector whose ranking statistic has sampling error comparable to the candidate spread.

## 6. Reproduction

All figures derive from versioned artifacts. The controlled pair: `research_configuration_search.py` with the input family documented in `docs/reproducao_configuration_search.md` (a wrong-but-plausible input family does not fail — it silently returns a different window; the telltale is the first decision year). The declared policy: `data/benevente_profile_ladder_v2_registration.json` (SHA-256 `fc5521f1…`), evaluated by `profile_ladder_v2.py --run`. Layer combination: `research_ladder_v2.py`, which asserts the risk match. Sizing, volatility-target, and cadence studies: `research_weighting_scheme.py`, `research_profile_risk_layers.py`, `research_cadence_and_exemption.py`. Published evidence for the demonstration site is generated from the registration by `tools/build_ladder_web_evidence.py`, so a page cannot state a number the registration does not imply.

## References

Bailey, D. H., & López de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. *Journal of Portfolio Management*, 40(5), 94–107.

Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance*, 20(4), 39–69.

DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? *Review of Financial Studies*, 22(5), 1915–1953.

Harvey, C. R., & Liu, Y. (2015). Backtesting. *Journal of Portfolio Management*, 42(1), 13–28.

White, H. (2000). A reality check for data snooping. *Econometrica*, 68(5), 1097–1126.
