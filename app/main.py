import shutil
import time
from concurrent.futures import CancelledError as ConcurrentCancelledError, Future
from enum import StrEnum
from functools import partial
from pathlib import Path
import logging
import json
import os
import platform
import re
import subprocess
import sys
import threading
from contextlib import asynccontextmanager, suppress

import asyncio
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Literal, Optional, Set

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile, Request, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ConfigDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pixelforge")

from .image_processor import process_directory, process_single_image, get_file_size_str, is_avif_available
from .video_processor import video_processor
from .utils import (
    get_app_base_path,
    is_supported_video_extension,
    is_supported_image_extension,
    iter_video_files,
    sanitize_filename,
)


class SentinelVideoProcessingError(Exception):
    """
    Exception raised when Sentinel video processing fails before any file relocation.

    This error is reserved for failures that happen while the input video is still in
    its original watch-folder location and before any processed/original/error file is
    moved into Sentinel-managed directories. Callers can use it to distinguish early
    processing failures from later file-move failures, where cleanup and retry
    semantics may differ because files might already have been relocated.
    """


class RequestMode(StrEnum):
    UPLOAD = "upload"
    FOLDER = "folder"


class ImageTargetFormat(StrEnum):
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
    BMP = "bmp"
    TIF = "tif"
    TIFF = "tiff"
    ICO = "ico"
    AVIF = "avif"


class VideoTargetFormat(StrEnum):
    MP4 = "mp4"
    MP4_HEVC = "mp4_hevc"
    MKV = "mkv"
    MOV = "mov"
    WEBM = "webm"
    WMV = "wmv"
    FLV = "flv"
    AVI = "avi"

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as exc:
                logger.error("Error sending WS message to %s: %s", client_id, exc)
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        for client_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_json(message)
            except Exception as exc:
                logger.warning("Error broadcasting WS message to %s: %s", client_id, exc)
                self.disconnect(client_id)

manager = ConnectionManager()
# -------------------------

FOLDER_DIALOG_UNAVAILABLE_ERROR = "Seletor indisponível em ambiente sem interface gráfica"
FOLDER_DIALOG_OPEN_ERROR = "Não foi possível abrir o seletor de pasta."

def _open_folder_dialog() -> tuple[str, str]:
    """Open folder picker in a separate process to avoid blocking server workers."""
    if platform.system() == "Linux" and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        msg = FOLDER_DIALOG_UNAVAILABLE_ERROR
        logger.warning(msg)
        return "", msg

    script = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "root = tk.Tk()\n"
        "root.withdraw()\n"
        "root.attributes('-topmost', True)\n"
        "folder = filedialog.askdirectory() or ''\n"
        "print(folder)\n"
        "root.destroy()\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or "subprocess returned non-zero exit status"
            logger.error("Error opening folder dialog subprocess: %s", stderr)
            return "", FOLDER_DIALOG_OPEN_ERROR
        return result.stdout.strip(), ""
    except Exception as exc:
        logger.error("Error opening folder dialog: %s", exc)
        return "", FOLDER_DIALOG_OPEN_ERROR

BASE_DIR = get_app_base_path()
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"
CONFIG_FILE = BASE_DIR / "config.json"
# Session-scoped allowlist roots.
# These paths live only in memory during runtime and are rebuilt on app startup.
ALLOWED_PATH_ROOTS: Set[Path] = set()
ALLOWED_PATHS_LOCK = threading.Lock()
CONFIG_CACHE_LOCK = threading.Lock()
CONFIG_CACHE: Dict[str, Any] = {"mtime_ns": None, "data": None}


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_IMAGE_UPLOAD_FILES = _read_int_env("PIXEL_FORGE_MAX_IMAGE_UPLOAD_FILES", 200)
MAX_VIDEO_UPLOAD_FILES = _read_int_env("PIXEL_FORGE_MAX_VIDEO_UPLOAD_FILES", 100)
MAX_IMAGE_UPLOAD_BYTES = _read_int_env("PIXEL_FORGE_MAX_IMAGE_UPLOAD_BYTES", 50 * 1024 * 1024)
MAX_VIDEO_UPLOAD_BYTES = _read_int_env("PIXEL_FORGE_MAX_VIDEO_UPLOAD_BYTES", 2 * 1024 * 1024 * 1024)
TEMP_FILES_MAX_AGE_SECONDS = _read_int_env("PIXEL_FORGE_TEMP_MAX_AGE_SECONDS", 48 * 3600)
TEMP_FILES_MAX_COUNT = _read_int_env("PIXEL_FORGE_TEMP_MAX_COUNT", 1000)
SENTINEL_RECENT_TTL_SECONDS = _read_int_env("PIXEL_FORGE_SENTINEL_RECENT_TTL_SECONDS", 30)
SENTINEL_FILE_STABILITY_SECONDS = 1
SENTINEL_IDLE_POLL_SECONDS = 5
SENTINEL_ACTIVE_POLL_SECONDS = 2
LOCAL_DEV_PORT_RANGE = range(8000, 8101)
CLIENT_ID_MAX_LENGTH = 64
CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
CLIENT_ID_ERROR_DETAIL = "client_id inválido"


