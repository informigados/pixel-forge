import os
import platform
import shutil
import urllib.request
import zipfile
import tarfile
from pathlib import Path

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

    temp_archives: list[Path] = []

    try:
        if system == "Windows":
            archive = Path("ffmpeg-win.zip")
            temp_archives.append(archive)
            _download_file("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", archive)
            _extract_from_zip(archive, {
                ffmpeg_binary_name: ffmpeg_exe,
                ffprobe_binary_name: ffprobe_exe,
            })

        elif system == "Linux":
            archive = Path("ffmpeg-linux.tar.xz")
            temp_archives.append(archive)
            _download_file("https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz", archive)
            _extract_from_tar(archive, {
                ffmpeg_binary_name: ffmpeg_exe,
                ffprobe_binary_name: ffprobe_exe,
            })

        elif system == "Darwin":
            ffmpeg_archive = Path("ffmpeg-macos.zip")
            ffprobe_archive = Path("ffprobe-macos.zip")
            temp_archives.extend([ffmpeg_archive, ffprobe_archive])

            # evermeet publishes ffmpeg and ffprobe in separate archives
            _download_file("https://evermeet.cx/ffmpeg/getrelease/zip", ffmpeg_archive)
            _extract_from_zip(ffmpeg_archive, {ffmpeg_binary_name: ffmpeg_exe})

            _download_file("https://evermeet.cx/ffprobe/getrelease/zip", ffprobe_archive)
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
    finally:
        for archive in temp_archives:
            try:
                if archive.exists():
                    archive.unlink()
            except OSError as exc:
                print(f"Warning: could not remove temporary archive {archive}: {exc}")

if __name__ == "__main__":
    download_ffmpeg()
