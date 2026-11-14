"""Qt desktop companion. Network polling stays off the GUI thread."""
import copy
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QScrollArea,QDialog,QComboBox,QLineEdit,QCheckBox,QDialogButtonBox,QMessageBox)
import vrchat_companion as core
import avatar_mapping as mapping
from measurement_format import format_measurement

STYLE = """
QWidget { background:#111416; color:#ecefee; font-family: 'Segoe UI', 'Inter', sans-serif; font-size:14px; }
QLabel { background:transparent; }
QLabel#brand { font-size:25px; font-weight:700; }
QLabel#heading { font-size:30px; font-weight:700; }
QLabel#muted { color:#99a4a4; }
QLabel#eyebrow { color:#c8b58c; font-size:11px; font-weight:700; }
QFrame#card { background:#1b2023; border:1px solid #2c3438; border-radius:18px; }
QFrame#status { background:#182523; border:1px solid #2b4540; border-radius:16px; }
QPushButton { background:#252d31; border:1px solid #364044; border-radius:10px; padding:10px 16px; font-weight:600; }
QPushButton:hover { background:#354045; border-color:#526268; }
QPushButton:pressed { background:#182023; }
QPushButton#primary { background:#dfc48d; border-color:#dfc48d; color:#201d17; }
QPushButton#primary:hover { background:#f0d8a8; }
QPushButton#subtle { background:transparent; border:0; color:#aeb9b9; }
QPushButton#danger { color:#f6a69c; }
QLineEdit,QComboBox { background:#222a2e; border:1px solid #3b474d; border-radius:10px; padding:11px; selection-background-color:#566c69; }
QLineEdit:focus,QComboBox:focus { border:1px solid #dfc48d; }
QComboBox::drop-down { border:0; width:28px; }
QComboBox QAbstractItemView { background:#222a2e; color:#ecefee; selection-background-color:#3c514d; padding:8px; }
QCheckBox { spacing:10px; background:transparent; }
QCheckBox::indicator { width:19px; height:19px; border:1px solid #53635f; border-radius:6px; background:#222a2e; }
QCheckBox::indicator:checked { background:#dfc48d; border-color:#dfc48d; image:none; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:transparent; width:8px; }
QScrollBar::handle:vertical { background:#3c494c; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
"""


def settings_path():
    if sys.platform=='win32': return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'MidsDenCompanion/config.json'
    if sys.platform=='darwin': return Path.home()/'Library/Application Support/MidsDenCompanion/config.json'
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'mids-den-companion/config.json'


def label(text,role=None):
    widget=QLabel(text)
    if role: widget.setObjectName(role)
    return widget


def button(text,callback,role=None):
    widget=QPushButton(text)
    if role: widget.setObjectName(role)
    widget.clicked.connect(callback)
    return widget


