import hashlib
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional


ALLOW_UNVERIFIED_DOWNLOADS = os.getenv(
    "PIXEL_FORGE_ALLOW_UNVERIFIED_DOWNLOADS",
    "",
).strip().lower() in {"1", "true", "yes", "on"}

WINDOWS_FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
WINDOWS_FFMPEG_SHA256_URL = f"{WINDOWS_FFMPEG_URL}.sha256"
LINUX_FFMPEG_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
LINUX_FFMPEG_MD5_URL = f"{LINUX_FFMPEG_URL}.md5"
MACOS_FFMPEG_URL = "https://evermeet.cx/ffmpeg/getrelease/zip"
MACOS_FFPROBE_URL = "https://evermeet.cx/ffprobe/getrelease/zip"


def _download_text(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def _extract_expected_digest(checksum_text: str, algorithm: str, filename: Optional[str] = None) -> str:
    digest_lengths = {"sha256": 64, "md5": 32}
    digest_length = digest_lengths[algorithm]

    for line in checksum_text.splitlines():
        if filename and filename not in line:
            continue
        tokens = line.replace("*", " ").split()
        for token in tokens:
            normalized = token.strip().lower()
            if len(normalized) == digest_length and all(ch in "0123456789abcdef" for ch in normalized):
                return normalized

    raise ValueError(f"Unable to parse {algorithm} digest for {filename or 'download'}")


def _calculate_file_digest(file_path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with open(file_path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_download(
    destination: Path,
    *,
    algorithm: str,
    checksum_url: Optional[str] = None,
    expected_digest: Optional[str] = None,
) -> None:
    resolved_digest = expected_digest.lower() if expected_digest else None
    if resolved_digest is None and checksum_url:
        checksum_text = _download_text(checksum_url)
        resolved_digest = _extract_expected_digest(checksum_text, algorithm, destination.name)

    if resolved_digest is None:
        if ALLOW_UNVERIFIED_DOWNLOADS:
            print(f"Warning: integrity verification skipped for {destination.name}")
            return
        raise ValueError(
            f"No integrity metadata available for {destination.name}. "
            "Set a checksum or PIXEL_FORGE_ALLOW_UNVERIFIED_DOWNLOADS=1 to bypass."
        )

    actual_digest = _calculate_file_digest(destination, algorithm)
    if actual_digest != resolved_digest:
        raise ValueError(
            f"Integrity verification failed for {destination.name}: "
            f"expected {resolved_digest}, got {actual_digest}"
        )

    print(f"Verified {algorithm} for {destination.name}")

def _download_file(url: str, destination: Path) -> None:
    print(f"Downloading from {url}...")
    urllib.request.urlretrieve(url, str(destination))


def _extract_from_zip(archive_path: Path, targets: dict[str, Path]) -> set[str]:
    extracted: set[str] = set()
    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        for member in zip_ref.namelist():
            normalized = member.rstrip("/")
            for binary_name, output_path in targets.items():
                if normalized == binary_name or normalized.endswith(f"/{binary_name}"):
                    print(f"Extracting {normalized} -> {output_path.name}")
                    with zip_ref.open(member) as source, open(output_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted.add(binary_name)
    return extracted


def _extract_from_tar(archive_path: Path, targets: dict[str, Path]) -> set[str]:
    extracted: set[str] = set()
    with tarfile.open(archive_path, "r:xz") as tar_ref:
        for member in tar_ref.getmembers():
            for binary_name, output_path in targets.items():
                if member.name.endswith(f"/{binary_name}"):
                    print(f"Extracting {member.name} -> {output_path.name}")
                    source = tar_ref.extractfile(member)
                    if source is None:
                        continue
                    with source, open(output_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted.add(binary_name)
    return extracted


def _mark_executable_if_needed(system: str, *files: Path) -> None:
    if system == "Windows":
        return
    for file_path in files:
        if file_path.exists():
            st = os.stat(file_path)
            os.chmod(file_path, st.st_mode | 0o111)


def download_ffmpeg():
    system = platform.system()
    machine = platform.machine()

    print(f"Detecting system: {system} {machine}")

    base_dir = Path(__file__).parent
    bin_dir = base_dir / "bin"
    bin_dir.mkdir(exist_ok=True)

    ffmpeg_exe = bin_dir / "ffmpeg.exe"
    ffprobe_exe = bin_dir / "ffprobe.exe"
    ffmpeg_binary_name = "ffmpeg.exe"
    ffprobe_binary_name = "ffprobe.exe"

    if system != "Windows":
        ffmpeg_exe = bin_dir / "ffmpeg"
        ffprobe_exe = bin_dir / "ffprobe"
        ffmpeg_binary_name = "ffmpeg"
        ffprobe_binary_name = "ffprobe"

    if ffmpeg_exe.exists() and ffprobe_exe.exists():
        print(f"FFmpeg and FFprobe already exist in {bin_dir}")
        return

    try:
        with tempfile.TemporaryDirectory(prefix="pixel-forge-ffmpeg-") as temp_dir:
            temp_dir_path = Path(temp_dir)

            if system == "Windows":
                archive = temp_dir_path / "ffmpeg-win.zip"
                _download_file(WINDOWS_FFMPEG_URL, archive)
                _verify_download(
                    archive,
                    algorithm="sha256",
                    checksum_url=WINDOWS_FFMPEG_SHA256_URL,
                )
                _extract_from_zip(archive, {
                    ffmpeg_binary_name: ffmpeg_exe,
                    ffprobe_binary_name: ffprobe_exe,
                })

            elif system == "Linux":
                archive = temp_dir_path / "ffmpeg-linux.tar.xz"
                _download_file(LINUX_FFMPEG_URL, archive)
                _verify_download(
                    archive,
                    algorithm="md5",
                    checksum_url=LINUX_FFMPEG_MD5_URL,
                )
                _extract_from_tar(archive, {
                    ffmpeg_binary_name: ffmpeg_exe,
                    ffprobe_binary_name: ffprobe_exe,
                })

            elif system == "Darwin":
                ffmpeg_archive = temp_dir_path / "ffmpeg-macos.zip"
                ffprobe_archive = temp_dir_path / "ffprobe-macos.zip"

                # evermeet publishes ffmpeg and ffprobe in separate archives
                _download_file(MACOS_FFMPEG_URL, ffmpeg_archive)
                _verify_download(
                    ffmpeg_archive,
                    algorithm="sha256",
                    expected_digest=os.getenv("PIXEL_FORGE_FFMPEG_MACOS_SHA256"),
                )
                _extract_from_zip(ffmpeg_archive, {ffmpeg_binary_name: ffmpeg_exe})

                _download_file(MACOS_FFPROBE_URL, ffprobe_archive)
                _verify_download(
                    ffprobe_archive,
                    algorithm="sha256",
                    expected_digest=os.getenv("PIXEL_FORGE_FFPROBE_MACOS_SHA256"),
                )
                _extract_from_zip(ffprobe_archive, {ffprobe_binary_name: ffprobe_exe})

            else:
                print(f"Unsupported system: {system}")
                return

        _mark_executable_if_needed(system, ffmpeg_exe, ffprobe_exe)

        missing = []
        if not ffmpeg_exe.exists():
            missing.append("ffmpeg")
        if not ffprobe_exe.exists():
            missing.append("ffprobe")

        if missing:
            print(f"FFmpeg installation incomplete. Missing: {', '.join(missing)}")
        else:
            print(f"FFmpeg tools installed to {bin_dir}")

    except Exception as e:
        print(f"Error installing FFmpeg: {e}")

if __name__ == "__main__":
    download_ffmpeg()
