"""Fase 0 do canal de WhatsApp: a fila, sem entrega.

Nada aqui envia mensagem. O programa lê os artefatos que o pipeline diário já
publica, decide se aconteceu algo que exige ciência de quem assina e escreve o
que *teria* sido enviado. Rodar semanas nesse modo é o que permite conferir a
lógica de gatilho à mão antes que um alerta errado chegue no celular de alguém —
e um alerta errado não se desfaz.

Três gatilhos, e apenas três, porque só eles exigem ação (docs/desenho_bot_whatsapp.md):

* mudança de estado da camada de proteção, por perfil;
* decisão anual disponível, quando a cesta do ano muda;
* item do radar classificado como exigindo revisão humana.

Duas propriedades que a fila carrega desde a primeira linha, porque acrescentá-las
depois obrigaria a reescrever o histórico:

* **Rastreabilidade.** Cada item traz o arquivo que o originou e o hash dele. Um
  alerta que não se rastreia até o artefato é um alerta que ninguém defende três
  anos depois — o problema que o produto inteiro existe para resolver.
* **Cadeia.** Cada item traz o hash do anterior. Apagar ou reescrever uma
  notificação passada quebra a cadeia de forma visível, como no monitor diário.

O texto não é gerado: cada gatilho aponta para um modelo com campos nomeados. A
plataforma exige modelos aprovados previamente para mensagens fora da janela de
conversa, então a fila já nasce no formato que a entrega vai exigir.
"""
from __future__ import annotations

from pathlib import Path
import sys
import argparse
import hashlib
import json
sys.path.insert(0, str(Path(__file__).resolve().parent))
from politica import escada

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = ROOT / "artifacts" / "notification_queue"
#: Os degraus vêm da política. Escritos à mão aqui, quem seguisse um degrau
#: declarado depois nunca receberia aviso de mudança de carteira, e nada no
#: programa reclamaria: ele simplesmente não olharia para esse perfil.
PROFILES = tuple(escada())
PERFIL_LABEL = {p: p.capitalize() for p in PROFILES}
ESTADO_LABEL = {"normal": "normal", "alerta": "alerta", "severo": "severo"}

