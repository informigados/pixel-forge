import importlib
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image

try:
    importlib.import_module("pillow_avif")
    AVIF_PLUGIN_AVAILABLE = True
except Exception:
    AVIF_PLUGIN_AVAILABLE = False

from .utils import (
    clamp_quality,
    compute_new_size,
    ensure_directory,
    is_supported_image_extension,
    iter_image_files,
)


logger = logging.getLogger("pixelforge")

try:
    PIL_RESAMPLING = Image.Resampling
except AttributeError:  # Pillow < 9.1
    class _PILResampling:
        LANCZOS = Image.LANCZOS
        BICUBIC = Image.BICUBIC

    PIL_RESAMPLING = _PILResampling


ALPHA_SUPPORTED_FORMATS = {"PNG", "WEBP", "AVIF", "TIFF", "ICO"}
SUPPORTED_TARGET_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF", "ICO", "AVIF"}


class ImageProcessingError(Exception):
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


def _normalize_target_format(target_format: str) -> str:
    fmt = target_format.upper()
    if fmt == "JPG":
        return "JPEG"
    if fmt == "TIF":
        return "TIFF"
    return fmt


def _ensure_target_format_supported(target_format_upper: str) -> None:
    if target_format_upper not in SUPPORTED_TARGET_FORMATS:
        raise ImageProcessingError(
            f"Formato de saída não suportado: {target_format_upper.lower()}"
        )
    if target_format_upper == "AVIF" and not AVIF_PLUGIN_AVAILABLE:
        raise ImageProcessingError(
            "Formato AVIF indisponível: plugin pillow-avif-plugin não encontrado"
        )


def is_avif_available() -> bool:
    return AVIF_PLUGIN_AVAILABLE


def _image_has_alpha(img: Image.Image) -> bool:
    if "A" in img.getbands():
        return True
    if img.mode == "P":
        return "transparency" in img.info
    return False


def _flatten_rgba_on_white(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _prepare_image_for_target(img: Image.Image, target_format_upper: str) -> Image.Image:
    has_alpha = _image_has_alpha(img)
    supports_alpha = target_format_upper in ALPHA_SUPPORTED_FORMATS

    if has_alpha and not supports_alpha:
        return _flatten_rgba_on_white(img)

    if supports_alpha:
        if has_alpha and img.mode != "RGBA":
            return img.convert("RGBA")
        if not has_alpha and img.mode not in {"RGB", "L"}:
            return img.convert("RGB")
        return img

    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _select_resize_filter(
    original_size: Tuple[int, int],
    new_size: Tuple[int, int],
):
    ow, oh = original_size
    nw, nh = new_size
    if nw < ow or nh < oh:
        return PIL_RESAMPLING.LANCZOS
    return PIL_RESAMPLING.BICUBIC


def process_single_image(
    source_path: Path,
    output_dir: str,
    target_format: str,
    quality: int,
    width: Optional[int],
    height: Optional[int],
    strip_metadata: bool = True,
) -> Path:
    if not source_path.exists() or not source_path.is_file():
        raise ImageProcessingError("Arquivo de origem inexistente", str(source_path))
    if not is_supported_image_extension(source_path.name):
        raise ImageProcessingError("Extensão de arquivo não suportada", str(source_path))

    output_directory = ensure_directory(output_dir)
    target_format_upper = _normalize_target_format(target_format)
    _ensure_target_format_supported(target_format_upper)
    quality_value = clamp_quality(quality)

    with Image.open(source_path) as img:
        # Preserve EXIF if requested and available
        exif_data = None
        if not strip_metadata:
            exif_data = img.info.get("exif")

        img = _prepare_image_for_target(img, target_format_upper)
        new_width, new_height = compute_new_size(img.width, img.height, width, height)
        if (new_width, new_height) != (img.width, img.height):
            resize_filter = _select_resize_filter((img.width, img.height), (new_width, new_height))
            img = img.resize((new_width, new_height), resample=resize_filter)

        output_filename = source_path.stem + "." + target_format.lower()
        output_path = output_directory / output_filename

        save_kwargs = {"format": target_format_upper}
        
        # Formats that support quality
        if target_format_upper in ["JPEG", "WEBP", "AVIF"]:
            save_kwargs["quality"] = quality_value
            
        # Formats that support optimization
        if target_format_upper in ["JPEG", "PNG", "WEBP", "AVIF"]:
            save_kwargs["optimize"] = True

        # Pass EXIF if preserved
        if exif_data and target_format_upper in ["JPEG", "WEBP", "AVIF"]:
            save_kwargs["exif"] = exif_data

        img.save(output_path, **save_kwargs)
        return output_path


def get_file_size_str(path: Path) -> str:
    """Returns human readable file size."""
    try:
        size_bytes = path.stat().st_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    except Exception:
        return "-"


def process_directory(
    source_dir: str,
    output_dir: str,
    target_format: str,
    quality: int,
    width: Optional[int],
    height: Optional[int],
    strip_metadata: bool = True,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Tuple[int, List[str], int, List[Dict[str, str]]]:
    start = time.perf_counter()
    image_paths = list(iter_image_files(source_dir))
    total_files = len(image_paths)
    
    errors: List[str] = []
    results: List[Dict[str, str]] = []
    processed_count = 0

    if total_files == 0:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return 0, errors, duration_ms, results

    for i, path in enumerate(image_paths):
        if progress_callback:
            # Report progress
            try:
                percent = int(((i) / total_files) * 100)
                progress_callback(path.name, percent)
            except Exception as exc:
                logger.debug("Falha ao reportar progresso da imagem %s: %s", path.name, exc)

        try:
            output_path = process_single_image(path, output_dir, target_format, quality, width, height, strip_metadata)
            results.append({
                "file": path.name,
                "success": True,
                "original": str(path),
                "processed": str(output_path),
                "original_size": get_file_size_str(path),
                "processed_size": get_file_size_str(output_path)
            })
            processed_count += 1
        except ImageProcessingError as exc:
            message = f"{path}: {exc}"
            errors.append(message)
            logger.warning(message)
        except Exception as exc:
            message = f"{path}: {exc}"
            errors.append(message)
            logger.error(message)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info("Processamento em lote concluído: %s arquivos em %sms", processed_count, duration_ms)
    return processed_count, errors, duration_ms, results
