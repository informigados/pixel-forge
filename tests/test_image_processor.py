from PIL import Image

from app.image_processor import process_single_image
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
