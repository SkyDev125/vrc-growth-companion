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
    env = dict(os.environ, MIDSDEN_SMOKE_REPORT=str(report), MIDSDEN_DISABLE_UPDATE_CHECKS='1')
    print('Checking frozen app startup', flush=True)
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
            raw=subprocess.check_output(['powershell.exe','-NoProfile','-Command',script],env=app_env,text=True,timeout=15).strip()
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
        print('Windows: installing legacy app and checking running-app upgrade', flush=True)
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
        print('Windows: checking current running-app upgrade', flush=True)
        new_app=start_running(1)
        upgrade_running(new_app)
        subprocess.run([str(installed),'--self-test'],env=app_env,check=True,timeout=90)
        # Exercise the updater's real external PowerShell -> setup -> restart handoff.
        print('Windows: checking updater install/restart handoff', flush=True)
        sys.path.insert(0,str(Path(__file__).parent))
        import updater
        new_app=start_running(1)
        report.unlink(missing_ok=True)
        saved_env=dict(os.environ)
        try:
            os.environ.update(app_env)
            os.environ.update(_PYI_ARCHIVE_FILE=str(installed), _PYI_APPLICATION_HOME_DIR=str(Path(directory)/'removed runtime'), _PYI_PARENT_PROCESS_LEVEL='1')
            helper=updater.launch_helper(setup,installed,Path(directory)/'update cache',new_app.pid,restart_self_test=True)
        except Exception:
            new_app.kill();new_app.wait(timeout=15)
            raise
        finally:
            os.environ.clear();os.environ.update(saved_env)
        subprocess.run(['powershell.exe','-NoProfile','-Command',
            '(Get-Process -Id '+str(new_app.pid)+').CloseMainWindow() | Out-Null'],check=True,timeout=15)
        new_app.wait(timeout=30)
        assert helper.wait(timeout=240)==0
        deadline=time.monotonic()+90
        while not report.exists() and time.monotonic()<deadline:time.sleep(.2)
        assert json.loads(report.read_text())['status']=='ok'
        assert (Path(directory)/'update cache/install-result.txt').read_text(encoding='utf-8-sig').strip()=='ok'
        assert json.loads((config_dir/'config.json').read_text())['oscPort']==19000
        time.sleep(2) # Let the self-test window and runtime exit before uninstalling.
        print('Windows: checking uninstall', flush=True)
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
            from macos_image import run_image_tool
            run_image_tool(['detach',str(mount)],force_detach=True)
        print('macOS app launches from mounted DMG')
    if sys.platform != 'win32':
        # Install over a disposable native app, then launch its frozen self-test.
        sys.path.insert(0,str(Path(__file__).parent))
        import updater
        if sys.platform=='darwin':
            target=Path(directory)/'installed/MidsDenCompanion.app'
            shutil.copytree(out/'MidsDenCompanion.app',target,symlinks=True)
            package=out/'mids-den-companion-macos.dmg'
        else:
            target=Path(directory)/'installed companion';shutil.copy2(binary,target)
            package=binary
        report.unlink(missing_ok=True)
        old=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])
        saved_env=dict(os.environ)
        try:
            os.environ.update(env)
            restart_binary=target/'Contents/MacOS/MidsDenCompanion' if sys.platform=='darwin' else target
            os.environ.update(_PYI_ARCHIVE_FILE=str(restart_binary), _PYI_APPLICATION_HOME_DIR=str(Path(directory)/'removed runtime'), _PYI_PARENT_PROCESS_LEVEL='1')
            helper=updater.launch_helper(package,target,Path(directory)/'update cache',old.pid,restart_self_test=True)
            old.terminate();old.wait(timeout=10)
            assert helper.wait(timeout=180)==0, (Path(directory)/'update cache/install.log').read_text()
            assert json.loads(report.read_text())['status']=='ok'
            assert (Path(directory)/'update cache/install-result.txt').read_text().strip()=='ok'
        finally:
            os.environ.clear();os.environ.update(saved_env)
            if old.poll() is None:old.kill();old.wait()
        print('Native updater replacement and restarted frozen app passed:',sys.platform)
