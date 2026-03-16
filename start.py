import argparse
import os
import shutil
import socket
import sys
import threading
import time
import webbrowser

import uvicorn
from pathlib import Path

from setup_ffmpeg import download_ffmpeg

MIN_PYTHON_VERSION = (3, 10)

def find_free_port(start_port=8000, max_port=8100):
    """
    Encontra uma porta livre disponível no sistema, começando de start_port.
    Tenta ligar o socket para garantir que a porta está realmente livre.
    """
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Tenta ligar na porta para ver se está disponível
                # Verifica disponibilidade apenas na interface local para manter o escopo do app em loopback.
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return None

def open_browser(url):
    """Abre o navegador padrão após um breve delay."""
    time.sleep(2) # Aguarda o servidor iniciar
    print(f"Abrindo navegador em: {url}")
    webbrowser.open(url)


def _ffmpeg_local_paths(base_dir: Path) -> tuple[Path, Path]:
    bin_dir = base_dir / "bin"
    if os.name == "nt":
        return (bin_dir / "ffmpeg.exe", bin_dir / "ffprobe.exe")
    return (bin_dir / "ffmpeg", bin_dir / "ffprobe")


def ensure_ffmpeg_available() -> bool:
    """Ensure FFmpeg/FFprobe exists locally or on PATH; auto-download if missing."""
    has_path_ffmpeg = bool(shutil.which("ffmpeg"))
    has_path_ffprobe = bool(shutil.which("ffprobe"))
    if has_path_ffmpeg and has_path_ffprobe:
        print("FFmpeg detectado no PATH.")
        return True

    base_dir = Path(__file__).resolve().parent
    local_ffmpeg, local_ffprobe = _ffmpeg_local_paths(base_dir)
    if local_ffmpeg.exists() and local_ffprobe.exists():
        print(f"FFmpeg local detectado em: {base_dir / 'bin'}")
        return True

    print("FFmpeg nao encontrado. Iniciando configuracao automatica...")
    try:
        download_ffmpeg()
    except Exception as exc:
        print(f"Falha durante configuracao automatica do FFmpeg: {exc}")

    has_path_ffmpeg = bool(shutil.which("ffmpeg"))
    has_path_ffprobe = bool(shutil.which("ffprobe"))
    if has_path_ffmpeg and has_path_ffprobe:
        print("FFmpeg configurado com sucesso via PATH.")
        return True
    if local_ffmpeg.exists() and local_ffprobe.exists():
        print(f"FFmpeg configurado com sucesso em: {base_dir / 'bin'}")
        return True

    print("Erro: FFmpeg/FFprobe nao disponiveis apos tentativa automatica.")
    print("Execute setup_ffmpeg.py manualmente ou instale FFmpeg no PATH.")
    return False


def ensure_supported_python_version(version_info=None) -> bool:
    current = version_info or sys.version_info
    current_version = tuple(current[:2]) if not hasattr(current, "major") else (current.major, current.minor)
    if current_version >= MIN_PYTHON_VERSION:
        return True

    if hasattr(current, "major"):
        detected = f"{current.major}.{current.minor}.{getattr(current, 'micro', 0)}"
    else:
        detected = ".".join(str(part) for part in current[:3])

    print(
        "Erro: Python "
        f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ e obrigatorio. "
        f"Versao detectada: {detected}"
    )
    return False


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap do Pixel Forge.")
    parser.add_argument("--check-python", action="store_true", help="Verifica se a versao do Python e suportada.")
    parser.add_argument("--check-ffmpeg", action="store_true", help="Verifica se FFmpeg/FFprobe estao disponiveis.")
    return parser


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.check_python or args.check_ffmpeg:
        if args.check_python and not ensure_supported_python_version():
            return 1
        if args.check_ffmpeg and not ensure_ffmpeg_available():
            return 1
        return 0

    if not ensure_supported_python_version():
        return 1
    if not ensure_ffmpeg_available():
        return 1

    # Tenta encontrar uma porta livre
    port = find_free_port()
    
    if port is None:
        print("Erro Crítico: Nenhuma porta disponível entre 8000 e 8100.")
        print("Por favor, feche algumas aplicações e tente novamente.")
        sys.exit(1)
        
    host = "127.0.0.1"
    url = f"http://localhost:{port}"
    reload_enabled = os.getenv("PIXEL_FORGE_DEV_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    
    print("===================================================")
    print("  Pixel Forge - Equipe Informigados")
    print("  Iniciando sistema de forma inteligente...")
    print(f"  Porta selecionada: {port}")
    print(f"  Acesse: {url}")
    print("===================================================")
    
    # Inicia a thread para abrir o navegador
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    # Inicia o servidor Uvicorn
    # 'app.main:app' é o caminho para a aplicação FastAPI
    # reload deve ficar desativado por padrão para execução estável (produção/local final).
    # Use PIXEL_FORGE_DEV_RELOAD=1 apenas em desenvolvimento.
    try:
        uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)
    except KeyboardInterrupt:
        print("\nSistema encerrado pelo usuário.")
    except Exception as e:
        print(f"\nErro ao iniciar o servidor: {e}")
        input("Pressione Enter para sair...")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
