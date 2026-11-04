"""Fetch Microsoft's offline x64 runtime and verify its Authenticode signature."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://go.microsoft.com/fwlink/?linkid=2124701'


def prepare():
    destination = ROOT / 'bin' / 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix('.download')
        try:
            print('Downloading the offline WebView2 runtime from Microsoft...', flush=True)
            with urllib.request.urlopen(URL, timeout=120) as source, temporary.open('wb') as output:
                shutil.copyfileobj(source, output, length=1024*1024)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                    str(ROOT / 'scripts' / 'verify_microsoft_signature.ps1'),
                    '-Path', str(destination)], check=True)
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    destination.with_suffix('.exe.sha256').write_text(f'{digest}  {destination.name}\n', encoding='utf-8')
    return destination


if __name__ == '__main__':
    print(prepare())
