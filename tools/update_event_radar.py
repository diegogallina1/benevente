"""Consolida eventos públicos e classifica materialidade sem transmitir ordens."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree


BRT = timezone(timedelta(hours=-3))
CKAN_PACKAGE = "https://dados.cvm.gov.br/api/3/action/package_show?id=cia_aberta-doc-ipe"
NEWS_ENDPOINT = "https://news.google.com/rss/search"
NEWS_QUERIES = (
    "mercado financeiro Brasil B3 ações",
    "Banco Central Brasil Copom juros inflação câmbio",
    "CVM fato relevante companhia aberta",
    "VIVA3 OR CURY3 OR CMIN3 OR BBSE3 OR LEVE3",
)
HIGH_RISK_TERMS = (
    "fraude", "recuperação judicial", "default", "calote", "intervenção", "falência",
    "rompimento", "acidente", "sanção", "investigação", "corrupção", "rebaixamento",
    "cancelamento", "suspensão", "prejuízo", "crise", "guerra", "pandemia",
)
MATERIAL_TERMS = (
    "fato relevante", "aquisição", "fusão", "incorporação", "opa", "dividendos",
    "guidance", "resultado", "lucro", "ebitda", "dívida", "copom", "selic",
    "inflação", "câmbio", "regulação", "oferta", "recompra", "mudança de controle",
)
NEGATIVE_TERMS = HIGH_RISK_TERMS + ("queda", "redução", "perda", "multa", "inadimplência")
POSITIVE_TERMS = ("lucro recorde", "elevação", "aumento", "aprovação", "recompra", "dividendo")
RELEVANT_CVM_CATEGORIES = {
    "Fato Relevante", "Comunicado ao Mercado", "Dados Econômico-Financeiros",
    "Informações de Companhias em Recuperação Judicial ou Extrajudicial",
    "Informação Prestada às Bolsas Estrangeiras", "OPA - Edital de Oferta Pública de Ações",
}


def _request(url: str, *, timeout: int = 30, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"User-Agent": "BeneventeResearchRadar/1.0 (+https://github.com/diegogallina1/benevente)"}
    request_headers.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=request_headers), timeout=timeout) as response:
        return response.read()


def _clean(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _iso(value: datetime) -> str:
    return value.astimezone(BRT).isoformat(timespec="seconds")


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    try:
        parsed = parsedate_to_datetime(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=BRT)
    except (TypeError, ValueError):
        pass
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=BRT)
        except ValueError:
            continue
    return None


def _event_id(source: str, title: str, url: str, published_at: str) -> str:
    value = "|".join((source.lower(), title.lower(), url, published_at))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fetch_google_news(query: str, cutoff: datetime) -> list[dict[str, Any]]:
    parameters = urllib.parse.urlencode({"q": query, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
    root = ElementTree.fromstring(_request(f"{NEWS_ENDPOINT}?{parameters}"))
    events = []
    for node in root.findall("./channel/item"):
        published = _parse_date(node.findtext("pubDate"))
        if published is None or published.astimezone(timezone.utc) < cutoff.astimezone(timezone.utc):
            continue
        raw_title = _clean(node.findtext("title"))
        title, separator, publisher = raw_title.rpartition(" - ")
        source = publisher if separator else "Google Notícias"
        title = title if separator else raw_title
        url = _clean(node.findtext("link"))
        published_at = _iso(published)
        events.append({
            "id": _event_id(source, title, url, published_at),
            "source": source,
            "source_type": "noticia_descoberta",
            "source_tier": "fonte_secundaria_a_confirmar",
            "title": title,
            "summary": _clean(node.findtext("description"))[:900],
            "url": url,
            "published_at": published_at,
            "query": query,
        })
    return events


def _current_cvm_resource(year: int) -> str:
    package = json.loads(_request(CKAN_PACKAGE).decode("utf-8"))["result"]
    suffix = f"({year})"
    resources = [item for item in package["resources"] if item.get("name", "").endswith(suffix)]
    if not resources:
        raise RuntimeError(f"recurso IPE {year} não localizado")
    return resources[0]["url"]


def fetch_cvm_ipe(year: int, cutoff: datetime) -> list[dict[str, Any]]:
    archive = zipfile.ZipFile(io.BytesIO(_request(_current_cvm_resource(year), timeout=60)))
    csv_names = [name for name in archive.namelist() if name.lower().endswith((".csv", ".txt"))]
    if not csv_names:
        raise RuntimeError("arquivo IPE sem tabela")
    raw = archive.read(csv_names[0])
    decoded = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(decoded), delimiter=";")
    events = []
    for row in reader:
        category = (row.get("Categoria") or row.get("Categoria_Doc") or "").strip()
        if category not in RELEVANT_CVM_CATEGORIES:
            continue
        published = _parse_date(row.get("Data_Entrega") or row.get("DataEntrega"))
        if published is None or published.astimezone(timezone.utc) < cutoff.astimezone(timezone.utc):
            continue
        company = _clean(row.get("Nome_Companhia") or row.get("NomeCompanhia") or "Companhia aberta")
        subject = _clean(row.get("Assunto") or row.get("Tipo") or category)
        title = f"{company}: {category} — {subject}" if subject and subject != category else f"{company}: {category}"
        url = _clean(row.get("Link_Documento") or row.get("LinkDocumento") or "")
        published_at = _iso(published)
        events.append({
            "id": _event_id("CVM", title, url, published_at),
            "source": "CVM",
            "source_type": "documento_oficial",
            "source_tier": "primaria_oficial",
            "title": title,
            "summary": subject,
            "url": url,
            "published_at": published_at,
            "category": category,
            "company": company,
        })
    return events


def deterministic_classification(event: dict[str, Any], portfolio_tickers: Iterable[str]) -> dict[str, Any]:
    text = f"{event.get('title', '')} {event.get('summary', '')}".lower()
    tickers = [ticker for ticker in portfolio_tickers if ticker.lower() in text]
    score = 15 if event.get("source_tier") == "primaria_oficial" else 5
    if any(term in text for term in MATERIAL_TERMS):
        score += 25
    if any(term in text for term in HIGH_RISK_TERMS):
        score += 40
    if tickers:
        score += 25
        if any(term in text for term in HIGH_RISK_TERMS):
            score += 20
    if any(term in text for term in ("copom", "selic", "inflação", "câmbio", "banco central")):
        score += 20
    score = min(score, 100)
    if any(term in text for term in NEGATIVE_TERMS):
        impact = "negativo"
    elif any(term in text for term in POSITIVE_TERMS):
        impact = "positivo"
    else:
        impact = "incerto"
    urgency = "critica" if score >= 85 else "alta" if score >= 70 else "media" if score >= 50 else "baixa"
    return {
        "materiality": score,
        "confidence": 0.55 if event.get("source_tier") == "primaria_oficial" else 0.35,
        "urgency": urgency,
        "impact": impact,
        "horizon": "indeterminado",
        "impacted_tickers": tickers,
        "summary": event.get("summary") or event.get("title"),
        "rationale": "Triagem determinística por fonte, termos materiais e vínculo com a carteira.",
        "needs_human_review": score >= 50,
        "classifier": "regras_deterministicas",
    }


def _gemini_schema() -> dict[str, Any]:
    alert = {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "materiality": {"type": "INTEGER", "minimum": 0, "maximum": 100},
            "confidence": {"type": "NUMBER", "minimum": 0, "maximum": 1},
            "urgency": {"type": "STRING", "enum": ["baixa", "media", "alta", "critica"]},
            "impact": {"type": "STRING", "enum": ["positivo", "negativo", "misto", "incerto"]},
            "horizon": {"type": "STRING", "enum": ["intradiario", "dias", "semanas", "meses", "indeterminado"]},
            "impacted_tickers": {"type": "ARRAY", "items": {"type": "STRING"}},
            "summary": {"type": "STRING"},
            "rationale": {"type": "STRING"},
            "needs_human_review": {"type": "BOOLEAN"},
        },
        "required": [
            "id", "materiality", "confidence", "urgency", "impact", "horizon",
            "impacted_tickers", "summary", "rationale", "needs_human_review",
        ],
    }
    return {
        "type": "OBJECT",
        "properties": {"alerts": {"type": "ARRAY", "items": alert}},
        "required": ["alerts"],
    }


def classify_with_gemini(events: list[dict[str, Any]], api_key: str, model: str) -> dict[str, dict[str, Any]]:
    prompt = (
        "Você é um classificador de risco financeiro, não um assessor. Classifique somente os fatos fornecidos. "
        "Não invente números, não recomende compra ou venda e não trate uma manchete como confirmação. "
        "Materialidade mede potencial de alterar valor, solvência, governança ou risco macro da carteira. "
        "Exija revisão humana para materialidade >= 50. Itens:\n" +
        json.dumps([{
            "id": item["id"], "source": item["source"], "source_tier": item["source_tier"],
            "title": item["title"], "summary": item["summary"], "published_at": item["published_at"],
        } for item in events], ensure_ascii=False)
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": _gemini_schema()},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent"
    # urllib needs a body; keep the request explicit so the secret never enters the URL.
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key, "User-Agent": "BeneventeResearchRadar/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as handle:
        response = json.loads(handle.read().decode("utf-8"))
    text = "".join(part.get("text", "") for part in response["candidates"][0]["content"]["parts"])
    parsed = json.loads(text)
    allowed = {item["id"] for item in events}
    result = {}
    for item in parsed.get("alerts", []):
        if item.get("id") not in allowed:
            continue
        item["materiality"] = max(0, min(100, int(item["materiality"])))
        item["confidence"] = max(0.0, min(1.0, float(item["confidence"])))
        item["classifier"] = f"gemini:{model}"
        result[item["id"]] = item
    return result


def _state(score: int) -> str:
    return "critico" if score >= 85 else "alerta" if score >= 70 else "atencao" if score >= 50 else "normal"


def build_radar(previous: dict[str, Any], now: datetime, collected: list[dict[str, Any]], source_status: list[dict[str, Any]], api_key: str = "", model: str = "gemini-3.5-flash") -> dict[str, Any]:
    old_events = {item["id"]: item for item in previous.get("events", [])}
    unique = {item["id"]: item for item in collected}
    new_events = [item for key, item in unique.items() if key not in old_events]
    portfolio_tickers = ("VIVA3", "CURY3", "CMIN3", "BBSE3", "LEVE3")
    classifications: dict[str, dict[str, Any]] = {}
    classifier_status = "gemini_disponivel_sem_itens_novos" if api_key else "deterministico_sem_chave"
    classifier_error = None
    upgrade_events = [
        item for item in old_events.values()
        if item.get("classification", {}).get("classifier") == "regras_deterministicas"
    ][:40]
    new_ids = {item["id"] for item in new_events}
    classification_targets = new_events + [item for item in upgrade_events if item["id"] not in new_ids]
    if api_key and classification_targets:
        try:
            for start in range(0, len(classification_targets), 20):
                classifications.update(classify_with_gemini(classification_targets[start:start + 20], api_key, model))
            classifier_status = f"gemini:{model}"
        except Exception as error:  # Network/API failure must not stop collection.
            classifier_status = "deterministico_apos_falha_gemini"
            classifier_error = f"{type(error).__name__}: {error}"[:300]
    for event in new_events:
        event["classification"] = classifications.get(event["id"]) or deterministic_classification(event, portfolio_tickers)
        event["state"] = _state(event["classification"]["materiality"])
        old_events[event["id"]] = event
    for event in upgrade_events:
        if event["id"] in classifications:
            event["classification"] = classifications[event["id"]]
            event["state"] = _state(event["classification"]["materiality"])
    ordered_events = sorted(old_events.values(), key=lambda item: item.get("published_at", ""), reverse=True)[:300]
    latest = sorted(new_events, key=lambda item: (item["classification"]["materiality"], item["published_at"]), reverse=True)
    top_score = max((item["classification"]["materiality"] for item in latest), default=0)
    consolidation = {
        "run_at": _iso(now), "window_hours": 12, "new_items": len(new_events),
        "items_by_state": {state: sum(item["state"] == state for item in new_events) for state in ("critico", "alerta", "atencao", "normal")},
        "source_status": source_status, "classifier_status": classifier_status,
        "classifier_error": classifier_error, "state": _state(top_score),
    }
    consolidations = [consolidation, *previous.get("consolidations", [])][:60]
    document = {
        "schema_version": "1.0.0", "generated_at": _iso(now), "timezone": "America/Sao_Paulo",
        "schedule": ["00:10", "12:10"], "window_hours": 12, "current_state": consolidation["state"],
        "portfolio_tickers": list(portfolio_tickers),
        "policy": "O radar informa e prioriza revisão humana; não altera pesos nem transmite ordens.",
        "latest_items": latest[:30] if latest else (previous.get("latest_items", [])[:30] or ordered_events[:30]),
        "events": ordered_events, "consolidations": consolidations,
    }
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    document["record_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return document


def collect(now: datetime, lookback_hours: int = 36) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff = now - timedelta(hours=lookback_hours)
    events: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    sources = [("CVM IPE", lambda: fetch_cvm_ipe(now.year, cutoff))]
    sources.extend((f"Google Notícias · {query}", lambda query=query: fetch_google_news(query, cutoff)) for query in NEWS_QUERIES)
    for name, function in sources:
        try:
            source_events = function()
            events.extend(source_events)
            statuses.append({"source": name, "status": "ok", "items": len(source_events)})
        except Exception as error:
            statuses.append({"source": name, "status": "indisponivel", "items": 0, "detail": f"{type(error).__name__}: {error}"[:240]})
    return list({item["id"]: item for item in events}.values()), statuses


def update(output: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(BRT)
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    events, status = collect(now, lookback_hours=168 if not previous.get("events") else 36)
    result = build_radar(
        previous, now, events, status, api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("web/event_radar.json"))
    args = parser.parse_args()
    result = update(args.output)
    latest = result["consolidations"][0]
    print(f"{latest['new_items']} itens novos; estado {latest['state']}; classificador {latest['classifier_status']}")


if __name__ == "__main__":
    main()
