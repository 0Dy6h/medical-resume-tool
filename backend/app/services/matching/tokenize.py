"""CJK-aware tokenization for requirement↔fact comparison.

Chinese does not separate words with whitespace, so splitting on spaces (what
the previous matcher did) yields whole clauses as "tokens" and nothing can ever
overlap.  Contiguous character bigrams are used instead: they need no
dictionary, are deterministic, and match shared sub-terms — "队列研究" and
"社区糖尿病队列" share the 队列 bigram without either being a dictionary entry.

Latin/digit runs are kept whole ("SPSS", "GCP", "R"), since splitting those
would destroy the acronyms that carry the most signal.
"""

from __future__ import annotations

import re

#: One run of CJK characters, or one run of latin letters/digits.
_CJK_RUN = re.compile(r"[一-鿿]+")
_LATIN_RUN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]*|\d+(?:\.\d+)?")

#: Latin tokens too generic to carry matching signal.
_LATIN_STOPWORDS = frozenset(
    {
        "and", "or", "the", "of", "in", "for", "with", "to", "a", "an",
        "no", "id", "etc", "e", "g", "i",
    }
)

#: Single CJK characters that are pure grammar/filler.  Bigrams containing only
#: these are dropped so "的能力" style fragments do not become match evidence.
_CJK_FILLER = frozenset("的了和与及或者是在有为以对等就并且很非常一二三四五六七八九十")


def bigrams(text: str) -> list[str]:
    """Return contiguous character bigrams of one CJK run.

    A single-character run yields itself, so a one-character term is not lost.
    """
    if len(text) == 1:
        return [text]
    return [text[index : index + 2] for index in range(len(text) - 1)]


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/latin text into comparable units.

    Returns tokens in order, with duplicates kept so callers can weigh term
    frequency. Pure-filler bigrams and generic latin words are excluded.
    """
    if not text:
        return []
    tokens: list[str] = []
    lowered = text.lower()
    for match in _CJK_RUN.finditer(lowered):
        for gram in bigrams(match.group()):
            if all(char in _CJK_FILLER for char in gram):
                continue
            tokens.append(gram)
    for match in _LATIN_RUN.finditer(lowered):
        token = match.group()
        if token in _LATIN_STOPWORDS:
            continue
        if token.isdigit():
            # Bare numbers (years, counts) collide across unrelated entries.
            continue
        tokens.append(token)
    return tokens
