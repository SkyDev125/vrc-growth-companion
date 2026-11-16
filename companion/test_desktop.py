import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import copy,json,tempfile,threading
from pathlib import Path
import unittest
from unittest.mock import patch
try:
 from PySide6.QtGui import QGuiApplication
 import desktop
except ImportError:
 desktop=None

@unittest.skipIf(desktop is None,'Qt build dependency unavailable')
class DesktopTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QGuiApplication.instance() or QGuiApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.patch=patch.object(desktop,'settings_path',return_value=Path(self.temp.name)/'config.json');self.patch.start()
  self.window=desktop.CompanionWindow(auto_start=False)
  self.window.sources=[{'id':'height','name':'Height','unit':'m','value':3,'originalValue':2}]
 def tearDown(self):self.window.close();self.patch.stop();self.temp.cleanup()
 def test_edit_and_save_existing_eye_height(self):
  self.window.openEditor(0)
  item=self.window.editor['item']
  self.assertEqual(self.window.saveMapping(json.dumps(item)),'')
  self.assertEqual(self.window.config['profiles']['manual'][0]['target'],'/avatar/eyeheight')
 def test_manual_target_and_duplicate_validation(self):
  self.window.openEditor(-1);item=self.window.editor['item'];item['target']='TailSize'
  self.assertEqual(self.window.saveMapping(json.dumps(item)),'')
  self.assertEqual(self.window.config['profiles']['manual'][-1]['target'],'/avatar/parameters/TailSize')
  self.window.openEditor(-1)
  self.assertIn('already',self.window.saveMapping(json.dumps(item)))
 def test_preset_can_be_removed_and_restored(self):
  self.window.removeMapping(0);self.assertEqual(self.window.config['profiles']['manual'],[])
  self.window.eyeHeightPreset()
  self.assertEqual(self.window.saveMapping(json.dumps(self.window.editor['item'])),'')
  self.assertEqual(len(self.window.config['profiles']['manual']),1)
 def test_avatar_change_preserves_draft_and_prevents_wrong_profile_save(self):
  self.window.openEditor(0);draft=copy.deepcopy(self.window.editor['item'])
  self.window.config['profiles']['avtr_b']=[]
  self.window.events.put(('data',self.window.sources,{'avatar':'avtr_b','parameters':{}}));self.window.drain()
  self.assertEqual(self.window.profile,'avtr_b');self.assertEqual(self.window.editor['item'],draft)
  self.assertIn('Avatar changed',self.window.saveMapping(json.dumps(draft)))
 def test_readonly_parameters_are_visible_but_cannot_be_saved(self):
  self.window.discovery={'parameters':{},'allParameters':{'/avatar/parameters/Velocity':{'kind':'float','writable':False}}}
  self.window.openEditor(-1)
  params=json.loads(self.window.editorJson)['parameters']
  self.assertFalse(params[1]['writable'])
  item=self.window.editor['item'];item['target']=params[1]['address']
  self.assertIn('writable',self.window.saveMapping(json.dumps(item)))
 def test_preview_follows_values_and_disabled_state(self):
  self.assertEqual(json.loads(self.window.stateJson)['rows'][0]['output'],'3')
  self.window.sources[0]['value']=4
  self.assertEqual(json.loads(self.window.stateJson)['rows'][0]['output'],'4')
  self.window.enableMapping(0,False)
  self.assertEqual(json.loads(self.window.stateJson)['rows'][0]['output'],'Off')
 def test_connection_settings_and_resend(self):
  self.assertNotEqual(self.window.saveConnection('8.8.8.8','9000'),'')
  self.assertEqual(self.window.saveConnection('127.0.0.1','9010'),'')
  self.assertEqual(self.window.config['oscPort'],9010)
  self.window.resend();self.assertEqual(self.window.resend_generation,1)
 def test_updates_work_while_syncing_is_paused(self):
  self.window.stop_event.set();self.window.paused=True
  self.window.updates.events.put(('checked',{'version':'1.3.0'}))
  self.window.updates.drain()
  state=json.loads(self.window.stateJson)
  self.assertTrue(state['paused']);self.assertTrue(state['update']['available'])
  self.assertFalse(state['update']['busy'])
  self.window.updates.events.put(('error','Download failed; please retry'))
  self.window.updates.drain()
  self.assertIn('retry',json.loads(self.window.stateJson)['update']['message'])
 def test_growth_mode_persists_and_finish_command(self):
  self.assertFalse(json.loads(self.window.stateJson)['smoothGrowth'])
  self.window.setSmoothGrowth(True)
  self.assertTrue(desktop.core.load_config(Path(self.temp.name)/'config.json')['smoothGrowth'])
  self.window.finishGrowth();self.assertEqual(self.window.finish_generation,1)
 def test_growth_preferences_persist_validate_and_rollback_on_write_failure(self):
  options={'speed':2,'curve':'steady','maxDuration':30}
  self.assertEqual(self.window.saveGrowthOptions(json.dumps(options)),'')
  self.assertEqual(desktop.core.load_config(Path(self.temp.name)/'config.json')['growthOptions'],options)
  self.assertNotEqual(self.window.saveGrowthOptions('{"speed":0}'),'')
  self.assertEqual(self.window.config['growthOptions'],options)
  with patch.object(desktop.core,'save_config',side_effect=OSError('disk unavailable')):
   self.assertIn('disk unavailable',self.window.saveGrowthOptions('{}'))
  self.assertEqual(self.window.config['growthOptions'],options)
 def test_worker_sends_changes_avatar_switch_and_reconnect_only(self):
  import avatar_mapping as m
  a={'avatar':'avtr_a','queryPort':9001,'parameters':{}}
  b={'avatar':'avtr_b','queryPort':9001,'parameters':{}}
  states=[(a,3),(a,3),(a,4),(b,4),(b,4),(None,4),(b,4),(b,4)]
  position=[0];stop=threading.Event();writes=[]
  def wait(_):
   position[0]+=1
   if position[0]>=len(states):stop.set()
  def sources(_):return [{'id':'height','name':'Height','value':states[position[0]][1],'originalValue':2,'unit':'m'}]
  with patch.object(stop,'wait',side_effect=wait),patch.object(m,'discover',side_effect=lambda *_a,**_k:copy.deepcopy(states[position[0]][0])),patch.object(m,'fetch_measurements',side_effect=sources),patch.object(m,'send_mapping',side_effect=lambda c,i,s:writes.append(s['value'])):
   self.window.sync(stop)
  self.assertEqual(writes,[3,4,4,4])
 def test_resonite_switch_preserves_mappings_ports_and_persists(self):
  original=copy.deepcopy(self.window.config['profiles']['manual'])
  self.assertEqual(self.window.saveConnection('127.0.0.1','19000'),'')
  self.assertEqual(self.window.setTargetApp('resonite'),'')
  self.assertEqual(self.window.profile,'resonite');self.assertEqual(self.window.config['oscPort'],9002)
  self.window.openEditor(0)
  self.assertEqual(json.loads(self.window.editorJson)['parameters'][0]['address'],'/midsden/scale')
  self.assertEqual(self.window.saveMapping(json.dumps(self.window.editor['item'])),'')
  self.assertEqual(self.window.saveConnection('127.0.0.1','19002'),'')
  self.assertEqual(self.window.setTargetApp('vrchat'),'')
  self.assertEqual(self.window.config['oscPort'],19000)
  self.assertEqual(self.window.config['profiles']['manual'],original)
  self.assertEqual(self.window.setTargetApp('resonite'),'')
  self.assertEqual(self.window.config['oscPort'],19002)
  saved=desktop.core.load_config(Path(self.temp.name)/'config.json')
  self.assertEqual(saved['targetApp'],'resonite');self.assertEqual(saved['oscDestinations']['vrchat']['port'],19000)
  self.window.events.put(('connection',True));self.window.drain()
  self.assertFalse(self.window.detected)
 def test_resonite_worker_never_uses_vrchat_discovery(self):
  self.window.setTargetApp('resonite');stop=threading.Event();writes=[]
  with patch.object(stop,'wait',side_effect=lambda _:stop.set()),patch.object(desktop.mapping,'discover') as discover,patch.object(desktop.mapping,'fetch_measurements',return_value=self.window.sources),patch.object(desktop.mapping,'send_mapping',side_effect=lambda c,i,s:writes.append(i)):
   self.window.sync(stop)
  discover.assert_not_called()
  self.assertEqual(len(writes),1);self.assertEqual(writes[0]['target'],'/midsden/scale')
  self.assertEqual(writes[0]['platform'],'resonite')
 def test_chilloutvr_profiles_preset_and_game_switching(self):
  import chilloutvr
  original=copy.deepcopy(self.window.config['profiles']['manual'])
  self.window.saveConnection('127.0.0.1','19000')
  self.assertEqual(self.window.setTargetApp('chilloutvr'),'')
  self.assertEqual(self.window.config['profiles'][self.window.profile],[])
  self.window.eyeHeightPreset();item=self.window.editor['item']
  self.assertEqual(item['target'],'');self.assertEqual(item['mode'],'range')
  self.assertNotIn('/avatar/eyeheight',[p['address'] for p in json.loads(self.window.editorJson)['parameters']])
  item['target']='ScaleSlider';item.update(inputMin=1,inputMax=5,outputMin=0,outputMax=1)
  self.assertEqual(self.window.saveMapping(json.dumps(item)),'')
  saved=copy.deepcopy(self.window.config['profiles'][self.window.profile])
  self.window.saveConnection('127.0.0.1','19003')
  self.window.setTargetApp('resonite');self.window.setTargetApp('vrchat')
  self.assertEqual(self.window.config['oscPort'],19000)
  self.assertEqual(self.window.config['profiles']['manual'],original)
  self.window.setTargetApp('chilloutvr')
  self.assertEqual(self.window.config['oscPort'],19003)
  self.assertEqual(self.window.config['profiles'][self.window.profile],saved)
  self.assertEqual(desktop.core.load_config(Path(self.temp.name)/'config.json')['targetApp'],'chilloutvr')
 def test_queued_other_game_discovery_is_ignored(self):
  self.window.setTargetApp('chilloutvr')
  self.window.events.put(('connection',True,'vrchat'))
  self.window.events.put(('data',[],{'avatar':'avtr_old','parameters':{}},'vrchat'))
  self.window.events.put(('status','Old game status','vrchat'));self.window.drain()
  self.assertEqual(self.window.profile,'chilloutvr:manual');self.assertFalse(self.window.detected)
  self.assertEqual(len(self.window.sources),1)
  self.assertNotEqual(self.window.status,'Old game status')
 def test_chilloutvr_worker_uses_advertised_port_and_matching_profile(self):
  from test_chilloutvr import query_tree
  d=desktop.mapping.parse_tree(query_tree(),'chilloutvr');d.update(oscPort=19003,queryPort=49000)
  self.window.setTargetApp('chilloutvr')
  profile=desktop.mapping.profile_key(d,'chilloutvr')
  self.window.config['profiles'][profile]=[{**desktop.chilloutvr.scale_mapping(),'target':'/avatar/parameters/ScaleSlider'}]
  stop=threading.Event();writes=[]
  with patch.object(stop,'wait',side_effect=lambda _:stop.set()),patch.object(desktop.mapping,'discover',return_value=d),patch.object(desktop.mapping,'fetch_measurements',return_value=self.window.sources),patch.object(desktop.mapping,'send_mapping',side_effect=lambda c,i,s:writes.append((c['oscPort'],i['platform']))):
   self.window.sync(stop)
  self.assertEqual(writes,[(19003,'chilloutvr')])
  self.window.drain()
  self.assertEqual(self.window.profile,profile);self.assertTrue(self.window.detected)
  self.assertEqual(self.window.config['oscDestinations']['chilloutvr']['port'],19003)
 def test_game_change_during_discovery_discards_old_result(self):
  stop=threading.Event();writes=[]
  def discover(*args,**kwargs):
   self.window.setTargetApp('chilloutvr');stop.set()
   return {'avatar':'avtr_old','queryPort':9001,'parameters':{}}
  with patch.object(desktop.mapping,'discover',side_effect=discover),patch.object(desktop.mapping,'fetch_measurements') as fetch,patch.object(desktop.mapping,'send_mapping',side_effect=lambda *args:writes.append(args)):
   self.window.sync(stop)
  fetch.assert_not_called();self.assertEqual(writes,[])
  self.window.drain();self.assertEqual(self.window.profile,'chilloutvr:manual')
  self.assertNotIn('avtr_old',self.window.config['profiles'])
