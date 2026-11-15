"""Retry transient disk-image contention on native build runners."""
import subprocess
import sys
import time


def run_image_tool(arguments, *, force_detach=False):
    for attempt in range(4):
        result=subprocess.run(['hdiutil',*arguments],capture_output=True,text=True,timeout=120)
        if result.returncode==0:
            if result.stdout:print(result.stdout,end='')
            return result
        busy='resource busy' in result.stderr.lower()
        if not busy:
            print(result.stderr,file=sys.stderr)
            result.check_returncode()
        if attempt<3:
            print('Disk image is temporarily busy; retrying.')
            time.sleep(attempt+1)
    if force_detach and arguments[0]=='detach':
        # Only used for the test-owned image after its app process has exited.
        return subprocess.run(['hdiutil','detach','-force',*arguments[1:]],check=True,timeout=120)
    print(result.stderr,file=sys.stderr)
    result.check_returncode()
