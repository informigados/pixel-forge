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

from build_brand_assets import build_icons

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "win32":
        raise SystemExit("Build the Windows executable on Windows.")
    version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    icon_path = build_icons()
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
    requirements = (ROOT / "requirements.txt").read_text().splitlines()
    requirements += (ROOT / "requirements-desktop.txt").read_text().splitlines()
    for requirement in requirements:
        if requirement and not requirement.startswith('#'):
            collect_license(requirement.split('==')[0])
    version_file = staging / 'windows-version.txt'
    version_tuple = tuple(int(part) for part in version.split('.')) + (0,)
    version_file.write_text(f'''VSVersionInfo(
      ffi=FixedFileInfo(filevers={version_tuple}, prodvers={version_tuple}, mask=0x3f,
                       flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)),
      kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'INformigados'),
        StringStruct('FileDescription', 'Pixel Forge'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('ProductName', 'Pixel Forge'),
        StringStruct('ProductVersion', '{version}'),
        StringStruct('OriginalFilename', 'PixelForge.exe')])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])''', encoding='utf-8')
    name = f"PixelForge-{version}-windows-x64"
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
               '--windowed', '--noupx', '--name', name, '--icon', str(icon_path),
               '--version-file', str(version_file),
               '--paths', str(ROOT), '--add-data', f'{static};static',
               '--add-data', f'{notices};licenses',
               '--hidden-import', 'app.main', '--collect-all', 'uvicorn',
               '--collect-all', 'websockets', '--collect-all', 'PIL',
               '--collect-all', 'webview', '--collect-all', 'clr_loader', '--collect-all', 'pythonnet',
               '--hidden-import', 'webview.platforms.winforms',
               '--hidden-import', 'webview.platforms.edgechromium',
               '--exclude-module', 'PyQt5', '--exclude-module', 'PyQt6',
               '--exclude-module', 'PySide2', '--exclude-module', 'PySide6',
               '--exclude-module', 'cefpython3',
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
