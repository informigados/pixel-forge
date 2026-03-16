import hashlib

import pytest


def test_extract_expected_digest_parses_matching_line():
    import setup_ffmpeg

    checksum_text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  other-file.zip\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  ffmpeg-win.zip\n"
    )

    digest = setup_ffmpeg._extract_expected_digest(
        checksum_text,
        "sha256",
        "ffmpeg-win.zip",
    )

    assert digest == "b" * 64


def test_verify_download_rejects_digest_mismatch(tmp_path):
    import setup_ffmpeg

    archive = tmp_path / "ffmpeg-win.zip"
    archive.write_bytes(b"archive-content")

    with pytest.raises(ValueError, match="Integrity verification failed"):
        setup_ffmpeg._verify_download(
            archive,
            algorithm="sha256",
            expected_digest="0" * 64,
        )


def test_verify_download_accepts_matching_digest(tmp_path):
    import setup_ffmpeg

    archive = tmp_path / "ffmpeg-linux.tar.xz"
    archive.write_bytes(b"archive-content")
    expected_digest = hashlib.md5(b"archive-content").hexdigest()

    setup_ffmpeg._verify_download(
        archive,
        algorithm="md5",
        expected_digest=expected_digest,
    )


def test_download_ffmpeg_uses_temporary_directory_for_archives(tmp_path, monkeypatch):
    import setup_ffmpeg

    download_targets = []

    class DummyTempDir:
        def __enter__(self):
            return str(tmp_path / "temp-ffmpeg")

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_download(url, destination):
        download_targets.append(destination)

    monkeypatch.setattr(setup_ffmpeg.platform, "system", lambda: "Windows")
    monkeypatch.setattr(setup_ffmpeg.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(setup_ffmpeg.tempfile, "TemporaryDirectory", lambda prefix="": DummyTempDir())
    monkeypatch.setattr(setup_ffmpeg, "_download_file", fake_download)
    monkeypatch.setattr(setup_ffmpeg, "_verify_download", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup_ffmpeg, "_extract_from_zip", lambda *args, **kwargs: set())
    monkeypatch.setattr(setup_ffmpeg, "_mark_executable_if_needed", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup_ffmpeg.Path, "exists", lambda self: False)

    setup_ffmpeg.download_ffmpeg()

    assert download_targets
    assert download_targets[0] == tmp_path / "temp-ffmpeg" / "ffmpeg-win.zip"
