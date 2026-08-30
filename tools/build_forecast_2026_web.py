# -*- coding: utf-8 -*-
"""Publica, para o site, a faixa de 2026 contra o que está acontecendo.

Duas metades com origens diferentes, e a diferença é o ponto:

* a **faixa** vem de ``artifacts/forecast_2026_cone_v1/cone.json``, calculada uma
  vez em janeiro com dados anteriores ao primeiro pregão do ano. Ela é copiada
  daqui sem nenhum recálculo;
* o **realizado** vem de ``web/live_performance_<perfil>.json``, que o
  acompanhamento diário reescreve.

Rodar este programa todo dia útil, depois do acompanhamento, mantém o gráfico
atualizado sem nunca mexer na faixa. Se a faixa se movesse junto com o
resultado, ela não mediria nada, porque nunca erraria.

O ponto de comparação é o pregão decorrido, não a data: em agosto o realizado é
comparado com a faixa de agosto. Comparar meio ano com a faixa do ano inteiro
faria a carteira parecer atrasada só porque o ano não acabou.
"""
from __future__ import annotations

from pathlib import Path
import json
from politica import escada

ROOT = Path(__file__).resolve().parents[1]
CONE = ROOT / "artifacts" / "forecast_2026_cone_v1" / "cone.json"
#: A faixa dos degraus declarados depois de janeiro, que não podia entrar
#: no cone congelado sem mover as faixas dos outros. Ver
#: research_forecast_2026_cone_tardio.py.
CONE_TARDIO = ROOT / "artifacts" / "forecast_2026_cone_v1" / "cone_tardio.json"
WEB = ROOT / "web"
DESTINO = WEB / "forecast_2026.json"
#: Os degraus vêm da política. Ver tools/politica.py.
PERFIS = escada()


def _faixa_em(band: list[dict], sessoes: int) -> dict:
    """A linha da faixa no horizonte pedido, interpolada entre dois pontos.

    A faixa é gravada de cinco em cinco pregões. Pegar o ponto mais próximo
    daria um degrau visível justamente no número que a página compara, então
    interpola. Fora do intervalo, devolve a ponta.
    """
    if sessoes <= band[0]["sessions"]:
        return band[0]
    if sessoes >= band[-1]["sessions"]:
        return band[-1]
    for antes, depois in zip(band, band[1:]):
        if antes["sessions"] <= sessoes <= depois["sessions"]:
            vao = depois["sessions"] - antes["sessions"]
            peso = (sessoes - antes["sessions"]) / vao if vao else 0.0
            return {"sessions": sessoes,
                    **{q: round(antes[q] + (depois[q] - antes[q]) * peso, 6)
                       for q in ("p10", "p50", "p90")}}
    return band[-1]


def build() -> dict:
    cone = json.loads(CONE.read_text(encoding="utf-8"))
    tardio = json.loads(CONE_TARDIO.read_text(encoding="utf-8"))
    # As duas origens ficam juntas para o gráfico e separadas para quem lê: a
    # faixa de janeiro foi declarada antes do ano, a tardia foi desenhada depois
    # que o degrau existiu, com dados anteriores a 2026. Misturar as duas sem
    # dizer qual é qual daria ao degrau novo um mérito que ele não tem.
    faixas = {**cone["profiles"], **tardio["profiles"]}
    documento = {
        "status": cone["status"],
        "year": cone["year"],
        "question": cone["question"],
        "limitation": cone["limitation"],
        "method": cone["method"],
        "late_band": {"method": tardio["method"], "limitation": tardio["limitation"],
                      "profiles": sorted(tardio["profiles"])},
        "profiles": {},
    }

    for perfil in PERFIS:
        vivo = json.loads((WEB / f"live_performance_{perfil}.json").read_text(encoding="utf-8"))
        serie = vivo["series"]
        base = serie[0]["portfolio"]
        realizado = [{"sessions": i + 1,
                      "date": ponto["date"],
                      "r": round(ponto["portfolio"] / base - 1.0, 6)}
                     for i, ponto in enumerate(serie)]
        agora = realizado[-1]
        faixa = _faixa_em(faixas[perfil]["band"], agora["sessions"])
        documento["profiles"][perfil] = {
            "band": faixas[perfil]["band"],
            "band_drawn_on": faixas[perfil].get("drawn_on", cone.get("drawn_on", "2026-01-02")),
            "band_declared_before_year": perfil in cone["profiles"],
            "realised": realizado,
            "now": {
                "sessions": agora["sessions"],
                "date": agora["date"],
                "realised": agora["r"],
                "p10": faixa["p10"], "p50": faixa["p50"], "p90": faixa["p90"],
                "inside": bool(faixa["p10"] <= agora["r"] <= faixa["p90"]),
            },
        }
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    return documento


def main() -> None:
    d = build()
    print(f"{DESTINO.relative_to(ROOT)}: {DESTINO.stat().st_size / 1024:.1f} KB")
    for perfil, r in d["profiles"].items():
        n = r["now"]
        print(f"  {perfil:<13} {n['sessions']:>3} pregões até {n['date']} · "
              f"realizado {n['realised']*100:+.2f}% · faixa "
              f"{n['p10']*100:+.2f}% a {n['p90']*100:+.2f}% · "
              f"{'dentro' if n['inside'] else 'FORA'}")


if __name__ == "__main__":
    main()
