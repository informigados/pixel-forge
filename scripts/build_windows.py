"""Build a self-contained Windows executable, without bundling user data.

Run with the release venv: python scripts/build_windows.py
Frontend assets and bin/ffmpeg.exe + bin/ffprobe.exe must already exist.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "win32":
        raise SystemExit("Build the Windows executable on Windows.")
    version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    staging = ROOT / "build" / "release-assets"
    staging.mkdir(parents=True, exist_ok=True)
    static = staging / "static"
    static.mkdir(exist_ok=True)
    for filename in ["index.html", "manifest.webmanifest"]:
        shutil.copy2(ROOT / "static" / filename, static / filename)
    for directory in ["styles", "images", "vendor"]:
        shutil.copytree(ROOT / "static" / directory, static / directory, dirs_exist_ok=True)
    notices = staging / "licenses"
    notices.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", notices / "PixelForge-MIT.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", notices / "THIRD_PARTY_NOTICES.md")
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, notices / 'Python-LICENSE.txt')
    for filename in ['ffmpeg-license.txt', 'ffmpeg-readme.txt']:
        path = ROOT / 'bin' / filename
        if not path.exists():
            raise SystemExit(f'Missing {path}. Extract LICENSE and README.txt from the FFmpeg archive before distribution.')
        shutil.copy2(path, notices / filename)
    ffmpeg_build = subprocess.run([str(ROOT / 'bin' / 'ffmpeg.exe'), '-version'],
                                 capture_output=True, text=True, check=True).stdout
    (notices / 'ffmpeg-build.txt').write_text(ffmpeg_build, encoding='utf-8')
    # Include the license texts shipped by every installed runtime dependency.
    visited = set()
    def collect_license(name):
        dist = importlib.metadata.distribution(name)
        key = dist.metadata['Name']
        if key in visited:
            return
        visited.add(key)
        for file in dist.files or []:
            if 'license' in str(file).lower() or 'copying' in str(file).lower():
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = notices / key / str(file).replace('..', '_')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        from packaging.requirements import Requirement
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                collect_license(requirement.name)
    for requirement in (ROOT / "requirements.txt").read_text().splitlines():
        if requirement and not requirement.startswith('#'):
            collect_license(requirement.split('==')[0])
    # Reuse the project's cube silhouette for the Windows application icon.
    from PIL import Image, ImageDraw
    icon = Image.new('RGBA', (256, 256), (2, 6, 23, 255))
    draw = ImageDraw.Draw(icon)
    draw.polygon([(128, 24), (224, 60), (224, 196), (128, 232), (32, 196), (32, 60)], fill='#10b981')
    draw.polygon([(128, 46), (198, 72), (128, 98), (58, 72)], fill='#020617')
    draw.polygon([(144, 122), (204, 100), (204, 182), (144, 204)], fill='#020617')
    icon_path = staging / 'pixel-forge.ico'
    icon.save(icon_path, sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    name = f"PixelForge-{version}-windows-x64"
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
               '--console', '--noupx', '--name', name, '--icon', str(icon_path),
               '--paths', str(ROOT), '--add-data', f'{static};static',
               '--add-data', f'{notices};licenses',
               '--hidden-import', 'app.main', '--collect-all', 'uvicorn',
               '--collect-all', 'websockets', '--collect-all', 'PIL',
               '--copy-metadata', 'fastapi', '--copy-metadata', 'starlette',
               '--copy-metadata', 'opentelemetry-api']
    for binary in ['ffmpeg.exe', 'ffprobe.exe']:
        path = ROOT / 'bin' / binary
        if not path.is_file():
            raise SystemExit(f'Missing {path}. Run python setup_ffmpeg.py first.')
        command += ['--add-binary', f'{path};bin']
    subprocess.run(command + [str(ROOT / 'start.py')], cwd=ROOT, check=True)
    executable = ROOT / 'dist' / f'{name}.exe'
    with executable.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    executable.with_suffix('.exe.sha256').write_text(f'{checksum}  {executable.name}\n', encoding='utf-8')
    shutil.make_archive(str(ROOT / 'dist' / f'{name}-licenses'), 'zip', notices)
    print(f'Built {executable} ({executable.stat().st_size / 1024**2:.1f} MiB)')


if __name__ == '__main__':
    main()
