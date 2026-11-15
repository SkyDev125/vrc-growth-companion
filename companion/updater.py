"""Signed, opt-in application updates. No website credentials or Python install needed."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import urllib.request
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

ORIGIN = 'https://mid.shardware.net'
ASSETS = {
    'windows-x64': 'mids-den-companion-windows-setup.exe',
    'macos-arm64': 'mids-den-companion-macos-arm64.dmg',
    'macos-x64': 'mids-den-companion-macos-x64.dmg',
    'linux-x64': 'mids-den-companion-linux-x64',
}
MAX_PACKAGE = 500 * 1024 * 1024


def resources():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'update-assets'


def build_info():
    return json.loads((resources() / 'build.json').read_text(encoding='utf-8'))


def platform_key():
    machine = platform.machine().lower()
    if sys.platform == 'darwin':
        return 'macos-arm64' if machine in ('arm64', 'aarch64') else 'macos-x64' if machine in ('x86_64', 'amd64') else None
    if machine not in ('x86_64', 'amd64'): return None
    return {'win32': 'windows-x64', 'linux': 'linux-x64'}.get(sys.platform)


def generation(info):
    values = (info.get('build'), info.get('attempt'))
    if any(type(n) is not int or n < 0 for n in values):
        raise ValueError('Invalid update build number.')
    return values


def verify_manifest(envelope, current=None, key=None):
    """Verify bytes before interpreting any URLs, names or version fields."""
    try:
        payload = base64.b64decode(envelope['payload'], validate=True)
        signature = base64.b64decode(envelope['signature'], validate=True)
        public = load_pem_public_key(key or (resources() / 'public-key.pem').read_bytes())
        public.verify(signature, payload)
        info = json.loads(payload)
        if info.get('schema') != 1 or not re.fullmatch(r'\d+\.\d+\.\d+', info.get('version', '')):
            raise ValueError('Invalid update version.')
        build, attempt = generation(info)
        if current is not None and (build, attempt) <= generation(current): return None
        if set(info['assets']) != set(ASSETS): raise ValueError('Incomplete update release.')
        for target, name in ASSETS.items():
            item = info['assets'][target]
            expected = f'{ORIGIN}/api/companion/download/{build}-{attempt}/{name}'
            if item.get('url') != expected: raise ValueError('Unexpected update download address.')
            if type(item.get('size')) is not int or not 0 < item['size'] <= MAX_PACKAGE:
                raise ValueError('Invalid update download size.')
            if not re.fullmatch('[0-9a-f]{64}', item.get('sha256', '')):
                raise ValueError('Invalid update checksum.')
        return info
    except (KeyError, TypeError, InvalidSignature, UnicodeError) as error:
        raise ValueError('The update signature or manifest is invalid.') from error


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Update redirects are not allowed.')


def request(url):
    return urllib.request.build_opener(NoRedirect).open(
        urllib.request.Request(url, headers={'User-Agent': 'MidsDenCompanion-Updater/1'}), timeout=30)


def check():
    with request(ORIGIN + '/api/companion/update') as response:
        if response.status == 204: return None
        data = response.read(65537)
        if len(data) > 65536: raise ValueError('Update manifest is too large.')
    return verify_manifest(json.loads(data), build_info())


def verify_package(path, item):
    if path.stat().st_size != item['size']: raise ValueError('Update download is incomplete.')
    with path.open('rb') as file:
        if hashlib.file_digest(file, 'sha256').hexdigest() != item['sha256']:
            raise ValueError('Update checksum does not match. The app has not been changed.')


def download(info, directory, progress=lambda n: None):
    target = platform_key()
    if target not in ASSETS: raise ValueError('Updates are not available for this platform.')
    item = info['assets'][target]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    final = directory / ASSETS[target]
    partial = final.with_suffix(final.suffix + '.part')
    try:
        received = 0
        with request(item['url']) as response, partial.open('wb') as file:
            os.chmod(partial, 0o600)
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > item['size']: raise ValueError('Update download is larger than expected.')
                file.write(chunk)
                progress(round(received * 100 / item['size']))
        verify_package(partial, item)
        os.replace(partial, final)
        return final
    finally:
        partial.unlink(missing_ok=True)


def install_target(executable=None):
    executable = Path(executable or sys.executable).resolve()
    return executable.parents[2] if sys.platform == 'darwin' else executable


def launch_helper(package, target, directory, pid=None, restart_self_test=False):
    """Start an OS-provided helper outside the app, and confirm it is ready before quitting."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    ready = directory / 'helper-ready'
    result = directory / 'install-result.txt'
    ready.unlink(missing_ok=True)
    result.unlink(missing_ok=True)
    env = dict(os.environ, MIDSDEN_UPDATE_PACKAGE=str(package.resolve()), MIDSDEN_UPDATE_TARGET=str(target.resolve()),
               MIDSDEN_UPDATE_PID=str(pid or os.getpid()), MIDSDEN_UPDATE_READY=str(ready),
               MIDSDEN_UPDATE_RESULT=str(result))
    if restart_self_test: env['MIDSDEN_UPDATE_SELF_TEST'] = '1'
    # Copy helpers out of the frozen app's temporary extraction folder before it exits.
    suffix = 'ps1' if sys.platform == 'win32' else 'sh'
    helper = directory / ('install.' + suffix)
    helper.write_bytes((resources() / ('install.' + suffix)).read_bytes())
    if sys.platform == 'win32':
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(helper)]
        options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS}
    else:
        command = ['/bin/sh', str(helper), sys.platform]
        options = {'start_new_session': True}
    with (directory / 'install.log').open('wb') as log:
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **options)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None: raise RuntimeError('The updater could not start. See ' + str(directory / 'install.log'))
        if ready.exists(): return process
        time.sleep(.05)
    process.terminate()
    raise RuntimeError('The updater did not start in time; the app is still running.')
