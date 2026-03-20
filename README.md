# 🚀 Pixel Forge

<div align="left">
  
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue.svg"></a>
  <a href="https://fastapi.tiangolo.com/"><img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115.11-009688.svg"></a>
  <a href="https://github.com/informigados/pixel-forge/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/informigados/pixel-forge/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://deepwiki.com/informigados/pixel-forge"><img alt="Ask DeepWiki" src="https://deepwiki.com/badge.svg"></a>
  
  <p><strong>Local-first media conversion and optimization for images and video.</strong></p>
  <p>Built for speed, privacy, and production-grade reliability.</p>
</div>

## 🌐 Overview

Pixel Forge is a local web application to convert and optimize images/videos without uploading files to third-party cloud services.  
It combines a FastAPI backend, FFmpeg/Pillow processing pipelines, and a responsive UI with real-time feedback.

Default content language in the product is **Portuguese (Brazil)**, with additional locale support for **Portuguese (Portugal)**, **English**, and **Spanish**.

## ✨ Key Capabilities

### 🖼️ Image Processing

- Convert between `JPG`, `PNG`, `WEBP`, `AVIF`, `BMP`, `TIFF`, and `ICO`
- Quality controls and optional resize
- Metadata stripping option for privacy workflows
- Upload mode and folder mode
- Before/after comparison with file size details

### 🎬 Video Processing

- Convert using FFmpeg: `MP4`, `MKV`, `WEBM`, `MOV`, `AVI`, `WMV`, `FLV`
- HEVC option (`mp4_hevc`)
- Optional audio removal
- Upload mode and folder mode
- Real-time progress updates over WebSocket

### 🧭 UX and Operations

- Sentinel mode: watch a folder and auto-process new files
- Sentinel output layout: `output/sentinel-mode/originals`, `output/sentinel-mode/processed`, `output/sentinel-mode/errors`
- In-app processing history
- Open output location directly from the interface
- Smart presets for common usage scenarios
- Responsive layout for desktop and mobile

## 🛡️ Reliability and Security Highlights

- Streamed uploads (avoid loading full files in memory)
- Upload limits by file count and file size (configurable via environment variables)
- Temporary file cleanup policy (age + max file count)
- Path allowlist checks for file preview and open-location endpoints
- Path allowlist roots are in-memory and session-scoped (after restart, only startup/config roots are available)
- Filename sanitization
- Security response headers middleware
- Trusted host validation
- Linux folder picker (`/select-folder`) requires a graphical session (`DISPLAY`/`WAYLAND_DISPLAY`)
- Sentinel in-memory state currently runs on a single async loop task (parallelization would require explicit locking)

## 🧱 Tech Stack

- Backend: Python, FastAPI, Uvicorn
- Media: Pillow (+ optional AVIF plugin), FFmpeg/FFprobe
- Frontend: HTML, TailwindCSS compilado localmente, Font Awesome local, Vanilla JavaScript
- Tests: Pytest + FastAPI TestClient
- CI: GitHub Actions (Linux and Windows matrix)

## 🗂️ Project Structure

```text
pixel-forge/
  app/
    main.py
    image_processor.py
    video_processor.py
    utils.py
  frontend/
    tailwind-input.css
  scripts/
    sync-fontawesome-assets.mjs
  static/
    index.html
    images/
    styles/
    vendor/
    temp_compare/
  tests/
  .github/workflows/ci.yml
  requirements-dev.txt
  package.json
  tailwind.config.js
  start.py
  setup_ffmpeg.py
```

## ⚡ Quick Start

### ✅ Prerequisites

- Python `3.10+`
- FFmpeg is auto-bootstrapped on first run (or install manually if preferred)

### 🪟 Windows

```bat
run.bat
```

`run.bat` already performs bootstrap (dependencies + FFmpeg check/setup) before starting.

### 🐧 Linux/macOS

```bash
chmod +x run.sh
./run.sh
```

`run.sh` already performs bootstrap (dependencies + FFmpeg check/setup) before starting.

### 🛠️ Manual Setup (Any Platform)

```bash
git clone https://github.com/informigados/pixel-forge.git
cd pixel-forge
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
npm run build:frontend
python start.py
```

`start.py` checks FFmpeg/FFprobe and auto-runs `setup_ffmpeg.py` when needed.

The server starts on the first free port in the `8000-8100` range and prints the final URL in the console.

### 🎨 Frontend Asset Build

The repository ships with compiled frontend assets under `static/`, so end users do not need Node.js to run the app.

Use the frontend toolchain only when you want to rebuild local assets:

```bash
npm install
npm run build:frontend
```

This command:

- synchronizes Font Awesome files into `static/vendor/fontawesome`
- recompiles Tailwind CSS into `static/styles/app.css`

## 🧪 Running Tests

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
PIXEL_FORGE_DISABLE_SENTINEL=1 python -m pytest -q
```

PowerShell:

```powershell
$env:PIXEL_FORGE_DISABLE_SENTINEL='1'; python -m pytest -q
```

CI runs `compileall` + `pytest` on:

- Ubuntu (`3.11`, `3.12`)
- Windows (`3.11`, `3.12`)

## ⚙️ Configuration (Environment Variables)

The backend supports runtime hardening with environment variables:

- `PIXEL_FORGE_DISABLE_SENTINEL`
- `PIXEL_FORGE_MAX_IMAGE_UPLOAD_FILES`
- `PIXEL_FORGE_MAX_VIDEO_UPLOAD_FILES`
- `PIXEL_FORGE_MAX_IMAGE_UPLOAD_BYTES`
- `PIXEL_FORGE_MAX_VIDEO_UPLOAD_BYTES`
- `PIXEL_FORGE_TEMP_MAX_AGE_SECONDS`
- `PIXEL_FORGE_TEMP_MAX_COUNT`
- `PIXEL_FORGE_ALLOW_UNVERIFIED_DOWNLOADS`
- `PIXEL_FORGE_FFMPEG_MACOS_SHA256`
- `PIXEL_FORGE_FFPROBE_MACOS_SHA256`

## 🔌 API Endpoints (Core)

- `GET /` UI entrypoint
- `GET /config` / `POST /config` load/save runtime configuration
- `POST /process` image processing
- `POST /process-video` video processing
- `GET /system-check` ffmpeg/avif capability check
- `GET /preview` secure file preview (allowlisted paths only)
- `POST /open-location` secure folder open (allowlisted paths only)
- `POST /select-folder` opens native folder dialog (GUI environments)
- `WS /ws/{client_id}` real-time progress and sentinel events

## 🔐 Privacy, Security, and Disclosure

- Media is processed locally by design.
- Review [SECURITY.md](SECURITY.md) for vulnerability reporting.
- Repository hygiene blocks local/internal artifacts from being committed (see `.gitignore`).

## 📝 Changelog

### 2026-03-10 (1.0.0)

- Initial release.

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## 👥 Authors

- [INformigados](https://github.com/informigados)
- [Alex Brito](https://github.com/AlexBritoDEV)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
