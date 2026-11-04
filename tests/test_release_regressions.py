import asyncio
from pathlib import Path

import pytest
from PIL import Image

from app.image_processor import process_directory, process_single_image


def convert(source, output, fmt="png", strip=True):
    return process_single_image(source, str(output), fmt, 80, None, None, strip)


def test_conversion_preserves_original_and_existing_outputs(tmp_path):
    source = tmp_path / "photo.png"
    Image.new("RGB", (16, 24), "red").save(source)
    original = source.read_bytes()
    first = convert(source, tmp_path)
    second = convert(source, tmp_path)
    assert len({source, first, second}) == 3
    assert source.read_bytes() == original
    with Image.open(second) as image:
        assert image.size == (16, 24)


@pytest.mark.parametrize("strip", [True, False])
def test_exif_orientation_is_applied_before_metadata_removal(tmp_path, strip):
    source = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Private author"
    Image.new("RGB", (40, 20), "blue").save(source, exif=exif)
    result = convert(source, tmp_path / "out", "jpg", strip)
    with Image.open(result) as image:
        assert image.size == (20, 40)
        assert image.getexif().get(274, 1) == 1
        assert bool(image.getexif().get(315)) is not strip


def test_recursive_conversion_excludes_destination_and_keeps_duplicate_names(tmp_path):
    source = tmp_path / "source"
    output = source / "output"
    for folder in [source / "one", source / "two", output]:
        folder.mkdir(parents=True)
        Image.new("RGB", (16, 16), "green").save(folder / "same.png")
    count, errors, _, results = process_directory(str(source), str(output), "png", 80, None, None)
    assert count == 2
    assert errors == []
    assert len({r["processed"] for r in results}) == 2


@pytest.mark.parametrize("endpoint", ["/process", "/process-video"])
@pytest.mark.parametrize("invalid", [{"quality": "101"}, {"width": "-1"}, {"height": "0"}])
def test_invalid_conversion_parameters_return_validation_error(client, tmp_path, endpoint, invalid):
    data = {"mode": "upload", "output_dir": str(tmp_path), "quality": "80",
            "target_format": "mp4" if endpoint.endswith('video') else "png", **invalid}
    assert client.post(endpoint, data=data).status_code == 422


def test_folder_images_are_available_for_comparison(client, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "photo.png"
    Image.new("RGB", (16, 16)).save(original)
    response = client.post('/process', data={"mode": "folder", "source_dir": str(source),
                           "output_dir": str(tmp_path / "out"), "target_format": "webp", "quality": "80"})
    assert response.json()["processed_count"] == 1
    assert client.get('/preview', params={"path": str(original)}).status_code == 200


def test_failed_videos_are_not_counted_as_success(client, tmp_path, monkeypatch):
    import app.main as main
    async def fail(*args, **kwargs):
        return False, "Invalid video", None
    monkeypatch.setattr(main.video_processor, "process_video", fail)
    response = client.post('/process-video', data={"mode": "upload", "output_dir": str(tmp_path),
                           "target_format": "mp4", "quality": "80"},
                           files={"files": ("broken.mp4", b"invalid", "video/mp4")})
    assert response.json()["processed_count"] == 0
    assert response.json()["errors"] == ["Invalid video"]


def test_sentinel_uses_video_format_for_default_image_config(tmp_path, monkeypatch):
    import app.main as main
    captured = []
    async def process(*args, **kwargs):
        captured.append(args[2])
        return True, "ok", str(tmp_path / "video.mp4")
    monkeypatch.setattr(main.video_processor, "process_video", process)
    asyncio.run(main._process_sentinel_media(tmp_path / 'input.mov', file_type='videos',
                config=main.default_config(), processed_dir=tmp_path))
    assert captured == ['mp4']


def test_frozen_data_directory_is_persistent(tmp_path, monkeypatch):
    import app.utils as utils
    monkeypatch.setattr(utils.sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('PIXEL_FORGE_DATA_DIR', raising=False)
    assert utils.get_app_data_path() == tmp_path / 'PixelForge'


def test_cross_site_posts_and_websockets_are_rejected(client):
    from starlette.websockets import WebSocketDisconnect
    assert client.post('/config', json={'sentinel_enabled': True},
                       headers={'Origin': 'https://untrusted.example'}).status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws/test', headers={'Origin': 'https://untrusted.example'}):
            pass


def test_python_preflight_works_without_installed_dependencies(project_root):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-S', str(project_root / 'start.py'), '--check-python'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_frozen_folder_picker_uses_helper_mode(monkeypatch):
    import app.main as main
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(main.platform, 'system', lambda: 'Windows')
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout='C:/Fotos/ação\n', stderr='')
    monkeypatch.setattr(main.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(main.subprocess, 'run', run)
    folder, error = main._open_folder_dialog()
    assert folder == 'C:/Fotos/ação'
    assert error == ''
    assert calls[0] == [main.sys.executable, '--select-folder']
