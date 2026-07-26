"""Build the IDF table used by the requirement matcher.

Document frequency is computed over the requirement clauses segmented from the
committed HTML fixtures, so the weights are deterministic and reproducible — a
term common across postings (具有, 能力) gets a low weight, a distinctive one
(队列, 随访) a high one.  The output is committed as ``app/data/jd_idf.json``;
it is never recomputed from a live user's data, which would make the same match
score differently depending on who is logged in.

Run:  python -m scripts.build_idf      (from the backend/ directory)
"""

from __future__ import annotations

import glob
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from app.services.classifier import normalize_text  # noqa: E402
from app.services.matching.segment import segment_requirements  # noqa: E402
from app.services.matching.tokenize import tokenize  # noqa: E402

_BACKEND = Path(__file__).resolve().parents[1]
_OUT = _BACKEND / "app" / "data" / "jd_idf.json"


def _fixture_documents() -> list[str]:
    """Each requirement clause across all fixtures is one IDF 'document'."""
    documents: list[str] = []
    for path in sorted(glob.glob(str(_BACKEND / "fixtures" / "*" / "article*.html"))):
        html = Path(path).read_text(encoding="utf-8", errors="ignore")
        text = normalize_text(BeautifulSoup(html, "html.parser").get_text("\n", strip=True))
        documents.extend(segment_requirements(text).requirements)
    return documents


def build_idf(documents: list[str]) -> dict[str, float]:
    total = len(documents)
    if total == 0:
        return {}
    doc_frequency: dict[str, int] = {}
    for document in documents:
        for token in set(tokenize(document)):
            doc_frequency[token] = doc_frequency.get(token, 0) + 1
    # Smoothed IDF, so a token in every document still has a small positive weight.
    return {
        token: round(math.log((total + 1) / (freq + 1)) + 1.0, 4)
        for token, freq in sorted(doc_frequency.items())
    }


def main() -> None:
    documents = _fixture_documents()
    table = build_idf(documents)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(table, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(documents)} requirement documents -> {len(table)} tokens -> {_OUT}")


if __name__ == "__main__":
    main()
