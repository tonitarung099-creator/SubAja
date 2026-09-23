from app.core.subtitle import SubtitleEntry
from app.core.verbatim import is_verbatim_safe, tidy_local, split_entry_by_boundaries, lexical_tokens


def test_word_lock_accepts_only_formatting():
    assert is_verbatim_safe("aku nggak mau pergi kesana", "Aku nggak mau pergi kesana.")
    assert not is_verbatim_safe("aku nggak mau", "Aku tidak mau.")
    assert not is_verbatim_safe("aku udah pergi", "Aku pergi.")


def test_local_tidy_never_changes_words():
    src = "  aku   nggak mau pergi kesana  "
    out = tidy_local(src, add_terminal_punctuation=True)
    assert lexical_tokens(src) == lexical_tokens(out)


def test_split_preserves_all_words():
    e = SubtitleEntry(1, 1000, 5000, "aku sudah bilang kamu jangan pergi ke sana")
    parts = split_entry_by_boundaries(e, [(1000, "Speaker 1", 3000), (3000, "Speaker 2", 5000)])
    assert len(parts) == 2
    assert lexical_tokens(e.text) == lexical_tokens(" ".join(p.text for p in parts))
