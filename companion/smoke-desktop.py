"""Execute the frozen desktop app and check that its native Tk/SSL/OSC imports work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

out = Path(__file__).resolve().parents[1] / 'public/downloads'
if sys.platform == 'win32':
    binary = out / 'MidsDenCompanion.exe'
elif sys.platform == 'darwin':
    binary = out / 'MidsDenCompanion.app/Contents/MacOS/MidsDenCompanion'
else:
    binary = out / 'MidsDenCompanion'
with tempfile.TemporaryDirectory() as directory:
    report = Path(directory) / 'report.json'
    env = dict(os.environ, MIDSDEN_SMOKE_REPORT=str(report))
    subprocess.run([str(binary), '--self-test'], env=env, check=True, timeout=90)
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result == {'status': 'ok', 'platform': sys.platform}, result
    print('Native frozen GUI smoke test passed:', sys.platform)
    if sys.platform == 'win32':
        install_dir = Path(directory) / 'installed'
        setup = out / 'mids-den-companion-windows-setup.exe'
        subprocess.run([str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/DIR=' + str(install_dir)], check=True, timeout=120)
        installed = install_dir / 'MidsDenCompanion.exe'
        assert installed.is_file(), 'Installer did not install the app'
        report.unlink()
        subprocess.run([str(installed), '--self-test'], env=env, check=True, timeout=90)
        assert json.loads(report.read_text())['status'] == 'ok'
        subprocess.run([str(install_dir / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], check=True, timeout=90)
        print('Windows setup, installed app, and uninstaller passed')
    elif sys.platform == 'darwin':
        mount = Path(directory) / 'mounted'
        mount.mkdir()
        subprocess.run(['hdiutil', 'attach', str(out / 'mids-den-companion-macos.dmg'), '-nobrowse', '-mountpoint', str(mount)], check=True)
        try:
            report.unlink()
            mounted = mount / 'MidsDenCompanion.app/Contents/MacOS/MidsDenCompanion'
            subprocess.run([str(mounted), '--self-test'], env=env, check=True, timeout=90)
            assert json.loads(report.read_text())['status'] == 'ok'
        finally:
            subprocess.run(['hdiutil', 'detach', str(mount)], check=True)
        print('macOS app launches from mounted DMG')