def _build_local_dev_origins() -> List[str]:
    origins: List[str] = []
    for scheme in ("http", "https"):
        for host in ("localhost", "127.0.0.1"):
            for port in LOCAL_DEV_PORT_RANGE:
                origins.append(f"{scheme}://{host}:{port}")
    return origins


LOCAL_DEV_ALLOWED_ORIGINS = _build_local_dev_origins()


def _normalize_client_id_value(client_id: Optional[str]) -> Optional[str]:
    if client_id is None:
        return None

    normalized = client_id.strip()
    if not normalized:
        return None
    if len(normalized) > CLIENT_ID_MAX_LENGTH:
        raise ValueError("client_id too long")
    if not CLIENT_ID_PATTERN.fullmatch(normalized):
        raise ValueError("client_id contains unsupported characters")
    return normalized


def _validate_optional_client_id(client_id: Optional[str]) -> Optional[str]:
    try:
        return _normalize_client_id_value(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=CLIENT_ID_ERROR_DETAIL) from exc


def _normalize_path_string(path_value: str | Path) -> Path:
    raw = str(path_value).strip()
    if not raw:
        raise ValueError("Caminho vazio")
    if "\x00" in raw:
        raise ValueError("Caminho inválido")

    expanded = os.path.expanduser(raw)
    if not os.path.isabs(expanded):
        expanded = os.path.join(str(BASE_DIR), expanded)
    normalized = os.path.realpath(os.path.abspath(expanded))
    return Path(normalized)


def _validate_directory_input(
    path_value: str | Path,
    *,
    field_name: str,
    must_exist: bool,
) -> Path:
    try:
        candidate = _normalize_path_string(path_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} inválido") from exc

    if must_exist:
        # codeql[py/path-injection]
        if not candidate.exists() or not candidate.is_dir():
            raise HTTPException(status_code=400, detail=f"{field_name} inválido")
    else:
        current = candidate
        # codeql[py/path-injection]
        while not current.exists():
            parent = current.parent
            if parent == current:
                raise HTTPException(status_code=400, detail=f"{field_name} inválido")
            current = parent
        # codeql[py/path-injection]
        if not current.is_dir():
            raise HTTPException(status_code=400, detail=f"{field_name} inválido")
    return candidate


def _register_allowed_root(path: Path) -> None:
    """Register a root directory that endpoints can safely access."""
    candidate = path
    # codeql[py/path-injection]
    if candidate.exists() and candidate.is_file():
        root = candidate.parent
    else:
        # Treat missing paths as intended directory roots, not as parent fallback.
        root = candidate
    with ALLOWED_PATHS_LOCK:
        ALLOWED_PATH_ROOTS.add(root)


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_allowed_path(path: Path) -> bool:
    resolved = os.path.realpath(os.path.abspath(str(path)))
    with ALLOWED_PATHS_LOCK:
        roots = [os.path.realpath(os.path.abspath(str(root))) for root in ALLOWED_PATH_ROOTS]

    for root in roots:
        try:
            if os.path.commonpath([resolved, root]) == root:
                return True
        except ValueError:
            continue
    return False


