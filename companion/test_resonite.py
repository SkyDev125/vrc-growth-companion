import copy,socket,struct,unittest
from unittest.mock import patch
import avatar_mapping as mapping
import resonite


class ResoniteTests(unittest.TestCase):
    def test_ratio_preset_and_real_udp_packet_deduplication(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(.15)
            config={'oscHost':'127.0.0.1','oscPort':receiver.getsockname()[1]}
            item=resonite.scale_preset();sender=mapping.ChangedSender()
            self.assertTrue(sender.send(config,item,{'value':3,'originalValue':2}))
            data=receiver.recv(1024)
            self.assertTrue(data.startswith(b'/midsden/scale\0'));self.assertIn(b',f\0\0',data)
            self.assertEqual(struct.unpack('>f',data[-4:])[0],1.5)
            self.assertFalse(sender.send(config,item,{'value':3,'originalValue':2}))
            with self.assertRaises(socket.timeout):receiver.recv(1024)

    def test_custom_units_and_large_values_are_not_eyeheight_clamped(self):
        item={**resonite.scale_preset(),'source':'capacity','target':'/custom/capacity','mode':'value'}
        self.assertEqual(mapping.mapped_value(item,{'value':25000,'unit':'L'}),25000)
        self.assertEqual(mapping.mapped_value(resonite.scale_preset(),{'value':25000,'originalValue':1}),25000)
        for target in ('','/avatar/eyeheight','/foo/*','/foo bar'):
            with self.assertRaises(ValueError):mapping.validate_mapping({**item,'target':target})
        with self.assertRaises(ValueError):mapping.validate_mapping({**item,'platform':'vrchat'})

    def test_boolean_receivers_get_integer_zero_one(self):
        for value in (False,True):
            packet=mapping.encode_parameter('/midsden/toggle','bool',value,'resonite')
            self.assertIn(b',i\0\0',packet)
            self.assertEqual(struct.unpack('>i',packet[-4:])[0],int(value))
        self.assertIn(b',T\0\0',mapping.encode_parameter('/avatar/parameters/Toggle','bool',True))

    def test_generated_paths_are_stable_and_guide_defines_calibration(self):
        source={'id':'tail length','name':'Tail','unit':'cm'}
        options=resonite.parameter_options([source])
        self.assertEqual(options[1]['address'],'/midsden/measurements/tail%20length')
        text=resonite.setup_text({'oscHost':'127.0.0.1','oscPort':9002},[resonite.scale_preset()],[{'id':'height','name':'Height','unit':'m'}])
        for required in ('BaselineScale','AnimationTime = 0','not height in metres','uninitialized','unverified'):
            if required=='unverified':self.assertIn('does not confirm',text)
            else:self.assertIn(required,text)
