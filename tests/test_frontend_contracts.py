import re


def _read_index(project_root) -> str:
    index_file = project_root / "static" / "index.html"
    return index_file.read_text(encoding="utf-8")


def _classes_for_id(content: str, element_id: str) -> set[str]:
    tag_match = re.search(rf'<[^>]*\bid="{re.escape(element_id)}"[^>]*>', content)
    assert tag_match, f"Elemento com id='{element_id}' não encontrado"
    class_match = re.search(r'class="([^"]*)"', tag_match.group(0))
    assert class_match, f"Atributo class ausente no id='{element_id}'"
    return set(class_match.group(1).split())


def test_hidden_elements_do_not_ship_with_conflicting_layout_classes(project_root):
    content = _read_index(project_root)

    contract = [
        ("comparison-modal", {"hidden"}, {"flex"}),
        ("comparison-mode-2", {"hidden"}, {"grid", "grid-cols-2"}),
        ("dim-overlay-images", {"hidden"}, {"flex"}),
        ("dim-overlay-videos", {"hidden"}, {"flex"}),
        ("sentinel-badge", {"hidden"}, {"flex"}),
    ]

    for element_id, required, forbidden in contract:
        classes = _classes_for_id(content, element_id)
        assert required.issubset(classes), f"{element_id} deveria conter {required}"
        assert classes.isdisjoint(forbidden), f"{element_id} não deve conter {forbidden}"


def test_comparison_js_toggles_modal_and_grid_classes(project_root):
    content = _read_index(project_root)

    assert "modal.classList.remove('hidden');" in content
    assert "modal.classList.add('flex');" in content
    assert "modal.classList.add('hidden');" in content
    assert "modal.classList.remove('flex');" in content
    assert "mode2.classList.remove('grid', 'grid-cols-2');" in content
    assert "mode2.classList.add('grid', 'grid-cols-2');" in content
    assert "const customModal = document.getElementById('custom-modal');" in content
    assert "if (customModal && !customModal.classList.contains('hidden')) {" in content
    assert "CustomModal.close();" in content


def test_processing_console_and_video_mode_restore_contract(project_root):
    content = _read_index(project_root)

    assert "const LOG_MAX_LINES = 500;" in content
    assert "logLines = logLines.slice(-LOG_MAX_LINES);" in content
    assert "logEl.textContent = logLines.join('\\n') + '\\n';" in content
    assert "innerText" not in content

    assert "const videoMode = config.video_mode || config.mode || 'upload';" in content
    assert "input[name=\"mode_videos\"][value=\"folder\"]" in content
    assert "input[name=\"mode_videos\"][value=\"upload\"]" in content


def test_frontend_polish_and_feedback_contract(project_root):
    content = _read_index(project_root)

    assert "showToast('Não foi possível abrir o seletor de pasta.', 'error');" in content
    assert "showToast('Erro ao selecionar pasta.', 'error');" in content
    assert "p-4 sm:p-8" in content
    assert "absolute top-4 right-4 z-50" not in content
    assert "sm:absolute sm:top-4 sm:right-4" in content
    assert "hidden mx-auto sm:mx-0 sm:absolute sm:top-8 sm:right-8" in content
    assert 'href="https://github.com/informigados/pixel-forge/"' in content
    assert 'href="http://github.com/informigados/pixel-forge/"' not in content


def test_sentinel_error_translation_key_exists_in_all_languages(project_root):
    content = _read_index(project_root)
    assert content.count("sentinel_error:") == 4
    assert 'sentinel_error: "Erro (Sentinela): {file}"' in content
    assert 'formatI18n(\'sentinel_error\', { file: data.file }' in content


def test_image_dimensions_checkbox_is_outside_overlay_grid(project_root):
    content = _read_index(project_root)
    assert (
        '</div>\n                <div class="flex items-center gap-2 mt-1">\n'
        '                    <input type="checkbox" id="keep-original-dims"'
    ) in content


def test_presets_allow_no_preset_selection_for_images_and_videos(project_root):
    content = _read_index(project_root)
    assert '<option value="none" selected data-i18n="preset_none">Sem preset (Original)</option>' in content


def test_language_menu_uses_click_toggle_contract(project_root):
    content = _read_index(project_root)
    assert 'id="language-switcher"' in content
    assert 'id="lang-toggle-btn"' in content
    assert 'id="lang-menu"' in content
    assert "onclick=\"toggleLanguageMenu()\"" in content
    assert "function toggleLanguageMenu(forceOpen = null)" in content
    assert "closeLanguageMenu();" in content
    assert "group-hover:block" not in content


def test_video_tab_vertical_spacing_and_footer_year_contract(project_root):
    content = _read_index(project_root)
    assert '<div id="tab-videos" class="hidden">' in content
    assert "copyrightEl.textContent = `${year} © Pixel Forge`;" in content


def test_processing_flow_avoids_duplicate_submits_and_ws_races(project_root):
    content = _read_index(project_root)

    assert "const isProcessing = { images: false, videos: false };" in content
    assert "if (isProcessing[type]) {" in content
    assert "isProcessing[type] = true;" in content
    assert "isProcessing[type] = false;" in content
    assert "function hasActiveWebSocket()" in content
    assert "return Boolean(wsIsOpen && ws && ws.readyState === WebSocket.OPEN);" in content
    assert "if (hasActiveWebSocket()) {" in content
    assert "formData.append('client_id', clientId);" in content
    assert "WebSocket ainda não está pronto; processamento seguirá sem progresso em tempo real." in content


def test_client_id_and_preset_contracts_use_supported_and_guarded_access(project_root):
    content = _read_index(project_root)

    assert ".substr(2)" not in content
    assert "Math.random().toString(36).slice(2)" in content
    assert content.count("const targetFormatSelect = form?.elements?.namedItem('target_format');") == 2
    assert "if (preset.format && targetFormatSelect) targetFormatSelect.value = preset.format;" in content


def test_websocket_fallback_log_uses_correct_portuguese_accents(project_root):
    content = _read_index(project_root)

    assert "WebSocket ainda não está pronto; processamento seguirá sem progresso em tempo real." in content
    assert "WebSocket ainda nao esta pronto; processamento seguira sem progresso em tempo real." not in content
