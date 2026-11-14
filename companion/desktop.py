"""Native desktop interface; all network work runs outside Tk's UI thread."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import vrchat_companion as core


def settings_path():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'MidsDenCompanion/config.json'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/MidsDenCompanion/config.json'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'mids-den-companion/config.json'


class CompanionWindow:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        root.title("Mid's Den Companion")
        root.geometry('470x380')
        root.minsize(440, 360)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="Mid's Den", font=('', 22, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='VRChat height companion').pack(anchor='w', pady=(0, 20))
        try:
            self.config = core.load_config(settings_path())
        except (OSError, ValueError, json.JSONDecodeError):
            self.config = {'serverUrl': core.DEFAULT_URL, 'oscHost': core.DEFAULT_OSC_HOST, 'oscPort': 9000, 'oscQueryPort': 9001}
        self.host = tk.StringVar(value=self.config['oscHost'])
        self.port = tk.StringVar(value=str(self.config['oscPort']))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        for label, value in [('VRChat IP', self.host), ('OSC port', self.port)]:
            field = ttk.Frame(row)
            field.pack(side='left', fill='x', expand=True, padx=(0, 10))
            ttk.Label(field, text=label).pack(anchor='w')
            ttk.Entry(field, textvariable=value).pack(fill='x', pady=5)
        self.status = tk.StringVar(value='Ready')
        ttk.Label(frame, textvariable=self.status, wraplength=410).pack(anchor='w', pady=20)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x')
        self.toggle = ttk.Button(buttons, text='Start', command=self.toggle_run)
        self.toggle.pack(side='left')
        if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
            ttk.Button(buttons, text='Install shortcut', command=self.install).pack(side='right')
        ttk.Label(frame, text='Keep this window open and enable OSC in VRChat.\nUDP sending does not confirm receipt in the game.', wraplength=410).pack(anchor='w', pady=16)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.drain)
        self.start()

    def start(self):
        if self.worker and self.worker.is_alive():
            self.status.set('Stopping… please wait before restarting.')
            return
        try:
            host = core.validate_osc_host(self.host.get())
            port = int(self.port.get())
            if not 1 <= port <= 65535:
                raise ValueError('Port must be between 1 and 65535.')
            self.config.update(oscHost=host, oscPort=port)
            core.save_config(self.config, settings_path())
        except (OSError, ValueError) as error:
            messagebox.showerror('Settings', str(error))
            return
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self.sync, args=(dict(self.config), self.stop_event), daemon=True)
        self.worker.start()
        self.toggle.configure(text='Stop')

    def sync(self, config, stop):
        while not stop.is_set():
            try:
                height = core.fetch_current_height(config)
                if stop.is_set():
                    break
                if height is None:
                    self.events.put('Set your starting height on the website.')
                else:
                    core.send_eyeheight(height, config['oscPort'], config['oscHost'])
                    self.events.put(f"Sending {height:g} m to {config['oscHost']}:{config['oscPort']}")
            except (OSError, ValueError, RuntimeError) as error:
                self.events.put(str(error))
            stop.wait(core.DEFAULT_POLL_SECONDS)

    def toggle_run(self):
        if self.worker and self.worker.is_alive() and not self.stop_event.is_set():
            self.stop_event.set()
            self.toggle.configure(text='Start')
            self.status.set('Stopped')
        else:
            self.start()

    def drain(self):
        while not self.events.empty():
            value = self.events.get_nowait()
            if not self.stop_event.is_set():
                self.status.set(value)
        self.root.after(100, self.drain)

    def install(self):
        try:
            source = Path(sys.executable)
            if sys.platform == 'win32':
                target = settings_path().parent / 'MidsDenCompanion.exe'
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
                # Paths pass through environment variables rather than shell interpolation.
                env = dict(os.environ, MIDSDEN_INSTALL_TARGET=str(target))
                script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Mids Den Companion.lnk'));$s.TargetPath=$env:MIDSDEN_INSTALL_TARGET;$s.Save()"
                subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], env=env, check=True, creationflags=0x08000000)
            else:
                target = Path.home() / '.local/bin/mids-den-companion'
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
                target.chmod(0o755)
                shortcut = Path.home() / '.local/share/applications/mids-den-companion.desktop'
                shortcut.parent.mkdir(parents=True, exist_ok=True)
                shortcut.write_text(f'[Desktop Entry]\nType=Application\nName=Mid’s Den Companion\nExec="{target}"\nTerminal=false\nCategories=Game;\n')
            messagebox.showinfo('Installed', 'The companion is installed and its shortcut is ready. Settings are saved automatically.')
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror('Installation', str(error))

    def close(self):
        self.stop_event.set()
        self.root.destroy()


def main():
    if '--self-test' in sys.argv:
        import ssl
        core.encode_eyeheight_packet(1000)
        core.validate_osc_host('127.0.0.1')
        ssl.create_default_context()
        root = tk.Tk()
        root.withdraw()
        root.update()
        root.destroy()
        Path(os.environ['MIDSDEN_SMOKE_REPORT']).write_text(json.dumps({'status': 'ok', 'platform': sys.platform}), encoding='utf-8')
        return
    root = tk.Tk()
    CompanionWindow(root)
    root.mainloop()


if __name__ == '__main__':
    main()
