# 🤝 Contributing to Pixel Forge

Thank you for your interest in contributing.

## 🛠️ Development Setup

1. Install runtime dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Optional: rebuild local frontend assets after UI changes:
   ```bash
   npm install
   npm run build:frontend
   ```
4. Run tests:
   ```bash
   PIXEL_FORGE_DISABLE_SENTINEL=1 pytest -q
   ```

On Windows PowerShell:

```powershell
$env:PIXEL_FORGE_DISABLE_SENTINEL='1'
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -q
```

## ✅ Pull Request Checklist

1. Keep changes scoped to one clear objective.
2. Add or update tests for behavioral changes.
3. Ensure all tests pass locally.
4. Update documentation when relevant.
5. Use descriptive commit messages.
6. Do not commit runtime artifacts (`output/`, `temp_uploads/`, `static/temp_compare/*`) or local binaries.

## 🧩 Code Guidelines

1. Keep code readable and explicit.
2. Prefer small, testable functions.
3. Validate input at API boundaries.
4. Preserve pt-BR clarity in user-facing strings.

## 🐞 Reporting Bugs

Open an issue with:

1. Reproduction steps.
2. Expected and actual behavior.
3. Environment details (OS, Python version, FFmpeg availability).
