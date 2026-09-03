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
BASE_NEWS_QUERIES = (
    "mercado financeiro Brasil B3 ações",
    "Banco Central Brasil Copom juros inflação câmbio",
    "CVM fato relevante companhia aberta",
)
MAX_ITEMS_PER_NEWS_QUERY = 50
MAX_NEW_ITEMS_PER_RUN = 120
MAX_GEMINI_ITEMS_PER_RUN = 60
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


BYTES_MAXIMOS = 40 * 1024 * 1024
MEMBRO_MAXIMO = 200 * 1024 * 1024


def _request(url: str, *, timeout: int = 30, headers: dict[str, str] | None = None,
             limite: int = BYTES_MAXIMOS) -> bytes:
    """Baixa com teto de bytes.

    Sem teto, uma resposta grande é lida inteira na memória do runner: vale para
    o ZIP da CVM, para o RSS e para o JSON do modelo. O XML ainda expande
    entidades internas declaradas no próprio documento (o ElementTree recusa
    entidade externa, então XXE não se aplica, mas a bomba de entidades sim), e
    o teto de bytes é o que limita o tamanho do documento antes de parsear.
    """
    request_headers = {"User-Agent": "BeneventeResearchRadar/1.0 (+https://github.com/diegogallina1/benevente)"}
    request_headers.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=request_headers), timeout=timeout) as response:
        dados = response.read(limite + 1)
    if len(dados) > limite:
        raise RuntimeError(f"resposta acima do teto de {limite} bytes: {url.split('?')[0]}")
    return dados


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


def fetch_google_news(query: str, cutoff: datetime, limit: int = MAX_ITEMS_PER_NEWS_QUERY) -> list[dict[str, Any]]:
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
        if len(events) >= limit:
            break
    return events


def _current_cvm_resource(year: int) -> dict[str, Any]:
    package = json.loads(_request(CKAN_PACKAGE).decode("utf-8"))["result"]
    suffix = f"({year})"
    resources = [item for item in package["resources"] if item.get("name", "").endswith(suffix)]
    if not resources:
        raise RuntimeError(f"recurso IPE {year} não localizado")
    return resources[0]


def fetch_cvm_ipe(
    year: int, cutoff: datetime, known_fingerprint: str = "", counters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str, bool]:
    """`counters`, quando passado, recebe quantas linhas o arquivo tinha e por que cada uma ficou de fora.

    Sem isso um arquivo com colunas renomeadas ou datas ilegíveis vira "ok, 0 itens", indistinguível de um dia calmo.
    """
    resource = _current_cvm_resource(year)
    fingerprint = resource.get("last_modified") or resource.get("hash") or resource["url"]
    if known_fingerprint and fingerprint == known_fingerprint:
        return [], fingerprint, True
    archive = zipfile.ZipFile(io.BytesIO(_request(resource["url"], timeout=60)))
    csv_names = [name for name in archive.namelist() if name.lower().endswith((".csv", ".txt"))]
    if not csv_names:
        raise RuntimeError("arquivo IPE sem tabela")
    # O tamanho descomprimido é lido do cabeçalho antes de descomprimir: um ZIP
    # pequeno pode declarar um membro de gigabytes, e archive.read() o traria
    # inteiro para a memória. O nome do membro não vira caminho em disco aqui
    # (leitura por nome, sem extractall), então travessia de caminho não se
    # aplica; o que faltava era o teto de tamanho.
    declarado = archive.getinfo(csv_names[0]).file_size
    if declarado > MEMBRO_MAXIMO:
        raise RuntimeError(f"membro IPE declara {declarado} bytes, acima do teto de {MEMBRO_MAXIMO}")
    raw = archive.read(csv_names[0])
    decoded = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(decoded), delimiter=";")
    events = read_cvm_rows(reader, cutoff, counters)
    return events, fingerprint, False


