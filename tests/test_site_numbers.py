"""The site may not state a number the published evidence does not imply.

Three separate drifts got through review before this test existed. Pages that
were not edited kept the retired rule's figures while the pages next to them
showed the ladder. The chart plotted one strategy while the summary underneath
it described another. And a builder field counted years against cash on a series
nobody is offered, disagreeing with the prose by one year in every profile.

Each of those is invisible to a human reviewer reading one page at a time, and
each is exactly the kind of error this project's audit history exists to catch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
EVIDENCE = json.loads((WEB / "ladder_v2.json").read_text(encoding="utf-8"))
REGISTRATION = json.loads(
    (ROOT / "data" / "benevente_profile_ladder_v3_registration.json").read_text(encoding="utf-8"))
PAGES = {path.name: path.read_text(encoding="utf-8") for path in sorted(WEB.glob("*.html"))}

# Figures produced by the nested search that the declared ladder replaced. They
# remain reproducible in artifacts/configuration_search_2012/ and are correct
# about the rule they describe; they are simply not true of any live policy.
# A page that needs to cite one as history must be added to RETIRED_ALLOWED with
# the reason, so the exception is a decision rather than an oversight.
RETIRED = {
    "17,86%": "CAGR da seleção aninhada aposentada",
    "18,45%": "CAGR do Benevente 2 sob a regra aposentada",
    "509,8%": "acumulado do Benevente 1 aposentado",
    "543,8%": "acumulado do Benevente 2 aposentado",
    "22,93%": "volatilidade da regra aposentada",
    "28,75%": "queda máxima do Benevente 2 aposentado",
    "47,78%": "queda máxima do Benevente 1 aposentado",
    "11,77%": "Ibovespa medido sobre a curva do motor, que deriva",
}
RETIRED_ALLOWED: dict[str, set[str]] = {}


def _pt(value: float, digits: int = 2, percent: bool = True) -> str:
    """Format like the pages do: comma decimal, optional percent sign."""
    number = value * 100 if percent else value
    text = f"{number:,.{digits}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{text}%" if percent else text


def _normalise(text: str) -> str:
    """The pages use a typographic minus; a formatted number uses a hyphen."""
    return text.replace("−", "-").replace("–", "-")


@pytest.mark.parametrize("page", sorted(PAGES))
def test_no_page_restates_a_retired_figure(page: str) -> None:
    source = PAGES[page]
    for figure, meaning in RETIRED.items():
        if page in RETIRED_ALLOWED.get(figure, set()):
            continue
        # A retired CAGR of 17,86% and a live drawdown of -17,86% are the same
        # digits; only the sign separates them, so the sign is part of the match.
        pattern = r"(?<![-−\d,])" + re.escape(figure)
        assert not re.search(pattern, source), (
            f"{page} publica {figure} ({meaning}). Se a citação for histórica e deliberada, "
            f"acrescente a página a RETIRED_ALLOWED com o motivo."
        )


def test_published_evidence_matches_the_frozen_registration() -> None:
    assert EVIDENCE["policy"] == REGISTRATION["policy"]
    assert EVIDENCE["registration_sha256"] == REGISTRATION["registration_sha256"]
    assert EVIDENCE["approved_by"] == REGISTRATION["approved_by"]
    for name, item in EVIDENCE["profiles"].items():
        declared, frozen = item["declared"], REGISTRATION["profiles"][name]
        for field in ("maximum_equity_weight", "top_assets", "maximum_asset_weight",
                      "global_share_of_portfolio"):
            assert declared[field] == frozen[field], f"{name}.{field} divergiu do registro"


@pytest.mark.parametrize("name", sorted(EVIDENCE["profiles"]))
def test_every_profile_figure_appears_somewhere_on_the_site(name: str) -> None:
    """A published number must exist in the evidence, and be shown at least once."""
    item = EVIDENCE["profiles"][name]
    everything = _normalise("".join(PAGES.values()))
    for label, value in (("CAGR", item["benevente2"]["cagr"]),
                         ("queda", item["benevente2"]["max_drawdown"])):
        assert _pt(value) in everything, f"{name}: {label} {_pt(value)} não aparece em nenhuma página"


def test_the_chart_curve_agrees_with_the_profile_metrics() -> None:
    """The plotted path and the stated CAGR must be the same object.

    They were not: the chart read the retired series while the table beside it
    was built from a different file.
    """
    curve = EVIDENCE["monthly_curve"]
    years = len({date[:4] for date in curve["dates"]})
    labels = {"conservador": "Conservador", "equilibrado": "Equilibrado", "arrojado": "Arrojado"}
    for name, label in labels.items():
        values = curve["series"][label]
        implied = (values[-1] / values[0]) ** (1 / years) - 1
        stated = EVIDENCE["profiles"][name]["benevente2"]["cagr"]
        assert implied == pytest.approx(stated, abs=5e-4), (
            f"{label}: a curva do gráfico implica {implied:.4%} e a métrica publicada diz {stated:.4%}"
        )


def test_the_chart_carries_the_references_it_is_compared_against() -> None:
    curve = EVIDENCE["monthly_curve"]
    years = len({date[:4] for date in curve["dates"]})
    # A v3 declara o caixa como instrumento, então a curva é rotulada pelo papel
    # que se compra — não pelo índice que ninguém compra.
    for label, key in (("Tesouro Selic", "Tesouro Selic"), ("Ibovespa", "Ibovespa")):
        assert label in curve["series"], f"{label} sumiu do gráfico"
        values = curve["series"][label]
        implied = (values[-1] / values[0]) ** (1 / years) - 1
        assert implied == pytest.approx(EVIDENCE["references"][key]["cagr"], abs=5e-4)


def test_the_ladder_ordering_holds_in_the_published_numbers() -> None:
    order = ["conservador", "equilibrado", "arrojado"]
    cagr = [EVIDENCE["profiles"][name]["benevente2"]["cagr"] for name in order]
    drawdown = [EVIDENCE["profiles"][name]["benevente2"]["max_drawdown"] for name in order]
    assert cagr == sorted(cagr), "o retorno deixou de subir com o perfil"
    assert drawdown == sorted(drawdown, reverse=True), "a queda deixou de piorar com o perfil"


def test_pages_that_show_the_ladder_load_the_data_and_the_seal() -> None:
    source = PAGES["versoes.html"]
    assert "ladder.js" in source and "ladder.css" in source
    assert "data-ladder-seal" in source


def test_every_page_reaches_the_limitations() -> None:
    """No page may state a result without a route to what the system cannot do."""
    for page, source in PAGES.items():
        if page in {"limitacoes.html"}:
            continue
        # Vírgula OU ponto decimal: a página de evidência é em inglês e escapou
        # da primeira versão deste teste exatamente por isso.
        if not re.search(r"\d[,.]\d{1,2}\s*(?:%|pp)", source):
            continue
        assert "limitacoes" in source, f"{page} publica números e não linka as limitações"


COMPOSITION = json.loads((WEB / "composition.json").read_text(encoding="utf-8"))


def test_the_current_model_is_named_and_its_lineage_is_stated() -> None:
    """One brand, two modules. A separate product name divided attention
    without describing anything the modules did not already describe."""
    assert EVIDENCE["public_name"] == "Benevente"
    assert COMPOSITION["public_name"] == EVIDENCE["public_name"]
    assert set(EVIDENCE["lineage"]) == {"Benevente 1", "Benevente 2", "Benevente"}
    # Renaming must not touch the frozen registration: the seal is what makes
    # the registration worth having, and a name is not a policy.
    assert "public_name" not in REGISTRATION
    assert COMPOSITION["registration_sha256"] == REGISTRATION["registration_sha256"]


@pytest.mark.parametrize("name", sorted(COMPOSITION["profiles"]))
def test_each_profile_composition_adds_up_to_its_declared_budget(name: str) -> None:
    declared = REGISTRATION["profiles"][name]
    for year in COMPOSITION["profiles"][name]:
        parts = year["domestic_equity"] + year["global_sleeve"] + year["cash"]
        assert parts == pytest.approx(1.0, abs=1e-6), f"{name} {year['decision_year']} não soma 1"
        assert year["global_sleeve"] == pytest.approx(declared["global_share_of_portfolio"], abs=1e-6)
        assert len(year["positions"]) <= declared["top_assets"], (
            f"{name} {year['decision_year']} carrega {len(year['positions'])} emissores, "
            f"acima dos {declared['top_assets']} declarados"
        )
        total = sum(row["weight"] for row in year["positions"])
        assert total == pytest.approx(year["domestic_equity"], abs=1e-6)


@pytest.mark.parametrize("name", sorted(COMPOSITION["profiles"]))
def test_no_position_exceeds_the_declared_issuer_cap(name: str) -> None:
    cap = REGISTRATION["profiles"][name]["maximum_asset_weight"]
    for year in COMPOSITION["profiles"][name]:
        # The weight published here is already net of the global sleeve, so the
        # cap is compared on the same basis the engine applied it.
        scale = 1 - year["global_sleeve"]
        for row in year["positions"]:
            assert row["weight"] / scale <= cap + 1e-6, (
                f"{name} {year['decision_year']}: {row['ticker']} em {row['weight'] / scale:.4f} "
                f"acima do teto de {cap}"
            )


def test_what_the_decision_could_not_know_is_kept_apart() -> None:
    """The realised return must exist as its own field, never folded into score."""
    for name, years in COMPOSITION["profiles"].items():
        for year in years:
            for row in year["positions"]:
                assert "realised_next_year" in row, f"{name}: falta o retorno realizado"
                assert {"score", "trailing_12m", "trailing_vol"} <= set(row), name


def test_every_asset_reference_is_stamped_with_its_own_content() -> None:
    """A hand-bumped cache parameter is a promise someone will remember.

    It was broken three times in one session, and each failure was silent: the
    corrected file simply never reached the browser. The stamp is derived from
    the content, and this test is what makes the rule hold.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("stamp_assets", ROOT / "tools" / "stamp_assets.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    missing: list[str] = []
    stale: list[str] = []
    for page in sorted(WEB.glob("*.html")):
        _, changes = module.stamp(page, missing)
        if changes:
            stale.append(f"{page.name} ({changes})")
    assert not missing, f"referência para arquivo inexistente: {missing}"
    assert not stale, (
        f"parâmetro de cache defasado em {stale}. Rode tools/stamp_assets.py — sem isso a correção "
        f"não chega a nenhum navegador com cache."
    )


RETIRED_NAMES = {
    "Benevente Alpha": "nome de produto extra, descartado em favor da marca única",
    "Benevente Wealth System": "variação da marca que competia com o nome curto",
}


@pytest.mark.parametrize("page", sorted(PAGES))
def test_no_page_reintroduces_a_discarded_name(page: str) -> None:
    """Seis nomes circulavam ao mesmo tempo e o leitor não sabia qual era o quê.

    Ficaram: a marca Benevente, os módulos Benevente 1 e 2, e Benevente Quant AI
    como nome da pesquisa.
    """
    for name, reason in RETIRED_NAMES.items():
        assert name not in PAGES[page], f"{page} reintroduz '{name}' ({reason})"


def test_home_summary_selects_profiles_by_name_not_by_copy() -> None:
    """Um ajuste de texto já apagou os três perfis do resumo da home.

    O filtro que separava política de referência comparava o *rótulo* exibido
    ("Política declarada · …"); quando o rótulo virou "Com proteção · …" o
    filtro passou a não casar com nada e a home caiu num texto de reserva que
    descrevia a política aposentada — 509,8% acumulado e o MVO — ao lado das
    curvas dos três perfis. O discriminador agora é o nome da série.
    """
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert 'const PROFILE_SERIES = ["Conservador", "Equilibrado", "Arrojado"]' in source
    assert "PROFILE_SERIES.includes(name)" in source
    assert 'noteFor[name]?.startsWith(' not in source
    # E o texto de reserva da política aposentada não pode existir para ser exibido.
    for retired in ("acumulado. Venceu o CDI em", "e para o MVO é"):
        assert retired not in source, retired
