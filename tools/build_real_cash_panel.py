"""Painel de preços com o caixa real no lugar do índice.

A v2 declarou como caixa a coluna ``TITULO_CDI``: 100% do CDI capitalizado
diariamente, um índice sem custódia, sem spread e sem rolagem. A v3 declara um
instrumento comprável no lugar dela — Tesouro Selic, reconstruído do arquivo
diário do Tesouro Transparente e líquido de custódia e de giro.

Trocar a coluna num arquivo próprio, em vez de dentro do motor, é o que permite
hashear a entrada, versioná-la e reproduzir a decisão anos depois. O nome da
coluna continua ``TITULO_CDI`` porque é o contrato que o motor conhece; o que
mudou é o que ela contém, e é isso que o manifesto registra.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PANEL = ROOT / "data" / "prices_b3_with_global_2011_2025.csv"
SOURCE_MANIFEST = ROOT / "data" / "prices_b3_with_global_2011_2025_manifest.json"
SELIC = ROOT / "data" / "tesouro_selic_cash_index.csv"
SELIC_MANIFEST = ROOT / "data" / "tesouro_selic_cash_index_manifest.json"
OUT = ROOT / "data" / "prices_b3_real_cash_2011_2025.csv"
OUT_MANIFEST = ROOT / "data" / "prices_b3_real_cash_2011_2025_manifest.json"
CASH_COLUMN = "TITULO_CDI"


def build() -> dict:
    panel = pd.read_csv(SOURCE_PANEL, parse_dates=["date"]).set_index("date").sort_index()
    if CASH_COLUMN not in panel.columns:
        raise SystemExit(f"O painel de origem não tem a coluna {CASH_COLUMN}.")

    selic = pd.read_csv(SELIC, parse_dates=["date"]).set_index("date")["level"]
    aligned = selic.reindex(panel.index).ffill()
    first = aligned.first_valid_index()
    if first is None or first > panel.index.min():
        # O Tesouro Selic começa em 2010 e o painel em 2011; se um dia isso
        # deixar de ser verdade, é melhor falhar do que preencher com o índice.
        if first is None:
            raise SystemExit("A série do Tesouro Selic não cobre o painel.")

    scale = float(panel.at[first, CASH_COLUMN]) / float(aligned.loc[first])
    swapped = panel.copy()
    swapped[CASH_COLUMN] = aligned * scale
    if swapped[CASH_COLUMN].isna().any():
        raise SystemExit("O caixa real ficou com buracos; recuse-se a publicar um painel incompleto.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    swapped.reset_index().to_csv(OUT, index=False)

    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    selic_manifest = json.loads(SELIC_MANIFEST.read_text(encoding="utf-8"))
    # A comparação é feita na janela avaliada, não no painel inteiro: a coluna de
    # caixa de origem é PLANA antes de 2013 — não tem dado — e comparar sobre ela
    # produziria um número sem sentido. O buraco é a segunda razão para trocar a
    # coluna: a série do Tesouro Selic é real desde 2010.
    def cagr(series: pd.Series, since: str) -> float:
        window = series[series.index >= pd.Timestamp(since)]
        span = (window.index.max() - window.index.min()).days / 365.25
        return float(window.iloc[-1] / window.iloc[0]) ** (1 / span) - 1

    flat_until = None
    for year in sorted({d.year for d in panel.index}):
        block = panel[CASH_COLUMN][panel.index.year == year]
        if len(block) > 1 and abs(block.iloc[-1] / block.iloc[0] - 1) < 1e-9:
            flat_until = year
        else:
            break
    published, real = cagr(panel[CASH_COLUMN], "2015-01-01"), cagr(swapped[CASH_COLUMN], "2015-01-01")

    manifest = {
        **{k: v for k, v in source_manifest.items() if k not in ("sha256", "generated_at")},
        "derived_from": {"panel": SOURCE_PANEL.name,
                         "panel_sha256": hashlib.sha256(SOURCE_PANEL.read_bytes()).hexdigest(),
                         "cash_series": SELIC.name,
                         "cash_series_sha256": selic_manifest["sha256"]},
        "cash_column": CASH_COLUMN,
        "cash_instrument": "Tesouro Selic, líquido de custódia B3 e de spread de rolagem",
        "cash_rules": selic_manifest["rules"],
        "cash_cagr_evaluated_window_2015_2025": {"index_100pct_cdi": round(published, 6),
                                                 "real_instrument": round(real, 6)},
        "defect_repaired": {
            "issue": f"a coluna de caixa do painel de origem é plana até {flat_until} — não tem dado",
            "effect": ("A escada declarada avalia a partir de 2015 e não é afetada. A busca aninhada "
                       "arquivada, sim: ela ordena configurações pelos anos encerrados antes de cada "
                       "decisão, e 2012 entra em todas as ordenações com o caixa rendendo zero, o que "
                       "penaliza configurações mais defensivas. Como as duas pontas do experimento de "
                       "capacidade (36 e 256 candidatos) usaram o mesmo insumo, a comparação entre elas "
                       "permanece válida; o que não se pode afirmar é que a ordenação de 2015 a 2025 "
                       "teria sido a mesma com o caixa correto."),
            "repair": "A série do Tesouro Selic é real desde 2010, então este painel não tem o buraco.",
        },
        "note": ("Mesmas colunas de ações e mesmo IVVB11 do painel de origem. A única diferença é o "
                 "conteúdo da coluna de caixa, e ela é a razão de existir deste arquivo."),
        # O adaptador confere ``file_sha256`` antes de deixar o painel virar insumo
        # de desempenho. O nome do campo é o contrato dele, não uma escolha nossa.
        "file_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "cdi_source": ("Tesouro Selic (LFT) do Tesouro Transparente, líquido de custódia e de rolagem; "
                       "substitui a série 12 do BCB usada no painel de origem"),
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    manifest = build()
    cash = manifest["cash_cagr_evaluated_window_2015_2025"]
    print(f"{OUT.name}: caixa 2015-2025 {cash['index_100pct_cdi']*100:.2f}% (índice) -> "
          f"{cash['real_instrument']*100:.2f}% (Tesouro Selic real)")
    print(f"defeito reparado: {manifest['defect_repaired']['issue']}")
    print(f"file_sha256 {manifest['file_sha256'][:16]}…")


if __name__ == "__main__":
    main()
