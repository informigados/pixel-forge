from pathlib import Path


def test_security_policy_includes_private_reporting_channels(project_root: Path):
    content = (project_root / "SECURITY.md").read_text(encoding="utf-8")

    assert "GitHub Security Advisories" in content
    assert "security@informigados.com.br" in content


def test_contributing_mentions_dev_dependencies_and_frontend_build(project_root: Path):
    content = (project_root / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "requirements-dev.txt" in content
    assert "npm run build:frontend" in content


def test_bootstrap_scripts_delegate_python_and_ffmpeg_checks_to_start(project_root: Path):
    run_bat = (project_root / "run.bat").read_text(encoding="utf-8")
    run_sh = (project_root / "run.sh").read_text(encoding="utf-8")

    assert 'start.py --check-python' in run_bat
    assert 'start.py --check-ffmpeg' in run_bat
    assert 'requirements-dev.txt' in run_bat
    assert 'PIXEL_FORGE_INSTALL_DEV' in run_bat

    assert 'start.py --check-python' in run_sh
    assert 'start.py --check-ffmpeg' in run_sh
    assert 'requirements-dev.txt' in run_sh
    assert 'PIXEL_FORGE_INSTALL_DEV' in run_sh


def test_about_tab_content_is_translatable_and_author_assets_exist(project_root: Path):
    index_html = (project_root / "static" / "index.html").read_text(encoding="utf-8")

    for key in [
        "about_header",
        "about_version",
        "about_description",
        "about_feature_presets_title",
        "about_feature_presets_desc",
        "about_feature_sentinel_title",
        "about_feature_sentinel_desc",
        "about_feature_performance_title",
        "about_feature_performance_desc",
        "about_feature_privacy_title",
        "about_feature_privacy_desc",
        "about_credits_title",
        "about_built_by",
        "about_repo_link",
        "about_authors_title",
    ]:
        assert f'data-i18n="{key}"' in index_html

    assert (project_root / "static" / "images" / "authors" / "informigados.webp").exists()
    assert (project_root / "static" / "images" / "authors" / "alex-brito-dev.webp").exists()
