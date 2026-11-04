"""Check pinned runtime versions without importing any third-party package."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    requirements = (root / 'requirements.txt').read_text().splitlines()
    if sys.platform == 'win32':
        requirements += (root / 'requirements-desktop.txt').read_text().splitlines()
    for line in requirements:
        if not line.strip() or line.startswith('#'):
            continue
        name, expected = line.split('==', 1)
        try:
            if version(name) != expected:
                return 1
        except PackageNotFoundError:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
