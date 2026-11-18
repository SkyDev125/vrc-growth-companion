import socket,struct,unittest
import avatar_mapping as mapping
import resonite


class ResoniteTests(unittest.TestCase):
    def test_height_and_legacy_ratio_packets_keep_their_units(self):
        height = resonite.height_preset()
        legacy = {**height, 'target': '/midsden/scale', 'mode': 'ratio'}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1', 0))
            receiver.settimeout(.15)
            config = {'oscHost': '127.0.0.1', 'oscPort': receiver.getsockname()[1]}
            source = {'value': 3, 'originalValue': 2, 'unit': 'm'}
            sender = mapping.ChangedSender()
            for item, path, expected in ((height, b'/midsden/height', 3), (legacy, b'/midsden/scale', 1.5)):
                self.assertTrue(sender.send(config, item, source))
                packet = receiver.recv(1024)
                self.assertTrue(packet.startswith(path + b'\0'))
                self.assertIn(b',f\0\0', packet)
                self.assertEqual(struct.unpack('>f', packet[-4:])[0], expected)
                self.assertFalse(sender.send(config, item, source))
            with self.assertRaises(socket.timeout):
                receiver.recv(1024)

    def test_custom_units_and_large_values_are_not_eyeheight_clamped(self):
        item={**resonite.height_preset(),'source':'capacity','target':'/custom/capacity','mode':'value'}
        self.assertEqual(mapping.mapped_value(item,{'value':25000,'unit':'L'}),25000)
        self.assertEqual(mapping.mapped_value(resonite.height_preset(),{'value':25000,'originalValue':1}),25000)
        for target in ('','/avatar/eyeheight','/foo/*','/foo bar'):
            with self.assertRaises(ValueError):mapping.validate_mapping({**item,'target':target})
        with self.assertRaises(ValueError):mapping.validate_mapping({**item,'platform':'vrchat'})

    def test_boolean_receivers_get_integer_zero_one(self):
        for value in (False,True):
            packet=mapping.encode_parameter('/midsden/toggle','bool',value,'resonite')
            self.assertIn(b',i\0\0',packet)
            self.assertEqual(struct.unpack('>i',packet[-4:])[0],int(value))
        self.assertIn(b',T\0\0',mapping.encode_parameter('/avatar/parameters/Toggle','bool',True))

    def test_generated_paths_are_stable(self):
        source = {'id': 'tail length', 'name': 'Tail', 'unit': 'cm'}
        options = resonite.parameter_options([source])
        self.assertEqual(options[-1]['address'], '/midsden/measurements/tail%20length')