#: Modelos, com os campos que a entrega vai preencher. O texto fica aqui em
#: português corrido para poder ser submetido à aprovação como está.
TEMPLATES = {
    "camada_mudou": {
        "categoria": "utilitaria",
        "texto": ("Benevente · {perfil}: a camada de proteção passou de {de} para {para} "
                  "em {data}. Exposição em ações vai de {exposicao_antes} para "
                  "{exposicao_depois} no próximo pregão. Motivo observado: {motivo}. "
                  "Nenhuma ordem foi transmitida — a decisão é sua."),
        "campos": ("perfil", "de", "para", "data", "exposicao_antes", "exposicao_depois", "motivo"),
    },
    "decisao_anual": {
        "categoria": "utilitaria",
        "texto": ("Benevente · {perfil}: a decisão de {data} está disponível, com "
                  "{emissores} emissores e {acoes} em ações. O dossiê completo está no "
                  "site. Nenhuma ordem foi transmitida — a decisão é sua."),
        "campos": ("perfil", "data", "emissores", "acoes"),
    },
    # Um degrau declarado depois de janeiro herda a seleção de janeiro, e o
    # aviso não pode anunciar "a decisão de 02/01" para uma carteira que não
    # existia naquele dia. As duas datas aparecem, e cada uma diz o que é.
    "decisao_anual_derivada": {
        "categoria": "utilitaria",
        "texto": ("Benevente · {perfil}: a carteira está disponível, com {emissores} "
                  "emissores e {acoes} em ações. A seleção é a de {data}; este perfil "
                  "foi declarado em {declarado} e usa a mesma seleção com peso menor. "
                  "O dossiê completo está no site. Nenhuma ordem foi transmitida — a "
                  "decisão é sua."),
        "campos": ("perfil", "data", "emissores", "acoes", "declarado"),
    },
    "radar_revisao": {
        "categoria": "utilitaria",
        "texto": ("Benevente · radar: {quantidade} item(ns) sobre {tickers} marcado(s) "
                  "para revisão humana em {data}. O radar não altera pesos e não "
                  "participa do sinal de proteção."),
        "campos": ("quantidade", "tickers", "data"),
    },
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%".replace(".", ",")


def _item(kind: str, key: str, variables: dict, source: Path, previous_sha: str | None) -> dict:
    """Um item de fila, com o que o torna auditável e encadeado."""
    template = TEMPLATES[kind]
    faltando = [c for c in template["campos"] if c not in variables]
    if faltando:
        raise ValueError(f"{kind}: faltam campos {faltando}")
    body = {
        "key": key,
        "template": kind,
        "category": template["categoria"],
        "variables": {c: variables[c] for c in template["campos"]},
        "preview": template["texto"].format(**variables),
        "source": {"file": source.name, "sha256": _sha256_file(source)},
        "previous_record_sha256": previous_sha,
        "state": "queued_dry_run",
    }
    body["record_sha256"] = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return body


def overlay_events(previous_keys: set[str]) -> list[tuple[str, str, dict, Path]]:
    """Mudanças de estado da camada que ainda não foram enfileiradas."""
    found = []
    for profile in PROFILES:
        path = WEB / f"live_performance_{profile}.json"
        if not path.exists():
            continue
        live = json.loads(path.read_text(encoding="utf-8"))
        overlay = live.get("benevente2_overlay") or {}
        decisions = overlay.get("risk_decisions") or []
        base = sum(h["weight"] for h in live.get("holdings", []) if h["ticker"] != "IVVB11")
        multipliers = overlay.get("profile_multipliers") or {}
        factor = {0: 1.0, 1: multipliers.get("alerta", 1.0), 2: multipliers.get("severo", 1.0)}
        for decision in decisions:
            # O primeiro item é o início do ciclo, não uma mudança: avisar sobre
            # ele seria mandar mensagem no dia em que nada aconteceu.
            if decision.get("from_state") is None:
                continue
            key = f"camada:{profile}:{decision['effective_on']}:{decision['to_state']}"
            if key in previous_keys:
                continue
            de, para = int(decision["from_state"]), int(decision["to_state"])
            nomes = {0: "normal", 1: "alerta", 2: "severo"}
            found.append((
                "camada_mudou", key,
                {"perfil": PERFIL_LABEL[profile],
                 "de": nomes[de], "para": nomes[para],
                 "data": "/".join(reversed(decision["effective_on"].split("-"))),
                 "exposicao_antes": _pct(base * factor.get(de, 1.0)),
                 "exposicao_depois": _pct(decision.get("target_equity_weight")),
                 "motivo": decision.get("reason") or "mudança de estado observada"},
                path))
    return found


def annual_events(previous_keys: set[str]) -> list[tuple[str, str, dict, Path]]:
    found = []
    for profile in PROFILES:
        path = WEB / f"current_decision_2026_{profile}.json"
        if not path.exists():
            continue
        book = json.loads(path.read_text(encoding="utf-8"))
        derivacao = book.get("derivation")
        # derived_on é carimbo de tempo, e o resto do programa fala em datas. Sem
        # cortar aqui, o aviso saía com o horário picado no meio da data.
        declarado_em = derivacao["derived_on"][:10] if derivacao else None
        marco = declarado_em or book["decision_date"]
        key = f"decisao:{profile}:{marco}"
        if key in previous_keys:
            continue
        acoes = [h for h in book["holdings"] if h["ticker"] != "IVVB11"]
        campos = {"perfil": PERFIL_LABEL[profile],
                  "data": "/".join(reversed(book["decision_date"].split("-"))),
                  "emissores": str(len(acoes)),
                  "acoes": _pct(sum(h["weight"] for h in acoes))}
        if derivacao:
            campos["declarado"] = "/".join(reversed(declarado_em.split("-")))
        found.append((
            "decisao_anual_derivada" if derivacao else "decisao_anual", key, campos, path))
    return found


def radar_events(previous_keys: set[str]) -> list[tuple[str, str, dict, Path]]:
    path = WEB / "event_radar.json"
    if not path.exists():
        return []
    radar = json.loads(path.read_text(encoding="utf-8"))
    pending = [e for e in radar.get("events", [])
               if (e.get("classification") or {}).get("needs_human_review")]
    if not pending:
        return []
    # Um item por consolidação, não um por notícia: três alertas seguidos sobre o
    # mesmo emissor treinam o destinatário a ignorar o quarto.
    day = radar.get("generated_at", "")[:10]
    key = f"radar:{day}:{len(pending)}"
    if key in previous_keys:
        return []
    tickers = sorted({t for e in pending
                      for t in (e.get("classification") or {}).get("impacted_tickers", [])})
    return [("radar_revisao", key,
             {"quantidade": str(len(pending)),
              "tickers": ", ".join(tickers) or "carteira",
              "data": "/".join(reversed(day.split("-"))) if day else "hoje"},
             path)]


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    queue_path = output / "queue.json"
    previous = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else {"items": []}
    items = list(previous.get("items", []))
    seen = {item["key"] for item in items}
    last_sha = items[-1]["record_sha256"] if items else None

    novos = []
    for kind, key, variables, source in (overlay_events(seen) + annual_events(seen) + radar_events(seen)):
        item = _item(kind, key, variables, source, last_sha)
        last_sha = item["record_sha256"]
        items.append(item)
        seen.add(key)
        novos.append(item)

    document = {
        "phase": "0_dry_run",
        "delivery": "desligada: nenhum item desta fila foi ou será enviado nesta fase",
        "design": "docs/desenho_bot_whatsapp.md",
        "templates": TEMPLATES,
        "items": items,
    }
    queue_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"total": len(items), "novos": novos}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    result = run(args.output)
    print(f"fila com {result['total']} item(ns) · {len(result['novos'])} novo(s) nesta execução")
    for item in result["novos"]:
        print(f"\n  [{item['template']}] {item['key']}")
        print(f"  {item['preview']}")
        print(f"  origem {item['source']['file']} · {item['source']['sha256'][:12]}")
    if not result["novos"]:
        print("  nada novo: nenhum gatilho disparou desde a última execução")


if __name__ == "__main__":
    main()
