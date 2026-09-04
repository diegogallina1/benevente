"""A decisão de janeiro de 2026 nos três perfis declarados.

O acompanhamento corrente publicava um livro só, escolhido pela configuração
que a busca aninhada deixou viva antes de a política ser declarada. Enquanto o
explorador mostra onze anos reconstruídos nos três perfis, 2026 aparecia como
outra coisa — e o leitor não tem como saber que a diferença existe.

Este programa aplica a política congelada à data de 02/01/2026, com o universo
B3 daquela data, a ponte B3/CVM auditada e apenas os formulários ITR e DFP
recebidos pelo regulador antes dela. A triagem roda uma vez; cada perfil corta
dela o próprio número de emissores, com o próprio orçamento e o próprio teto.

Um ponto que precisa ficar explícito: reconstruir hoje uma decisão de janeiro
não introduz retrospectiva porque a política é **declarada**. Não há nada para
escolher — orçamento, número de nomes, tetos e fatores estavam congelados e
assinados antes desta execução. É a mesma razão pela qual reconstruir 2015 é
legítimo. O que seria ilegítimo é ajustar qualquer parâmetro olhando 2026, e o
registro existe exatamente para tornar isso verificável.

Uma advertência que sobrevive: o histórico anterior a 2013 não entra em nada
aqui, e o acompanhamento de 2026 usa preço de fechamento sem ajuste de
proventos, então o retorno parcial subestima as ações que pagaram dividendos.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import json
import sys

import pandas as pd

from advisor import snapshots_from_frame
from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 _price_column_for_ticker, _recent_market_sessions)
from build_current_2026_decision import current_mapping
from build_full_b3_cvm_fundamentals import build_full_panel
from config import SystemConfig
from profile_ladder_v2 import GLOBAL_FRACTION, LADDER_V2, _issuer_cap, domestic_protocol
from research_global_sleeve import GLOBAL_TICKER

ROOT = Path(__file__).resolve().parent
FACTOR = "triple_factor"
LIQUIDITY_FLOOR_BRL = 10_000_000

#: O ano da decisão sai do retrato do universo, e não de uma constante nem de um
#: sinalizador na linha de comando.
#:
#: A razão é evitar um erro específico: com o ano escrito à parte, dá para rodar
#: a lógica de um ano sobre os insumos de outro e receber uma carteira que
#: parece certa. Sendo propriedade do insumo, o ano e os dados não têm como se
#: separar. Quem quiser decidir 2027 troca o retrato, e o resto acompanha.
def ano_da_decisao(universe: "pd.DataFrame") -> int:
    return int(pd.Timestamp(universe.decision_date.iloc[0]).year)


def _screen_inputs(price_path, universe_path, mapping_path, cvm_cache, destination):
    """Universo datado, ponte auditada, fundamentos recebidos antes da decisão."""
    universe = pd.read_csv(universe_path)
    ano = ano_da_decisao(universe)
    universe["universe_year"] = ano
    prior = pd.read_csv(mapping_path, dtype={"ticker": str, "isin": str, "cnpj_cia": str})
    mapping = current_mapping(universe, prior, ano)

    liquid = universe[universe.average_daily_value_brl.ge(LIQUIDITY_FLOOR_BRL)].copy()
    fundamentals, coverage = build_full_panel(liquid, mapping, ano, ano, Path(cvm_cache))
    destination.mkdir(parents=True, exist_ok=True)
    fundamentals.to_csv(destination / f"fundamentals_{ano}.csv", index=False)
    coverage.to_csv(destination / f"fundamental_coverage_{ano}.csv", index=False)
    mapping.to_csv(destination / f"identifier_bridge_{ano}.csv", index=False)

    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date").sort_index()
    decision = pd.Timestamp(universe.decision_date.iloc[0])
    snapshots = snapshots_from_frame(fundamentals)
    known = [item for item in snapshots if pd.Timestamp(item.available_date) <= decision]

    prior_prices = prices.loc[prices.index < decision]
    columns = {item.ticker: _price_column_for_ticker(item.ticker, prior_prices.columns) for item in known}
    sessions = _recent_market_sessions(prices, decision, 252)
    complete = [t for t, c in columns.items() if c and prior_prices.loc[sessions, c].notna().all()]
    known = [item for item in known if item.ticker in complete]
    history = (prior_prices.loc[sessions, [*(columns[t] for t in complete), "TITULO_CDI"]]
               .rename(columns={columns[t]: t for t in complete}).pct_change().dropna())
    issuer_ids = {r.ticker: str(r.cnpj_cia) for r in
                  mapping[["ticker", "cnpj_cia"]].drop_duplicates("ticker").itertuples(index=False)}
    return {"ano": ano, "universe": universe, "liquid": liquid, "mapping": mapping, "fundamentals": fundamentals,
            "prices": prices, "decision": decision, "known": known, "history": history,
            "issuer_ids": issuer_ids, "engine": AnnualWalkForwardEngine(prices, snapshots, SystemConfig())}


def book_for_profile(profile: str, inputs: dict) -> dict:
    """O livro de um perfil: cesta doméstica, perna global e caixa."""
    declared = LADDER_V2[profile]
    budget, count = declared["maximum_equity_weight"], declared["top_assets"]
    global_share = round(budget * GLOBAL_FRACTION, 6)
    ano = inputs["ano"]
    domestic = domestic_protocol(profile, ano, ano + 1)

    protocol = AnnualWalkForwardConfig(
        ano, ano + 1, factor=FACTOR,
        maximum_equity_weight=domestic.maximum_equity_weight,
        maximum_asset_weight=domestic.maximum_asset_weight,
        top_assets=count, maximum_names_per_sector=domestic.maximum_names_per_sector)

    history, active = inputs["history"], list(inputs["history"].columns)
    proposal = inputs["engine"].triple_factor_proposal(
        history.tail(252), inputs["known"], inputs["decision"], pd.Series(0.0, index=active),
        protocol, float(SystemConfig().initial_portfolio_value_brl), inputs["issuer_ids"])

    weights = proposal.weights.reindex(active, fill_value=0.0)
    held = [t for t in weights.index if t != "TITULO_CDI" and weights[t] > 1e-6]
    scores = proposal.screen.set_index("ticker").factor_score

    # Os pesos vêm do sub-livro doméstico; a perna global é carregada fora dele,
    # então tudo escala por (1 - fração global) antes de somar o fundo.
    positions = sorted(
        ({"ticker": t.removesuffix(".SA"),
          "weight": round(float(weights[t]) * (1 - global_share), 6),
          "score": round(float(scores.get(t, float("nan"))), 4)} for t in held),
        key=lambda row: -row["weight"])
    domestic_total = round(sum(p["weight"] for p in positions), 6)
    return {
        "profile": profile,
        "declared": {"maximum_equity_weight": budget, "top_assets": count,
                     "maximum_asset_weight": _issuer_cap(budget, count),
                     "global_share_of_portfolio": global_share},
        "positions": positions,
        "domestic_equity": domestic_total,
        "global_sleeve": global_share,
        "global_instrument": GLOBAL_TICKER,
        "cash": round(1 - domestic_total - global_share, 6),
        "issuers": len(positions),
    }


def escala_de(base: dict, degrau: str, origem: str) -> dict:
    """O livro de um degrau derivado: a carteira da origem, inteira, em escala.

    Escala tudo pelo mesmo fator, inclusive a perna global, e a diferença vai
    para o caixa. Nenhum papel entra, sai ou troca de posição relativa: é a
    mesma seleção, com menos dinheiro em cima dela. É isso que separa derivar de
    decidir, e é o que a regra do degrau autoriza.
    """
    declarado_no_degrau = LADDER_V2[degrau]
    fator = declarado_no_degrau["maximum_equity_weight"] / LADDER_V2[origem]["maximum_equity_weight"]
    posicoes = [dict(p, weight=round(p["weight"] * fator, 6)) for p in base["positions"]]
    domestico = round(sum(p["weight"] for p in posicoes), 6)
    global_share = round(base["global_sleeve"] * fator, 6)
    return {
        "profile": degrau,
        "declared": {"maximum_equity_weight": declarado_no_degrau["maximum_equity_weight"],
                     "top_assets": declarado_no_degrau["top_assets"],
                     "maximum_asset_weight": _issuer_cap(declarado_no_degrau["maximum_equity_weight"],
                                                         declarado_no_degrau["top_assets"]),
                     "global_share_of_portfolio": global_share},
        "positions": posicoes,
        "domestic_equity": domestico,
        "global_sleeve": global_share,
        "global_instrument": GLOBAL_TICKER,
        "cash": round(1 - domestico - global_share, 6),
        "issuers": len(posicoes),
        "derivation": {
            "derived_from": origem,
            "factor": round(fator, 6),
            "method": "escala da carteira inteira, sem nova triagem",
            "decided_on": "2026-09-04",
            "record": "data/decisao_metodo_do_ultraconservador_2026-09-04.json",
        },
    }


def build(price_path, universe_path, mapping_path, cvm_cache, output) -> dict:
    destination = Path(output)
    inputs = _screen_inputs(price_path, universe_path, mapping_path, cvm_cache, destination)
    # O registro vem da política vigente, não de um caminho escrito à mão: era
    # assim que dois registros conseguiam se dizer vigentes ao mesmo tempo.
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    from politica import REGISTRO
    registration = json.loads(REGISTRO.read_text(encoding="utf-8"))
    # O ultraconservador é DERIVADO, não decidido, e a escolha do método é de
    # 04/09/2026: ele escala a carteira do conservador em vez de refazer a
    # triagem sob o próprio teto por ativo.
    #
    # Os dois caminhos davam a mesma fração em ações e distribuições diferentes
    # entre os doze papéis, e o site publicava um enquanto o gerador produzia o
    # outro. A regra do quarto degrau diz que ela "moveu o teto de ações, e só
    # ele", e que o degrau herda a camada do conservador em vez de ganhar
    # parâmetros próprios escolhidos depois de ver resultado. Recalcular a
    # triagem sob um teto por ativo próprio é uma segunda decisão sobre pesos, e
    # a declaração não autoriza uma. Escalar é o que ela descreve.
    #
    # A decisão está registrada em data/decisao_metodo_do_ultraconservador_2026-09-04.json.
    derivados = {"ultraconservador": "conservador"}
    books = {p: book_for_profile(p, inputs) for p in LADDER_V2 if p not in derivados}
    for degrau, origem in derivados.items():
        books[degrau] = escala_de(books[origem], degrau, origem)
    books = {p: books[p] for p in LADDER_V2}

    # Carteira com menos nomes do que a política declara não é a carteira da
    # política: é o que sobrou da triagem, publicado com o nome dela.
    #
    # O ensaio do workflow encontrou isto: com o cache da CVM incompleto, a
    # triagem de 2025 enxergou quatro fundamentos em vez de cento e quinze, e
    # saíram livros de três emissores onde o conservador declara doze. Nada
    # reclamou. Numa execução de janeiro com a CVM meio fora do ar, o resultado
    # seria uma cesta de três nomes publicada como o conservador declarado.
    #
    # Falhar aqui é a resposta certa: a decisão do ano pode esperar o dia
    # seguinte, e a janela do portão vai até 15 de janeiro exatamente para isso.
    curtos = [f"{nome}: {livro['issuers']} emissores, a política declara {LADDER_V2[nome]['top_assets']}"
              for nome, livro in books.items()
              if livro["issuers"] < LADDER_V2[nome]["top_assets"]]
    if curtos:
        raise SystemExit(
            "decisão recusada: a triagem não preencheu o número de emissores declarado.\n  "
            + "\n  ".join(curtos)
            + f"\n\nA triagem viu {len(inputs['known'])} papéis com fundamento e histórico completo. "
              "Confira se os formulários da CVM e o painel de preços cobrem a data antes de decidir.")
    # Reconstrução e decisão não são a mesma coisa, e a diferença é a data em
    # que isto rodou. Escrito à mão, o campo dizia "reconstrução" mesmo quando a
    # decisão fosse tomada no dia — que é exatamente o que 2027 exige para a
    # amostra confirmatória valer. Agora ele sai da comparação, não da memória.
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    reconstrucao = hoje > inputs["decision"].date()
    result = {
        "decision_date": str(inputs["decision"].date()),
        "generated_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "status": ("reconstrucao_sob_politica_congelada" if reconstrucao
                   else "decisao_tomada_na_data"),
        "policy": registration["policy"],
        "registration_sha256": registration["registration_sha256"],
        "approved_by": registration["approved_by"],
        # A frase acompanha o que o livro de fato é. Escrita fixa, ela diria
        # "reconstrução, não validação prospectiva" também no dia em que a
        # decisão passar a ser tomada na data — e aí estaria negando a única
        # coisa que a amostra confirmatória precisa afirmar.
        "honesty": (
            "A política é declarada e foi congelada antes desta execução, então aplicá-la a uma data "
            "passada não escolhe nada: orçamento, número de nomes, tetos e fatores já estavam assinados. "
            f"A amostra confirmatória começa em {registration['confirmatory_sample_starts']} — este livro é "
            "reconstrução, não validação prospectiva."
            if reconstrucao else
            "A decisão foi tomada na própria data, com o universo, a ponte e os fundamentos disponíveis "
            "nela, sob política congelada e assinada antes. Não é reconstrução: é a decisão do ano, e "
            f"a amostra confirmatória declarada começa em {registration['confirmatory_sample_starts']}."),
        "universe": {
            "all_instruments": int(len(inputs["universe"])),
            "equities_at_decision": int(inputs["universe"].asset_class.eq("equity").sum()),
            "identifier_bridge_accepted": int(len(inputs["mapping"])),
            "liquid_equities_examined": int(len(inputs["liquid"][inputs["liquid"].asset_class.eq("equity")])),
            "fundamental_snapshots": int(len(inputs["fundamentals"])),
            "screened_with_complete_price_history": int(len(inputs["known"])),
        },
        "books": books,
        "limitations": [
            "Não é recomendação individual nem ordem de compra.",
            "O acompanhamento usa preço de fechamento da B3 sem ajuste de proventos: o retorno parcial "
            "subestima ações que pagaram dividendos no período.",
            "A seleção exige ponte B3/CVM auditada e fundamentos comparáveis; emissores sem os dois "
            "ficam fora da triagem e isso está no arquivo de cobertura.",
        ],
    }
    (destination / f"profile_books_{inputs['ano']}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prices", default="data/prices_b3_cotahist_2011_2026.csv")
    parser.add_argument("--universe", default="artifacts/b3_universe_january_2026.csv")
    # A ponte precisa trazer a coluna isin: current_mapping funde por ticker E
    # isin, de propósito, para não carregar um vínculo por nome de papel. O
    # padrão apontava para uma exportação sem essa coluna, e quem rodasse o
    # comando como documentado recebia KeyError em vez da carteira.
    parser.add_argument("--mapping", default="data/b3_historical_cvm_ticker_map_2012_2025.csv")
    parser.add_argument("--cache-dir", default="work/cvm_cache")
    parser.add_argument("--output", default="artifacts/profile_books_2026")
    # Decidir a partir da captura, e não dos arquivos vivos, é o que torna a
    # carteira reproduzível anos depois: os bytes ficam congelados no dia, com
    # hash, e quem conferir lê os mesmos. Dois dos quatro insumos mudam sozinhos
    # com o tempo, então sem isso a reprodução depende de sorte.
    parser.add_argument("--insumos", type=Path, default=None,
                        help="Pasta de captura criada por tools/capturar_insumos.py.")
    args = parser.parse_args()
    prices, universe, mapping = args.prices, args.universe, args.mapping
    if args.insumos:
        manifesto = json.loads((args.insumos / "manifesto.json").read_text(encoding="utf-8"))
        caminhos = {item["papel"]: args.insumos / item["arquivo"] for item in manifesto["files"]}
        prices, universe, mapping = caminhos["prices"], caminhos["universe"], caminhos["mapping"]
        print(f"decidindo a partir da captura de {manifesto['decision_date']} "
              f"(manifesto {manifesto['manifest_sha256'][:12]})")
    result = build(prices, universe, mapping, args.cache_dir, args.output)
    print(f"decisão de {result['decision_date']} sob {result['policy']}\n")
    for name, book in result["books"].items():
        nomes = ", ".join(p["ticker"] for p in book["positions"])
        print(f"{name:<12} ações {book['domestic_equity']:.1%} · {GLOBAL_TICKER} {book['global_sleeve']:.1%} · "
              f"caixa {book['cash']:.1%}  ({book['issuers']} emissores)")
        print(f"             {nomes}")


if __name__ == "__main__":
    main()
