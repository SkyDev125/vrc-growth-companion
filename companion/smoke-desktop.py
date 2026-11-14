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
