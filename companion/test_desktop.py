import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
try:
 from PySide6.QtWidgets import QApplication
 import desktop
except ImportError:
 desktop=None

@unittest.skipIf(desktop is None,'Qt build dependency unavailable')
class DesktopTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=QApplication.instance() or QApplication([])
  cls.app.setStyleSheet(desktop.STYLE)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.patch=patch.object(desktop,'settings_path',return_value=Path(self.temp.name)/'config.json');self.patch.start()
  self.window=desktop.CompanionWindow(auto_start=False)
  self.window.sources=[{'id':'height','name':'Height','unit':'m','value':3,'originalValue':2}]
 def tearDown(self):
  self.window.close();self.patch.stop();self.temp.cleanup()
 def test_edit_and_save_existing_eye_height(self):
  d=desktop.MappingDialog(self.window,0);d.save()
  self.assertEqual(d.result(),d.DialogCode.Accepted)
  self.assertEqual(self.window.config['profiles']['manual'][0]['target'],'/avatar/eyeheight')
 def test_manual_target_and_duplicate_validation(self):
  d=desktop.MappingDialog(self.window)
  d.target.setEditText('TailSize');d.save()
  self.assertEqual(self.window.config['profiles']['manual'][-1]['target'],'/avatar/parameters/TailSize')
  other=desktop.MappingDialog(self.window);other.target.setEditText('TailSize');other.save()
  self.assertIn('already',other.error.text())
 def test_preset_can_be_removed_and_restored(self):
  self.window.remove_mapping(0);self.assertEqual(self.window.config['profiles']['manual'],[])
  self.window.add_eye_height();self.window.dialog.save()
  self.assertEqual(len(self.window.config['profiles']['manual']),1)
 def test_status_and_avatar_change(self):
  self.window.events.put(('connection',True));self.window.drain()
  self.assertIn('detected',self.window.connection.text())
  self.window.open_editor(0)
  self.window.config['profiles']['avtr_b']=[]
  self.window.events.put(('data',self.window.sources,{'avatar':'avtr_b','parameters':{}}));self.window.drain()
  self.assertEqual(self.window.profile,'avtr_b');self.assertIsNone(self.window.dialog)
