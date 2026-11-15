import subprocess
import unittest
from unittest.mock import patch
from macos_image import run_image_tool

class ImageToolTests(unittest.TestCase):
 def test_retries_transient_busy_only(self):
  busy=subprocess.CompletedProcess(['hdiutil'],1,'','Resource busy')
  success=subprocess.CompletedProcess(['hdiutil'],0,'','')
  with patch('macos_image.subprocess.run',side_effect=[busy,success]) as run,patch('macos_image.time.sleep') as sleep:
   run_image_tool(['create','test.dmg'])
   self.assertEqual(run.call_count,2);sleep.assert_called_once_with(1)
 def test_unrelated_failure_is_not_retried(self):
  failure=subprocess.CompletedProcess(['hdiutil'],1,'','No space left on device')
  with patch('macos_image.subprocess.run',return_value=failure) as run,patch('macos_image.time.sleep'):
   with self.assertRaises(subprocess.CalledProcessError):run_image_tool(['create','test.dmg'])
   self.assertEqual(run.call_count,1)
 def test_force_detach_is_limited_to_owned_cleanup(self):
  busy=subprocess.CompletedProcess(['hdiutil'],16,'','Resource busy')
  success=subprocess.CompletedProcess(['hdiutil'],0,'','')
  with patch('macos_image.subprocess.run',side_effect=[busy,busy,busy,busy,success]) as run,patch('macos_image.time.sleep'):
   run_image_tool(['detach','/test-owned-mount'],force_detach=True)
   self.assertEqual(run.call_args.args[0],['hdiutil','detach','-force','/test-owned-mount'])