class MappingDialog(QDialog):
    MODES={'Current value':'value','Growth ratio':'ratio','Map a range':'range','On / off threshold':'threshold'}
    def __init__(self,owner,index=None,preset=None):
        super().__init__(owner)
        self.owner,self.index,self.profile=owner,index,owner.profile
        self.setWindowTitle('Mapping · Mid’s Den')
        self.setMinimumWidth(620)
        self.setModal(True)
        layout=QVBoxLayout(self);layout.setContentsMargins(30,28,30,28);layout.setSpacing(18)
        layout.addWidget(label('MAKE A CONNECTION','eyebrow'))
        layout.addWidget(label('Your measurement. Your avatar.','brand'))
        grid=QGridLayout();grid.setSpacing(12)
        self.source=QComboBox()
        for source in owner.sources:self.source.addItem(f"{source['name']} · {source['unit']}",source['id'])
        self.target=QComboBox();self.target.setEditable(True)
        self.target.addItem('Eye height','/avatar/eyeheight')
        for address in sorted((owner.discovery or {}).get('parameters',{})):
            self.target.addItem(address.removeprefix(mapping.PREFIX),address)
        self.target.setCurrentIndex(-1);self.target.lineEdit().setPlaceholderText('Search or enter a parameter')
        self.kind=QComboBox();self.kind.addItems(['float','int','bool'])
        self.mode=QComboBox();self.mode.addItems(list(self.MODES))
        for col,title,widget in [(0,'Website measurement',self.source),(1,'Avatar parameter',self.target)]:
            grid.addWidget(label(title,'muted'),0,col);grid.addWidget(widget,1,col)
        grid.addWidget(label('Value type','muted'),2,0);grid.addWidget(self.kind,3,0)
        grid.addWidget(label('Send as','muted'),2,1);grid.addWidget(self.mode,3,1)
        layout.addLayout(grid)
        self.range_box=QWidget();ranges=QGridLayout(self.range_box);ranges.setContentsMargins(0,0,0,0)
        self.fields={}
        for i,(key,title,value) in enumerate([('inputMin','Measurement from','0'),('inputMax','Measurement to','10'),('outputMin','Parameter from','0'),('outputMax','Parameter to','1'),('threshold','Turn on at','1')]):
            field=QLineEdit(value);self.fields[key]=field
            ranges.addWidget(label(title,'muted'),(i//2)*2,i%2);ranges.addWidget(field,(i//2)*2+1,i%2)
        layout.addWidget(self.range_box)
        self.hint=label('','muted');self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.error=label('');self.error.setStyleSheet('color:#f6a69c');self.error.setWordWrap(True);layout.addWidget(self.error)
        actions=QHBoxLayout();self.enabled=QCheckBox('Mapping enabled');self.enabled.setChecked(True);actions.addWidget(self.enabled);actions.addStretch()
        actions.addWidget(button('Cancel',self.reject,'subtle'));actions.addWidget(button('Save mapping',self.save,'primary'));layout.addLayout(actions)
        item=preset or (owner.config['profiles'][self.profile][index] if index is not None else None)
        if item:
            self.source.setCurrentIndex(self.source.findData(item['source']))
            match=self.target.findData(item['target'])
            if match>=0:self.target.setCurrentIndex(match)
            else:self.target.setEditText(item['target'])
            self.kind.setCurrentText(item['kind'])
            self.mode.setCurrentText(next(k for k,v in self.MODES.items() if v==item['mode']))
            self.enabled.setChecked(item.get('enabled',True))
            for key,field in self.fields.items():field.setText(str(item.get(key,field.text())))
        self.target.activated.connect(self.choose_target)
        self.kind.currentTextChanged.connect(self.choose_kind)
        self.mode.currentTextChanged.connect(self.update_fields)
        self.source.currentIndexChanged.connect(self.update_fields)
        self.update_fields()

    def choose_target(self,*_):
        address=self.target.currentData()
        kind=(self.owner.discovery or {}).get('parameters',{}).get(address,'float')
        self.kind.setCurrentText(kind)
        if address=='/avatar/eyeheight':
            self.source.setCurrentIndex(self.source.findData('height'))
            self.mode.setCurrentText('Current value')
        self.choose_kind()

    def choose_kind(self,*_):
        if self.kind.currentText()=='bool':self.mode.setCurrentText('On / off threshold')
        elif self.mode.currentText()=='On / off threshold':self.mode.setCurrentText('Map a range')
        self.update_fields()

    def update_fields(self,*_):
        mode=self.MODES[self.mode.currentText()]
        for index in range(self.range_box.layout().count()):
            widget=self.range_box.layout().itemAt(index).widget()
            row=self.range_box.layout().getItemPosition(index)[0]
            widget.setVisible((mode=='range' and row<4) or (mode=='threshold' and row>=4))
        self.range_box.setVisible(mode in ('range','threshold'))
        source=next((s for s in self.owner.sources if s['id']==self.source.currentData()),{})
        unit=source.get('unit','saved units')
        self.hint.setText({'value':f'Sends the current amount in {unit}.','ratio':'Current ÷ starting amount. 1 means the original size.','range':f'Maps your range in {unit} to the avatar’s range, with limits.','threshold':f'Turns on at or above the amount in {unit}.'}[mode])
        self.adjustSize()

    def save(self):
        try:
            if self.profile!=self.owner.profile:raise ValueError('Avatar changed. Open the mapping again.')
            target=self.target.currentData() if self.target.currentIndex()>=0 and self.target.currentText()==self.target.itemText(self.target.currentIndex()) else self.target.currentText()
            item=mapping.validate_mapping(dict(source=self.source.currentData(),target=target,kind=self.kind.currentText(),mode=self.MODES[self.mode.currentText()],enabled=self.enabled.isChecked(),**{k:f.text() for k,f in self.fields.items()}))
            info=(self.owner.discovery or {}).get('allParameters',{}).get(item['target'])
            if info and (not info['writable'] or info['kind']!=item['kind']):raise ValueError('Choose a writable parameter with the matching type.')
            items=copy.deepcopy(self.owner.config['profiles'].get(self.profile,[]))
            if any(i!=self.index and other['target']==item['target'] for i,other in enumerate(items)):raise ValueError('This parameter already has a mapping.')
            if self.index is None:items.append(item)
            else:items[self.index]=item
            with self.owner.lock:self.owner.config['profiles'][self.profile]=items
            self.owner.persist();self.owner.refresh_cards();self.accept()
        except (ValueError,OSError) as error:self.error.setText(str(error))


class CompanionWindow(QMainWindow):
    def __init__(self,auto_start=True):
        super().__init__()
        self.setWindowTitle('Mid’s Den · Companion');self.resize(1000,720);self.setMinimumSize(820,580)
        self.events=queue.Queue();self.lock=threading.Lock();self.stop_event=threading.Event();self.worker=None
        self.sources=[];self.discovery=None;self.profile='manual';self.dialog=None
        try:self.config=core.load_config(settings_path())
        except (OSError,ValueError):self.config={'serverUrl':core.DEFAULT_URL,'oscHost':'127.0.0.1','oscPort':9000,'oscQueryPort':9001}
        mapping.migrate_profiles(self.config)
        body=QWidget();self.setCentralWidget(body);outer=QVBoxLayout(body);outer.setContentsMargins(34,28,34,24);outer.setSpacing(24)
        header=QHBoxLayout();brand=QVBoxLayout();brand.addWidget(label('MID’S DEN','eyebrow'));brand.addWidget(label('Companion','brand'));header.addLayout(brand);header.addStretch()
        header.addWidget(button('Connection settings',self.settings,'subtle'));self.pause=button('Pause',self.toggle_run);header.addWidget(self.pause);outer.addLayout(header)
        status=QFrame();status.setObjectName('status');sl=QHBoxLayout(status);sl.setContentsMargins(20,18,20,18)
        connection=QVBoxLayout();self.connection=label('●  Looking for VRChat');self.connection.setStyleSheet('font-weight:600;color:#9cceba');connection.addWidget(self.connection)
        self.profile_label=label('Enable OSC in VRChat to discover your avatar.','muted');connection.addWidget(self.profile_label);sl.addLayout(connection);sl.addStretch()
        self.measure_count=label('0 measurements','muted');sl.addWidget(self.measure_count);outer.addWidget(status)
        heading=QHBoxLayout();titles=QVBoxLayout();titles.addWidget(label('Bring your growth to life.','heading'));titles.addWidget(label('Connect measurements to your avatar.','muted'));heading.addLayout(titles);heading.addStretch();outer.addLayout(heading)
        tools=QHBoxLayout();tools.addWidget(label('YOUR MAPPINGS','eyebrow'));tools.addStretch();tools.addWidget(button('+ Eye height',self.add_eye_height));tools.addWidget(button('+ New mapping',self.new_mapping,'primary'));outer.addLayout(tools)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.cards=QWidget();self.card_layout=QVBoxLayout(self.cards);self.card_layout.setContentsMargins(0,0,8,0);self.card_layout.setSpacing(12);self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop);scroll.setWidget(self.cards);outer.addWidget(scroll,1)
        footer=QHBoxLayout();self.status=label('Ready','muted');footer.addWidget(self.status);footer.addStretch();footer.addWidget(label('Updates every 5 seconds','muted'));outer.addLayout(footer)
        self.refresh_cards();self.timer=QTimer(self);self.timer.timeout.connect(self.drain);self.timer.start(100)
        if auto_start:self.start()

    def persist(self):
        with self.lock:core.save_config(self.config,settings_path())

    def refresh_cards(self):
        while self.card_layout.count():
            item=self.card_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        sources={s['id']:s for s in self.sources}
        items=self.config['profiles'].get(self.profile,[])
        if not items:
            empty=QFrame();empty.setObjectName('card');layout=QVBoxLayout(empty);layout.setContentsMargins(28,30,28,30);layout.addWidget(label('Your next connection starts here.','brand'));layout.addWidget(label('Add a mapping, or start with the eye-height preset.','muted'));self.card_layout.addWidget(empty)
        for index,item in enumerate(items):
            card=QFrame();card.setObjectName('card');row=QHBoxLayout(card);row.setContentsMargins(20,18,20,18);row.setSpacing(18)
            enabled=QCheckBox();enabled.setChecked(item.get('enabled',True));enabled.setToolTip('Enable mapping');enabled.toggled.connect(lambda checked,i=index:self.enable_mapping(i,checked));row.addWidget(enabled)
            source=sources.get(item['source'],{});left=QVBoxLayout();left.addWidget(label(source.get('name','Height' if item['source']=='height' else item['source'])))
            left.addWidget(label(format_measurement(source['value'],source['unit']) if source else 'Waiting for website','muted'));row.addLayout(left,1)
            arrow=label('→');arrow.setStyleSheet('font-size:24px;color:#c8b58c');row.addWidget(arrow)
            right=QVBoxLayout();target='Eye height' if item['target']=='/avatar/eyeheight' else item['target'].removeprefix(mapping.PREFIX);name=label(target);name.setWordWrap(True);right.addWidget(name)
            modes={'value':'Current value','ratio':'Growth ratio','range':'Mapped range','threshold':'On / off threshold'};right.addWidget(label(modes[item['mode']],'muted'));row.addLayout(right,2)
            row.addWidget(button('Edit',lambda _=False,i=index:self.edit_mapping(i),'subtle'));row.addWidget(button('×',lambda _=False,i=index:self.remove_mapping(i),'subtle'));self.card_layout.addWidget(card)

    def enable_mapping(self,index,checked):
        try:
            with self.lock:self.config['profiles'][self.profile][index]['enabled']=checked
            self.persist()
        except OSError as error:self.status.setText(str(error))

    def new_mapping(self):self.open_editor()
    def edit_mapping(self,index):self.open_editor(index)
    def open_editor(self,index=None,preset=None):
        if self.dialog:self.dialog.close()
        self.dialog=MappingDialog(self,index,preset);self.dialog.show()
    def add_eye_height(self):
        items=self.config['profiles'].get(self.profile,[])
        index=next((i for i,item in enumerate(items) if item['target']=='/avatar/eyeheight'),None)
        self.open_editor(index,None if index is not None else mapping.eye_height_preset())
    def remove_mapping(self,index):
        with self.lock:self.config['profiles'][self.profile].pop(index)
        self.persist();self.refresh_cards()

    def settings(self):
        dialog=QDialog(self);dialog.setWindowTitle('Connection settings');dialog.setMinimumWidth(440);layout=QVBoxLayout(dialog);layout.setContentsMargins(28,28,28,28);layout.setSpacing(14)
        layout.addWidget(label('Connect to VRChat','brand'))
        host=QLineEdit(self.config['oscHost']);port=QLineEdit(str(self.config['oscPort']))
        for title,field in [('VRChat IP address',host),('OSC receive port',port)]:layout.addWidget(label(title,'muted'));layout.addWidget(field)
        error_label=label('');layout.addWidget(error_label)
        def save():
            try:
                address=core.validate_osc_host(host.text());number=int(port.text())
                if not 1<=number<=65535:raise ValueError('Use a port between 1 and 65535.')
                with self.lock:self.config.update(oscHost=address,oscPort=number)
                self.persist();self.discovery=None;dialog.accept()
            except (ValueError,OSError) as error:error_label.setText(str(error))
        layout.addWidget(button('Save connection',save,'primary'));dialog.exec()

    def start(self):
        if self.worker and self.worker.is_alive():QTimer.singleShot(150,self.start);return
        self.persist();self.stop_event=threading.Event();self.worker=threading.Thread(target=self.sync,args=(self.stop_event,),daemon=True);self.worker.start();self.pause.setText('Pause')

    def toggle_run(self):
        if self.worker and self.worker.is_alive() and not self.stop_event.is_set():
            self.stop_event.set();self.pause.setText('Resume');self.connection.setText('Ⅱ  Paused');self.status.setText('Syncing paused')
        else:self.start()

    def drain(self):
        while not self.events.empty():
            value=self.events.get_nowait()
            if self.stop_event.is_set():continue
            if value[0]=='connection':
                self.connection.setText('●  VRChat detected' if value[1] else '○  Waiting for VRChat')
                self.connection.setToolTip('OSCQuery is responding. UDP delivery is not acknowledged.' if value[1] else 'Discovery unavailable. Manual OSC mappings can still send.')
            elif value[0]=='status':self.status.setText(value[1])
            else:
                self.sources,self.discovery=value[1:];profile=mapping.profile_key(self.discovery)
                if profile!=self.profile and self.dialog:self.dialog.close();self.dialog=None
                self.profile=profile;self.profile_label.setText('Avatar · '+profile[-8:] if profile!='manual' else 'Shared mappings · avatar discovery unavailable')
                self.measure_count.setText(f'{len(self.sources)} measurements');self.refresh_cards()

    def closeEvent(self,event):
        self.stop_event.set();self.timer.stop();event.accept()

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


def main():
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    app.setApplicationName('Mid’s Den Companion')
    if '--self-test' in sys.argv:
        import ssl,zeroconf
        ssl.create_default_context();core.encode_eyeheight_packet(1000)
        window=CompanionWindow(auto_start=False);window.show();app.processEvents()
        window.open_editor(preset=mapping.eye_height_preset());app.processEvents();window.dialog.close();window.close()
        Path(os.environ['MIDSDEN_SMOKE_REPORT']).write_text(json.dumps({'status':'ok','platform':sys.platform}))
        return
    window=CompanionWindow();window.show();sys.exit(app.exec())

if __name__=='__main__':main()
