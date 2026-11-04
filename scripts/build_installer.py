"""Package the desktop executable, shortcuts and offline WebView2 dependency."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from prepare_webview2 import prepare

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    executable = ROOT / 'dist' / f'PixelForge-{version}-windows-x64.exe'
    if not executable.exists():
        raise SystemExit('Build the desktop executable first: python scripts/build_windows.py')
    runtime = prepare()
    candidates = [shutil.which('ISCC.exe'),
        str(Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe'),
        str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Inno Setup 6' / 'ISCC.exe')]
    compiler = next((str(p) for p in candidates if p and Path(p).is_file()), None)
    if not compiler:
        raise SystemExit('Install Inno Setup 6 to build the Windows installer.')
    subprocess.run([compiler, f'/DMyAppVersion={version}', f'/DSourceExe={executable}',
        f'/DIconFile={ROOT / "static/images/app-icon.ico"}',
        f'/DLicenseArchive={ROOT / "dist" / f"PixelForge-{version}-windows-x64-licenses.zip"}',
        f'/DWebView2Installer={runtime}', f'/DOutputDirectory={ROOT / "dist"}',
        str(ROOT / 'installer' / 'pixel-forge.iss')], check=True)
    installer = ROOT / 'dist' / f'PixelForge-{version}-setup-windows-x64.exe'
    with installer.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    installer.with_suffix('.exe.sha256').write_text(f'{digest}  {installer.name}\n', encoding='utf-8')
    print(f'Installer built: {installer}')


if __name__ == '__main__':
    main()
