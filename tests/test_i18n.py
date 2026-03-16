import re


def _extract_language_block(content: str, lang_key: str, next_key: str) -> str:
    pattern = rf"{re.escape(lang_key)}:\s*\{{(.*?)\n\s*\}},\n\s*{re.escape(next_key)}:"
    match = re.search(pattern, content, flags=re.S)
    assert match, f"Bloco de idioma não encontrado: {lang_key}"
    return match.group(1)


def _extract_keys_from_block(block: str) -> set[str]:
    return set(re.findall(r"^\s*([a-zA-Z0-9_]+)\s*:", block, flags=re.M))


def test_i18n_has_all_data_i18n_keys(project_root):
    index_file = project_root / "static" / "index.html"
    content = index_file.read_text(encoding="utf-8")

    data_i18n_keys = set(re.findall(r'data-i18n="([^"]+)"', content))
    assert data_i18n_keys, "Nenhuma chave data-i18n encontrada no HTML"

    pt_block = _extract_language_block(content, "pt", "'pt-pt'")
    pt_keys = _extract_keys_from_block(pt_block)

    missing = sorted(data_i18n_keys - pt_keys)
    assert not missing, f"Chaves data-i18n ausentes no idioma pt: {missing}"


def test_i18n_language_key_sets_are_consistent(project_root):
    index_file = project_root / "static" / "index.html"
    content = index_file.read_text(encoding="utf-8")

    pt_keys = _extract_keys_from_block(_extract_language_block(content, "pt", "'pt-pt'"))
    ptpt_keys = _extract_keys_from_block(_extract_language_block(content, "'pt-pt'", "en"))
    en_keys = _extract_keys_from_block(_extract_language_block(content, "en", "es"))
    es_block_match = re.search(r"es:\s*\{(.*?)\n\s*\}\n\s*\};", content, flags=re.S)
    assert es_block_match, "Bloco de idioma não encontrado: es"
    es_keys = _extract_keys_from_block(es_block_match.group(1))

    assert pt_keys == ptpt_keys == en_keys == es_keys
