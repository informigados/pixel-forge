import asyncio
import io
import logging
import tempfile
from contextlib import suppress
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(20, 40, 60)).save(buf, format="PNG")
    return buf.getvalue()


def _make_transparent_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (32, 32), color=(0, 0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


TEST_SENTINEL_WAIT_SECONDS = 0.05
ERROR_NO_FILE_SENT = "Nenhum arquivo enviado"
ERROR_INVALID_MODE = "Modo inválido"
MINIMAL_MP4_BYTES = (
    b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
)


def test_process_without_files_returns_400(client):
    response = client.post(
        "/process",
        data={
            "mode": "upload",
            "output_dir": "output/images",
            "target_format": "webp",
            "quality": "80",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == ERROR_NO_FILE_SENT


def test_system_check_returns_expected_keys(client):
    response = client.get("/system-check")
    assert response.status_code == 200
    payload = response.json()
    assert "ffmpeg" in payload
    assert "avif" in payload
    assert isinstance(payload["ffmpeg"], bool)
    assert isinstance(payload["avif"], bool)


def test_process_invalid_mode_returns_400(client):
    response = client.post(
        "/process",
        data={
            "mode": "invalid",
            "output_dir": "output/images",
            "target_format": "webp",
            "quality": "80",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == ERROR_INVALID_MODE


def test_image_upload_process_and_preview(client):
    image_data = _make_png_bytes()
    with tempfile.TemporaryDirectory() as td:
        out_dir = str(Path(td) / "out")
        response = client.post(
            "/process",
            data={
                "mode": "upload",
                "output_dir": out_dir,
                "target_format": "jpg",
                "quality": "75",
            },
            files={"files": ("sample.png", image_data, "image/png")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["processed_count"] == 1
        assert payload["errors"] == []
        processed_path = payload["results"][0]["processed"]
        assert Path(processed_path).exists()

        preview_response = client.get("/preview", params={"path": processed_path})
        assert preview_response.status_code == 200


def test_process_video_folder_empty_is_success(client):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source"
        out = Path(td) / "out"
        src.mkdir()
        out.mkdir()

        # only image in folder; video processor should return success with zero processed videos
        Image.new("RGB", (32, 32), color=(1, 2, 3)).save(src / "image.jpg")

        response = client.post(
            "/process-video",
            data={
                "mode": "folder",
                "source_dir": str(src),
                "output_dir": str(out),
                "target_format": "mp4",
                "quality": "80",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["processed_count"] == 0
        assert payload["results"] == []


def test_preview_blocks_non_allowed_path(client, project_root):
    readme = project_root / "README.md"
    response = client.get("/preview", params={"path": str(readme.resolve())})
    assert response.status_code == 403
    assert response.json()["detail"] == "Acesso negado para este caminho"


def test_open_location_blocks_non_allowed_path(client, project_root):
    readme = project_root / "README.md"
    response = client.post("/open-location", json={"path": str(readme.resolve())})
    assert response.status_code == 403
    assert response.json()["detail"] == "Acesso negado para este caminho"


def test_register_allowed_root_missing_directory_does_not_expand_to_parent(tmp_path):
    import app.main as main_module

    missing_dir = (tmp_path / "new-allowed-root").resolve()
    parent_dir = missing_dir.parent

    with main_module.ALLOWED_PATHS_LOCK:
        original_roots = set(main_module.ALLOWED_PATH_ROOTS)
        main_module.ALLOWED_PATH_ROOTS.clear()

    try:
        main_module._register_allowed_root(missing_dir)
        with main_module.ALLOWED_PATHS_LOCK:
            current_roots = set(main_module.ALLOWED_PATH_ROOTS)

        assert missing_dir in current_roots
        assert parent_dir not in current_roots
    finally:
        with main_module.ALLOWED_PATHS_LOCK:
            main_module.ALLOWED_PATH_ROOTS.clear()
            main_module.ALLOWED_PATH_ROOTS.update(original_roots)


def test_validate_directory_input_allows_new_nested_output_path(tmp_path):
    import app.main as main_module

    target = tmp_path / "nested" / "output" / "images"
    validated = main_module._validate_directory_input(
        target,
        field_name="Pasta de destino",
        must_exist=False,
    )

    assert validated == target.resolve()


def test_select_folder_returns_error_details_when_dialog_fails(client, monkeypatch):
    monkeypatch.setattr(
        "app.main._open_folder_dialog",
        lambda: ("", "Seletor indisponível em ambiente sem interface gráfica"),
    )

    response = client.post("/select-folder")
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == ""
    assert "error" in payload
    assert "indisponível" in payload["error"]


def test_image_upload_file_count_limit_returns_413(client, monkeypatch):
    monkeypatch.setattr("app.main.MAX_IMAGE_UPLOAD_FILES", 1)
    image_bytes = _make_png_bytes()
    response = client.post(
        "/process",
        data={
            "mode": "upload",
            "output_dir": "output/images",
            "target_format": "webp",
            "quality": "80",
        },
        files=[
            ("files", ("a.png", image_bytes, "image/png")),
            ("files", ("b.png", image_bytes, "image/png")),
        ],
    )
    assert response.status_code == 413
    assert "limite de 1" in response.json()["detail"]


def test_video_upload_file_count_limit_returns_413(client, monkeypatch):
    monkeypatch.setattr("app.main.MAX_VIDEO_UPLOAD_FILES", 1)
    fake_video = MINIMAL_MP4_BYTES
    response = client.post(
        "/process-video",
        data={
            "mode": "upload",
            "output_dir": "output/videos",
            "target_format": "mp4",
            "quality": "80",
        },
        files=[
            ("files", ("a.mp4", fake_video, "video/mp4")),
            ("files", ("b.mp4", fake_video, "video/mp4")),
        ],
    )
    assert response.status_code == 413
    assert "limite de 1" in response.json()["detail"]


def test_process_transparent_png_to_jpg_uses_white_background(client):
    image_data = _make_transparent_png_bytes()
    with tempfile.TemporaryDirectory() as td:
        out_dir = str(Path(td) / "out")
        response = client.post(
            "/process",
            data={
                "mode": "upload",
                "output_dir": out_dir,
                "target_format": "jpg",
                "quality": "90",
            },
            files={"files": ("transparent.png", image_data, "image/png")},
        )
        assert response.status_code == 200
        processed_path = Path(response.json()["results"][0]["processed"])
        assert processed_path.exists()

        with Image.open(processed_path) as out_image:
            pixel = out_image.getpixel((0, 0))
            assert pixel[0] >= 240
            assert pixel[1] >= 240
            assert pixel[2] >= 240


def test_config_rejects_unknown_keys(client):
    response = client.post("/config", json={"quality": 80, "unexpected": "value"})
    assert response.status_code == 422


def test_config_rejects_invalid_quality_type(client):
    response = client.post("/config", json={"quality": "../../etc/passwd"})
    assert response.status_code == 422


def test_open_location_windows_file_uses_select_flag(client, project_root, monkeypatch):
    target_file = project_root / "output" / "images" / "safe-test.txt"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("ok", encoding="utf-8")

    popen_calls = []

    def fake_popen(args, *unused_args, **unused_kwargs):
        popen_calls.append(args)
        return Mock()

    monkeypatch.setattr("app.main.platform.system", lambda: "Windows")
    monkeypatch.setattr("app.main.subprocess.Popen", fake_popen)

    response = client.post("/open-location", json={"path": str(target_file.resolve())})
    assert response.status_code == 200
    assert popen_calls
    assert popen_calls[0][0] == "explorer"
    assert popen_calls[0][1].startswith("/select,")
    assert str(target_file.resolve()) in popen_calls[0][1]


def test_open_location_internal_error_does_not_leak_exception_details(client, project_root, monkeypatch):
    target_file = project_root / "output" / "images" / "safe-open-error.txt"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("ok", encoding="utf-8")

    def fake_popen(*args, **kwargs):
        raise RuntimeError("segredo-interno")

    monkeypatch.setattr("app.main.subprocess.Popen", fake_popen)

    response = client.post("/open-location", json={"path": str(target_file.resolve())})
    assert response.status_code == 500
    assert response.json()["detail"] == "Erro interno ao abrir localização"
    assert "segredo-interno" not in response.text


def test_update_config_internal_error_does_not_leak_exception_details(client, monkeypatch):
    def fake_save_config(*args, **kwargs):
        raise RuntimeError("segredo-config")

    monkeypatch.setattr("app.main.save_config", fake_save_config)

    response = client.post("/config", json={"output_dir": "output/images"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Erro interno ao atualizar configuração"
    assert "segredo-config" not in response.text


def test_websocket_endpoint_accepts_connection(client):
    with client.websocket_connect("/ws/test-client", headers={"host": "localhost"}) as websocket:
        websocket.send_text("ping")
        assert websocket is not None
        websocket.close()


def test_websocket_receives_image_progress_for_folder_processing(client):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "src"
        out = Path(td) / "out"
        src.mkdir()
        out.mkdir()
        (src / "progress.png").write_bytes(_make_png_bytes())

        with client.websocket_connect("/ws/progress-client", headers={"host": "localhost"}) as websocket:
            response = client.post(
                "/process",
                data={
                    "mode": "folder",
                    "source_dir": str(src),
                    "output_dir": str(out),
                    "target_format": "webp",
                    "quality": "80",
                    "client_id": "progress-client",
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["processed_count"] == 1

            ws_msg = websocket.receive_json()
            assert ws_msg["type"] == "progress"
            assert ws_msg["category"] == "images"
            assert ws_msg["file"] == "progress.png"
            assert isinstance(ws_msg["percent"], int)


def test_log_future_exception_records_background_failures(caplog):
    from concurrent.futures import Future

    import app.main as main_module

    future = Future()
    try:
        raise RuntimeError("falha-background")
    except RuntimeError as exc:
        future.set_exception(exc)

    with caplog.at_level(logging.ERROR, logger="pixelforge"):
        main_module._log_future_exception(future, context="Erro ao reportar progresso")

    assert "Erro ao reportar progresso" in caplog.text
    assert "falha-background" in caplog.text


def test_ensure_directory_accepts_path_instance(tmp_path):
    from app.utils import ensure_directory

    target = tmp_path / "nested" / "dir"
    created = ensure_directory(target)

    assert created.exists()
    assert created.is_dir()
    assert created == target.resolve()


def test_sentinel_video_processing_works_with_three_return_values(monkeypatch, tmp_path):
    import app.main as main_module

    original_sleep = asyncio.sleep

    async def fast_sleep(delay, *args, **kwargs):
        return await original_sleep(min(delay, 0.01), *args, **kwargs)

    watch_dir = tmp_path / "watch"
    output_dir = tmp_path / "out"
    watch_dir.mkdir()
    output_dir.mkdir()
    video_file = watch_dir / "clip.mp4"
    video_file.write_bytes(b"fake-video-bytes")

    sent_messages = []

    async def fake_broadcast(message):
        sent_messages.append(message)

    async def fake_process_video(file_path, output_dir, *args, **kwargs):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "clip.mp4"
        out_path.write_bytes(b"processed")
        return True, "ok", str(out_path)

    monkeypatch.setattr(main_module.manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(main_module.video_processor, "process_video", fake_process_video)
    monkeypatch.setattr(main_module.asyncio, "sleep", fast_sleep)
    monkeypatch.setattr(
        main_module,
        "load_config",
        lambda: {
            "mode": "upload",
            "output_dir": str(output_dir),
            "source_dir": "",
            "target_format": "mp4",
            "quality": 80,
            "width": None,
            "height": None,
            "sentinel_enabled": True,
            "watch_folder": str(watch_dir),
        },
    )

    old_in_progress = set(main_module.SENTINEL_IN_PROGRESS)
    old_recently_handled = dict(main_module.SENTINEL_RECENTLY_HANDLED)
    main_module.SENTINEL_IN_PROGRESS.clear()
    main_module.SENTINEL_RECENTLY_HANDLED.clear()

    try:
        async def _run_once():
            task = asyncio.create_task(main_module.sentinel_loop())
            await original_sleep(TEST_SENTINEL_WAIT_SECONDS)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await asyncio.gather(task)

        asyncio.run(_run_once())
    finally:
        main_module.SENTINEL_IN_PROGRESS.clear()
        main_module.SENTINEL_RECENTLY_HANDLED.clear()
        main_module.SENTINEL_IN_PROGRESS.update(old_in_progress)
        main_module.SENTINEL_RECENTLY_HANDLED.update(old_recently_handled)

    message_types = [msg.get("type") for msg in sent_messages]
    assert "sentinel_start" in message_types
    assert "sentinel_complete" in message_types
    assert "sentinel_error" not in message_types

    complete_msg = next(msg for msg in sent_messages if msg.get("type") == "sentinel_complete")
    assert "sentinel-mode" in complete_msg["original"]
    assert "originals" in complete_msg["original"]
    assert "sentinel-mode" in complete_msg["processed"]
    assert "processed" in complete_msg["processed"]


def test_process_request_mode_accepts_only_upload_or_folder():
    from pydantic import ValidationError

    from app.main import ProcessRequest

    valid = ProcessRequest(
        mode="upload",
        output_dir="output/images",
        target_format="webp",
        quality=80,
    )
    assert valid.mode == "upload"

    with pytest.raises(ValidationError):
        ProcessRequest(
            mode="invalid",
            output_dir="output/images",
            target_format="webp",
            quality=80,
        )
