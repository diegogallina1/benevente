"""Demonstra o fluxo inteiro: perguntas, mapa e as duas portas do fim.

As perguntas definem o perfil pela restrição mais apertada. O mapa mede a
carteira contra ele. E aí aparecem dois caminhos, que este script imprime lado a
lado porque a comparação é a decisão: adequar entrega o método completo e cobra
o imposto na hora; adaptar quase não custa e entrega metade do método.

Imprimir os dois juntos é deliberado. Mostrar só um deles, e depois o outro, é
como se conduz alguém a uma escolha sem que perceba que houve escolha.
"""
from __future__ import annotations

from pathlib import Path
import json

from b3_connection import Qualidade
from client_intake import Intake, as_json, PROFILES
from portfolio_mapping import Bucket, Position, Source, adapt_portfolio, map_portfolio

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "portfolio_mapping_v1"


def brl(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def carteira_exemplo() -> list[Position]:
    """Carteira sintética de demonstração, com os casos que importam.

    A qualidade do custo de cada linha veio de research_b3_connection.py, que
    reconstrói o que a API da B3 permite reconstruir. A WEGE3 é o caso real e
    incômodo: comprada antes de 01/11/2019, chega com dois terços da posição sem
    nenhuma compra que a explique.
    """
    return [
        # já está na cesta do perfil, e no peso
        Position("CURY3", Bucket.ACAO, 44_000, 23_050, Source.B3_INVESTIDOR,
                 cost_quality=Qualidade.RECONSTRUIDO),
        # está na cesta, muito acima do peso e com ganho grande — mas o custo só
        # cobre um terço, então o imposto dela não é apurável
        Position("WEGE3", Bucket.ACAO, 180_000, 38_000, Source.B3_INVESTIDOR,
                 cost_quality=Qualidade.PARCIAL),
        # não está na cesta e tem prejuízo — a venda gera crédito
        Position("MGLU3", Bucket.ACAO, 25_000, 192_000, Source.B3_INVESTIDOR,
                 cost_quality=Qualidade.RECONSTRUIDO),
        # renda fixa de balcão: a B3 não manda valor nem custo, veio do escritório
        Position("CDB Banco Beta", Bucket.RENDA_FIXA, 310_000, 300_000,
                 Source.OPEN_FINANCE, conglomerate="Beta", days_held=500, liquid=False,
                 cost_quality=Qualidade.DECLARADO),
        Position("Tesouro Selic", Bucket.CAIXA, 120_000, 118_000, Source.B3_INVESTIDOR,
                 cost_quality=Qualidade.RECONSTRUIDO),
        # ativo fora do escopo: nunca passou pela B3
        Position("Cripto", Bucket.FORA_DO_ESCOPO, 21_000, 30_000, Source.MANUAL,
                 cost_quality=Qualidade.DECLARADO),
    ]


def respostas_exemplo() -> Intake:
    """Um cliente de exemplo: prazo longo, estômago médio, reserva feita."""
    return Intake(
        answers={"horizonte": "5_mais", "queda": "ate_20", "reserva": "sim", "retirada": "nao"},
        carried_loss_brl=0.0, locked_tickers=(),
    )


def _resumo(nome: str, mapa: dict) -> None:
    print(f"\n=== {nome} · {mapa['path_label']} ===")
    print(f"  módulos aplicados:  {', '.join(mapa['modules'])}")
    print(f"  giro necessário:    R$ {mapa['turnover_brl']:,.0f}")
    print(f"  execução:           R$ {mapa['transition_cost_brl']:,.0f}")
    print(f"  imposto apurado:    R$ {mapa['transition_tax_brl']:,.0f}")
    if not mapa["tax_is_complete"]:
        print(f"  INCOMPLETO:         R$ {mapa['unpriced_sale_brl']:,.0f} vendidos sem custo "
              f"apurável (" + ", ".join(p["ticker"]
                                        for p in mapa["positions_without_cost_basis"]) + ")")
    print(f"  custo da mudança:   R$ {mapa['transition_total_brl']:,.0f} "
          f"({mapa['transition_cost_pct']:.2%} do patrimônio)"
          + ("" if mapa["tax_is_complete"] else "  — piso, não total"))
    print(f"  histórico publicado descreve esta carteira: "
          f"{'sim' if mapa['track_record_applies'] else 'NÃO'}")


def alvo_do_perfil(perfil: str) -> tuple[dict, str]:
    """O livro declarado do perfil, lido de onde o site já o publica."""
    books = json.loads((ROOT / "web" / f"current_decision_2026_{perfil}.json")
                       .read_text(encoding="utf-8"))
    acoes = {h["ticker"]: h["weight"] for h in books["holdings"] if h["ticker"] != "IVVB11"}
    return ({"positions": acoes,
             "global_sleeve": next((h["weight"] for h in books["holdings"]
                                    if h["ticker"] == "IVVB11"), 0.0),
             "cash": books["cdi_weight"]}, books["decision_date"])


def main() -> None:
    alvo, decisao = alvo_do_perfil("equilibrado")
    books = {"decision_date": decisao}

    intake = respostas_exemplo()
    perfil = intake.assessment()
    posicoes = carteira_exemplo()
    kwargs = {"carried_loss_brl": intake.carried_loss_brl, "locked_tickers": intake.locked_tickers}

    print("PERGUNTAS")
    print(f"  {perfil['rationale']}")
    print(f"  pior queda medida deste perfil: {perfil['worst_measured_drawdown']:.1%}")

    adequar = map_portfolio(posicoes, alvo, **kwargs)
    adaptar = adapt_portfolio(posicoes, alvo, **kwargs)

    print(f"\nCARTEIRA de R$ {adequar['total_brl']:,.0f} · origem: "
          f"{len(adequar['sources'])} fonte(s)")
    print(f"  já aderente ao perfil {perfil['profile']}: {adequar['alignment']:.1%}")
    if adequar["fgc_breaches"]:
        print(f"  ALERTA FGC: {adequar['fgc_breaches']} acima de R$ 250.000 por conglomerado")

    _resumo("CAMINHO A", adequar)
    print(f"{'ativo':<16}{'ação':<10}{'de':>12}{'para':>12}  observação")
    for m in adequar["moves"]:
        nota = m["notes"][0] if m["notes"] else m["reason"]
        print(f"{m['ticker']:<16}{m['action']:<10}{m['from_brl']:>12,.0f}{m['to_brl']:>12,.0f}"
              f"  {nota[:46]}")

    _resumo("CAMINHO B", adaptar)
    print(f"  ações antes {adaptar['equity_before']:.1%} · orçamento do perfil "
          f"{adaptar['equity_budget']:.1%} · depois {adaptar['equity_after']:.1%}"
          + ("  (já abaixo do orçamento: nada é comprado)" if adaptar["equity_below_budget"] else ""))
    print(f"  teto por emissor: {adaptar['issuer_cap']:.1%} ({adaptar['issuer_cap_rule']})")
    if adaptar["tax_left_on_table_brl"] > 0:
        print(f"  prejuízo mantido sem realizar: R$ {adaptar['unrealised_loss_kept_brl']:,.0f} — "
              f"realizá-lo economizaria R$ {adaptar['tax_left_on_table_brl']:,.0f} de imposto")
    print(f"{'ativo':<16}{'ação':<10}{'de':>12}{'para':>12}  observação")
    for m in adaptar["moves"]:
        nota = m["notes"][0] if m["notes"] else m["reason"]
        print(f"{m['ticker']:<16}{m['action']:<10}{m['from_brl']:>12,.0f}{m['to_brl']:>12,.0f}"
              f"  {nota[:46]}")

    diferenca = adequar["transition_total_brl"] - adaptar["transition_total_brl"]
    print("\nA ESCOLHA")
    if diferenca > 0:
        print(f"  Adequar custa R$ {diferenca:,.0f} a mais agora, mexe em "
              f"R$ {adequar['turnover_brl'] - adaptar['turnover_brl']:,.0f} a mais, e é o único "
              f"caminho que o histórico publicado descreve.")
    else:
        # Contraintuitivo e verdadeiro: o plano completo realiza também os
        # prejuízos, e eles abatem o imposto dos ganhos. Manter pode sair caro.
        print(f"  Adequar custa R$ {abs(diferenca):,.0f} a MENOS agora, porque o plano "
              f"completo realiza também os prejuízos da carteira e eles abatem o imposto dos "
              f"ganhos na mesma cesta. Manter, aqui, é mais caro e entrega metade do método.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mapping_example.json").write_text(json.dumps({
        "status": "demonstration_only",
        "warning": "Carteira sintética escrita à mão para exercitar o módulo.",
        "target_profile": perfil["profile"], "target_decision": books["decision_date"],
        "intake": {"answers": intake.answers, "assessment": perfil, "questionnaire": as_json()},
        "mapping": adequar,
        "alternative": adaptar,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # A mesma carteira contra cada perfil da escada. A lista vem do questionário
    # em vez de repetida aqui: quando a escada ganhou um degrau, este arquivo
    # seguiu sozinho, e uma lista copiada teria deixado o degrau novo de fora
    # sem ninguém notar.
    # O protótipo da tela precisa dos
    # três porque o questionário pode terminar em qualquer um deles, e mostrar
    # sempre o mesmo mapa faria as perguntas parecerem decorativas.
    todos = {}
    for nome in PROFILES:
        livro, data = alvo_do_perfil(nome)
        todos[nome] = {"decision": data,
                       "adequar": map_portfolio(posicoes, livro, **kwargs),
                       "adaptar": adapt_portfolio(posicoes, livro, **kwargs)}
    (OUT / "mapping_by_profile.json").write_text(json.dumps({
        "status": "demonstration_only",
        "warning": "Carteira sintética escrita à mão para exercitar o módulo.",
        "questionnaire": as_json(),
        "profiles": todos,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nMapa nos três perfis:")
    for nome, dados in todos.items():
        print(f"  {nome:<13} adequar {brl(dados['adequar']['transition_total_brl']):>12} · "
              f"adaptar {brl(dados['adaptar']['transition_total_brl']):>12}")


if __name__ == "__main__":
    main()
