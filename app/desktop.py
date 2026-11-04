"""Native desktop host; the existing local FastAPI app remains the workspace."""
import logging
import sys
import threading
import time

from .utils import get_app_base_path, get_app_data_path

APP_ID = 'INformigados.PixelForge'
logger = logging.getLogger('pixelforge')


def prepare_desktop_logging():
    """Windowed executables have no stdout/stderr; keep diagnostics on disk."""
    if sys.stdout is None or sys.stderr is None:
        logs = get_app_data_path() / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        stream = (logs / 'desktop.log').open('a', encoding='utf-8', buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream


def run_desktop(port, *, webview_module=None, server_factory=None):
    import uvicorn
    from .main import app
    from .video_processor import video_processor
    if webview_module is None:
        import webview as webview_module
    webview = webview_module
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    config = uvicorn.Config(app, host='127.0.0.1', port=port, reload=False,
                            timeout_graceful_shutdown=3, log_config=None)
    server = (server_factory or uvicorn.Server)(config)
    thread = threading.Thread(target=server.run, name='PixelForge server', daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('Não foi possível iniciar o serviço local do Pixel Forge.')
            time.sleep(0.05)
        screens = getattr(webview, 'screens', [])
        width = min(1120, max(420, screens[0].width - 64)) if screens else 1120
        height = min(900, max(480, screens[0].height - 80)) if screens else 900
        window = webview.create_window('Pixel Forge', f'http://127.0.0.1:{port}',
            width=width, height=height, min_size=(420, 480), resizable=True,
            frameless=False, background_color='#020617', text_select=True)

        def select_folder():
            selected = window.create_file_dialog(webview.FileDialog.FOLDER)
            return selected[0] if selected else ''

        app.state.folder_picker = select_folder
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True
        webview.settings['ALLOW_FILE_URLS'] = False
        webview.start(gui='edgechromium' if sys.platform == 'win32' else None,
                      private_mode=False, storage_path=str(get_app_data_path() / 'webview'),
                      icon=str(get_app_base_path() / 'static' / 'images' / 'app-icon.ico'))
    finally:
        app.state.folder_picker = None
        video_processor.stop_active_processes()
        server.should_exit = True
        thread.join(timeout=10)


def show_startup_error(error):
    logger.exception('Falha ao iniciar a janela do Pixel Forge')
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,
            'Não foi possível abrir o Pixel Forge.\n\n'
            'Reinstale usando o instalador completo para verificar o WebView2.\n\n'
            f'Detalhes: {error}', 'Pixel Forge', 0x10)
