import re
import sys
import os
from pathlib import Path
from typing import Iterator, List, Tuple


VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".ico", ".avif"}
VALID_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv"}


def get_app_base_path() -> Path:
    """
    Returns the base path of the application, compatible with PyInstaller (frozen) 
    and development modes.
    """
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        return Path(sys._MEIPASS)
    else:
        # Running in normal Python environment
        # Assumes this file is in app/utils.py, so parent.parent is root
        return Path(__file__).resolve().parent.parent


def to_windows_long_path(path: Path | str) -> str:
    """
    Converts a path to the Windows extended path format (\\\\?\\) to support long paths.
    Only applies on Windows and if the path is absolute.
    """
    path_str = str(path)
    if sys.platform != "win32":
        return path_str
    
    # Check if already has prefix
    if path_str.startswith("\\\\?\\"):
        return path_str
        
    # Must be absolute for this to work
    p = Path(path_str).resolve()
    abs_path = str(p)
    
    if not abs_path.startswith("\\\\?\\"):
        return f"\\\\?\\{abs_path}"
    return abs_path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize the filename to prevent directory traversal and invalid characters.
    Removes directory separators and keeps only safe characters.
    """
    # Remove path information
    filename = Path(filename).name
    # Remove potentially dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove control characters
    filename = "".join(ch for ch in filename if ord(ch) >= 32)
    return filename.strip()


def normalize_path(path_str: str | Path) -> Path:
    path = Path(path_str).expanduser()
    return path.resolve()


def ensure_directory(path_str: str | Path) -> Path:
    directory = normalize_path(path_str)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def iter_image_files(root_dir: str | Path) -> Iterator[Path]:
    directory = normalize_path(root_dir)
    if not directory.exists() or not directory.is_dir():
        raise ValueError("Diretório de origem inválido")
    for path in directory.rglob("*"):
        if path.is_file() and is_supported_image_extension(path.name):
            yield path


def iter_video_files(root_dir: str | Path) -> Iterator[Path]:
    directory = normalize_path(root_dir)
    if not directory.exists() or not directory.is_dir():
        raise ValueError("Diretório de origem inválido")
    for path in directory.rglob("*"):
        if path.is_file() and is_supported_video_extension(path.name):
            yield path


def is_supported_image_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in VALID_IMAGE_EXTENSIONS

def is_supported_video_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in VALID_VIDEO_EXTENSIONS


def clamp_quality(value: int) -> int:
    if value < 0:
        return 0
    if value > 100:
        return 100
    return value


def compute_new_size(original_width: int, original_height: int, target_width: int | None, target_height: int | None) -> Tuple[int, int]:
    if target_width is None and target_height is None:
        return original_width, original_height
    if target_width is not None and target_height is not None:
        width = max(1, target_width)
        height = max(1, target_height)
        return width, height
    if target_width is not None:
        width = max(1, target_width)
        ratio = width / float(original_width)
        height = max(1, int(original_height * ratio))
        return width, height
    assert target_height is not None
    height = max(1, target_height)
    ratio = height / float(original_height)
    width = max(1, int(original_width * ratio))
    return width, height
