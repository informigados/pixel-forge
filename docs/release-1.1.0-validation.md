# Pixel Forge 1.1.0 — validation

Date: 2026-11-03.

## Automated coverage

- 107 pytest cases passed on Windows, using the pinned runtime dependencies.
- Real conversions cover JPG, PNG, WEBP, AVIF, BMP, TIFF and ICO.
- Real conversions cover MP4, HEVC, MKV, WEBM, MOV, AVI, WMV and FLV,
  including odd source dimensions, resize and audio removal.
- Regression cases cover original/output preservation, duplicate names,
  EXIF orientation and privacy, recursive output exclusion, folder previews,
  invalid dimensions/quality, video error counts, mixed Sentinel formats,
  cross-site request rejection, bootstrap and executable path handling.
- Python dependency audit and npm audit: no known vulnerabilities reported
  for the resolved dependencies at the time of this review.

## Browser checks

- All five tabs checked at 320, 375, 768 and 1440 px.
- Screenshots reviewed for spacing, clipping, contrast and dialog layout.
- Four locales, keyboard tab navigation, Escape dismissal, focus restoration,
  image upload/conversion and history checked in Edge automation.
- Comparison images remain the same displayed size while the slider clips
  the processed layer. Reduced-motion preferences are respected.
- No JavaScript exceptions occurred during the final browser walkthrough.

## Windows executable

- Built with a complete Python 3.14 runtime, Pillow 13 and FFmpeg 9.0.2.
- Started from a different working directory with Python and FFmpeg absent
  from PATH; AVIF and video capabilities were available.
- All seven image and eight video formats exercised through the packaged API.
- Original/processed image previews served successfully.
- Live Sentinel test handled an image, video and corrupt image, placing each
  in the appropriate originals/processed/errors directory.
- Configuration and outputs stored outside the extraction directory.
- SHA-256 checksum and third-party license archive accompany the executable.

## Limits

The Windows UI automation environment did not expose the native folder dialog
as a targetable window. Helper-mode invocation, UTF-8 handling, bundled Tcl/Tk
and cancellation/error handling are covered, but a visual end-to-end selection
still needs a manual check in an interactive Windows session.

The executable is unsigned. Validation used representative local media,
not every possible codec, malformed file, GPU, browser or OS combination.
Linux/macOS executables are not included in this release.
