"""Qt Quick desktop UI backed by the existing change-only OSC worker."""
import copy
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
from PySide6.QtCore import QObject,Property,Signal,Slot,QTimer,QUrl
from PySide6.QtGui import QGuiApplication,QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow,QSGRendererInterface
import vrchat_companion as core
import avatar_mapping as mapping
from measurement_format import format_measurement
from update_controller import UpdateController
from smooth_growth import MotionSender
from growth_options import normalize as growth_options


def settings_path():
    if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'MidsDenCompanion/config.json'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/MidsDenCompanion/config.json'
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'mids-den-companion/config.json'


def ui_path():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'ui'


class CompanionWindow(QObject):
    stateChanged=Signal()
    editorChanged=Signal()
    def __init__(self,auto_start=True):
        super().__init__()
        self.events=queue.Queue();self.lock=threading.Lock();self.stop_event=threading.Event();self.worker=None
        self.sources=[];self.discovery=None;self.profile='manual';self.resend_generation=0
        self.motion_epoch=0;self.finish_generation=0;self.motion={'active':False,'outputs':{}}
        self.detected=False;self.paused=False;self.status='Ready';self.editor=None;self.editor_error=''
        try:self.config=core.load_config(settings_path())
        except (OSError,ValueError):self.config={'serverUrl':core.DEFAULT_URL,'oscHost':'127.0.0.1','oscPort':9000,'oscQueryPort':9001}
        mapping.migrate_profiles(self.config)
        self.updates=UpdateController(settings_path().parent/'updates',
            enabled=auto_start and not os.environ.get('MIDSDEN_DISABLE_UPDATE_CHECKS'),parent=self)
        self.updates.changed.connect(self.stateChanged)
        self.timer=QTimer(self);self.timer.timeout.connect(self.drain);self.timer.start(100)
        if auto_start:self.start()

    def persist(self):
        with self.lock:core.save_config(self.config,settings_path())

    @Property(str,notify=stateChanged)
    def stateJson(self):
        sources={s['id']:s for s in self.sources};rows=[]
        modes={'value':'Current value','ratio':'Growth ratio','range':'Mapped range','threshold':'On / off'}
        for item in self.config['profiles'].get(self.profile,[]):
            source=sources.get(item['source']);enabled=item.get('enabled',True)
            output='Waiting';health='waiting'
            if not enabled:output='Off';health='off'
            elif source and mapping.can_send(item,sources,self.discovery):
                try:
                    value=mapping.mapped_value(item,source)
                    output=('On' if value else 'Off') if isinstance(value,bool) else f'{value:.4g}'
                    health='ready'
                    if item['target'] in self.motion['outputs']:
                        value=self.motion['outputs'][item['target']]
                        output=('On' if value else 'Off') if isinstance(value,bool) else f'{value:.4g}'
                except (ValueError,KeyError,TypeError,OverflowError):output='Invalid';health='error'
            elif source:output='Unavailable';health='waiting'
            if item['target']=='/avatar/eyeheight' and (self.discovery or {}).get('scalingAllowed') is False:
                output='Blocked';health='waiting'
            rows.append({'name':source['name'] if source else ('Height' if item['source']=='height' else item['source']),
                'value':format_measurement(source['value'],source['unit']) if source else 'Waiting for website',
                'target':'Eye height' if item['target']=='/avatar/eyeheight' else item['target'].removeprefix(mapping.PREFIX),
                'address':item['target'],'mode':modes[item['mode']],'kind':item['kind'],'mappingEnabled':enabled,'output':output,'health':health})
        return json.dumps({'rows':rows,'detected':self.detected,'paused':self.paused,'status':self.status,
            'profile':self.profile,'sourceCount':len(self.sources),'host':self.config['oscHost'],'port':self.config['oscPort'],
            'update':self.updates.state,'smoothGrowth':self.config.get('smoothGrowth',False),'growthOptions':growth_options(self.config.get('growthOptions')),'motion':self.motion})

    @Slot()
    def checkUpdates(self):self.updates.check()

    @Slot()
    def installUpdate(self):self.updates.install()

    @Property(str,notify=editorChanged)
    def editorJson(self):
        if self.editor is None:return '{}'
        available=(self.discovery or {}).get('allParameters') or {address:{'kind':kind,'writable':True} for address,kind in (self.discovery or {}).get('parameters',{}).items()}
        parameters=[{'name':'Eye height','address':'/avatar/eyeheight','kind':'float','writable':True}]
        parameters.extend({'name':address.removeprefix(mapping.PREFIX),'address':address,'kind':info.get('kind') or 'unsupported',
            'writable':bool(info.get('writable') and info.get('kind') in ('float','int','bool'))} for address,info in sorted(available.items()))
        return json.dumps({**self.editor,'parameters':parameters,'sources':self.sources,'error':self.editor_error})

    @Slot(int)
    def openEditor(self,index):
        items=self.config['profiles'].get(self.profile,[])
        if index>=len(items):return
        item=copy.deepcopy(items[index]) if index>=0 else {'source':self.sources[0]['id'] if self.sources else '',
            'target':'','kind':'float','mode':'range','enabled':True,'inputMin':0,'inputMax':10,'outputMin':0,'outputMax':1,'threshold':1}
        self.editor={'index':index,'profile':self.profile,'item':item};self.editor_error='';self.editorChanged.emit()

    @Slot()
    def eyeHeightPreset(self):
        items=self.config['profiles'].get(self.profile,[])
        index=next((i for i,item in enumerate(items) if item['target']=='/avatar/eyeheight'),-1)
        self.openEditor(index)
        if index<0:self.editor['item']=mapping.eye_height_preset();self.editorChanged.emit()

    @Slot(str,result=str)
    def saveMapping(self,raw):
        try:
            if self.editor is None:raise ValueError('Open a mapping first.')
            if self.editor['profile']!=self.profile:raise ValueError('Avatar changed. Reopen this mapping before saving.')
            item=mapping.validate_mapping(json.loads(raw))
            if item['source'] not in {s['id'] for s in self.sources}:raise ValueError('Choose an available measurement.')
            info=(self.discovery or {}).get('allParameters',{}).get(item['target'])
            if info and (not info['writable'] or info['kind']!=item['kind']):raise ValueError('Choose a writable parameter with the matching type.')
            items=copy.deepcopy(self.config['profiles'].get(self.profile,[]));index=self.editor['index']
            if any(i!=index and other['target']==item['target'] for i,other in enumerate(items)):raise ValueError('This parameter already has a mapping.')
            if index<0:items.append(item)
            else:items[index]=item
            with self.lock:
                previous=self.config['profiles'].get(self.profile,[])
                self.config['profiles'][self.profile]=items
                try:core.save_config(self.config,settings_path())
                except OSError:
                    self.config['profiles'][self.profile]=previous
                    raise
            self.editor=None;self.stateChanged.emit();return ''
        except (ValueError,OSError,KeyError,TypeError) as error:return str(error)

    @Slot(int,bool)
    def enableMapping(self,index,enabled):
        items=self.config['profiles'].get(self.profile,[])
        if not 0<=index<len(items):return
        try:
            with self.lock:items[index]['enabled']=enabled
            self.persist();self.stateChanged.emit()
        except OSError as error:self.status=str(error);self.stateChanged.emit()

    @Slot(int)
    def removeMapping(self,index):
        items=self.config['profiles'].get(self.profile,[])
        if not 0<=index<len(items):return
        with self.lock:items.pop(index)
        self.persist();self.stateChanged.emit()

    @Slot(str,str,result=str)
    def saveConnection(self,host,port):
        try:
            address=core.validate_osc_host(host);number=int(port)
            if not 1<=number<=65535:raise ValueError('Use a port between 1 and 65535.')
            with self.lock:self.config.update(oscHost=address,oscPort=number)
            self.persist();self.discovery=None;self.motion_epoch+=1;self.motion={'active':False,'outputs':{}};self.stateChanged.emit();return ''
        except (ValueError,OSError) as error:return str(error)

    @Slot()
    def resend(self):
        with self.lock:self.resend_generation+=1
        self.status='Resend requested · next check';self.stateChanged.emit()

    @Slot(bool)
    def setSmoothGrowth(self,enabled):
        with self.lock:self.config['smoothGrowth']=enabled
        self.persist();self.stateChanged.emit()

    @Slot(str,result=str)
    def saveGrowthOptions(self,raw):
        try:
            options=growth_options(json.loads(raw),strict=True)
            with self.lock:
                previous=self.config.get('growthOptions')
                self.config['growthOptions']=options
                try:core.save_config(self.config,settings_path())
                except OSError:
                    if previous is None:self.config.pop('growthOptions',None)
                    else:self.config['growthOptions']=previous
                    raise
            self.stateChanged.emit();return ''
        except (OSError,ValueError,TypeError) as error:return str(error)

    @Slot()
    def finishGrowth(self):
        with self.lock:self.finish_generation+=1

    def start(self):
        if self.worker and self.worker.is_alive():QTimer.singleShot(150,self.start);return
        self.persist();self.stop_event=threading.Event();self.worker=threading.Thread(target=self.sync,args=(self.stop_event,),daemon=True);self.worker.start();self.paused=False;self.stateChanged.emit()

    @Slot()
    def toggleRun(self):
        if self.worker and self.worker.is_alive() and not self.stop_event.is_set():
            self.stop_event.set();self.motion={'active':False,'outputs':{}};self.paused=True;self.status='Syncing paused';self.stateChanged.emit()
        else:self.start()

    def drain(self):
        changed=False
        while not self.events.empty():
            event=self.events.get_nowait()
            if self.stop_event.is_set():continue
            changed=True
            if event[0]=='connection':self.detected=event[1]
            elif event[0]=='status':self.status=event[1]
            elif event[0]=='motion':self.motion=event[1]
            else:
                self.sources,self.discovery=event[1:];self.profile=mapping.profile_key(self.discovery)
                if self.editor and self.editor['profile']!=self.profile:
                    self.editor_error='Avatar changed. Reopen this mapping before saving.'
        if changed:self.stateChanged.emit()

    def close(self):self.stop_event.set();self.timer.stop();self.updates.close()

    def sync(self, stop):
        last_browse = 0
        known_port = None
        sender=MotionSender(self,stop)
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
                with self.lock:requested_generation=self.resend_generation;epoch=self.motion_epoch
                if not discovery and ever_detected and requested_generation==last_generation:
                    sender.clear()
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
                    generation=self.resend_generation;epoch=self.motion_epoch
                sources = mapping.fetch_measurements(config)
                if epoch!=self.motion_epoch:continue
                self.events.put(('data',sources,discovery))
                items=config.get('profiles',{}).get(profile,[])
                sender.submit((config['oscHost'],config['oscPort'],profile,known_port,reconnect,generation),config,items,sources,discovery)
                active=sum(i.get('enabled',True) for i in items)
                skipped=0;sent=0
                last_generation=generation
                self.events.put(('status',f"{active} active mapping{'s' if active != 1 else ''} · "+(f'{sent} updated' if sent else 'Up to date')+(f' · {skipped} unavailable' if skipped else '')))
            except (OSError,ValueError,RuntimeError) as error:
                self.events.put(('status',str(error)))
            stop.wait(core.DEFAULT_POLL_SECONDS)
        sender.close()