def read_cvm_rows(reader: Iterable[dict[str, Any]], cutoff: datetime, counters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    tally: dict[str, Any] = {"rows_read": 0, "rows_other_category": 0, "rows_without_date": 0, "rows_before_window": 0, "rows_kept": 0}
    categories: dict[str, int] = {}
    columns_seen = False
    events = []
    for row in reader:
        tally["rows_read"] += 1
        columns_seen = columns_seen or any(key in row for key in ("Categoria", "Categoria_Doc"))
        category = (row.get("Categoria") or row.get("Categoria_Doc") or "").strip()
        categories[category] = categories.get(category, 0) + 1
        if category not in RELEVANT_CVM_CATEGORIES:
            tally["rows_other_category"] += 1
            continue
        published = _parse_date(row.get("Data_Entrega") or row.get("DataEntrega"))
        if published is None:
            tally["rows_without_date"] += 1
            continue
        if published.astimezone(timezone.utc) < cutoff.astimezone(timezone.utc):
            tally["rows_before_window"] += 1
            continue
        tally["rows_kept"] += 1
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
    if counters is not None:
        counters.update(tally)
        counters["columns_recognised"] = columns_seen or tally["rows_read"] == 0
        counters["categories_seen"] = dict(sorted(categories.items(), key=lambda pair: -pair[1])[:8])
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
    urgency = _urgencia_por_nota(score)
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
        result[item["id"]] = _classificacao_saneada(item, model)
    return result


URGENCIAS = ("baixa", "media", "alta", "critica")
IMPACTOS = ("positivo", "negativo", "misto", "incerto")
HORIZONTES = ("intradiario", "dias", "semanas", "meses", "indeterminado")
TICKER = re.compile(r"^[A-Z0-9]{4,8}$")


def _classificacao_saneada(item: dict[str, Any], model: str) -> dict[str, Any]:
    """Reconstrói a classificação a partir de campos conhecidos e validados.

    A entrada do modelo inclui manchete escrita por terceiro, então a saída dele
    é dado não confiável: é injeção de prompt por construção. O responseSchema
    é aplicado no servidor do provedor, não aqui, e antes disso o código
    devolvia o dicionário do modelo direto para o arquivo publicado, aceitando
    qualquer chave e qualquer valor nos campos de texto e de enumeração. Agora
    só passa o que está previsto, com valor dentro do conjunto declarado, e
    chave desconhecida é descartada em vez de publicada.
    """
    materialidade = max(0, min(100, int(item.get("materiality") or 0)))
    urgencia = str(item.get("urgency") or "").strip().lower()
    impacto = str(item.get("impact") or "").strip().lower()
    horizonte = str(item.get("horizon") or "").strip().lower()
    brutos = item.get("impacted_tickers")
    tickers = [t for t in [str(x).strip().upper() for x in brutos[:20]] if TICKER.match(t)] if isinstance(brutos, list) else []
    return {
        "id": item["id"],
        "materiality": materialidade,
        "confidence": max(0.0, min(1.0, float(item.get("confidence") or 0.0))),
        "urgency": urgencia if urgencia in URGENCIAS else _urgencia_por_nota(materialidade),
        "impact": impacto if impacto in IMPACTOS else "incerto",
        "horizon": horizonte if horizonte in HORIZONTES else "indeterminado",
        "impacted_tickers": tickers,
        "summary": str(item.get("summary") or "")[:900],
        "rationale": str(item.get("rationale") or "")[:900],
        # A regra de revisão humana é da política, não do modelo: pedir no
        # prompt e confiar na resposta deixaria o modelo dispensar a revisão de
        # um evento material.
        "needs_human_review": bool(item.get("needs_human_review")) or materialidade >= 50,
        "classifier": f"gemini:{model}",
    }


def _urgencia_por_nota(score: int) -> str:
    return "critica" if score >= 85 else "alta" if score >= 70 else "media" if score >= 50 else "baixa"


def _state(score: int) -> str:
    return "critico" if score >= 85 else "alerta" if score >= 70 else "atencao" if score >= 50 else "normal"


def build_radar(
    previous: dict[str, Any], now: datetime, collected: list[dict[str, Any]],
    source_status: list[dict[str, Any]], api_key: str = "", model: str = "gemini-3.5-flash",
    portfolio_tickers: Iterable[str] = ("VIVA3", "CURY3", "CMIN3", "BBSE3", "LEVE3"),
) -> dict[str, Any]:
    old_events = {item["id"]: item for item in previous.get("events", [])}
    unique = {item["id"]: item for item in collected}
    portfolio_tickers = tuple(dict.fromkeys(portfolio_tickers))
    new_events = [item for key, item in unique.items() if key not in old_events]
    new_events.sort(key=lambda item: (
        item.get("source_tier") == "primaria_oficial",
        any(ticker.lower() in f"{item.get('title', '')} {item.get('summary', '')}".lower() for ticker in portfolio_tickers),
        item.get("published_at", ""),
    ), reverse=True)
    new_events = new_events[:MAX_NEW_ITEMS_PER_RUN]
    classifications: dict[str, dict[str, Any]] = {}
    classifier_status = "gemini_disponivel_sem_itens_novos" if api_key else "deterministico_sem_chave"
    classifier_error = None
    upgrade_events = [
        item for item in old_events.values()
        if item.get("classification", {}).get("classifier") == "regras_deterministicas"
    ][:40]
    new_ids = {item["id"] for item in new_events}
    classification_targets = (new_events + [item for item in upgrade_events if item["id"] not in new_ids])[:MAX_GEMINI_ITEMS_PER_RUN]
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
    sources_ok = sum(1 for item in source_status if item.get("status") == "ok")
    # "normal" só quando alguém de fato olhou: sem nenhuma fonte respondendo, o estado é "sem_coleta".
    collection = "completa" if source_status and sources_ok == len(source_status) else "parcial" if sources_ok else "sem_coleta"
    consolidation = {
        "run_at": _iso(now), "window_hours": 12, "new_items": len(new_events),
        "items_by_state": {state: sum(item["state"] == state for item in new_events) for state in ("critico", "alerta", "atencao", "normal")},
        "source_status": source_status, "sources_ok": f"{sources_ok}/{len(source_status)}", "collection": collection,
        "classifier_status": classifier_status,
        "classifier_error": classifier_error, "state": "sem_coleta" if collection == "sem_coleta" else _state(top_score),
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


def collect(
    now: datetime, lookback_hours: int = 36,
    portfolio_tickers: Iterable[str] = ("VIVA3", "CURY3", "CMIN3", "BBSE3", "LEVE3"),
    previous_source_status: Iterable[dict[str, Any]] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff = now - timedelta(hours=lookback_hours)
    events: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    portfolio_query = " OR ".join(dict.fromkeys(portfolio_tickers))
    queries = (*BASE_NEWS_QUERIES, portfolio_query) if portfolio_query else BASE_NEWS_QUERIES
    previous_sources = {item.get("source"): item for item in previous_source_status}
    previous_cvm = previous_sources.get("CVM IPE", {})
    try:
        counters: dict[str, Any] = {}
        cvm_events, fingerprint, cached = fetch_cvm_ipe(
            now.year, cutoff,
            known_fingerprint=previous_cvm.get("fingerprint", "") if previous_cvm.get("status") == "ok" else "",
            counters=counters,
        )
        events.extend(cvm_events)
        unreadable = bool(counters) and counters["rows_read"] > 0 and not counters["columns_recognised"]
        statuses.append({
            "source": "CVM IPE", "status": "formato_desconhecido" if unreadable else "ok", "items": len(cvm_events),
            "fingerprint": fingerprint, "download": "dispensado_sem_atualizacao" if cached else "atualizado",
            "rows": counters or previous_cvm.get("rows", {}),
        })
    except Exception as error:
        statuses.append({"source": "CVM IPE", "status": "indisponivel", "items": 0, "detail": f"{type(error).__name__}: {error}"[:240]})
    sources = [(f"Google Notícias · {query}", lambda query=query: fetch_google_news(query, cutoff)) for query in queries]
    for name, function in sources:
        try:
            source_events = function()
            events.extend(source_events)
            statuses.append({"source": name, "status": "ok", "items": len(source_events)})
        except Exception as error:
            statuses.append({"source": name, "status": "indisponivel", "items": 0, "detail": f"{type(error).__name__}: {error}"[:240]})
    return list({item["id"]: item for item in events}.values()), statuses


def _tickers_in(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    definitions = data.get("portfolio_definitions", {})
    allocation = (definitions.get("benevente2") or definitions.get("benevente1") or {}).get("target_allocation", [])
    return [item["ticker"] for item in allocation if item.get("ticker") and item["ticker"] != "CDI"]


def load_portfolio_tickers(web_directory: Path) -> tuple[str, ...]:
    """União dos tickers de todos os perfis publicados; o arquivo legado só entra quando não há perfil."""
    profile_files = sorted(web_directory.glob("live_performance_*.json"))
    sources = profile_files or [web_directory / "live_performance.json"]
    tickers: dict[str, None] = {}
    for path in sources:
        if path.exists():
            tickers.update(dict.fromkeys(_tickers_in(path)))
    return tuple(tickers) or ("VIVA3", "CURY3", "CMIN3", "BBSE3", "LEVE3")


def update(output: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(BRT)
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    portfolio_tickers = load_portfolio_tickers(output.parent)
    previous_runs = previous.get("consolidations", [])
    events, status = collect(
        now, lookback_hours=168 if not previous.get("events") else 36,
        portfolio_tickers=portfolio_tickers,
        previous_source_status=previous_runs[0].get("source_status", []) if previous_runs else [],
    )
    result = build_radar(
        previous, now, events, status, api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip(),
        portfolio_tickers=portfolio_tickers,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
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
