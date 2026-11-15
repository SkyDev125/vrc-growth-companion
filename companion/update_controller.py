"""UI-thread state, background network work, and explicit update installation."""
import queue
import sys
import threading
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtGui import QGuiApplication
import updater


class UpdateController(QObject):
    changed = Signal()

    def __init__(self, directory, enabled=True, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.events = queue.Queue()
        self.info = None
        self.busy = False
        self.current = updater.build_info()
        self.state = {'version': self.current['version'], 'available': False, 'busy': False,
                      'message': '', 'progress': -1}
        result = directory / 'install-result.txt'
        if result.exists():
            message = result.read_text(encoding='utf-8-sig').strip()
            self.state['message'] = 'Updated successfully' if message == 'ok' else message
            result.unlink(missing_ok=True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drain)
        self.timer.start(100)
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check)
        if enabled and getattr(sys, 'frozen', False):
            self.check_timer.start(6 * 60 * 60 * 1000)
            QTimer.singleShot(4000, self.check)

    def notify(self, **changes):
        self.state.update(changes)
        self.changed.emit()

    def check(self):
        if self.busy: return
        self.busy = True
        self.notify(busy=True, message='Checking for updates…', progress=-1)
        def work():
            try: self.events.put(('checked', updater.check()))
            except Exception as error: self.events.put(('error', 'Could not check for updates. Try again later.'))
        threading.Thread(target=work, daemon=True).start()

    def install(self):
        if self.busy or not self.info: return
        if not getattr(sys, 'frozen', False):
            self.notify(message='Install a packaged release to use automatic updates.')
            return
        self.busy = True
        self.notify(busy=True, message='Downloading update…', progress=0)
        info = self.info
        def work():
            try:
                target = updater.install_target()
                package = updater.download(info, self.directory,
                    lambda n: self.events.put(('progress', n)))
                updater.verify_package(package, info['assets'][updater.platform_key()])
                updater.launch_helper(package, target, self.directory)
                self.events.put(('quit', None))
            except Exception as error: self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def drain(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == 'checked':
                self.info = value
                self.busy = False
                self.notify(busy=False, available=bool(value), progress=-1,
                            message=('Update available · ' + value['version']) if value else 'You’re up to date')
            elif kind == 'progress': self.notify(progress=value)
            elif kind == 'error':
                self.busy = False
                self.notify(busy=False, message=value, progress=-1)
            elif kind == 'quit': QGuiApplication.instance().quit()

    def close(self):
        self.timer.stop()
        self.check_timer.stop()