def _validate_allowed_media_file(path_value: str) -> Path:
    try:
        candidate = _normalize_path_string(path_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Caminho inválido") from exc

    if not _is_allowed_path(candidate):
        raise HTTPException(status_code=403, detail="Acesso negado para este caminho")
    # codeql[py/path-injection]
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if not (is_supported_image_extension(candidate.name) or is_supported_video_extension(candidate.name)):
        raise HTTPException(status_code=400, detail="Apenas arquivos de mídia podem ser visualizados")
    return candidate


def _validate_allowed_existing_path(path_value: str) -> Path:
    try:
        candidate = _normalize_path_string(path_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Caminho inválido") from exc

    if not _is_allowed_path(candidate):
        raise HTTPException(status_code=403, detail="Acesso negado para este caminho")
    # codeql[py/path-injection]
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return candidate


def _initialize_allowed_roots() -> None:
    _register_allowed_root(BASE_DIR / "output")
    _register_allowed_root(STATIC_DIR / "temp_compare")
    _register_allowed_root(BASE_DIR / "temp_uploads")


def _cleanup_temp_directory(directory: Path, max_age_seconds: int, max_files: int) -> None:
    if not directory.exists():
        return
    now = time.time()
    files: List[Path] = []
    for item in directory.iterdir():
        if not item.is_file():
            continue
        files.append(item)
        try:
            if now - item.stat().st_mtime > max_age_seconds:
                item.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Falha ao limpar arquivo temporário %s: %s", item, exc)

    files = [f for f in files if f.exists()]
    if len(files) <= max_files:
        return

    def _safe_mtime(file_path: Path) -> float:
        try:
            return file_path.stat().st_mtime
        except Exception:
            return 0.0

    files.sort(key=_safe_mtime, reverse=True)
    for stale in files[max_files:]:
        try:
            stale.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Falha ao remover excesso de temporários %s: %s", stale, exc)


def _get_config_mtime_ns() -> Optional[int]:
    if not CONFIG_FILE.exists():
        return None
    try:
        return CONFIG_FILE.stat().st_mtime_ns
    except OSError:
        return None


def _read_config_from_disk() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        return default_config()
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        config = default_config()
        config.update({k: raw.get(k, v) for k, v in config.items()})
        return config
    except Exception:
        return default_config()

# --- Sentinel Background Task ---
sentinel_task: Optional[asyncio.Task] = None
# Sentinel state is currently accessed by a single coroutine task (sentinel_loop).
# If Sentinel processing becomes parallel in the future, guard these structures with an async lock.
SENTINEL_IN_PROGRESS: Set[Path] = set()
SENTINEL_RECENTLY_HANDLED: Dict[Path, float] = {}


def _prune_sentinel_recent_cache(now_ts: float) -> None:
    stale = [
        path for path, timestamp in SENTINEL_RECENTLY_HANDLED.items()
        if now_ts - timestamp > SENTINEL_RECENT_TTL_SECONDS
    ]
    for path in stale:
        SENTINEL_RECENTLY_HANDLED.pop(path, None)


def _build_unique_destination(directory: Path, filename: str) -> Path:
    target = directory / filename
    if not target.exists():
        return target
    stamp = int(time.time() * 1000)
    stem = Path(filename).stem or "arquivo"
    suffix = Path(filename).suffix
    return directory / f"{stem}_{stamp}{suffix}"


def _get_sentinel_file_type(file_path: Path) -> Optional[str]:
    if not file_path.is_file():
        return None
    if file_path.name.startswith(".") or file_path.name.startswith("~"):
        return None
    if is_supported_image_extension(file_path.name):
        return "images"
    if is_supported_video_extension(file_path.name):
        return "videos"
    return None


def _should_skip_sentinel_file(file_key: Path, now_ts: float) -> bool:
    if file_key in SENTINEL_IN_PROGRESS:
        return True
    last_handled = SENTINEL_RECENTLY_HANDLED.get(file_key)
    return bool(last_handled and (now_ts - last_handled) < SENTINEL_RECENT_TTL_SECONDS)


async def _check_file_stability(file_path: Path, stable_seconds: int) -> bool:
    """Check whether a file is stable enough to process."""
    try:
        initial_size = file_path.stat().st_size
        await asyncio.sleep(stable_seconds)
        if not file_path.exists():
            return False
        final_size = file_path.stat().st_size
        return initial_size == final_size
    except Exception:
        return False


def _prepare_sentinel_directories(config: Dict[str, Any], watch_dir: Path) -> Dict[str, Path]:
    output_dir = _validate_directory_input(
        config.get("output_dir") or str(watch_dir / "output"),
        field_name="Pasta de saída",
        must_exist=False,
    )
    sentinel_root = output_dir / "sentinel-mode"
    directories = {
        "output": output_dir,
        "root": sentinel_root,
        "originals": sentinel_root / "originals",
        "processed": sentinel_root / "processed",
        "errors": sentinel_root / "errors",
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    _register_allowed_root(output_dir)
    _register_allowed_root(sentinel_root)
    return directories


async def _process_sentinel_media(
    file_path: Path,
    *,
    file_type: str,
    config: Dict[str, Any],
    processed_dir: Path,
) -> Optional[Path]:
    if file_type == "images":
        return await asyncio.to_thread(
            process_single_image,
            file_path,
            str(processed_dir),
            config.get("target_format", "webp"),
            config.get("quality", 80),
            config.get("width"),
            config.get("height"),
            True,
        )

    target_fmt = config.get("target_format", "mp4")
    success, msg, out_path = await video_processor.process_video(
        file_path,
        processed_dir,
        target_fmt,
        config.get("quality", 80),
        config.get("width"),
        config.get("height"),
        False,
    )
    if not success:
        raise SentinelVideoProcessingError(msg)
    return Path(out_path) if out_path else None


async def _handle_sentinel_error(
    file_path: Path,
    error: Exception,
    *,
    errors_dir: Path,
    file_type: str,
) -> None:
    logger.error("Sentinel error processing %s: %s", file_path, error)
    try:
        dest_error = _build_unique_destination(errors_dir, file_path.name)
        shutil.move(str(file_path), str(dest_error))
    except Exception as move_exc:
        logger.warning("Falha ao mover arquivo do sentinel para erros %s: %s", file_path, move_exc)

    await manager.broadcast({
        "type": "sentinel_error",
        "file": file_path.name,
        "error": str(error),
        "file_type": file_type,
    })


async def _process_sentinel_file(
    file_path: Path,
    *,
    file_key: Path,
    file_type: str,
    config: Dict[str, Any],
    watch_dir: Path,
) -> None:
    directories = _prepare_sentinel_directories(config, watch_dir)

    await manager.broadcast({
        "type": "sentinel_start",
        "file": file_path.name,
        "file_type": file_type,
    })

    SENTINEL_IN_PROGRESS.add(file_key)
    try:
        processed_path = await _process_sentinel_media(
            file_path,
            file_type=file_type,
            config=config,
            processed_dir=directories["processed"],
        )
        dest_original = _build_unique_destination(directories["originals"], file_path.name)
        shutil.move(str(file_path), str(dest_original))

        await manager.broadcast({
            "type": "sentinel_complete",
            "original": str(dest_original),
            "processed": str(processed_path) if processed_path else "",
            "original_size": get_file_size_str(dest_original),
            "processed_size": get_file_size_str(processed_path) if processed_path else "-",
            "file_type": file_type,
        })
    except Exception as exc:
        await _handle_sentinel_error(
            file_path,
            exc,
            errors_dir=directories["errors"],
            file_type=file_type,
        )
    finally:
        SENTINEL_RECENTLY_HANDLED[file_key] = time.time()
        SENTINEL_IN_PROGRESS.discard(file_key)


def _log_future_exception(future: Future[Any], *, context: str) -> None:
    try:
        exc = future.exception()
    except ConcurrentCancelledError:
        return
    except Exception as callback_exc:
        logger.warning("Falha ao inspecionar tarefa em background (%s): %s", context, callback_exc)
        return

    if exc is not None:
        logger.error(context, exc_info=(type(exc), exc, exc.__traceback__))


def _schedule_background_coroutine(
    coro: Coroutine[Any, Any, Any],
    loop: asyncio.AbstractEventLoop,
    *,
    context: str,
) -> Future[Any]:
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.add_done_callback(partial(_log_future_exception, context=context))
    return future

async def sentinel_loop():
    logger.info("Sentinel loop started.")
    while True:
        try:
            config = load_config()
            
            # Check if enabled and configured
            if not config.get("sentinel_enabled") or not config.get("watch_folder"):
                await asyncio.sleep(SENTINEL_IDLE_POLL_SECONDS)
                continue

            watch_dir = _validate_directory_input(
                config["watch_folder"],
                field_name="Pasta monitorada",
                must_exist=True,
            )
            if not watch_dir.exists() or not watch_dir.is_dir():
                await asyncio.sleep(SENTINEL_IDLE_POLL_SECONDS)
                continue

            now_ts = time.time()
            _prune_sentinel_recent_cache(now_ts)

            for file_path in watch_dir.iterdir():
                file_type = _get_sentinel_file_type(file_path)
                if not file_type:
                    continue

                file_key = file_path.resolve()
                if _should_skip_sentinel_file(file_key, now_ts):
                    continue
                if not await _check_file_stability(file_path, SENTINEL_FILE_STABILITY_SECONDS):
                    continue

                logger.info("Sentinel detected: %s", file_path)
                await _process_sentinel_file(
                    file_path,
                    file_key=file_key,
                    file_type=file_type,
                    config=config,
                    watch_dir=watch_dir,
                )

            await asyncio.sleep(SENTINEL_ACTIVE_POLL_SECONDS)

        except Exception as exc:
            logger.exception("Sentinel loop error")
            await asyncio.sleep(SENTINEL_IDLE_POLL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global sentinel_task
    _initialize_allowed_roots()
    (STATIC_DIR / "temp_compare").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "temp_uploads").mkdir(parents=True, exist_ok=True)
    await asyncio.gather(
        asyncio.to_thread(
            _cleanup_temp_directory,
            STATIC_DIR / "temp_compare",
            TEMP_FILES_MAX_AGE_SECONDS,
            TEMP_FILES_MAX_COUNT,
        ),
        asyncio.to_thread(
            _cleanup_temp_directory,
            BASE_DIR / "temp_uploads",
            TEMP_FILES_MAX_AGE_SECONDS,
            TEMP_FILES_MAX_COUNT,
        ),
    )
    config = load_config()
    if config.get("output_dir"):
        try:
            _register_allowed_root(
                _validate_directory_input(
                    config["output_dir"],
                    field_name="Pasta de saída",
                    must_exist=False,
                )
            )
        except HTTPException as exc:
            logger.warning("Configuração ignorada para output_dir inválido: %s", exc.detail)
    if _read_bool_env("PIXEL_FORGE_DISABLE_SENTINEL", False):
        logger.info("Sentinel loop desativado por variável de ambiente.")
        sentinel_task = None
    else:
        sentinel_task = asyncio.create_task(sentinel_loop())

    try:
        yield
    finally:
        if sentinel_task:
            sentinel_task.cancel()
            with suppress(asyncio.CancelledError):
                _ = await sentinel_task


app = FastAPI(title="Pixel Forge", version="0.1.0", lifespan=lifespan)

# Serve static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

images_dir = STATIC_DIR / "images"
if not images_dir.exists():
    images_dir.mkdir(parents=True, exist_ok=True)

app.mount("/images", StaticFiles(directory=images_dir), name="images")

# Security: Trusted Host Middleware to prevent Host Header attacks
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "::1"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_DEV_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    return response


class ConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Optional[Literal["upload", "folder"]] = None
    output_dir: Optional[str] = None
    source_dir: Optional[str] = None
    target_format: Optional[str] = None
    quality: Optional[int] = Field(default=None, ge=0, le=100)
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    sentinel_enabled: Optional[bool] = None
    watch_folder: Optional[str] = None

def default_config() -> Dict[str, Any]:
    return {
        "mode": "upload",
        "output_dir": "",
        "source_dir": "",
        "target_format": "webp",
        "quality": 80,
        "width": None,
        "height": None,
        "sentinel_enabled": False,
        "watch_folder": "",
    }


def load_config() -> Dict[str, Any]:
    mtime_ns = _get_config_mtime_ns()
    with CONFIG_CACHE_LOCK:
        cached_data = CONFIG_CACHE["data"]
        if cached_data is not None and CONFIG_CACHE["mtime_ns"] == mtime_ns:
            return dict(cached_data)

    config = _read_config_from_disk()
    with CONFIG_CACHE_LOCK:
        CONFIG_CACHE["data"] = dict(config)
        CONFIG_CACHE["mtime_ns"] = mtime_ns
    return dict(config)


def save_config(data: Dict[str, Any]) -> None:
    config = load_config()
    allowed_keys = default_config().keys()
    for key in allowed_keys:
        if key in data:
            config[key] = data[key]
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    with CONFIG_CACHE_LOCK:
        CONFIG_CACHE["data"] = dict(config)
        CONFIG_CACHE["mtime_ns"] = _get_config_mtime_ns()


@app.get("/")
def read_root() -> FileResponse:
    if not INDEX_FILE.exists():
        return FileResponse(STATIC_DIR / "fallback.html") if (STATIC_DIR / "fallback.html").exists() else JSONResponse({"error": "Index not found"}, status_code=500)
    return FileResponse(INDEX_FILE)


@app.get("/config")
def get_config() -> Dict[str, Any]:
    return load_config()


@app.post("/config")
def update_config(config: ConfigUpdateRequest) -> Dict[str, str]:
    try:
        payload = config.model_dump(exclude_none=True)
        for key in ("output_dir", "source_dir", "watch_folder"):
            if key in payload and payload[key]:
                must_exist = key != "output_dir"
                validated = _validate_directory_input(
                    payload[key],
                    field_name=key,
                    must_exist=must_exist,
                )
                payload[key] = str(validated)
                _register_allowed_root(validated)
        save_config(payload)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erro ao atualizar configuração")
        raise HTTPException(status_code=500, detail="Erro interno ao atualizar configuração")


@app.post("/select-folder")
def select_folder_dialog() -> Dict[str, str]:
    """Opens a native folder selection dialog on the server machine."""
    folder, error = _open_folder_dialog()
    if folder:
        try:
            validated = _validate_directory_input(folder, field_name="Pasta selecionada", must_exist=True)
        except HTTPException as exc:
            logger.warning("Seletor retornou pasta inválida: %s", exc.detail)
            return {"path": "", "error": "Pasta selecionada inválida"}
        _register_allowed_root(validated)
        return {"path": str(validated)}
    if error:
        public_error = (
            FOLDER_DIALOG_OPEN_ERROR
            if error == FOLDER_DIALOG_OPEN_ERROR
            else FOLDER_DIALOG_UNAVAILABLE_ERROR
        )
        return {"path": "", "error": public_error}
    return {"path": ""}



@app.get("/system-check")
def system_check() -> Dict[str, bool]:
    return {
        "ffmpeg": video_processor.check_ffmpeg(),
        "avif": is_avif_available(),
    }


@app.get("/preview")
def preview_file(path: str):
    """Serves a local file for preview/comparison."""
    file_path = _validate_allowed_media_file(path)
    # codeql[py/path-injection]
    return FileResponse(file_path)


@app.post("/open-location")
def open_file_location(path: str = Body(..., embed=True)):
    """Opens the file location in the OS file explorer."""
    logger.info("Opening location for: %s", path)
    p = _validate_allowed_existing_path(path)
    
    try:
        if platform.system() == "Windows":
            # codeql[py/path-injection]
            if p.is_file():
                subprocess.Popen(["explorer", f"/select,{str(p)}"])
            else:
                subprocess.Popen(["explorer", str(p)])
        elif platform.system() == "Darwin":
            # codeql[py/path-injection]
            if p.is_file():
                subprocess.Popen(["open", "-R", str(p)])
            else:
                subprocess.Popen(["open", str(p)])
        else:
            # codeql[py/path-injection]
            folder = p.parent if p.is_file() else p
            subprocess.Popen(["xdg-open", str(folder)])
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Error opening location for %s: %s", p, exc)
        raise HTTPException(status_code=500, detail="Erro interno ao abrir localização")

class ProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: RequestMode = RequestMode.UPLOAD
    source_dir: Optional[str] = None
    output_dir: str
    target_format: ImageTargetFormat
    quality: int = Field(ge=0, le=100)
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    strip_metadata: bool = True

class VideoProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: RequestMode = RequestMode.UPLOAD
    source_dir: Optional[str] = None
    output_dir: str
    target_format: VideoTargetFormat
    quality: int = Field(ge=0, le=100)
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    remove_audio: bool = False


def _resolve_image_request(
    *,
    mode: RequestMode,
    output_dir: str,
    target_format: ImageTargetFormat,
    quality: int,
    width: Optional[int],
    height: Optional[int],
    strip_metadata: bool,
) -> Dict[str, Any]:
    output_path = _validate_directory_input(output_dir, field_name="Pasta de destino", must_exist=False)
    _register_allowed_root(output_path)

    return {
        "mode": mode.value,
        "output_path": output_path,
        "target_format": target_format.value,
        "quality": quality,
        "width": width,
        "height": height,
        "strip_metadata": strip_metadata,
    }


def _build_image_progress_callbacks(
    loop: asyncio.AbstractEventLoop,
    client_id: Optional[str],
) -> tuple[Callable[[str, int], Awaitable[None]], Callable[[str, int], None]]:
    async def report_progress_async(filename: str, percent: int) -> None:
        if client_id:
            await manager.send_personal_message({
                "type": "progress",
                "category": "images",
                "file": filename,
                "percent": percent,
            }, client_id)

    def report_progress_sync(filename: str, percent: int) -> None:
        _schedule_background_coroutine(
            report_progress_async(filename, percent),
            loop,
            context=f"Erro ao reportar progresso de imagem para {filename}",
        )

    return report_progress_async, report_progress_sync


async def _process_folder_images(
    *,
    source_dir: str,
    output_path: Path,
    target_format: str,
    quality: int,
    width: Optional[int],
    height: Optional[int],
    strip_metadata: bool,
    report_progress_sync: Callable[[str, int], None],
) -> Dict[str, Any]:
    src = _validate_directory_input(
        source_dir,
        field_name="Pasta de origem",
        must_exist=True,
    )
    count, errors, duration, results = await asyncio.to_thread(
        process_directory,
        str(src),
        str(output_path),
        target_format,
        quality,
        width,
        height,
        strip_metadata,
        report_progress_sync,
    )
    return {
        "status": "success",
        "processed_count": count,
        "errors": errors,
        "duration_ms": duration,
        "results": results,
    }


async def _process_uploaded_images(
    *,
    output_path: Path,
    target_format: str,
    quality: int,
    width: Optional[int],
    height: Optional[int],
    strip_metadata: bool,
    files: List[UploadFile],
    report_progress_async: Callable[[str, int], Awaitable[None]],
) -> Dict[str, Any]:
    if len(files) > MAX_IMAGE_UPLOAD_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Quantidade de arquivos excede o limite de {MAX_IMAGE_UPLOAD_FILES}",
        )

    temp_compare_dir = STATIC_DIR / "temp_compare"
    temp_compare_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_temp_directory(temp_compare_dir, TEMP_FILES_MAX_AGE_SECONDS, TEMP_FILES_MAX_COUNT)

    start = time.perf_counter()
    errors: List[str] = []
    results: List[Dict[str, str]] = []
    processed_count = 0
    total_files = len(files)

    for index, upload in enumerate(files):
        original_name = upload.filename or f"upload_{index + 1}"
        safe_name = sanitize_filename(original_name) or f"upload_{index + 1}"
        safe_suffix = Path(safe_name).suffix.lower()
        original_path: Optional[Path] = None

        try:
            if not is_supported_image_extension(safe_name):
                errors.append(f"Arquivo {original_name}: extensão não suportada")
                continue

            timestamp = int(time.time() * 1000)
            stem = Path(safe_name).stem or f"upload_{index + 1}"
            original_filename = f"upload_{stem}_{timestamp}{safe_suffix}"
            original_path = temp_compare_dir / original_filename

            bytes_written = 0
            file_too_large = False
            with open(original_path, "wb") as buffer:
                while True:
                    chunk = await upload.read(UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > MAX_IMAGE_UPLOAD_BYTES:
                        file_too_large = True
                        break
                    buffer.write(chunk)

            if file_too_large:
                errors.append(
                    f"Arquivo {original_name}: tamanho excede o limite de {MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)} MB"
                )
                try:
                    original_path.unlink(missing_ok=True)
                except Exception as exc:
                    logger.warning("Falha ao remover upload de imagem excedido %s: %s", original_path, exc)
                continue

            processed_path = await asyncio.to_thread(
                process_single_image,
                original_path,
                str(output_path),
                target_format,
                quality,
                width,
                height,
                strip_metadata,
            )
            results.append({
                "file": original_name,
                "success": True,
                "original": str(original_path),
                "processed": str(processed_path),
                "original_size": get_file_size_str(original_path),
                "processed_size": get_file_size_str(processed_path),
            })
            processed_count += 1
        except Exception as exc:
            errors.append(f"Arquivo {original_name}: {exc}")
            logger.error("Erro ao processar upload de imagem %s: %s", original_name, exc)
            if original_path and original_path.exists():
                try:
                    original_path.unlink(missing_ok=True)
                except Exception as cleanup_exc:
                    logger.warning("Falha ao limpar upload de imagem %s: %s", original_path, cleanup_exc)
        finally:
            try:
                await upload.close()
            except Exception as exc:
                logger.debug("Falha ao fechar upload de imagem %s: %s", original_name, exc)
            percent = int(((index + 1) / total_files) * 100) if total_files > 0 else 100
            await report_progress_async(original_name, percent)

    return {
        "status": "success",
        "processed_count": processed_count,
        "errors": errors,
        "duration_ms": int((time.perf_counter() - start) * 1000),
        "results": results,
    }

@app.post("/process")
async def process_images(
    mode: RequestMode = Form(...),
    source_dir: Optional[str] = Form(None),
    output_dir: str = Form(...),
    target_format: ImageTargetFormat = Form(...),
    quality: int = Form(...),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    strip_metadata: bool = Form(True),
    client_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(None),
):
    resolved = _resolve_image_request(
        mode=mode,
        output_dir=output_dir,
        target_format=target_format,
        quality=quality,
        width=width,
        height=height,
        strip_metadata=strip_metadata,
    )
    safe_client_id = _validate_optional_client_id(client_id)
    loop = asyncio.get_running_loop()
    report_progress_async, report_progress_sync = _build_image_progress_callbacks(loop, safe_client_id)

    try:
        if resolved["mode"] == "folder":
            if not source_dir:
                raise HTTPException(status_code=400, detail="Pasta de origem obrigatória no modo pasta")
            return await _process_folder_images(
                source_dir=source_dir,
                output_path=resolved["output_path"],
                target_format=resolved["target_format"],
                quality=resolved["quality"],
                width=resolved["width"],
                height=resolved["height"],
                strip_metadata=resolved["strip_metadata"],
                report_progress_sync=report_progress_sync,
            )

        if resolved["mode"] == "upload":
            if not files:
                raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")
            return await _process_uploaded_images(
                output_path=resolved["output_path"],
                target_format=resolved["target_format"],
                quality=resolved["quality"],
                width=resolved["width"],
                height=resolved["height"],
                strip_metadata=resolved["strip_metadata"],
                files=files,
                report_progress_async=report_progress_async,
            )

        raise HTTPException(status_code=400, detail="Modo inválido")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in process_images")
        raise HTTPException(status_code=500, detail="Erro interno ao processar imagens")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    try:
        safe_client_id = _normalize_client_id_value(client_id)
    except ValueError:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=CLIENT_ID_ERROR_DETAIL,
        )
        return

    if safe_client_id is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=CLIENT_ID_ERROR_DETAIL,
        )
        return

    await manager.connect(websocket, safe_client_id)
    try:
        while True:
            await websocket.receive_text() # Keep connection open
    except WebSocketDisconnect:
        manager.disconnect(safe_client_id)

@app.post("/process-video")
async def process_videos(
    mode: RequestMode = Form(...),
    source_dir: Optional[str] = Form(None),
    output_dir: str = Form(...),
    target_format: VideoTargetFormat = Form(...),
    quality: int = Form(...),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    remove_audio: bool = Form(False),
    strip_metadata: bool = Form(False),
    client_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(None),
):
    try:
        request_data = VideoProcessRequest(
            mode=mode,
            source_dir=source_dir,
            output_dir=output_dir,
            target_format=target_format,
            quality=quality,
            width=width,
            height=height,
            remove_audio=remove_audio,
        )
        safe_client_id = _validate_optional_client_id(client_id)
        results = []
        output_dir_path = _validate_directory_input(
            request_data.output_dir,
            field_name="Pasta de destino",
            must_exist=False,
        )
        _register_allowed_root(output_dir_path)
        
        # Define progress callback
        async def report_progress(filename: str, percent: int):
            if safe_client_id:
                await manager.send_personal_message({
                    "type": "progress",
                    "category": "videos",
                    "file": filename,
                    "percent": percent
                }, safe_client_id)

        if request_data.mode == RequestMode.FOLDER:
            if not request_data.source_dir:
                 raise HTTPException(status_code=400, detail="Pasta de origem obrigatória")
            source_dir_path = _validate_directory_input(
                request_data.source_dir,
                field_name="Pasta de origem",
                must_exist=True,
            )
            
            # Iterate video files in folder
            video_paths = list(iter_video_files(source_dir_path))
            total_videos = len(video_paths)

            for i, v_path in enumerate(video_paths, start=1):
                # Report start
                if safe_client_id:
                     await manager.send_personal_message({
                        "type": "status",
                        "category": "videos",
                        "message": f"Processando {v_path.name} ({i}/{total_videos})..."
                    }, safe_client_id)

                async def file_progress(p, _name=v_path.name):
                    await report_progress(_name, p)

                success, msg, out_path = await video_processor.process_video(
                    v_path,
                    output_dir_path,
                    request_data.target_format.value,
                    request_data.quality,
                    request_data.width,
                    request_data.height,
                    request_data.remove_audio,
                    strip_metadata=strip_metadata,
                    progress_callback=file_progress
                )
                results.append({
                    "file": v_path.name,
                    "success": success,
                    "message": msg,
                    "original": str(v_path),
                    "processed": out_path if out_path else None,
                    "original_size": get_file_size_str(v_path),
                    "processed_size": get_file_size_str(Path(out_path)) if out_path else "-"
                })
                
        elif request_data.mode == RequestMode.UPLOAD:
            if not files:
                raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")
            if len(files) > MAX_VIDEO_UPLOAD_FILES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Quantidade de arquivos excede o limite de {MAX_VIDEO_UPLOAD_FILES}",
                )
                
            # For videos, stream uploads to disk first to avoid memory pressure.
            temp_dir = BASE_DIR / "temp_uploads"
            temp_dir.mkdir(exist_ok=True)
            _cleanup_temp_directory(temp_dir, TEMP_FILES_MAX_AGE_SECONDS, TEMP_FILES_MAX_COUNT)
            
            for i, file in enumerate(files):
                if safe_client_id:
                     await manager.send_personal_message({
                        "type": "status",
                        "category": "videos",
                        "message": f"Processando upload {file.filename} ({i+1}/{len(files)})..."
                    }, safe_client_id)

                # Sanitize filename
                original_name = file.filename or f"video_{i+1}"
                safe_name = sanitize_filename(original_name) or f"video_{i+1}"
                temp_name = f"{Path(safe_name).stem}_{int(time.time() * 1000)}_{i}{Path(safe_name).suffix}"
                temp_path = temp_dir / temp_name
                
                try:
                    bytes_written = 0
                    file_too_large = False
                    with open(temp_path, "wb") as buffer:
                        # Stream copy
                        while content := await file.read(UPLOAD_CHUNK_SIZE):
                            bytes_written += len(content)
                            if bytes_written > MAX_VIDEO_UPLOAD_BYTES:
                                file_too_large = True
                                break
                            buffer.write(content)

                    if file_too_large:
                        results.append({
                            "file": original_name,
                            "success": False,
                            "message": f"Tamanho excede o limite de {MAX_VIDEO_UPLOAD_BYTES // (1024 * 1024)} MB",
                            "original": str(temp_path),
                            "processed": None,
                            "original_size": "-",
                            "processed_size": "-"
                        })
                        try:
                            temp_path.unlink(missing_ok=True)
                        except Exception as exc:
                            logger.warning("Falha ao remover upload de vídeo excedido %s: %s", temp_path, exc)
                        continue
                            
                    # Process
                    async def file_progress(p, _name=original_name):
                        await report_progress(_name, p)

                    success, msg, out_path = await video_processor.process_video(
                        temp_path,
                        output_dir_path,
                        request_data.target_format.value,
                        request_data.quality,
                        request_data.width,
                        request_data.height,
                        request_data.remove_audio,
                        strip_metadata=strip_metadata,
                        progress_callback=file_progress
                    )
                    results.append({
                        "file": original_name,
                        "success": success,
                        "message": msg,
                        "original": str(temp_path),
                        "processed": out_path if out_path else None,
                        "original_size": get_file_size_str(temp_path),
                        "processed_size": get_file_size_str(Path(out_path)) if out_path else "-"
                    })
                    
                finally:
                    # Cleanup temp file
                    if temp_path.exists():
                        try:
                            temp_path.unlink(missing_ok=True)
                        except Exception as exc:
                            logger.warning("Falha ao limpar upload temporário de vídeo %s: %s", temp_path, exc)
                    try:
                        await file.close()
                    except Exception as exc:
                        logger.debug("Falha ao fechar upload de vídeo %s: %s", original_name, exc)
        return {"status": "success", "processed_count": len(results), "results": results}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in process_videos")
        raise HTTPException(status_code=500, detail="Erro interno ao processar vídeos")
