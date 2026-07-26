"""CJK-aware tokenizer unit tests."""

from app.services.matching.tokenize import bigrams, tokenize


def test_chinese_run_becomes_contiguous_bigrams():
    assert bigrams("队列研究") == ["队列", "列研", "研究"]


def test_single_character_run_is_kept():
    assert bigrams("护") == ["护"]


def test_latin_acronyms_are_kept_whole():
    tokens = tokenize("熟悉SPSS和GCP规范")
    assert "spss" in tokens
    assert "gcp" in tokens


def test_two_chinese_terms_sharing_a_word_share_a_bigram():
    a = set(tokenize("队列研究设计"))
    b = set(tokenize("社区糖尿病队列建设"))
    assert "队列" in a & b


def test_whitespace_splitting_would_have_failed_here():
    # Whole-clause "tokens" (the old behavior) share nothing; bigrams do.
    old_a = set("具有队列研究经验".split())
    old_b = set("参与社区队列随访".split())
    assert not (old_a & old_b)
    new_a = set(tokenize("具有队列研究经验"))
    new_b = set(tokenize("参与社区队列随访"))
    assert new_a & new_b


def test_bare_numbers_are_dropped():
    assert "2025" not in tokenize("发表于2025年")


def test_filler_only_bigrams_are_dropped():
    tokens = tokenize("的了在有")
    assert tokens == []


def test_empty_input():
    assert tokenize("") == []
