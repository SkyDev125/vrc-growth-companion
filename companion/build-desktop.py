"""Run on each target OS with PyInstaller installed; produces native desktop artifacts."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

project = Path(__file__).resolve().parents[1]
out = project / 'public/downloads'
name = 'MidsDenCompanion'
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed', '--name', name, '--distpath', str(out), str(project / 'companion/desktop.py')], check=True)
if sys.platform == 'win32':
    compiler = shutil.which('ISCC')
    if not compiler:
        raise SystemExit('Desktop EXE built. Install Inno Setup on the build machine to create the setup EXE.')
    subprocess.run([compiler, str(project / 'companion/windows-installer.iss')], check=True)
elif sys.platform == 'darwin':
    with tempfile.TemporaryDirectory() as folder:
        stage = Path(folder)
        shutil.copytree(out / (name + '.app'), stage / (name + '.app'), symlinks=True)
        (stage / 'Applications').symlink_to('/Applications')
        subprocess.run(['hdiutil', 'create', '-volname', "Mid's Den Companion", '-srcfolder', str(stage), '-ov', str(out / 'mids-den-companion-macos.dmg')], check=True)
