# Pixel Forge 1.1.1 — desktop and branding validation

The supplied `static/images/logo.png` and `icon.png` are preserved unchanged.
The logo keeps its 2172:724 aspect ratio. Derived web icons and the Windows ICO
use proportional resizing and transparent padding. The ICO contains 16, 24, 32,
48, 64, 128 and 256 pixel images.

The Windows host uses pywebview with the Edge Chromium/WebView2 renderer.
A native-window integration check confirmed the supplied logo loaded, all three
title-bar buttons were present, and minimize, maximize, restore and close worked.
The local Uvicorn server completed shutdown when the window closed.
The desktop folder picker is owned by the main window and no longer launches
a detached console helper in normal desktop mode.

112 automated tests passed, including native-frame options, server cleanup,
folder picker selection/cancellation and active video-process termination.
Browser screenshots were reviewed at desktop and mobile widths. Desktop
dependency auditing reported no known vulnerabilities in the resolved packages.

The installer is per-user and includes the Microsoft offline WebView2 runtime.
Its Microsoft Authenticode signature is verified before packaging. The installer
checks both per-machine and per-user runtime registrations before installing it.
Start menu and desktop shortcuts point to the application and explicit custom
ICO, using the same AppUserModelID as the application window.

A silent installation in an isolated directory succeeded. The created Start menu
shortcut was inspected: its target, working directory and ICO path matched the
installed files, and the installed ICO matched the derived ICO byte for byte.
Launching that shortcut opened the packaged WebView2 workspace; its logo retained
its aspect ratio and image conversion succeeded inside the window.
Installation in the default per-user Programs directory was then verified,
including the desktop shortcut's executable and explicit custom ICO paths.

Existing configuration and output directories are preserved during updates and
uninstallation. Portable and setup executables are unsigned and include SHA-256
checksums. Windows can therefore show an unknown publisher notice.
