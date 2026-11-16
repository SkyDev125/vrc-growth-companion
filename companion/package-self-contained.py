#!/usr/bin/env python3
"""Build self-contained Mid's Den companion downloads for Windows, macOS, and Linux."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


VERSION = "3.13.18"
BUILD_TAG = "20261110"
TARGETS = {
    "windows": {
        "x86_64": ("x86_64-pc-windows-msvc", "2e0fed09d48989f64c9305da9ff2d37a41c0d13ab2aa6283405b2b620dfbf805"),
        "arm64": ("aarch64-pc-windows-msvc", "0a8840071810ddb8565256cd406b466d4e9dc6dc523395a5477880dbc4f67eb3"),
    },
    "macos": {
        "x86_64": ("x86_64-apple-darwin", "d27d59a722db9f69926eb6d9564071247221f45a04da920ea7f3001c97e32f9b"),
        "arm64": ("aarch64-apple-darwin", "7a2384641584ab9984221fcb0fc9265df465922af71be71410529e2a9c3f0540"),
    },
    "linux": {
        "x86_64": ("x86_64-unknown-linux-gnu", "f2d2199eb25880e07863b391cf7124e7ffa1338b0d65600dfcec117c4223a7fb"),
        "arm64": ("aarch64-unknown-linux-gnu", "55c00325f7c1fddf325dfc621aabdfbbac4dc54adda224af88ec411dc12db239"),
    },
}
APP_FILES = (
    "README.md",
    "Start Companion.bat",
    "Start Companion.command",
    "start-companion-windows.ps1",
    "start-companion.sh",
    "vrchat_companion.py",
    "growth_options.py",
    "desktop.py",
    "avatar_mapping.py",
    "resonite.py",
    "measurement_format.py",
    "measurement-units.json",
)
PACKAGE_ROOT = "Mids-Den-VRChat-Companion"


def download_runtime(target: str, expected_sha256: str, destination: Path) -> None:
    asset = f"cpython-{VERSION}%2B{BUILD_TAG}-{target}-install_only_stripped.tar.gz"
    url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{BUILD_TAG}/{asset}"
    request = Request(url, headers={"User-Agent": "MidsDen-Companion-packager/1.0"})
    print(f"Downloading {target}...", flush=True)
    digest = hashlib.sha256()
    with urlopen(request, timeout=120) as response, destination.open("wb") as archive:
        while chunk := response.read(1024 * 1024):
            archive.write(chunk)
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {target}: {actual}")


def add_windows_zip(source_dir: Path, output: Path) -> None:
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sorted(source_dir.rglob("*")):
            if source.is_dir() and not source.is_symlink():
                continue
            relative = PurePosixPath(PACKAGE_ROOT) / source.relative_to(source_dir).as_posix()
            info = ZipInfo(str(relative))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            source_mode = source.lstat().st_mode
            if stat.S_ISLNK(source_mode):
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, os.readlink(source))
            else:
                info.external_attr = (stat.S_IFREG | stat.S_IMODE(source_mode)) << 16
                archive.writestr(info, source.read_bytes())


def compact_runtime(runtime_dir, platform):
    root = runtime_dir / 'python'
    lib = root / 'Lib' if platform == 'windows' else root / 'lib/python3.13'
    for directory in ('site-packages', 'test', 'ensurepip', 'idlelib', 'turtledemo', '__pycache__'):
        shutil.rmtree(lib / directory, ignore_errors=True)
    zip_path = root / 'python313.zip' if platform == 'windows' else root / 'lib/python313.zip'
    with ZipFile(zip_path, 'w', compression=ZIP_DEFLATED) as archive:
        for source in list(lib.rglob('*.py')):
            if source.is_symlink():
                continue
            archive.write(source, source.relative_to(lib).as_posix())
            source.unlink()
    for source in list(lib.rglob('*.pyc')):
        source.unlink()
    for directory in sorted(lib.rglob('*'), reverse=True):
        if directory.is_dir() and not directory.is_symlink():
            try: directory.rmdir()
            except OSError: pass


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    downloads = project / "public" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mids-den-companion-") as temp_name:
        temp = Path(temp_name)
        archives = temp / "downloads"
        archives.mkdir()

        for platform, architectures in TARGETS.items():
            stage = temp / platform / PACKAGE_ROOT
            stage.mkdir(parents=True)
            for filename in APP_FILES:
                shutil.copy2(project / 'companion' / filename, stage / filename)
            for launcher in ("Start Companion.command", "start-companion.sh"):
                (stage / launcher).chmod(0o755)
            for architecture, (target, checksum) in architectures.items():
                runtime_archive = archives / f"{platform}-{architecture}.tar.gz"
                download_runtime(target, checksum, runtime_archive)
                runtime_dir = stage / ".runtime" / architecture
                runtime_dir.mkdir(parents=True, exist_ok=True)
                subprocess.run(["tar", "-xzf", str(runtime_archive), "-C", str(runtime_dir)], check=True)
                runtime_archive.unlink()
                compact_runtime(runtime_dir, platform)

                expected_executable = "python.exe" if platform == "windows" else f"python{VERSION.rsplit('.', 1)[0]}"
                if not any(runtime_dir.rglob(expected_executable)):
                    raise RuntimeError(f"{target} runtime does not contain {expected_executable}")

            if platform == "windows":
                output = downloads / "mids-den-vrchat-companion-windows.zip"
                add_windows_zip(stage, output)
            else:
                suffix = "macos" if platform == "macos" else "linux"
                output = downloads / f"mids-den-vrchat-companion-{suffix}.tar.gz"
                output.unlink(missing_ok=True)
                subprocess.run([
                    "tar", "-czf", str(output), "-C", str(stage.parent), PACKAGE_ROOT,
                ], check=True)

            digest = hashlib.sha256()
            with output.open("rb") as artifact:
                while chunk := artifact.read(1024 * 1024):
                    digest.update(chunk)
            print(f"Built {output} ({output.stat().st_size:,} bytes; sha256 {digest.hexdigest()})", flush=True)


if __name__ == "__main__":
    main()
