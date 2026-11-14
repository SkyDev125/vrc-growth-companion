# VRChat Growth Companion

Self-contained desktop companion for Mid’s Den. No Python installation is required.

Download the latest installers from [Releases](https://github.com/SkyDev125/vrc-growth-companion/releases/latest): Windows setup EXE, macOS DMG for Apple Silicon or Intel, or the Linux x64 executable.

Enable OSC in VRChat, open the companion, and use 127.0.0.1:9000 when VRChat runs on the same computer. The app saves settings and sends the latest height every five seconds. UDP sending does not confirm in-game receipt. Settings stay in your user application settings directory.

Windows setup installs shortcuts and an uninstaller. On macOS, drag the app from the DMG into Applications. On Linux, mark the download executable and use Install shortcut inside the window.

OSC eye heights from 0.01 to 10,000 m are accepted; VRChat officially supports 0.1–100 m. Worlds can enforce scaling restrictions. Builds are unsigned; macOS/Windows may require opening approval.

## Builds

Actions runs tests, builds with PyInstaller on each OS, executes a native GUI/SSL/OSC smoke check, and publishes installers with SHA-256 checksums. For local builds, install PyInstaller 6.22.3 and run `python companion/build-desktop.py` on the target OS (Windows also needs Inno Setup 6).

This repository contains only companion source and build configuration. It contains no dashboard data or bot credentials.
