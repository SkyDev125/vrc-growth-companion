"""Native desktop interface; all network work runs outside Tk's UI thread."""
import copy
import time
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
import avatar_mapping as mapping
from measurement_format import format_measurement


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
        root.geometry('980x800')
        root.minsize(820, 800)
        self.theme()
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="Mid's Den", font=('', 22, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='VRChat companion').pack(anchor='w', pady=(0, 20))
        try:
            self.config = core.load_config(settings_path())
        except (OSError, ValueError, json.JSONDecodeError):
            self.config = {'serverUrl': core.DEFAULT_URL, 'oscHost': core.DEFAULT_OSC_HOST, 'oscPort': 9000, 'oscQueryPort': 9001}
        self.lock = threading.Lock()
        self.profile = 'manual'
        self.sources = []
        self.discovery = None
        self.config.setdefault('profiles', {})
        mapping.migrate_profiles(self.config)
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
        ttk.Label(frame, textvariable=self.status, style='Status.TLabel', wraplength=880).pack(anchor='w', pady=(16,8))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x')
        self.toggle = ttk.Button(buttons, text='Resume', command=self.toggle_run)
        self.toggle.pack(side='left')
        if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
            ttk.Button(buttons, text='Install shortcut', command=self.install).pack(side='right')
        self.connection = tk.StringVar(value='●  Looking for VRChat…')
        ttk.Label(frame,textvariable=self.connection,style='Connection.TLabel').pack(anchor='w',pady=(12,4))
        self.build_mappings(frame)
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
        self.worker = threading.Thread(target=self.sync, args=(self.stop_event,), daemon=True)
        self.worker.start()
        self.toggle.configure(text='Pause')

    def build_mappings(self, frame):
        toolbar=ttk.Frame(frame)
        toolbar.pack(fill='x',pady=(14,10))
        ttk.Label(toolbar,text='Your mappings',style='Title.TLabel').pack(side='left')
        ttk.Button(toolbar,text='+ Eye height preset',command=self.add_eye_height).pack(side='right')
        self.profile_label = tk.StringVar(value='Manual / shared mappings')
        ttk.Label(frame, textvariable=self.profile_label, font=('', 12, 'bold')).pack(anchor='w', pady=(16, 6))
        self.table = ttk.Treeview(frame, columns=('source','target','mode'), show='headings', height=2,selectmode='browse')
        for key, title, width in [('source','Measurement',180),('target','Avatar parameter',280),('mode','Mapping',120)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width)
        self.table.pack(fill='both', expand=True)
        self.table.bind('<<TreeviewSelect>>', self.edit_selected)
        ttk.Separator(frame).pack(fill='x',pady=(16,4))
        editor = ttk.Frame(frame)
        editor.pack(fill='x', pady=10)
        self.source = tk.StringVar()
        self.target = tk.StringVar()
        self.kind = tk.StringVar(value='float')
        self.mode = tk.StringVar(value='range')
        self.enabled = tk.BooleanVar(value=True)
        self.source_box = ttk.Combobox(editor, textvariable=self.source, state='readonly')
        self.target_box = ttk.Combobox(editor, textvariable=self.target)
        for col, (title, widget) in enumerate([('Measurement',self.source_box),('Avatar parameter',self.target_box)]):
            ttk.Label(editor, text=title).grid(row=0,column=col,sticky='w')
            widget.grid(row=1,column=col,sticky='ew',padx=(0,8))
            editor.columnconfigure(col,weight=1)
        self.target_box.bind('<<ComboboxSelected>>', self.choose_target)
        self.source_box.bind('<<ComboboxSelected>>', self.update_fields)
        types = ttk.Combobox(editor, textvariable=self.kind, values=['float','int','bool'], state='readonly',width=9)
        modes = ttk.Combobox(editor, textvariable=self.mode, values=['value','ratio','range','threshold'], state='readonly',width=12)
        ttk.Label(editor,text='Type').grid(row=2,column=0,sticky='w',pady=(8,0))
        types.grid(row=3,column=0,sticky='w')
        ttk.Label(editor,text='Mapping').grid(row=2,column=1,sticky='w',pady=(8,0))
        modes.grid(row=3,column=1,sticky='w')
        types.bind('<<ComboboxSelected>>',self.choose_kind)
        modes.bind('<<ComboboxSelected>>',self.update_fields)
        self.fields = ttk.Frame(frame)
        self.fields.pack(fill='x')
        self.numbers = {key:tk.StringVar(value=value) for key,value in [('inputMin','0'),('inputMax','10'),('outputMin','0'),('outputMax','1'),('threshold','1')]}
        self.hint = tk.StringVar()
        ttk.Label(frame,textvariable=self.hint,wraplength=740).pack(anchor='w',pady=6)
        actions = ttk.Frame(frame)
        actions.pack(fill='x')
        ttk.Button(actions,text='+ New mapping',command=self.new_mapping).pack(side='left')
        ttk.Button(actions,text='Save mapping',style='Accent.TButton',command=self.save_mapping).pack(side='left',padx=8)
        ttk.Button(actions,text='Remove',command=self.remove_mapping).pack(side='left')
        ttk.Checkbutton(actions,text='Enabled',variable=self.enabled).pack(side='right')
        self.update_fields()
        self.refresh_table()

    def persist(self):
        with self.lock:
            core.save_config(self.config, settings_path())

    def theme(self):
        bg, panel, text, muted, gold = '#101412','#1c231f','#eef1e8','#a9b5aa','#dfbf7b'
        self.root.configure(bg=bg)
        style=ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10),background=bg,foreground=text)
        style.configure('TFrame',background=bg)
        style.configure('TLabel',background=bg,foreground=muted)
        style.configure('Title.TLabel',font=('Segoe UI',16,'bold'),foreground=text)
        style.configure('Status.TLabel',foreground=muted)
        style.configure('Connection.TLabel',foreground=gold,font=('Segoe UI',11,'bold'))
        style.configure('TButton',background=panel,foreground=text,padding=(14,9),borderwidth=0)
        style.map('TButton',background=[('active','#303b33')])
        style.configure('Accent.TButton',background=gold,foreground='#151a16')
        style.map('Accent.TButton',background=[('active','#efd49e')])
        style.configure('TEntry',fieldbackground=panel,foreground=text,insertcolor=text,padding=8)
        style.configure('TCombobox',fieldbackground=panel,background=panel,foreground=text,arrowsize=14,padding=7)
        style.map('TCombobox',fieldbackground=[('readonly',panel)],foreground=[('readonly',text)],selectbackground=[('readonly',panel)],selectforeground=[('readonly',text)])
        style.configure('Treeview',background=panel,fieldbackground=panel,foreground=text,rowheight=42,borderwidth=0)
        style.configure('Treeview.Heading',background=bg,foreground=muted,padding=(12,10),relief='flat')
        style.map('Treeview',background=[('selected','#354637')],foreground=[('selected',text)])
        style.configure('TCheckbutton',background=bg,foreground=text,padding=6)
        self.root.option_add('*TCombobox*Listbox.background',panel)
        self.root.option_add('*TCombobox*Listbox.foreground',text)
        self.root.option_add('*TCombobox*Listbox.selectBackground','#354637')

    def add_eye_height(self):
        items=copy.deepcopy(self.config['profiles'].get(self.profile,[]))
        existing=next((i for i,item in enumerate(items) if item['target']=='/avatar/eyeheight'),None)
        if existing is None:
            items.append(mapping.eye_height_preset())
            with self.lock: self.config['profiles'][self.profile]=items
            self.persist()
            self.refresh_table()
            existing=len(items)-1
        self.table.selection_set(str(existing))
        self.edit_selected()

    def choose_target(self, _event=None):
        kind = (self.discovery or {}).get('parameters',{}).get(self.target.get())
        if kind: self.kind.set(kind)
        self.choose_kind()

    def choose_kind(self, _event=None):
        if self.kind.get() == 'bool': self.mode.set('threshold')
        elif self.mode.get() == 'threshold': self.mode.set('range')
        self.update_fields()

    def update_fields(self, _event=None):
        for child in self.fields.winfo_children(): child.destroy()
        source = next((s for s in self.sources if self.source_label(s)==self.source.get()),{})
        unit = source.get('unit','units')
        mode = self.mode.get()
        keys = [('inputMin',f'From ({unit})'),('inputMax',f'To ({unit})'),('outputMin','OSC from'),('outputMax','OSC to')] if mode=='range' else [('threshold',f'On at ({unit})')] if mode=='threshold' else []
        for col,(key,label) in enumerate(keys):
            ttk.Label(self.fields,text=label).grid(row=0,column=col,sticky='w')
            ttk.Entry(self.fields,textvariable=self.numbers[key],width=14).grid(row=1,column=col,sticky='ew',padx=(0,8))
            self.fields.columnconfigure(col,weight=1)
        self.hint.set({'value':f'Sends the current value in {unit}.','ratio':'Current ÷ original; 1 means the starting size.','range':'Maps this measurement range to the OSC range, with limits.','threshold':'On at or above the threshold; off below it.'}[mode])

    @staticmethod
    def source_label(source):
        return f"{source['name']} ({source.get('unit','')})"

    def refresh_table(self):
        self.table.delete(*self.table.get_children())
        names = {s['id']:s['name'] for s in self.sources}
        for index,item in enumerate(self.config['profiles'].get(self.profile,[])):
            self.table.insert('', 'end', iid=str(index), values=(names.get(item['source'],item['source']),('Eye height' if item['target']=='/avatar/eyeheight' else item['target'].removeprefix(mapping.PREFIX)),item['mode'] if item.get('enabled',True) else 'Disabled'))

    def new_mapping(self):
        self.table.selection_remove(*self.table.selection())
        self.target.set('')
        self.enabled.set(True)

    def edit_selected(self, _event=None):
        selected = self.table.selection()
        if not selected: return
        items = self.config['profiles'].get(self.profile,[])
        if int(selected[0]) >= len(items): return
        item = items[int(selected[0])]
        source = next((s for s in self.sources if s['id']==item['source']),None)
        self.source.set(self.source_label(source) if source else '')
        for key in ('target','kind','mode'): getattr(self,key).set(item[key])
        self.enabled.set(item.get('enabled',True))
        for key,var in self.numbers.items(): var.set(str(item.get(key,var.get())))
        self.update_fields()

    def save_mapping(self):
        try:
            source = next((s for s in self.sources if self.source_label(s)==self.source.get()),None)
            item = mapping.validate_mapping(dict(source=source['id'] if source else '',target=self.target.get(),kind=self.kind.get(),mode=self.mode.get(),enabled=self.enabled.get(),**{k:v.get() for k,v in self.numbers.items()}))
            info = (self.discovery or {}).get('allParameters',{}).get(item['target'])
            if info and (not info['writable'] or info['kind'] != item['kind']):
                raise ValueError('This parameter is read-only or has a different type.')
            items = copy.deepcopy(self.config['profiles'].get(self.profile,[]))
            selected = self.table.selection()
            index = int(selected[0]) if selected else len(items)
            if any(i!=index and other['target']==item['target'] for i,other in enumerate(items)):
                raise ValueError('This parameter already has a mapping.')
            if index<len(items): items[index]=item
            else: items.append(item)
            with self.lock: self.config['profiles'][self.profile]=items
            self.persist()
            self.refresh_table()
        except (ValueError,OSError) as error: messagebox.showerror('Mapping',str(error))

    def remove_mapping(self):
        selected = self.table.selection()
        if not selected: return
        with self.lock:
            items = list(self.config['profiles'].get(self.profile,[]))
            del items[int(selected[0])]
            self.config['profiles'][self.profile]=items
        self.persist()
        self.refresh_table()

    def sync(self, stop):
        last_browse = 0
        known_port = None
        while not stop.is_set():
            with self.lock: config = copy.deepcopy(self.config)
            try:
                browse = time.monotonic()-last_browse>30
                discovery = mapping.discover(config,known_port,browse=browse)
                if browse: last_browse=time.monotonic()
                if discovery: known_port=discovery['queryPort']
                profile = mapping.profile_key(discovery)
                with self.lock:
                    if profile not in self.config['profiles']:
                        self.config['profiles'][profile]=[mapping.eye_height_preset()]
                        core.save_config(self.config,settings_path())
                    config=copy.deepcopy(self.config)
                self.events.put(('connection',bool(discovery)))
                sources = mapping.fetch_measurements(config)
                self.events.put(('data',sources,discovery))
                sent, skipped = 0, 0
                source_map = {s['id']:s for s in sources}
                for item in config.get('profiles',{}).get(profile,[]):
                    if stop.is_set(): break
                    if not item.get('enabled',True): continue
                    if not mapping.can_send(item,source_map,discovery):
                        skipped+=1
                        continue
                    try:
                        mapping.send_mapping(config,item,source_map[item['source']])
                        sent+=1
                    except (OSError,ValueError,KeyError,TypeError,OverflowError): skipped+=1
                self.events.put(('status',f"Sending to {config['oscHost']}:{config['oscPort']} · {sent} mappings"+(f' · {skipped} unavailable' if skipped else '')))
            except (OSError,ValueError,RuntimeError) as error:
                self.events.put(('status',str(error)))
            stop.wait(core.DEFAULT_POLL_SECONDS)

    def toggle_run(self):
        if self.worker and self.worker.is_alive() and not self.stop_event.is_set():
            self.stop_event.set()
            self.toggle.configure(text='Resume')
            self.status.set('Paused')
            self.connection.set('○  Paused')
        else:
            self.start()

    def drain(self):
        while not self.events.empty():
            value = self.events.get_nowait()
            if self.stop_event.is_set(): continue
            if value[0]=='connection':
                self.connection.set('●  VRChat detected · OSCQuery responding' if value[1] else '○  VRChat not detected · manual OSC available')
            elif value[0]=='status': self.status.set(value[1])
            else:
                previous_labels = [self.source_label(s) for s in self.sources]
                self.sources,self.discovery = value[1:]
                profile = mapping.profile_key(self.discovery)
                changed = profile != self.profile
                self.profile = profile
                self.profile_label.set('Avatar mappings · '+profile[-8:] if profile!='manual' else 'Manual / shared mappings · discovery unavailable' if not self.discovery else 'Manual / shared mappings · avatar ID unavailable')
                self.source_box.configure(values=[self.source_label(s) for s in self.sources])
                if not self.source.get() and self.sources: self.source.set(self.source_label(self.sources[0]))
                self.target_box.configure(values=sorted((self.discovery or {}).get('parameters',{})))
                if changed:
                    self.new_mapping()
                    self.refresh_table()
                elif not self.table.selection(): self.refresh_table()
                if changed or previous_labels != [self.source_label(s) for s in self.sources]:
                    self.update_fields()
        self.root.after(100,self.drain)

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
        import zeroconf
        assert mapping.mapped_value({'source':'height','target':'Test','kind':'float','mode':'ratio'}, {'value':4,'originalValue':2}) == 2
        assert mapping.parse_tree({'FULL_PATH':'/avatar/parameters/Test','TYPE':'f','ACCESS':3})['parameters']
        mapping.encode_parameter('Test','bool',True)
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
