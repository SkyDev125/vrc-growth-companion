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
  self.root.setWidth(800);self.root.setHeight(430);self.bridge.openEditor(-1);QTest.qWait(220)
  popup=self.root.findChild(QObject,'mappingEditor')
  self.assertLessEqual(popup.property('height'),self.root.height()-40)
  self.bridge.sources[0]['value']=4;self.bridge.stateChanged.emit();self.app.processEvents()
  self.assertEqual(self.evaluate(self.root,'state.rows[0].output'),'4')
  self.assertFalse(self.warnings,self.warnings)

 def test_editor_header_and_save_stay_visible_when_body_scrolls(self):
  self.root.setWidth(800);self.root.setHeight(430);self.bridge.openEditor(-1);QTest.qWait(220)
  save=self.root.findChild(QObject,'saveMapping')
  header=self.root.findChild(QObject,'editorHeader')
  scroll=self.root.findChild(QObject,'editorFieldsScroll')
  for item in (save,header):
   point=item.mapToScene(item.boundingRect().center())
   self.assertGreater(point.y(),0)
   self.assertLess(point.y(),self.root.height())
  header_y=header.mapToScene(header.boundingRect().center()).y()
  save_y=save.mapToScene(save.boundingRect().center()).y()
  self.evaluate(scroll,'contentItem.contentY = Math.max(0, contentItem.contentHeight - contentItem.height)')
  self.app.processEvents()
  self.assertAlmostEqual(header.mapToScene(header.boundingRect().center()).y(),header_y,delta=.5)
  self.assertEqual(save.mapToScene(save.boundingRect().center()).y(),save_y)
 def test_default_editor_fits_without_scroll_and_hovered_parameter_selects(self):
  self.bridge.openEditor(-1);QTest.qWait(200)
  scroll=self.root.findChild(QObject,'editorFieldsScroll')
  self.assertLessEqual(self.evaluate(scroll,'contentItem.contentHeight'),scroll.property('availableHeight')+1)
  arrow=self.root.findChild(QObject,'parameterDropdown')
  chevron=self.root.findChild(QObject,'parameterChevron')
  self.assertAlmostEqual(chevron.mapToScene(chevron.boundingRect().center()).y(),arrow.mapToScene(arrow.boundingRect().center()).y(),places=1)
  QTest.mouseClick(self.root,Qt.MouseButton.LeftButton,pos=arrow.mapToScene(arrow.boundingRect().center()).toPoint());QTest.qWait(150)
  listing=self.root.findChild(QObject,'parameterResults')
  first=listing.property('contentItem').childItems()[0]
  center=first.mapToScene(first.boundingRect().center()).toPoint()
  QTest.mouseMove(self.root,center);QTest.qWait(50)
  self.assertTrue(first.property('hovered'))
  QTest.mouseClick(self.root,Qt.MouseButton.LeftButton,pos=center);self.app.processEvents()
  picker=self.root.findChild(QObject,'parameterSearch').parentItem()
  self.assertEqual(picker.property('address'),'/avatar/eyeheight')
  self.assertFalse(self.warnings,self.warnings)

 def test_single_parameter_highlight_is_fully_inside_list(self):
  self.bridge.discovery={'parameters':{},'allParameters':{}}
  self.bridge.openEditor(0);QTest.qWait(200)
  arrow=self.root.findChild(QObject,'parameterDropdown')
  QTest.mouseClick(self.root,Qt.MouseButton.LeftButton,pos=arrow.mapToScene(arrow.boundingRect().center()).toPoint());QTest.qWait(150)
  listing=self.root.findChild(QObject,'parameterResults')
  first=listing.property('contentItem').childItems()[0]
  QTest.mouseMove(self.root,first.mapToScene(first.boundingRect().center()).toPoint());self.app.processEvents()
  self.assertTrue(first.property('hovered'))
  self.assertGreaterEqual(listing.height()+.1,first.height())
  row_bottom=first.mapToScene(first.boundingRect().bottomRight()).y()
  list_bottom=listing.mapToScene(listing.boundingRect().bottomRight()).y()
  self.assertLessEqual(row_bottom,list_bottom+.1)
  self.assertFalse(self.warnings,self.warnings)

 def test_window_uses_native_frame_and_controls(self):
  flags=self.root.flags()
  self.assertFalse(flags & Qt.WindowType.FramelessWindowHint)
  self.assertTrue(flags & Qt.WindowType.WindowTitleHint)
  self.assertTrue(flags & Qt.WindowType.WindowMinMaxButtonsHint)
  self.assertIsNone(self.root.findChild(QObject,'minimizeWindow'))
  self.assertIsNone(self.root.findChild(QObject,'maximizeWindow'))
  self.assertIsNone(self.root.findChild(QObject,'closeWindow'))
 def test_update_banner_and_controls(self):
  self.bridge.updates.notify(available=True,message='Update available · 1.3.0')
  QTest.qWait(50)
  button=self.root.findChild(QObject,'installUpdate')
  self.assertTrue(button.property('visible'));self.assertTrue(button.property('enabled'))
  self.bridge.updates.notify(busy=True,progress=50,message='Downloading update…')
  QTest.qWait(50)
  self.assertFalse(button.property('enabled'))
  self.assertEqual(self.evaluate(self.root,'state.update.progress'),50)
 def test_mouse_focus_has_no_gold_outline_but_keyboard_focus_does(self):
  settings=self.root.findChild(QObject,'connectionSettings')
  self.root.requestActivate();QTest.qWait(50)
  self.evaluate(settings,'forceActiveFocus(Qt.MouseFocusReason)');self.app.processEvents()
  self.assertFalse(settings.property('visualFocus'))
  QTest.keyClick(self.root,Qt.Key.Key_Tab);self.app.processEvents()
  self.assertTrue(self.root.activeFocusItem().property('visualFocus'))
