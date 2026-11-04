from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
from PIL import Image

from app import desktop


class FakeServer:
    def __init__(self, config):
        self.started = False
        self.should_exit = False

    def run(self):
        self.started = True
        while not self.should_exit:
            threading.Event().wait(0.005)


@pytest.mark.parametrize('fail_gui', [False, True])
def test_desktop_has_native_frame_and_stops_backend(monkeypatch, fail_gui):
    import app.main as main
    calls = {}
    stopped = []
    selected = ['C:/Pictures']
    window = SimpleNamespace(create_file_dialog=lambda mode: selected)
    def create(title, url, **kwargs):
        calls.update(title=title, url=url, **kwargs)
        return window
    def start(**kwargs):
        calls['start'] = kwargs
        assert main.app.state.folder_picker() == 'C:/Pictures'
        selected.clear()
        assert main.app.state.folder_picker() == ''
        if fail_gui:
            raise RuntimeError('Renderer unavailable')
    fake = SimpleNamespace(create_window=create, start=start, settings={},
                           FileDialog=SimpleNamespace(FOLDER=1))
    server = FakeServer(None)
    monkeypatch.setattr(main.video_processor, 'stop_active_processes', lambda: stopped.append(True))
    if fail_gui:
        with pytest.raises(RuntimeError, match='Renderer unavailable'):
            desktop.run_desktop(8042, webview_module=fake, server_factory=lambda cfg: server)
    else:
        desktop.run_desktop(8042, webview_module=fake, server_factory=lambda cfg: server)
    assert calls['resizable'] is True
    assert calls['frameless'] is False
    assert calls['url'] == 'http://127.0.0.1:8042'
    assert Path(calls['start']['icon']).name == 'app-icon.ico'
    assert server.should_exit
    assert stopped == [True]
    assert main.app.state.folder_picker is None


def test_owned_native_folder_picker_endpoint(client, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.app.state, 'folder_picker', lambda: str(tmp_path), raising=False)
    assert client.post('/select-folder').json()['path'] == str(tmp_path.resolve())
    monkeypatch.setattr(main.app.state, 'folder_picker', lambda: '', raising=False)
    assert client.post('/select-folder').json() == {'path': ''}


def test_windows_icon_has_all_sizes_and_transparency(project_root):
    with Image.open(project_root / 'static/images/app-icon.ico') as icon:
        assert {(16,16), (32,32), (48,48), (256,256)} <= icon.ico.sizes()
        assert icon.convert('RGBA').getpixel((0,0))[3] == 0
    with Image.open(project_root / 'static/images/logo.png') as logo:
        assert logo.size == (2172, 724)


def test_close_terminates_only_active_conversion_processes():
    from app.video_processor import VideoProcessor
    calls = []
    class Process:
        def poll(self): return None
        def terminate(self): calls.append('terminated')
    processor = VideoProcessor()
    processor._active_processes.add(Process())
    processor.stop_active_processes()
    assert calls == ['terminated']
    assert processor._stopping.is_set()
