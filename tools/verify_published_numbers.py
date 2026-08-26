"""Every number the paper and the site state, asserted against the artifacts.

"Verified" here means machine-checked: each claim below either reproduces from a
versioned artifact within a stated tolerance or this script exits non-zero and
names the claim. A figure whose only source is a conversation transcript is not
allowed to survive — that rule already caught the cadence table once.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(("ok      " if ok else "FALHA   ") + label + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(label)


def close(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    # ---------------------------------------------------------------- A. par controlado
    g36 = json.loads((ROOT / "artifacts/configuration_search_control36_2026/summary.json").read_text(encoding="utf-8"))
    g256 = json.loads((ROOT / "artifacts/configuration_search_expanded_2026/summary.json").read_text(encoding="utf-8"))
    n36, n256, d36, d256 = g36["nested"], g256["nested"], g36["deflated_sharpe"], g256["deflated_sharpe"]
    check("G36 nested 15.31%", close(n36["cagr"], .1531, 5e-4))
    check("G256 nested 12.68%", close(n256["cagr"], .1268, 5e-4))
    check("delta -2.63 pp", close(n36["cagr"] - n256["cagr"], .0263, 1e-3))
    check("G36 pos-IR 13.89% / G256 11.64%",
          close(n36["cagr_after_tax"], .1389, 5e-4) and close(n256["cagr_after_tax"], .1164, 5e-4))
    check("sharpe excesso 0.452 / 0.368",
          close(n36["excess_sharpe_vs_cdi"], .452, 1e-3) and close(n256["excess_sharpe_vs_cdi"], .368, 1e-3))
    check("Ibov 5/10 vs 3/10", n36["years_beating_ibovespa"] == 5 and n256["years_beating_ibovespa"] == 3)
    check("switches 3 vs 4", n36["configuration_switches"] == 3 and n256["configuration_switches"] == 4)
    check("DSR 0.957 sig / 0.777 nao-sig",
          close(d36["deflated_sharpe_probability"], .957, 1e-3) and d36["significant_at_95"]
          and close(d256["deflated_sharpe_probability"], .777, 1e-3) and not d256["significant_at_95"])
    check("E[max|nulo] 0.375 -> 0.746",
          close(d36["expected_maximum_sharpe_under_null"], .375, 1e-3)
          and close(d256["expected_maximum_sharpe_under_null"], .746, 1e-3))
    check("sharpe observado 0.958 / 1.047",
          close(d36["observed_sharpe"], .958, 1e-3) and close(d256["observed_sharpe"], 1.047, 1e-3))

    ctl = pd.read_csv(ROOT / "artifacts/configuration_search_control36_2026/configuration_annual_returns.csv").set_index("decision_year")
    exp = pd.read_csv(ROOT / "artifacts/configuration_search_expanded_2026/configuration_annual_returns.csv").set_index("decision_year")
    shared = [c for c in ctl.columns if c in exp.columns]
    joined = ctl[shared].join(exp[shared], lsuffix="_a", rsuffix="_b").dropna()
    worst = max(abs(joined[f"{c}_a"] - joined[f"{c}_b"]).max() for c in shared)
    check("identidade bit a bit das 36 compartilhadas (<=1e-15)", len(shared) == 36 and worst <= 1e-15, f"{worst:.1e}")

    sel = pd.read_csv(ROOT / "artifacts/configuration_search_expanded_2026/nested_selection_annual.csv").set_index("decision_year")
    check("2018: low-vol escolhida, -7.2% contra caixa 6.4%",
          sel.loc[2018, "selected_configuration"] == "eq55_n8_low_volatility"
          and close(sel.loc[2018, "net_return"], -.072, 2e-3) and close(sel.loc[2018, "cdi_net_return"], .064, 2e-3))

    # ------------------------------------------------------- B. diagnóstico do fatorial
    # O diagnóstico do fatorial usa a MESMA janela do par controlado (2016–2025):
    # o CDI vem da própria seleção aninhada da rodada ampliada. Usar o CDI de
    # 2015–2025 aqui muda todos os Sharpe e foi exatamente o erro que este
    # verificador pegou na primeira execução.
    cdi = sel["cdi_net_return"]
    import re as _re
    NAME = _re.compile(r"eq(\d+)_(n|f)(\d+)(s\d+)?_(.+)")

    def excess_sharpe(series: pd.Series) -> float:
        s = series.dropna()
        e = (s - cdi.reindex(s.index)).dropna()
        return float(e.mean() / e.std(ddof=1))

    rows = []
    for c in exp.columns:
        eq, fam, size, sec, fac = NAME.match(c).groups()
        s = exp[c].dropna()
        w = (1 + s).cumprod()
        rows.append(dict(cfg=c, eq=int(eq), fam=fam, size=int(size), fac=fac,
                         cagr=w.iloc[-1] ** (1 / len(s)) - 1, pior=s.min(), sh=excess_sharpe(exp[c])))
    d = pd.DataFrame(rows)
    fm = d.groupby("fac").sh.mean()
    check("fator: triple 0.645 / value 0.481 / mom 0.424 / lowvol 0.293",
          close(fm["triple_factor"], .645, 2e-3) and close(fm["value_quality"], .481, 2e-3)
          and close(fm["momentum_12m"], .424, 2e-3) and close(fm["low_volatility"], .293, 2e-3))
    trio = [excess_sharpe(exp[f"eq{b}_n5_triple_factor"]) for b in (35, 55, 75)]
    check("orçamento é dial puro: sharpe 0.7602 invariável (eq35/55/75 n5 triple)",
          all(close(v, .7602, 5e-4) for v in trio))
    nfam = d[d.fam.eq("n")].groupby("size").agg(sh=("sh", "mean"), pior=("pior", "mean"))
    check("contagem em U: n5 0.472 / n20 0.512, pior médio n20 -3.8%",
          close(nfam.loc[5, "sh"], .472, 2e-3) and close(nfam.loc[20, "sh"], .512, 2e-3)
          and close(nfam.loc[20, "pior"], -.038, 2e-3))
    janela = exp.loc[exp.index >= 2015]
    corr = janela["eq55_n5_triple_factor"].corr(janela["eq55_n12_triple_factor"])
    check("correlação anual n5 x n12 = 0.93 (2015–2025)", close(corr, .934, 4e-3), f"{corr:.3f}")

    uni = pd.read_csv(ROOT / "artifacts/published_nested/annual_results.csv").set_index("decision_year").eligible_universe_size
    check("20 nomes = 74% do universo de 2016 e 21% do de 2025",
          close(20 / uni.loc[2016], .74, 1e-2) and close(20 / uni.loc[2025], .21, 1e-2))

    # ------------------------------------------------------------------- C. escada v2
    L = json.loads((ROOT / "web/ladder_v2.json").read_text(encoding="utf-8"))
    R = json.loads((ROOT / "data/benevente_profile_ladder_v2_registration.json").read_text(encoding="utf-8"))
    esperado = {"conservador": (.35, 12, .1339, -.1670, .1251, -.0916),
                "equilibrado": (.55, 8, .1637, -.2652, .1551, -.1786),
                "arrojado": (.75, 5, .2032, -.3564, .1987, -.2894)}
    for nome, (eqw, tops, c1, dd1, c2, dd2) in esperado.items():
        item = L["profiles"][nome]
        ok = (item["declared"]["maximum_equity_weight"] == eqw and item["declared"]["top_assets"] == tops
              and close(item["benevente1"]["cagr"], c1, 5e-4) and close(item["benevente1"]["max_drawdown"], dd1, 5e-4)
              and close(item["benevente2"]["cagr"], c2, 5e-4) and close(item["benevente2"]["max_drawdown"], dd2, 5e-4)
              and item["years_beating_cdi"] == 8 and item["years"] == 11)
        check(f"escada {nome}: declarado + B1/B2 + 8/11", ok)
        red = abs(item["benevente1"]["max_drawdown"] - item["benevente2"]["max_drawdown"]) * 100
        custo = (item["benevente1"]["cagr"] - item["benevente2"]["cagr"]) * 100
        check(f"escada {nome}: camada devolve {red:.2f} pp de queda por {custo:.2f} pp",
              6.7 - .05 <= red <= 8.7 + .05 and custo < 1.0)
    check("CDI 9.61% e Ibovespa 11.74% da fonte datada",
          close(L["references"]["CDI"]["cagr"], .0961, 5e-4) and close(L["references"]["Ibovespa"]["cagr"], .1174, 5e-4))
    check("selo e assinatura: evidência == registro",
          L["registration_sha256"] == R["registration_sha256"] and L["approved_by"] == R["approved_by"]
          and R["registration_sha256"].startswith("fc5521f1"))
    forbidden = json.dumps(R).lower()
    # Parâmetros de política com "drawdown" no nome (limiares do overlay) são
    # permitidos; estatísticas de resultado, não.
    check("registro sem estatística de desempenho",
          all(t not in forbidden for t in ('"cagr"', "realised_return", "observed_sharpe", "cumulative_return", "max_drawdown\"")))

    cand = pd.read_csv(ROOT / "artifacts/ladder_v2_candidates/ladder_v2_candidates.csv")
    pega = lambda p, r: float(cand[(cand.perfil.eq(p)) & (cand.regime.str.startswith(r))].sharpe_excesso.iloc[0])
    check("sharpe do par publicado sobe nos 3 (0.512→0.561, 0.507→0.603, 0.537→0.617)",
          close(pega("conservador", "3"), .512, 1e-3) and close(pega("conservador", "5"), .561, 1e-3)
          and close(pega("equilibrado", "3"), .507, 1e-3) and close(pega("equilibrado", "5"), .603, 1e-3)
          and close(pega("arrojado", "3"), .537, 1e-3) and close(pega("arrojado", "5"), .617, 1e-3))
    check("doméstico isolado: conservador 0.408 → 0.328",
          close(pega("conservador", "1"), .408, 1e-3) and close(pega("conservador", "2"), .328, 1e-3))

    # ------------------------------------------------------------ D. negativos auxiliares
    lw = pd.read_csv(ROOT / "artifacts/weighting_scheme_v1/ladder_by_weighting.csv")
    bw = pd.read_csv(ROOT / "artifacts/weighting_scheme_v1/basket_size_by_weighting.csv")
    lw["cfg"] = "perfil:" + lw.perfil
    bw["cfg"] = "cesta:n" + bw.posicoes.astype(str)
    both = pd.concat([lw[["cfg", "peso", "cagr", "sharpe_excesso", "dd_diario", "pior_ano"]],
                      bw[["cfg", "peso", "cagr", "sharpe_excesso", "dd_diario", "pior_ano"]]]).drop_duplicates(["cfg", "peso"])
    base = both[both.peso.eq("score")].set_index("cfg")
    inv = both[both.peso.eq("inverse_volatility")].set_index("cfg")
    idx = base.index.intersection(inv.index)
    dc = inv.loc[idx, "cagr"] - base.loc[idx, "cagr"]
    ds = inv.loc[idx, "sharpe_excesso"] - base.loc[idx, "sharpe_excesso"]
    ddd = inv.loc[idx, "dd_diario"] - base.loc[idx, "dd_diario"]
    check("peso: score vence inverse-vol em 8 de 8 (cagr e sharpe)",
          len(idx) == 8 and (dc < 0).all() and (ds < 0).all())
    check("peso: inverse-vol compra 0.95 pp de queda por 2.11 pp de retorno",
          close(dc.mean(), -.0211, 1e-3) and close(ddd.mean(), .0095, 1.5e-3))
    n16 = bw[bw.posicoes.eq(16)].set_index("peso")
    check("peso: n16 pior ano +0.50% -> -3.10% sob inverse-vol",
          close(n16.loc["score", "pior_ano"], .0050, 1e-3) and close(n16.loc["inverse_volatility", "pior_ano"], -.0310, 1e-3))

    rl = pd.read_csv(ROOT / "artifacts/profile_risk_layers_v1/risk_layers_by_profile.csv")
    meta = rl[rl.regime.str.contains("meta de vol anual")].set_index("perfil")
    escada = rl[rl.regime.str.startswith("escada (")].set_index("perfil")
    check("meta de vol: queda máxima intacta no conservador (-19.23% igual)",
          close(meta.loc["conservador", "drawdown"], escada.loc["conservador", "drawdown"], 1e-6)
          and close(escada.loc["conservador", "drawdown"], -.1923, 5e-4))

    # -------------------------------------------------------------------- E. cadência v2
    cadfile = ROOT / "artifacts/cadence_v2_profiles/cadence_by_profile.csv"
    if cadfile.exists():
        cad = pd.read_csv(cadfile)
        celula = lambda p, c: float(cad[(cad.perfil.eq(p)) & (cad.cadencia.eq(c))].vs_anual_pp.iloc[0])
        site = {("conservador", "semestral"): .13, ("conservador", "trimestral"): .03, ("conservador", "mensal"): -.98,
                ("equilibrado", "semestral"): .23, ("equilibrado", "trimestral"): -.96, ("equilibrado", "mensal"): -2.30,
                ("arrojado", "semestral"): -.33, ("arrojado", "trimestral"): -2.90, ("arrojado", "mensal"): -5.95}
        ok = all(close(celula(p, c), v, .03) for (p, c), v in site.items())
        check("cadência v2: as nove células da página batem com o artefato", ok)
    else:
        check("cadência v2: artefato persistido existe", False, "rode tools/persist_cadence_v2.py")

    # ----------------------------------------------------- F. o site repete o que os dados dizem
    versoes = (ROOT / "web/versoes.html").read_text(encoding="utf-8")
    for fig in ("−16,7", "−9,2", "−26,5", "−17,9", "−35,6", "−28,9", "0,512", "0,561", "0,507", "0,603", "0,537", "0,617", "0,408", "0,328"):
        check(f"versoes.html cita {fig}", fig.replace("−", "") in versoes.replace("−", ""))
    home = (ROOT / "web/index.html").read_text(encoding="utf-8")
    curva = L["monthly_curve"]["series"]
    for rotulo, chave in (("265,6", "Conservador"), ("388,6", "Equilibrado"), ("634,0", "Arrojado"), ("174,4", "CDI")):
        implied = curva[chave][-1] - 100
        check(f"home fallback {rotulo}% == fim da curva {chave}",
              rotulo in home and close(implied, float(rotulo.replace(",", ".")), .06))
    for page in ("quant-ai.html", "metodo.html", "index.html", "para-escritorios.html", "versoes.html", "limitacoes.html"):
        s = (ROOT / "web" / page).read_text(encoding="utf-8")
        check(f"{page} sem Ibovespa defasado (11,33/11.33/11,77/11.77)",
              all(x not in s for x in ("11,33", "11.33", "11,77", "11.77", "46,95", "46.95")))

    # ------------------------------------------------- F2. apuração por lote publicada
    lot = json.loads((ROOT / "artifacts/tax_lot_accounting/summary.json").read_text(encoding="utf-8"))
    drags = [run["equity_tax_drag_pp"] for run in lot["runs"]]
    check("site: arrasto do IR por lote 0,7–2,1 pp confere com o artefato",
          0.6 <= min(drags) <= 0.8 and 2.0 <= max(drags) <= 2.2)
    ratios = [run["lot_level_tax_brl"] / run["aggregate_annual_tax_brl"] for run in lot["runs"]]
    check("site: lote até 10% abaixo do agregado confere com o artefato",
          0.89 <= min(ratios) and max(ratios) < 1.0)
    metodo_page = (ROOT / "web/metodo.html").read_text(encoding="utf-8")
    limitacoes_page = (ROOT / "web/limitacoes.html").read_text(encoding="utf-8")
    check("método e limitações publicam a mesma faixa 0,7–2,1",
          "0,7 e 2,1" in metodo_page and "0,7 e 2,1" in limitacoes_page)

    # ------------------------------------------------- G. manuscritos não podem derivar
    btech = (ROOT / "paper/fucape_btech_2026.md").read_text(encoding="utf-8")
    cifer = (ROOT / "paper/ieee_cifer_2027.tex").read_text(encoding="utf-8")
    novo = (ROOT / "paper/declared_over_searched_2026.md").read_text(encoding="utf-8")
    check("BTech carrega o resultado posterior (256, 2,63 pp, 0,777, fc5521f1)",
          all(x in btech for x in ("256 candidatos", "2,63 pontos percentuais", "0,777", "fc5521f1")))
    check("BTech: oito hipóteses rejeitadas, não cinco",
          "Oito hipóteses foram testadas" in btech and "Cinco hipóteses foram testadas" not in btech)
    check("CiFer: regra aninhada como registro do período, não como vigente",
          "protocol of record for the period" in cifer and "The current protocol is nested" not in cifer)
    check("CiFer carrega o resultado posterior (2.63, 0.777, declared)",
          all(x in cifer for x in ("2.63 percentage points", "0.777", "declared and frozen per investor profile")))
    check("manuscrito novo: tabela do par com 1.047 (não 0.806) e faixa 6.7-8.7",
          "1.047" in novo and "| 0.806 |" not in novo and "6.7–8.7" in novo)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FALHA(S):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("TODOS OS NÚMEROS PUBLICADOS CONFEREM COM OS ARTEFATOS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
