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
from PySide6.QtGui import QFont,QPainter,QPen,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QScrollArea,QDialog,QComboBox,QLineEdit,QCheckBox,QDialogButtonBox,QMessageBox,QCompleter,QStyleOptionButton,QStyle)
import vrchat_companion as core
import avatar_mapping as mapping
from measurement_format import format_measurement

STYLE = """
QWidget { background:#111416; color:#ecefee; font-family: 'Segoe UI', 'Inter', 'Noto Sans', 'DejaVu Sans', sans-serif; font-size:13px; }
QLabel { background:transparent; }
QLabel#brand { font-size:19px; font-weight:700; }
QLabel#heading { font-size:30px; font-weight:700; }
QLabel#muted { color:#99a4a4; }
QLabel#eyebrow { color:#c8b58c; font-size:11px; font-weight:700; }
QFrame#card { background:#1b2023; border:1px solid #2c3438; border-radius:10px; }
QFrame#status { background:#182523; border:1px solid #2b4540; border-radius:16px; }
QPushButton { background:#252d31; border:1px solid #364044; border-radius:10px; padding:7px 12px; font-weight:600; }
QPushButton:hover { background:#354045; border-color:#526268; }
QPushButton:pressed { background:#182023; }
QPushButton#primary { background:#dfc48d; border-color:#dfc48d; color:#201d17; }
QPushButton#primary:hover { background:#f0d8a8; }
QPushButton#subtle { background:transparent; border:0; color:#aeb9b9; }
QPushButton#danger { color:#f6a69c; }
QLineEdit,QComboBox { background:#222a2e; border:1px solid #3b474d; border-radius:10px; padding:7px 10px; selection-background-color:#566c69; }
QLineEdit:focus,QComboBox:focus { border:1px solid #dfc48d; }
QComboBox::drop-down { border:0; width:28px; }
QComboBox QLineEdit { padding:0; border:0; background:transparent; }
QPushButton#subtle:hover { background:#252d31; color:#ecefee; }
QPushButton#danger:hover { background:#3a2224; color:#f6a69c; }
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


class VisibleComboBox(QComboBox):
    """Keep the browse affordance visible on dark themes on every OS."""
    def wheelEvent(self,event):
        if self.view().isVisible():super().wheelEvent(event)
        else:event.ignore()

    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#bac7c6'),1.6))
        x,y=self.width()-18,self.height()//2
        painter.drawLine(x-4,y-2,x,y+2)
        painter.drawLine(x,y+2,x+4,y-2)


class VisibleCheckBox(QCheckBox):
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.isChecked():return
        option=QStyleOptionButton();self.initStyleOption(option)
        rect=self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator,option,self)
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#201d17'),2))
        x,y=rect.center().x(),rect.center().y()
        painter.drawLine(x-5,y,x-1,y+4);painter.drawLine(x-1,y+4,x+6,y-4)


class MappingDialog(QDialog):
    MODES={'Current value':'value','Growth ratio':'ratio','Map a range':'range','On / off threshold':'threshold'}
    def __init__(self,owner,index=None,preset=None):
        super().__init__(owner)
        self.owner,self.index,self.profile=owner,index,owner.profile
        self.setWindowTitle('Mapping · Mid’s Den')
        self.setFixedWidth(600)
        self.setModal(True)
        layout=QVBoxLayout(self);layout.setContentsMargins(22,20,22,20);layout.setSpacing(12)
        layout.addWidget(label('Edit mapping' if index is not None else 'New mapping','brand'))
        grid=QGridLayout();grid.setHorizontalSpacing(12);grid.setVerticalSpacing(6);grid.setColumnStretch(0,1);grid.setColumnStretch(1,2)
        self.source=VisibleComboBox()
        for source in owner.sources:self.source.addItem(f"{source['name']} · {source['unit']}",source['id'])
        self.target=VisibleComboBox();self.target.setEditable(True)
        self.target.addItem('Eye height','/avatar/eyeheight')
        available=(owner.discovery or {}).get('allParameters') or {address:{'kind':kind,'writable':True} for address,kind in (owner.discovery or {}).get('parameters',{}).items()}
        for address,info in sorted(available.items()):
            self.target.addItem(address.removeprefix(mapping.PREFIX),address)
            entry=self.target.model().item(self.target.count()-1)
            usable=info.get('writable') and info.get('kind') in ('float','int','bool')
            entry.setEnabled(bool(usable))
            entry.setToolTip(address+' · '+str(info.get('kind') or 'unsupported type')+('' if usable else ' · read-only or unsupported'))
        for combo in (self.source,self.target):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(14)
        self.target.setCurrentIndex(-1);self.target.lineEdit().setPlaceholderText('Search or enter a parameter')
        self.target.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.target.setMaxVisibleItems(12)
        self.target.view().setMaximumHeight(300)
        completer=QCompleter(self.target.model(),self.target)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.target.setCompleter(completer)
        completer.activated.connect(self.complete_target)
        target_field=QWidget();target_layout=QHBoxLayout(target_field);target_layout.setContentsMargins(0,0,0,0);target_layout.setSpacing(6)
        target_layout.addWidget(self.target,1)
        self.browse=button('All ▾',self.target.showPopup)
        self.browse.setToolTip('Browse all available parameters')
        target_layout.addWidget(self.browse)

        self.kind=VisibleComboBox();self.kind.addItems(['float','int','bool'])
        self.mode=VisibleComboBox();self.mode.addItems(list(self.MODES))
        for col,title,widget in [(0,'Website measurement',self.source),(1,f"Avatar parameter · {len(available)} discovered",target_field)]:
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
        self.error=label('');self.error.setStyleSheet('color:#f6a69c');self.error.setWordWrap(True);self.error.hide();layout.addWidget(self.error)
        actions=QHBoxLayout();self.enabled=VisibleCheckBox('Mapping enabled');self.enabled.setChecked(True);actions.addWidget(self.enabled);actions.addStretch()
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

    def complete_target(self,text):
        index=self.target.findText(text)
        if index>=0:
            self.target.setCurrentIndex(index)
            self.choose_target()

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
            index=self.target.findText(self.target.currentText())
            target=self.target.itemData(index) if index>=0 else self.target.currentText()
            item=mapping.validate_mapping(dict(source=self.source.currentData(),target=target,kind=self.kind.currentText(),mode=self.MODES[self.mode.currentText()],enabled=self.enabled.isChecked(),**{k:f.text() for k,f in self.fields.items()}))
            info=(self.owner.discovery or {}).get('allParameters',{}).get(item['target'])
            if info and (not info['writable'] or info['kind']!=item['kind']):raise ValueError('Choose a writable parameter with the matching type.')
            items=copy.deepcopy(self.owner.config['profiles'].get(self.profile,[]))
            if any(i!=self.index and other['target']==item['target'] for i,other in enumerate(items)):raise ValueError('This parameter already has a mapping.')
            if self.index is None:items.append(item)
            else:items[self.index]=item
            with self.owner.lock:self.owner.config['profiles'][self.profile]=items
            self.owner.persist();self.owner.refresh_cards();self.accept()
        except (ValueError,OSError) as error:
            self.error.setText(str(error));self.error.show();self.adjustSize()


class CompanionWindow(QMainWindow):
    def __init__(self,auto_start=True):
        super().__init__()
        self.setWindowTitle('Mid’s Den · Companion');self.resize(860,430);self.setMinimumSize(760,360)
        self.events=queue.Queue();self.lock=threading.Lock();self.stop_event=threading.Event();self.worker=None
        self.sources=[];self.discovery=None;self.profile='manual';self.dialog=None;self.resend_generation=0
        try:self.config=core.load_config(settings_path())
        except (OSError,ValueError):self.config={'serverUrl':core.DEFAULT_URL,'oscHost':'127.0.0.1','oscPort':9000,'oscQueryPort':9001}
        mapping.migrate_profiles(self.config)
        body=QWidget();self.setCentralWidget(body);outer=QVBoxLayout(body);outer.setContentsMargins(20,16,20,14);outer.setSpacing(12)
        header=QHBoxLayout();brand=QVBoxLayout();brand.addWidget(label('Mid’s Den · Companion','brand'));header.addLayout(brand);header.addStretch()
        header.addWidget(button('Resend',self.resend,'subtle'));header.addWidget(button('Connection settings',self.settings,'subtle'));self.pause=button('Pause',self.toggle_run);header.addWidget(self.pause);outer.addLayout(header)
        status=QFrame();status.setObjectName('status');sl=QHBoxLayout(status);sl.setContentsMargins(12,10,12,10)
        connection=QHBoxLayout();connection.setSpacing(16);self.connection=label('●  Looking for VRChat');self.connection.setStyleSheet('font-weight:600;color:#9cceba');connection.addWidget(self.connection)
        self.profile_label=label('Enable OSC in VRChat','muted');connection.addWidget(self.profile_label);sl.addLayout(connection);sl.addStretch()
        self.measure_count=label('0 measurements','muted');sl.addWidget(self.measure_count);outer.addWidget(status)
        tools=QHBoxLayout();tools.addWidget(label('YOUR MAPPINGS','eyebrow'));tools.addStretch();tools.addWidget(button('+ Eye height',self.add_eye_height));tools.addWidget(button('+ New mapping',self.new_mapping,'primary'));outer.addLayout(tools)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.cards=QWidget();self.card_layout=QVBoxLayout(self.cards);self.card_layout.setContentsMargins(0,0,8,0);self.card_layout.setSpacing(6);self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop);scroll.setWidget(self.cards);outer.addWidget(scroll,1)
        footer=QHBoxLayout();self.status=label('Ready','muted');footer.addWidget(self.status);footer.addStretch();footer.addWidget(label('Checks every 5s · sends changes only','muted'));outer.addLayout(footer)
        self.refresh_cards();self.timer=QTimer(self);self.timer.timeout.connect(self.drain);self.timer.start(100)
        if auto_start:self.start()

    def persist(self):
        with self.lock:core.save_config(self.config,settings_path())

    def refresh_cards(self):
        signature=(self.profile,json.dumps(self.config['profiles'].get(self.profile,[]),sort_keys=True),tuple((s['id'],s['name'],s['unit']) for s in self.sources))
        if getattr(self,'_cards_signature',None)==signature:
            sources={s['id']:s for s in self.sources}
            for source_id,widget in self._value_labels:
                source=sources.get(source_id)
                widget.setText(format_measurement(source['value'],source['unit']) if source else 'Waiting for website')
            for item,widget in self._output_labels:self.update_output(item,widget,sources)
            return
        self._cards_signature=signature
        self._value_labels=[]
        self._output_labels=[]
        while self.card_layout.count():
            item=self.card_layout.takeAt(0)
            if item.widget():
                item.widget().hide();item.widget().deleteLater()
        sources={s['id']:s for s in self.sources}
        items=self.config['profiles'].get(self.profile,[])
        if not items:
            empty=QFrame();empty.setObjectName('card');layout=QVBoxLayout(empty);layout.setContentsMargins(18,20,18,20);layout.addWidget(label('No mappings yet','brand'));layout.addWidget(label('Add a mapping or choose the eye-height preset.','muted'));self.card_layout.addWidget(empty)
        for index,item in enumerate(items):
            card=QFrame();card.setObjectName('card');row=QHBoxLayout(card);row.setContentsMargins(12,9,12,9);row.setSpacing(12)
            enabled=VisibleCheckBox('On' if item.get('enabled',True) else 'Off');enabled.setChecked(item.get('enabled',True));enabled.setToolTip('Enable mapping');enabled.toggled.connect(lambda checked,i=index:self.enable_mapping(i,checked));row.addWidget(enabled)
            source=sources.get(item['source'],{});left=QVBoxLayout();left.addWidget(label(source.get('name','Height' if item['source']=='height' else item['source'])))
            value_label=label(format_measurement(source['value'],source['unit']) if source else 'Waiting for website','muted');self._value_labels.append((item['source'],value_label));left.addWidget(value_label);row.addLayout(left,1)
            arrow=label('→');arrow.setStyleSheet('font-size:18px;color:#c8b58c');row.addWidget(arrow)
            right=QVBoxLayout();target='Eye height' if item['target']=='/avatar/eyeheight' else item['target'].removeprefix(mapping.PREFIX);name=label(target);name.setWordWrap(True);name.setToolTip(item['target']);right.addWidget(name)
            modes={'value':'Current value','ratio':'Growth ratio','range':'Mapped range','threshold':'On / off threshold'};description=modes[item['mode']]+' · '+item['kind'];right.addWidget(label(description,'muted'));row.addLayout(right,2)
            output=label('','muted');output.setMinimumWidth(80);output.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter);output.setToolTip('Calculated OSC output. UDP delivery is not acknowledged.');self._output_labels.append((item,output));self.update_output(item,output,sources);row.addWidget(output)
            row.addWidget(button('Edit',lambda _=False,i=index:self.edit_mapping(i),'subtle'));remove=button('×',lambda _=False,i=index:self.remove_mapping(i),'danger');remove.setToolTip('Remove mapping');row.addWidget(remove);self.card_layout.addWidget(card)

    def update_output(self,item,widget,sources):
        if not item.get('enabled',True):widget.setText('Paused');return
        if item['source'] not in sources:widget.setText('Waiting');return
        if not mapping.can_send(item,sources,self.discovery):widget.setText('Unavailable');return
        try:
            value=mapping.mapped_value(item,sources[item['source']])
            widget.setText(('On' if value else 'Off') if isinstance(value,bool) else f'{value:.4g}')
        except (ValueError,KeyError,TypeError,OverflowError):widget.setText('Invalid')

    def enable_mapping(self,index,checked):
        try:
            with self.lock:self.config['profiles'][self.profile][index]['enabled']=checked
            self.persist();self.refresh_cards()
        except OSError as error:self.status.setText(str(error))

    def new_mapping(self):self.open_editor()
    def edit_mapping(self,index):self.open_editor(index)
    def open_editor(self,index=None,preset=None):
        if self.dialog:self.dialog.close()
        self.dialog=MappingDialog(self,index,preset)
        active=self.dialog
        self.dialog.finished.connect(lambda _result:self.clear_editor(active))
        self.dialog.show()
    def clear_editor(self,dialog):
        if self.dialog is dialog:self.dialog=None

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
        error_label=label('');error_label.setStyleSheet('color:#f6a69c');error_label.setWordWrap(True);layout.addWidget(error_label)
        def save():
            try:
                address=core.validate_osc_host(host.text());number=int(port.text())
                if not 1<=number<=65535:raise ValueError('Use a port between 1 and 65535.')
                with self.lock:self.config.update(oscHost=address,oscPort=number)
                self.persist();self.discovery=None;dialog.accept()
            except (ValueError,OSError) as error:error_label.setText(str(error))
        layout.addWidget(button('Save connection',save,'primary'));dialog.exec()

    def resend(self):
        with self.lock:self.resend_generation+=1
        self.status.setText('Resend requested · next check')

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
                if self.dialog and profile!=self.dialog.profile:
                    self.dialog.error.setText('Avatar changed. Reopen this mapping before saving.');self.dialog.error.show()
                self.profile=profile;self.profile_label.setText('Avatar · '+profile[-8:] if profile!='manual' else 'Shared mappings · avatar discovery unavailable')
                self.measure_count.setText(f'{len(self.sources)} measurements');self.refresh_cards()

    def closeEvent(self,event):
        self.stop_event.set();self.timer.stop();event.accept()

    def sync(self, stop):
        last_browse = 0
        known_port = None
        sender=mapping.ChangedSender()
        was_detected=False
        ever_detected=False
        reconnect=0
        last_generation=0
        last_profile='manual'
        while not stop.is_set():
            with self.lock: config = copy.deepcopy(self.config)
            try:
                browse = time.monotonic()-last_browse>30
                discovery = mapping.discover(config,known_port,browse=browse)
                if browse: last_browse=time.monotonic()
                if discovery: known_port=discovery['queryPort']
                if discovery and not was_detected:reconnect+=1
                was_detected=bool(discovery)
                self.events.put(('connection',bool(discovery)))
                with self.lock:requested_generation=self.resend_generation
                if not discovery and ever_detected and requested_generation==last_generation:
                    self.events.put(('status','VRChat discovery lost · waiting to reconnect'))
                    stop.wait(core.DEFAULT_POLL_SECONDS)
                    continue
                ever_detected=ever_detected or bool(discovery)
                profile = last_profile if not discovery and ever_detected else mapping.profile_key(discovery)
                last_profile=profile
                with self.lock:
                    if profile not in self.config['profiles']:
                        self.config['profiles'][profile]=[mapping.eye_height_preset()]
                        core.save_config(self.config,settings_path())
                    config=copy.deepcopy(self.config)
                    generation=self.resend_generation
                sender.begin((config['oscHost'],config['oscPort'],profile,known_port,reconnect,generation))
                sources = mapping.fetch_measurements(config)
                self.events.put(('data',sources,discovery))
                sent, skipped, active = 0, 0, 0
                source_map = {s['id']:s for s in sources}
                items=config.get('profiles',{}).get(profile,[])
                sender.prune({item['target'] for item in items if item.get('enabled',True) and mapping.can_send(item,source_map,discovery)})
                for item in items:
                    if stop.is_set(): break
                    if not item.get('enabled',True): continue
                    if not mapping.can_send(item,source_map,discovery):
                        skipped+=1
                        continue
                    try:
                        if sender.send(config,item,source_map[item['source']]):sent+=1
                        active+=1
                    except (OSError,ValueError,KeyError,TypeError,OverflowError): skipped+=1
                last_generation=generation
                self.events.put(('status',f"{active} active mapping{'s' if active != 1 else ''} · "+(f'{sent} updated' if sent else 'Up to date')+(f' · {skipped} unavailable' if skipped else '')))
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
