import shutil
import subprocess
import logging
import traceback
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable
import json
import asyncio
import re
from .utils import ensure_directory, is_supported_video_extension, normalize_path, get_app_base_path, sanitize_filename, to_windows_long_path

logger = logging.getLogger("pixelforge")

class VideoProcessor:
    def __init__(self):
        # Check system PATH
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.ffprobe_path = shutil.which("ffprobe")
        
        # Check local bin folder
        local_bin_dir = get_app_base_path() / "bin"
        
        if not self.ffmpeg_path:
            local_ffmpeg = local_bin_dir / "ffmpeg.exe"
            if local_ffmpeg.exists():
                self.ffmpeg_path = str(local_ffmpeg)
                
        if not self.ffprobe_path:
            local_ffprobe = local_bin_dir / "ffprobe.exe"
            if local_ffprobe.exists():
                self.ffprobe_path = str(local_ffprobe)
                    
        if not self.ffmpeg_path:
            logger.warning("FFmpeg não encontrado no PATH do sistema. Processamento de vídeo não funcionará.")
        else:
            logger.info(f"FFmpeg encontrado em: {self.ffmpeg_path}")
            
        if self.ffprobe_path:
            logger.info(f"FFprobe encontrado em: {self.ffprobe_path}")

    def check_ffmpeg(self) -> bool:
        return self.ffmpeg_path is not None

    def _get_video_metadata_sync(self, file_path: Path) -> Dict:
        """Sync implementation of get_video_metadata using subprocess.run"""
        if not self.check_ffmpeg():
            return {}
        
        try:
            input_path_str = to_windows_long_path(file_path)
            cmd = [
                self.ffprobe_path or "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                input_path_str
            ]
            
            # Run synchronously
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"Erro ao ler metadados (código {result.returncode}): {result.stderr}")
                return {}
                
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Falha ao obter metadados (sync): {repr(e)}\n{traceback.format_exc()}")
            return {}

    async def get_video_metadata(self, file_path: Path) -> Dict:
        return await asyncio.to_thread(self._get_video_metadata_sync, file_path)

    def _process_video_sync(
        self,
        cmd: List[str],
        duration_sec: float,
        output_path: Path,
        progress_callback_sync: Optional[Callable]
    ) -> Tuple[bool, str, Optional[str]]:
        """Sync implementation of process_video using subprocess.Popen"""
        try:
            logger.info(f"Iniciando conversão (sync): {' '.join(cmd)}")
            
            # Using Popen for real-time output reading
            # On Windows, we need to be careful with creationflags if needed, but usually defaults work
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True, # Text mode
                encoding='utf-8',
                errors='ignore'
            )
            
            time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
            last_percent = -1
            stderr_lines = []
            
            # Read stderr
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                
                if line:
                    line_str = line.strip()
                    stderr_lines.append(line_str)
                    if len(stderr_lines) > 20:
                        stderr_lines.pop(0)
                        
                    match = time_pattern.search(line_str)
                    if match and duration_sec > 0:
                        try:
                            h, m, s = map(float, match.groups())
                            current_seconds = h * 3600 + m * 60 + s
                            percent = int((current_seconds / duration_sec) * 100)
                            percent = max(0, min(99, percent))
                            
                            if percent != last_percent:
                                last_percent = percent
                                if progress_callback_sync:
                                    progress_callback_sync(percent)
                        except Exception as exc:
                            logger.debug("Falha ao interpretar progresso do FFmpeg: %s", exc)
                            
            returncode = process.poll()
            
            if returncode != 0:
                error_details = "\n".join(stderr_lines)
                logger.error(f"Erro FFmpeg (sync): {error_details}")
                return False, f"Erro na conversão: {stderr_lines[-1] if stderr_lines else 'Erro desconhecido'}", None

            if progress_callback_sync:
                progress_callback_sync(100)

            return True, f"Vídeo processado com sucesso: {output_path.name}", str(output_path)
            
        except Exception as e:
             logger.error(f"Erro interno no processamento de vídeo (sync): {repr(e)}\n{traceback.format_exc()}")
             return False, f"Erro interno: {str(e)}", None

    async def process_video(
        self,
        file_path: Path,
        output_dir: Path,
        target_format: str = "mp4",
        quality: int = 80,
        width: Optional[int] = None,
        height: Optional[int] = None,
        remove_audio: bool = False,
        strip_metadata: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Process a single video file using FFmpeg with real-time progress.
        Delegates to sync implementation via thread to avoid event loop issues.
        """
        if not self.check_ffmpeg():
            return False, "FFmpeg não instalado ou não encontrado no PATH.", None

        if not file_path.exists():
             return False, f"Arquivo não encontrado: {file_path}", None

        try:
            ensure_directory(output_dir)
            
            # 1. Get metadata (now async wrapper around sync)
            metadata = await self.get_video_metadata(file_path)
            duration_sec = 0.0
            try:
                if metadata and 'format' in metadata and 'duration' in metadata['format']:
                    duration_sec = float(metadata['format']['duration'])
            except Exception as exc:
                logger.debug("Falha ao interpretar duração do vídeo %s: %s", file_path, exc)

            # Construct command (logic identical to before)
            final_ext = target_format
            if target_format == "mp4_hevc":
                final_ext = "mp4"
                
            safe_stem = sanitize_filename(file_path.stem)
            output_filename = f"{safe_stem}.{final_ext}"
            output_path = output_dir / output_filename
            crf = int(51 - (quality * 0.33))
            crf = max(0, min(51, crf))

            input_path_str = to_windows_long_path(file_path)
            output_path_str = to_windows_long_path(output_path)

            cmd = [self.ffmpeg_path, "-y", "-i", input_path_str]

            if target_format == "mp4_hevc":
                cmd.extend(["-c:v", "libx265", "-tag:v", "hvc1"])
            elif target_format in ["mp4", "mkv", "mov"]:
                cmd.extend(["-c:v", "libx264"])
            elif target_format == "webm":
                cmd.extend(["-c:v", "libvpx-vp9"])
            elif target_format == "wmv":
                cmd.extend(["-c:v", "wmv2"])
            elif target_format == "flv":
                cmd.extend(["-c:v", "flv1"])
            elif target_format == "avi":
                cmd.extend(["-c:v", "mpeg4"])
            else:
                cmd.extend(["-c:v", "libx264"])

            if target_format not in ["wmv", "flv", "avi"]:
                cmd.extend(["-crf", str(crf), "-preset", "medium"])
            else:
                cmd.extend(["-q:v", str(max(2, int((100-quality)/5)))])

            if remove_audio:
                cmd.append("-an")
            else:
                if target_format in ["mp4", "mkv", "mov", "mp4_hevc"]:
                    cmd.extend(["-c:a", "aac", "-b:a", "128k"])
                elif target_format == "webm":
                    cmd.extend(["-c:a", "libvorbis", "-b:a", "128k"])
                elif target_format == "wmv":
                    cmd.extend(["-c:a", "wmav2", "-b:a", "128k"])
                else:
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", "128k"])

            if strip_metadata:
                cmd.extend(["-map_metadata", "-1"])

            if width or height:
                w = width if width else -2
                h = height if height else -2
                cmd.extend(["-vf", f"scale={w}:{h}"])

            cmd.append(output_path_str)
            
            logger.info(f"Comando FFmpeg construído: {cmd}")

            # Prepare callback for sync execution
            loop = asyncio.get_running_loop()
            
            def sync_callback_wrapper(p):
                if progress_callback:
                    # Thread-safe call to async callback
                    asyncio.run_coroutine_threadsafe(progress_callback(p), loop)

            # Run in thread
            return await asyncio.to_thread(
                self._process_video_sync,
                cmd,
                duration_sec,
                output_path,
                sync_callback_wrapper
            )

        except Exception as e:
            logger.error(f"Erro interno no processamento de vídeo: {repr(e)}\n{traceback.format_exc()}")
            return False, f"Erro interno: {str(e)}", None

video_processor = VideoProcessor()
