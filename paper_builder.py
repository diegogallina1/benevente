"""Validate that the canonical IEEE manuscript is present in the repository."""
from pathlib import Path


PAPER = Path("paper/ieee_cifer_2027.tex")


def build_paper_files() -> None:
    if not PAPER.exists():
        raise FileNotFoundError(f"Canonical manuscript not found: {PAPER}")
    text = PAPER.read_text(encoding="utf-8")
    required = ("Benevente Quant AI", "Prospective R", "ITR")
    if not all(item in text for item in required):
        raise ValueError("Canonical manuscript is incomplete")
    print(f"Canonical IEEE manuscript verified: {PAPER}")


if __name__ == "__main__":
    build_paper_files()
