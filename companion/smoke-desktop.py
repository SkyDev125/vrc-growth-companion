"""Execute the frozen desktop app and check that its Qt Quick interface and SSL/OSC imports work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import shutil

out = Path(__file__).resolve().parents[1] / 'public/downloads'
if sys.platform == 'win32':
    binary = out / 'MidsDenCompanion/MidsDenCompanion.exe'
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
        install_dir=Path(directory)/'installed'
        setup=out/'mids-den-companion-windows-setup.exe'
        install_args=['/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/DIR='+str(install_dir)]
        installed=install_dir/'MidsDenCompanion.exe'
        isolated=Path(directory)/'userdata'
        config_dir=isolated/'MidsDenCompanion';config_dir.mkdir(parents=True)
        (config_dir/'config.json').write_text(json.dumps({'serverUrl':'http://127.0.0.1:9','oscHost':'127.0.0.1','oscPort':19000}))
        app_env=dict(env,LOCALAPPDATA=str(isolated),MIDSDEN_TEST_EXE=str(installed))
        script="@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $env:MIDSDEN_TEST_EXE } | Select-Object ProcessId,ParentProcessId,@{Name='HasWindow';Expression={ (Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue).MainWindowHandle -ne 0 }}) | ConvertTo-Json -Compress"
        def processes():
            raw=subprocess.check_output(['powershell.exe','-NoProfile','-Command',script],env=app_env,text=True).strip()
            data=json.loads(raw) if raw else []
            return data if isinstance(data,list) else [data]
        def start_running(expected):
            process=subprocess.Popen([str(installed)],env=app_env)
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                if process.poll() is not None:raise AssertionError('Installed app exited before upgrade test')
                entries=processes()
                if len(entries)==expected and any(p['HasWindow'] for p in entries):return process
                time.sleep(.5)
            process.kill()
            raise AssertionError(f'Expected {expected} processes and a visible app window: {processes()}')
        def upgrade_running(process):
            subprocess.run([str(setup),*install_args],check=True,timeout=180)
            process.wait(timeout=30)
            assert processes()==[], 'Upgrade left an old app process running or unexpectedly restarted it'
        # Reproduce the reported two-process one-file installation, then update it.
        previous=Path(directory)/'previous';previous.mkdir()
        subprocess.run(['gh','release','download','desktop-13-1','--repo',os.environ['GH_REPO'],
            '--pattern','mids-den-companion-windows-setup.exe','--dir',str(previous)],check=True,timeout=120)
        subprocess.run([str(previous/'mids-den-companion-windows-setup.exe'),*install_args],check=True,timeout=180)
        old_app=start_running(2)
        upgrade_running(old_app)
        assert (install_dir/'_internal').is_dir(), 'Bundled runtime was not installed'
        report.unlink(missing_ok=True)
        subprocess.run([str(installed),'--self-test'],env=app_env,check=True,timeout=90)
        assert json.loads(report.read_text())['status']=='ok'
        # Future upgrades see a single process and close it as well.
        new_app=start_running(1)
        upgrade_running(new_app)
        subprocess.run([str(installed),'--self-test'],env=app_env,check=True,timeout=90)
        subprocess.run([str(install_dir/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=90)
        print('Windows: two-process legacy upgrade, single-process new app, running-app upgrade, and uninstall passed')
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
