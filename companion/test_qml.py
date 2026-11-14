import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
try:
 from PySide6.QtCore import QObject,QUrl,Qt,QPoint
 from PySide6.QtGui import QGuiApplication
 from PySide6.QtQuick import QQuickWindow,QSGRendererInterface
 from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression
 from PySide6.QtTest import QTest
 import desktop
except ImportError:desktop=None

@unittest.skipIf(desktop is None,'Qt build dependency unavailable')
class QuickInterfaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
  cls.app=QGuiApplication.instance() or QGuiApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(desktop,'settings_path',return_value=Path(self.temp.name)/'config.json');self.patch.start()
  self.bridge=desktop.CompanionWindow(False)
  self.bridge.sources=[{'id':'height','name':'Height','unit':'m','value':3,'originalValue':2}]
  self.bridge.discovery={'parameters':{'/avatar/parameters/TailSize':'float'},'allParameters':{'/avatar/parameters/TailSize':{'kind':'float','writable':True},'/avatar/parameters/Velocity':{'kind':'float','writable':False}}}
  self.engine=QQmlApplicationEngine();self.warnings=[];self.engine.warnings.connect(lambda entries:self.warnings.extend(str(x) for x in entries))
  self.engine.rootContext().setContextProperty('bridge',self.bridge)
  self.engine.load(QUrl.fromLocalFile(str(desktop.ui_path()/'Main.qml')))
  self.assertTrue(self.engine.rootObjects());self.root=self.engine.rootObjects()[0];QTest.qWait(50)
 def tearDown(self):
  self.bridge.close();self.root.close();self.engine.deleteLater();self.app.processEvents();self.patch.stop();self.temp.cleanup()
 def evaluate(self,obj,expression):
  expr=QQmlExpression(self.engine.rootContext(),obj,expression);result=expr.evaluate()
  self.assertFalse(expr.hasError(),expr.error().toString());return result[0] if isinstance(result,tuple) else result
 def test_single_dropdown_browses_searches_and_saves(self):
  self.bridge.openEditor(-1);QTest.qWait(200)
  picker=self.root.findChild(QObject,'parameterSearch').parentItem()
  arrow=self.root.findChild(QObject,'parameterDropdown')
  point=arrow.mapToScene(arrow.boundingRect().center()).toPoint()
  QTest.mouseClick(self.root,Qt.MouseButton.LeftButton,pos=point);QTest.qWait(150)
  self.assertEqual(self.evaluate(picker,'filtered.length'),3)
  self.evaluate(picker,'browsingAll=false; children[0].text="SIZE"; filter()')
  self.assertEqual(self.evaluate(picker,'filtered.length'),1)
  self.evaluate(picker,'choose(0)')
  self.evaluate(self.root,'saveEditor()')
  self.assertEqual(self.bridge.config['profiles']['manual'][-1]['target'],'/avatar/parameters/TailSize')
  self.assertFalse(self.warnings,self.warnings)
 def test_editor_fits_small_window_and_state_updates(self):
  self.root.setWidth(800);self.root.setHeight(430);self.bridge.openEditor(-1);QTest.qWait(150)
  popup=self.root.findChild(QObject,'mappingEditor')
  self.assertLessEqual(popup.property('height'),398)
  self.bridge.sources[0]['value']=4;self.bridge.stateChanged.emit();self.app.processEvents()
  self.assertEqual(self.evaluate(self.root,'state.rows[0].output'),'4')
  self.assertFalse(self.warnings,self.warnings)