def style_native_frame(window):
    """Theme our own native Windows frame without replacing its controls."""
    if sys.platform!='win32':return
    import ctypes
    from ctypes import wintypes
    try:
        set_attribute=ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        set_attribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        set_attribute.restype=ctypes.c_long
        hwnd=int(window.winId())
        dark=wintypes.BOOL(True)
        set_attribute(hwnd,20,ctypes.byref(dark),ctypes.sizeof(dark))
        # Windows 11 supports caption colors; older Windows keeps its OS theme.
        for attribute,rgb in ((35,0x001e150f),(36,0x00f7f3f0)):
            color=wintypes.DWORD(rgb)
            set_attribute(hwnd,attribute,ctypes.byref(color),ctypes.sizeof(color))
    except (OSError,AttributeError):
        pass


def main():
    os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
    # A software scene graph keeps the companion independent of the game's GPU.
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    app=QGuiApplication(sys.argv);app.setApplicationName('Mid’s Den Companion');app.setOrganizationName('MidsDen')
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MidsDen.Companion')
    app.setWindowIcon(QIcon(str(ui_path()/'app-icon.svg')))
    smoke='--self-test' in sys.argv
    controller=CompanionWindow(auto_start=not smoke)
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('bridge',controller)
    engine.load(QUrl.fromLocalFile(str(ui_path()/'Main.qml')))
    if not engine.rootObjects():raise RuntimeError('The companion interface could not load.')
    window=engine.rootObjects()[0]
    style_native_frame(window)
    app.aboutToQuit.connect(controller.close)
    if smoke:
        import ssl,zeroconf
        import updater
        updater.verify_manifest(json.loads((updater.resources()/'verification-fixture.json').read_text()))
        ssl.create_default_context();core.encode_eyeheight_packet(1000)
        if sys.platform=='win32':
            from ctypes import wintypes
            get_style=ctypes.windll.user32.GetWindowLongW
            get_style.argtypes=[wintypes.HWND,ctypes.c_int]
            get_style.restype=ctypes.c_long
            style=get_style(int(window.winId()),-16)
            assert style & 0x00c00000 == 0x00c00000, 'Native caption missing'
            assert style & 0x00020000 and style & 0x00010000, 'Native minimize/maximize controls missing'
            assert style & 0x00040000, 'Native resize frame missing'
        controller.openEditor(-1)
        def finish():
            Path(os.environ['MIDSDEN_SMOKE_REPORT']).write_text(json.dumps({'status':'ok','platform':sys.platform}))
            app.quit()
        QTimer.singleShot(500,finish)
    sys.exit(app.exec())

if __name__=='__main__':main()
