"""Stamp every local CSS and JS reference with a hash of the file's content.

Three times in one session a corrected stylesheet or script never reached the
browser because its ``?v=`` parameter had not been bumped by hand. Each time the
symptom was indistinguishable from the fix not working, so the time went into
debugging the wrong file — and the same stale asset would have been served to
every visitor with a warm cache after deploy.

A hand-maintained version parameter fails in exactly this way: it is a promise
that someone will remember, and the failure is silent. Deriving the parameter
from the content removes the promise. The stamp changes when, and only when, the
file changes.

``--check`` makes the same rule enforceable in CI, so a stale stamp fails a test
instead of shipping.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
# Only local assets. A cross-origin URL is not ours to stamp, and a data: URI
# carries its own content already.
REFERENCE = re.compile(r'((?:href|src)="\./)([A-Za-z0-9_-]+\.(?:css|js))(\?v=[^"]*)?(")')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def stamp(page: Path, missing: list[str]) -> tuple[str, int]:
    source = page.read_text(encoding="utf-8")
    changes = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changes
        prefix, name, current, suffix = match.groups()
        asset = WEB / name
        if not asset.exists():
            missing.append(f"{page.name} → {name}")
            return match.group(0)
        wanted = f"?v={digest(asset)}"
        if current != wanted:
            changes += 1
        return f"{prefix}{name}{wanted}{suffix}"

    return REFERENCE.sub(replace, source), changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive every asset's cache parameter from its content.")
    parser.add_argument("--check", action="store_true",
                        help="Fail instead of writing, so CI catches a stale stamp.")
    args = parser.parse_args()

    missing: list[str] = []
    stale: list[str] = []
    for page in sorted(WEB.glob("*.html")):
        updated, changes = stamp(page, missing)
        if changes:
            stale.append(f"{page.name}: {changes} referência(s)")
            if not args.check:
                # newline explícito: no Windows o padrão grava CRLF, o
                # .gitattributes entrega LF, e o hash carimbado deixa de
                # bater com o arquivo que qualquer clone recebe.
                page.write_text(updated, encoding="utf-8", newline="\n")

    for item in missing:
        print(f"AUSENTE  {item}", file=sys.stderr)
    if args.check:
        for item in stale:
            print(f"DEFASADO {item}", file=sys.stderr)
        if stale or missing:
            print("\nRode tools/stamp_assets.py para regravar os parâmetros.", file=sys.stderr)
            return 1
        print("Todos os parâmetros de cache correspondem ao conteúdo.")
        return 0

    if missing:
        return 1
    print("\n".join(f"atualizado {item}" for item in stale) or "Nada a fazer: já estavam corretos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
