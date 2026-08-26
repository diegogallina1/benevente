"""Gate a deployment on the security checks, instead of remembering to run them.

A checklist that lives in a document gets read once. This one exits non-zero, so
it can sit in front of the deploy command and fail the deploy when something
regresses. It has two modes:

``static``
    Runs against the working tree before anything is published. No network.
``live``
    Runs against a deployed URL and asserts the behaviour the static checks can
    only promise: the headers actually arrive, a foreign origin is actually
    refused, a malformed ticker is actually rejected.

Every check states what it is protecting against, because a check whose purpose
nobody remembers is the first one to be commented out when it goes red.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

REQUIRED_HEADERS = {
    "content-security-policy": "Sem CSP, qualquer injeção vira execução de script.",
    "strict-transport-security": "Sem HSTS, a primeira visita aceita downgrade para HTTP.",
    "x-content-type-options": "Sem nosniff, o navegador pode reinterpretar um JSON como HTML.",
    "x-frame-options": "Sem isso, a página pode ser embutida para clickjacking.",
    "referrer-policy": "Evita vazar a URL completa para terceiros.",
    "permissions-policy": "Nega câmera, microfone e geolocalização por padrão.",
}
# Interpolations that are safe inside innerHTML because they are numbers, colours
# derived from a fixed palette, or values already passed through the escaper.
SAFE_INTERPOLATION = re.compile(
    r"\$\{(escapeHtml\(|[A-Za-z_$][\w$]*\s*\?|.*?(?:toFixed|toLocaleString|format|pct|Pct|plain|Plain|seriesColor|"
    r"length|count|width|index|weight|Weight|value|Value|date|Date|number|Number)\b)")


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    def check(self, ok: bool, label: str, reason: str, fatal: bool = True) -> None:
        if ok:
            self.passed.append(label)
        elif fatal:
            self.failures.append(f"{label} — {reason}")
        else:
            self.warnings.append(f"{label} — {reason}")

    def report(self) -> int:
        for item in self.passed:
            print(f"  ok      {item}")
        for item in self.warnings:
            print(f"  atencao {item}")
        for item in self.failures:
            print(f"  FALHA   {item}")
        print(f"\n{len(self.passed)} ok, {len(self.warnings)} atenção, {len(self.failures)} falha(s)")
        return 1 if self.failures else 0


def static_checks(web: Path, repo: Path, result: Result) -> None:
    api = web / "api"

    # A secret reachable from the browser is a published secret.
    client_files = [path for path in web.rglob("*")
                    if path.suffix in {".js", ".html", ".json", ".css"} and api not in path.parents]
    leaked = [str(path.relative_to(repo)) for path in client_files
              if "process.env" in path.read_text(encoding="utf-8", errors="ignore")]
    result.check(not leaked, "nenhum process.env fora de api/",
                 f"variáveis de servidor alcançáveis pelo cliente: {leaked}")

    tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout.splitlines()
    real_env = [item for item in tracked if re.search(r"\.env(\.|$)", item) and not item.endswith(".example")]
    result.check(not real_env, "nenhum arquivo .env versionado", f"credenciais no repositório: {real_env}")

    # A syntax error in a serverless function is a 500 in production.
    for path in sorted(api.glob("*.js")):
        check = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        result.check(check.returncode == 0, f"sintaxe de {path.name}", check.stderr.strip()[:160])

    # Control characters in source are invisible in review and have hidden
    # meaning in a regular expression.
    for path in sorted(api.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        bad = [character for character in text
               if (ord(character) < 32 and character not in "\n\r\t") or ord(character) == 127]
        result.check(not bad, f"{path.name} sem caracteres de controle",
                     f"{len(bad)} caractere(s) invisível(is) no fonte")

    # Every public endpoint has to bound its own abuse.
    for path in sorted(api.glob("*.js")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        result.check("isRateLimited" in text, f"{path.name} com limite de taxa",
                     "endpoint público sem teto gasta cota paga de quem o hospeda")
        result.check("hasAllowedOrigin" in text, f"{path.name} com checagem de origem",
                     "sem allowlist, qualquer site chama este endpoint do navegador de um visitante")

    config = json.loads((web / "vercel.json").read_text(encoding="utf-8"))
    present = {header["key"].lower() for block in config.get("headers", []) for header in block.get("headers", [])}
    for header, reason in REQUIRED_HEADERS.items():
        result.check(header in present, f"cabeçalho {header}", reason)

    # Heuristic, deliberately noisy on the side of caution: an interpolation
    # inside an innerHTML template that is not obviously a number or escaped.
    for path in sorted(web.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if "innerHTML" not in line:
                continue
            raw = [item for item in re.findall(r"\$\{[^}]*\}", line) if not SAFE_INTERPOLATION.match(item)]
            result.check(not raw, f"{path.name}:{number} escapa o que injeta",
                         f"interpolação sem escapeHtml em innerHTML: {raw[:3]}", fatal=False)


def live_checks(base: str, result: Result) -> None:
    import urllib.error
    import urllib.request

    # The edge rejects the default ``Python-urllib`` agent with 403, which made
    # every live check fail against a perfectly healthy deployment -- a false
    # alarm that reads exactly like an outage and could motivate rolling back a
    # good release. The checker identifies itself honestly rather than
    # impersonating a browser: it is the site owner's own monitoring.
    agent = "benevente-predeploy-check/1.0 (+https://benevente.dgo.fi)"

    def request(path: str, method: str = "GET", headers: dict | None = None) -> tuple[int, dict]:
        req = urllib.request.Request(f"{base.rstrip('/')}{path}", method=method,
                                     headers={"User-Agent": agent, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.status, {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as error:
            return error.code, {key.lower(): value for key, value in error.headers.items()}
        except Exception as exc:  # network failures should fail the gate, not pass it
            result.failures.append(f"requisição a {path} falhou — {exc}")
            return 0, {}

    status, headers = request("/")
    result.check(status == 200, "página inicial responde", f"status {status}")
    for header, reason in REQUIRED_HEADERS.items():
        result.check(header in headers, f"{header} presente em produção", reason)

    prices = "/api/chart-series?symbol=PETR4&start=2025-01-02&end=2025-12-30"
    status, _ = request(prices)
    result.check(status == 200, "endpoint de preços responde", f"status {status}")
    status, _ = request("/api/chart-series?symbol=..%2F..%2Fevil&start=2025-01-02&end=2025-12-30")
    result.check(status == 400, "ticker malformado é recusado", f"esperado 400, veio {status}")
    status, _ = request(prices, headers={"Origin": "https://evil.example"})
    result.check(status == 403, "origem externa recusada em preços", f"esperado 403, veio {status}")
    status, _ = request("/api/demo-request")
    result.check(status == 405, "contato recusa método errado", f"esperado 405, veio {status}")
    status, _ = request("/api/demo-request", method="POST", headers={"Origin": "https://evil.example"})
    result.check(status == 403, "origem externa recusada no contato", f"esperado 403, veio {status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Security gate to run before and after a deployment.")
    parser.add_argument("--web", default="web", help="Directory published to the host.")
    parser.add_argument("--url", help="Deployed base URL; adds the live checks.")
    parser.add_argument("--live-only", action="store_true", help="Skip the working-tree checks.")
    args = parser.parse_args()

    repo = Path(__file__).parent
    result = Result()
    if not args.live_only:
        print("Verificações no código:")
        static_checks(repo / args.web, repo, result)
    if args.url:
        print("\nVerificações no ambiente publicado:")
        live_checks(args.url, result)
    print()
    sys.exit(result.report())


if __name__ == "__main__":
    main()
