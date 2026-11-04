# Third-party components

Pixel Forge source code is distributed under the MIT license in LICENSE.
The Windows distribution includes independently licensed runtime components.
Their license texts are included in the executable's `licenses` directory
(extracted with the application at launch).

- Python: Python Software Foundation license, https://docs.python.org/3/license.html
- FastAPI, Starlette, Uvicorn, Pydantic and dependencies: see bundled license texts.
- Pillow and its bundled codecs: see bundled Pillow license texts.
- pywebview, Python.NET and CLR loader: see bundled license texts.
- Microsoft Edge WebView2 Runtime: distributed in the Windows installer under
  Microsoft's WebView2 runtime distribution terms. The Microsoft-signed offline
  installer runs only when the runtime is absent.
  https://developer.microsoft.com/microsoft-edge/webview2/
- Font Awesome Free 6.7.2: icons CC BY 4.0, fonts SIL OFL 1.1, code MIT.
  https://fontawesome.com/license/free
- Tailwind CSS: MIT. Only the compiled stylesheet is needed at runtime.
- FFmpeg and FFprobe: separate command-line programs from Gyan's essentials build,
  distributed under GNU GPL v3 or later. Pixel Forge invokes them as subprocesses.
  The FFmpeg distribution does not change the license of Pixel Forge's source.
  See `ffmpeg-license.txt`, `ffmpeg-build.txt` and `ffmpeg-source.txt` in the
  release downloads for license, build configuration and corresponding source.

FFmpeg upstream: https://ffmpeg.org/
Windows build provider: https://www.gyan.dev/ffmpeg/builds/
