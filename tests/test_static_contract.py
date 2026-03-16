from pathlib import Path


def test_index_uses_local_frontend_assets(project_root: Path):
    index_html = (project_root / "static" / "index.html").read_text(encoding="utf-8")

    assert "cdn.tailwindcss.com" not in index_html
    assert "cdnjs.cloudflare.com" not in index_html
    assert '/static/styles/app.css' in index_html
    assert '/static/vendor/fontawesome/css/all.min.css' in index_html


def test_index_includes_mobile_and_accessibility_regressions(project_root: Path):
    index_html = (project_root / "static" / "index.html").read_text(encoding="utf-8")

    assert '<meta name="description"' in index_html
    assert '<meta name="theme-color"' in index_html
    assert 'role="tablist"' in index_html
    assert 'class="tab-strip flex flex-nowrap' in index_html
    assert 'h-24 sm:h-32' in index_html
    assert 'aria-label="Qualidade da imagem"' in index_html
    assert 'aria-label="Qualidade do vídeo"' in index_html
    assert 'aria-valuetext="80%"' in index_html
    assert 'updateQualitySlider(this, \'quality-val-images\')' in index_html
    assert 'updateQualitySlider(this, \'quality-val-videos\')' in index_html


def test_manifest_exists_for_local_app_shell(project_root: Path):
    manifest_path = project_root / "static" / "manifest.webmanifest"
    manifest_text = manifest_path.read_text(encoding="utf-8")

    assert manifest_path.exists()
    assert '"name": "Pixel Forge"' in manifest_text
    assert '"theme_color": "#0f172a"' in manifest_text


def test_ci_workflow_uses_valid_actions_and_full_matrix(project_root: Path):
    workflow = (project_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v4" in workflow
    assert '- os: windows-latest\n            python-version: "3.12"' in workflow
    assert "python -m pytest -q --tb=short" in workflow
