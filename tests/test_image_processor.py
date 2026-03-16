import pytest
from PIL import Image

from app.image_processor import ImageProcessingError, process_directory, process_single_image
from app.utils import iter_image_files, iter_video_files


def test_process_single_image_accepts_jpg_target(tmp_path):
    source = tmp_path / "input.png"
    Image.new("RGB", (40, 40), color=(100, 50, 10)).save(source)

    output_dir = tmp_path / "out"
    processed = process_single_image(
        source_path=source,
        output_dir=str(output_dir),
        target_format="jpg",
        quality=80,
        width=None,
        height=None,
        strip_metadata=True,
    )

    assert processed.exists()
    assert processed.suffix.lower() == ".jpg"


def test_iterators_only_return_supported_files(tmp_path):
    root = tmp_path / "source"
    root.mkdir()

    # image files
    Image.new("RGB", (10, 10), color=(1, 2, 3)).save(root / "a.png")
    Image.new("RGB", (10, 10), color=(4, 5, 6)).save(root / "b.jpg")
    # unsupported
    (root / "note.txt").write_text("hello", encoding="utf-8")
    # pretend video
    (root / "sample.mp4").write_bytes(b"fake")

    image_files = list(iter_image_files(str(root)))
    video_files = list(iter_video_files(str(root)))

    image_names = sorted(path.name for path in image_files)
    video_names = sorted(path.name for path in video_files)

    assert image_names == ["a.png", "b.jpg"]
    assert video_names == ["sample.mp4"]


def test_iterators_handle_nested_directories_and_ignore_hidden_files(tmp_path):
    root = tmp_path / "source"
    nested = root / "nested"
    deeper = nested / "deeper"
    hidden_dir = root / ".private"
    root.mkdir()
    nested.mkdir()
    deeper.mkdir()
    hidden_dir.mkdir()

    Image.new("RGB", (10, 10), color=(1, 2, 3)).save(root / "a.png")
    Image.new("RGB", (10, 10), color=(4, 5, 6)).save(nested / "b.jpg")
    Image.new("RGB", (10, 10), color=(7, 8, 9)).save(deeper / "c.webp")
    Image.new("RGB", (10, 10), color=(9, 8, 7)).save(root / ".hidden.png")
    Image.new("RGB", (10, 10), color=(3, 2, 1)).save(hidden_dir / "hidden-dir.png")
    (root / "sample.mp4").write_bytes(b"fake")
    (nested / "clip.mov").write_bytes(b"fake-mov")
    (root / ".hidden.mp4").write_bytes(b"fake-hidden")
    (hidden_dir / "secret.webm").write_bytes(b"fake-secret")

    image_names = sorted(path.relative_to(root).as_posix() for path in iter_image_files(root))
    video_names = sorted(path.relative_to(root).as_posix() for path in iter_video_files(root))

    assert image_names == ["a.png", "nested/b.jpg", "nested/deeper/c.webp"]
    assert video_names == ["nested/clip.mov", "sample.mp4"]


def test_process_single_image_raises_for_missing_source(tmp_path):
    missing_source = tmp_path / "does_not_exist.png"

    with pytest.raises(ImageProcessingError, match="origem inexistente"):
        process_single_image(
            source_path=missing_source,
            output_dir=str(tmp_path / "out"),
            target_format="jpg",
            quality=80,
            width=None,
            height=None,
            strip_metadata=True,
        )


def test_process_single_image_raises_for_unsupported_target_format(tmp_path):
    source = tmp_path / "input.png"
    Image.new("RGB", (40, 40), color=(10, 20, 30)).save(source)

    with pytest.raises(ImageProcessingError, match="Formato de saída não suportado"):
        process_single_image(
            source_path=source,
            output_dir=str(tmp_path / "out"),
            target_format="heic",
            quality=80,
            width=None,
            height=None,
            strip_metadata=True,
        )


def test_process_single_image_surfaces_output_permission_errors(tmp_path, monkeypatch):
    source = tmp_path / "input.png"
    Image.new("RGB", (40, 40), color=(10, 20, 30)).save(source)

    def fake_ensure_directory(_path):
        raise PermissionError("sem permissão")

    monkeypatch.setattr("app.image_processor.ensure_directory", fake_ensure_directory)

    with pytest.raises(PermissionError, match="sem permissão"):
        process_single_image(
            source_path=source,
            output_dir=str(tmp_path / "blocked"),
            target_format="jpg",
            quality=80,
            width=None,
            height=None,
            strip_metadata=True,
        )


def test_process_directory_iterates_source_only_once(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "out"
    source_dir.mkdir()
    Image.new("RGB", (20, 20), color=(1, 2, 3)).save(source_dir / "a.png")
    Image.new("RGB", (20, 20), color=(4, 5, 6)).save(source_dir / "b.png")

    import app.image_processor as image_processor_module

    original_iter = image_processor_module.iter_image_files
    call_count = 0

    def counting_iter(root_dir):
        nonlocal call_count
        call_count += 1
        return original_iter(root_dir)

    monkeypatch.setattr(image_processor_module, "iter_image_files", counting_iter)

    processed_count, errors, _duration_ms, results = process_directory(
        str(source_dir),
        str(output_dir),
        "jpg",
        80,
        None,
        None,
        True,
    )

    assert call_count == 1
    assert processed_count == 2
    assert errors == []
    assert len(results) == 2


def test_process_single_image_does_not_pass_optimize_for_tiff(tmp_path, monkeypatch):
    source = tmp_path / "input.png"
    Image.new("RGB", (20, 20), color=(1, 2, 3)).save(source)

    captured_kwargs = {}
    original_save = Image.Image.save

    def save_without_optimize(self, fp, format=None, **params):
        captured_kwargs.update(params)
        return original_save(self, fp, format=format, **params)

    monkeypatch.setattr(Image.Image, "save", save_without_optimize)

    processed = process_single_image(
        source_path=source,
        output_dir=str(tmp_path / "out"),
        target_format="tiff",
        quality=80,
        width=None,
        height=None,
        strip_metadata=True,
    )

    assert processed.exists()
    assert "optimize" not in captured_kwargs
