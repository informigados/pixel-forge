def test_windows_uses_create_no_window_flag(monkeypatch, tmp_path):
    import app.video_processor as video_processor_module

    popen_kwargs = {}

    class DummyProcess:
        def __init__(self):
            class _DummyStderr:
                def readline(self):
                    return ""

            self.stderr = _DummyStderr()

        def poll(self):
            return 0

    def fake_popen(*args, **kwargs):
        popen_kwargs.update(kwargs)
        return DummyProcess()

    processor = video_processor_module.VideoProcessor()
    processor.ffmpeg_path = "ffmpeg"

    monkeypatch.setattr(video_processor_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(video_processor_module.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(video_processor_module.subprocess, "Popen", fake_popen)

    success, message, output = processor._process_video_sync(
        ["ffmpeg", "-i", "input.mp4", "output.mp4"],
        0.0,
        tmp_path / "output.mp4",
        None,
    )

    assert success is True
    assert isinstance(message, str)
    assert output == str(tmp_path / "output.mp4")
    assert popen_kwargs["creationflags"] == 0x08000000


def test_get_subprocess_creationflags_is_zero_outside_windows(monkeypatch):
    import app.video_processor as video_processor_module

    monkeypatch.setattr(video_processor_module.platform, "system", lambda: "Linux")

    assert video_processor_module._get_subprocess_creationflags() == 0
