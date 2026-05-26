from scripts.clean_latex_from_ppt import clean_text


def test_clean_text_removes_noise_and_normalizes_latex():
    raw = "α ≤ β\u200b\n\\\\frac {x}{y}\x00\nnormal text\n"
    cleaned = clean_text(raw, unicode_math=True)

    assert r"\alpha" in cleaned
    assert r"\le" in cleaned
    assert r"\beta" in cleaned
    assert r"\frac" in cleaned
    assert "\u200b" not in cleaned
    assert "\x00" not in cleaned
