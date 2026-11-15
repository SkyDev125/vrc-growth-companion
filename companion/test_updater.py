import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import updater


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        self.bytes = b'complete fake installer'
        self.info = {'schema': 1, 'version': '1.3.0', 'build': 25, 'attempt': 2, 'assets': {}}
        for target, name in updater.ASSETS.items():
            self.info['assets'][target] = {'url': f'{updater.ORIGIN}/api/companion/download/25-2/{name}',
                'size': len(self.bytes), 'sha256': hashlib.sha256(self.bytes).hexdigest()}

    def envelope(self, info=None):
        payload = json.dumps(info or self.info).encode()
        return {'payload': base64.b64encode(payload).decode(),
                'signature': base64.b64encode(self.key.sign(payload)).decode()}

    def test_signature_tampering_and_rollback(self):
        self.assertEqual(updater.verify_manifest(self.envelope(), {'build': 24, 'attempt': 1}, self.public), self.info)
        self.assertIsNone(updater.verify_manifest(self.envelope(), {'build': 25, 'attempt': 2}, self.public))
        self.assertIsNone(updater.verify_manifest(self.envelope(), {'build': 26, 'attempt': 1}, self.public))
        envelope = self.envelope()
        envelope['payload'] = base64.b64encode(b'{}').decode()
        with self.assertRaises(ValueError): updater.verify_manifest(envelope, key=self.public)
        with self.assertRaises(ValueError): updater.verify_manifest(self.envelope())

    def test_even_signed_manifest_must_have_exact_origin_and_platform_assets(self):
        mutations = [lambda i: i['assets']['linux-x64'].update(url='https://evil.invalid/file'),
                     lambda i: i['assets'].pop('macos-x64'),
                     lambda i: i['assets']['windows-x64'].update(size=updater.MAX_PACKAGE+1),
                     lambda i: i['assets']['windows-x64'].update(sha256='not-a-hash')]
        for mutate in mutations:
            info = copy.deepcopy(self.info); mutate(info)
            with self.assertRaises(ValueError): updater.verify_manifest(self.envelope(info), key=self.public)

    def test_download_is_atomic_and_rejects_truncation_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(updater, 'platform_key', return_value='linux-x64'):
            destination = Path(directory)
            for content in (self.bytes[:-1], b'x' * len(self.bytes), self.bytes+b'x'):
                with patch.object(updater, 'request', return_value=io.BytesIO(content)):
                    with self.assertRaises(ValueError): updater.download(self.info, destination)
                self.assertEqual(list(destination.iterdir()), [])
            progress = []
            with patch.object(updater, 'request', return_value=io.BytesIO(self.bytes)):
                file = updater.download(self.info, destination, progress.append)
            self.assertEqual(file.read_bytes(), self.bytes)
            self.assertEqual(progress[-1], 100)

    def test_real_key_fixture_and_redirect_rejection(self):
        fixture = json.loads((updater.resources()/'verification-fixture.json').read_text())
        self.assertEqual(updater.verify_manifest(fixture)['schema'], 1)
        with self.assertRaises(ValueError): updater.NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid')

    @unittest.skipUnless(sys.platform == 'linux', 'Linux executable replacement')
    def test_linux_helper_waits_replaces_restarts_and_preserves_userdata(self):
        with tempfile.TemporaryDirectory(prefix='update paths with spaces ') as directory:
            root = Path(directory)
            target = root/'Companion'; target.write_text('#!/bin/sh\nexit 99\n');target.chmod(0o755)
            marker = root/'restarted'
            package = root/'new'; package.write_text('#!/bin/sh\nprintf updated > "'+str(marker)+'"\n')
            settings = root/'config.json'; settings.write_text('keep this')
            old = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(90)'])
            try:
                helper = updater.launch_helper(package, target, root/'cache', old.pid)
                self.assertIn('exit 99', target.read_text())
                old.terminate(); old.wait(timeout=5)
                self.assertEqual(helper.wait(timeout=15), 0)
                self.assertEqual((root/'cache/install-result.txt').read_text().strip(), 'ok')
                self.assertEqual(marker.read_text(), 'updated')
                self.assertEqual(settings.read_text(), 'keep this')
                self.assertFalse(Path(str(target)+'.update-old').exists())
            finally:
                if old.poll() is None: old.kill(); old.wait()

    @unittest.skipUnless(sys.platform == 'linux', 'Linux helper rollback')
    def test_linux_install_failure_keeps_previous_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'Companion'
            target.write_text('#!/bin/sh\nexit 0\n');target.chmod(0o755)
            old=subprocess.Popen([sys.executable,'-c','import time;time.sleep(90)'])
            try:
                helper=updater.launch_helper(root/'missing-download',target,root/'cache',old.pid)
                old.terminate();old.wait(timeout=5)
                self.assertNotEqual(helper.wait(timeout=15),0)
                self.assertEqual(target.read_text(),'#!/bin/sh\nexit 0\n')
                self.assertIn('failed',(root/'cache/install-result.txt').read_text())
            finally:
                if old.poll() is None:old.kill();old.wait()
