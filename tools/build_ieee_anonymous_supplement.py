"""Build the double-anonymous supplementary archive for the IEEE submission.

The archive contains the dated protocol, result tables, source panels needed by
the published experiments and the small set of reproduction programs.  It does
not contain author names, repository addresses or local absolute paths.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "Benevente_Quant_AI_IEEE_Anonymous_Supplement.zip"

FILES = (
    "artifacts/paper_release/paper_evidence.json",
    "artifacts/paper_release/paper_release_manifest.json",
    "artifacts/published_nested/annual_holdings.csv",
    "artifacts/published_nested/annual_results.csv",
    "artifacts/published_nested/annual_transitions.csv",
    "artifacts/published_nested/daily_curve.csv",
    "artifacts/published_nested/protocol.json",
    "artifacts/llm_contamination/annual_by_arm.csv",
    "artifacts/llm_contamination/constraint_audit.csv",
    "artifacts/llm_contamination/summary.json",
    "data/b3_historical_universes_2012_2025.csv",
    "data/b3_primary_corporate_events_2011_2025.csv",
    "data/fundamentals_cvm_january_panel.csv",
    "data/market_snapshot_panel.csv",
    "backtest_engine.py",
    "build_nested_run_artifacts.py",
    "research_configuration_search.py",
    "research_llm_contamination.py",
    "tools/build_paper_release.py",
)


README = """# Anonymous supplementary archive

This archive accompanies the double-anonymous review version of the paper.
It contains the frozen protocol, annual and daily outputs, the four-arm
language-model sensitivity results, the historical universe and event panels,
and the programs required to inspect the calculations.

The language-model experiment is retrospective.  It is not evidence of
prospective alpha or absence of training-data contamination.  The production
contract keeps asset selection and portfolio weights deterministic; the model
only explains a sealed decision record.

Run `python tools/build_paper_release.py` from the extracted archive after
installing the dependencies described by the source imports.  The included
`MANIFEST.sha256` records the exact bytes submitted for review.
"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    missing = [relative for relative in FILES if not (ROOT / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing supplement files: {missing}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        (staging / "README.md").write_text(README, encoding="utf-8")

        for relative in FILES:
            source = ROOT / relative
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == "artifacts/llm_contamination/summary.json":
                payload = json.loads(source.read_text(encoding="utf-8"))
                payload.pop("cache_directory", None)
                target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            else:
                target.write_bytes(source.read_bytes())

        manifest_lines = []
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = path.relative_to(staging).as_posix()
            manifest_lines.append(f"{digest(path)}  {relative}")
        (staging / "MANIFEST.sha256").write_text(
            "\n".join(manifest_lines) + "\n", encoding="utf-8"
        )

        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(item for item in staging.rglob("*") if item.is_file()):
                archive.write(path, path.relative_to(staging).as_posix())

    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
